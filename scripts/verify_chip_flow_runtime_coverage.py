#!/usr/bin/env python3
"""驗證 chip-flow runtime coverage audit。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "chip-flow-runtime-coverage.v1"
ALLOWED_STATUS = {"OK", "BLOCKED"}
ALLOWED_DECISIONS = {"RUNTIME_COVERAGE_OK", "RUNTIME_COVERAGE_BLOCKED", "RUNTIME_COVERAGE_NOT_MEASURED"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify chip-flow runtime coverage audit")
    parser.add_argument("--artifact", default="artifacts/chip_flow_runtime_coverage_2026-06-06.json")
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
    coverage = payload.get("coverage") or {}
    decision = payload.get("decision") or {}

    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version mismatch")
    if payload.get("status") not in ALLOWED_STATUS:
        errors.append("status not allowed")
    if decision.get("status") not in ALLOWED_DECISIONS:
        errors.append("decision status not allowed")
    for key in ("research_only", "coverage_audit_only", "does_not_send_push"):
        if contract.get(key) is not True:
            errors.append(f"contract.{key} must be true")
    for key in ("changes_model", "changes_production_ranking", "changes_risk_adjusted_score"):
        if contract.get(key) is not False:
            errors.append(f"contract.{key} must be false")
    if decision.get("production_status") != "BLOCKED":
        errors.append("production must remain blocked")
    if "runtime_data_checked" not in coverage:
        errors.append("coverage.runtime_data_checked missing")
    if "institutional_available_rate" not in coverage:
        errors.append("institutional coverage missing")
    if "margin_available_rate" not in coverage:
        errors.append("margin coverage missing")

    status = "OK" if not errors else "FAILED"
    print(json.dumps({"status": status, "artifact": str(artifact), "errors": errors}, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
