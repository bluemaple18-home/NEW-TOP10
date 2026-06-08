#!/usr/bin/env python3
"""驗證 calibrated warning-only dry-run 訊息 artifact。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "capital-realism05-warning-dry-run-message.v1"
BLOCKED_TERMS = ("賣出", "全賣", "減碼", "停損", "出場", "砍掉", "一定要")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify CAPITAL-REALISM-05 warning dry-run message")
    parser.add_argument(
        "--artifact",
        default="artifacts/model_experiments/capital_realism05_warning_dry_run_message_2026-06-05.json",
    )
    parser.add_argument("--max-message-chars", type=int, default=1800)
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
    contract = payload.get("contract", {})
    summary = payload.get("summary", {})
    selected = payload.get("selected_items") or []
    message = str(payload.get("message") or "")
    decision = payload.get("decision", {})

    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version mismatch")
    if payload.get("status") != "OK":
        errors.append("status must be OK")
    for key in ("research_only", "dry_run_only", "does_not_send_push", "non_personal_warning_only", "no_personal_holdings"):
        if not contract.get(key):
            errors.append(f"contract.{key} must be true")
    for key in ("changes_model", "changes_production_ranking", "changes_risk_adjusted_score"):
        if contract.get(key):
            errors.append(f"contract.{key} must be false")
    if contract.get("risk_alert_suppressed") is not True:
        errors.append("RISK_ALERT must be suppressed")
    if contract.get("allowed_levels") != ["WEAKENING"]:
        errors.append("allowed_levels must be WEAKENING only")
    if int(summary.get("selected_items") or 0) != len(selected):
        errors.append("selected_items summary mismatch")
    if int(summary.get("message_chars") or 0) > args.max_message_chars:
        errors.append("message too long")
    for item in selected:
        if item.get("warning_level") != "WEAKENING":
            errors.append(f"{item.get('stock_id')}: selected item must be WEAKENING")
    blocked_hits = [term for term in BLOCKED_TERMS if term in message]
    if blocked_hits:
        errors.append(f"message contains blocked direct-trade terms: {blocked_hits}")
    if decision.get("status") != "WARNING_DRY_RUN_MESSAGE_READY":
        errors.append("decision.status must be WARNING_DRY_RUN_MESSAGE_READY")
    if decision.get("recommendation_channel") != "NO_CHANGE":
        errors.append("recommendation channel must remain unchanged")
    if decision.get("warning_channel") != "RESEARCH_ONLY_NOT_PUSH":
        errors.append("warning channel must stay research-only")

    status = "OK" if not errors else "FAILED"
    print(json.dumps({"status": status, "artifact": str(artifact), "errors": errors}, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
