#!/usr/bin/env python3
"""記錄每日報牌頻道 publish 結果。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from build_top10_agent_status_rollup import build_rollup
    from top10_agent_status import DEFAULT_MANIFEST_PATH, build_event, read_manifest, write_agent_event
except ModuleNotFoundError:
    from scripts.build_top10_agent_status_rollup import build_rollup
    from scripts.top10_agent_status import DEFAULT_MANIFEST_PATH, build_event, read_manifest, write_agent_event


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="record top10 daily publish event")
    parser.add_argument("--run-date", required=True)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--status", required=True, choices=["ok", "skipped", "failed"])
    parser.add_argument("--decision", default=None, choices=["pass", "stop", "not_applicable"])
    parser.add_argument("--reason", default=None)
    parser.add_argument("--message", default=None, type=Path)
    parser.add_argument("--send-exit-code", default=None, type=int)
    parser.add_argument("--artifacts-dir", default=ARTIFACTS_DIR, type=Path)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST_PATH, type=Path)
    parser.add_argument("--skip-rollup", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifacts_dir = resolve_path(args.artifacts_dir)
    manifest_path = resolve_path(args.manifest)
    run_id = args.run_id or f"daily-{args.run_date}"
    now = datetime.now(timezone.utc).isoformat()
    decision = args.decision or default_decision(args.status)
    artifact_paths: list[str | Path] = [artifacts_dir / "automation_status.json"]
    if args.message:
        artifact_paths.append(resolve_path(args.message))

    event = build_event(
        run_id=run_id,
        run_date=args.run_date,
        agent_id="daily_push",
        status=args.status,
        decision=decision,
        started_at=now,
        finished_at=now,
        input_refs=[safe_ref(path, artifacts_dir) for path in artifact_paths],
        artifact_paths=[safe_ref(path, artifacts_dir) for path in artifact_paths],
        failure_reason=args.reason if args.status in {"failed", "skipped"} else None,
        next_action=next_action(args.status, args.reason),
        metrics={"send_exit_code": args.send_exit_code},
        discord_channel="daily_pick_channel",
        message_type="daily_top10",
    )
    write_agent_event(event, artifacts_dir=artifacts_dir, manifest_path=manifest_path)

    if not args.skip_rollup:
        manifest = read_manifest(manifest_path)
        rollup = build_rollup(artifacts_dir, args.run_date, run_id, manifest)
        write_rollup(artifacts_dir, args.run_date, run_id, rollup)

    print(json.dumps({"status": "ok", "run_id": run_id, "agent_id": "daily_push"}, ensure_ascii=False))
    return 0


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def default_decision(status: str) -> str:
    if status == "ok":
        return "pass"
    if status == "failed":
        return "stop"
    return "not_applicable"


def next_action(status: str, reason: str | None) -> str | None:
    if status == "ok":
        return "daily pick message sent to report channel"
    if status == "failed":
        return "post blocker to ops progress channel and retry only after fixing send failure"
    if reason:
        return "record skip reason in ops progress channel"
    return None


def safe_ref(path: str | Path, artifacts_dir: Path) -> str:
    value = Path(path)
    if not value.is_absolute():
        return str(value)
    try:
        return str(value.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        pass
    try:
        return str(value.resolve().relative_to(artifacts_dir.resolve()))
    except ValueError:
        return f"local_artifact/{value.name}"


def write_rollup(artifacts_dir: Path, run_date: str, run_id: str, rollup: dict[str, Any]) -> None:
    output = artifacts_dir / "harness_status" / run_date / run_id / "rollup.json"
    latest = artifacts_dir / "harness_status" / run_date / "latest_rollup.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(rollup, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    output.write_text(payload, encoding="utf-8")
    latest.write_text(payload, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
