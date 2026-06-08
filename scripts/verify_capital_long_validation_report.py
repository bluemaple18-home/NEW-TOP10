#!/usr/bin/env python3
"""驗證有限本金長區間報告契約。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify capital long validation report")
    parser.add_argument("--report", default="artifacts/model_experiments/capital_long_validation_report_2026-06-03.json")
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def main() -> int:
    args = parse_args()
    report_path = resolve_path(args.report)
    errors: list[str] = []
    if not report_path.exists():
        errors.append(f"report missing: {report_path}")
        print(json.dumps({"status": "FAILED", "errors": errors}, ensure_ascii=False))
        return 1
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    contract = payload.get("contract", {})
    if payload.get("status") != "OK":
        errors.append("status must be OK")
    if not contract.get("research_only"):
        errors.append("contract.research_only must be true")
    for key in ("changes_model", "changes_ranking_score", "changes_production_push"):
        if contract.get(key):
            errors.append(f"{key} must be false")
    if payload.get("decision", {}).get("production_ready"):
        errors.append("production_ready must be false")
    if payload.get("decision", {}).get("status") != "LONG_VALIDATION_BLOCKS_PRODUCTION_CHANGE":
        errors.append("long validation should block production change")
    if payload.get("long_window", {}).get("return_delta", 0) >= 0:
        errors.append("regime long return should not beat fixed65 in this report")
    if not payload.get("segments"):
        errors.append("segments missing")

    status = "OK" if not errors else "FAILED"
    print(json.dumps({"status": status, "report": str(report_path), "errors": errors}, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
