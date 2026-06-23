#!/usr/bin/env python3
"""把 daily automation_status 轉成 TOP10 harness status events。"""

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
AUTOMATION_STATUS_PATH = ARTIFACTS_DIR / "automation_status.json"

FAILED_STATUSES = {"FAILED"}
WARNING_STATUSES = {"WARN"}
SKIPPED_STATUSES = {"SKIPPED", "DRY_RUN"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="record top10 daily harness status events")
    parser.add_argument("--run-date", default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--status", default=AUTOMATION_STATUS_PATH, type=Path)
    parser.add_argument("--artifacts-dir", default=ARTIFACTS_DIR, type=Path)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST_PATH, type=Path)
    parser.add_argument("--skip-rollup", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifacts_dir = resolve_path(args.artifacts_dir)
    manifest_path = resolve_path(args.manifest)
    status_path = resolve_path(args.status)
    status = read_json(status_path)
    run_date = args.run_date or str(status.get("run_date") or datetime.now().date().isoformat())
    run_id = args.run_id or f"daily-{run_date}"

    events = build_daily_events(
        status=status,
        status_path=status_path,
        artifacts_dir=artifacts_dir,
        run_date=run_date,
        run_id=run_id,
    )
    for event in events:
        write_agent_event(event, artifacts_dir=artifacts_dir, manifest_path=manifest_path)

    if not args.skip_rollup:
        manifest = read_manifest(manifest_path)
        rollup = build_rollup(artifacts_dir, run_date, run_id, manifest)
        write_rollup(artifacts_dir, run_date, run_id, rollup)

    print(json.dumps({"status": "ok", "run_id": run_id, "event_count": len(events)}, ensure_ascii=False))
    return 0


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"automation status not found: {safe_ref(path, ARTIFACTS_DIR)}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"automation status must be object: {safe_ref(path, ARTIFACTS_DIR)}")
    return payload


def build_daily_events(
    *,
    status: dict[str, Any],
    status_path: Path,
    artifacts_dir: Path,
    run_date: str,
    run_id: str,
) -> list[dict[str, Any]]:
    started_at = str(status.get("started_at") or utc_now())
    finished_at = str(status.get("finished_at") or utc_now())
    steps = status.get("steps") if isinstance(status.get("steps"), list) else []
    step_map = {str(step.get("name")): step for step in steps if isinstance(step, dict) and step.get("name")}
    metadata = status.get("metadata") if isinstance(status.get("metadata"), dict) else {}
    automation_status = str(status.get("status") or "FAILED").upper()
    summary_path = artifacts_dir / f"daily_run_summary_{run_date}.json"
    base_artifacts = [status_path]
    if summary_path.exists():
        base_artifacts.append(summary_path)

    events = [
        harness_event(status, steps, base_artifacts, artifacts_dir, run_date, run_id, started_at, finished_at),
        preflight_event(status, step_map, base_artifacts, artifacts_dir, run_date, run_id),
        step_group_event(
            run_id=run_id,
            run_date=run_date,
            agent_id="data_etl",
            steps=[step_map.get("etl")],
            input_refs=["config/automation.yaml"],
            artifact_paths=dataset_artifacts(metadata, artifacts_dir),
            fallback_started_at=started_at,
            fallback_finished_at=finished_at,
            artifacts_dir=artifacts_dir,
            missing_status=upstream_missing_status(automation_status, step_map, "etl"),
            missing_reason="ETL step did not run",
            next_action="inspect automation_status and daily log before trusting ranking",
        ),
        step_group_event(
            run_id=run_id,
            run_date=run_date,
            agent_id="data_quality_gate",
            steps=[step_map.get("data.validate"), step_map.get("data.freshness.after_etl")],
            input_refs=dataset_artifacts(metadata, artifacts_dir),
            artifact_paths=[status_path],
            fallback_started_at=started_at,
            fallback_finished_at=finished_at,
            artifacts_dir=artifacts_dir,
            missing_status=upstream_missing_status(automation_status, step_map, "data.validate"),
            missing_reason="data quality gate did not complete",
            next_action="do not publish ranking until data.validate and freshness are available",
        ),
        step_group_event(
            run_id=run_id,
            run_date=run_date,
            agent_id="ranking",
            steps=[step_map.get("ranking"), step_map.get("ranking.artifact")],
            input_refs=dataset_artifacts(metadata, artifacts_dir),
            artifact_paths=metadata_paths(metadata, artifacts_dir, ["ranking_artifact", "expected_ranking_artifact"]),
            fallback_started_at=started_at,
            fallback_finished_at=finished_at,
            artifacts_dir=artifacts_dir,
            missing_status=upstream_missing_status(automation_status, step_map, "ranking"),
            missing_reason="ranking step did not complete",
            next_action="block daily pick publish until ranking artifact is fresh",
        ),
        anomaly_event(status, step_map, metadata, artifacts_dir, run_date, run_id, started_at, finished_at),
        outcome_event(step_map, metadata, artifacts_dir, run_date, run_id, started_at, finished_at),
        ops_event(status, base_artifacts, artifacts_dir, run_date, run_id, started_at, finished_at),
    ]
    return events


def harness_event(
    status: dict[str, Any],
    steps: list[Any],
    artifact_paths: list[str | Path],
    artifacts_dir: Path,
    run_date: str,
    run_id: str,
    started_at: str,
    finished_at: str,
) -> dict[str, Any]:
    automation_status = str(status.get("status") or "FAILED").upper()
    event_status, decision = automation_to_event_status(automation_status)
    errors = status.get("errors") if isinstance(status.get("errors"), list) else []
    skip_reason = status.get("skip_reason")
    return make_event(
        run_id=run_id,
        run_date=run_date,
        agent_id="harness_runner",
        status=event_status,
        decision=decision,
        started_at=started_at,
        finished_at=finished_at,
        input_refs=["config/automation.yaml"],
        artifact_paths=artifact_paths,
        artifacts_dir=artifacts_dir,
        failure_reason=first_text(errors) or (str(skip_reason) if skip_reason else None),
        next_action=harness_next_action(event_status),
        metrics={
            "automation_status": automation_status,
            "step_count": len(steps),
            "error_count": len(errors),
            "dry_run": bool(status.get("dry_run")),
        },
    )


def preflight_event(
    status: dict[str, Any],
    step_map: dict[str, dict[str, Any]],
    artifact_paths: list[str | Path],
    artifacts_dir: Path,
    run_date: str,
    run_id: str,
) -> dict[str, Any]:
    skip_step = step_map.get("daily.disabled") or step_map.get("daily.trading_day_gate")
    if skip_step:
        return step_group_event(
            run_id=run_id,
            run_date=run_date,
            agent_id="preflight",
            steps=[skip_step],
            input_refs=["config/automation.yaml"],
            artifact_paths=artifact_paths,
            fallback_started_at=str(status.get("started_at") or utc_now()),
            fallback_finished_at=str(status.get("finished_at") or utc_now()),
            artifacts_dir=artifacts_dir,
            missing_status=("skipped", "not_applicable"),
            missing_reason=None,
            next_action="wait for enabled trading-day run",
        )
    return step_group_event(
        run_id=run_id,
        run_date=run_date,
        agent_id="preflight",
        steps=[
            step_map.get("resource_guard.daily"),
            step_map.get("daily.schema"),
            step_map.get("daily.run_date"),
            step_map.get("model.exists"),
            step_map.get("data.freshness.preflight"),
        ],
        input_refs=["config/automation.yaml", "models/latest_lgbm.pkl"],
        artifact_paths=artifact_paths,
        fallback_started_at=str(status.get("started_at") or utc_now()),
        fallback_finished_at=str(status.get("finished_at") or utc_now()),
        artifacts_dir=artifacts_dir,
        missing_status=upstream_missing_status(str(status.get("status") or "FAILED").upper(), step_map, "daily.schema"),
        missing_reason="daily preflight did not complete",
        next_action="fix preflight before ETL/ranking",
    )


def anomaly_event(
    status: dict[str, Any],
    step_map: dict[str, dict[str, Any]],
    metadata: dict[str, Any],
    artifacts_dir: Path,
    run_date: str,
    run_id: str,
    started_at: str,
    finished_at: str,
) -> dict[str, Any]:
    steps = [
        step_map.get("decision.quality"),
        step_map.get("decision.quality.artifact"),
        step_map.get("daily.postcheck"),
    ]
    artifact_paths = metadata_paths(metadata, artifacts_dir, ["decision_quality_artifact", "expected_decision_quality_artifact"])
    if not artifact_paths:
        artifact_paths = [artifacts_dir / f"decision_quality_{run_date}.json"]
    return step_group_event(
        run_id=run_id,
        run_date=run_date,
        agent_id="anomaly_circuit_breaker",
        steps=steps,
        input_refs=metadata_paths(metadata, artifacts_dir, ["ranking_artifact", "expected_ranking_artifact"]),
        artifact_paths=artifact_paths,
        fallback_started_at=started_at,
        fallback_finished_at=finished_at,
        artifacts_dir=artifacts_dir,
        missing_status=upstream_missing_status(str(status.get("status") or "FAILED").upper(), step_map, "decision.quality"),
        missing_reason="anomaly/circuit breaker checks did not complete",
        next_action="keep publish blocked until decision_quality or postcheck evidence exists",
    )


def outcome_event(
    step_map: dict[str, dict[str, Any]],
    metadata: dict[str, Any],
    artifacts_dir: Path,
    run_date: str,
    run_id: str,
    started_at: str,
    finished_at: str,
) -> dict[str, Any]:
    return step_group_event(
        run_id=run_id,
        run_date=run_date,
        agent_id="outcome_tracker",
        steps=[step_map.get("candidate.persistence"), step_map.get("weekly.snapshot"), step_map.get("market.context")],
        input_refs=metadata_paths(metadata, artifacts_dir, ["ranking_artifact", "expected_ranking_artifact"]),
        artifact_paths=metadata_paths(
            metadata,
            artifacts_dir,
            ["market_context_artifact", "expected_market_context_artifact"],
        ),
        fallback_started_at=started_at,
        fallback_finished_at=finished_at,
        artifacts_dir=artifacts_dir,
        missing_status=("skipped", "not_applicable"),
        missing_reason="outcome tracker evidence not produced by this daily run",
        next_action="track realized outcomes when enough market data has elapsed",
    )


def ops_event(
    status: dict[str, Any],
    artifact_paths: list[str | Path],
    artifacts_dir: Path,
    run_date: str,
    run_id: str,
    started_at: str,
    finished_at: str,
) -> dict[str, Any]:
    automation_status = str(status.get("status") or "FAILED").upper()
    event_status, decision = automation_to_event_status(automation_status)
    if event_status == "ok":
        next_action = "post daily summary to ops progress channel"
    elif event_status == "skipped":
        next_action = "record skipped daily run in ops progress channel"
    else:
        next_action = "post blocker and next repair action to ops progress channel"
    return make_event(
        run_id=run_id,
        run_date=run_date,
        agent_id="ops_reporter",
        status=event_status,
        decision=decision,
        started_at=started_at,
        finished_at=finished_at,
        input_refs=artifact_paths,
        artifact_paths=artifact_paths,
        artifacts_dir=artifacts_dir,
        failure_reason=first_text(status.get("errors") if isinstance(status.get("errors"), list) else []),
        next_action=next_action,
        metrics={"automation_status": automation_status},
        discord_channel="ops_progress_channel",
        message_type="run_status" if event_status == "ok" else "blocker",
    )


def step_group_event(
    *,
    run_id: str,
    run_date: str,
    agent_id: str,
    steps: list[dict[str, Any] | None],
    input_refs: list[str | Path],
    artifact_paths: list[str | Path],
    fallback_started_at: str,
    fallback_finished_at: str,
    artifacts_dir: Path,
    missing_status: tuple[str, str],
    missing_reason: str | None,
    next_action: str | None,
) -> dict[str, Any]:
    present_steps = [step for step in steps if isinstance(step, dict)]
    if not present_steps:
        event_status, decision = missing_status
        failure_reason = missing_reason
        started_at = fallback_started_at
        finished_at = fallback_finished_at
    else:
        event_status, decision = combined_step_status(present_steps)
        failure_reason = first_failure_message(present_steps)
        started_at = str(present_steps[0].get("started_at") or fallback_started_at)
        finished_at = str(present_steps[-1].get("finished_at") or fallback_finished_at)
        if event_status in {"ok", "warning"}:
            failure_reason = None
    return make_event(
        run_id=run_id,
        run_date=run_date,
        agent_id=agent_id,
        status=event_status,
        decision=decision,
        started_at=started_at,
        finished_at=finished_at,
        input_refs=input_refs,
        artifact_paths=artifact_paths,
        artifacts_dir=artifacts_dir,
        failure_reason=failure_reason,
        next_action=None if event_status == "ok" else next_action,
        metrics={
            "steps": [
                {
                    "name": step.get("name"),
                    "status": step.get("status"),
                    "exit_code": step.get("exit_code"),
                    "message": step.get("message"),
                }
                for step in present_steps
            ]
        },
    )


def make_event(
    *,
    run_id: str,
    run_date: str,
    agent_id: str,
    status: str,
    decision: str,
    started_at: str,
    finished_at: str,
    input_refs: list[str | Path],
    artifact_paths: list[str | Path],
    artifacts_dir: Path,
    failure_reason: str | None = None,
    next_action: str | None = None,
    metrics: dict[str, Any] | None = None,
    discord_channel: str | None = None,
    message_type: str | None = None,
) -> dict[str, Any]:
    return build_event(
        run_id=run_id,
        run_date=run_date,
        agent_id=agent_id,
        status=status,
        decision=decision,
        started_at=started_at,
        finished_at=finished_at,
        input_refs=[safe_ref(item, artifacts_dir) for item in input_refs],
        artifact_paths=[safe_ref(item, artifacts_dir) for item in artifact_paths],
        failure_reason=failure_reason,
        next_action=next_action,
        metrics=metrics or {},
        discord_channel=discord_channel,
        message_type=message_type,
    )


def combined_step_status(steps: list[dict[str, Any]]) -> tuple[str, str]:
    statuses = {str(step.get("status") or "").upper() for step in steps}
    if statuses & FAILED_STATUSES:
        return "failed", "stop"
    if statuses and statuses <= SKIPPED_STATUSES:
        return "skipped", "not_applicable"
    if statuses & WARNING_STATUSES or statuses & SKIPPED_STATUSES:
        return "warning", "partial"
    return "ok", "pass"


def automation_to_event_status(status: str) -> tuple[str, str]:
    if status == "OK":
        return "ok", "pass"
    if status == "SKIPPED":
        return "skipped", "not_applicable"
    return "failed", "stop"


def upstream_missing_status(
    automation_status: str,
    step_map: dict[str, dict[str, Any]],
    expected_step: str,
) -> tuple[str, str]:
    if automation_status == "SKIPPED":
        return "skipped", "not_applicable"
    if expected_step not in step_map:
        return "blocked", "stop"
    return "skipped", "not_applicable"


def metadata_paths(metadata: dict[str, Any], artifacts_dir: Path, keys: list[str]) -> list[str | Path]:
    paths: list[str | Path] = []
    for key in keys:
        value = metadata.get(key)
        if isinstance(value, str) and value:
            paths.append(value)
    return unique_refs(paths, artifacts_dir)


def dataset_artifacts(metadata: dict[str, Any], artifacts_dir: Path) -> list[str | Path]:
    freshness = metadata.get("data_freshness") if isinstance(metadata.get("data_freshness"), dict) else {}
    datasets = freshness.get("datasets") if isinstance(freshness.get("datasets"), dict) else {}
    paths = []
    for info in datasets.values():
        if isinstance(info, dict) and isinstance(info.get("path"), str):
            paths.append(info["path"])
    return unique_refs(paths, artifacts_dir)


def unique_refs(paths: list[str | Path], artifacts_dir: Path) -> list[str]:
    seen = set()
    result = []
    for path in paths:
        ref = safe_ref(path, artifacts_dir)
        if ref not in seen:
            seen.add(ref)
            result.append(ref)
    return result


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


def first_failure_message(steps: list[dict[str, Any]]) -> str | None:
    for step in steps:
        status = str(step.get("status") or "").upper()
        if status in FAILED_STATUSES | WARNING_STATUSES | SKIPPED_STATUSES and step.get("message"):
            return str(step.get("message"))
    return None


def first_text(values: list[Any]) -> str | None:
    for value in values:
        if value:
            return str(value)
    return None


def harness_next_action(event_status: str) -> str | None:
    if event_status == "ok":
        return "continue to daily publish gate and external review branch"
    if event_status == "skipped":
        return "record skipped run; wait for next eligible trading day"
    return "stop publish; repair failing daily step before retry"


def write_rollup(artifacts_dir: Path, run_date: str, run_id: str, rollup: dict[str, Any]) -> None:
    output = artifacts_dir / "harness_status" / run_date / run_id / "rollup.json"
    latest = artifacts_dir / "harness_status" / run_date / "latest_rollup.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(rollup, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    output.write_text(payload, encoding="utf-8")
    latest.write_text(payload, encoding="utf-8")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
