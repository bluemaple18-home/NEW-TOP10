#!/usr/bin/env python3
"""產出 production trail10 的不發送推播 preview。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "production-trail10-publish-preview.v1"
FORBIDDEN_PHRASES = ("你應該賣出", "賣幾成", "停損價已到，立刻出場", "正式持倉通知")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build production trail10 publish preview")
    parser.add_argument("--date", default=datetime.now().date().isoformat())
    parser.add_argument("--shadow", default=None)
    parser.add_argument("--review", default=None)
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


def default_shadow(date_text: str) -> Path:
    return PROJECT_ROOT / "artifacts" / "shadow" / "production_trail10" / f"production_trail10_shadow_{date_text}.json"


def default_review(date_text: str) -> Path:
    return PROJECT_ROOT / "artifacts" / "shadow" / "production_trail10" / f"production_trail10_shadow_review_{date_text}.json"


def format_stock(row: dict[str, Any]) -> str:
    return f"{row.get('stock_id')} {row.get('stock_name') or ''}".strip()


def build_message(shadow: dict[str, Any]) -> dict[str, Any]:
    top10 = shadow.get("production_top10") if isinstance(shadow.get("production_top10"), list) else []
    positions = shadow.get("shadow_positions") if isinstance(shadow.get("shadow_positions"), list) else []
    zone = [row for row in positions if row.get("status") == "trail_stop_zone"]
    triggered = [row for row in positions if row.get("status") == "exit_triggered"]
    hold = [row for row in positions if row.get("status") == "hold"]
    lines = [
        "今日正式 Top10 仍照 production ranking，trail10 僅為後台觀察。",
        "近期觀察股 trail10 狀態：",
    ]
    if zone:
        names = "、".join(format_stock(row) for row in zone[:8])
        lines.append(f"接近 trail10 轉弱區：{names}。未進場者不要追；若已持有，請自行檢查。")
    if triggered:
        names = "、".join(format_stock(row) for row in triggered[:8])
        lines.append(f"已碰到 trail10 轉弱線：{names}。這是非個人化觀察，不是正式持倉訊息。")
    if not zone and not triggered:
        lines.append("今日沒有接近或碰到 trail10 轉弱線的觀察股。")
    return {
        "formal_top10_section": {
            "title": "今日正式 Top10",
            "source": "production_ranking",
            "items": top10,
            "body": "今日正式 Top10 仍照 production ranking；trail10 shadow 不改排序。",
        },
        "trail10_observation_section": {
            "title": "Trail10 後台觀察",
            "hold_count": len(hold),
            "trail_stop_zone": [{"stock_id": row.get("stock_id"), "stock_name": row.get("stock_name"), "trail_threshold": row.get("trail_threshold"), "latest_close": row.get("latest_close")} for row in zone],
            "exit_triggered": [{"stock_id": row.get("stock_id"), "stock_name": row.get("stock_name"), "trail_threshold": row.get("trail_threshold"), "latest_close": row.get("latest_close")} for row in triggered],
            "body": "\n".join(lines),
        },
    }


def has_forbidden_copy(text: str) -> bool:
    return any(phrase in text for phrase in FORBIDDEN_PHRASES)


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    shadow_path = resolve_path(args.shadow) or default_shadow(args.date)
    review_path = resolve_path(args.review) or default_review(args.date)
    if not shadow_path.exists():
        raise FileNotFoundError(f"找不到 shadow artifact：{shadow_path}")
    if not review_path.exists():
        raise FileNotFoundError(f"找不到 review artifact：{review_path}")
    shadow = read_json(shadow_path)
    review = read_json(review_path)
    message = build_message(shadow)
    body_text = json.dumps(message, ensure_ascii=False)
    if review.get("decision") == "SHADOW_SIGNAL_BLOCKED":
        decision = "PREVIEW_BLOCKED"
    elif has_forbidden_copy(body_text):
        decision = "PREVIEW_NEEDS_COPY_FIX"
    else:
        decision = "PREVIEW_READY_FOR_REVIEW"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_date": args.date,
        "status": "OK",
        "contract": {
            "preview_only": True,
            "live_send": False,
            "changes_production_ranking": False,
            "changes_clawd_live_message": False,
            "changes_model": False,
            "personalized_sell_instruction": False,
            "non_personal_observation_only": True,
        },
        "inputs": {
            "shadow": repo_path(shadow_path),
            "review": repo_path(review_path),
            "review_decision": review.get("decision"),
        },
        "message_preview": message,
        "forbidden_phrases": list(FORBIDDEN_PHRASES),
        "copy_risk_found": has_forbidden_copy(body_text),
        "decision": decision,
        "blocked_reasons": [] if decision != "PREVIEW_BLOCKED" else ["shadow_signal_blocked"],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    section = payload["message_preview"]["trail10_observation_section"]
    lines = [
        f"# Production Trail10 Publish Preview - {payload['run_date']}",
        "",
        f"- decision: `{payload['decision']}`",
        f"- live_send: `{payload['contract']['live_send']}`",
        "",
        "## Preview Body",
        "",
        payload["message_preview"]["formal_top10_section"]["body"],
        "",
        section["body"],
        "",
        "## Boundary",
        "",
        "- 這是 dry-run preview，不發送、不改正式推播。",
        "- 文案是非個人化觀察，不是個人持倉操作指令。",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    output = resolve_path(args.output) or PROJECT_ROOT / "artifacts" / "shadow" / "production_trail10" / f"production_trail10_publish_preview_{args.date}.json"
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
