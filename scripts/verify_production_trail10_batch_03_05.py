#!/usr/bin/env python3
"""驗證 production trail10 batch 03-05 artifacts。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "production-trail10-batch-03-05-verification.v1"
REVIEW_SCHEMA = "production-trail10-shadow-review.v1"
PREVIEW_SCHEMA = "production-trail10-publish-preview.v1"
READINESS_SCHEMA = "production-trail10-rollout-readiness.v1"
FORBIDDEN_PREVIEW_PHRASES = ("你應該賣出", "賣幾成", "停損價已到，立刻出場", "正式持倉通知")
LIVE_APPROVAL_STEPS = {"LIVE_SEND_APPROVED", "PRODUCTION_ROLLOUT_APPROVED"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify production trail10 batch 03-05")
    parser.add_argument("--date", required=True)
    parser.add_argument("--shadow-dir", default="artifacts/shadow/production_trail10")
    parser.add_argument("--output", default="artifacts/shadow/production_trail10/production_trail10_batch_03_05_verification_latest.json")
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


def artifact_paths(args: argparse.Namespace) -> dict[str, Path]:
    root = resolve_path(args.shadow_dir)
    if root is None:
        raise RuntimeError("shadow dir resolution failed")
    return {
        "review": root / f"production_trail10_shadow_review_{args.date}.json",
        "preview": root / f"production_trail10_publish_preview_{args.date}.json",
        "readiness": root / f"production_trail10_rollout_readiness_{args.date}.json",
    }


def has_forbidden_text(payload: dict[str, Any]) -> bool:
    text = json.dumps(payload.get("message_preview"), ensure_ascii=False)
    return any(phrase in text for phrase in FORBIDDEN_PREVIEW_PHRASES)


def safe_contract(payload: dict[str, Any]) -> bool:
    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    return (
        contract.get("changes_production_ranking") is False
        and contract.get("changes_clawd_live_message") is False
        and contract.get("changes_model") is False
    )


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    paths = artifact_paths(args)
    missing = {key: repo_path(path) for key, path in paths.items() if not path.exists()}
    review = read_json(paths["review"]) if paths["review"].exists() else {}
    preview = read_json(paths["preview"]) if paths["preview"].exists() else {}
    readiness = read_json(paths["readiness"]) if paths["readiness"].exists() else {}
    checks = [
        {"name": "artifacts_exist", "ok": not missing, "value": missing},
        {"name": "review_schema", "ok": review.get("schema_version") == REVIEW_SCHEMA, "value": review.get("schema_version")},
        {"name": "preview_schema", "ok": preview.get("schema_version") == PREVIEW_SCHEMA, "value": preview.get("schema_version")},
        {"name": "readiness_schema", "ok": readiness.get("schema_version") == READINESS_SCHEMA, "value": readiness.get("schema_version")},
        {"name": "dates_consistent", "ok": review.get("run_date") == args.date and preview.get("run_date") == args.date and readiness.get("run_date") == args.date, "value": {"review": review.get("run_date"), "preview": preview.get("run_date"), "readiness": readiness.get("run_date")}},
        {"name": "contracts_safe", "ok": safe_contract(review) and safe_contract(preview) and safe_contract(readiness), "value": {"review": review.get("contract"), "preview": preview.get("contract"), "readiness": readiness.get("contract")}},
        {"name": "preview_no_forbidden_copy", "ok": not has_forbidden_text(preview), "value": preview.get("message_preview")},
        {"name": "readiness_no_live_approval", "ok": readiness.get("decision") not in LIVE_APPROVAL_STEPS and (readiness.get("contract") or {}).get("live_send_approved") is False, "value": {"decision": readiness.get("decision"), "contract": readiness.get("contract")}},
        {"name": "blocked_signal_blocks_preview", "ok": not (review.get("decision") == "SHADOW_SIGNAL_BLOCKED" and preview.get("decision") == "PREVIEW_READY_FOR_REVIEW"), "value": {"review": review.get("decision"), "preview": preview.get("decision")}},
    ]
    failed = [check for check in checks if not check["ok"]]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK" if not failed else "FAILED",
        "date": args.date,
        "summary": {
            "check_count": len(checks),
            "failed_count": len(failed),
            "review_decision": review.get("decision"),
            "preview_decision": preview.get("decision"),
            "readiness_decision": readiness.get("decision"),
        },
        "artifacts": {key: repo_path(path) for key, path in paths.items()},
        "checks": checks,
    }


def main() -> int:
    args = parse_args()
    output = resolve_path(args.output)
    if output is None:
        raise RuntimeError("output resolution failed")
    payload = build_payload(args)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output)}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
