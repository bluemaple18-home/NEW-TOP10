#!/usr/bin/env python3
"""TOP10 harness agent status event contract.

這個模組只處理事件格式、驗證與落檔，不執行 runner 本身。
"""

from __future__ import annotations

import json
import fcntl
import os
import re
from contextlib import contextmanager, nullcontext
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


def owns_latest_run(artifacts_dir: Path, run_date: str, run_id: str) -> bool:
    """同日既有 latest owner 不得由舊 run 的回讀／重建暗中取代。"""
    latest = artifacts_dir / "harness_status" / run_date / "latest_run_id.txt"
    try:
        owner = latest.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return True
    return not owner or owner == run_id


def is_early_daily_failure(event: dict[str, Any]) -> bool:
    """辨識 Daily 在 publish 前失敗的正式阻塞事件。"""
    return (
        event["agent_id"] == "daily_push"
        and event["run_id"] == f"daily-{event['run_date']}"
        and event["status"] == "skipped" and event["decision"] == "stop"
        and str(event.get("failure_reason") or "").startswith("daily failed before publish;")
    )


def newer_harness_run(artifacts_dir: Path, run_date: str, run_id: str, event: dict[str, Any]) -> bool:
    """只允許有較晚、可驗證開始時間的新 Daily 接管 owner。"""
    if event.get("agent_id") != "harness_runner" and not is_early_daily_failure(event):
        return False
    owner_path = artifacts_dir / "harness_status" / run_date / "latest_run_id.txt"
    try:
        owner = owner_path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return False
    if owner == run_id:
        return False
    try:
        prior = json.loads(event_paths(artifacts_dir, run_date, owner, "harness_runner")["event"].read_text(encoding="utf-8"))
    except FileNotFoundError:
        # 舊版可由送達事件建立 latest；仍須比較其最早可驗證時間。
        prior = None
        for agent_id in ("research_worker", "daily_push", "ops_reporter"):
            try:
                prior = json.loads(event_paths(artifacts_dir, run_date, owner, agent_id)["event"].read_text(encoding="utf-8"))
                break
            except FileNotFoundError:
                continue
            except (OSError, UnicodeError, ValueError, TypeError):
                return False
        if prior is None:
            # 無可核對的前任開始時間時，禁止舊 run 搶回 owner。
            return False
    except (OSError, UnicodeError, ValueError, TypeError):
        return False
    try:
        current_start = datetime.fromisoformat(str(event["started_at"]))
        prior_start = datetime.fromisoformat(str(prior["started_at"]))
    except (ValueError, TypeError, KeyError):
        return False
    return (owner != run_id and prior.get("run_id") == owner
            and current_start.tzinfo is not None and prior_start.tzinfo is not None
            and current_start > prior_start)


@contextmanager
def rollup_lock(artifacts_dir: Path, run_date: str, run_id: str):
    """同日期所有 run 共用鎖，避免 latest 指標被舊快照覆蓋。"""
    root = artifacts_dir / "harness_status" / run_date
    root.mkdir(parents=True, exist_ok=True)
    if root.is_symlink():
        raise RuntimeError("rollup date root symlink rejected")
    # 鎖目錄 inode；單純替換 rollup.lock 檔名不能產生第二把鎖。
    descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def event_record_complete(artifacts_dir: Path, run_date: str, run_id: str, agent_id: str) -> bool:
    """歷史送達以該 run 的事件、JSONL 與 rollup 驗證，latest 可指向新 run。"""
    paths = event_paths(artifacts_dir, run_date, run_id, agent_id)
    rollup = paths["root"] / "rollup.json"
    try:
        event = json.loads(paths["event"].read_text(encoding="utf-8"))
        if (event.get("run_date") != run_date or event.get("run_id") != run_id
            or event.get("agent_id") != agent_id or event.get("status") != "ok"
            or event.get("decision") != "pass"):
            return False
        history = [json.loads(line) for line in paths["jsonl"].read_text(encoding="utf-8").splitlines() if line]
        if not any(item.get("agent_id") == agent_id and item.get("run_id") == run_id
                   and item.get("status") == "ok" for item in history):
            return False
        for path in (rollup,):
            state = json.loads(path.read_text(encoding="utf-8"))
            if state.get("run_date") != run_date or state.get("run_id") != run_id:
                return False
            if not any(item.get("agent_id") == agent_id and item.get("status") == "ok"
                       for item in state.get("agents", []) if isinstance(item, dict)):
                return False
    except (OSError, UnicodeError, ValueError, TypeError, AttributeError):
        return False
    return True


def write_agent_event(
    event: dict[str, Any], *, artifacts_dir: str | Path = "artifacts",
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH, lock_held: bool = False,
) -> Path:
    manifest = read_manifest(manifest_path)
    errors = validate_event(event, manifest)
    if errors:
        raise ValueError("; ".join(errors))
    artifacts = Path(artifacts_dir)
    lock = nullcontext() if lock_held else rollup_lock(artifacts, event["run_date"], event["run_id"])
    with lock:
        paths = event_paths(artifacts, event["run_date"], event["run_id"], event["agent_id"])
        paths["event"].parent.mkdir(parents=True, exist_ok=True)
        paths["event"].write_text(json.dumps(event, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        with paths["jsonl"].open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        has_owner = paths["latest_run"].exists()
        daily_pre_publish_failure = is_early_daily_failure(event)
        delivery_without_owner = (not has_owner and event["agent_id"] in {"daily_push", "ops_reporter"}
                                  and not daily_pre_publish_failure)
        if (not delivery_without_owner and owns_latest_run(artifacts, event["run_date"], event["run_id"])
            or newer_harness_run(artifacts, event["run_date"], event["run_id"], event)):
            paths["latest_run"].write_text(event["run_id"] + "\n", encoding="utf-8")
        return paths["event"]


def load_events(events_dir: Path) -> list[dict[str, Any]]:
    events = []
    if not events_dir.exists():
        return events
    for path in sorted(events_dir.glob("*.json")):
        events.append(json.loads(path.read_text(encoding="utf-8")))
    return events
