#!/usr/bin/env python3
"""驗證完整候選池流動性 shadow replay report。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify liquidity candidate universe replay report")
    parser.add_argument("--artifact", default="artifacts/liquidity_quality_candidate_universe_replay_report_2026-06-03.json")
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
    if payload.get("decision", {}).get("production_ready"):
        errors.append("production_ready must be false")
    if not isinstance(contract.get("sample_is_small"), bool):
        errors.append("sample_is_small must be boolean")
    if not contract.get("portfolio_replay_boundary"):
        errors.append("portfolio replay boundary must be explicit")
    if "comparisons_vs_recomputed_production" not in payload:
        errors.append("comparisons missing")

    status = "OK" if not errors else "FAILED"
    print(json.dumps({"status": status, "artifact": str(artifact), "errors": errors}, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
