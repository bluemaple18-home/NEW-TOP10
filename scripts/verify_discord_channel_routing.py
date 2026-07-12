#!/usr/bin/env python3
"""驗證 TOP10 Discord 頻道路由不混線。

只檢查本 repo 的設定與 OpenClaw Discord allowlist，不輸出 token、不送 Discord、不碰其他專案。
"""

from __future__ import annotations

import os
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "top10-discord-channel-routing-verification.v1"
REVIEW_APPROVAL_CHANNEL_ID = "1523986945955463188"


def read_text(rel: str) -> str:
    return (PROJECT_ROOT / rel).read_text(encoding="utf-8")


def channel_id_from_target(target: Any) -> str:
    text = str(target or "").strip()
    return text.split("channel:", 1)[1] if text.startswith("channel:") else text


def display_path(path: Path) -> str:
    home = Path.home()
    try:
        return "~/" + str(path.resolve().relative_to(home))
    except ValueError:
        return str(path)


def openclaw_discord_channel_status(channel_id: str) -> dict[str, Any]:
    config_path = Path(os.environ.get("OPENCLAW_CONFIG_PATH", "~/.openclaw/openclaw.json")).expanduser()
    if not config_path.exists():
        return {
            "ok": False,
            "value": {"config": display_path(config_path), "reason": "openclaw_config_missing"},
        }

    config = json.loads(config_path.read_text(encoding="utf-8"))
    discord = ((config.get("channels") or {}).get("discord") or {})
    guilds = discord.get("guilds") if isinstance(discord.get("guilds"), dict) else {}
    matched: list[dict[str, Any]] = []
    for guild_id, guild in guilds.items():
        if not isinstance(guild, dict):
            continue
        channels = guild.get("channels") if isinstance(guild.get("channels"), dict) else {}
        entry = channels.get(channel_id)
        if isinstance(entry, dict):
            matched.append(
                {
                    "guild": guild_id,
                    "requireMention": entry.get("requireMention"),
                    "users": entry.get("users"),
                }
            )

    ok = any(
        entry.get("requireMention") is False
        and isinstance(entry.get("users"), list)
        and "*" in entry.get("users", [])
        for entry in matched
    )
    return {
        "ok": ok,
        "value": {
            "config": display_path(config_path),
            "channel_id": channel_id,
            "matched": matched,
        },
    }


def main() -> int:
    config = yaml.safe_load((PROJECT_ROOT / "config" / "automation.yaml").read_text(encoding="utf-8")) or {}
    notify = config.get("notify") if isinstance(config.get("notify"), dict) else {}
    review_channel_id = channel_id_from_target(notify.get("review_approval_clawd_to"))
    review_approval_openclaw_status = openclaw_discord_channel_status(review_channel_id)
    checks = [
        {
            "name": "stock_watchlist_target_configured",
            "ok": notify.get("clawd_to") == "channel:1507327845003825154",
            "value": notify.get("clawd_to"),
        },
        {
            "name": "task_report_target_configured",
            "ok": notify.get("ops_clawd_to") == "channel:1519179377336651796",
            "value": notify.get("ops_clawd_to"),
        },
        {
            "name": "review_approval_target_configured",
            "ok": notify.get("review_approval_clawd_to") == f"channel:{REVIEW_APPROVAL_CHANNEL_ID}",
            "value": notify.get("review_approval_clawd_to"),
        },
        {
            "name": "review_approval_openclaw_component_allowlist",
            "ok": review_approval_openclaw_status["ok"],
            "value": review_approval_openclaw_status["value"],
        },
        {
            "name": "ops_report_uses_task_report_target",
            "ok": 'notify.get("ops_clawd_to")' in read_text("scripts/send_top10_ops_report.py")
            and "review_approval_clawd_to" not in read_text("scripts/send_top10_ops_report.py"),
            "value": "scripts/send_top10_ops_report.py",
        },
        {
            "name": "pm_review_cards_prefer_review_approval_target",
            "ok": "review_approval_clawd_to" in read_text("scripts/run_pm_research_harness_loop.py")
            and "top10.pm_review.send_cards" in read_text("scripts/run_pm_research_harness_loop.py"),
            "value": "scripts/run_pm_research_harness_loop.py",
        },
        {
            "name": "pm_review_cards_disclose_button_ttl_and_fallback",
            "ok": "DEFAULT_COMPONENT_TTL_DAYS = 7" in read_text("integrations/openclaw-top10-pm-review/core.js")
            and "componentTtlMs: DEFAULT_COMPONENT_TTL_MS" in read_text("integrations/openclaw-top10-pm-review/index.js")
            and "Codex 重送此卡" in read_text("integrations/openclaw-top10-pm-review/core.js")
            and "/top10pm approve" not in read_text("integrations/openclaw-top10-pm-review/core.js"),
            "value": "integrations/openclaw-top10-pm-review/core.js",
        },
        {
            "name": "task_report_does_not_expand_approval_cards",
            "ok": "approve/reject 卡不在本頻道展開" in read_text("scripts/build_top10_ops_progress_message.py")
            and "render_pm_card_rows(card)" not in read_text("scripts/build_top10_ops_progress_message.py"),
            "value": "scripts/build_top10_ops_progress_message.py",
        },
        {
            "name": "daily_publish_runs_separate_ops_report",
            "ok": "send_top10_ops_report.py" in read_text("scripts/run_daily_publish.sh")
            and "send_clawd_publish_message.py" in read_text("scripts/run_daily_publish.sh"),
            "value": "scripts/run_daily_publish.sh",
        },
    ]
    failed = [check for check in checks if not check["ok"]]
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK" if not failed else "FAILED",
        "scope": "TOP10new repo only",
        "routes": {
            "stock_watchlist": notify.get("clawd_to"),
            "task_report": notify.get("ops_clawd_to"),
            "review_approval": notify.get("review_approval_clawd_to"),
        },
        "checks": checks,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
