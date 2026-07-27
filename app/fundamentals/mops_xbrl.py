"""MOPS 官方季度 XBRL 整批檔解析。

此模組只處理離線下載與正規化；API、排名與訓練流程不得直接呼叫外部來源。
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime, timezone
from html import unescape
from pathlib import Path
import re
from typing import Any, Iterable
from urllib.parse import urlencode
from zipfile import ZipFile

import requests

from app.fundamentals.metrics import compute_financial_metrics


MOPS_XBRL_PAGE = "https://mopsov.twse.com.tw/mops/web/t203sb02"
MOPS_DOWNLOAD_ENDPOINT = "https://mopsov.twse.com.tw/server-java/FileDownLoad"
PERIOD_RE = re.compile(r"-(?P<stock_id>[0-9A-Za-z]+)-(?P<period>\d{4}Q[1-4])\.html$", re.IGNORECASE)
ROW_RE = re.compile(r"<tr\b[^>]*>(?P<body>.*?)</tr>", re.IGNORECASE | re.DOTALL)
ZH_RE = re.compile(r'<span\s+class=["\']zh["\']>(?P<label>.*?)</span>', re.IGNORECASE | re.DOTALL)
FACT_RE = re.compile(
    r"<ix:nonfraction\b(?P<attrs>[^>]*)>(?P<value>.*?)</ix:nonfraction>",
    re.IGNORECASE | re.DOTALL,
)
TAG_RE = re.compile(r"<[^>]+>")
CONTEXT_RE = re.compile(
    r"<(?:[A-Za-z0-9_]+:)?context\b(?P<attrs>[^>]*)>(?P<body>.*?)</(?:[A-Za-z0-9_]+:)?context>",
    re.IGNORECASE | re.DOTALL,
)
START_DATE_RE = re.compile(
    r"<(?:[A-Za-z0-9_]+:)?startdate\b[^>]*>(?P<value>.*?)</(?:[A-Za-z0-9_]+:)?startdate>",
    re.IGNORECASE | re.DOTALL,
)
END_DATE_RE = re.compile(
    r"<(?:[A-Za-z0-9_]+:)?enddate\b[^>]*>(?P<value>.*?)</(?:[A-Za-z0-9_]+:)?enddate>",
    re.IGNORECASE | re.DOTALL,
)
INSTANT_RE = re.compile(
    r"<(?:[A-Za-z0-9_]+:)?instant\b[^>]*>(?P<value>.*?)</(?:[A-Za-z0-9_]+:)?instant>",
    re.IGNORECASE | re.DOTALL,
)

MAX_ZIP_MEMBERS = 10_000
MAX_ZIP_MEMBER_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES = 8 * 1024 * 1024 * 1024

FIELD_LABELS: dict[str, tuple[str, ...]] = {
    "revenue": ("營業收入合計", "收益合計", "營業收入"),
    "gross_profit": ("營業毛利（毛損）淨額", "營業毛利（毛損）"),
    "operating_income": ("營業利益（損失）", "營業利益"),
    "net_income": ("本期淨利（淨損）", "本期稅後淨利（淨損）", "本期淨利"),
    "eps": ("基本每股盈餘合計", "基本每股盈餘（元）", "基本每股盈餘"),
    "current_assets": ("流動資產合計",),
    "current_liabilities": ("流動負債合計",),
    "total_liabilities": ("負債總計",),
    "total_assets": ("資產總計",),
    "equity": ("權益總額", "權益總計", "權益合計"),
    "operating_cash_flow": ("營業活動之淨現金流入（流出）", "營業活動之淨現金流量"),
    "capex": ("取得不動產、廠房及設備", "購置不動產、廠房及設備"),
}


def mops_xbrl_download_url(period: str) -> str:
    """回傳官方季度整批 XBRL ZIP 下載網址。"""

    year, quarter = parse_period(period)
    query = urlencode(
        {
            "step": "9",
            "functionName": "show_file2",
            "fileName": f"tifrs-{year}Q{quarter}.zip",
            "filePath": f"/ifrs/{year}/",
        }
    )
    return f"{MOPS_DOWNLOAD_ENDPOINT}?{query}"


def parse_period(period: str) -> tuple[int, int]:
    match = re.fullmatch(r"(\d{4})Q([1-4])", str(period).strip().upper())
    if not match:
        raise ValueError(f"非法財報季度：{period}")
    return int(match.group(1)), int(match.group(2))


def conservative_available_from(period: str) -> str:
    """以涵蓋特殊發行人的較晚期限作為保守可用日。"""

    year, quarter = parse_period(period)
    if quarter == 1:
        return date(year, 6, 1).isoformat()
    if quarter == 2:
        return date(year, 8, 30).isoformat()
    if quarter == 3:
        return date(year, 11, 30).isoformat()
    return date(year + 1, 5, 1).isoformat()


def completed_periods(start_period: str, end_period: str) -> list[str]:
    start_year, start_quarter = parse_period(start_period)
    end_year, end_quarter = parse_period(end_period)
    start_index = start_year * 4 + start_quarter
    end_index = end_year * 4 + end_quarter
    if start_index > end_index:
        raise ValueError("start_period 不得晚於 end_period")
    return [
        f"{index // 4}Q{index % 4}"
        if index % 4
        else f"{index // 4 - 1}Q4"
        for index in range(start_index, end_index + 1)
    ]


def download_xbrl_zip(period: str, destination_dir: Path, timeout_seconds: int = 180) -> Path:
    """下載單季官方 XBRL ZIP；已存在且可開啟時直接重用。"""

    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"tifrs-{period}.zip"
    if destination.exists() and _valid_zip(destination):
        return destination

    response = requests.get(
        mops_xbrl_download_url(period),
        headers={"User-Agent": "Mozilla/5.0", "Referer": MOPS_XBRL_PAGE},
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    temporary = destination.with_suffix(".zip.part")
    temporary.write_bytes(response.content)
    if not _valid_zip(temporary):
        temporary.unlink(missing_ok=True)
        raise ValueError(f"MOPS {period} 回應不是有效 ZIP")
    temporary.replace(destination)
    return destination


def parse_xbrl_zip(
    zip_path: Path,
    universe: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """解析單季 ZIP；同一股票同時有合併與個別報表時優先合併報表。"""

    selected: dict[str, tuple[int, dict[str, Any]]] = {}
    with ZipFile(zip_path) as archive:
        _validate_zip_resources(archive)
        for info in archive.infolist():
            name = info.filename
            match = PERIOD_RE.search(name)
            if not match:
                continue
            stock_id = match.group("stock_id")
            if universe is not None and stock_id not in universe:
                continue
            priority = 2 if "-cr-" in name.lower() else 1
            if stock_id in selected and selected[stock_id][0] >= priority:
                continue
            metric = parse_xbrl_document(
                archive.read(info).decode("utf-8", errors="replace"),
                stock_id=stock_id,
                period=match.group("period").upper(),
            )
            if metric is not None:
                selected[stock_id] = (priority, metric)
    return {stock_id: item[1] for stock_id, item in selected.items()}


def parse_xbrl_document(html: str, stock_id: str, period: str) -> dict[str, Any] | None:
    """從單一 inline XBRL HTML 取出目前季度的標準財務指標。"""

    values: dict[str, float] = {}
    contexts = _parse_contexts(html)
    cash_flow_contexts: dict[str, tuple[date, date] | None] = {}
    label_to_field = {
        _normalize_label(label): field
        for field, labels in FIELD_LABELS.items()
        for label in reversed(labels)
    }
    for row_match in ROW_RE.finditer(html):
        row = row_match.group("body")
        label_match = ZH_RE.search(row)
        if not label_match:
            continue
        label = _normalize_label(label_match.group("label"))
        field = label_to_field.get(label)
        if field is None or field in values:
            continue
        selected = _select_current_fact(row, field=field, period=period, contexts=contexts)
        if selected is None:
            continue
        value, context = selected
        if value is not None:
            values[field] = value
            if field in {"operating_cash_flow", "capex"}:
                cash_flow_contexts[field] = context

    if not values:
        return None
    cash_flow_metadata = _cash_flow_metadata(values, cash_flow_contexts, period, contexts_present=bool(contexts))
    if cash_flow_metadata.get("cash_flow_grain") == "invalid_context":
        values.pop("operating_cash_flow", None)
        values.pop("capex", None)
    computed = compute_financial_metrics({period: values})[0]
    return {
        **asdict(computed),
        "stock_id": str(stock_id),
        "period": period,
        "available_from": conservative_available_from(period),
        "availability_policy": "statutory_conservative",
        **cash_flow_metadata,
    }


def build_cache_payload(
    stock_id: str,
    metrics: Iterable[dict[str, Any]],
    source_periods: Iterable[str],
) -> dict[str, Any]:
    normalized = _normalize_quarterly_cash_flow(item for item in metrics if item is not None)
    ordered = sorted(normalized, key=lambda item: (str(item["available_from"]), str(item["year"])), reverse=True)
    periods = sorted(set(source_periods))
    now = datetime.now(timezone.utc).isoformat()
    return {
        "stock_id": str(stock_id),
        "source": "MOPS XBRL",
        "updated_at": now,
        "years": [str(item["year"]) for item in ordered],
        "metrics": ordered,
        "source_urls": {
            "income_statement": MOPS_XBRL_PAGE,
            "balance_sheet": MOPS_XBRL_PAGE,
            "cash_flow": MOPS_XBRL_PAGE,
        },
        "source_periods": periods,
        "availability_policy": "statutory_conservative",
        "notes": (
            "MOPS 官方季度 XBRL 離線回填；可用日採法定期限後的保守日期。"
            "整批檔可能反映後續更補正後版本，不代表逐版本歷史快照。"
        ),
    }


def _parse_fact(raw_value: str, attrs: str) -> float | None:
    cleaned = unescape(TAG_RE.sub("", raw_value)).replace(",", "").strip()
    if not cleaned or cleaned in {"-", "—"}:
        return None
    try:
        value = float(cleaned)
    except ValueError:
        return None
    if re.search(r"""\bsign\s*=\s*["']-["']""", attrs, re.IGNORECASE):
        value = -abs(value)
    return value


def _normalize_label(value: str) -> str:
    text = unescape(TAG_RE.sub("", value))
    return re.sub(r"[\s　]+", "", text).strip()


def _attribute(attrs: str, name: str) -> str | None:
    match = re.search(rf"""\b{re.escape(name)}\s*=\s*["'](?P<value>[^"']+)["']""", attrs, re.IGNORECASE)
    return unescape(match.group("value")).strip() if match else None


def _parse_contexts(html: str) -> dict[str, tuple[date, date]]:
    contexts: dict[str, tuple[date, date]] = {}
    for match in CONTEXT_RE.finditer(html):
        context_id = _attribute(match.group("attrs"), "id")
        if not context_id:
            continue
        body = match.group("body")
        start_match = START_DATE_RE.search(body)
        end_match = END_DATE_RE.search(body)
        instant_match = INSTANT_RE.search(body)
        try:
            if start_match and end_match:
                start = date.fromisoformat(_normalize_label(start_match.group("value")))
                end = date.fromisoformat(_normalize_label(end_match.group("value")))
            elif instant_match:
                start = end = date.fromisoformat(_normalize_label(instant_match.group("value")))
            else:
                continue
        except ValueError:
            continue
        if start <= end:
            contexts[context_id] = (start, end)
    return contexts


def _period_dates(period: str) -> tuple[date, date, date]:
    year, quarter = parse_period(period)
    quarter_start_month = 3 * (quarter - 1) + 1
    quarter_start = date(year, quarter_start_month, 1)
    if quarter == 4:
        quarter_end = date(year, 12, 31)
    else:
        quarter_end = date(year, quarter_start_month + 3, 1) - date.resolution
    return date(year, 1, 1), quarter_start, quarter_end


def _select_current_fact(
    row: str,
    *,
    field: str,
    period: str,
    contexts: dict[str, tuple[date, date]],
) -> tuple[float, tuple[date, date] | None] | None:
    parsed: list[tuple[float, tuple[date, date] | None]] = []
    for fact_match in FACT_RE.finditer(row):
        value = _parse_fact(fact_match.group("value"), fact_match.group("attrs"))
        if value is None:
            continue
        context_ref = _attribute(fact_match.group("attrs"), "contextRef")
        context = contexts.get(context_ref) if context_ref else None
        parsed.append((value, context))
    if not parsed:
        return None
    if not contexts:
        return parsed[0]

    year_start, quarter_start, quarter_end = _period_dates(period)
    current = [item for item in parsed if item[1] is not None and item[1][1] == quarter_end]
    if not current:
        return None
    preferred_start = year_start if field in {"operating_cash_flow", "capex"} else quarter_start
    for item in current:
        if item[1] is not None and item[1][0] == preferred_start:
            return item
    for item in current:
        if item[1] is not None and item[1][0] == year_start:
            return item
    return current[0]


def _cash_flow_metadata(
    values: dict[str, float],
    contexts: dict[str, tuple[date, date] | None],
    period: str,
    *,
    contexts_present: bool,
) -> dict[str, Any]:
    reported = {
        "reported_operating_cash_flow": values.get("operating_cash_flow"),
        "reported_capex": values.get("capex"),
    }
    if not contexts_present:
        return reported
    selected = [context for context in contexts.values() if context is not None]
    if not selected or any(context != selected[0] for context in selected[1:]):
        return {**reported, "cash_flow_grain": "invalid_context"}

    start, end = selected[0]
    year_start, quarter_start, quarter_end = _period_dates(period)
    if end != quarter_end:
        return {**reported, "cash_flow_grain": "invalid_context"}
    if start == quarter_start:
        grain = "single_quarter"
    elif start == year_start:
        grain = "year_to_date"
    else:
        grain = "invalid_context"
    return {
        **reported,
        "cash_flow_period_start": start.isoformat(),
        "cash_flow_period_end": end.isoformat(),
        "cash_flow_grain": grain,
    }


def _normalize_quarterly_cash_flow(metrics: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = [dict(item) for item in metrics]
    by_period = {str(item.get("year")): item for item in normalized}
    for item in normalized:
        period = str(item.get("year", ""))
        try:
            year, quarter = parse_period(period)
        except ValueError:
            continue
        grain = item.get("cash_flow_grain")
        if grain == "single_quarter":
            continue
        if grain != "year_to_date":
            continue
        previous = by_period.get(f"{year}Q{quarter - 1}") if quarter > 1 else None
        if previous is None:
            item["free_cash_flow"] = None
            item["cash_flow_grain"] = "missing_previous_ytd"
            continue
        current_ocf = item.get("reported_operating_cash_flow")
        previous_ocf = previous.get("reported_operating_cash_flow")
        current_capex = item.get("reported_capex")
        previous_capex = previous.get("reported_capex")
        if current_ocf is None or previous_ocf is None:
            item["free_cash_flow"] = None
            item["cash_flow_grain"] = "missing_previous_ytd"
            continue
        quarter_ocf = float(current_ocf) - float(previous_ocf)
        if current_capex is None and previous_capex is None:
            quarter_capex = 0.0
        elif current_capex is None or previous_capex is None:
            item["free_cash_flow"] = None
            item["cash_flow_grain"] = "missing_previous_ytd"
            continue
        else:
            quarter_capex = float(current_capex) - float(previous_capex)
        item["free_cash_flow"] = round(quarter_ocf + quarter_capex, 4)
        item["cash_flow_grain"] = "single_quarter"
        item["cash_flow_normalization"] = "ytd_difference"
    return normalized


def _validate_zip_resources(archive: ZipFile) -> None:
    members = archive.infolist()
    if len(members) > MAX_ZIP_MEMBERS:
        raise ValueError(f"ZIP member 數量超限：{len(members)} > {MAX_ZIP_MEMBERS}")
    total_size = 0
    for info in members:
        if info.file_size > MAX_ZIP_MEMBER_UNCOMPRESSED_BYTES:
            raise ValueError(
                "ZIP member 單檔未壓縮大小超限："
                f"{info.filename}={info.file_size} > {MAX_ZIP_MEMBER_UNCOMPRESSED_BYTES}"
            )
        total_size += info.file_size
        if total_size > MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES:
            raise ValueError(
                "ZIP member 總未壓縮大小超限："
                f"{total_size} > {MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES}"
            )


def _valid_zip(path: Path) -> bool:
    try:
        with ZipFile(path) as archive:
            _validate_zip_resources(archive)
            return bool(archive.namelist())
    except Exception:
        return False
