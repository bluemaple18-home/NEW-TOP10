#!/usr/bin/env python3
"""TOP10 harness agent status event contract.

這個模組只處理事件格式、驗證與落檔，不執行 runner 本身。
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "top10-agent-status-event.v1"
DEFAULT_MANIFEST_PATH = Path("docs/architecture/top10_harness_team.dashboard.json")
STATUS_ENUM = {"pending", "running", "ok", "warning", "degraded", "skipped", "failed", "blocked"}
DECISION_ENUM = {
    "pass",
    "stop",
    "degrade",
    "quarantine",
    "partial",
    "accept",
    "reject",
    "needs_more_data",
    "not_applicable",
}
ABSOLUTE_LOCAL_PATH = re.compile(r"^(?:/Users/|/private/|/tmp/|[A-Za-z]:[\\/])")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def repo_relative(path: str | Path, project_root: Path) -> str:
    resolved = Path(path)
    if not resolved.is_absolute():
        return str(resolved)
    try:
        return str(resolved.resolve().relative_to(project_root.resolve()))
    except ValueError:
        return str(resolved)


def read_manifest(path: str | Path = DEFAULT_MANIFEST_PATH) -> dict[str, Any]:
    manifest_path = Path(path)
    if not manifest_path.exists():
        return {}
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def known_agent_ids(manifest: dict[str, Any]) -> set[str]:
    return {str(agent.get("id")) for agent in manifest.get("agents", []) if isinstance(agent, dict) and agent.get("id")}


def known_channel_ids(manifest: dict[str, Any]) -> set[str]:
    return {str(channel.get("id")) for channel in manifest.get("channels", []) if isinstance(channel, dict) and channel.get("id")}


def build_event(
    *,
    run_id: str,
    run_date: str,
    agent_id: str,
    status: str,
    decision: str = "not_applicable",
    started_at: str | None = None,
    finished_at: str | None = None,
    input_refs: list[str] | None = None,
    artifact_paths: list[str] | None = None,
    failure_reason: str | None = None,
    next_action: str | None = None,
    metrics: dict[str, Any] | None = None,
    discord_channel: str | None = None,
    message_type: str | None = None,
) -> dict[str, Any]:
    start = started_at or utc_now()
    finish = finished_at or (utc_now() if status != "running" else None)
    duration = duration_seconds(start, finish)
    event: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "run_id": run_id,
        "run_date": run_date,
        "agent_id": agent_id,
        "status": status,
        "decision": decision,
        "started_at": start,
        "finished_at": finish,
        "duration_seconds": duration,
        "input_refs": input_refs or [],
        "artifact_paths": artifact_paths or [],
        "failure_reason": failure_reason,
        "next_action": next_action,
        "metrics": metrics or {},
    }
    if discord_channel:
        event["discord_channel"] = discord_channel
    if message_type:
        event["message_type"] = message_type
    return event


def duration_seconds(started_at: str | None, finished_at: str | None) -> float | None:
    if not started_at or not finished_at:
        return None
    try:
        start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        finish = datetime.fromisoformat(finished_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    return round(max(0.0, (finish - start).total_seconds()), 6)


def validate_event(event: Any, manifest: dict[str, Any] | None = None) -> list[str]:
    errors: list[str] = []
    if not isinstance(event, dict):
        return ["root: must be object"]
    manifest = manifest or {}
    required = [
        "schema_version",
        "run_id",
        "run_date",
        "agent_id",
        "status",
        "decision",
        "started_at",
        "finished_at",
        "duration_seconds",
        "input_refs",
        "artifact_paths",
        "failure_reason",
        "next_action",
    ]
    for key in required:
        if key not in event:
            errors.append(f"{key}: missing")
    if event.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version: must be {SCHEMA_VERSION}")
    for key in ("run_id", "run_date", "agent_id", "status", "decision"):
        if not isinstance(event.get(key), str) or not event.get(key):
            errors.append(f"{key}: must be non-empty string")
    if event.get("status") not in STATUS_ENUM:
        errors.append(f"status: unsupported {event.get('status')!r}")
    if event.get("decision") not in DECISION_ENUM:
        errors.append(f"decision: unsupported {event.get('decision')!r}")

    agents = known_agent_ids(manifest)
    if agents and event.get("agent_id") not in agents:
        errors.append(f"agent_id: unknown {event.get('agent_id')!r}")
    channels = known_channel_ids(manifest)
    if event.get("discord_channel") and channels and event.get("discord_channel") not in channels:
        errors.append(f"discord_channel: unknown {event.get('discord_channel')!r}")

    for key in ("input_refs", "artifact_paths"):
        value = event.get(key)
        if not isinstance(value, list):
            errors.append(f"{key}: must be list")
            continue
        for index, item in enumerate(value):
            if not isinstance(item, str):
                errors.append(f"{key}[{index}]: must be string")
            elif ABSOLUTE_LOCAL_PATH.search(item):
                errors.append(f"{key}[{index}]: must be repo-relative, got {item}")

    metrics = event.get("metrics")
    if metrics is not None and not isinstance(metrics, dict):
        errors.append("metrics: must be object")
    duration = event.get("duration_seconds")
    if duration is not None and not isinstance(duration, (int, float)):
        errors.append("duration_seconds: must be number or null")
    if event.get("finished_at") is None and event.get("status") != "running":
        errors.append("finished_at: required unless status is running")
    return errors


def event_paths(artifacts_dir: Path, run_date: str, run_id: str, agent_id: str) -> dict[str, Path]:
    root = artifacts_dir / "harness_status" / run_date / run_id
    return {
        "root": root,
        "event": root / "events" / f"{agent_id}.json",
        "jsonl": root / "events.jsonl",
        "latest_run": artifacts_dir / "harness_status" / run_date / "latest_run_id.txt",
    }


def write_agent_event(event: dict[str, Any], *, artifacts_dir: str | Path = "artifacts", manifest_path: str | Path = DEFAULT_MANIFEST_PATH) -> Path:
    manifest = read_manifest(manifest_path)
    errors = validate_event(event, manifest)
    if errors:
        raise ValueError("; ".join(errors))
    artifacts = Path(artifacts_dir)
    paths = event_paths(artifacts, event["run_date"], event["run_id"], event["agent_id"])
    paths["event"].parent.mkdir(parents=True, exist_ok=True)
    paths["event"].write_text(json.dumps(event, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with paths["jsonl"].open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    paths["latest_run"].write_text(event["run_id"] + "\n", encoding="utf-8")
    return paths["event"]


def load_events(events_dir: Path) -> list[dict[str, Any]]:
    events = []
    if not events_dir.exists():
        return events
    for path in sorted(events_dir.glob("*.json")):
        events.append(json.loads(path.read_text(encoding="utf-8")))
    return events
