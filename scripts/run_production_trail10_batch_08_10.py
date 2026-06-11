#!/usr/bin/env python3
"""執行 production trail10 batch 08-10 gate。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="run production trail10 batch 08-10")
    parser.add_argument("--date", default=datetime.now().date().isoformat())
    parser.add_argument("--shadow-dir", default="artifacts/shadow/production_trail10")
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


def write_artifact(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    path.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")


def base_contract() -> dict[str, Any]:
    return {
        "changes_official_daily_report": False,
        "changes_production_ranking": False,
        "changes_model": False,
        "changes_clawd_payload": False,
        "changes_clawd_live_message": False,
        "live_send": False,
        "dry_run_only": True,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {payload['schema_version']} - {payload['run_date']}",
        "",
        f"- decision: `{payload['decision']}`",
    ]
    if payload.get("blocked_reasons"):
        lines.extend(["", "## Blockers", ""])
        lines.extend([f"- {item}" for item in payload["blocked_reasons"]])
    return "\n".join(lines) + "\n"


def build_payloads(args: argparse.Namespace) -> dict[str, dict[str, Any]]:
    root = resolve_path(args.shadow_dir)
    if root is None:
        raise RuntimeError("shadow dir resolution failed")
    review_loop_path = root / f"production_trail10_daily_report_review_loop_{args.date}.json"
    review_loop = read_json(review_loop_path) if review_loop_path.exists() else {}
    review_ready = review_loop.get("decision") == "READY_FOR_OFFICIAL_DAILY_REPORT_REVIEW"
    available_days = ((review_loop.get("review_window") or {}).get("useful_window_days") or 0)
    if review_ready:
        official_decision = "OFFICIAL_DAILY_REPORT_REVIEW_READY"
        blocked = []
        integration_decision = "OFFICIAL_DAILY_REPORT_INTEGRATION_PLAN_READY"
        clawd_decision = "CLAWD_DRY_RUN_PREVIEW_READY"
    else:
        official_decision = "CONTINUE_DRY_RUN_REVIEW_LOOP"
        blocked = ["review_loop_not_ready_or_fewer_than_3_days"]
        integration_decision = "OFFICIAL_DAILY_REPORT_INTEGRATION_BLOCKED"
        clawd_decision = "CLAWD_DRY_RUN_PREVIEW_BLOCKED"
    official = {
        "schema_version": "production-trail10-official-daily-report-review.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_date": args.date,
        "contract": base_contract(),
        "inputs": {"review_loop": repo_path(review_loop_path), "review_loop_decision": review_loop.get("decision"), "useful_window_days": available_days},
        "decision": official_decision,
        "blocked_reasons": blocked,
        "next_recommended_action": "CONTINUE_DRY_RUN_UNTIL_3_OK_DAYS" if blocked else "PLAN_OFFICIAL_DAILY_REPORT_DRY_INTEGRATION",
    }
    integration = {
        "schema_version": "production-trail10-official-daily-report-integration.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_date": args.date,
        "contract": base_contract(),
        "inputs": {"official_review_decision": official_decision},
        "integration_plan": [] if blocked else ["append trail10 shadow section to official daily report after human approval"],
        "decision": integration_decision,
        "blocked_reasons": blocked,
    }
    clawd = {
        "schema_version": "production-trail10-clawd-dry-run-preview.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_date": args.date,
        "contract": {**base_contract(), "clawd_live_send": False},
        "inputs": {"official_review_decision": official_decision, "integration_decision": integration_decision},
        "preview": None if blocked else "Trail10 daily report section ready for Clawd dry-run preview only.",
        "decision": clawd_decision,
        "blocked_reasons": blocked,
    }
    return {"official": official, "integration": integration, "clawd": clawd}


def main() -> int:
    args = parse_args()
    root = resolve_path(args.shadow_dir)
    if root is None:
        raise RuntimeError("shadow dir resolution failed")
    payloads = build_payloads(args)
    paths = {
        "official": root / f"production_trail10_official_daily_report_review_{args.date}.json",
        "integration": root / f"production_trail10_official_daily_report_integration_{args.date}.json",
        "clawd": root / f"production_trail10_clawd_dry_run_preview_{args.date}.json",
    }
    for key, payload in payloads.items():
        write_artifact(paths[key], payload)
    print(json.dumps({"status": "OK", "decision": payloads["official"]["decision"], "outputs": {key: repo_path(path) for key, path in paths.items()}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
