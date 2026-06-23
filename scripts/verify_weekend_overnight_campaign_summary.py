#!/usr/bin/env python3
"""驗證 weekend overnight campaign summary。

Verifier 只讀 artifact；不執行 replay、不修改任何 production 資源。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from weekend_training_common import PRODUCTION_IMPACT, WEEKEND_DIR, read_json, repo_path, rollup_paths, write_json


REPORT_DATE = "2026-06-17"
TRAINING_DATE = "2026-06-13"
VERIFICATION_PATH = WEEKEND_DIR / "overnight_campaign_summary_verification_latest.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify weekend overnight campaign summary")
    parser.add_argument("--date", default=REPORT_DATE)
    parser.add_argument("--training-date", default=TRAINING_DATE)
    return parser.parse_args()


def artifact_path(stem: str, date: str) -> Path:
    return WEEKEND_DIR / f"{stem}_{date}.json"


def check(name: str, condition: bool, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"name": name, "passed": bool(condition), "details": details or {}}


def int_value(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def build_verification(date: str, training_date: str) -> dict[str, Any]:
    rollup_path, _ = rollup_paths(training_date)
    rollup = read_json(rollup_path)
    rollup_summary = rollup.get("summary") if isinstance(rollup.get("summary"), dict) else {}
    paths = {
        "provenance_design": artifact_path("weekend_production_baseline_provenance_design", date),
        "topic_default_audit": artifact_path("weekend_topic_default_entry_filter_contract_audit", date),
        "regime_slice_audit": artifact_path("weekend_regime_slice_data_adequacy_audit", date),
        "summary": artifact_path("overnight_campaign_summary", date),
    }
    payloads = {key: read_json(path) for key, path in paths.items()}
    summary = payloads["summary"]
    provenance = payloads["provenance_design"]
    topic_default = payloads["topic_default_audit"]
    regime = payloads["regime_slice_audit"]
    progress = summary.get("research_map_progress_change") if isinstance(summary.get("research_map_progress_change"), dict) else {}
    gate = summary.get("gate_summary") if isinstance(summary.get("gate_summary"), dict) else {}
    checks = [
        check("all_required_artifacts_exist", all(path.exists() for path in paths.values()), {key: repo_path(path) for key, path in paths.items()}),
        check("summary_status_ok", summary.get("status") == "OK", {"status": summary.get("status")}),
        check("production_impact_no_change", summary.get("production_impact") == PRODUCTION_IMPACT, {"production_impact": summary.get("production_impact")}),
        check("actual_replay_count_zero", int_value(summary.get("actual_replay_count"), -1) == 0, {"actual_replay_count": summary.get("actual_replay_count")}),
        check(
            "smoke_replay_skipped_no_gate",
            gate.get("smoke_replay_status") == "SKIPPED_GATE_NOT_PASSED" and gate.get("any_gate_passed") is False,
            gate,
        ),
        check(
            "artifact_blocker_count_matches_rollup",
            int_value(progress.get("artifact_blocker_count")) == int_value(rollup_summary.get("artifact_blocker_count")) == 202176,
            {
                "summary_artifact_blocker_count": progress.get("artifact_blocker_count"),
                "rollup_artifact_blocker_count": rollup_summary.get("artifact_blocker_count"),
            },
        ),
        check(
            "topic_default_count_matches_rollup",
            int_value((topic_default.get("summary") or {}).get("unsupported_reason_count"))
            == int_value((rollup_summary.get("unsupported_reason_top_counts") or {}).get("UNSUPPORTED_ENTRY_FILTER:TOPIC_DEFAULT"))
            == 88695,
            {
                "topic_default_audit_count": (topic_default.get("summary") or {}).get("unsupported_reason_count"),
                "rollup_count": (rollup_summary.get("unsupported_reason_top_counts") or {}).get("UNSUPPORTED_ENTRY_FILTER:TOPIC_DEFAULT"),
            },
        ),
        check(
            "regime_slice_count_matches_rollup",
            int_value((regime.get("summary") or {}).get("unsupported_category_count"))
            == int_value((rollup_summary.get("unsupported_category_counts") or {}).get("UNSUPPORTED_REGIME_SLICE_NO_DATA"))
            == 283824,
            {
                "regime_audit_count": (regime.get("summary") or {}).get("unsupported_category_count"),
                "rollup_count": (rollup_summary.get("unsupported_category_counts") or {}).get("UNSUPPORTED_REGIME_SLICE_NO_DATA"),
            },
        ),
        check(
            "expanded_progress_not_increased_by_artifact_blocker",
            int_value(progress.get("expanded_processed_increase_from_artifact_blocker"), -1) == 0,
            progress,
        ),
        check(
            "provenance_design_does_not_allow_materialization",
            (provenance.get("gate") or {}).get("materialize_artifacts_backtest_production_allowed") is False,
            provenance.get("gate") if isinstance(provenance.get("gate"), dict) else {},
        ),
        check(
            "topic_default_does_not_allow_log_or_percentile_mapping",
            (topic_default.get("gate") or {}).get("allow_mapping_to_log_gate") is False
            and (topic_default.get("gate") or {}).get("allow_mapping_to_percentile_gate") is False,
            topic_default.get("gate") if isinstance(topic_default.get("gate"), dict) else {},
        ),
        check(
            "regime_slice_holds_unsupported",
            all((item.get("maintain_unsupported") is True and item.get("enough_for_replay") is False) for item in regime.get("slices", [])),
            {"slice_count": len(regime.get("slices", [])) if isinstance(regime.get("slices"), list) else 0},
        ),
    ]
    status = "OK" if all(item["passed"] for item in checks) else "FAILED"
    return {
        "schema_version": "weekend-overnight-campaign-summary-verification.v1",
        "date": date,
        "training_date": training_date,
        "status": status,
        "artifact": repo_path(paths["summary"]),
        "production_impact": PRODUCTION_IMPACT,
        "checks": checks,
        "errors": [item["name"] for item in checks if not item["passed"]],
    }


def main() -> int:
    args = parse_args()
    payload = build_verification(args.date, args.training_date)
    write_json(VERIFICATION_PATH, payload)
    print(json.dumps({"status": payload["status"], "artifact": payload["artifact"], "errors": payload["errors"]}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
