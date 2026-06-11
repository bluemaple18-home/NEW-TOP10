#!/usr/bin/env python3
"""驗證 production trail10 batch 08-10 artifacts。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "production-trail10-batch-08-10-verification.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify production trail10 batch 08-10")
    parser.add_argument("--date", required=True)
    parser.add_argument("--shadow-dir", default="artifacts/shadow/production_trail10")
    parser.add_argument("--output", default="artifacts/shadow/production_trail10/production_trail10_batch_08_10_verification_latest.json")
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
        and contract.get("changes_production_ranking") is False
        and contract.get("changes_model") is False
        and contract.get("changes_clawd_payload") is False
        and contract.get("changes_clawd_live_message") is False
        and contract.get("live_send") is False
    )


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    root = resolve_path(args.shadow_dir)
    if root is None:
        raise RuntimeError("shadow dir resolution failed")
    paths = {
        "review_loop": root / f"production_trail10_daily_report_review_loop_{args.date}.json",
        "official": root / f"production_trail10_official_daily_report_review_{args.date}.json",
        "integration": root / f"production_trail10_official_daily_report_integration_{args.date}.json",
        "clawd": root / f"production_trail10_clawd_dry_run_preview_{args.date}.json",
    }
    payloads = {key: read_json(path) if path.exists() else {} for key, path in paths.items()}
    useful_days = ((payloads["review_loop"].get("review_window") or {}).get("useful_window_days") or 0)
    official_decision = payloads["official"].get("decision")
    checks = [
        {"name": "artifacts_exist", "ok": all(path.exists() for path in paths.values()), "value": {key: repo_path(path) for key, path in paths.items()}},
        {"name": "contracts_safe", "ok": all(contract_safe(payloads[key]) for key in ["official", "integration", "clawd"]), "value": {key: payloads[key].get("contract") for key in ["official", "integration", "clawd"]}},
        {"name": "not_ready_before_3_days", "ok": not (useful_days < 3 and official_decision == "OFFICIAL_DAILY_REPORT_REVIEW_READY"), "value": {"useful_days": useful_days, "official_decision": official_decision}},
        {"name": "clawd_not_live", "ok": (payloads["clawd"].get("contract") or {}).get("clawd_live_send") is False, "value": payloads["clawd"].get("contract")},
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
            "review_loop_decision": payloads["review_loop"].get("decision"),
            "official_decision": official_decision,
            "integration_decision": payloads["integration"].get("decision"),
            "clawd_decision": payloads["clawd"].get("decision"),
        },
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
