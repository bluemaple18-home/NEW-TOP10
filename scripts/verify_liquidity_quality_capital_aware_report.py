#!/usr/bin/env python3
"""驗證流動性品質有限本金 replay 報告。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify liquidity quality capital-aware report")
    parser.add_argument("--artifact", default="artifacts/model_experiments/liquidity_quality_capital_aware_report_2026-06-03.json")
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
    if payload.get("status") != "OK":
        errors.append("status must be OK")
    if not contract.get("research_only"):
        errors.append("must be research_only")
    for key in ("changes_production_ranking", "changes_risk_adjusted_score", "changes_model"):
        if contract.get(key):
            errors.append(f"{key} must be false")
    if not contract.get("finite_capital"):
        errors.append("finite_capital must be true")
    if decision.get("production_ready"):
        errors.append("production_ready must be false")
    if decision.get("default_liquidity_score_change") != "REJECT_AS_DEFAULT":
        errors.append("default liquidity score change must be rejected")
    required_runs = {
        "production_fixed65",
        "log_gate_fixed65",
        "percentile_gate_fixed65",
        "production_fixed85",
        "log_gate_fixed85",
        "percentile_gate_fixed85",
        "production_regime",
        "log_gate_regime",
        "percentile_gate_regime",
        "production_regime_non_worsening",
        "log_gate_regime_non_worsening",
        "log_gate_regime_improved_only",
        "production_regime_h20",
        "log_gate_regime_h20",
        "percentile_gate_regime_h20",
    }
    missing = required_runs - set((payload.get("runs") or {}).keys())
    if missing:
        errors.append(f"missing runs: {sorted(missing)}")

    status = "OK" if not errors else "FAILED"
    print(json.dumps({"status": status, "artifact": str(artifact), "errors": errors}, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
