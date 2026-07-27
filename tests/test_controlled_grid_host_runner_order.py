from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import run_controlled_grid_drain_host_runner as runner


RUN_DATE = "2099-01-07"


def ok_step(name: str, command: list[str]) -> dict[str, Any]:
    return {
        "name": name,
        "command": command,
        "started_at": "2099-01-07T00:00:00+00:00",
        "finished_at": "2099-01-07T00:00:00+00:00",
        "returncode": 0,
        "stdout_tail": "",
        "stderr_tail": "",
        "status": "OK",
    }


def failed_step(name: str, command: list[str], stderr: str) -> dict[str, Any]:
    step = ok_step(name, command)
    step["returncode"] = 2
    step["stderr_tail"] = stderr
    step["status"] = "FAILED"
    return step


def test_host_runner_refreshes_fog_map_before_inventory(monkeypatch, tmp_path: Path) -> None:
    state = {"fog_map_processed": 33358, "run_history_processed": 33360, "fog_verified": False}
    calls: list[str] = []

    monkeypatch.setattr(runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("TOP10_WEEKEND_CLEANUP_ENABLED", "0")

    def fake_run_step(name: str, command: list[str]) -> dict[str, Any]:
        calls.append(name)
        if name == "build_research_progress_before_inventory":
            return ok_step(name, command)
        if name == "build_fog_map_before_inventory":
            state["fog_map_processed"] = state["run_history_processed"]
            return ok_step(name, command)
        if name == "verify_fog_map_before_inventory":
            if state["fog_map_processed"] != 33360:
                return failed_step(name, command, "stale fog map still at 33358")
            state["fog_verified"] = True
            return ok_step(name, command)
        if name == "build_inventory_and_bounded_frontier_queue":
            if not state["fog_verified"]:
                return failed_step(name, command, "inventory saw stale fog map at 33358")
            return ok_step(name, command)
        return ok_step(name, command)

    monkeypatch.setattr(runner, "run_step", fake_run_step)

    assert runner.run_linkage(RUN_DATE, "/fake/python") == 0
    assert calls[:4] == [
        "build_research_progress_before_inventory",
        "build_fog_map_before_inventory",
        "verify_fog_map_before_inventory",
        "build_inventory_and_bounded_frontier_queue",
    ]
    assert calls.index("verify_fog_map_before_inventory") < calls.index("build_inventory_and_bounded_frontier_queue")
    assert "weekend_full_artifact_retention" not in " ".join(calls)


def test_host_runner_does_not_build_inventory_when_pre_inventory_fog_verify_fails(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    monkeypatch.setattr(runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("TOP10_WEEKEND_CLEANUP_ENABLED", "0")

    def fake_run_step(name: str, command: list[str]) -> dict[str, Any]:
        calls.append(name)
        if name == "verify_fog_map_before_inventory":
            return failed_step(name, command, "stale fog map still at 33358")
        return ok_step(name, command)

    monkeypatch.setattr(runner, "run_step", fake_run_step)

    assert runner.run_linkage(RUN_DATE, "/fake/python") == 1
    assert "build_inventory_and_bounded_frontier_queue" not in calls
    assert calls == [
        "build_research_progress_before_inventory",
        "build_fog_map_before_inventory",
        "verify_fog_map_before_inventory",
    ]
