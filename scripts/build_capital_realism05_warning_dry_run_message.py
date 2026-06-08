#!/usr/bin/env python3
"""建立 calibrated warning-only dry-run 訊息，不發送推播。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "capital-realism05-warning-dry-run-message.v1"
RUN_DATE = "2026-06-05"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build calibrated warning-only dry-run message")
    parser.add_argument(
        "--watchlist-artifact",
        default=None,
        help="recent_top10_watchlist_warning_YYYY-MM-DD.json；未指定時使用最新 artifact",
    )
    parser.add_argument("--max-items", type=int, default=12)
    parser.add_argument(
        "--output",
        default=f"artifacts/model_experiments/capital_realism05_warning_dry_run_message_{RUN_DATE}.json",
    )
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def latest_watchlist_artifact() -> Path:
    matches = sorted((PROJECT_ROOT / "artifacts" / "model_experiments").glob("recent_top10_watchlist_warning_????-??-??.json"))
    if not matches:
        raise FileNotFoundError("找不到 recent_top10_watchlist_warning_YYYY-MM-DD.json")
    return matches[-1]


def warning_score(item: dict[str, Any]) -> tuple[int, int, str]:
    signals = set(item.get("signals") or [])
    score = 0
    if item.get("dropped_from_top10"):
        score += 3
    if "rank_worsened" in signals:
        score += 2
    if "close_below_ma20" in signals:
        score += 2
    if "close_below_ma10" in signals:
        score += 1
    if "close_below_ma5" in signals:
        score += 1
    if "long_upper_shadow" in signals:
        score += 1
    days_seen = int(item.get("days_seen_in_window") or 0)
    return (-score, -days_seen, str(item.get("stock_id")))


def signal_text(item: dict[str, Any]) -> str:
    signals = set(item.get("signals") or [])
    labels: list[str] = []
    if item.get("dropped_from_top10"):
        labels.append("最新已不在 Top10")
    if "rank_worsened" in signals:
        labels.append("排名後退")
    if "close_below_ma20" in signals:
        labels.append("跌到月線下方")
    elif "close_below_ma10" in signals:
        labels.append("跌破短線均線")
    elif "close_below_ma5" in signals:
        labels.append("跌破 5 日線")
    if "long_upper_shadow" in signals:
        labels.append("上攻後被壓回")
    return "、".join(labels[:3]) or "短線熱度降溫"


def item_line(item: dict[str, Any]) -> str:
    stock = f"{item.get('stock_id')} {item.get('stock_name') or ''}".strip()
    history = f"近 7 個 ranking 日入榜 {item.get('days_seen_in_window')} 天"
    if item.get("latest_rank") is None:
        rank_text = "榜外觀察"
    else:
        rank_text = f"最新排名第 {item.get('latest_rank')} 名"
    return f"- {stock}：{rank_text}，{history}；原因：{signal_text(item)}。"


def build_message(payload: dict[str, Any], selected: list[dict[str, Any]]) -> str:
    target_date = payload.get("target_date")
    lines = [
        f"⚠️ 近 7 日 Top10 觀察提醒｜{target_date}",
        "",
        "這不是交易指令，也不是個人持倉通知。",
        "意思是：最近曾被資金追過的股票，有些短線熱度開始降溫；未進場者先不要追，已持有者自己檢查成本和風險線。",
        "",
    ]
    if selected:
        lines.append("今天先看這些 WEAKENING 名單：")
        lines.extend(item_line(item) for item in selected)
    else:
        lines.append("今天沒有明顯 WEAKENING 名單。")
    lines.extend(
        [
            "",
            "白話：",
            "它們不是不能再漲，而是短線買盤沒有前幾天乾淨。",
            "Phase 1 先只提醒風險，不做個人化買賣建議。",
        ]
    )
    return "\n".join(lines)


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    source = resolve_path(args.watchlist_artifact) if args.watchlist_artifact else latest_watchlist_artifact()
    watchlist = json.loads(source.read_text(encoding="utf-8"))
    weakening_items = [item for item in watchlist.get("items", []) if item.get("warning_level") == "WEAKENING"]
    selected = sorted(weakening_items, key=warning_score)[: args.max_items]
    message = build_message(watchlist, selected)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK",
        "contract": {
            "research_only": True,
            "dry_run_only": True,
            "does_not_send_push": True,
            "changes_model": False,
            "changes_production_ranking": False,
            "changes_risk_adjusted_score": False,
            "non_personal_warning_only": True,
            "no_personal_holdings": True,
            "risk_alert_suppressed": True,
            "allowed_levels": ["WEAKENING"],
        },
        "inputs": {
            "watchlist_artifact": repo_path(source),
            "target_date": watchlist.get("target_date"),
            "max_items": args.max_items,
        },
        "summary": {
            "source_items": len(watchlist.get("items", [])),
            "weakening_items": len(weakening_items),
            "selected_items": len(selected),
            "message_chars": len(message),
        },
        "selected_items": selected,
        "message": message,
        "decision": {
            "status": "WARNING_DRY_RUN_MESSAGE_READY",
            "recommendation_channel": "NO_CHANGE",
            "warning_channel": "RESEARCH_ONLY_NOT_PUSH",
            "primary_read": "只輸出 WEAKENING dry-run；RISK_ALERT 已由 CAPITAL-REALISM-04 判定暫停。",
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# CAPITAL-REALISM-05 Warning Dry-run Message",
            "",
            f"- status: `{payload['status']}`",
            f"- decision: `{payload['decision']['status']}`",
            f"- selected_items: `{payload['summary']['selected_items']}`",
            f"- message_chars: `{payload['summary']['message_chars']}`",
            "",
            "## Message",
            "",
            "```text",
            payload["message"],
            "```",
            "",
            "## Contract",
            "",
            "```json",
            json.dumps(payload["contract"], ensure_ascii=False, indent=2),
            "```",
            "",
        ]
    )


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = resolve_path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "output": repo_path(output),
                "decision": payload["decision"]["status"],
                "selected_items": payload["summary"]["selected_items"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
