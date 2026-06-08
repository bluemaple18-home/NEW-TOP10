#!/usr/bin/env python3
"""驗證零股有限本金 replay 矩陣報告。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_RUN_COUNT = 18


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify odd-lot capital matrix report")
    parser.add_argument(
        "--artifact",
        default="artifacts/model_experiments/odd_lot_capital_matrix_report_2026-06-04.json",
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
    decision = payload.get("decision", {})
    runs = payload.get("runs") or {}

    if payload.get("status") != "OK":
        errors.append("status must be OK")
    if payload.get("schema_version") != "odd-lot-capital-matrix-report.v1":
        errors.append("schema_version mismatch")
    if len(runs) != EXPECTED_RUN_COUNT:
        errors.append(f"expected {EXPECTED_RUN_COUNT} runs, got {len(runs)}")

    for key in ("research_only", "finite_capital", "odd_lot_default"):
        if not contract.get(key):
            errors.append(f"contract.{key} must be true")
    for key in ("changes_model", "changes_production_ranking", "changes_risk_adjusted_score"):
        if contract.get(key):
            errors.append(f"contract.{key} must be false")
    if contract.get("buy_lot_size") != 1 or contract.get("sell_lot_size") != 1:
        errors.append("contract lot sizes must both be 1")

    for label, row in runs.items():
        if row.get("buy_lot_size") != 1 or row.get("sell_lot_size") != 1:
            errors.append(f"{label}: run lot sizes must both be 1")
        if not row.get("research_only"):
            errors.append(f"{label}: research_only must be true")
        if row.get("changes_model") or row.get("changes_ranking_score"):
            errors.append(f"{label}: must not change model or ranking score")
        path_text = row.get("path")
        if not path_text or not resolve_path(path_text).exists():
            errors.append(f"{label}: source artifact missing")

    if decision.get("odd_lot_policy") != "ADOPT_AS_DEFAULT_CAPITAL_REPLAY_ASSUMPTION":
        errors.append("odd_lot_policy must be adopted as capital replay assumption")
    if decision.get("tp15_partial_runner") != "REJECT_AS_DEFAULT_EXIT_RULE":
        errors.append("tp15 partial runner must be rejected as default")
    if decision.get("ranking_decision") != "KEEP_K9_MINIMAL_OVERLAY_WITH_BASELINE_CONTROL":
        errors.append("ranking decision must keep K9 minimal overlay with baseline control")

    status = "OK" if not errors else "FAILED"
    print(json.dumps({"status": status, "artifact": str(artifact), "errors": errors}, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
