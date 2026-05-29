#!/usr/bin/env python3
"""驗證台灣市場情境 fetcher 的資料契約。"""

from __future__ import annotations

import json
import math
import sys
import tempfile
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app import market_context_fetcher as fetcher

ARTIFACT_PATH = PROJECT_ROOT / "artifacts" / "market_context_fetcher_verification_latest.json"
TRADE_DATE = "2026-05-29"


def fake_twse_quotes() -> dict[str, Any]:
    return {
        "tables": [
            {
                "title": "收盤指數資訊",
                "fields": ["指數", "收盤指數", "漲跌(+/-)", "漲跌百分比(%)"],
                "data": [["發行量加權股價指數", "20,000.00", "+100.00", "0.50"]],
            },
            {
                "title": "每日收盤行情",
                "fields": ["證券代號", "證券名稱", "成交金額", "漲跌(+/-)", "漲跌價差"],
                "data": [
                    ["1111", "測試一", "100,000", "+", "1.00"],
                    ["2222", "測試二", "80,000", "-", "-1.00"],
                    ["3333", "測試三", "50,000", "", "0.00"],
                ],
            },
        ]
    }


def fake_twse_institutional() -> dict[str, Any]:
    return {
        "fields": ["證券代號", "外資及陸資買賣超股數", "投信買賣超股數", "自營商買賣超股數"],
        "data": [
            ["1111", "1,000", "200", "-50"],
            ["2222", "-300", "100", "20"],
        ],
    }


def fake_tpex_quotes() -> dict[str, Any]:
    return {
        "aaData": [
            ["4444", "上櫃一", "10.00", "1.00"],
            ["5555", "上櫃二", "10.00", "-1.00"],
            ["6666", "上櫃三", "10.00", "0.00"],
        ]
    }


def fake_taifex_futures() -> list[dict[str, Any]]:
    return [
        {
            "Date": TRADE_DATE,
            "Contract": "TX",
            "Close": "20,050",
            "Change": "50",
            "Change%": "0.25",
            "Volume": "12,345",
        }
    ]


def fake_taifex_pcr() -> list[dict[str, Any]]:
    return [
        {
            "Date": TRADE_DATE,
            "Put/Call OI Ratio%": "110.5",
            "Put OI": "100,000",
            "Call OI": "90,000",
        }
    ]


def fake_taifex_oi() -> list[dict[str, Any]]:
    return [
        {"身份別": "外資", "未平倉口數": "10,000", "未平倉口數增減": "500"},
        {"身份別": "投信", "未平倉口數": "1,200", "未平倉口數增減": "-20"},
        {"身份別": "自營商", "未平倉口數": "-2,300", "未平倉口數增減": "100"},
    ]


def fake_fetch_json(url: str, params: dict[str, Any] | None = None) -> Any:
    if "MI_INDEX" in url:
        return fake_twse_quotes()
    if "T86" in url:
        return fake_twse_institutional()
    if "tpex.org.tw" in url:
        return fake_tpex_quotes()
    if "DailyMarketReportFut" in url:
        return fake_taifex_futures()
    if "PutCallRatio" in url:
        return fake_taifex_pcr()
    if "MarketDataOfMajorInstitutionalTraders" in url:
        return fake_taifex_oi()
    raise AssertionError(f"unexpected URL: {url}")


def fake_fetch_with_tpex_failure(url: str, params: dict[str, Any] | None = None) -> Any:
    if "tpex.org.tw" in url:
        raise RuntimeError("synthetic TPEX outage")
    return fake_fetch_json(url, params)


def assert_no_nan(value: Any) -> bool:
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, dict):
        return all(assert_no_nan(child) for child in value.values())
    if isinstance(value, list):
        return all(assert_no_nan(child) for child in value)
    return True


def build_with_fetch(fake_fetch) -> dict[str, Any]:
    original_fetch = fetcher.fetch_json
    fetcher.fetch_json = fake_fetch
    try:
        return fetcher.build_market_context(TRADE_DATE)
    finally:
        fetcher.fetch_json = original_fetch


def main() -> int:
    payload = build_with_fetch(fake_fetch_json)
    failed_payload = build_with_fetch(fake_fetch_with_tpex_failure)

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "market_context.json"
        written_path = fetcher.write_payload(payload, str(output_path))
        roundtrip = json.loads(written_path.read_text(encoding="utf-8"))

    checks = {
        "schema_version": payload.get("schema_version") == fetcher.SCHEMA_VERSION,
        "source_status_ok": all(
            payload["source_status"][source]["status"] == "ok" for source in ("twse", "tpex", "taifex")
        ),
        "taiex_close_parsed": payload["taiex"]["close"] == 20000.0,
        "breadth_ratio_parsed": payload["breadth"]["advance_ratio"] == 0.333333,
        "institutional_parsed": payload["institutional"]["foreign_net"] == 700.0,
        "taifex_parsed": payload["futures"]["tx_close"] == 20050.0 and payload["options"]["pcr"] == 110.5,
        "summary_not_unknown": payload["summary"]["domestic_context_label"] != "UNKNOWN",
        "single_source_failure_warn": failed_payload["source_status"]["tpex"]["status"] == "warn",
        "single_source_failure_keeps_nulls": failed_payload["breadth"]["tpex_up"] is None,
        "single_source_failure_no_crash": failed_payload["schema_version"] == fetcher.SCHEMA_VERSION,
        "failed_source_data_date_null": failed_payload["source_status"]["tpex"]["data_date"] is None,
        "write_payload_roundtrip": roundtrip["trade_date"] == TRADE_DATE,
        "no_nan_payload": assert_no_nan(payload) and "NaN" not in json.dumps(payload, ensure_ascii=False, allow_nan=False),
    }

    status = "OK" if all(checks.values()) else "FAILED"
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(
        json.dumps(
            {
                "status": status,
                "trade_date": TRADE_DATE,
                "checks": checks,
                "sample": {
                    "label": payload["summary"]["domestic_context_label"],
                    "taiex_close": payload["taiex"]["close"],
                    "advance_ratio": payload["breadth"]["advance_ratio"],
                    "source_status": payload["source_status"],
                },
                "failure_sample": {
                    "tpex_status": failed_payload["source_status"]["tpex"],
                    "notes": failed_payload["summary"]["notes"],
                },
            },
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    if status != "OK":
        failed = [name for name, passed in checks.items() if not passed]
        raise SystemExit(f"MARKET_CONTEXT_FETCHER_FAILED failed={failed}")
    print("MARKET_CONTEXT_FETCHER_OK")
    print(ARTIFACT_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
