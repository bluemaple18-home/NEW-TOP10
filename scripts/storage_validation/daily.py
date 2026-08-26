#!/usr/bin/env python3
"""Digest-pinned daily storage validation entrypoint.

此入口只負責把 source/output/runtime roots 接到 canonical AutomationRunner；
每日流程本身仍由 app.automation.daily_orchestrator 的 production order 執行。
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any


ENTRYPOINT_SCHEMA_VERSION = "top10-daily-storage-validation-cycle.v1"
CANONICAL_ORCHESTRATOR = "app.automation.daily_orchestrator"
SOURCE_IDENTITY_FILES = (
    "config/automation.yaml",
    "config/signals.yaml",
    "requirements.txt",
    "scripts/run_automation.py",
    "app/automation/daily_orchestrator.py",
    "app/automation/execution.py",
    "app/agent_b_ranking.py",
    "app/pipeline_cli.py",
    "scripts/generate_daily_report.py",
    "scripts/build_clawd_publish_payload.py",
    "models/latest_lgbm.pkl",
    "data/reference/tradable_universe.csv",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_identity(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.exists():
        return {"path": relative, "exists": False}
    stat = path.stat()
    return {
        "path": relative,
        "exists": True,
        "size_bytes": stat.st_size,
        "sha256": _sha256(path),
    }


def source_identity(source_root: Path) -> dict[str, Any]:
    files = {
        relative: identity
        for relative in SOURCE_IDENTITY_FILES
        if (identity := _file_identity(source_root, relative))["exists"]
    }
    digest_payload = json.dumps(files, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return {
        "root": str(source_root),
        "files": files,
        "identity_sha256": hashlib.sha256(digest_payload).hexdigest(),
    }


def _artifact_identity(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False}
    stat = path.stat()
    return {
        "path": str(path),
        "exists": True,
        "size_bytes": stat.st_size,
        "sha256": _sha256(path),
        "mtime": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
    }


def _reject_git_scope(output_root: Path) -> None:
    git_entry = output_root / ".git"
    if git_entry.exists() or git_entry.is_symlink():
        raise RuntimeError("daily storage validation output root must not be a git checkout")


def _load_source_runner(source_root: Path) -> ModuleType:
    current_project = Path(__file__).resolve().parents[2]
    if source_root == current_project:
        from scripts import run_automation

        return run_automation

    module_path = source_root / "scripts" / "run_automation.py"
    if not module_path.is_file():
        raise FileNotFoundError(f"canonical runner missing: {module_path}")
    sys.path.insert(0, str(source_root))
    module_name = "_top10_validation_run_automation_" + hashlib.sha256(
        str(module_path).encode("utf-8")
    ).hexdigest()[:12]
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load canonical runner: {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def run_validation_cycle(
    *,
    source_root: Path | str,
    output_root: Path | str,
    run_date: str,
    cycle_id: str,
    runtime_root: Path | str | None = None,
    dry_run: bool = False,
) -> Path:
    source = Path(source_root).resolve()
    output = Path(output_root).resolve()
    runtime = Path(runtime_root).resolve() if runtime_root is not None else output / "logs" / "storage_safety" / "runtime" / "daily"
    if not source.is_dir():
        raise FileNotFoundError(f"source_root missing: {source}")
    output.mkdir(parents=True, exist_ok=True)
    runtime.mkdir(parents=True, exist_ok=True)
    _reject_git_scope(output)

    started_at = datetime.now(timezone.utc).isoformat()
    before = source_identity(source)
    automation = _load_source_runner(source)
    runner = automation.AutomationRunner(
        mode="daily",
        dry_run=dry_run,
        trigger="manual",
        resource_profile="standard",
        run_date=run_date,
        source_root=source,
        output_root=output,
        runtime_root=runtime,
        validation_mode=True,
    )
    exit_code = runner.run()
    after = source_identity(source)
    source_unchanged = before["identity_sha256"] == after["identity_sha256"]
    status = "OK" if exit_code == 0 and source_unchanged else "FAILED"
    if not source_unchanged:
        runner.status.errors.append("source identity changed during validation cycle")

    latest_date = runner._latest_feature_date()
    artifacts = {
        "ranking": _artifact_identity(output / "artifacts" / f"ranking_{latest_date}.csv"),
        "daily_report": _artifact_identity(output / "artifacts" / f"daily_report_{latest_date}.json"),
        "clawd_publish_payload": _artifact_identity(output / "artifacts" / f"clawd_publish_payload_{latest_date}.json"),
        "clawd_publish_message": _artifact_identity(output / "artifacts" / f"clawd_publish_message_{latest_date}.md"),
        "automation_status": _artifact_identity(runner._status_output_path()),
    }
    receipt = {
        "schema_version": ENTRYPOINT_SCHEMA_VERSION,
        "status": status,
        "child_exit_code": exit_code,
        "cycle_id": cycle_id,
        "run_date": run_date,
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "canonical_orchestrator": CANONICAL_ORCHESTRATOR,
        "roots": {
            "source_root": str(source),
            "output_root": str(output),
            "runtime_root": str(runtime),
        },
        "sandbox_output_roots": {
            "artifacts": str(output / "artifacts"),
            "logs": str(output / "logs"),
            "data": str(output / "data"),
            "runtime": str(runtime),
        },
        "source_identity": before,
        "source_identity_after": after,
        "source_identity_unchanged": source_unchanged,
        "external_send_contract": {
            "validation_mode": True,
            "clawd_send_enabled": False,
            "ops_send_enabled": False,
            "discord_send_enabled": False,
            "llm_rewrite_enabled": False,
            "blocked_scripts": [
                "scripts/run_daily_publish.sh",
                "scripts/send_daily_ops_report.py",
            ],
        },
        "orchestrator_call_sequence": [step.name for step in runner.status.steps],
        "commands": [
            {
                "name": step.name,
                "status": step.status,
                "command": step.command,
                "exit_code": step.exit_code,
            }
            for step in runner.status.steps
            if step.command is not None
        ],
        "artifacts": artifacts,
        "automation_status": as_status_payload(runner.status),
    }
    receipt_path = runtime / f"daily_validation_{cycle_id}.json"
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    if status != "OK":
        raise RuntimeError(f"daily validation cycle failed; receipt={receipt_path}")
    return receipt_path


def as_status_payload(status: Any) -> dict[str, Any]:
    return {
        "status": status.status,
        "run_date": status.run_date,
        "errors": list(status.errors),
        "metadata": dict(status.metadata),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TOP10 daily storage validation trusted entrypoint")
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=Path.cwd())
    parser.add_argument("--runtime-root", type=Path, default=None)
    parser.add_argument("--run-date", required=True)
    parser.add_argument("--cycle-id", required=True)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        receipt_path = run_validation_cycle(
            source_root=args.source_root,
            output_root=args.output_root,
            runtime_root=args.runtime_root,
            run_date=args.run_date,
            cycle_id=args.cycle_id,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps({"status": "OK", "cycle_id": args.cycle_id, "receipt_path": str(receipt_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    raise SystemExit(main())
