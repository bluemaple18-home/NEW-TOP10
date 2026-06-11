#!/usr/bin/env python3
"""驗證 production trail10 daily report review loop。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "production-trail10-daily-report-review-loop-verification.v1"
REPORT_SCHEMA = "production-trail10-daily-report-review-loop.v1"
ALLOWED_DECISIONS = {
    "CONTINUE_DRY_RUN_REVIEW_LOOP",
    "READY_FOR_OFFICIAL_DAILY_REPORT_REVIEW",
    "BLOCKED_BY_COPY_RISK",
    "BLOCKED_BY_SIGNAL_QUALITY",
    "BLOCKED_BY_INPUT_GAPS",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify production trail10 daily report review loop")
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--output", default="artifacts/shadow/production_trail10/production_trail10_daily_report_review_loop_verification_latest.json")
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


def contract_safe(payload: dict[str, Any]) -> bool:
    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    return (
        contract.get("changes_official_daily_report") is False
        and contract.get("changes_clawd_payload") is False
        and contract.get("changes_clawd_live_message") is False
        and contract.get("live_send_approved") is False
        and contract.get("uses_stale_fallback") is False
    )


def build_payload(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    window = payload.get("review_window") if isinstance(payload.get("review_window"), dict) else {}
    ready_with_too_few = payload.get("decision") == "READY_FOR_OFFICIAL_DAILY_REPORT_REVIEW" and int(window.get("useful_window_days") or 0) < 3
    daily = payload.get("daily_results") if isinstance(payload.get("daily_results"), list) else []
    checks = [
        {"name": "schema", "ok": payload.get("schema_version") == REPORT_SCHEMA, "value": payload.get("schema_version")},
        {"name": "decision_allowed", "ok": payload.get("decision") in ALLOWED_DECISIONS, "value": payload.get("decision")},
        {"name": "contract_safe", "ok": contract_safe(payload), "value": payload.get("contract")},
        {"name": "not_ready_with_fewer_than_3_days", "ok": not ready_with_too_few, "value": window},
        {"name": "daily_results_present_or_blocked", "ok": bool(daily) or payload.get("decision") == "BLOCKED_BY_INPUT_GAPS", "value": len(daily)},
        {"name": "no_personalized_sell_issue_when_ready", "ok": not (payload.get("decision") == "READY_FOR_OFFICIAL_DAILY_REPORT_REVIEW" and any("personalized_sell_instruction" in row.get("issues", []) for row in daily)), "value": daily},
    ]
    failed = [check for check in checks if not check["ok"]]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK" if not failed else "FAILED",
        "artifact": repo_path(path),
        "summary": {"check_count": len(checks), "failed_count": len(failed), "decision": payload.get("decision")},
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
