#!/usr/bin/env python3
"""驗證 chip-flow readiness 報告。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "chip-flow-readiness.v1"
RUN_DATE = datetime.now().strftime("%Y-%m-%d")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify chip-flow readiness report")
    parser.add_argument(
        "--artifact",
        default=f"artifacts/model_experiments/chip_flow_readiness_report_{RUN_DATE}.json",
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
    matrix = payload.get("capability_matrix") or {}
    gate = payload.get("gate") or {}
    decision = payload.get("decision") or {}
    blockers = payload.get("blockers") or []

    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version mismatch")
    if payload.get("status") != "OK":
        errors.append("status must be OK")

    for key in ("research_only", "static_audit_only", "does_not_send_push", "does_not_fetch_network_data"):
        if contract.get(key) is not True:
            errors.append(f"contract.{key} must be true")
    for key in ("changes_model", "changes_production_ranking", "changes_risk_adjusted_score"):
        if contract.get(key) is not False:
            errors.append(f"contract.{key} must be false")

    if matrix.get("institutional_investor_fetch", {}).get("status") != "PRESENT":
        errors.append("institutional fetcher must be present")
    if matrix.get("margin_purchase_short_sale_fetch", {}).get("status") != "PRESENT":
        errors.append("margin fetcher must be present")
    if matrix.get("institutional_integration", {}).get("status") != "PARTIAL":
        errors.append("institutional integration must be partial")
    if matrix.get("margin_integration", {}).get("status") != "PARTIAL":
        errors.append("margin integration should be partial after integrator wiring")
    if matrix.get("production_ranking_exposure", {}).get("status") != "ABSENT":
        errors.append("production ranking must not expose chip columns yet")

    candidate = gate.get("candidate") or {}
    if candidate.get("id") != "chip_flow":
        errors.append("feature gate chip_flow candidate missing")
    if candidate.get("shadow_status") != "BLOCKED":
        errors.append("chip_flow shadow_status should be BLOCKED")
    if not gate.get("chip_data_contract_artifacts"):
        errors.append("chip_data_contract artifact should be present")
    if not any("replay" in str(item) and "not stable" in str(item) for item in blockers):
        errors.append("warning replay stability blocker not recorded")

    if decision.get("status") != "NOT_READY_FOR_PRODUCTION":
        errors.append("decision.status must be NOT_READY_FOR_PRODUCTION")
    if decision.get("first_promotable_shape") != "research overlay only; not warning channel":
        errors.append("first promotable shape mismatch")
    if "production ranking score" not in set(decision.get("not_usable_now") or []):
        errors.append("production ranking score must be marked not usable")
    if "正式 warning channel" not in set(decision.get("not_usable_now") or []):
        errors.append("production warning channel must be marked not usable")
    if "mainline handoff blocks chip_flow production warning/ranking promotion" not in blockers:
        errors.append("handoff blocker must be recorded")

    if len(payload.get("recommended_shadow_features") or []) < 4:
        errors.append("recommended shadow features too thin")
    if len(payload.get("recommended_warning_candidates") or []) < 4:
        errors.append("recommended warning candidates too thin")

    status = "OK" if not errors else "FAILED"
    print(json.dumps({"status": status, "artifact": str(artifact), "errors": errors}, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
