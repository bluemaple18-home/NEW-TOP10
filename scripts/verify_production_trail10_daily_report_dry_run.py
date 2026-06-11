#!/usr/bin/env python3
"""驗證 production trail10 daily report dry-run artifact。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "production-trail10-daily-report-dry-run-verification.v1"
REPORT_SCHEMA = "production-trail10-daily-report-dry-run.v1"
ALLOWED_DECISIONS = {
    "DAILY_REPORT_DRY_RUN_READY",
    "DAILY_REPORT_DRY_RUN_NEEDS_COPY_FIX",
    "DRY_RUN_BLOCKED_INPUT_MISSING",
    "DRY_RUN_BLOCKED_SIGNAL_QUALITY",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify production trail10 daily report dry-run")
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--output", default="artifacts/shadow/production_trail10/production_trail10_daily_report_dry_run_verification_latest.json")
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


def inputs_exist(payload: dict[str, Any]) -> bool:
    if payload.get("decision") == "DRY_RUN_BLOCKED_INPUT_MISSING":
        return bool(payload.get("input_gaps"))
    inputs = payload.get("inputs") if isinstance(payload.get("inputs"), dict) else {}
    for key in ["shadow", "review", "preview", "readiness"]:
        path = resolve_path(inputs.get(key))
        if path is None or not path.exists():
            return False
    return True


def safe_contract(payload: dict[str, Any]) -> bool:
    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    return (
        contract.get("dry_run_only") is True
        and contract.get("changes_official_daily_report") is False
        and contract.get("changes_clawd_payload") is False
        and contract.get("changes_clawd_live_message") is False
        and contract.get("changes_production_ranking") is False
        and contract.get("changes_model") is False
        and contract.get("personalized_sell_instruction") is False
        and contract.get("uses_stale_fallback") is False
        and contract.get("live_send") is False
    )


def copy_guard_ok(payload: dict[str, Any]) -> bool:
    guard = payload.get("copy_guard") if isinstance(payload.get("copy_guard"), dict) else {}
    if payload.get("decision") == "DAILY_REPORT_DRY_RUN_NEEDS_COPY_FIX":
        return bool(guard.get("found_forbidden_phrases"))
    return not guard.get("found_forbidden_phrases") and guard.get("personalized_sell_instruction") is False


def build_payload(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    checks = [
        {"name": "schema", "ok": payload.get("schema_version") == REPORT_SCHEMA, "value": payload.get("schema_version")},
        {"name": "decision_allowed", "ok": payload.get("decision") in ALLOWED_DECISIONS, "value": payload.get("decision")},
        {"name": "safe_contract", "ok": safe_contract(payload), "value": payload.get("contract")},
        {"name": "inputs_exist_or_gaps_declared", "ok": inputs_exist(payload), "value": {"inputs": payload.get("inputs"), "input_gaps": payload.get("input_gaps")}},
        {"name": "copy_guard", "ok": copy_guard_ok(payload), "value": payload.get("copy_guard")},
        {
            "name": "required_fields",
            "ok": all(
                key in payload
                for key in [
                    "schema_version",
                    "run_date",
                    "contract",
                    "inputs",
                    "report_sections",
                    "copy_guard",
                    "trail10_summary",
                    "blocked_reasons",
                    "decision",
                    "next_recommended_action",
                ]
            ),
            "value": sorted(payload),
        },
        {
            "name": "ready_has_sections",
            "ok": payload.get("decision") != "DAILY_REPORT_DRY_RUN_READY" or len(payload.get("report_sections") or []) >= 3,
            "value": len(payload.get("report_sections") or []),
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
