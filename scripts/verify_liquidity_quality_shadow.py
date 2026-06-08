#!/usr/bin/env python3
"""驗證流動性品質 shadow artifact 邊界。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify liquidity quality shadow")
    parser.add_argument("--artifact", default="artifacts/liquidity_quality_shadow_2026-06-03.json")
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
    summary = payload.get("summary", {})
    dates = payload.get("dates", [])
    if payload.get("status") != "OK":
        errors.append("status must be OK")
    if not contract.get("research_only"):
        errors.append("must be research_only")
    for key in ("changes_production_ranking", "changes_risk_adjusted_score", "changes_model"):
        if contract.get(key):
            errors.append(f"{key} must be false")
    if not contract.get("tradability_gate_preserved"):
        errors.append("tradability gate must be preserved")
    if "existing ranking artifact rows only" not in str(contract.get("source_ranking_scope")):
        errors.append("source scope limitation must be explicit")
    if not dates:
        errors.append("dates missing")
    for variant in ("production", "percentile_gate", "log_gate"):
        if variant not in summary.get("variants", {}):
            errors.append(f"summary missing variant {variant}")
    for item in dates:
        variants = item.get("variants", {})
        for variant in ("production", "percentile_gate", "log_gate"):
            rows = (variants.get(variant) or {}).get("items") or []
            if len(rows) != 10:
                errors.append(f"{item.get('date')} {variant} must have 10 items")
            if variant != "production":
                gate_fail = (variants.get(variant) or {}).get("stats", {}).get("gate_fail_count")
                if int(gate_fail or 0) != 0:
                    errors.append(f"{item.get('date')} {variant} contains gate-failed item")
    if payload.get("decision", {}).get("production_ready"):
        errors.append("production_ready must be false")

    status = "OK" if not errors else "FAILED"
    print(json.dumps({"status": status, "artifact": str(artifact), "errors": errors}, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
