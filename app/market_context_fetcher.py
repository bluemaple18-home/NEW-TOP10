#!/usr/bin/env python3
"""台灣國內市場情境 artifact 產生器。

本模組只產生獨立 `market_context_YYYY-MM-DD.json`，不改 ranking、不改模型。
必要來源失敗時保留診斷與 null，CLI 回傳非零供呼叫端判定失敗。
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from app.tskg.twse_t86 import load_t86_snapshot, market_aggregate
from app.taifex_historical import fetch_historical


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
    parser.add_argument("--backfill", action="store_true", help="使用期交所帶日期的歷史行情與 OI 入口")
    parser.add_argument(
        "--twse-t86-input",
        default=None,
        help="已驗證的 TSKG T86 snapshot；提供後不重複呼叫 T86 endpoint",
    )
    return parser.parse_args()


def ymd(date_text: str) -> str:
    return iso_date_from_any(date_text).replace("-", "")


def iso_date_from_any(value: Any, fallback: str | None = None) -> str:
    """嚴格解析來源日期；保留舊參數但絕不以要求日期代替缺值。"""
    text = str(value or "").strip()
    for pattern, fmt in ((r"\d{8}", "%Y%m%d"), (r"\d{4}/\d{2}/\d{2}", "%Y/%m/%d"),
                         (r"\d{4}-\d{2}-\d{2}", "%Y-%m-%d")):
        if re.fullmatch(pattern, text):
            try:
                return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
            except ValueError:
                break
    raise ValueError(f"來源日期缺漏或格式錯誤：{value!r}")


def number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip()
    if not re.fullmatch(r"[+-]?(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(?:\.[0-9]+)?%?", text):
        return None
    parsed = float(text.replace(",", "").removesuffix("%"))
    return parsed if math.isfinite(parsed) else None


def fetch_json(url: str, params: dict[str, Any] | None = None) -> Any:
    """有限次重試暫時性連線、5xx 與非 JSON 回應；4xx 直接拒絕。"""
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        response = None
        reason = ""
        try:
            response = requests.get(url, params=params, headers=REQUEST_HEADERS, timeout=20)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
            reason = type(exc).__name__
        else:
            status = getattr(response, "status_code", 200)
            if 400 <= status < 500:
                raise RuntimeError(_fetch_json_diagnostic(response, attempt, f"HTTP_{status}"))
            if status >= 500:
                reason = f"HTTP_{status}"
            else:
                response.raise_for_status()
                try:
                    return response.json()
                except ValueError as exc:
                    reason = type(exc).__name__
        if attempt == max_attempts:
            raise RuntimeError(_fetch_json_diagnostic(response, attempt, reason))
        time.sleep(2 ** (attempt - 1))
    raise AssertionError("不可達：fetch_json 重試迴圈未結束")


def _fetch_json_diagnostic(response: Any, attempts: int, reason: str) -> str:
    status = getattr(response, "status_code", None)
    headers = getattr(response, "headers", {}) or {}
    content_type = headers.get("Content-Type", headers.get("content-type"))
    body_prefix = re.sub(r"[\r\n]+", " ", str(getattr(response, "text", ""))[:200])
    return (
        f"fetch_json failed reason={reason} http_status={status} "
        f"content_type={content_type!r} body_prefix={body_prefix!r} attempts={attempts}"
    )


class PCRFormatError(ValueError):
    """PCR 回應無法辨識或解碼；僅此類內容錯誤可重試。"""


def decode_pcr_response(content: bytes) -> tuple[list[dict[str, Any]], str]:
    """嗅探內容而非 Content-Type；成交量比率不可替代未平倉量比率。"""
    try:
        text = content.decode("utf-8-sig").lstrip()
    except UnicodeDecodeError as exc:
        raise PCRFormatError("PCR 非 UTF-8 回應") from exc
    if text.startswith(("[", "{")):
        try:
            payload = json.loads(text)
        except ValueError as exc:
            raise PCRFormatError("PCR JSON 語法無法解析") from exc
        rows = normalize_list(payload)
        source_format = "json"
    else:
        mapping = {"日期": "Date", "賣權未平倉量": "PutOI", "買權未平倉量": "CallOI",
                   "買賣權未平倉量比率%": "PutCallOIRatio%"}
        try:
            reader = csv.DictReader(io.StringIO(text), strict=True)
            fields = reader.fieldnames or []
            if not set(mapping).intersection(fields):
                raise PCRFormatError("PCR 無法辨識 JSON／CSV")
            if not set(mapping).issubset(fields) or len(fields) != len(set(fields)):
                raise ValueError("PCR CSV 必要欄位缺漏或重複")
            rows = []
            for row in reader:
                if None in row or any(row.get(key) is None for key in mapping):
                    raise ValueError("PCR CSV 資料欄數不符")
                rows.append({target: row[key] for key, target in mapping.items()})
        except csv.Error as exc:
            raise PCRFormatError("PCR CSV 語法無法解析") from exc
        source_format = "csv"
    # 兩條路徑使用同一日期契約；數值驗證保留在既有 PCR 解析器。
    return [dict(row, Date=iso_date_from_any(row.get("Date"))) for row in rows], source_format


def fetch_pcr() -> tuple[list[dict[str, Any]], str]:
    """僅 PCR 自適應格式；確定性欄位錯誤不重試，沿用 18R1 的三次上限。"""
    for attempt in range(1, 4):
        response = None
        try:
            response = requests.get("https://openapi.taifex.com.tw/v1/PutCallRatio",
                                    headers=REQUEST_HEADERS, timeout=20)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
            reason = type(exc).__name__
        else:
            status = response.status_code
            if 400 <= status < 500:
                raise RuntimeError(_fetch_json_diagnostic(response, attempt, f"HTTP_{status}"))
            if status >= 500:
                reason = f"HTTP_{status}"
            else:
                response.raise_for_status()
                try:
                    return decode_pcr_response(response.content)
                except PCRFormatError as exc:
                    reason = str(exc)
        if attempt == 3:
            raise RuntimeError(_fetch_json_diagnostic(response, attempt, reason))
        time.sleep(2 ** (attempt - 1))
    raise AssertionError("不可達：PCR 重試迴圈未結束")


def fetch_dated_pcr_official(trade_date: str) -> tuple[list[dict[str, Any]], str]:
    """API日期落後時只取官網指定日；仍沿用既有PCR欄位與數值驗證。"""
    from bs4 import BeautifulSoup

    date = datetime.strptime(trade_date, "%Y-%m-%d").strftime("%Y/%m/%d")
    response = requests.post(
        "https://www.taifex.com.tw/cht/3/pcRatioExcel",
        data={"queryStartDate": date, "queryEndDate": date},
        headers=REQUEST_HEADERS, timeout=20, allow_redirects=False,
    )
    if response.status_code != 200:
        raise RuntimeError(f"PCR 官網 HTTP_{response.status_code}")
    fields = {"日期", "賣權成交量", "買權成交量", "買賣權成交量比率%",
              "賣權未平倉量", "買權未平倉量", "買賣權未平倉量比率%"}
    tables = []
    for table in BeautifulSoup(response.content, "html.parser").find_all("table"):
        rows = table.find_all("tr")
        headers = [re.sub(r"\s+", "", x.get_text()) for x in rows[0].find_all(["th", "td"])] if rows else []
        if len(headers) == len(fields) and set(headers) == fields:
            tables.append((headers, rows[1:]))
    if len(tables) != 1:
        raise ValueError("PCR 官網必須恰有一份完整欄位表格")
    headers, rows = tables[0]
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in rows:
        cells = [x.get_text(strip=True) for x in row.find_all(["td", "th"])]
        if cells:
            if len(cells) != len(headers):
                raise ValueError("PCR 官網資料欄數不符")
            cells[headers.index("日期")] = datetime.strptime(
                cells[headers.index("日期")], "%Y/%m/%d"
            ).strftime("%Y-%m-%d")
            writer.writerow(cells)
    parsed, _ = decode_pcr_response(output.getvalue().encode("utf-8"))
    selected = dated_rows(parsed, trade_date)
    if len(selected) != 1:
        raise ValueError(f"PCR 官網目標日必須恰有一筆，實際 {len(selected)} 筆")
    return selected, "html"


def empty_payload(trade_date: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "trade_date": trade_date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "taiwan_only",
        "unavailable_fields": {
            "taiex.trade_value_change_pct": {
                "reason": "source_not_provided", "detail": "當日來源未提供成交金額日變動率",
            },
            **{f"futures_oi.{key}_change": {
                "reason": "source_not_provided", "detail": "當日來源未提供未平倉淨口數日差",
            } for key in ("foreign", "trust", "dealer")},
        },
        "units": {
            "taiex.close": "index_points", "taiex.change": "index_points",
            "taiex.change_pct": "percent", "taiex.trade_value": "TWD",
            "institutional": "shares", "futures.tx_close": "index_points",
            "futures.tx_change": "index_points", "futures.tx_change_pct": "percent",
            "futures.tx_volume": "contracts", "futures.basis": "index_points",
            "futures_oi": "contracts", "options.pcr": "percent",
            "options.put_oi": "contracts", "options.call_oi": "contracts",
        },
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
        raise ValueError("必要表格缺漏")
    fields = table.get("fields") or []
    data = table.get("data") or []
    if not fields or len(set(fields)) != len(fields) or not data:
        raise ValueError("表格欄位／資料缺漏或欄名重複")
    if any(not isinstance(row, list) or len(row) != len(fields) for row in data):
        raise ValueError("表格資料欄數與 fields 不符")
    for key in ("total", "totalCount"):
        if key in table and require_count(table[key], key) != len(data):
            raise ValueError(f"{key} 宣告筆數與資料列數不符")
    if "stat" in table and table["stat"] != "OK":
        raise ValueError(f"來源狀態不是 OK：{table['stat']!r}")
    return [dict(zip(fields, row, strict=True)) for row in data]


def row_value(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row:
            return row[key]
    return None


def require_number(value: Any, label: str, *, nonnegative: bool = False) -> float:
    result = number(value)
    if result is None or (nonnegative and result < 0):
        raise ValueError(f"{label} 必要數值缺漏或格式錯誤：{value!r}")
    return result


def require_count(value: Any, label: str) -> int:
    result = require_number(value, label, nonnegative=True)
    if not result.is_integer():
        raise ValueError(f"{label} 必須為整數")
    return int(result)


def check_date(value: Any, expected: str | None = None) -> str:
    actual = iso_date_from_any(value)
    if expected is not None and actual != iso_date_from_any(expected):
        raise ValueError(f"來源日期 {actual} 與要求 {expected} 不符")
    return actual


def quote_rows(payload: dict[str, Any], required: set[str]) -> list[dict[str, Any]]:
    tables = [t for t in payload.get("tables", []) if required <= set(t.get("fields", []))]
    if len(tables) != 1:
        raise ValueError(f"必要行情表缺漏或重複：{sorted(required)}")
    return table_rows(tables[0])


def unique_rows(rows: list[dict[str, Any]], key: str) -> None:
    seen: set[str] = set()
    if not rows:
        raise ValueError("必要來源資料為空")
    for row in rows:
        value = str(row.get(key) or "").strip()
        if not value or value in seen:
            raise ValueError(f"{key} 缺漏或重複：{value!r}")
        seen.add(value)


def sign_text(value: Any) -> str:
    if value is None:
        raise ValueError("漲跌符號欄缺漏")
    return re.sub(r"<[^>]*>", "", str(value)).strip()


def signed_change(sign: str, magnitude: Any) -> float:
    value = require_number(magnitude, "漲跌幅度")
    if sign in {"+", "-"}:
        return abs(value) * (1 if sign == "+" else -1)
    if sign == "" and value == 0:
        return 0.0
    raise ValueError(f"漲跌符號與幅度無法判讀：{sign!r}/{magnitude!r}")


def parse_twse_quotes(payload: dict[str, Any], trade_date: str) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    check_date(payload.get("date"), trade_date)
    if "stat" in payload and payload["stat"] != "OK":
        raise ValueError(f"上市來源狀態不是 OK：{payload['stat']!r}")
    index_rows = []
    for table in payload.get("tables", []):
        if {"指數", "收盤指數", "漲跌點數", "漲跌(+/-)", "漲跌百分比(%)"} <= set(table.get("fields", [])):
            index_rows.extend(row for row in table_rows(table) if row["指數"].strip() in {"發行量加權股價指數", "TAIEX"})
    if len(index_rows) != 1:
        raise ValueError("價格指數表的發行量加權股價指數缺漏或重複")
    index = index_rows[0]
    taiex = {
        "close": require_number(index["收盤指數"], "收盤指數", nonnegative=True),
        "change": signed_change(sign_text(index["漲跌(+/-)"]), index["漲跌點數"]),
        "change_pct": require_number(index["漲跌百分比(%)"], "指數漲跌百分比"),
        "trade_value": None,
        "trade_value_change_pct": None,
    }
    rows = quote_rows(payload, {"證券代號", "漲跌(+/-)", "漲跌價差", "收盤價", "成交股數", "成交筆數", "成交金額"})
    unique_rows(rows, "證券代號")
    up = down = flat = 0
    excluded = {"no_trade": 0, "no_closing_price": 0, "X": 0}
    total_value = 0.0
    for row in rows:
        sign = sign_text(row["漲跌(+/-)"])
        delta = require_number(row["漲跌價差"], "漲跌價差")
        volume = require_count(row["成交股數"], "成交股數")
        trades = require_count(row["成交筆數"], "成交筆數")
        value = require_number(row["成交金額"], "成交金額", nonnegative=True)
        total_value += value
        raw_close = str(row["收盤價"]).strip()
        close = None if raw_close == "--" else require_number(raw_close, "收盤價", nonnegative=True)
        if sign not in {"+", "-", "", "X"}:
            raise ValueError(f"未知上市漲跌符號：{sign!r}")
        # X 為不可比較狀態；即使有成交與零價差也不能推定平盤。
        if sign == "X":
            excluded["X"] += 1
        elif close is None or not volume or not trades or not value:
            if sign or delta != 0:
                raise ValueError("上市行情有漲跌但缺有效收盤／成交")
            excluded["no_trade" if volume == trades == value == 0 else "no_closing_price"] += 1
        else:
            change = signed_change(sign, delta)
            up += int(change > 0)
            down += int(change < 0)
            flat += int(change == 0)
    taiex["trade_value"] = round(total_value, 2)
    breadth = {"twse_up": up, "twse_down": down, "twse_flat": flat,
               "twse_metadata": {"scope": "ALLBUT0999 回傳證券（含 ETF／ETN 等，非純股票）",
                                 "source_rows": len(rows), "excluded_counts": excluded}}
    return taiex, breadth, []


def parse_twse_institutional(payload: Any, trade_date: str | None = None) -> tuple[dict[str, Any], list[str]]:
    check_date(payload.get("date"), trade_date)
    rows = table_rows(payload)
    unique_rows(rows, "證券代號")
    fields = {"foreign_net": "外陸資買賣超股數(不含外資自營商)",
              "trust_net": "投信買賣超股數", "dealer_net": "自營商買賣超股數"}
    result = {}
    for key, field in fields.items():
        values = [require_number(row.get(field), field) for row in rows]
        if any(not value.is_integer() for value in values):
            raise ValueError(f"{field} 股數必須為整數")
        result[key] = sum(int(value) for value in values)
    return result, []


def parse_tpex_quotes(payload: dict[str, Any], trade_date: str | None = None) -> tuple[dict[str, Any], list[str]]:
    check_date(payload.get("date"), trade_date)
    rows = quote_rows(payload, {"代號", "漲跌"})
    for table in payload.get("tables", []):
        if {"代號", "漲跌"} <= set(table.get("fields", [])) and "date" in table:
            text = str(table["date"])
            if not re.fullmatch(r"[0-9]{3}/[0-9]{2}/[0-9]{2}", text):
                raise ValueError("上櫃表格民國日期格式錯誤")
            year, month, day = map(int, text.split("/"))
            check_date(f"{year + 1911:04d}-{month:02d}-{day:02d}", check_date(payload.get("date")))
    unique_rows(rows, "代號")
    up = down = flat = 0
    excluded = {"---": 0, "除息": 0, "除權": 0, "除權息": 0}
    for row in rows:
        raw = str(row["漲跌"]).strip()
        if raw in excluded:
            excluded[raw] += 1
            continue
        change = require_number(row["漲跌"], "上櫃漲跌")
        up += int(change > 0)
        down += int(change < 0)
        flat += int(change == 0)
    return {"tpex_up": up, "tpex_down": down, "tpex_flat": flat,
            "tpex_metadata": {"scope": "全部回傳上櫃證券（含權證等，非純股票）",
                              "source_rows": len(rows), "excluded_counts": excluded}}, []


def one_row(rows: list[dict[str, Any]], label: str) -> dict[str, Any]:
    if len(rows) != 1:
        raise ValueError(f"{label} 必須恰有一筆，實際 {len(rows)} 筆")
    return rows[0]


def dated_rows(payload: Any, trade_date: str) -> list[dict[str, Any]]:
    return [row for row in normalize_list(payload) if check_date(row.get("Date")) == trade_date]


def unavailable_historical(payload: Any, trade_date: str) -> bool:
    """只有來源確實提供較新日期且缺目標日時才判為 openapi 歷史缺口。"""
    try:
        rows = normalize_list(payload)
        dates = [check_date(row.get("Date")) for row in rows]
    except (TypeError, ValueError, KeyError):
        return False
    return bool(dates) and trade_date not in dates and max(dates) > trade_date


def parse_taifex_payloads(
    futures_payload: Any,
    pcr_payload: Any,
    oi_payload: Any,
    trade_date: str,
    *,
    unavailable_sections: frozenset[str] = frozenset(),
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[str]]:
    check_date(trade_date)
    errors: list[str] = []
    futures = {"tx_close": None, "tx_change": None, "tx_change_pct": None, "tx_volume": None, "basis": None}
    futures_oi = {"foreign_oi": None, "foreign_change": None, "trust_oi": None,
                  "trust_change": None, "dealer_oi": None, "dealer_change": None}
    options = {"pcr": None, "put_oi": None, "call_oi": None}
    if "futures" not in unavailable_sections:
        try:
            candidates = []
            for row in dated_rows(futures_payload, trade_date):
                if row.get("Contract") != "TX":
                    continue
                if row.get("TradingSession") not in {"一般", "盤後"}:
                    raise ValueError("TX TradingSession 缺漏或未知")
                if row["TradingSession"] != "一般":
                    continue
                month = str(row.get("ContractMonth(Week)") or "")
                if re.fullmatch(r"\d{6}/\d{6}|\d{6}W[1-5]", month):
                    continue
                if not re.fullmatch(r"\d{6}", month):
                    raise ValueError(f"TX 契約月份格式錯誤：{month!r}")
                datetime.strptime(month + "01", "%Y%m%d")
                # 以官方當日仍掛牌的月契約為準，避免自行推算到期日漏掉休市順延。
                if month >= trade_date.replace("-", "")[:6]:
                    candidates.append(row)
            if not candidates:
                raise ValueError("當日一般盤掛牌 TX 月契約缺漏")
            unique_rows(candidates, "ContractMonth(Week)")
            nearest = min(row["ContractMonth(Week)"] for row in candidates)
            row = one_row([r for r in candidates if r["ContractMonth(Week)"] == nearest], "TX 近月")
            futures.update(tx_close=require_number(row.get("Last"), "TX Last", nonnegative=True),
                           tx_change=require_number(row.get("Change"), "TX Change"),
                           tx_change_pct=require_number(row.get("%"), "TX %"),
                           tx_volume=require_count(row.get("Volume"), "TX Volume"),
                           contract_month=nearest, trading_session="一般", selection_basis="source-listed")
        except ValueError as exc:
            errors.append(f"TAIFEX futures：{exc}")
    if "options" not in unavailable_sections:
        try:
            row = one_row(dated_rows(pcr_payload, trade_date), "PCR 當日")
            options.update(pcr=require_number(row.get("PutCallOIRatio%"), "PutCallOIRatio%", nonnegative=True),
                           put_oi=require_count(row.get("PutOI"), "PutOI"),
                           call_oi=require_count(row.get("CallOI"), "CallOI"))
        except ValueError as exc:
            errors.append(f"TAIFEX PCR：{exc}")
    if "oi" not in unavailable_sections:
        try:
            rows = [row for row in dated_rows(oi_payload, trade_date) if row.get("ContractCode") == "臺股期貨"]
            values = {}
            for key, label in (("foreign", "外資及陸資"), ("trust", "投信"), ("dealer", "自營商")):
                row = one_row([r for r in rows if r.get("Item") == label], f"臺股期貨 {label}")
                value = require_number(row.get("OpenInterest(Net)"), "OpenInterest(Net)")
                if not value.is_integer():
                    raise ValueError("未平倉淨口數必須為整數")
                values[f"{key}_oi"] = int(value)
            futures_oi.update(values)
        except ValueError as exc:
            errors.append(f"TAIFEX OI：{exc}")
    return futures, futures_oi, options, errors


def normalize_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        payload = next((payload[key] for key in ("data", "Data", "items") if key in payload), None)
    if not isinstance(payload, list) or not payload or any(not isinstance(row, dict) for row in payload):
        raise ValueError("必要來源清單缺漏、為空或資料格式錯誤")
    return payload


def source_status(warnings: list[str], data_date: str | None) -> SourceStatus:
    return SourceStatus(status="error" if warnings or not data_date else "ok",
                        data_date=data_date, fallback_used=False, warnings=warnings)


def has_any_value(section: dict[str, Any]) -> bool:
    return any(value is not None for value in section.values())


def update_advance_ratio(payload: dict[str, Any]) -> None:
    breadth = payload["breadth"]
    keys = ("twse_up", "twse_down", "twse_flat", "tpex_up", "tpex_down", "tpex_flat")
    if any(breadth.get(key) is None for key in keys):
        breadth["advance_ratio"] = None
        return
    up = sum(breadth[key] for key in ("twse_up", "tpex_up"))
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
            notes.append(f"{source}: {'; '.join(status.get('warnings') or [status.get('reason_code', 'warn')])}")
    payload["errors"] = {source: status["warnings"] for source, status in payload["source_status"].items()
                         if status["status"] == "error"}
    unavailable = any(status["status"] == "unavailable_via_openapi" for status in payload["source_status"].values())
    payload["status"] = "error" if payload["errors"] else "unavailable_via_openapi" if unavailable else "ok"
    if payload["status"] != "ok":
        label = "UNKNOWN"
    payload["summary"] = {
        "domestic_context_label": label,
        "notes": notes,
    }


def build_market_context(
    trade_date: str,
    *,
    twse_t86_snapshot: dict[str, Any] | None = None,
    backfill: bool = False,
) -> dict[str, Any]:
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
        if twse_t86_snapshot is None:
            institutional = fetch_json(
                "https://www.twse.com.tw/rwd/zh/fund/T86",
                {"date": date_param, "selectType": "ALLBUT0999", "response": "json"},
            )
            institutional_values, warnings = parse_twse_institutional(institutional, trade_date)
        else:
            if twse_t86_snapshot.get("trade_date") != trade_date:
                raise ValueError("T86 snapshot trade_date differs from market-context date")
            institutional_values = market_aggregate(twse_t86_snapshot)
            for key in ("foreign_net", "trust_net", "dealer_net"):
                require_number(institutional_values.get(key), key)
            warnings = []
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
        tpex_breadth, warnings = parse_tpex_quotes(tpex_quotes, trade_date)
        payload["breadth"].update(tpex_breadth)
        tpex_warnings.extend(warnings)
    except Exception as exc:
        tpex_warnings.append(f"TPEX quotes fetch failed: {exc}")
    tpex_has_data = any(payload["breadth"].get(key) is not None for key in ("tpex_up", "tpex_down", "tpex_flat"))
    payload["source_status"]["tpex"] = source_status(tpex_warnings, trade_date if tpex_has_data else None).to_dict()

    taifex_warnings: list[str] = []
    historical_info: dict[str, dict[str, Any]] = {}
    try:
        if backfill:
            futures_payload, historical_info["futures"] = fetch_historical("futures", trade_date, headers=REQUEST_HEADERS)
        else:
            futures_payload = fetch_json("https://openapi.taifex.com.tw/v1/DailyMarketReportFut")
    except Exception as exc:
        futures_payload = []
        taifex_warnings.append(f"TAIFEX futures fetch failed: {exc}")
    pcr_format = None
    try:
        pcr_payload, pcr_format = fetch_pcr()
    except Exception as exc:
        pcr_payload = []
        taifex_warnings.append(f"TAIFEX put/call fetch failed: {exc}")
    try:
        if backfill:
            oi_payload, historical_info["oi"] = fetch_historical("oi", trade_date, headers=REQUEST_HEADERS)
        else:
            oi_payload = fetch_json(
                "https://openapi.taifex.com.tw/v1/MarketDataOfMajorInstitutionalTradersDetailsOfFuturesContractsBytheDate"
            )
    except Exception as exc:
        oi_payload = []
        taifex_warnings.append(f"TAIFEX futures OI fetch failed: {exc}")
    unavailable = frozenset(
        name for name, info in historical_info.items()
        if info["status"] == "unavailable_historical"
    )
    # 僅處理整份PCR API日期落後；目標日已有錯值／重複列時仍直接拒收。
    if (pcr_payload and pcr_format in {"json", "csv"}
            and max(check_date(row.get("Date")) for row in pcr_payload) < trade_date
            and dated_rows(futures_payload, trade_date) and dated_rows(oi_payload, trade_date)):
        try:
            pcr_payload, pcr_format = fetch_dated_pcr_official(trade_date)
        except Exception as exc:
            taifex_warnings.append(f"TAIFEX PCR dated fallback failed: {exc}")
    # 歷史兩入口均無該日、PCR 亦明確只含其他較新日期時，保留整組不可用。
    # 空清單或損壞 PCR 仍是 error；不得藉非交易日分支隱藏來源故障。
    if backfill and unavailable == frozenset({"futures", "oi"}) and unavailable_historical(pcr_payload, trade_date):
        try:
            for row in normalize_list(pcr_payload):
                require_number(row.get("PutCallOIRatio%"), "PutCallOIRatio%", nonnegative=True)
                require_count(row.get("PutOI"), "PutOI")
                require_count(row.get("CallOI"), "CallOI")
        except ValueError:
            pass  # 保留原解析器的 PCR 失敗診斷。
        else:
            unavailable |= {"options"}
    futures, futures_oi, options, warnings = parse_taifex_payloads(
        futures_payload, pcr_payload, oi_payload, trade_date,
        unavailable_sections=unavailable,
    )
    payload["futures"].update(futures)
    payload["futures_oi"].update(futures_oi)
    payload["options"].update(options)
    taifex_warnings.extend(warnings)
    taifex_has_data = has_any_value(payload["futures"]) or has_any_value(payload["futures_oi"]) or has_any_value(payload["options"])
    taifex_status = source_status(taifex_warnings, trade_date if taifex_has_data else None).to_dict()
    taifex_status["pcr_format"] = pcr_format
    if backfill:
        taifex_status.update(source="taifex_historical", components=historical_info,
                             fallback_used=any(info["fallback_used"] for info in historical_info.values()))
    if pcr_format == "html":
        taifex_status.update(pcr_source="taifex_pcRatioExcel", pcr_fallback_used=True, fallback_used=True)
    if unavailable and not taifex_warnings:
        # 沿用卡 18 的下游狀態名稱；實際來源與缺口原因由 metadata 明確區分。
        taifex_status.update(status="unavailable_via_openapi", data_date=None,
                             reason_code="unavailable_historical",
                             unavailable_components=sorted(unavailable))
        for section in sorted(unavailable):
            field_section = "futures_oi" if section == "oi" else section
            for key in payload[field_section]:
                payload["unavailable_fields"][f"{field_section}.{key}"] = {
                    "reason": "unavailable_historical",
                    "detail": "TAIFEX 來源無目標日資料；不得以鄰日替代",
                }
    payload["source_status"]["taifex"] = taifex_status

    if payload["futures"]["tx_close"] is not None and payload["taiex"]["close"] is not None:
        payload["futures"]["basis"] = round(payload["futures"]["tx_close"] - payload["taiex"]["close"], 2)
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
    try:
        t86_snapshot = (
            load_t86_snapshot(Path(args.twse_t86_input).expanduser())
            if args.twse_t86_input else None
        )
        payload = build_market_context(
            args.date, twse_t86_snapshot=t86_snapshot,
            backfill=getattr(args, "backfill", False) or os.environ.get("TOP10_BACKFILL") == "1",
        )
    except Exception as exc:
        payload = empty_payload(args.date)
        for source in payload["source_status"]:
            payload["source_status"][source] = source_status([f"市場背景建立失敗：{exc}"], None).to_dict()
        update_summary(payload)
    output_path = write_payload(payload, args.output)
    accepted = payload["status"] in {"ok", "unavailable_via_openapi"}
    cli_status = {"ok": "OK", "unavailable_via_openapi": "UNAVAILABLE_VIA_OPENAPI", "error": "ERROR"}[payload["status"]]
    print(json.dumps({"status": cli_status, "output": str(output_path)}, ensure_ascii=False))
    return 0 if accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
