#!/usr/bin/env python3
"""匯出 TOP10 loop 狀態給 ai-core team_status_adapter 接入前驗證。

這支 exporter 只讀既有 harness rollup/event artifacts，不執行 daily、
publish、ranking 或 portfolio 動作。
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
DEFAULT_OUTPUT = PROJECT_ROOT / ".work" / "loop-status-exporter" / "evidence" / "top10_loop_status_latest.json"
SCHEMA_VERSION = "top10-loop-status-summary.v1"
TEAM_ID = "top10"
TEAM_NAME = "TOP10 Team"
LOCAL_ABSOLUTE_MARKERS = ("/Users/", "/private/", "/tmp/", "/var/folders/")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export normalized TOP10 loop status summary.")
    parser.add_argument("--run-date", default=None, help="預設使用 artifacts/harness_status 下最新日期。")
    parser.add_argument("--run-id", default=None, help="預設使用 daily-<run-date>，不存在時才用 latest_run_id.txt。")
    parser.add_argument("--artifacts-dir", default=ARTIFACTS_DIR, type=Path)
    parser.add_argument("--output", default=DEFAULT_OUTPUT, type=Path)
    parser.add_argument("--validate-only", action="store_true", help="只建立並驗證 payload，不寫檔。")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifacts_dir = resolve_path(args.artifacts_dir)
    output = resolve_path(args.output)
    summary = build_summary(artifacts_dir=artifacts_dir, run_date=args.run_date, run_id=args.run_id)
    validate_summary(summary)
    if not args.validate_only:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "ok",
                "team_id": summary["team_id"],
                "team_status": summary["status"],
                "latest_run_id": summary["latest_run_id"],
                "output": repo_path(output) if not args.validate_only else None,
                "write_enabled": not args.validate_only,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be object: {repo_path(path)}")
    return payload


def repo_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def artifact_ref(path: Path, artifacts_dir: Path) -> str:
    try:
        return f"artifacts/{path.resolve().relative_to(artifacts_dir.resolve()).as_posix()}"
    except ValueError:
        return repo_path(path)


def latest_run_date(artifacts_dir: Path) -> str | None:
    root = artifacts_dir / "harness_status"
    if not root.exists():
        return None
    dates = sorted(path.name for path in root.iterdir() if path.is_dir())
    return dates[-1] if dates else None


def choose_run_id(artifacts_dir: Path, run_date: str, requested_run_id: str | None) -> str | None:
    if requested_run_id:
        return requested_run_id
    daily_run_id = f"daily-{run_date}"
    if (artifacts_dir / "harness_status" / run_date / daily_run_id / "rollup.json").exists():
        return daily_run_id
    latest = artifacts_dir / "harness_status" / run_date / "latest_run_id.txt"
    if latest.exists():
        return latest.read_text(encoding="utf-8").strip() or None
    return None


def rollup_path(artifacts_dir: Path, run_date: str, run_id: str) -> Path:
    return artifacts_dir / "harness_status" / run_date / run_id / "rollup.json"


def event_dir(artifacts_dir: Path, run_date: str, run_id: str) -> Path:
    return artifacts_dir / "harness_status" / run_date / run_id / "events"


def load_events(artifacts_dir: Path, run_date: str, run_id: str) -> list[dict[str, Any]]:
    root = event_dir(artifacts_dir, run_date, run_id)
    if not root.exists():
        return []
    events: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        events.append(read_json(path))
    return events


def max_finished_at(events: list[dict[str, Any]], fallback: str | None) -> str | None:
    values = [str(event.get("finished_at")) for event in events if event.get("finished_at")]
    return sorted(values)[-1] if values else fallback


def map_team_status(raw_status: str | None, missing_rollup: bool = False) -> str:
    if missing_rollup:
        return "unknown"
    if raw_status == "ok":
        return "ok"
    if raw_status in {"failed"}:
        return "failed"
    if raw_status in {"blocked", "degraded", "warning"}:
        return "blocked"
    if raw_status in {"running", "pending"}:
        return "running"
    return "unknown"


def blockers_from_rollup(rollup: dict[str, Any] | None) -> list[str]:
    if rollup is None:
        return ["top10_harness_rollup_missing"]
    blockers: list[str] = []
    status = str(rollup.get("status") or "unknown")
    if status not in {"ok"}:
        blockers.append(f"harness_status:{status}")
    validation_errors = rollup.get("validation_errors")
    if isinstance(validation_errors, dict) and validation_errors:
        blockers.append("harness_validation_errors")
    summary = rollup.get("summary") if isinstance(rollup.get("summary"), dict) else {}
    for key in ("failed_count", "missing_count", "formal_task_attention_count"):
        value = summary.get(key)
        if isinstance(value, int) and value > 0:
            blockers.append(f"{key}:{value}")
    return blockers


def attention_items(rollup: dict[str, Any] | None) -> list[dict[str, Any]]:
    if rollup is None:
        return []
    rows = rollup.get("agents") if isinstance(rollup.get("agents"), list) else []
    items: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        status = str(row.get("status") or "")
        if status not in {"failed", "blocked", "warning", "degraded", "pending"}:
            continue
        items.append(
            {
                "agent_id": row.get("agent_id"),
                "status": status,
                "failure_reason": row.get("failure_reason"),
                "next_action": row.get("next_action"),
            }
        )
    return items


def research_rollup_refs(artifacts_dir: Path, run_date: str, primary_run_id: str | None) -> list[dict[str, Any]]:
    root = artifacts_dir / "harness_status" / run_date
    if not root.exists():
        return []
    refs: list[dict[str, Any]] = []
    for path in sorted(root.glob("*/rollup.json")):
        run_id = path.parent.name
        if run_id == primary_run_id:
            continue
        payload = read_json(path)
        if run_id.startswith("fog-") or run_id.startswith("research-"):
            refs.append(
                {
                    "run_id": run_id,
                    "status": payload.get("status"),
                    "generated_at": payload.get("generated_at"),
                    "summary_path": artifact_ref(path, artifacts_dir),
                }
            )
    return refs[-10:]


def loop_surface(rollup_ref: str | None, research_refs: list[dict[str, Any]]) -> dict[str, Any]:
    evidence = [rollup_ref] if rollup_ref else []
    evidence.extend(str(ref["summary_path"]) for ref in research_refs if ref.get("summary_path"))
    return {
        "schema_version": "top10.loop_surface.v1",
        "flow": "top10",
        "maker": "TOP10 owner bots and dashboard/event nodes",
        "checker": "data quality gate, anomaly circuit breaker, external review harness",
        "trigger": "daily pipeline and ops channels",
        "evidence": evidence,
        "failure_policy": "fail loud through harness status blockers; exporter never publishes or changes ranking",
        "improvement_path": "outcome tracker, disagreement next actions, and review deltas become reviewed task cards",
    }


def build_summary(artifacts_dir: Path, run_date: str | None = None, run_id: str | None = None) -> dict[str, Any]:
    selected_date = run_date or latest_run_date(artifacts_dir) or date.today().isoformat()
    selected_run_id = choose_run_id(artifacts_dir, selected_date, run_id)
    rollup: dict[str, Any] | None = None
    selected_rollup_path: Path | None = None
    events: list[dict[str, Any]] = []
    if selected_run_id:
        selected_rollup_path = rollup_path(artifacts_dir, selected_date, selected_run_id)
        if selected_rollup_path.exists():
            rollup = read_json(selected_rollup_path)
            events = load_events(artifacts_dir, selected_date, selected_run_id)
    missing_rollup = rollup is None
    raw_status = str(rollup.get("status")) if rollup else None
    research_refs = research_rollup_refs(artifacts_dir, selected_date, selected_run_id)
    finished_at = max_finished_at(events, str(rollup.get("generated_at")) if rollup else None)
    rollup_ref = artifact_ref(selected_rollup_path, artifacts_dir) if selected_rollup_path and selected_rollup_path.exists() else None
    blockers = blockers_from_rollup(rollup)
    return {
        "schema_version": SCHEMA_VERSION,
        "team_id": TEAM_ID,
        "team_name": TEAM_NAME,
        "status": map_team_status(raw_status, missing_rollup=missing_rollup),
        "raw_harness_status": raw_status,
        "latest_run_id": selected_run_id,
        "latest_run_summary": rollup_ref,
        "run_date": selected_date,
        "finished_at": finished_at,
        "blockers": blockers,
        "next_action": None if not blockers else "review TOP10 harness rollup blockers before marking live in ai-core",
        "board_path": "external:top10/.work/boards/main.json",
        "handoff_path": "external:top10/.work/current/handoff.md",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source_adapter": "external_project_status_exporter",
        "loop_surface": loop_surface(rollup_ref, research_refs),
        "refs": {
            "daily_rollup": rollup_ref,
            "research_rollups": research_refs,
        },
        "summary": rollup.get("summary") if rollup else {},
        "attention_items": attention_items(rollup),
        "metadata": {
            "owner_bot_count": 10,
            "formal_agent_count": 15,
            "exporter_is_read_only": True,
            "no_production_push": True,
            "no_channel_send": True,
            "no_portfolio_action": True,
        },
    }


def validate_summary(summary: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = {
        "schema_version",
        "team_id",
        "status",
        "latest_run_id",
        "finished_at",
        "blockers",
        "loop_surface",
        "refs",
    }
    missing = sorted(required - set(summary))
    errors.extend(f"{key}: missing" for key in missing)
    if summary.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version: must be {SCHEMA_VERSION}")
    if summary.get("team_id") != TEAM_ID:
        errors.append("team_id: must be top10")
    if summary.get("status") not in {"ok", "running", "blocked", "failed", "unknown"}:
        errors.append(f"status: unsupported {summary.get('status')!r}")
    if not isinstance(summary.get("blockers"), list):
        errors.append("blockers: must be list")
    if not isinstance(summary.get("loop_surface"), dict):
        errors.append("loop_surface: must be object")
    if not isinstance(summary.get("refs"), dict):
        errors.append("refs: must be object")
    encoded = json.dumps(summary, ensure_ascii=False, sort_keys=True)
    for marker in LOCAL_ABSOLUTE_MARKERS:
        if marker in encoded:
            errors.append(f"paths: contains local absolute marker {marker}")
            break
    if errors:
        raise ValueError("; ".join(errors))
    return []


if __name__ == "__main__":
    raise SystemExit(main())
