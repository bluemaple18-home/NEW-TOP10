#!/usr/bin/env python3
"""以封存官方數值驗證市場解析與失敗契約；不發出網路請求。"""
from __future__ import annotations
import argparse
import gzip
import json
import sys
from pathlib import Path
from unittest.mock import patch
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from app import market_context_fetcher as fetcher
from app.tskg.twse_t86 import build_t86_snapshot
ARTIFACT_PATH = PROJECT_ROOT / "artifacts/market_context_fetcher_verification_latest.json"
TRADE_DATE = "2026-10-22"
FIXTURES = PROJECT_ROOT / "tests/fixtures/market_context_official"
NAMES = {"MI_INDEX": "twse-mi-index", "T86": "twse-t86", "stk_wn1430_result.php": "tpex-quotes", "DailyMarketReportFut": "taifex-futures", "PutCallRatio": "taifex-pcr", "MarketDataOfMajorInstitutionalTradersDetailsOfFuturesContractsBytheDate": "taifex-oi"}
def official(name):
    return json.loads(gzip.decompress((FIXTURES / (name + ".json.gz")).read_bytes()))
def replay(url, params=None):
    return official(NAMES[url.rsplit("/", 1)[-1]])
def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ARTIFACT_PATH)
    args = parser.parse_args(argv)
    with patch.object(fetcher, "fetch_json", replay), patch.object(fetcher, "fetch_pcr", return_value=(official("taifex-pcr"), "json")):
        payload = fetcher.build_market_context(TRADE_DATE)
    def missing(url, params=None):
        if "tpex.org.tw" in url:
            raise RuntimeError("驗證用櫃買中斷")
        return replay(url, params)
    with patch.object(fetcher, "fetch_json", missing), patch.object(fetcher, "fetch_pcr", return_value=(official("taifex-pcr"), "json")):
        failure = fetcher.build_market_context(TRADE_DATE)
    snapshot = build_t86_snapshot(official("twse-t86"), requested_trade_date=TRADE_DATE, retrieved_at="2026-10-25T06:21:20Z")
    def reuse(url, params=None):
        if "T86" in url:
            raise AssertionError("提供snapshot後不得重抓T86")
        return replay(url, params)
    with patch.object(fetcher, "fetch_json", reuse), patch.object(fetcher, "fetch_pcr", return_value=(official("taifex-pcr"), "json")):
        reused = fetcher.build_market_context(TRADE_DATE, twse_t86_snapshot=snapshot)
    sums = {"foreign_net": -284113812, "trust_net": -14647281, "dealer_net": -1553936358}
    checks = {
        "overall_ok": payload["status"] == "ok" and not payload["errors"],
        "sources_ok": all(s["status"] == "ok" for s in payload["source_status"].values()),
        "twse_counts": [payload["breadth"][k] for k in ("twse_up", "twse_down", "twse_flat")] == [303, 959, 99],
        "tpex_counts": [payload["breadth"][k] for k in ("tpex_up", "tpex_down", "tpex_flat")] == [1180, 4667, 332],
        "index": [payload["taiex"][k] for k in ("close", "change", "change_pct")] == [46041.43, -846.34, -1.81],
        "institutional": payload["institutional"] == reused["institutional"] == sums,
        "futures": payload["futures"]["tx_close"] == 46272 and payload["futures"]["contract_month"] == "202611",
        "pcr": payload["options"] == {"pcr": 66.18, "put_oi": 64809, "call_oi": 97930},
        "source_failure_is_error": failure["status"] == "error" and failure["source_status"]["tpex"]["status"] == "error" and bool(failure["errors"].get("tpex")),
        "failure_not_zero": failure["breadth"]["tpex_up"] is None and failure["breadth"]["advance_ratio"] is None,
    }
    result = {"status": "OK" if all(checks.values()) else "FAILED", "trade_date": TRADE_DATE, "checks": checks, "failed": [k for k, ok in checks.items() if not ok], "network": "封存官方fixture；fetch_json／fetch_pcr 皆無真實網路"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "OK" else 1
if __name__ == "__main__":
    raise SystemExit(main())
