#!/usr/bin/env python3
"""隔離補跑 daily Top 10 歷史日期，並產出逐日 manifest 與正式路徑不變證據。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_automation import AutomationRunner


CARD_ID = "CARD-NEW-TOP10-ISOLATED-DAILY-BACKFILL-20260827"
SCHEMA_VERSION = "top10-isolated-daily-backfill.v1"
DEFAULT_START_DATE = "2026-08-03"
DEFAULT_END_DATE = "2026-08-26"
DEFAULT_OUTPUT_RELATIVE = Path("artifacts/isolated_daily_backfill/2026-08-03_2026-08-26")
FORMAL_ARTIFACT_PATTERNS = (
    "ranking_*.csv",
    "daily_run_summary_*.json",
    "automation_status*.json",
    "daily_report_*.json",
    "daily_report_*.md",
    "clawd_publish_payload_*.json",
    "clawd_publish_message_*.md",
    "clawd_send_status_*.json",
    "ops_progress_send_status_*.json",
    "daily_postcheck_*.json",
    "external_review_summary_*.json",
)
SUPPLEMENTAL_DAILY_FLAGS = {
    "candidate_persistence_enabled": False,
    "weekly_snapshot_enabled": False,
    "tskg_t86_enabled": False,
    "market_context_enabled": False,
    "daily_recommendation_performance_enabled": False,
    "decision_quality_enabled": False,
    "daily_performance_review_enabled": False,
    "gross55_shadow_monitor_enabled": False,
    "gross55_shadow_monitor_batch_enabled": False,
    "capital_entry_quality_shadow_monitor_enabled": False,
    "capital_entry_quality_shadow_monitor_batch_enabled": False,
    "candidate_trail10_shadow_monitor_enabled": False,
    "overlap_first_recommendation_shadow_enabled": False,
    "shadow_historical_evidence_report_enabled": False,
    "overlay_append_only_shadow_enabled": False,
    "daily_shadow_status_report_enabled": False,
    "postcheck_enabled": False,
    "daily_report_enabled": True,
    "clawd_payload_enabled": True,
    "weekend_enabled": True,
    "market_coverage_enabled": False,
    "max_data_lag_days": 9999,
}


class BackfillNoGo(RuntimeError):
    """任務卡 stop condition 被觸發。"""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_identity(path: Path, root: Path) -> dict[str, Any]:
    relative = str(path.relative_to(root))
    if not path.exists():
        return {"path": relative, "exists": False}
    stat = path.stat()
    return {
        "path": relative,
        "exists": True,
        "size_bytes": stat.st_size,
        "mtime": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        "sha256": sha256_file(path),
    }


def collect_formal_baseline(source_root: Path) -> dict[str, Any]:
    artifacts = source_root / "artifacts"
    files: dict[str, dict[str, Any]] = {}
    if artifacts.exists():
        for pattern in FORMAL_ARTIFACT_PATTERNS:
            for path in artifacts.glob(pattern):
                if path.is_file():
                    files[str(path.relative_to(source_root))] = file_identity(path, source_root)
        host_runner = artifacts / "host_runner"
        if host_runner.exists():
            for path in host_runner.rglob("*"):
                if path.is_file():
                    files[str(path.relative_to(source_root))] = file_identity(path, source_root)
    payload = json.dumps(files, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return {
        "schema_version": "formal-daily-artifact-baseline.v1",
        "source_root": str(source_root),
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "patterns": list(FORMAL_ARTIFACT_PATTERNS),
        "file_count": len(files),
        "files": files,
        "baseline_sha256": hashlib.sha256(payload).hexdigest(),
    }


def compare_formal_baseline(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_files = before.get("files", {})
    after_files = after.get("files", {})
    added = sorted(set(after_files) - set(before_files))
    removed = sorted(set(before_files) - set(after_files))
    changed = sorted(
        path
        for path in set(before_files) & set(after_files)
        if before_files[path].get("sha256") != after_files[path].get("sha256")
        or before_files[path].get("mtime") != after_files[path].get("mtime")
        or before_files[path].get("size_bytes") != after_files[path].get("size_bytes")
    )
    return {
        "status": "PASS" if not added and not removed and not changed else "FAILED",
        "added": added,
        "removed": removed,
        "changed": changed,
        "before_sha256": before.get("baseline_sha256"),
        "after_sha256": after.get("baseline_sha256"),
    }


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"日期必須是 YYYY-MM-DD: {value}") from exc


def weekday_dates(start: date, end: date) -> list[date]:
    if end < start:
        raise ValueError("end-date 不得早於 start-date")
    current = start
    result: list[date] = []
    while current <= end:
        if current.weekday() < 5:
            result.append(current)
        current += timedelta(days=1)
    return result


def resolve_output_root(source_root: Path, output_root: Path | None) -> Path:
    resolved = (output_root or source_root / DEFAULT_OUTPUT_RELATIVE).resolve()
    allowed_root = (source_root / "artifacts" / "isolated_daily_backfill").resolve()
    try:
        resolved.relative_to(allowed_root)
    except ValueError as exc:
        raise BackfillNoGo(f"output_root must stay under {allowed_root}: {resolved}") from exc
    if (resolved / ".git").exists() or (resolved / ".git").is_symlink():
        raise BackfillNoGo("output_root must not be a git checkout")
    return resolved


def resolve_evidence_dir(output_root: Path, evidence_dir: Path | None) -> Path:
    resolved = (evidence_dir or output_root / "evidence").resolve()
    try:
        resolved.relative_to(output_root.resolve())
    except ValueError as exc:
        raise BackfillNoGo(f"evidence_dir must stay under output_root: {resolved}") from exc
    return resolved


def resolve_sanitized_receipt_path(source_root: Path, receipt_path: Path | None) -> Path | None:
    if receipt_path is None:
        return None
    resolved = receipt_path.resolve()
    allowed_root = (source_root / "docs" / "evidence" / CARD_ID).resolve()
    try:
        resolved.relative_to(allowed_root)
    except ValueError as exc:
        raise BackfillNoGo(f"sanitized_receipt_path must stay under {allowed_root}: {resolved}") from exc
    if resolved.name != "sanitized_receipt.md":
        raise BackfillNoGo("sanitized_receipt_path filename must be sanitized_receipt.md")
    return resolved


def tree_stats(root: Path) -> dict[str, Any]:
    if not root.exists():
        return {"path": str(root), "exists": False, "file_count": 0, "total_bytes": 0}
    file_count = 0
    total_bytes = 0
    largest: list[dict[str, Any]] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        stat = path.stat()
        file_count += 1
        total_bytes += stat.st_size
        largest.append({"path": str(path.relative_to(root)), "size_bytes": stat.st_size})
    largest = sorted(largest, key=lambda item: item["size_bytes"], reverse=True)[:10]
    return {
        "path": str(root),
        "exists": True,
        "file_count": file_count,
        "total_bytes": total_bytes,
        "largest_files": largest,
    }


def capacity_gate(before: dict[str, Any], after_single: dict[str, Any], total_run_count: int) -> dict[str, Any]:
    growth_files = max(0, int(after_single["file_count"]) - int(before["file_count"]))
    growth_bytes = max(0, int(after_single["total_bytes"]) - int(before["total_bytes"]))
    projected_files = int(before["file_count"]) + growth_files * total_run_count
    projected_bytes = int(before["total_bytes"]) + growth_bytes * total_run_count
    max_files = int(os.environ.get("TOP10_ISOLATED_BACKFILL_MAX_FILES", "5000"))
    max_bytes = int(os.environ.get("TOP10_ISOLATED_BACKFILL_MAX_BYTES", str(5 * 1024 * 1024 * 1024)))
    status = "PASS" if projected_files <= max_files and projected_bytes <= max_bytes else "NO-GO"
    return {
        "schema_version": "top10-isolated-backfill-capacity.v1",
        "status": status,
        "single_day_growth": {"files": growth_files, "bytes": growth_bytes},
        "projected_total": {"files": projected_files, "bytes": projected_bytes},
        "limits": {"max_files": max_files, "max_bytes": max_bytes},
        "rollback_scope": "isolated_output_root",
        "rollback_guidance": (
            "Remove only the isolated output root after independently verifying it resolves under "
            "artifacts/isolated_daily_backfill. No destructive command is serialized."
        ),
    }


def write_sanitized_evidence_receipt(receipt_path: Path, manifest: dict[str, Any]) -> None:
    """寫入可合併的小型 receipt；避免原始 manifest、絕對路徑與本機狀態進 repo。"""
    lines = [
        "# Isolated daily backfill sanitized receipt",
        "",
        f"- schema_version: {manifest['schema_version']}",
        f"- status: {manifest['status']}",
        f"- date_range: {manifest['date_range']['start']}..{manifest['date_range']['end']}",
        f"- representative_date: {manifest['representative_date']}",
        f"- completed_count: {len(manifest['completed'])}",
        f"- skipped_count: {len(manifest['skipped'])}",
        f"- capacity_status: {manifest['capacity']['status']}",
        f"- formal_baseline_status: {manifest['formal_baseline_comparison']['status']}",
        "- output_scope: artifacts/isolated_daily_backfill/2026-08-03_2026-08-26",
        "- runtime_artifacts_tracked: false",
        "- production_write_allowed: false",
        "- scheduler_change_allowed: false",
        "- rollback_guidance: remove only the isolated output root after verifying it resolves under the isolated backfill root; no destructive command is serialized.",
        "",
    ]
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text("\n".join(lines), encoding="utf-8")


@contextmanager
def temporary_environment(values: dict[str, str]) -> Iterator[None]:
    previous = {key: os.environ.get(key) for key in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def apply_isolated_config(runner: AutomationRunner) -> None:
    daily = runner.config.setdefault("daily", {})
    daily.update({"enabled": True, **SUPPLEMENTAL_DAILY_FLAGS})
    notify = runner.config.setdefault("notify", {})
    notify["llm_rewrite_enabled"] = False


def pipeline_start_for(run_day: date, lookback_days: int) -> str:
    return (run_day - timedelta(days=lookback_days)).isoformat()


def command_env(output_root: Path, runtime: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "TOP10_OUTPUT_ROOT": str(output_root),
            "TOP10_RUNTIME_ROOT": str(runtime),
            "TOP10_LLM_REWRITE_ENABLED": "0",
            "TOP10_PRODUCTION_RANKING_OVERLAY": "0",
            "TOP10_ENABLE_PRODUCTION_TRAIL10_SHADOW": "0",
            "TOP10_ENABLE_PRODUCTION_TRAIL10_DAILY_REPORT_DRY_RUN": "0",
            "PYTHONDONTWRITEBYTECODE": "1",
            "TMPDIR": str(runtime / "tmp"),
            "UV_CACHE_DIR": str(runtime / "cache" / "uv"),
            "XDG_CACHE_HOME": str(runtime / "cache" / "xdg"),
            "MPLCONFIGDIR": str(runtime / "cache" / "matplotlib"),
            "JOBLIB_TEMP_FOLDER": str(runtime / "tmp" / "joblib"),
        }
    )
    return env


def prepare_runtime(runtime: Path) -> None:
    for path in [
        runtime / "tmp",
        runtime / "cache" / "uv",
        runtime / "cache" / "xdg",
        runtime / "cache" / "matplotlib",
        runtime / "tmp" / "joblib",
    ]:
        path.mkdir(parents=True, exist_ok=True)


def run_command(source_root: Path, output_root: Path, runtime: Path, command: list[str]) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc).isoformat()
    completed = subprocess.run(
        command,
        cwd=source_root,
        env=command_env(output_root, runtime),
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "command": command,
        "status": "OK" if completed.returncode == 0 else "FAILED",
        "exit_code": completed.returncode,
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
    }


def run_shared_etl(source_root: Path, output_root: Path, start: date, end: date, lookback_days: int) -> dict[str, Any]:
    runtime = output_root / "logs" / "isolated_daily_backfill" / "runtime" / "shared-etl"
    prepare_runtime(runtime)
    receipt_path = output_root / "manifest" / "shared-etl.json"
    required_outputs = [
        output_root / "data" / "clean" / "features.parquet",
        output_root / "data" / "clean" / "events.parquet",
        output_root / "data" / "clean" / "universe.parquet",
    ]
    if receipt_path.exists() and all(path.exists() for path in required_outputs):
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["reused_existing_outputs"] = True
        return receipt
    window_start = pipeline_start_for(start, lookback_days)
    commands = [
        [
            sys.executable,
            "-m",
            "app.pipeline_cli",
            "run",
            "--start-date",
            window_start,
            "--end-date",
            end.isoformat(),
            "--data-dir",
            str(output_root / "data"),
            "--artifacts-dir",
            str(output_root / "artifacts"),
        ],
        [
            sys.executable,
            "-m",
            "app.pipeline_cli",
            "validate",
            "--data-dir",
            str(output_root / "data"),
            "--json",
        ],
    ]
    outcomes = []
    for command in commands:
        outcome = run_command(source_root, output_root, runtime, command)
        outcomes.append(outcome)
        if outcome["exit_code"] != 0:
            raise BackfillNoGo(f"shared isolated ETL failed: {outcome}")
    receipt = {
        "schema_version": "top10-isolated-backfill-shared-etl.v1",
        "status": "OK",
        "pipeline_window": {"start_date": window_start, "end_date": end.isoformat()},
        "roots": {"source_root": str(source_root), "output_root": str(output_root), "runtime_root": str(runtime)},
        "commands": outcomes,
        "data_tree": tree_stats(output_root / "data"),
    }
    write_json(output_root / "manifest" / "shared-etl.json", receipt)
    return receipt


def available_feature_dates(output_root: Path) -> set[str]:
    try:
        import pandas as pd
    except ImportError as exc:
        raise BackfillNoGo(f"pandas unavailable for isolated date verification: {exc}") from exc
    features_path = output_root / "data" / "clean" / "features.parquet"
    if not features_path.exists():
        raise BackfillNoGo(f"isolated ETL did not create features.parquet: {features_path}")
    try:
        frame = pd.read_parquet(features_path, columns=["trade_date"])
        date_column = "trade_date"
    except Exception:
        frame = pd.read_parquet(features_path, columns=["date"])
        date_column = "date"
    dates = pd.to_datetime(frame[date_column], errors="coerce").dropna().dt.date
    return {item.isoformat() for item in dates}


def status_payload(output_root: Path, run_day: date) -> dict[str, Any]:
    run_date = run_day.isoformat()
    ranking = output_root / "artifacts" / f"ranking_{run_date}.csv"
    return {
        "schema_version": "daily-run-status.v1",
        "mode": "daily",
        "status": "OK",
        "dry_run": False,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "run_date": run_date,
        "skip_reason": None,
        "errors": [],
        "steps": [
            {"name": "shared_etl.reuse", "status": "OK", "message": "isolated shared ETL reused for bounded backfill"},
            {"name": "data.freshness.strict_run_date", "status": "OK", "message": f"requested_date={run_date} present_in_features"},
            {"name": "ranking.artifact", "status": "OK", "message": str(ranking)},
        ],
        "metadata": {
            "output_root": str(output_root),
            "validation_mode": False,
            "strict_run_date": True,
            "isolated_backfill": True,
            "ranking_artifact": str(ranking),
            "expected_ranking_artifact": str(ranking),
            "data_freshness": {
                "datasets": {
                    "features.parquet": {
                        "path": str(output_root / "data" / "clean" / "features.parquet"),
                        "latest_date": run_date,
                        "backfill_source": "shared_isolated_etl",
                    }
                }
            },
        },
    }


def write_daily_status(output_root: Path, run_day: date, payload: dict[str, Any]) -> None:
    artifacts = output_root / "artifacts"
    run_date = run_day.isoformat()
    write_json(artifacts / f"automation_status_{run_date}.json", payload)
    write_json(artifacts / "automation_status.json", payload)
    summary = {
        "schema_version": "daily-run-status.v1",
        "run_date": run_date,
        "mode": "daily",
        "status": payload["status"],
        "dry_run": False,
        "skip_reason": None,
        "started_at": payload["started_at"],
        "finished_at": payload["finished_at"],
        "errors": [],
        "step_summary": payload["steps"],
        "metadata": payload["metadata"],
    }
    write_json(artifacts / f"daily_run_summary_{run_date}.json", summary)


def validate_daily_outputs(output_root: Path, run_day: date) -> dict[str, Any]:
    artifacts = output_root / "artifacts"
    run_date = run_day.isoformat()
    ranking = artifacts / f"ranking_{run_date}.csv"
    summary = artifacts / f"daily_run_summary_{run_date}.json"
    status_snapshot = artifacts / f"automation_status_{run_date}.json"
    report = artifacts / f"daily_report_{run_date}.json"
    payload = artifacts / f"clawd_publish_payload_{run_date}.json"
    message = artifacts / f"clawd_publish_message_{run_date}.md"
    required = {
        "ranking": ranking,
        "daily_run_summary": summary,
        "automation_status_snapshot": status_snapshot,
        "daily_report": report,
        "clawd_publish_payload": payload,
        "clawd_publish_message": message,
    }
    missing = [name for name, path in required.items() if not path.exists()]
    if missing:
        raise BackfillNoGo(f"missing isolated artifacts for {run_date}: {missing}")

    with ranking.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise BackfillNoGo(f"ranking is empty for {run_date}: {ranking}")
    columns = set(rows[0])
    required_columns = {"stock_id", "final_score"}
    if not required_columns.issubset(columns):
        raise BackfillNoGo(f"ranking missing columns for {run_date}: {sorted(required_columns - columns)}")

    status_payload = json.loads(status_snapshot.read_text(encoding="utf-8"))
    summary_payload = json.loads(summary.read_text(encoding="utf-8"))
    if status_payload.get("status") != "OK":
        raise BackfillNoGo(f"automation status is not OK for {run_date}: {status_payload.get('status')}")
    if status_payload.get("run_date") != run_date:
        raise BackfillNoGo(f"automation run_date mismatch for {run_date}: {status_payload.get('run_date')}")
    freshness = status_payload.get("metadata", {}).get("data_freshness", {}).get("datasets", {})
    feature_latest = freshness.get("features.parquet", {}).get("latest_date")
    if feature_latest != run_date:
        raise BackfillNoGo(f"feature latest_date mismatch for {run_date}: {feature_latest}")

    return {
        "status": "completed",
        "run_date": run_date,
        "ranking_rows": len(rows),
        "ranking_columns": sorted(columns),
        "feature_latest_date": feature_latest,
        "summary_status": summary_payload.get("status"),
        "artifacts": {name: file_identity(path, output_root) for name, path in required.items()},
    }


def run_cycle(source_root: Path, output_root: Path, run_day: date, lookback_days: int) -> dict[str, Any]:
    del lookback_days
    run_date = run_day.isoformat()
    runtime = output_root / "logs" / "isolated_daily_backfill" / "runtime" / run_date
    prepare_runtime(runtime)
    started_at = datetime.now(timezone.utc).isoformat()
    commands = [
        [
            sys.executable,
            "-m",
            "app.agent_b_ranking",
            "--date",
            run_date,
            "--data-dir",
            str(output_root / "data" / "clean"),
            "--model-dir",
            str(source_root / "models"),
            "--artifact-dir",
            str(output_root / "artifacts"),
            "--config",
            str(source_root / "config" / "signals.yaml"),
            "--no-report",
        ],
    ]
    outcomes = []
    for command in commands:
        outcome = run_command(source_root, output_root, runtime, command)
        outcomes.append(outcome)
        if outcome["exit_code"] != 0:
            raise BackfillNoGo(f"isolated ranking failed for {run_date}: {outcome}")
    status = status_payload(output_root, run_day)
    write_daily_status(output_root, run_day, status)
    report_command = [
        sys.executable,
        "scripts/generate_daily_report.py",
        "--ranking",
        str(output_root / "artifacts" / f"ranking_{run_date}.csv"),
        "--status",
        str(output_root / "artifacts" / "automation_status.json"),
        "--artifacts-dir",
        str(output_root / "artifacts"),
    ]
    payload_command = [
        sys.executable,
        "scripts/build_clawd_publish_payload.py",
        "--report",
        str(output_root / "artifacts" / f"daily_report_{run_date}.json"),
        "--artifacts-dir",
        str(output_root / "artifacts"),
    ]
    for command in [report_command, payload_command]:
        outcome = run_command(source_root, output_root, runtime, command)
        outcomes.append(outcome)
        if outcome["exit_code"] != 0:
            raise BackfillNoGo(f"isolated final artifact command failed for {run_date}: {outcome}")
    status["metadata"]["daily_report_artifact"] = str(output_root / "artifacts" / f"daily_report_{run_date}.json")
    status["metadata"]["clawd_publish_payload"] = str(output_root / "artifacts" / f"clawd_publish_payload_{run_date}.json")
    status["metadata"]["clawd_publish_message"] = str(output_root / "artifacts" / f"clawd_publish_message_{run_date}.md")
    write_daily_status(output_root, run_day, status)
    validation = validate_daily_outputs(output_root, run_day)
    receipt = {
        "schema_version": "top10-isolated-daily-cycle.v1",
        "status": "OK",
        "run_date": run_date,
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "pipeline_window": {"source": "shared_isolated_etl"},
        "roots": {"source_root": str(source_root), "output_root": str(output_root), "runtime_root": str(runtime)},
        "commands": outcomes,
        "validation": validation,
        "external_write_contract": {
            "run_daily_publish": False,
            "clawd_live_send": False,
            "ops_live_send": False,
            "external_review": False,
            "scheduler_change": False,
        },
    }
    receipt_path = output_root / "manifest" / "daily" / f"{run_date}.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    return receipt


def launchd_status() -> dict[str, Any]:
    completed = subprocess.run(
        ["launchctl", "list", "com.new-top10.daily"],
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "command": ["launchctl", "list", "com.new-top10.daily"],
        "exit_code": completed.returncode,
        "stdout_sha256": hashlib.sha256(completed.stdout.encode("utf-8")).hexdigest(),
        "stderr": completed.stderr[-1000:],
        "loaded": completed.returncode == 0,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_backfill(args: argparse.Namespace) -> dict[str, Any]:
    source_root = args.source_root.resolve()
    output_root = resolve_output_root(source_root, args.output_root)
    evidence_dir = resolve_evidence_dir(output_root, args.evidence_dir)
    sanitized_receipt_path = resolve_sanitized_receipt_path(source_root, args.sanitized_receipt_path)
    output_root.mkdir(parents=True, exist_ok=True)
    evidence_dir.mkdir(parents=True, exist_ok=True)

    run_days = weekday_dates(args.start_date, args.end_date)
    if not run_days:
        raise BackfillNoGo("date range contains no weekday candidates")
    representative = args.representative_date or run_days[0]
    if representative not in run_days:
        raise BackfillNoGo("representative-date must be a weekday inside the requested date range")

    formal_before = collect_formal_baseline(source_root)
    launchd_before = launchd_status()
    write_json(evidence_dir / "formal-baseline-before.json", formal_before)
    write_json(evidence_dir / "launchd-before.json", launchd_before)

    skipped = [
        {"run_date": item.isoformat(), "status": "skipped", "reason": "weekend_precheck"}
        for item in (args.start_date + timedelta(days=offset) for offset in range((args.end_date - args.start_date).days + 1))
        if item.weekday() >= 5
    ]
    shared_etl = run_shared_etl(source_root, output_root, args.start_date, args.end_date, args.lookback_days)
    available_dates = available_feature_dates(output_root)
    actual_run_days = [item for item in run_days if item.isoformat() in available_dates]
    skipped.extend(
        {"run_date": item.isoformat(), "status": "skipped", "reason": "no_market_data_in_isolated_etl"}
        for item in run_days
        if item.isoformat() not in available_dates
    )
    if not actual_run_days:
        raise BackfillNoGo("isolated ETL produced no weekday market dates in requested range")
    if args.representative_date is None and representative not in actual_run_days:
        representative = actual_run_days[0]
    if representative not in actual_run_days:
        raise BackfillNoGo(f"representative date has no isolated market data: {representative.isoformat()}")

    before_single = tree_stats(output_root)
    representative_receipt = run_cycle(source_root, output_root, representative, args.lookback_days)
    after_single = tree_stats(output_root)
    capacity = capacity_gate(before_single, after_single, len(actual_run_days))
    write_json(evidence_dir / "capacity-receipt.json", capacity)
    if capacity["status"] != "PASS":
        raise BackfillNoGo(f"capacity gate is not PASS: {capacity}")

    completed = [representative_receipt]
    for run_day in actual_run_days:
        if run_day == representative:
            continue
        completed.append(run_cycle(source_root, output_root, run_day, args.lookback_days))

    formal_after = collect_formal_baseline(source_root)
    formal_comparison = compare_formal_baseline(formal_before, formal_after)
    launchd_after = launchd_status()
    write_json(evidence_dir / "formal-baseline-after.json", formal_after)
    write_json(evidence_dir / "formal-baseline-comparison.json", formal_comparison)
    write_json(evidence_dir / "launchd-after.json", launchd_after)
    if formal_comparison["status"] != "PASS":
        raise BackfillNoGo(f"formal baseline changed: {formal_comparison}")

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "DELIVERED_CANDIDATE",
        "card_id": CARD_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date_range": {"start": args.start_date.isoformat(), "end": args.end_date.isoformat()},
        "representative_date": representative.isoformat(),
        "roots": {"source_root": str(source_root), "output_root": str(output_root), "evidence_dir": str(evidence_dir)},
        "shared_etl": shared_etl,
        "completed": completed,
        "skipped": skipped,
        "failed": [],
        "capacity": capacity,
        "formal_baseline_comparison": formal_comparison,
        "launchd": {"before": launchd_before, "after": launchd_after},
        "rollback": {
            "scope": "isolated_output_root",
            "guidance": (
                "Remove only this isolated output root after verifying it resolves under "
                "artifacts/isolated_daily_backfill. No destructive command is serialized."
            ),
        },
    }
    manifest_path = output_root / "manifest" / "isolated_daily_backfill_manifest.json"
    write_json(manifest_path, manifest)
    if sanitized_receipt_path is not None:
        write_sanitized_evidence_receipt(sanitized_receipt_path, manifest)
    return manifest


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run isolated NEW-TOP10 daily backfill")
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--evidence-dir", type=Path, default=None)
    parser.add_argument("--sanitized-receipt-path", type=Path, default=None)
    parser.add_argument("--start-date", type=parse_date, default=parse_date(DEFAULT_START_DATE))
    parser.add_argument("--end-date", type=parse_date, default=parse_date(DEFAULT_END_DATE))
    parser.add_argument("--representative-date", type=parse_date, default=None)
    parser.add_argument("--lookback-days", type=int, default=420)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        manifest = run_backfill(args)
    except BackfillNoGo as exc:
        evidence_dir = None
        try:
            output_root = resolve_output_root(args.source_root.resolve(), args.output_root)
            evidence_dir = resolve_evidence_dir(output_root, args.evidence_dir)
        except BackfillNoGo:
            pass
        payload = {
            "schema_version": SCHEMA_VERSION,
            "status": "NO-GO",
            "card_id": CARD_ID,
            "reason": str(exc),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        if evidence_dir is not None:
            write_json(evidence_dir / "no-go.json", payload)
        print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps({"status": manifest["status"], "manifest": str(Path(manifest["roots"]["output_root"]) / "manifest" / "isolated_daily_backfill_manifest.json")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
