#!/usr/bin/env python3
"""發送 TOP10 工作進度訊息到 ops Discord 頻道。"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

try:
    from build_top10_agent_status_rollup import build_rollup
    from build_top10_ops_progress_message import resolve_rollup_path, safe_ref
    from top10_agent_status import DEFAULT_MANIFEST_PATH, build_event, read_manifest, write_agent_event
except ModuleNotFoundError:
    from scripts.build_top10_agent_status_rollup import build_rollup
    from scripts.build_top10_ops_progress_message import resolve_rollup_path, safe_ref
    from scripts.top10_agent_status import DEFAULT_MANIFEST_PATH, build_event, read_manifest, write_agent_event


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
STATUS_SCHEMA_VERSION = "top10-ops-report-send-status.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="send TOP10 ops progress report")
    parser.add_argument("--run-date", default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--artifacts-dir", default=ARTIFACTS_DIR, type=Path)
    parser.add_argument("--config", default=Path("config/automation.yaml"), type=Path)
    parser.add_argument("--message", default=None, type=Path)
    parser.add_argument("--send", action="store_true", help="正式送出；仍需 notify.ops_clawd_enabled=true 且 ops_clawd_dry_run=false")
    parser.add_argument("--allow-stale-send", action="store_true", help="允許補送非今日 ops 訊息")
    parser.add_argument("--output", default=None, type=Path)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST_PATH, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifacts_dir = resolve_path(args.artifacts_dir)
    config_path = resolve_path(args.config)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    notify = config.get("notify") if isinstance(config.get("notify"), dict) else {}
    rollup_path = resolve_rollup_path(artifacts_dir, args.run_date, args.run_id)
    if rollup_path is None:
        raise SystemExit("missing TOP10 harness rollup; cannot send ops report")
    rollup = read_json(rollup_path)
    run_date = str(rollup.get("run_date") or args.run_date or datetime.now().date().isoformat())
    run_id = str(rollup.get("run_id") or args.run_id or f"daily-{run_date}")
    message_path = resolve_message(args.message, artifacts_dir, run_date)
    build_research_decision_brief(run_date=run_date, artifacts_dir=artifacts_dir)
    if args.message is None or not message_path.exists():
        run_checked(
            [
                python_bin(),
                "scripts/build_top10_ops_progress_message.py",
                "--run-date",
                run_date,
                "--run-id",
                run_id,
                "--artifacts-dir",
                str(artifacts_dir),
            ]
        )
    message_path = resolve_message(args.message, artifacts_dir, run_date)
    output_path = resolve_path(args.output) if args.output else artifacts_dir / f"ops_progress_send_status_{run_date}.json"

    send_allowed = bool(args.send and notify.get("ops_clawd_enabled") is True and notify.get("ops_clawd_dry_run") is False)
    dry_run = not send_allowed
    node_bin = str(notify.get("clawd_cli_node") or "/opt/homebrew/opt/node/bin/node")
    cli_entry = str(notify.get("clawd_cli_entry") or "/Users/mattkuo/new clawd/dist/index.js")
    channel = str(notify.get("ops_clawd_channel") or notify.get("clawd_channel") or "")
    target = str(notify.get("ops_clawd_to") or "")
    status = initial_status(
        run_date=run_date,
        run_id=run_id,
        artifacts_dir=artifacts_dir,
        message_path=message_path,
        rollup_path=rollup_path,
        output_path=output_path,
        channel=channel,
        target=target,
        dry_run=dry_run,
        send_allowed=send_allowed,
        notify=notify,
        node_bin=node_bin,
        cli_entry=cli_entry,
    )

    try:
        validate_preflight(
            node_bin=node_bin,
            cli_entry=cli_entry,
            channel=channel,
            target=target,
            message_path=message_path,
            run_date=run_date,
            send_allowed=send_allowed,
            allow_stale_send=args.allow_stale_send,
            timezone_name=str(config.get("timezone") or "Asia/Taipei"),
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
    output_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_ops_event(status, artifacts_dir=artifacts_dir, manifest_path=resolve_path(args.manifest))
    print(f"TOP10_OPS_REPORT_SEND status={status['status']} dry_run={dry_run} output={output_path}")
    return 0 if status["status"] == "OK" else 1


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return payload


def resolve_message(path: Path | None, artifacts_dir: Path, run_date: str) -> Path:
    if path is not None:
        return resolve_path(path)
    return artifacts_dir / f"ops_progress_message_{run_date}.md"


def initial_status(
    *,
    run_date: str,
    run_id: str,
    artifacts_dir: Path,
    message_path: Path,
    rollup_path: Path,
    output_path: Path,
    channel: str,
    target: str,
    dry_run: bool,
    send_allowed: bool,
    notify: dict[str, Any],
    node_bin: str,
    cli_entry: str,
) -> dict[str, Any]:
    return {
        "schema_version": STATUS_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_date": run_date,
        "run_id": run_id,
        "message_path": safe_ref(message_path, artifacts_dir),
        "rollup_path": safe_ref(rollup_path, artifacts_dir),
        "output_path": safe_ref(output_path, artifacts_dir),
        "channel": channel,
        "target": target,
        "dry_run": dry_run,
        "send_attempted": send_allowed,
        "preflight": {
            "ops_clawd_enabled": bool(notify.get("ops_clawd_enabled")),
            "ops_clawd_dry_run": bool(notify.get("ops_clawd_dry_run", True)),
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


def validate_preflight(
    *,
    node_bin: str,
    cli_entry: str,
    channel: str,
    target: str,
    message_path: Path,
    run_date: str,
    send_allowed: bool,
    allow_stale_send: bool,
    timezone_name: str,
) -> None:
    missing = []
    if not Path(node_bin).exists():
        missing.append(f"node_bin={node_bin}")
    if not Path(cli_entry).exists():
        missing.append(f"cli_entry={cli_entry}")
    if not channel:
        missing.append("notify.ops_clawd_channel")
    if not target:
        missing.append("notify.ops_clawd_to")
    if not message_path.exists():
        missing.append(f"message_path={message_path}")
    if missing:
        raise RuntimeError("Ops Clawd send preflight failed: " + ", ".join(missing))
    local_today = datetime.now(ZoneInfo(timezone_name)).date().isoformat()
    if send_allowed and run_date != local_today and not allow_stale_send:
        raise RuntimeError(
            f"stale ops message blocked: run_date={run_date} today={local_today}; "
            "use --allow-stale-send only for explicit manual catch-up"
        )


def write_ops_event(status: dict[str, Any], *, artifacts_dir: Path, manifest_path: Path) -> None:
    event_status = "ok" if status.get("status") == "OK" else "failed"
    decision = "pass" if event_status == "ok" else "stop"
    event = build_event(
        run_id=str(status["run_id"]),
        run_date=str(status["run_date"]),
        agent_id="ops_reporter",
        status=event_status,
        decision=decision,
        started_at=str(status["generated_at"]),
        finished_at=datetime.now(timezone.utc).isoformat(),
        input_refs=[str(status["rollup_path"])],
        artifact_paths=[str(status["message_path"]), str(status["output_path"])],
        failure_reason="; ".join(status.get("errors") or []) if event_status == "failed" else None,
        next_action=None if event_status == "ok" else "check ops Clawd config or CLI before next unattended run",
        metrics={"dry_run": status.get("dry_run"), "send_attempted": status.get("send_attempted"), "exit_code": status.get("exit_code")},
        discord_channel="ops_progress_channel",
        message_type="run_status" if event_status == "ok" else "blocker",
    )
    write_agent_event(event, artifacts_dir=artifacts_dir, manifest_path=manifest_path)
    manifest = read_manifest(manifest_path)
    rollup = build_rollup(artifacts_dir, str(status["run_date"]), str(status["run_id"]), manifest)
    write_rollup(artifacts_dir, str(status["run_date"]), str(status["run_id"]), rollup)


def write_rollup(artifacts_dir: Path, run_date: str, run_id: str, rollup: dict[str, Any]) -> None:
    output = artifacts_dir / "harness_status" / run_date / run_id / "rollup.json"
    latest = artifacts_dir / "harness_status" / run_date / "latest_rollup.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(rollup, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    output.write_text(payload, encoding="utf-8")
    latest.write_text(payload, encoding="utf-8")


def run_checked(command: list[str]) -> None:
    completed = subprocess.run(command, cwd=PROJECT_ROOT)
    if completed.returncode != 0:
        raise RuntimeError(f"command failed exit_code={completed.returncode}: {' '.join(command)}")


def build_research_decision_brief(*, run_date: str, artifacts_dir: Path) -> None:
    run_checked(
        [
            python_bin(),
            "scripts/build_research_decision_brief.py",
            "--run-date",
            run_date,
            "--artifacts-dir",
            str(artifacts_dir),
        ]
    )


def python_bin() -> str:
    candidate = PROJECT_ROOT / ".venv" / "bin" / "python"
    return str(candidate) if candidate.exists() else "python3"


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
