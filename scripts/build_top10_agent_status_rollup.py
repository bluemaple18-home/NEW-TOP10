#!/usr/bin/env python3
"""建立 TOP10 harness agent status dashboard rollup。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from top10_agent_status import DEFAULT_MANIFEST_PATH, load_events, read_manifest, validate_event
except ModuleNotFoundError:
    from scripts.top10_agent_status import DEFAULT_MANIFEST_PATH, load_events, read_manifest, validate_event


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
SCHEMA_VERSION = "top10-agent-status-rollup.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build top10 harness status rollup")
    parser.add_argument("--run-date", required=True)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--artifacts-dir", default=ARTIFACTS_DIR, type=Path)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST_PATH, type=Path)
    parser.add_argument("--output", default=None, type=Path)
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def main() -> int:
    args = parse_args()
    artifacts_dir = resolve(args.artifacts_dir)
    run_id = args.run_id or latest_run_id(artifacts_dir, args.run_date)
    if not run_id:
        raise SystemExit(f"missing run_id and latest_run_id for {args.run_date}")
    manifest = read_manifest(resolve(args.manifest))
    rollup = build_rollup(artifacts_dir, args.run_date, run_id, manifest)
    output = resolve(args.output) if args.output else artifacts_dir / "harness_status" / args.run_date / run_id / "rollup.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(rollup, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    latest = artifacts_dir / "harness_status" / args.run_date / "latest_rollup.json"
    latest.write_text(json.dumps(rollup, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": rollup["status"], "output": repo_path(output), "failed_count": rollup["summary"]["failed_count"]}, ensure_ascii=False))
    return 0 if rollup["status"] not in {"failed", "blocked"} else 1


def latest_run_id(artifacts_dir: Path, run_date: str) -> str | None:
    path = artifacts_dir / "harness_status" / run_date / "latest_run_id.txt"
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8").strip() or None


def build_rollup(artifacts_dir: Path, run_date: str, run_id: str, manifest: dict[str, Any]) -> dict[str, Any]:
    event_dir = artifacts_dir / "harness_status" / run_date / run_id / "events"
    events = load_events(event_dir)
    events_by_agent = {event.get("agent_id"): event for event in events}
    agent_rows = []
    failed_count = 0
    warning_count = 0
    missing_count = 0
    validation_errors: dict[str, list[str]] = {}

    manifest_agents = manifest.get("agents", [])
    for agent in manifest_agents:
        agent_id = agent["id"]
        event = events_by_agent.get(agent_id)
        if event is None:
            missing_count += 1
            agent_rows.append(
                {
                    "agent_id": agent_id,
                    "label": agent.get("label"),
                    "index": agent.get("index"),
                    "lane": agent.get("lane"),
                    "status": "pending",
                    "decision": "not_applicable",
                    "discord_channel": agent.get("discord_channel"),
                    "missing": True,
                }
            )
            continue
        errors = validate_event(event, manifest)
        if errors:
            validation_errors[agent_id] = errors
        status = event.get("status")
        if status in {"failed", "blocked"}:
            failed_count += 1
        elif status in {"warning", "degraded", "skipped"}:
            warning_count += 1
        agent_rows.append(
            {
                "agent_id": agent_id,
                "label": agent.get("label"),
                "index": agent.get("index"),
                "lane": agent.get("lane"),
                "status": status,
                "decision": event.get("decision"),
                "duration_seconds": event.get("duration_seconds"),
                "failure_reason": event.get("failure_reason"),
                "next_action": event.get("next_action"),
                "artifact_paths": event.get("artifact_paths") or [],
                "input_refs": event.get("input_refs") or [],
                "metrics": event.get("metrics") or {},
                "discord_channel": event.get("discord_channel") or agent.get("discord_channel"),
                "message_type": event.get("message_type"),
                "missing": False,
            }
        )

    status = "ok"
    if validation_errors or failed_count:
        status = "failed"
    elif missing_count:
        status = "degraded"
    elif warning_count:
        status = "warning"

    agent_rows = sorted(agent_rows, key=lambda row: row.get("index") or 999)
    formal_tasks = build_formal_tasks(manifest_agents, agent_rows)
    flow_edges = build_flow_edges(manifest.get("flows", []), agent_rows, manifest.get("channels", []))
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_date": run_date,
        "run_id": run_id,
        "status": status,
        "summary": {
            "agent_count": len(manifest.get("agents", [])),
            "event_count": len(events),
            "failed_count": failed_count,
            "warning_count": warning_count,
            "missing_count": missing_count,
            "validation_error_count": sum(len(value) for value in validation_errors.values()),
            "formal_task_count": len(formal_tasks),
            "formal_task_attention_count": sum(1 for task in formal_tasks if task.get("requires_attention")),
            "flow_edge_count": len(flow_edges),
            "flow_edge_blocked_count": sum(1 for edge in flow_edges if edge.get("edge_status") == "blocked"),
        },
        "agents": agent_rows,
        "formal_tasks": formal_tasks,
        "flow_edges": flow_edges,
        "channels": manifest.get("channels", []),
        "flows": manifest.get("flows", []),
        "validation_errors": validation_errors,
    }


def build_formal_tasks(manifest_agents: list[dict[str, Any]], agent_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows_by_agent = {row["agent_id"]: row for row in agent_rows}
    tasks = []
    for agent in manifest_agents:
        agent_id = str(agent["id"])
        row = rows_by_agent.get(agent_id, {})
        status = str(row.get("status") or "pending")
        tasks.append(
            {
                "task_id": f"TOP10-HARNESS-{int(agent.get('index') or 0):02d}-{agent_id}",
                "agent_id": agent_id,
                "label": agent.get("label"),
                "lane": agent.get("lane"),
                "index": agent.get("index"),
                "responsibility": agent.get("responsibility"),
                "status": status,
                "decision": row.get("decision", "not_applicable"),
                "requires_attention": status in {"pending", "warning", "degraded", "failed", "blocked"},
                "missing": bool(row.get("missing")),
                "inputs": agent.get("inputs") or [],
                "outputs": agent.get("outputs") or [],
                "dashboard_metrics": agent.get("dashboard_metrics") or [],
                "stop_conditions": agent.get("stop_conditions") or [],
                "artifact_paths": row.get("artifact_paths") or agent.get("artifact_paths") or [],
                "input_refs": row.get("input_refs") or [],
                "failure_reason": row.get("failure_reason"),
                "next_action": row.get("next_action"),
                "discord_channel": row.get("discord_channel") or agent.get("discord_channel"),
                "message_type": row.get("message_type"),
            }
        )
    return tasks


def build_flow_edges(flows: list[dict[str, Any]], agent_rows: list[dict[str, Any]], channels: list[dict[str, Any]]) -> list[dict[str, Any]]:
    agent_status = {row["agent_id"]: row.get("status") for row in agent_rows}
    channel_ids = {channel.get("id") for channel in channels}
    agent_ids = set(agent_status)
    edges = []
    for index, flow in enumerate(flows, start=1):
        source = str(flow.get("from") or "")
        target = str(flow.get("to") or "")
        source_status = agent_status.get(source)
        target_status = agent_status.get(target)
        source_kind = "channel" if source in channel_ids else "agent" if source in agent_ids else "unknown"
        target_kind = "channel" if target in channel_ids else "agent" if target in agent_ids else "unknown"
        edges.append(
            {
                "edge_id": f"TOP10-FLOW-{index:02d}-{source}-to-{target}",
                "from": source,
                "to": target,
                "kind": flow.get("kind"),
                "label": flow.get("label"),
                "source_kind": source_kind,
                "target_kind": target_kind,
                "source_status": source_status,
                "target_status": target_status,
                "connected": source_kind != "unknown" and target_kind != "unknown",
                "edge_status": flow_edge_status(source_status, target_status, target_kind),
            }
        )
    return edges


def flow_edge_status(source_status: str | None, target_status: str | None, target_kind: str) -> str:
    if source_status in {"failed", "blocked"}:
        return "blocked"
    if source_status in {None, "pending", "running"}:
        return "pending"
    if target_kind == "channel":
        return "active" if source_status in {"ok", "warning", "degraded", "skipped"} else "pending"
    if target_status in {"failed", "blocked"}:
        return "blocked"
    if target_status in {None, "pending", "running"}:
        return "pending"
    return "active"


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
