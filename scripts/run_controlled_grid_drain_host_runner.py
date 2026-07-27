#!/usr/bin/env python3
"""重建 controlled-grid-drain 連動 artifacts。

這個 host runner 只負責把現有 run_history / map / weekend artifacts 串回
gates、rollup 與 fog map；不啟動 replay、不訓練模型、不改 production ranking。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_IMPACT = "NO_PRODUCTION_CHANGE"
SCHEMA_VERSION = "controlled-grid-drain-host-runner.v1"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def tail(text: str, limit: int = 6000) -> str:
    return text[-limit:]


def run_step(name: str, command: list[str]) -> dict[str, Any]:
    started_at = now_utc()
    proc = subprocess.run(command, cwd=PROJECT_ROOT, text=True, capture_output=True, check=False)
    return {
        "name": name,
        "command": command,
        "started_at": started_at,
        "finished_at": now_utc(),
        "returncode": proc.returncode,
        "stdout_tail": tail(proc.stdout),
        "stderr_tail": tail(proc.stderr),
        "status": "OK" if proc.returncode == 0 else "FAILED",
    }


def inventory_path(date: str) -> Path:
    return PROJECT_ROOT / "artifacts" / "weekend_training" / f"weekend_universe_inventory_{date}.json"


def gates_path(date: str) -> Path:
    return PROJECT_ROOT / "artifacts" / "weekend_training" / f"controlled_grid_drain_gates_{date}.json"


def status_path(date: str) -> Path:
    return PROJECT_ROOT / "artifacts" / "host_runner" / date / f"controlled_grid_drain_host_runner_status_{date}.json"


def summary_path(date: str) -> Path:
    return PROJECT_ROOT / "artifacts" / "host_runner" / date / f"controlled_grid_drain_host_runner_summary_{date}.json"


def build_gates(date: str, status: str, steps: list[dict[str, Any]]) -> dict[str, Any]:
    inventory = read_json(inventory_path(date))
    inv_summary = inventory.get("summary") if isinstance(inventory.get("summary"), dict) else {}
    representative_count = int(inv_summary.get("representative_required_count") or 0)
    payload = {
        "schema_version": "controlled-grid-drain-gates.v1",
        "generated_at": now_utc(),
        "date": date,
        "status": status,
        "controlled_grid_drain_ready": status == "OK",
        "baseline_alias": "artifacts/backtest/production_baseline_harness_medium_window",
        "target_production_path_created": False,
        "production_impact": PRODUCTION_IMPACT,
        "runner_mode": "linkage_only",
        "notes": [
            "Rebuilds linkage artifacts only.",
            "Does not execute replay, train model, change production ranking, or promote results.",
        ],
        "gates": {
            "queue_contract": {
                "inventory_summary": {
                    "baseline_blocker_cleared": status == "OK",
                    "no_replay_required_after_alias": representative_count == 0,
                    "full_universe_total": inv_summary.get("full_universe_total"),
                    "current_processed_count": inv_summary.get("current_processed_count"),
                    "current_remaining_count": inv_summary.get("current_remaining_count"),
                },
                "queue_summary": {
                    "representative_replay_count": representative_count,
                    "queue_count": representative_count,
                },
            },
            "micro_batch": {"status": "NOT_RUN_LINKAGE_ONLY"},
            "unattended_resume": {"status": "NOT_RUN_LINKAGE_ONLY"},
        },
        "steps": steps,
    }
    write_json(gates_path(date), payload)
    return payload


def build_failed_gates_without_inventory(date: str, steps: list[dict[str, Any]]) -> dict[str, Any]:
    payload = {
        "schema_version": "controlled-grid-drain-gates.v1",
        "generated_at": now_utc(),
        "date": date,
        "status": "FAILED",
        "controlled_grid_drain_ready": False,
        "baseline_alias": "artifacts/backtest/production_baseline_harness_medium_window",
        "target_production_path_created": False,
        "production_impact": PRODUCTION_IMPACT,
        "runner_mode": "linkage_only",
        "notes": [
            "Pre-inventory research map refresh failed; inventory was not rebuilt.",
            "Does not execute replay, train model, change production ranking, or promote results.",
        ],
        "gates": {
            "queue_contract": {
                "inventory_summary": {},
                "queue_summary": {"representative_replay_count": None, "queue_count": None},
            },
            "micro_batch": {"status": "NOT_RUN_LINKAGE_ONLY"},
            "unattended_resume": {"status": "NOT_RUN_LINKAGE_ONLY"},
        },
        "steps": steps,
    }
    write_json(gates_path(date), payload)
    return payload


def pre_inventory_refresh_commands(py: str, date: str) -> list[tuple[str, list[str]]]:
    return [
        ("build_research_progress_before_inventory", [py, "scripts/build_research_campaign_progress.py", "--date", date]),
        ("build_fog_map_before_inventory", [py, "scripts/build_research_fog_map.py", "--date", date]),
        ("verify_fog_map_before_inventory", [py, "scripts/verify_research_fog_map.py", "--date", date]),
    ]


def inventory_commands(py: str, date: str) -> list[tuple[str, list[str]]]:
    return [
        (
            "build_inventory_and_bounded_frontier_queue",
            [py, "scripts/build_weekend_universe_inventory.py", "--date", date, "--write-bounded-frontier-queue"],
        ),
        ("verify_inventory", [py, "scripts/verify_weekend_universe_inventory.py", "--date", date]),
        ("verify_frontier_queue", [py, "scripts/verify_weekend_frontier_queue.py", "--date", date]),
    ]


def post_inventory_linkage_commands(py: str, date: str) -> list[tuple[str, list[str]]]:
    return [
        ("build_rollup", [py, "scripts/build_weekend_training_rollup.py", "--date", date]),
        ("verify_rollup", [py, "scripts/verify_weekend_training_rollup.py", "--date", date]),
        ("build_research_progress_after_rollup", [py, "scripts/build_research_campaign_progress.py", "--date", date]),
        ("build_fog_map_after_rollup", [py, "scripts/build_research_fog_map.py", "--date", date]),
        ("verify_fog_map_after_rollup", [py, "scripts/verify_research_fog_map.py", "--date", date]),
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="run controlled grid drain linkage host runner")
    parser.add_argument("--date", required=True)
    return parser.parse_args()


def cleanup_enabled() -> bool:
    value = os.environ.get("TOP10_WEEKEND_CLEANUP_ENABLED", "1").strip().lower()
    return value not in {"0", "false", "no", "off"}


def run_linkage(date: str, py: str) -> int:
    steps: list[dict[str, Any]] = []
    for name, command in pre_inventory_refresh_commands(py, date):
        step = run_step(name, command)
        steps.append(step)
        if step["returncode"] != 0:
            gates = build_failed_gates_without_inventory(date, steps)
            return write_status(date, "FAILED", steps, gates)

    for name, command in inventory_commands(py, date):
        step = run_step(name, command)
        steps.append(step)
        if step["returncode"] != 0:
            gates = build_failed_gates_without_inventory(date, steps)
            return write_status(date, "FAILED", steps, gates)

    gates = build_gates(date, "OK", steps)
    status = "OK"
    for name, command in post_inventory_linkage_commands(py, date):
        step = run_step(name, command)
        steps.append(step)
        if step["returncode"] != 0:
            status = "FAILED"
            break
    if status == "OK" and cleanup_enabled():
        keep_latest = os.environ.get("TOP10_WEEKEND_CLEANUP_KEEP_LATEST_DATES", "1")
        cleanup_action = os.environ.get("TOP10_WEEKEND_CLEANUP_ACTION", "compress")
        step = run_step(
            "fog_map.weekend_full_artifact_retention",
            [
                py,
                "scripts/cleanup_weekend_training_full_artifacts.py",
                "--keep-latest-dates",
                keep_latest,
                "--action",
                cleanup_action,
                "--execute",
            ],
        )
        steps.append(step)
        if step["returncode"] != 0:
            status = "FAILED"
    if status != gates["status"]:
        gates = build_gates(date, status, steps)
    return write_status(date, status, steps, gates)


def main() -> int:
    args = parse_args()
    py = str(PROJECT_ROOT / ".venv" / "bin" / "python")
    return run_linkage(args.date, py)


def write_status(date: str, status: str, steps: list[dict[str, Any]], gates: dict[str, Any]) -> int:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now_utc(),
        "run_date": date,
        "status": status,
        "runner_mode": "linkage_only",
        "production_impact": PRODUCTION_IMPACT,
        "controlled_grid_drain_ready": status == "OK",
        "target_production_path_created": False,
        "gates_artifact": repo_path(gates_path(date)),
        "fog_map_latest": "artifacts/research_map/research_fog_map_latest.json",
        "host_runner_status_path": repo_path(status_path(date)),
        "host_runner_summary_path": repo_path(summary_path(date)),
        "steps": steps,
        "notes": [
            "Linkage-only repair runner.",
            "No replay execution, model training, production ranking write, or promotion.",
        ],
    }
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": payload["generated_at"],
        "run_date": date,
        "status": status,
        "runner_mode": payload["runner_mode"],
        "gates_artifact": payload["gates_artifact"],
        "fog_map_latest": payload["fog_map_latest"],
        "controlled_grid_drain_ready": payload["controlled_grid_drain_ready"],
        "production_impact": PRODUCTION_IMPACT,
        "failed_steps": [step["name"] for step in steps if step["returncode"] != 0],
    }
    write_json(status_path(date), payload)
    write_json(summary_path(date), summary)
    print(
        json.dumps(
            {
                "status": status,
                "output": repo_path(status_path(date)),
                "summary": repo_path(summary_path(date)),
                "gates": repo_path(gates_path(date)),
            },
            ensure_ascii=False,
        )
    )
    return 0 if status == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
