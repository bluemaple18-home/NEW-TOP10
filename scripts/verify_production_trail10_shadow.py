#!/usr/bin/env python3
"""驗證 production trail10 shadow artifact。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "production-trail10-shadow-verification.v1"
REPORT_SCHEMA = "production-trail10-shadow.v1"
REQUIRED_STATUSES = {"candidate_active", "min_hold_not_met", "hold", "trail_stop_zone", "exit_triggered", "expired_or_removed"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify production trail10 shadow")
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--output", default="artifacts/shadow/production_trail10/production_trail10_shadow_verification_latest.json")
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


def output_paths_exist(payload: dict[str, Any]) -> bool:
    outputs = payload.get("outputs") if isinstance(payload.get("outputs"), dict) else {}
    for key in ["json", "markdown", "latest"]:
        path = resolve_path(outputs.get(key))
        if path is None or not path.exists():
            return False
    return True


def min_hold_respected(rows: list[dict[str, Any]]) -> bool:
    for row in rows:
        if row.get("status") != "exit_triggered":
            continue
        if int(row.get("days_held") or 0) < int(row.get("min_holding_days") or 5):
            return False
    return True


def no_personal_sell(rows: list[dict[str, Any]]) -> bool:
    return all(row.get("personalized_sell_instruction") is False for row in rows if isinstance(row, dict))


def build_payload(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    positions = payload.get("shadow_positions") if isinstance(payload.get("shadow_positions"), list) else []
    warnings = payload.get("warning_candidates") if isinstance(payload.get("warning_candidates"), list) else []
    status_set = {str(row.get("status")) for row in positions if isinstance(row, dict)}
    checks = [
        {"name": "schema", "ok": payload.get("schema_version") == REPORT_SCHEMA, "value": payload.get("schema_version")},
        {"name": "status_ok", "ok": payload.get("status") == "OK", "value": payload.get("status")},
        {
            "name": "contract_safe",
            "ok": contract.get("shadow_only") is True
            and contract.get("production_ranking_source_unchanged") is True
            and contract.get("changes_production_ranking") is False
            and contract.get("changes_clawd_live_message") is False
            and contract.get("changes_model") is False
            and contract.get("personalized_sell_instruction") is False
            and contract.get("uses_future_data_for_exit") is False
            and contract.get("does_not_send_push") is True,
            "value": contract,
        },
        {"name": "production_top10_present", "ok": len(payload.get("production_top10") or []) > 0, "value": len(payload.get("production_top10") or [])},
        {"name": "shadow_positions_present", "ok": len(positions) > 0, "value": len(positions)},
        {"name": "allowed_statuses", "ok": status_set.issubset(REQUIRED_STATUSES), "value": sorted(status_set)},
        {"name": "min_hold_respected", "ok": min_hold_respected(positions), "value": None},
        {"name": "positions_not_personal_sell", "ok": no_personal_sell(positions), "value": None},
        {"name": "warnings_not_personal_sell", "ok": no_personal_sell(warnings), "value": None},
        {"name": "outputs_exist", "ok": output_paths_exist(payload), "value": payload.get("outputs")},
        {
            "name": "required_fields",
            "ok": all(
                key in payload
                for key in [
                    "schema_version",
                    "run_date",
                    "contract",
                    "inputs",
                    "production_top10",
                    "shadow_positions",
                    "shadow_events",
                    "exit_policy",
                    "capital_policy",
                    "warning_candidates",
                    "decision",
                    "blocked_reasons",
                ]
            ),
            "value": sorted(payload),
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
            "decision": payload.get("decision"),
            "status_counts": (payload.get("summary") or {}).get("status_counts"),
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
