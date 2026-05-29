#!/usr/bin/env python3
"""台灣國內市場情境 artifact 產生器。

本模組只產生獨立 `market_context_YYYY-MM-DD.json`，不改 ranking、不改模型。
外部資料源失敗時會記錄 warning 並保留欄位為 null，不讓 daily ranking 被阻塞。
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "market-context.tw.v1"
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


@dataclass
class SourceStatus:
    status: str = "warn"
    data_date: str | None = None
    fallback_used: bool = False
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "data_date": self.data_date,
            "fallback_used": self.fallback_used,
            "warnings": self.warnings,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="generate Taiwan market context artifact")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def ymd(date_text: str) -> str:
    return datetime.fromisoformat(date_text).strftime("%Y%m%d")


def iso_date_from_any(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    for fmt in ("%Y%m%d", "%Y/%m/%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return fallback


def number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip().replace(",", "").replace("%", "")
    if text in {"", "--", "---", "NaN", "nan"}:
        return None
    text = text.replace("+", "")
    try:
        parsed = float(text)
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def fetch_json(url: str, params: dict[str, Any] | None = None) -> Any:
    response = requests.get(url, params=params, headers=REQUEST_HEADERS, timeout=20)
    response.raise_for_status()
    return response.json()


def empty_payload(trade_date: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "trade_date": trade_date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "taiwan_only",
        "source_status": {
            "twse": SourceStatus().to_dict(),
            "tpex": SourceStatus().to_dict(),
            "taifex": SourceStatus().to_dict(),
        },
        "taiex": {
            "close": None,
            "change": None,
            "change_pct": None,
            "trade_value": None,
            "trade_value_change_pct": None,
        },
        "breadth": {
            "twse_up": None,
            "twse_down": None,
            "twse_flat": None,
            "tpex_up": None,
            "tpex_down": None,
            "tpex_flat": None,
            "advance_ratio": None,
        },
        "institutional": {
            "foreign_net": None,
            "trust_net": None,
            "dealer_net": None,
        },
        "futures": {
            "tx_close": None,
            "tx_change": None,
            "tx_change_pct": None,
            "tx_volume": None,
            "basis": None,
        },
        "futures_oi": {
            "foreign_oi": None,
            "foreign_change": None,
            "trust_oi": None,
            "trust_change": None,
            "dealer_oi": None,
            "dealer_change": None,
        },
        "options": {
            "pcr": None,
            "put_oi": None,
            "call_oi": None,
        },
        "summary": {
            "domestic_context_label": "UNKNOWN",
            "notes": [],
        },
    }


def first_table(payload: dict[str, Any], title_keyword: str) -> dict[str, Any] | None:
    for table in payload.get("tables", []) or []:
        if title_keyword in str(table.get("title", "")):
            return table
    return None


def table_rows(table: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not table:
        return []
    fields = table.get("fields") or []
    return [dict(zip(fields, row, strict=False)) for row in table.get("data", []) or []]


def row_value(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row:
            return row[key]
    return None


def parse_twse_quotes(payload: dict[str, Any], trade_date: str) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    warnings: list[str] = []
    taiex = {
        "close": None,
        "change": None,
        "change_pct": None,
        "trade_value": None,
        "trade_value_change_pct": None,
    }
    breadth = {"twse_up": None, "twse_down": None, "twse_flat": None}

    for row in table_rows(first_table(payload, "收盤指數")):
        name = str(row_value(row, "指數", "指數名稱", "index") or "")
        if "發行量加權股價指數" in name or "TAIEX" in name:
            taiex["close"] = number(row_value(row, "收盤指數", "收盤", "close"))
            taiex["change"] = number(row_value(row, "漲跌(+/-)", "漲跌點數", "change"))
            taiex["change_pct"] = number(row_value(row, "漲跌百分比(%)", "漲跌百分比", "change_pct"))
            break

    quote_rows = table_rows(first_table(payload, "每日收盤行情"))
    if quote_rows:
        up = down = flat = 0
        trade_value = 0.0
        for row in quote_rows:
            sign_text = str(row_value(row, "漲跌(+/-)", "漲跌", "sign") or "").strip()
            change_value = number(row_value(row, "漲跌價差", "change"))
            if "+" in sign_text or (change_value is not None and change_value > 0):
                up += 1
            elif "-" in sign_text or (change_value is not None and change_value < 0):
                down += 1
            else:
                flat += 1
            trade_value += number(row_value(row, "成交金額", "value")) or 0.0
        breadth.update({"twse_up": up, "twse_down": down, "twse_flat": flat})
        taiex["trade_value"] = round(trade_value, 2)
    else:
        warnings.append("TWSE quote table missing")

    if taiex["close"] is None:
        warnings.append("TAIEX close missing")
    return taiex, breadth, warnings


def parse_twse_institutional(payload: Any) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    result = {"foreign_net": None, "trust_net": None, "dealer_net": None}
    rows = payload if isinstance(payload, list) else table_rows(payload if isinstance(payload, dict) else None)
    if not rows:
        return result, ["TWSE institutional rows missing"]
    foreign = trust = dealer = 0.0
    found = {"foreign": False, "trust": False, "dealer": False}
    for row in rows:
        foreign_value = number(
            row_value(row, "外資及陸資買賣超股數", "外資及陸資(不含外資自營商)買賣超股數", "foreign_net")
        )
        trust_value = number(row_value(row, "投信買賣超股數", "trust_net"))
        dealer_value = number(row_value(row, "自營商買賣超股數", "dealer_net"))
        if foreign_value is not None:
            foreign += foreign_value
            found["foreign"] = True
        if trust_value is not None:
            trust += trust_value
            found["trust"] = True
        if dealer_value is not None:
            dealer += dealer_value
            found["dealer"] = True
    result["foreign_net"] = round(foreign, 2) if found["foreign"] else None
    result["trust_net"] = round(trust, 2) if found["trust"] else None
    result["dealer_net"] = round(dealer, 2) if found["dealer"] else None
    for key, ok in found.items():
        if not ok:
            warnings.append(f"{key} institutional net missing")
    return result, warnings


def parse_tpex_quotes(payload: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    rows = payload.get("aaData") or payload.get("tables") or []
    up = down = flat = 0
    if not rows:
        return {"tpex_up": None, "tpex_down": None, "tpex_flat": None}, ["TPEX quote rows missing"]
    for raw in rows:
        if isinstance(raw, dict):
            change = number(row_value(raw, "漲跌", "change"))
        elif isinstance(raw, list) and len(raw) > 3:
            change = number(raw[3])
        else:
            change = None
        if change is None:
            flat += 1
        elif change > 0:
            up += 1
        elif change < 0:
            down += 1
        else:
            flat += 1
    return {"tpex_up": up, "tpex_down": down, "tpex_flat": flat}, warnings


def parse_taifex_payloads(
    futures_payload: Any,
    pcr_payload: Any,
    oi_payload: Any,
    trade_date: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[str]]:
    warnings: list[str] = []
    futures = {"tx_close": None, "tx_change": None, "tx_change_pct": None, "tx_volume": None, "basis": None}
    futures_oi = {
        "foreign_oi": None,
        "foreign_change": None,
        "trust_oi": None,
        "trust_change": None,
        "dealer_oi": None,
        "dealer_change": None,
    }
    options = {"pcr": None, "put_oi": None, "call_oi": None}

    for row in normalize_list(futures_payload):
        contract = str(row_value(row, "Contract", "契約", "contract") or "")
        date_value = iso_date_from_any(row_value(row, "Date", "交易日期", "date"), trade_date)
        if contract.startswith("TX") and date_value == trade_date:
            futures["tx_close"] = number(row_value(row, "Close", "收盤價", "close"))
            futures["tx_change"] = number(row_value(row, "Change", "漲跌", "change"))
            futures["tx_change_pct"] = number(row_value(row, "Change%", "漲跌%", "change_pct"))
            futures["tx_volume"] = number(row_value(row, "Volume", "成交量", "volume"))
            break
    if futures["tx_close"] is None:
        warnings.append("TAIFEX TX futures row missing")

    for row in normalize_list(pcr_payload):
        date_value = iso_date_from_any(row_value(row, "Date", "日期", "date"), trade_date)
        if date_value != trade_date:
            continue
        options["pcr"] = number(row_value(row, "Put/Call OI Ratio%", "Put/Call未平倉比率%", "pcr"))
        options["put_oi"] = number(row_value(row, "Put OI", "賣權未平倉量", "put_oi"))
        options["call_oi"] = number(row_value(row, "Call OI", "買權未平倉量", "call_oi"))
        break
    if options["pcr"] is None:
        warnings.append("TAIFEX put/call ratio row missing")

    for row in normalize_list(oi_payload):
        label = str(row_value(row, "身份別", "Trader", "trader") or "")
        oi = number(row_value(row, "未平倉口數", "Open Interest", "open_interest"))
        change = number(row_value(row, "未平倉口數增減", "Change", "change"))
        if "外資" in label or "Foreign" in label:
            futures_oi["foreign_oi"] = oi
            futures_oi["foreign_change"] = change
        elif "投信" in label or "Investment Trust" in label:
            futures_oi["trust_oi"] = oi
            futures_oi["trust_change"] = change
        elif "自營" in label or "Dealer" in label:
            futures_oi["dealer_oi"] = oi
            futures_oi["dealer_change"] = change
    if all(value is None for value in futures_oi.values()):
        warnings.append("TAIFEX institutional futures OI missing")

    return futures, futures_oi, options, warnings


def normalize_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("data", "Data", "items"):
            if isinstance(payload.get(key), list):
                return [row for row in payload[key] if isinstance(row, dict)]
    return []


def source_status(warnings: list[str], data_date: str | None) -> SourceStatus:
    if not warnings:
        status = "ok"
    elif data_date:
        status = "warn"
    else:
        status = "warn"
    return SourceStatus(status=status, data_date=data_date, fallback_used=False, warnings=warnings)


def has_any_value(section: dict[str, Any]) -> bool:
    return any(value is not None for value in section.values())


def update_advance_ratio(payload: dict[str, Any]) -> None:
    breadth = payload["breadth"]
    up = sum(value or 0 for value in [breadth.get("twse_up"), breadth.get("tpex_up")])
    down = sum(value or 0 for value in [breadth.get("twse_down"), breadth.get("tpex_down")])
    flat = sum(value or 0 for value in [breadth.get("twse_flat"), breadth.get("tpex_flat")])
    total = up + down + flat
    breadth["advance_ratio"] = round(up / total, 6) if total else None


def update_summary(payload: dict[str, Any]) -> None:
    notes: list[str] = []
    change = payload["taiex"].get("change")
    advance_ratio = payload["breadth"].get("advance_ratio")
    label = "UNKNOWN"
    if change is not None and advance_ratio is not None:
        if change > 0 and advance_ratio >= 0.55:
            label = "RISK_ON"
        elif change < 0 and advance_ratio <= 0.45:
            label = "RISK_OFF"
        else:
            label = "MIXED"
    for source, status in payload["source_status"].items():
        if status.get("status") != "ok":
            notes.append(f"{source}: {'; '.join(status.get('warnings') or ['warn'])}")
    payload["summary"] = {
        "domestic_context_label": label,
        "notes": notes,
    }


def build_market_context(trade_date: str) -> dict[str, Any]:
    payload = empty_payload(trade_date)
    date_param = ymd(trade_date)

    twse_warnings: list[str] = []
    try:
        twse_quotes = fetch_json(
            "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX",
            {"date": date_param, "type": "ALLBUT0999", "response": "json"},
        )
        taiex, twse_breadth, warnings = parse_twse_quotes(twse_quotes, trade_date)
        payload["taiex"].update(taiex)
        payload["breadth"].update(twse_breadth)
        twse_warnings.extend(warnings)
    except Exception as exc:
        twse_warnings.append(f"TWSE quotes fetch failed: {exc}")

    try:
        institutional = fetch_json(
            "https://www.twse.com.tw/rwd/zh/fund/T86",
            {"date": date_param, "selectType": "ALLBUT0999", "response": "json"},
        )
        institutional_values, warnings = parse_twse_institutional(institutional)
        payload["institutional"].update(institutional_values)
        twse_warnings.extend(warnings)
    except Exception as exc:
        twse_warnings.append(f"TWSE institutional fetch failed: {exc}")
    twse_has_data = has_any_value(payload["taiex"]) or has_any_value(payload["institutional"])
    payload["source_status"]["twse"] = source_status(twse_warnings, trade_date if twse_has_data else None).to_dict()

    tpex_warnings: list[str] = []
    try:
        dt = datetime.fromisoformat(trade_date)
        roc_date = f"{dt.year - 1911}/{dt.month:02d}/{dt.day:02d}"
        tpex_quotes = fetch_json(
            "https://www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no1430/stk_wn1430_result.php",
            {"l": "zh-tw", "d": roc_date, "se": "AL"},
        )
        tpex_breadth, warnings = parse_tpex_quotes(tpex_quotes)
        payload["breadth"].update(tpex_breadth)
        tpex_warnings.extend(warnings)
    except Exception as exc:
        tpex_warnings.append(f"TPEX quotes fetch failed: {exc}")
    tpex_has_data = any(payload["breadth"].get(key) is not None for key in ("tpex_up", "tpex_down", "tpex_flat"))
    payload["source_status"]["tpex"] = source_status(tpex_warnings, trade_date if tpex_has_data else None).to_dict()

    taifex_warnings: list[str] = []
    try:
        futures_payload = fetch_json("https://openapi.taifex.com.tw/v1/DailyMarketReportFut")
    except Exception as exc:
        futures_payload = []
        taifex_warnings.append(f"TAIFEX futures fetch failed: {exc}")
    try:
        pcr_payload = fetch_json("https://openapi.taifex.com.tw/v1/PutCallRatio")
    except Exception as exc:
        pcr_payload = []
        taifex_warnings.append(f"TAIFEX put/call fetch failed: {exc}")
    try:
        oi_payload = fetch_json(
            "https://openapi.taifex.com.tw/v1/MarketDataOfMajorInstitutionalTradersDetailsOfFuturesContractsBytheDate"
        )
    except Exception as exc:
        oi_payload = []
        taifex_warnings.append(f"TAIFEX futures OI fetch failed: {exc}")
    futures, futures_oi, options, warnings = parse_taifex_payloads(futures_payload, pcr_payload, oi_payload, trade_date)
    payload["futures"].update(futures)
    payload["futures_oi"].update(futures_oi)
    payload["options"].update(options)
    taifex_warnings.extend(warnings)
    taifex_has_data = has_any_value(payload["futures"]) or has_any_value(payload["futures_oi"]) or has_any_value(payload["options"])
    payload["source_status"]["taifex"] = source_status(taifex_warnings, trade_date if taifex_has_data else None).to_dict()

    update_advance_ratio(payload)
    update_summary(payload)
    return payload


def write_payload(payload: dict[str, Any], output: str | None) -> Path:
    output_path = Path(output).expanduser() if output else PROJECT_ROOT / "artifacts" / f"market_context_{payload['trade_date']}.json"
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return output_path


def main() -> int:
    args = parse_args()
    payload = build_market_context(args.date)
    output_path = write_payload(payload, args.output)
    print(json.dumps({"status": "OK", "output": str(output_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
