#!/usr/bin/env python3
"""驗證收盤後 Clawd live send 營運設定。

這個 verifier 只檢查設定與入口，不發送訊息、不重跑 daily。
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "clawd-live-send-config-verification.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify Clawd live send config")
    parser.add_argument("--output", default="artifacts/clawd_live_send_config_verification_latest.json")
    return parser.parse_args()


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def read_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_installed_plist() -> tuple[Path, str | None]:
    path = Path.home() / "Library" / "LaunchAgents" / "com.new-top10.daily.plist"
    if not path.exists():
        return path, None
    return path, path.read_text(encoding="utf-8")


def build_payload() -> dict[str, Any]:
    config_path = PROJECT_ROOT / "config" / "automation.yaml"
    repo_plist_path = PROJECT_ROOT / "scripts" / "com.new-top10.daily.plist"
    publish_path = PROJECT_ROOT / "scripts" / "run_daily_publish.sh"
    send_script_path = PROJECT_ROOT / "scripts" / "send_clawd_publish_message.py"

    config = read_yaml(config_path)
    notify = config.get("notify") if isinstance(config.get("notify"), dict) else {}
    repo_plist = repo_plist_path.read_text(encoding="utf-8") if repo_plist_path.exists() else ""
    publish_script = publish_path.read_text(encoding="utf-8") if publish_path.exists() else ""
    installed_plist_path, installed_plist = load_installed_plist()

    checks = [
        {
            "name": "notify_clawd_enabled_true",
            "ok": notify.get("clawd_enabled") is True,
            "value": notify.get("clawd_enabled"),
        },
        {
            "name": "notify_clawd_dry_run_false",
            "ok": notify.get("clawd_dry_run") is False,
            "value": notify.get("clawd_dry_run"),
        },
        {
            "name": "notify_channel_target",
            "ok": notify.get("clawd_channel") == "discord"
            and isinstance(notify.get("clawd_to"), str)
            and notify.get("clawd_to", "").startswith("channel:"),
            "value": {"channel": notify.get("clawd_channel"), "to": notify.get("clawd_to")},
        },
        {
            "name": "clawd_cli_paths_exist",
            "ok": Path(str(notify.get("clawd_cli_node", ""))).exists()
            and Path(str(notify.get("clawd_cli_entry", ""))).exists(),
            "value": {
                "node": notify.get("clawd_cli_node"),
                "entry": notify.get("clawd_cli_entry"),
            },
        },
        {
            "name": "repo_daily_plist_uses_publish_entry",
            "ok": "scripts/run_daily_publish.sh" in repo_plist,
            "value": repo_path(repo_plist_path),
        },
        {
            "name": "installed_daily_plist_uses_publish_entry",
            "ok": installed_plist is not None and "scripts/run_daily_publish.sh" in installed_plist,
            "value": str(installed_plist_path),
        },
        {
            "name": "publish_script_requires_current_ok_run",
            "ok": "daily run_date mismatch" in publish_script
            and "metadata.clawd_publish_message" in publish_script
            and "notify.clawd_enabled is not true" in publish_script
            and "notify.clawd_dry_run is not false" in publish_script,
            "value": repo_path(publish_path),
        },
        {
            "name": "publish_script_uses_send_clawd_publish_message",
            "ok": "send_clawd_publish_message.py" in publish_script and "--send" in publish_script,
            "value": repo_path(send_script_path),
        },
    ]

    failed = [check for check in checks if not check["ok"]]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK" if not failed else "FAILED",
        "summary": {
            "check_count": len(checks),
            "failed_count": len(failed),
            "live_send_config_ready": not failed,
        },
        "checks": checks,
    }


def main() -> int:
    args = parse_args()
    payload = build_payload()
    output = Path(args.output)
    if not output.is_absolute():
        output = PROJECT_ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output)}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
