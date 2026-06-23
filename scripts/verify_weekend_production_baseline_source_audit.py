#!/usr/bin/env python3
"""驗證 production baseline ranking source audit。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build_weekend_production_baseline_source_audit import REQUIRED_COLUMNS, SCHEMA_VERSION, audit_paths
from weekend_training_common import PRODUCTION_IMPACT, repo_path, resolve_path, write_json


VERIFY_SCHEMA_VERSION = "weekend-production-baseline-source-audit-verification.v1"
REQUIRED_TOP_LEVEL_FIELDS = {
    "baseline_source_status",
    "baseline_source_path",
    "date_coverage",
    "required_columns",
    "column_contract_ok",
    "comparable_with_candidate_rankings",
    "can_materialize_artifacts_backtest_production",
    "unlockable_combo_count_estimate",
    "next_action",
    "production_impact",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify production baseline source audit")
    parser.add_argument("--date", required=True)
    parser.add_argument("--artifact", default=None)
    parser.add_argument(
        "--output",
        default="artifacts/weekend_training/weekend_production_baseline_source_audit_verification_latest.json",
    )
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_payload(date: str, artifact: Path) -> dict[str, Any]:
    payload = read_json(artifact)
    can_materialize = payload.get("can_materialize_artifacts_backtest_production") is True
    blocker_reasons = payload.get("blocker_reasons") if isinstance(payload.get("blocker_reasons"), list) else []
    coverage = payload.get("date_coverage") if isinstance(payload.get("date_coverage"), dict) else {}
    missing_fields = sorted(field for field in REQUIRED_TOP_LEVEL_FIELDS if field not in payload)
    required_columns = set(payload.get("required_columns") if isinstance(payload.get("required_columns"), list) else [])
    text = json.dumps(payload, ensure_ascii=False)
    checks = [
        {"name": "artifact_exists", "ok": artifact.exists(), "value": repo_path(artifact)},
        {"name": "schema", "ok": payload.get("schema_version") == SCHEMA_VERSION, "value": payload.get("schema_version")},
        {"name": "status_explicit", "ok": payload.get("status") in {"OK", "BLOCKED"}, "value": payload.get("status")},
        {"name": "required_fields_present", "ok": not missing_fields, "value": missing_fields},
        {
            "name": "required_columns_contract",
            "ok": REQUIRED_COLUMNS.issubset(required_columns),
            "value": sorted(required_columns),
        },
        {
            "name": "production_impact",
            "ok": payload.get("production_impact") == PRODUCTION_IMPACT,
            "value": payload.get("production_impact"),
        },
        {
            "name": "materialize_true_has_source_and_coverage",
            "ok": (not can_materialize)
            or (
                bool(payload.get("baseline_source_path"))
                and bool(coverage.get("start_date"))
                and bool(coverage.get("end_date"))
                and payload.get("column_contract_ok") is True
                and payload.get("comparable_with_candidate_rankings") is True
            ),
            "value": {
                "can_materialize": can_materialize,
                "baseline_source_path": payload.get("baseline_source_path"),
                "date_coverage": coverage,
                "column_contract_ok": payload.get("column_contract_ok"),
                "comparable_with_candidate_rankings": payload.get("comparable_with_candidate_rankings"),
            },
        },
        {
            "name": "materialize_false_has_blocker",
            "ok": can_materialize or bool(blocker_reasons),
            "value": blocker_reasons,
        },
        {
            "name": "blocked_does_not_claim_unlockable_count",
            "ok": can_materialize or int(payload.get("unlockable_combo_count_estimate") or 0) == 0,
            "value": payload.get("unlockable_combo_count_estimate"),
        },
        {"name": "no_promotion_ready", "ok": "PROMOTION_READY" not in text, "value": False},
    ]
    failed = [check for check in checks if not check["ok"]]
    return {
        "schema_version": VERIFY_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": date,
        "status": "OK" if not failed else "FAILED",
        "artifact": repo_path(artifact),
        "summary": {"check_count": len(checks), "failed_count": len(failed)},
        "checks": checks,
        "errors": failed,
    }


def main() -> int:
    args = parse_args()
    default_artifact, _ = audit_paths(args.date)
    artifact = resolve_path(args.artifact) or default_artifact
    output = resolve_path(args.output)
    payload = build_payload(args.date, artifact)
    write_json(output, payload)
    print(
        json.dumps(
            {"status": payload["status"], "failed_count": payload["summary"]["failed_count"], "output": repo_path(output)},
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
