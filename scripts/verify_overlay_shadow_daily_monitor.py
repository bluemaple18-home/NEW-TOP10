#!/usr/bin/env python3
"""驗證 combined overlay shadow daily receipt 與 append-only 不變量。"""

from __future__ import annotations

import json
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = PROJECT_ROOT / "artifacts/model_experiments/overlay_shadow_daily_status.json"
LEDGERS = [
    PROJECT_ROOT / "artifacts/model_experiments/chip_overlay_shadow_ledger_v1.json",
    PROJECT_ROOT / "artifacts/model_experiments/event_overlay_shadow_ledger_v1.json",
    PROJECT_ROOT / "artifacts/model_experiments/volume_climax_warning_shadow_ledger_v1.json",
]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    status = read_json(STATUS_PATH)
    assert status["schema_version"] == "overlay-shadow-daily-monitor.v1"
    assert status["status"] == "OK"
    assert status["promotion_allowed"] is False
    assert status["changes_production_ranking"] is False
    assert status["components"]["chip"]["exit_code"] == 0
    assert status["components"]["event"]["exit_code"] == 0
    assert status["components"]["volume_climax"]["exit_code"] == 0

    automation = yaml.safe_load((PROJECT_ROOT / "config/automation.yaml").read_text(encoding="utf-8"))
    assert automation["daily"]["overlay_append_only_shadow_enabled"] is True

    for name, path in zip(("chip", "event", "volume_climax"), LEDGERS, strict=True):
        ledger = read_json(path)
        observation_dates = [str(row["ranking_date"]) for row in ledger["observations"]]
        assert observation_dates == sorted(set(observation_dates))
        if name != "volume_climax":
            warning_keys = [
                (str(row.get("record")), str(row.get("reason_code")), str(row.get("stage")))
                for row in ledger["warnings_and_exclusions"]
            ]
            assert warning_keys == sorted(set(warning_keys))
        assert ledger["summary"]["promotion_ready"] is False
        appended = int(ledger["last_run_receipt"]["observations_appended"])
        assert appended >= 0
        component = status["components"][name]["result"]
        assert component["observation_count"] == ledger["summary"]["observation_count"]
        assert component["observations_appended"] == appended
        if name != "volume_climax":
            warnings_appended = int(ledger["last_run_receipt"]["warnings_appended"])
            assert warnings_appended >= 0
            assert component["warnings_appended"] == warnings_appended

    regime = read_json(
        PROJECT_ROOT / "artifacts/model_experiments/market_regime_history_append_only_2026-07-22.json"
    )
    regime_markdown = (
        PROJECT_ROOT / "artifacts/model_experiments/market_regime_history_append_only_2026-07-22.md"
    ).read_text(encoding="utf-8")
    assert f"- trade_days: {regime['summary']['trade_days']}" in regime_markdown
    print("OVERLAY_SHADOW_DAILY_MONITOR_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
