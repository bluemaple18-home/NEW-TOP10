#!/usr/bin/env python3
"""驗證 chip-flow shadow materialized features。"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "chip-flow-materialized-features.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify chip-flow shadow materialized features")
    parser.add_argument(
        "--artifact",
        default="artifacts/model_experiments/chip_flow_materialized_features_2026-06-06.json",
    )
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def csv_header(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        return next(reader)


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
    csv_path = resolve_path((payload.get("outputs") or {}).get("csv", ""))

    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version mismatch")
    if payload.get("status") != "OK":
        errors.append("status must be OK")
    for key in ("research_only", "shadow_materialization_only", "does_not_send_push", "does_not_write_production_features"):
        if contract.get(key) is not True:
            errors.append(f"contract.{key} must be true")
    for key in ("changes_model", "changes_production_ranking", "changes_risk_adjusted_score"):
        if contract.get(key) is not False:
            errors.append(f"contract.{key} must be false")
    if decision.get("production_status") != "BLOCKED":
        errors.append("production must remain blocked")
    if int(summary.get("row_count") or 0) <= 0:
        errors.append("row_count must be positive")
    if int(summary.get("institutional_rows") or 0) <= 0:
        errors.append("institutional rows must be positive")
    if int(summary.get("margin_rows") or 0) <= 0:
        errors.append("margin rows must be positive")
    if not csv_path.exists():
        errors.append("materialized csv missing")
    else:
        header = set(csv_header(csv_path))
        for col in ("institutional_available", "margin_available", "margin_purchase_today_balance"):
            if col not in header:
                errors.append(f"csv missing column: {col}")

    status = "OK" if not errors else "FAILED"
    print(json.dumps({"status": status, "artifact": str(artifact), "errors": errors}, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
