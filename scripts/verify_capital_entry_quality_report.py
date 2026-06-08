#!/usr/bin/env python3
"""驗證有限本金入場品質報告契約。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify capital entry quality report")
    parser.add_argument("--report", default="artifacts/model_experiments/capital_entry_quality_report_2026-06-03.json")
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def main() -> int:
    args = parse_args()
    path = resolve_path(args.report)
    errors: list[str] = []
    if not path.exists():
        errors.append(f"report missing: {path}")
        print(json.dumps({"status": "FAILED", "errors": errors}, ensure_ascii=False))
        return 1
    payload = json.loads(path.read_text(encoding="utf-8"))
    contract = payload.get("contract", {})
    if payload.get("status") != "OK":
        errors.append("status must be OK")
    if not contract.get("research_only"):
        errors.append("must be research_only")
    if contract.get("uses_future_rankings_for_filters"):
        errors.append("entry filters must not use future rankings")
    for key in ("changes_model", "changes_ranking_score", "changes_production_push"):
        if contract.get(key):
            errors.append(f"{key} must be false")
    decision = payload.get("decision", {})
    if decision.get("production_ready"):
        errors.append("production_ready must be false")
    if decision.get("balanced_shadow_candidate") != "non_worsening":
        errors.append("non_worsening should be balanced shadow candidate")
    if decision.get("conservative_shadow_candidate") != "improved_only":
        errors.append("improved_only should be conservative shadow candidate")
    required = {"baseline_half", "baseline_long", "first_day_half", "first_day_long", "non_worsening_half", "non_worsening_long", "improved_only_half", "improved_only_long"}
    if not required.issubset(set(payload.get("runs", {}))):
        errors.append("required runs missing")

    status = "OK" if not errors else "FAILED"
    print(json.dumps({"status": status, "report": str(path), "errors": errors}, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
