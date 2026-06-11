#!/usr/bin/env python3
"""產出 production trail10 daily report dry-run artifact。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "production-trail10-daily-report-dry-run.v1"
ALLOWED_DECISIONS = {
    "DAILY_REPORT_DRY_RUN_READY",
    "DAILY_REPORT_DRY_RUN_NEEDS_COPY_FIX",
    "DRY_RUN_BLOCKED_INPUT_MISSING",
    "DRY_RUN_BLOCKED_SIGNAL_QUALITY",
}
FORBIDDEN_PHRASES = (
    "你應該賣出",
    "賣出幾成",
    "正式停損通知",
    "系統判定你要出場",
    "立刻出場",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build production trail10 daily report dry-run")
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


def input_paths(shadow_dir: Path, run_date: str) -> dict[str, Path]:
    return {
        "shadow": shadow_dir / f"production_trail10_shadow_{run_date}.json",
        "review": shadow_dir / f"production_trail10_shadow_review_{run_date}.json",
        "preview": shadow_dir / f"production_trail10_publish_preview_{run_date}.json",
        "readiness": shadow_dir / f"production_trail10_rollout_readiness_{run_date}.json",
    }


def stock_name(row: dict[str, Any]) -> str:
    return f"{row.get('stock_id')} {row.get('stock_name') or ''}".strip()


def compact_items(rows: list[dict[str, Any]], status: str) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        if row.get("status") != status:
            continue
        result.append(
            {
                "stock_id": row.get("stock_id"),
                "stock_name": row.get("stock_name"),
                "status": row.get("status"),
                "latest_close": row.get("latest_close"),
                "trail_threshold": row.get("trail_threshold"),
                "reason": row.get("status_reason"),
            }
        )
    return result


def build_sections(shadow: dict[str, Any], preview: dict[str, Any]) -> list[dict[str, Any]]:
    positions = shadow.get("shadow_positions") if isinstance(shadow.get("shadow_positions"), list) else []
    zone = compact_items(positions, "trail_stop_zone")
    triggered = compact_items(positions, "exit_triggered")
    formal_body = "正式 Top10 仍照 production ranking；本 dry-run 不改排名、不改正式日報。"
    if zone:
        zone_names = "、".join(stock_name(row) for row in zone[:8])
        zone_body = f"接近轉弱區：{zone_names}。還沒進場的人不要追；如果本來就有持有，請自行檢查。"
    else:
        zone_body = "目前沒有接近轉弱區的觀察股。"
    if triggered:
        triggered_names = "、".join(stock_name(row) for row in triggered[:8])
        triggered_body = f"近期走勢變弱：{triggered_names}。這是 trail10 shadow 觀察，不是個人持倉通知。"
    else:
        triggered_body = "目前沒有碰到 trail10 轉弱線的觀察股。"
    preview_body = ((preview.get("message_preview") or {}).get("trail10_observation_section") or {}).get("body")
    return [
        {
            "section_id": "official_top10_unchanged",
            "title": "正式 Top10 仍照 production ranking",
            "body": formal_body,
            "items": shadow.get("production_top10") or [],
        },
        {
            "section_id": "trail10_weakening_watch",
            "title": "近期觀察股轉弱提醒",
            "body": "\n".join([zone_body, triggered_body]),
            "trail_stop_zone": zone,
            "exit_triggered": triggered,
            "source_preview_body": preview_body,
        },
        {
            "section_id": "usage_boundary",
            "title": "使用邊界",
            "body": "這是 trail10 shadow daily report dry-run，不是正式持倉通知；未進場者不要追，已持有者自行檢查持倉。",
        },
    ]


def copy_guard(sections: list[dict[str, Any]]) -> dict[str, Any]:
    text = json.dumps(sections, ensure_ascii=False)
    found = [phrase for phrase in FORBIDDEN_PHRASES if phrase in text]
    return {
        "forbidden_phrases": list(FORBIDDEN_PHRASES),
        "found_forbidden_phrases": found,
        "personalized_sell_instruction": False,
        "plain_language": True,
    }


def blocked_payload(args: argparse.Namespace, paths: dict[str, Path], missing: dict[str, str]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_date": args.date,
        "status": "OK",
        "contract": contract(),
        "inputs": {key: repo_path(path) for key, path in paths.items()},
        "input_gaps": missing,
        "report_sections": [],
        "copy_guard": copy_guard([]),
        "trail10_summary": {},
        "blocked_reasons": ["missing_required_input_artifact"],
        "decision": "DRY_RUN_BLOCKED_INPUT_MISSING",
        "next_recommended_action": "REBUILD_MISSING_TRAIL10_SHADOW_INPUTS_BEFORE_DAILY_REPORT_DRY_RUN",
    }


def contract() -> dict[str, Any]:
    return {
        "dry_run_only": True,
        "changes_official_daily_report": False,
        "changes_clawd_payload": False,
        "changes_clawd_live_message": False,
        "changes_production_ranking": False,
        "changes_model": False,
        "personalized_sell_instruction": False,
        "uses_stale_fallback": False,
        "live_send": False,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    shadow_dir = resolve_path(args.shadow_dir)
    if shadow_dir is None:
        raise RuntimeError("shadow dir resolution failed")
    paths = input_paths(shadow_dir, args.date)
    missing = {key: repo_path(path) or str(path) for key, path in paths.items() if not path.exists()}
    if missing:
        return blocked_payload(args, paths, missing)
    shadow = read_json(paths["shadow"])
    review = read_json(paths["review"])
    preview = read_json(paths["preview"])
    readiness = read_json(paths["readiness"])
    sections = build_sections(shadow, preview)
    guard = copy_guard(sections)
    blocked_reasons: list[str] = []
    if review.get("decision") == "SHADOW_SIGNAL_BLOCKED" or readiness.get("decision") == "BLOCKED_BY_SIGNAL_QUALITY":
        blocked_reasons.append("shadow_signal_quality_blocked")
        decision = "DRY_RUN_BLOCKED_SIGNAL_QUALITY"
    elif guard["found_forbidden_phrases"]:
        blocked_reasons.append("copy_guard_forbidden_phrase")
        decision = "DAILY_REPORT_DRY_RUN_NEEDS_COPY_FIX"
    else:
        decision = "DAILY_REPORT_DRY_RUN_READY"
    positions = shadow.get("shadow_positions") if isinstance(shadow.get("shadow_positions"), list) else []
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_date": args.date,
        "status": "OK",
        "contract": contract(),
        "inputs": {
            "shadow": repo_path(paths["shadow"]),
            "review": repo_path(paths["review"]),
            "preview": repo_path(paths["preview"]),
            "readiness": repo_path(paths["readiness"]),
            "review_decision": review.get("decision"),
            "preview_decision": preview.get("decision"),
            "readiness_decision": readiness.get("decision"),
        },
        "input_gaps": {},
        "report_sections": sections,
        "copy_guard": guard,
        "trail10_summary": {
            "status_counts": (shadow.get("summary") or {}).get("status_counts", {}),
            "trail_stop_zone": compact_items(positions, "trail_stop_zone"),
            "exit_triggered": compact_items(positions, "exit_triggered"),
            "warning_candidate_count": (shadow.get("summary") or {}).get("warning_candidate_count"),
        },
        "blocked_reasons": blocked_reasons,
        "decision": decision,
        "next_recommended_action": "ADD_TO_DAILY_REPORT_DRY_RUN_REVIEW_LOOP",
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# Production Trail10 Daily Report Dry-Run - {payload['run_date']}",
        "",
        f"- decision: `{payload['decision']}`",
        f"- live_send: `{payload['contract']['live_send']}`",
        f"- changes_official_daily_report: `{payload['contract']['changes_official_daily_report']}`",
        "",
    ]
    if payload.get("input_gaps"):
        lines.extend(["## Missing Inputs", ""])
        lines.extend([f"- {key}: {path}" for key, path in payload["input_gaps"].items()])
        return "\n".join(lines) + "\n"
    for section in payload["report_sections"]:
        lines.extend([f"## {section['title']}", "", section["body"], ""])
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    output = resolve_path(args.output) or PROJECT_ROOT / "artifacts" / "shadow" / "production_trail10" / f"production_trail10_daily_report_dry_run_{args.date}.json"
    if output is None:
        raise RuntimeError("output resolution failed")
    payload = build_payload(args)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    latest = output.parent / "production_trail10_daily_report_dry_run_latest.json"
    latest.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "decision": payload["decision"], "output": repo_path(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
