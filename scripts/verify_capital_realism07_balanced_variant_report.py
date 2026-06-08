#!/usr/bin/env python3
"""驗證 CAPITAL-REALISM-07 balanced variant report。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "capital-realism07-balanced-variant-report.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify CAPITAL-REALISM-07 balanced variant report")
    parser.add_argument(
        "--artifact",
        default="artifacts/model_experiments/capital_realism07_balanced_variant_report_2026-06-05.json",
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
    if contract.get("run_count") != 9 or len(runs) != 9:
        errors.append("expected 9 balanced variant runs")
    if contract.get("sizing_policy") != "p12_open8_new2":
        errors.append("sizing policy must be p12_open8_new2")
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
        source = row.get("path")
        if not source or not resolve_path(source).exists():
            errors.append(f"{run_id}: source artifact missing")

    if set((summary.get("by_variant") or {}).keys()) != {"current", "feature_k9", "sector_k9"}:
        errors.append("by_variant must contain current, feature_k9, sector_k9")
    if decision.get("status") != "BALANCED_SIZING_ROBUST_RANKING_VARIANT_NOT_PROMOTED":
        errors.append("decision.status mismatch")
    if decision.get("ranking_variant_promotion") is not False:
        errors.append("ranking_variant_promotion must be false")
    if decision.get("production_change") is not False:
        errors.append("production_change must be false")

    status = "OK" if not errors else "FAILED"
    print(json.dumps({"status": status, "artifact": str(artifact), "errors": errors}, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
