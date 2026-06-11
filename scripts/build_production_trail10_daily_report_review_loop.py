#!/usr/bin/env python3
"""彙整 trail10 daily report dry-run 的連續 review loop。"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "production-trail10-daily-report-review-loop.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build production trail10 daily report review loop")
    parser.add_argument("--date", default=datetime.now().date().isoformat())
    parser.add_argument("--shadow-dir", default="artifacts/shadow/production_trail10")
    parser.add_argument("--output", default=None)
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


def dry_run_date(path: Path) -> str | None:
    match = re.fullmatch(r"production_trail10_daily_report_dry_run_(\d{4}-\d{2}-\d{2})\.json", path.name)
    return match.group(1) if match else None


def dry_run_files(root: Path, run_date: str) -> list[Path]:
    rows = []
    for path in root.glob("production_trail10_daily_report_dry_run_????-??-??.json"):
        date_text = dry_run_date(path)
        if date_text and date_text <= run_date:
            rows.append(path)
    return sorted(rows, key=lambda item: dry_run_date(item) or "")


def inspect_day(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    guard = payload.get("copy_guard") if isinstance(payload.get("copy_guard"), dict) else {}
    summary = payload.get("trail10_summary") if isinstance(payload.get("trail10_summary"), dict) else {}
    gaps = payload.get("input_gaps") if isinstance(payload.get("input_gaps"), dict) else {}
    date_text = str(payload.get("run_date") or dry_run_date(path))
    issues = []
    if gaps:
        issues.append("input_gaps")
    if guard.get("found_forbidden_phrases"):
        issues.append("copy_guard_forbidden_phrase")
    if guard.get("personalized_sell_instruction") is not False:
        issues.append("personalized_sell_instruction")
    for key in ["changes_official_daily_report", "changes_clawd_payload", "changes_clawd_live_message", "uses_stale_fallback", "live_send"]:
        if contract.get(key) is not False:
            issues.append(key)
    if contract.get("dry_run_only") is not True:
        issues.append("not_dry_run_only")
    unclear = []
    for key in ["trail_stop_zone", "exit_triggered"]:
        for row in summary.get(key, []) or []:
            if not row.get("reason") or row.get("trail_threshold") is None:
                unclear.append({"stock_id": row.get("stock_id"), "status": key})
    if unclear:
        issues.append("unclear_trail10_basis")
    return {
        "date": date_text,
        "artifact": repo_path(path),
        "decision": payload.get("decision"),
        "copy_guard_ok": not guard.get("found_forbidden_phrases") and guard.get("personalized_sell_instruction") is False,
        "signal_basis_ok": not unclear,
        "contract_safe": not any(issue in issues for issue in ["changes_official_daily_report", "changes_clawd_payload", "changes_clawd_live_message", "uses_stale_fallback", "live_send"]),
        "trail10_status_counts": summary.get("status_counts", {}),
        "issues": issues,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    root = resolve_path(args.shadow_dir)
    if root is None or not root.exists():
        raise FileNotFoundError(f"找不到 shadow dir：{args.shadow_dir}")
    files = dry_run_files(root, args.date)
    latest = files[-20:]
    preferred = files[-5:]
    useful = files[-3:]
    results = [inspect_day(path) for path in latest]
    issue_days = [row for row in results if row["issues"]]
    useful_results = [inspect_day(path) for path in useful]
    if not results:
        decision = "BLOCKED_BY_INPUT_GAPS"
        blockers = ["no_dry_run_artifacts"]
    elif issue_days:
        issue_set = {issue for row in issue_days for issue in row["issues"]}
        if "copy_guard_forbidden_phrase" in issue_set or "personalized_sell_instruction" in issue_set:
            decision = "BLOCKED_BY_COPY_RISK"
        elif "unclear_trail10_basis" in issue_set:
            decision = "BLOCKED_BY_SIGNAL_QUALITY"
        else:
            decision = "BLOCKED_BY_INPUT_GAPS"
        blockers = sorted(issue_set)
    elif len(useful_results) < 3:
        decision = "CONTINUE_DRY_RUN_REVIEW_LOOP"
        blockers = ["insufficient_review_days"]
    else:
        decision = "READY_FOR_OFFICIAL_DAILY_REPORT_REVIEW"
        blockers = []
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_date": args.date,
        "contract": {
            "review_loop_only": True,
            "changes_official_daily_report": False,
            "changes_clawd_payload": False,
            "changes_clawd_live_message": False,
            "live_send_approved": False,
            "uses_stale_fallback": False,
        },
        "input_artifacts": [repo_path(path) for path in latest],
        "review_window": {
            "minimum_useful_days": 3,
            "preferred_days": 5,
            "extended_days": 20,
            "available_days": len(results),
            "useful_window_days": len(useful_results),
            "preferred_window_days": len(preferred),
        },
        "daily_results": results,
        "signal_quality_summary": {"issue_days": len([row for row in results if "unclear_trail10_basis" in row["issues"]])},
        "copy_quality_summary": {"issue_days": len([row for row in results if "copy_guard_forbidden_phrase" in row["issues"] or "personalized_sell_instruction" in row["issues"]])},
        "user_visible_risk_summary": {"official_surface_changed": False, "clawd_changed": False, "live_send": False},
        "decision": decision,
        "blocked_reasons": blockers,
        "next_recommended_action": "CONTINUE_DRY_RUN_REVIEW_LOOP_UNTIL_3_OK_DAYS" if decision == "CONTINUE_DRY_RUN_REVIEW_LOOP" else "OFFICIAL_DAILY_REPORT_REVIEW_GATE",
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# Production Trail10 Daily Report Review Loop - {payload['run_date']}",
        "",
        f"- decision: `{payload['decision']}`",
        f"- available_days: `{payload['review_window']['available_days']}`",
        f"- useful_window_days: `{payload['review_window']['useful_window_days']}`",
        "",
        "## Days",
        "",
    ]
    for row in payload["daily_results"]:
        lines.append(f"- `{row['date']}` decision=`{row['decision']}` issues=`{row['issues']}`")
    if payload["blocked_reasons"]:
        lines.extend(["", "## Blockers", ""])
        lines.extend([f"- {item}" for item in payload["blocked_reasons"]])
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    output = resolve_path(args.output) or PROJECT_ROOT / "artifacts" / "shadow" / "production_trail10" / f"production_trail10_daily_report_review_loop_{args.date}.json"
    if output is None:
        raise RuntimeError("output resolution failed")
    payload = build_payload(args)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    latest = output.parent / "production_trail10_daily_report_review_loop_latest.json"
    latest.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": "OK", "decision": payload["decision"], "output": repo_path(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
