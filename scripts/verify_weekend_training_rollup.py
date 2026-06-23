#!/usr/bin/env python3
"""驗證 weekend training rollup。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from weekend_training_common import PROJECT_ROOT, UNSUPPORTED_CATEGORIES, repo_path, resolve_path, rollup_paths, write_json


SCHEMA_VERSION = "weekend-training-rollup-verification.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify weekend training rollup")
    parser.add_argument("--date", required=True)
    parser.add_argument("--artifact", default=None)
    parser.add_argument("--output", default="artifacts/weekend_training/weekend_training_rollup_verification_latest.json")
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def source_audit_path(date: str) -> Path:
    return PROJECT_ROOT / "artifacts" / "weekend_training" / f"weekend_production_baseline_source_audit_{date}.json"


def build_payload(date: str, artifact: Path) -> dict[str, Any]:
    payload = read_json(artifact)
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    required = {
        "full_universe_total",
        "processed_before",
        "processed_after",
        "executed_replay_count",
        "equivalence_inherited_count",
        "rule_pruned_count",
        "unsupported_count",
        "low_information_count",
        "next_stage_count",
        "rejected_count",
    }
    md_path = artifact.with_suffix(".md")
    md_text = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
    classified_total = int(summary.get("rollup_classified_total") or 0)
    full_total = int(summary.get("full_universe_total") or 0)
    unsupported_category_counts = summary.get("unsupported_category_counts") if isinstance(summary.get("unsupported_category_counts"), dict) else {}
    unsupported_category_sum = sum(int(value or 0) for value in unsupported_category_counts.values())
    unknown_unsupported_categories = sorted(str(key) for key in unsupported_category_counts if str(key) not in UNSUPPORTED_CATEGORIES)
    artifact_category_counts = summary.get("artifact_blocker_category_counts") if isinstance(summary.get("artifact_blocker_category_counts"), dict) else {}
    artifact_reason_counts = summary.get("artifact_blocker_reason_top_counts") if isinstance(summary.get("artifact_blocker_reason_top_counts"), dict) else {}
    artifact_blocker_count = int(summary.get("artifact_blocker_count") or 0)
    audit_path = source_audit_path(date)
    source_audit = read_json(audit_path)
    source_audit_count = int((source_audit.get("summary") or {}).get("missing_baseline_rows") or 0)
    source_audit_is_blocked = (
        source_audit.get("status") == "BLOCKED"
        and source_audit.get("can_materialize_artifacts_backtest_production") is False
    )
    checks = [
        {"name": "artifact_exists", "ok": artifact.exists(), "value": repo_path(artifact)},
        {"name": "markdown_exists", "ok": md_path.exists(), "value": repo_path(md_path)},
        {"name": "schema", "ok": payload.get("schema_version") == "weekend-training-rollup.v1", "value": payload.get("schema_version")},
        {"name": "required_summary_keys", "ok": required.issubset(summary), "value": sorted(set(summary) & required)},
        {"name": "rollup_counts_add_to_full_universe", "ok": classified_total == full_total, "value": {"classified": classified_total, "full": full_total}},
        {
            "name": "unsupported_breakdown_sums_to_unsupported_count",
            "ok": unsupported_category_sum == int(summary.get("unsupported_count") or 0),
            "value": {"category_sum": unsupported_category_sum, "unsupported_count": summary.get("unsupported_count")},
        },
        {
            "name": "unsupported_categories_known",
            "ok": not unknown_unsupported_categories,
            "value": unknown_unsupported_categories,
        },
        {
            "name": "artifact_blocker_count_matches_source_audit",
            "ok": (not source_audit_is_blocked and artifact_blocker_count == 0)
            or (source_audit_is_blocked and artifact_blocker_count == source_audit_count),
            "value": {
                "rollup": artifact_blocker_count,
                "source_audit": source_audit_count,
                "source_status": source_audit.get("status"),
            },
        },
        {
            "name": "artifact_blocker_count_within_unsupported",
            "ok": 0 <= artifact_blocker_count <= int(summary.get("unsupported_count") or 0),
            "value": {"artifact_blocker_count": artifact_blocker_count, "unsupported_count": summary.get("unsupported_count")},
        },
        {
            "name": "artifact_blocker_category_count",
            "ok": sum(int(value or 0) for value in artifact_category_counts.values()) == artifact_blocker_count
            and (
                artifact_blocker_count == 0
                or int(artifact_category_counts.get("ARTIFACT_BLOCKER_PROVENANCE_GAP") or 0) == artifact_blocker_count
            ),
            "value": artifact_category_counts,
        },
        {
            "name": "artifact_blocker_reason_count",
            "ok": artifact_blocker_count == 0
            or int(artifact_reason_counts.get("MISSING_BASELINE_RANKINGS_DIR:artifacts/backtest/production") or 0) == artifact_blocker_count,
            "value": artifact_reason_counts,
        },
        {"name": "processed_after_not_less_than_before", "ok": int(summary.get("processed_after") or 0) >= int(summary.get("processed_before") or 0), "value": {"before": summary.get("processed_before"), "after": summary.get("processed_after")}},
        {"name": "no_promotion_ready", "ok": "PROMOTION_READY" not in json.dumps(payload, ensure_ascii=False) and "PROMOTION_READY" not in md_text, "value": False},
        {"name": "production_impact", "ok": payload.get("production_impact") == "NO_PRODUCTION_CHANGE", "value": payload.get("production_impact")},
    ]
    failed = [check for check in checks if not check["ok"]]
    return {
        "schema_version": SCHEMA_VERSION,
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
    default_artifact, _ = rollup_paths(args.date)
    artifact = resolve_path(args.artifact) or default_artifact
    output = resolve_path(args.output)
    payload = build_payload(args.date, artifact)
    write_json(output, payload)
    print(json.dumps({"status": payload["status"], "failed_count": payload["summary"]["failed_count"], "output": repo_path(output)}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
