#!/usr/bin/env python3
"""驗證 production baseline materialization review artifact。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from build_production_baseline_harness import TARGET_BASELINE_PATH  # noqa: E402
from build_production_baseline_materialization_review import SCHEMA_VERSION, output_paths  # noqa: E402
from weekend_training_common import PRODUCTION_IMPACT, repo_path, resolve_path, write_json  # noqa: E402


VERIFY_SCHEMA_VERSION = "production-baseline-materialization-review-verification.v1"
FORBIDDEN_TEXT = "PROMOTION_READY"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify production baseline materialization review")
    parser.add_argument("--date", required=True)
    parser.add_argument("--artifact", default=None)
    parser.add_argument(
        "--output",
        default="artifacts/weekend_training/production_baseline_materialization_review_verification_latest.json",
    )
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_exact_or_under(path_text: str | None, root: Path) -> bool:
    if not path_text:
        return False
    path = resolve_path(path_text)
    if path is None:
        return False
    try:
        resolved = path.resolve()
        root_resolved = root.resolve()
        return resolved == root_resolved or bool(resolved.relative_to(root_resolved))
    except ValueError:
        return False


def build_payload(date: str, artifact: Path) -> dict[str, Any]:
    review = read_json(artifact)
    text = json.dumps(review, ensure_ascii=False)
    checks_payload = review.get("checks") if isinstance(review.get("checks"), dict) else {}
    allowed = review.get("allowed_date_range") if isinstance(review.get("allowed_date_range"), dict) else {}
    dates = allowed.get("dates") if isinstance(allowed.get("dates"), list) else []
    can_materialize = review.get("can_materialize_research_baseline") is True
    target_output_path = review.get("target_output_path")
    checks = [
        {"name": "artifact_exists", "ok": artifact.exists(), "value": repo_path(artifact)},
        {"name": "schema", "ok": review.get("schema_version") == SCHEMA_VERSION, "value": review.get("schema_version")},
        {
            "name": "review_status_explicit",
            "ok": review.get("materialization_review_status") in {"OK", "BLOCKED"},
            "value": review.get("materialization_review_status"),
        },
        {
            "name": "harness_verification_status_ok",
            "ok": checks_payload.get("harness_verification_ok") is True,
            "value": checks_payload.get("harness_verification_ok"),
        },
        {
            "name": "manifest_provenance_complete",
            "ok": review.get("manifest_provenance_complete") is True
            and checks_payload.get("manifest_provenance_complete") is True,
            "value": review.get("manifest_provenance_complete"),
        },
        {
            "name": "target_output_path_not_artifacts_backtest_production",
            "ok": not is_exact_or_under(str(target_output_path or ""), TARGET_BASELINE_PATH),
            "value": target_output_path,
        },
        {
            "name": "can_materialize_only_three_day_smoke",
            "ok": (not can_materialize)
            or (
                review.get("date_coverage_sufficient_for_smoke") is True
                and len(dates) == 3
                and allowed.get("scope") == "3-day smoke only"
            ),
            "value": allowed,
        },
        {
            "name": "estimated_unlockable_combo_count_zero",
            "ok": int(review.get("estimated_unlockable_combo_count") or 0) == 0,
            "value": review.get("estimated_unlockable_combo_count"),
        },
        {
            "name": "production_impact_no_change",
            "ok": review.get("production_impact") == PRODUCTION_IMPACT,
            "value": review.get("production_impact"),
        },
        {
            "name": "target_production_path_not_created",
            "ok": TARGET_BASELINE_PATH.exists() is False,
            "value": {"path": repo_path(TARGET_BASELINE_PATH), "exists": TARGET_BASELINE_PATH.exists()},
        },
        {"name": "no_promotion_ready", "ok": FORBIDDEN_TEXT not in text, "value": False},
        {
            "name": "ok_status_matches_can_materialize",
            "ok": (review.get("materialization_review_status") == "OK") == can_materialize,
            "value": {
                "materialization_review_status": review.get("materialization_review_status"),
                "can_materialize_research_baseline": can_materialize,
            },
        },
    ]
    failed = [check for check in checks if not check["ok"]]
    return {
        "schema_version": VERIFY_SCHEMA_VERSION,
        "generated_at": now_utc(),
        "date": date,
        "status": "OK" if not failed else "FAILED",
        "artifact": repo_path(artifact),
        "summary": {
            "check_count": len(checks),
            "failed_count": len(failed),
            "materialization_review_status": review.get("materialization_review_status"),
            "can_materialize_research_baseline": can_materialize,
            "production_impact": review.get("production_impact"),
        },
        "checks": checks,
        "errors": failed,
    }


def main() -> int:
    args = parse_args()
    default_artifact, _ = output_paths(args.date)
    artifact = resolve_path(args.artifact) or default_artifact
    output = resolve_path(args.output)
    assert output is not None
    payload = build_payload(args.date, artifact)
    write_json(output, payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "failed_count": payload["summary"]["failed_count"],
                "output": repo_path(output),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
