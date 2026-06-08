#!/usr/bin/env python3
"""驗證 CAPITAL-REALISM-06 sizing policy report。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "capital-realism06-sizing-policy-report.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify CAPITAL-REALISM-06 sizing policy report")
    parser.add_argument(
        "--artifact",
        default="artifacts/model_experiments/capital_realism06_sizing_policy_report_2026-06-05.json",
    )
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def main() -> int:
    args = parse_args()
    artifact = resolve_path(args.artifact)
    errors: list[str] = []
    if not artifact.exists():
        errors.append(f"artifact missing: {artifact}")
        print(json.dumps({"status": "FAILED", "errors": errors}, ensure_ascii=False))
        return 1

    payload = json.loads(artifact.read_text(encoding="utf-8"))
    contract = payload.get("contract", {})
    runs = payload.get("runs") or {}
    summary = payload.get("summary") or {}
    decision = payload.get("decision") or {}

    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version mismatch")
    if payload.get("status") != "OK":
        errors.append("status must be OK")
    if contract.get("run_count") != 27 or len(runs) != 27:
        errors.append("expected 27 sizing runs")
    for key in ("research_only", "finite_capital", "odd_lot_default"):
        if not contract.get(key):
            errors.append(f"contract.{key} must be true")
    for key in ("changes_model", "changes_production_ranking", "changes_risk_adjusted_score"):
        if contract.get(key):
            errors.append(f"contract.{key} must be false")

    for run_id, row in runs.items():
        if row.get("buy_lot_size") != 1 or row.get("sell_lot_size") != 1:
            errors.append(f"{run_id}: lot sizes must be 1")
        if not row.get("research_only"):
            errors.append(f"{run_id}: research_only must be true")
        if row.get("changes_model") or row.get("changes_ranking_score"):
            errors.append(f"{run_id}: must not change model or ranking score")
        source = row.get("path")
        if not source or not resolve_path(source).exists():
            errors.append(f"{run_id}: source artifact missing")

    by_setup = summary.get("by_setup") or {}
    if len(by_setup) != 9:
        errors.append("expected 9 setup summaries")
    if not summary.get("return_leader") or not summary.get("balanced_candidate"):
        errors.append("return leader and balanced candidate required")
    if decision.get("status") != "SIZING_POLICY_CANDIDATE_FOUND":
        errors.append("decision.status must be sizing policy candidate found")
    if decision.get("production_change") is not False:
        errors.append("production_change must be false")
    if not decision.get("recommended_next_shadow"):
        errors.append("recommended_next_shadow missing")

    status = "OK" if not errors else "FAILED"
    print(json.dumps({"status": status, "artifact": str(artifact), "errors": errors}, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
