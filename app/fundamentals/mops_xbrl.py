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
        for name in archive.namelist():
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
                archive.read(name).decode("utf-8", errors="replace"),
                stock_id=stock_id,
                period=match.group("period").upper(),
            )
            if metric is not None:
                selected[stock_id] = (priority, metric)
    return {stock_id: item[1] for stock_id, item in selected.items()}


def parse_xbrl_document(html: str, stock_id: str, period: str) -> dict[str, Any] | None:
    """從單一 inline XBRL HTML 取出目前季度的標準財務指標。"""

    values: dict[str, float] = {}
    label_to_field = {
        _normalize_label(label): field
        for field, labels in FIELD_LABELS.items()
        for label in reversed(labels)
    }
    for row_match in ROW_RE.finditer(html):
        row = row_match.group("body")
        label_match = ZH_RE.search(row)
        fact_match = FACT_RE.search(row)
        if not label_match or not fact_match:
            continue
        label = _normalize_label(label_match.group("label"))
        field = label_to_field.get(label)
        if field is None or field in values:
            continue
        value = _parse_fact(fact_match.group("value"), fact_match.group("attrs"))
        if value is not None:
            values[field] = value

    if not values:
        return None
    computed = compute_financial_metrics({period: values})[0]
    return {
        **asdict(computed),
        "stock_id": str(stock_id),
        "period": period,
        "available_from": conservative_available_from(period),
        "availability_policy": "statutory_conservative",
    }


def build_cache_payload(
    stock_id: str,
    metrics: Iterable[dict[str, Any]],
    source_periods: Iterable[str],
) -> dict[str, Any]:
    ordered = sorted(metrics, key=lambda item: (str(item["available_from"]), str(item["year"])), reverse=True)
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


def _valid_zip(path: Path) -> bool:
    try:
        with ZipFile(path) as archive:
            return bool(archive.namelist())
    except Exception:
        return False
