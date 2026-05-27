#!/usr/bin/env python3
"""透過本機 Clawd/OpenClaw CLI 發送每日 Top10 訊息。

預設只做 dry-run。正式送出必須同時設定 config 與 CLI 旗標，避免誤發。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATUS_SCHEMA_VERSION = "clawd-send-status.v1"


def main() -> int:
    parser = argparse.ArgumentParser(description="send or dry-run Clawd Top10 publish message")
    parser.add_argument("--date", default=None, help="訊息日期，格式 YYYY-MM-DD；未指定時使用最新 clawd_publish_message")
    parser.add_argument("--message", default=None, help="指定 message Markdown 路徑")
    parser.add_argument("--payload", default=None, help="指定 clawd_publish_payload JSON 路徑")
    parser.add_argument("--config", default="config/automation.yaml")
    parser.add_argument("--send", action="store_true", help="正式送出；仍需 notify.clawd_enabled=true 且 clawd_dry_run=false")
    parser.add_argument("--output", default=None, help="指定 send status JSON 路徑")
    args = parser.parse_args()

    config = load_config(PROJECT_ROOT / args.config)
    notify = config.get("notify", {})
    message_path = resolve_message_path(PROJECT_ROOT / "artifacts", args.date, args.message)
    message_date = date_from_message_path(message_path)
    payload_path = resolve_payload_path(PROJECT_ROOT / "artifacts", message_date, args.payload)
    payload = load_json(payload_path)
    output_path = Path(args.output) if args.output else PROJECT_ROOT / "artifacts" / f"clawd_send_status_{message_date}.json"
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path

    send_allowed = bool(args.send and notify.get("clawd_enabled") is True and notify.get("clawd_dry_run") is False)
    dry_run = not send_allowed
    node_bin = str(notify.get("clawd_cli_node") or "/opt/homebrew/opt/node/bin/node")
    cli_entry = str(notify.get("clawd_cli_entry") or "/Users/mattkuo/new clawd/dist/index.js")
    channel = str(notify.get("clawd_channel") or "")
    target = str(notify.get("clawd_to") or "")

    status = {
        "schema_version": STATUS_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "message_date": message_date,
        "message_path": str(message_path),
        "payload_path": str(payload_path),
        "payload_delivery_status": payload.get("delivery", {}).get("status"),
        "payload_top1": top_item_label(payload),
        "channel": channel,
        "target": target,
        "dry_run": dry_run,
        "send_attempted": send_allowed,
        "preflight": {
            "clawd_enabled": bool(notify.get("clawd_enabled")),
            "clawd_dry_run": bool(notify.get("clawd_dry_run", True)),
            "send_flag": bool(args.send),
            "node_bin": node_bin,
            "cli_entry": cli_entry,
        },
        "status": "RUNNING",
        "command": None,
        "exit_code": None,
        "stdout": "",
        "stderr": "",
        "errors": [],
    }

    try:
        validate_preflight(
            node_bin=node_bin,
            cli_entry=cli_entry,
            channel=channel,
            target=target,
            message_path=message_path,
            message_date=message_date,
            payload_path=payload_path,
            payload=payload,
        )
        command = [
            node_bin,
            cli_entry,
            "message",
            "send",
            "--channel",
            channel,
            "--target",
            target,
            "--message",
            message_path.read_text(encoding="utf-8"),
            "--json",
        ]
        if dry_run:
            command.append("--dry-run")
        status["command"] = mask_command(command)
        completed = subprocess.run(command, cwd=Path(cli_entry).resolve().parent.parent, text=True, capture_output=True)
        status["exit_code"] = completed.returncode
        status["stdout"] = redact_output(completed.stdout.strip())
        status["stderr"] = redact_output(completed.stderr.strip())
        status["status"] = "OK" if completed.returncode == 0 else "FAILED"
    except Exception as exc:
        status["status"] = "FAILED"
        status["errors"].append(str(exc))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"CLAWD_SEND_STATUS status={status['status']} dry_run={dry_run} output={output_path}")
    return 0 if status["status"] == "OK" else 1


def load_config(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_message_path(artifacts_dir: Path, date: str | None, message: str | None) -> Path:
    if message:
        path = Path(message)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        if path.exists():
            return path
        raise FileNotFoundError(f"指定 Clawd message 不存在：{path}")
    if date:
        path = artifacts_dir / f"clawd_publish_message_{date}.md"
        if path.exists():
            return path
        raise FileNotFoundError(f"指定日期 Clawd message 不存在：{path}")
    files = sorted(artifacts_dir.glob("clawd_publish_message_*.md"))
    if not files:
        raise FileNotFoundError("找不到 clawd_publish_message_*.md")
    return files[-1]


def resolve_payload_path(artifacts_dir: Path, message_date: str, payload: str | None) -> Path:
    if payload:
        path = Path(payload)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        if path.exists():
            return path
        raise FileNotFoundError(f"指定 Clawd payload 不存在：{path}")
    path = artifacts_dir / f"clawd_publish_payload_{message_date}.json"
    if path.exists():
        return path
    raise FileNotFoundError(f"找不到對應 Clawd payload：{path}")


def date_from_message_path(path: Path) -> str:
    match = re.search(r"clawd_publish_message_(\d{4}-\d{2}-\d{2})\.md$", path.name)
    if not match:
        raise ValueError(f"Clawd message 檔名無法解析日期：{path}")
    return match.group(1)


def validate_preflight(
    node_bin: str,
    cli_entry: str,
    channel: str,
    target: str,
    message_path: Path,
    message_date: str,
    payload_path: Path,
    payload: dict[str, Any],
) -> None:
    missing = []
    if not Path(node_bin).exists():
        missing.append(f"node_bin={node_bin}")
    if not Path(cli_entry).exists():
        missing.append(f"cli_entry={cli_entry}")
    if not channel:
        missing.append("notify.clawd_channel")
    if not target:
        missing.append("notify.clawd_to")
    if not message_path.exists():
        missing.append(f"message_path={message_path}")
    if missing:
        raise RuntimeError("Clawd send preflight failed: " + ", ".join(missing))
    delivery = payload.get("delivery", {})
    if delivery.get("status") != "READY_FOR_CLAWD":
        raise RuntimeError(f"Clawd payload is not ready: delivery.status={delivery.get('status')}")
    if payload.get("ranking_date") != message_date:
        raise RuntimeError(f"Clawd payload date mismatch: payload={payload.get('ranking_date')} message={message_date}")
    payload_message = payload.get("artifacts", {}).get("message")
    if not payload_message:
        raise RuntimeError("Clawd payload missing artifacts.message")
    if Path(payload_message).resolve() != message_path.resolve():
        raise RuntimeError(f"Clawd payload message mismatch: payload={payload_message} message={message_path}")
    if date_from_payload_path(payload_path) != message_date:
        raise RuntimeError(f"Clawd payload filename date mismatch: payload={payload_path.name} message={message_date}")
    if delivery.get("channel") != channel:
        raise RuntimeError(f"Clawd payload channel mismatch: payload={delivery.get('channel')} config={channel}")
    if delivery.get("to") != target:
        raise RuntimeError(f"Clawd payload target mismatch: payload={delivery.get('to')} config={target}")


def date_from_payload_path(path: Path) -> str:
    match = re.search(r"clawd_publish_payload_(\d{4}-\d{2}-\d{2})\.json$", path.name)
    if not match:
        raise ValueError(f"Clawd payload 檔名無法解析日期：{path}")
    return match.group(1)


def top_item_label(payload: dict[str, Any]) -> str | None:
    top10 = payload.get("top10")
    if not isinstance(top10, list) or not top10:
        return None
    first = top10[0]
    return f"{first.get('stock_id')} {first.get('stock_name')}".strip()


def mask_command(command: list[str]) -> list[str]:
    masked = list(command)
    if "--message" in masked:
        index = masked.index("--message")
        if index + 1 < len(masked):
            masked[index + 1] = f"<message chars={len(masked[index + 1])}>"
    return masked


def redact_output(text: str) -> str:
    if not text:
        return ""
    patterns = [
        (r"(?i)(token|webhook|password|secret|authorization)([\"'\s:=]+)([^\"'\s,}]+)", r"\1\2<redacted>"),
        (r"https://discord(?:app)?\.com/api/webhooks/[^\s\"']+", "https://discord.com/api/webhooks/<redacted>"),
    ]
    redacted = text
    for pattern, replacement in patterns:
        redacted = re.sub(pattern, replacement, redacted)
    return redacted


if __name__ == "__main__":
    raise SystemExit(main())
