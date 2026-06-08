#!/usr/bin/env python3
"""驗證有限本金出場規則報告契約。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify capital exit rule report")
    parser.add_argument("--report", default="artifacts/model_experiments/capital_exit_rule_report_2026-06-03.json")
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def main() -> int:
    args = parse_args()
    report_path = resolve_path(args.report)
    errors: list[str] = []
    if not report_path.exists():
        fail(errors, f"report missing: {report_path}")
        print(json.dumps({"status": "FAILED", "errors": errors}, ensure_ascii=False))
        return 1

    payload: dict[str, Any] = json.loads(report_path.read_text(encoding="utf-8"))
    contract = payload.get("contract", {})
    if payload.get("status") != "OK":
        fail(errors, "report status is not OK")
    if not contract.get("research_only"):
        fail(errors, "report must be research_only")
    for key in ("changes_model", "changes_ranking_score", "changes_production_push"):
        if contract.get(key):
            fail(errors, f"{key} must be false")

    rows = payload.get("runs", [])
    names = {row.get("name") for row in rows}
    required = {
        "baseline_fixed40_fixed65",
        "candidate_fixed40_regime",
        "tp15_sell33_regime",
        "tp15_sell40_regime",
        "tp15_sell50_regime",
        "tp20_sell33_regime",
        "tp20_sell50_regime",
    }
    missing = sorted(required - names)
    if missing:
        fail(errors, f"missing runs: {missing}")

    for row in rows:
        if not row.get("research_only"):
            fail(errors, f"{row.get('name')} is not research_only")
        if row.get("changes_model") or row.get("changes_ranking_score"):
            fail(errors, f"{row.get('name')} changes production boundary")
        if row.get("initial_cash") != 500000.0:
            fail(errors, f"{row.get('name')} initial cash must be 500000")
        if row.get("buy_lot_size") != 100:
            fail(errors, f"{row.get('name')} buy lot size must be 100")

    decisions = payload.get("decisions", {})
    if decisions.get("production_boundary", {}).get("promotion_ready"):
        fail(errors, "promotion_ready must stay false")
    if decisions.get("winner") != "candidate_fixed40_regime":
        fail(errors, "winner must currently be candidate_fixed40_regime")
    if decisions.get("tp_partial_runner", {}).get("decision") != "REJECT_AS_PRIMARY_RULE":
        fail(errors, "TP partial runner must not be accepted as primary rule")

    status = "OK" if not errors else "FAILED"
    print(json.dumps({"status": status, "report": str(report_path), "errors": errors}, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
