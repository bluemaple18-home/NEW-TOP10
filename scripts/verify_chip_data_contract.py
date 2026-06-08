#!/usr/bin/env python3
"""驗證 chip-flow data contract。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "chip-data-contract.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify chip-flow data contract")
    parser.add_argument("--artifact", default="artifacts/chip_data_contract_2026-06-06.json")
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
    sources = payload.get("sources") or {}
    materialization = payload.get("materialization") or {}
    checks = payload.get("checks") or {}
    decision = payload.get("decision") or {}

    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version mismatch")
    if payload.get("status") != "OK":
        errors.append("status must be OK")
    for key in ("research_only", "does_not_send_push"):
        if contract.get(key) is not True:
            errors.append(f"contract.{key} must be true")
    for key in ("changes_model", "changes_production_ranking", "changes_risk_adjusted_score"):
        if contract.get(key) is not False:
            errors.append(f"contract.{key} must be false")
    if contract.get("missing_value_policy", {}).get("missing_is_not_zero") is not True:
        errors.append("missing value policy must distinguish missing from zero")
    if contract.get("missing_value_policy", {}).get("zero_requires_available_flag") is not True:
        errors.append("zero must require availability flag")
    if contract.get("as_of_policy", {}).get("minimum_lag_trading_days_for_daily_recommendation") < 1:
        errors.append("as-of lag must be at least 1 trading day")

    institutional_cols = set(sources.get("finmind_institutional_investors", {}).get("normalized_columns") or [])
    margin_cols = set(sources.get("finmind_margin_purchase_short_sale", {}).get("normalized_columns") or [])
    for col in ("foreign_buy", "trust_buy", "dealer_buy", "institutional_available"):
        if col not in institutional_cols:
            errors.append(f"institutional column missing: {col}")
    for col in ("margin_purchase_today_balance", "margin_purchase_balance_change", "margin_available"):
        if col not in margin_cols:
            errors.append(f"margin column missing: {col}")
    if materialization.get("raw_cache_required_before_promotion") is not True:
        errors.append("raw cache must be required before promotion")
    if not all(checks.values()):
        errors.append("not all implementation checks passed")
    if decision.get("status") != "CONTRACT_READY_FOR_SHADOW":
        errors.append("decision must be CONTRACT_READY_FOR_SHADOW")
    if decision.get("production_status") != "BLOCKED":
        errors.append("production must remain blocked")

    status = "OK" if not errors else "FAILED"
    print(json.dumps({"status": status, "artifact": str(artifact), "errors": errors}, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
