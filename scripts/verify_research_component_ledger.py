#!/usr/bin/env python3
"""驗證研究元件治理 ledger。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "research-component-ledger-verification.v1"
REPORT_SCHEMA = "research-component-ledger.v1"

ALLOWED_FAMILIES = {"research_registry", "runtime_contract"}
ALLOWED_LIFECYCLE_STATUSES = {
    "production",
    "shadow",
    "report_only",
    "off",
    "reference",
    "diagnostic",
    "blocked",
    "rejected",
}
NON_PRODUCTION_STATUSES = ALLOWED_LIFECYCLE_STATUSES - {"production"}
FORBIDDEN_PROMOTION_STATUSES = {"blocked", "rejected", "off", "diagnostic", "reference"}
FORBIDDEN_PROMOTION_USES = {
    "production_switch",
    "immediate_production_switch",
    "ranking_replacement",
    "publish_order_replacement",
    "unconditional_publish_replacement",
    "direct_production_rerank",
}
LOCAL_ABSOLUTE_MARKERS = ("/Users/", "/private/", "file://")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify research component ledger")
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--output", default="artifacts/model_experiments/research_component_ledger_verification_latest.json")
    return parser.parse_args()


def resolve_path(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def list_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("components") if isinstance(payload.get("components"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def evidence_exists(evidence: list[str]) -> bool:
    if not evidence:
        return False
    for item in evidence:
        path = resolve_path(item)
        if path is None or not path.exists():
            return False
    return True


def has_portable_commands(commands: list[str]) -> bool:
    if not commands:
        return False
    for command in commands:
        text = str(command)
        if any(marker in text for marker in LOCAL_ABSOLUTE_MARKERS):
            return False
    return True


def has_forbidden_promotion_use(row: dict[str, Any]) -> bool:
    allowed = {str(item) for item in row.get("allowed_next_use", [])}
    return bool(allowed & FORBIDDEN_PROMOTION_USES)


def is_guarded_production_mutator(row: dict[str, Any]) -> bool:
    if row.get("changes_production_ranking") is not True:
        return True
    return (
        row.get("lifecycle_status") == "production"
        and row.get("source_status") == "production"
        and row.get("production_baseline") is True
        and row.get("promotion_ready") is False
        and evidence_exists(list(row.get("evidence", [])))
        and bool(row.get("promotion_gates"))
    )


def build_payload(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    rows = list_rows(payload)
    ledger_ids = [str(row.get("ledger_id")) for row in rows]
    lifecycle_by_id = {str(row.get("ledger_id")): str(row.get("lifecycle_status")) for row in rows}
    family_by_id = {str(row.get("ledger_id")): str(row.get("component_family")) for row in rows}

    checks = [
        {"name": "schema", "ok": payload.get("schema_version") == REPORT_SCHEMA, "value": payload.get("schema_version")},
        {"name": "status_ok", "ok": payload.get("status") == "OK", "value": payload.get("status")},
        {
            "name": "ledger_only_contract",
            "ok": contract.get("ledger_only") is True
            and contract.get("uses_existing_artifacts_only") is True
            and contract.get("changes_production_ranking") is False
            and contract.get("changes_clawd_message") is False
            and contract.get("changes_model") is False
            and contract.get("production_switch_ready") is False
            and contract.get("promotion_ready") is False
            and contract.get("runtime_router_available") is True,
            "value": contract,
        },
        {"name": "components_present", "ok": bool(rows), "value": len(rows)},
        {
            "name": "ledger_ids_unique",
            "ok": len(ledger_ids) == len(set(ledger_ids)),
            "value": sorted({item for item in ledger_ids if ledger_ids.count(item) > 1}),
        },
        {
            "name": "families_allowed",
            "ok": all(family in ALLOWED_FAMILIES for family in family_by_id.values()),
            "value": sorted(set(family_by_id.values())),
        },
        {
            "name": "both_families_present",
            "ok": ALLOWED_FAMILIES.issubset(set(family_by_id.values())),
            "value": sorted(set(family_by_id.values())),
        },
        {
            "name": "lifecycles_allowed",
            "ok": all(status in ALLOWED_LIFECYCLE_STATUSES for status in lifecycle_by_id.values()),
            "value": sorted(set(lifecycle_by_id.values())),
        },
        {
            "name": "required_fields_present",
            "ok": all(has_required_fields(row) for row in rows),
            "value": [row.get("ledger_id") for row in rows if not has_required_fields(row)],
        },
        {
            "name": "evidence_exists",
            "ok": all(evidence_exists(list(row.get("evidence", []))) for row in rows),
            "value": {
                row.get("ledger_id"): row.get("evidence")
                for row in rows
                if not evidence_exists(list(row.get("evidence", [])))
            },
        },
        {
            "name": "verification_commands_portable",
            "ok": all(has_portable_commands(list(row.get("verification_commands", []))) for row in rows),
            "value": {
                row.get("ledger_id"): row.get("verification_commands")
                for row in rows
                if not has_portable_commands(list(row.get("verification_commands", [])))
            },
        },
        {
            "name": "non_production_cannot_change_ranking",
            "ok": all(
                row.get("changes_production_ranking") is not True
                for row in rows
                if row.get("lifecycle_status") in NON_PRODUCTION_STATUSES
            ),
            "value": {
                row.get("ledger_id"): row.get("lifecycle_status")
                for row in rows
                if row.get("lifecycle_status") in NON_PRODUCTION_STATUSES
                and row.get("changes_production_ranking") is True
            },
        },
        {
            "name": "production_mutators_guarded",
            "ok": all(is_guarded_production_mutator(row) for row in rows),
            "value": {
                row.get("ledger_id"): {
                    "lifecycle_status": row.get("lifecycle_status"),
                    "source_status": row.get("source_status"),
                    "production_baseline": row.get("production_baseline"),
                    "promotion_ready": row.get("promotion_ready"),
                    "evidence": row.get("evidence"),
                    "promotion_gates": row.get("promotion_gates"),
                }
                for row in rows
                if not is_guarded_production_mutator(row)
            },
        },
        {
            "name": "blocked_rejected_not_promotion_ready",
            "ok": all(
                row.get("promotion_ready") is not True and not has_forbidden_promotion_use(row)
                for row in rows
                if row.get("lifecycle_status") in FORBIDDEN_PROMOTION_STATUSES
            ),
            "value": {
                row.get("ledger_id"): {
                    "lifecycle_status": row.get("lifecycle_status"),
                    "promotion_ready": row.get("promotion_ready"),
                    "allowed_next_use": row.get("allowed_next_use"),
                }
                for row in rows
                if row.get("lifecycle_status") in FORBIDDEN_PROMOTION_STATUSES
                and (row.get("promotion_ready") is True or has_forbidden_promotion_use(row))
            },
        },
        {
            "name": "vwap_has_specific_verification",
            "ok": any(
                row.get("component_id") == "vwap_regime_gated_entry"
                and any("verify_vwap_cost_basis_features.py" in str(command) for command in row.get("verification_commands", []))
                for row in rows
            ),
            "value": {
                row.get("ledger_id"): row.get("verification_commands")
                for row in rows
                if row.get("component_id") == "vwap_regime_gated_entry"
            },
        },
    ]
    failed = [check for check in checks if not check["ok"]]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK" if not failed else "FAILED",
        "artifact": repo_path(path),
        "summary": {
            "check_count": len(checks),
            "failed_count": len(failed),
            "component_count": len(rows),
        },
        "checks": checks,
    }


def has_required_fields(row: dict[str, Any]) -> bool:
    required_scalar_fields = [
        "ledger_id",
        "component_family",
        "component_id",
        "category",
        "source_status",
        "lifecycle_status",
        "effect_type",
        "next_action",
    ]
    required_list_fields = ["evidence", "verification_commands", "blocked_uses", "promotion_gates"]
    if not all(row.get(field) is not None and row.get(field) != "" for field in required_scalar_fields):
        return False
    return all(isinstance(row.get(field), list) for field in required_list_fields)


def main() -> int:
    args = parse_args()
    artifact = resolve_path(args.artifact)
    if artifact is None or not artifact.exists():
        raise FileNotFoundError(f"找不到 artifact：{args.artifact}")
    output = resolve_path(args.output)
    if output is None:
        raise RuntimeError("output resolution failed")
    payload = build_payload(artifact)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output)}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
