#!/usr/bin/env python3
"""驗證完整候選池流動性 shadow artifact。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify liquidity quality candidate universe shadow")
    parser.add_argument("--artifact", default="artifacts/liquidity_quality_candidate_universe_shadow_2026-06-03.json")
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
    if payload.get("status") != "OK":
        errors.append("status must be OK")
    if not contract.get("research_only"):
        errors.append("must be research_only")
    for key in ("changes_production_ranking", "changes_risk_adjusted_score", "changes_model"):
        if contract.get(key):
            errors.append(f"{key} must be false")
    if contract.get("candidate_scope") != "full daily StockRanker candidate universe rebuilt in memory":
        errors.append("candidate scope must be full rebuilt universe")
    if not contract.get("tradability_gate_preserved"):
        errors.append("tradability gate must be preserved")
    dates = payload.get("dates", [])
    if not dates:
        errors.append("dates missing")
    for item in dates:
        if int(item.get("candidate_universe_rows") or 0) < 100:
            errors.append(f"{item.get('date')} candidate universe too small")
        variants = item.get("variants", {})
        for variant in ("production", "percentile_gate", "log_gate"):
            rows = (variants.get(variant) or {}).get("items") or []
            if len(rows) != 10:
                errors.append(f"{item.get('date')} {variant} must have 10 rows")
            if variant != "production" and int((variants.get(variant) or {}).get("stats", {}).get("gate_fail_count") or 0) != 0:
                errors.append(f"{item.get('date')} {variant} contains gate failed stock")
    if payload.get("decision", {}).get("production_ready"):
        errors.append("production_ready must be false")

    status = "OK" if not errors else "FAILED"
    print(json.dumps({"status": status, "artifact": str(artifact), "errors": errors}, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
