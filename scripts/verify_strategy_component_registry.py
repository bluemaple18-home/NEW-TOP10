#!/usr/bin/env python3
"""驗證策略零件庫 artifact。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "strategy-component-registry-verification.v1"
REPORT_SCHEMA = "strategy-component-registry.v1"

ALLOWED_STATUSES = {
    "REUSABLE_CANDIDATE",
    "CONDITIONAL_CANDIDATE",
    "DIAGNOSTIC_ONLY",
    "REJECTED",
    "DATA_UNAVAILABLE",
    "REFERENCE_AVAILABLE",
    "MESSAGE_AVAILABLE",
    "NEEDS_TEST",
}

REQUIRED_COMPONENTS = {
    "candidate_ranking",
    "trail10",
    "overlap_first",
    "chip_flow",
    "fundamental_revenue",
    "industry_map",
    "concept_membership",
    "notification_bucket",
    "market_regime_history",
    "market_context",
}

FORBIDDEN_PROMOTION_USES = {
    "production_switch",
    "immediate_production_switch",
    "ranking_replacement",
    "publish_order_replacement",
    "unconditional_publish_replacement",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify strategy component registry")
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--output", default="artifacts/model_experiments/strategy_component_registry_verification_latest.json")
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


def evidence_exists(evidence: list[str]) -> bool:
    for item in evidence:
        path = resolve_path(item)
        if path is None or not path.exists():
            return False
    return True


def has_forbidden_allowed_use(row: dict[str, Any]) -> bool:
    allowed = {str(item) for item in row.get("allowed_next_use", [])}
    return bool(allowed & FORBIDDEN_PROMOTION_USES)


def build_payload(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    components = payload.get("components") if isinstance(payload.get("components"), list) else []
    ids = {str(row.get("component_id")) for row in components if isinstance(row, dict)}
    status_by_id = {
        str(row.get("component_id")): str(row.get("status"))
        for row in components
        if isinstance(row, dict)
    }
    checks = [
        {"name": "schema", "ok": payload.get("schema_version") == REPORT_SCHEMA, "value": payload.get("schema_version")},
        {"name": "status_ok", "ok": payload.get("status") == "OK", "value": payload.get("status")},
        {
            "name": "registry_only_contract",
            "ok": contract.get("registry_only") is True
            and contract.get("uses_existing_artifacts_only") is True
            and contract.get("changes_production_ranking") is False
            and contract.get("changes_clawd_message") is False
            and contract.get("changes_model") is False
            and contract.get("production_switch_ready") is False
            and contract.get("promotion_ready") is False,
            "value": contract,
        },
        {
            "name": "required_components_present",
            "ok": REQUIRED_COMPONENTS.issubset(ids),
            "value": sorted(REQUIRED_COMPONENTS - ids),
        },
        {
            "name": "statuses_allowed",
            "ok": all(str(row.get("status")) in ALLOWED_STATUSES for row in components if isinstance(row, dict)),
            "value": sorted(set(status_by_id.values())),
        },
        {
            "name": "evidence_exists",
            "ok": all(evidence_exists(list(row.get("evidence", []))) for row in components if isinstance(row, dict)),
            "value": {
                row.get("component_id"): row.get("evidence")
                for row in components
                if isinstance(row, dict) and not evidence_exists(list(row.get("evidence", [])))
            },
        },
        {
            "name": "candidate_ranking_conditional",
            "ok": status_by_id.get("candidate_ranking") == "CONDITIONAL_CANDIDATE",
            "value": status_by_id.get("candidate_ranking"),
        },
        {
            "name": "trail10_reusable",
            "ok": status_by_id.get("trail10") == "REUSABLE_CANDIDATE",
            "value": status_by_id.get("trail10"),
        },
        {
            "name": "overlap_rejected",
            "ok": status_by_id.get("overlap_first") == "REJECTED",
            "value": status_by_id.get("overlap_first"),
        },
        {
            "name": "rejected_components_cannot_allow_promotion",
            "ok": all(
                not has_forbidden_allowed_use(row)
                for row in components
                if isinstance(row, dict) and row.get("status") in {"REJECTED", "DATA_UNAVAILABLE", "DIAGNOSTIC_ONLY"}
            ),
            "value": {
                row.get("component_id"): row.get("allowed_next_use")
                for row in components
                if isinstance(row, dict)
                and row.get("status") in {"REJECTED", "DATA_UNAVAILABLE", "DIAGNOSTIC_ONLY"}
                and has_forbidden_allowed_use(row)
            },
        },
        {
            "name": "reference_components_not_alpha",
            "ok": all(
                "standalone_alpha_without_replay" in row.get("blocked_uses", [])
                for row in components
                if isinstance(row, dict) and row.get("status") == "REFERENCE_AVAILABLE"
            ),
            "value": {
                row.get("component_id"): row.get("blocked_uses")
                for row in components
                if isinstance(row, dict) and row.get("status") == "REFERENCE_AVAILABLE"
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
            "component_count": len(components),
        },
        "checks": checks,
    }


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
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output)}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
