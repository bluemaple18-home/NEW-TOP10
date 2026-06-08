#!/usr/bin/env python3
"""驗證 chip composite warning report。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "chip-composite-warning-report.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify chip composite warning report")
    parser.add_argument(
        "--artifact",
        default="artifacts/model_experiments/chip_composite_warning_report_2026-06-08.json",
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
    contract = payload.get("contract") or {}
    summary = payload.get("summary") or {}
    decision = payload.get("decision") or {}
    outcomes = summary.get("group_outcomes") or {}

    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version mismatch")
    if payload.get("status") != "OK":
        errors.append("status must be OK")
    for key in ("research_only", "warning_only", "does_not_send_push"):
        if contract.get(key) is not True:
            errors.append(f"contract.{key} must be true")
    for key in ("changes_model", "changes_production_ranking", "changes_risk_adjusted_score"):
        if contract.get(key) is not False:
            errors.append(f"contract.{key} must be false")
    if decision.get("production_status") != "BLOCKED":
        errors.append("production must remain blocked")
    if int(summary.get("observation_count") or 0) <= 0:
        errors.append("observations missing")
    if int(summary.get("target_date_count") or 0) <= 0:
        errors.append("target dates missing")
    for group in ("COMPOSITE_RISK", "CHIP_RISK_ONLY", "TECH_WEAK_ONLY", "NO_COMPOSITE_RISK"):
        if group not in outcomes:
            errors.append(f"group outcome missing: {group}")

    status = "OK" if not errors else "FAILED"
    print(json.dumps({"status": status, "artifact": str(artifact), "errors": errors}, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
