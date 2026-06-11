#!/usr/bin/env python3
"""整合 production trail10 shadow review / preview 的 rollout readiness。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "production-trail10-rollout-readiness.v1"
ALLOWED_NEXT_STEPS = {
    "KEEP_SHADOW_ONLY",
    "ADD_TO_DAILY_REPORT_DRY_RUN",
    "ADD_TO_PAGE_EXPLANATION_DRY_RUN",
    "ADD_TO_CLAWD_DRY_RUN_PREVIEW",
    "BLOCKED_BY_SIGNAL_QUALITY",
    "BLOCKED_BY_COPY_RISK",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build production trail10 rollout readiness")
    parser.add_argument("--date", default=datetime.now().date().isoformat())
    parser.add_argument("--review", default=None)
    parser.add_argument("--preview", default=None)
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


def default_review(date_text: str) -> Path:
    return PROJECT_ROOT / "artifacts" / "shadow" / "production_trail10" / f"production_trail10_shadow_review_{date_text}.json"


def default_preview(date_text: str) -> Path:
    return PROJECT_ROOT / "artifacts" / "shadow" / "production_trail10" / f"production_trail10_publish_preview_{date_text}.json"


def choose_next_step(review_decision: str, preview_decision: str) -> tuple[str, list[str]]:
    blockers: list[str] = []
    if review_decision == "SHADOW_SIGNAL_BLOCKED":
        return "BLOCKED_BY_SIGNAL_QUALITY", ["shadow_signal_blocked"]
    if preview_decision == "PREVIEW_BLOCKED":
        return "BLOCKED_BY_SIGNAL_QUALITY", ["preview_blocked_by_shadow"]
    if preview_decision == "PREVIEW_NEEDS_COPY_FIX":
        return "BLOCKED_BY_COPY_RISK", ["preview_copy_risk"]
    if review_decision == "SHADOW_SIGNAL_MONITOR":
        return "KEEP_SHADOW_ONLY", ["shadow_signal_monitor"]
    return "ADD_TO_DAILY_REPORT_DRY_RUN", blockers


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    review_path = resolve_path(args.review) or default_review(args.date)
    preview_path = resolve_path(args.preview) or default_preview(args.date)
    if not review_path.exists():
        raise FileNotFoundError(f"找不到 review artifact：{review_path}")
    if not preview_path.exists():
        raise FileNotFoundError(f"找不到 preview artifact：{preview_path}")
    review = read_json(review_path)
    preview = read_json(preview_path)
    next_step, blockers = choose_next_step(str(review.get("decision")), str(preview.get("decision")))
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_date": args.date,
        "status": "OK",
        "contract": {
            "readiness_only": True,
            "live_send_approved": False,
            "changes_production_ranking": False,
            "changes_clawd_live_message": False,
            "changes_model": False,
            "dry_run_only": True,
        },
        "inputs": {
            "review": repo_path(review_path),
            "preview": repo_path(preview_path),
            "review_decision": review.get("decision"),
            "preview_decision": preview.get("decision"),
        },
        "next_step": next_step,
        "allowed_next_steps": sorted(ALLOWED_NEXT_STEPS),
        "decision": next_step,
        "blocked_reasons": blockers,
        "readiness_summary": {
            "signal_quality": review.get("decision"),
            "copy_quality": preview.get("decision"),
            "live_send": False,
            "recommended_surface": "daily_report_dry_run" if next_step == "ADD_TO_DAILY_REPORT_DRY_RUN" else "shadow_artifact_only",
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# Production Trail10 Rollout Readiness - {payload['run_date']}",
        "",
        f"- decision: `{payload['decision']}`",
        f"- live_send_approved: `{payload['contract']['live_send_approved']}`",
        f"- review: `{payload['inputs']['review_decision']}`",
        f"- preview: `{payload['inputs']['preview_decision']}`",
        "",
        "## Next",
        "",
        f"- {payload['next_step']}",
    ]
    if payload["blocked_reasons"]:
        lines.extend(["", "## Blockers", ""])
        lines.extend([f"- {item}" for item in payload["blocked_reasons"]])
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    output = resolve_path(args.output) or PROJECT_ROOT / "artifacts" / "shadow" / "production_trail10" / f"production_trail10_rollout_readiness_{args.date}.json"
    if output is None:
        raise RuntimeError("output resolution failed")
    payload = build_payload(args)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "decision": payload["decision"], "output": repo_path(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
