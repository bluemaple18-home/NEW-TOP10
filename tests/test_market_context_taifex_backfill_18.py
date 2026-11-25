"""TAIFEX openapi 歷史缺口與當日失敗的離線反例。"""

import copy
import json
from types import SimpleNamespace

from app import market_context_fetcher as market
from scripts.run_automation import AutomationRunner, RuntimePaths
from scripts.build_decision_quality import market_context_summary
from scripts.build_feature_experiment_gate import build_market_context_candidate
from tests.test_market_context_fetcher import DATE, ENDPOINTS, official


def _latest_only(monkeypatch):
    # 卡 20 已接歷史來源；此組保留卡 18「來源仍無該日」的下游契約。
    monkeypatch.setattr(market, "fetch_historical", lambda section, date, **kwargs: ([], {
        "status": "unavailable_historical", "fallback_used": False,
    }))
    values = {name: official(name) for name in ENDPOINTS.values()}
    monkeypatch.setattr(market, "fetch_pcr", lambda: (copy.deepcopy(values["taifex-pcr"]), "json"))
    for name in ("taifex-futures", "taifex-oi"):
        for row in values[name]:
            row["Date"] = "20261027"
    monkeypatch.setattr(market, "fetch_json", lambda url, params=None: copy.deepcopy(
        values[ENDPOINTS[url.rsplit("/", 1)[-1]]]
    ))


def test_backfill_identifies_historical_gap_and_preserves_pcr(monkeypatch):
    _latest_only(monkeypatch)
    payload = market.build_market_context(DATE, backfill=True)
    assert payload["status"] == "unavailable_via_openapi"
    assert payload["options"] == {"pcr": 66.18, "put_oi": 64809, "call_oi": 97930}
    assert payload["source_status"]["taifex"]["reason_code"] == "unavailable_historical"
    assert payload["source_status"]["taifex"]["unavailable_components"] == ["futures", "oi"]
    assert payload["unavailable_fields"]["futures.tx_close"]["reason"] == "unavailable_historical"
    assert payload["unavailable_fields"]["futures_oi.foreign_oi"]["reason"] == "unavailable_historical"
    assert payload["summary"]["domestic_context_label"] == "UNKNOWN"
    assert not payload["errors"]


def test_backfill_cli_returns_zero_and_runner_records_unavailable(tmp_path, monkeypatch):
    _latest_only(monkeypatch)
    output = tmp_path / "artifacts" / f"market_context_{DATE}.json"
    monkeypatch.setattr(market, "parse_args", lambda: SimpleNamespace(
        date=DATE, output=str(output), twse_t86_input=None, backfill=True,
    ))
    assert market.main() == 0
    assert json.loads(output.read_text())["status"] == "unavailable_via_openapi"

    runner = object.__new__(AutomationRunner)
    runner.runtime_paths = RuntimePaths(tmp_path, tmp_path, tmp_path)
    runner.run_date = DATE
    runner.backfill = True
    runner.dry_run = False
    runner.status = SimpleNamespace(metadata={}, steps=[])
    runner._run_command = lambda name, command: None
    runner._now = lambda: "2026-10-22T00:00:00Z"
    assert runner._run_market_context({"market_context_enabled": True}) == output
    assert runner.status.metadata["market_context_status"] == "unavailable_via_openapi"
    assert runner.status.steps[-1].status == "UNAVAILABLE"


def test_current_mode_same_missing_rows_still_error(monkeypatch):
    _latest_only(monkeypatch)
    payload = market.build_market_context(DATE, backfill=False)
    assert payload["status"] == "error"
    assert payload["source_status"]["taifex"]["status"] == "error"
    assert payload["errors"]["taifex"]


def test_backfill_malformed_pcr_still_error(monkeypatch):
    _latest_only(monkeypatch)
    monkeypatch.setattr(market, "fetch_pcr", lambda: ([], "json"))
    payload = market.build_market_context(DATE, backfill=True)
    assert payload["status"] == "error"
    assert any("PCR" in warning for warning in payload["errors"]["taifex"])


def test_partial_context_is_not_accepted_by_downstream(tmp_path, monkeypatch):
    _latest_only(monkeypatch)
    payload = market.build_market_context(DATE, backfill=True)
    context_path = tmp_path / f"market_context_{DATE}.json"
    context_path.write_text(json.dumps(payload))
    (tmp_path / "market_context_fetcher_verification_latest.json").write_text(
        json.dumps({"status": "OK", "checks": {"fixture": True}})
    )
    assert market_context_summary(payload, context_path, DATE)["available"] is False
    assert build_market_context_candidate(tmp_path)["shadow_status"] == "BLOCKED"
