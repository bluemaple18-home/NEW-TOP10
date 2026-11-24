from __future__ import annotations

import errno
import json
import os
from pathlib import Path
from unittest import mock

import pytest

from app import storage_safety
from app.storage_safety import (
    GlobalPolicy,
    Inventory,
    JobPolicy,
    Sample,
    StorageObservationError,
    measure_paths,
    project_write_snapshot,
    run_guarded_job,
    take_sample,
)


def test_measure_paths_does_not_restat_every_regular_file(tmp_path: Path) -> None:
    """Fog 每分鐘掃描不可對同一 regular file 重複做 metadata stat。"""

    metered = tmp_path / "artifacts" / "autonomous_research"
    metered.mkdir(parents=True)
    expected_bytes = 0
    file_count = 128
    for index in range(file_count):
        payload = b"x" * (index + 1)
        (metered / f"sample-{index:03d}.bin").write_bytes(payload)
        expected_bytes += len(payload)

    original_stat = Path.stat
    regular_file_stat_calls = 0

    def counted_stat(self: Path, *args: object, **kwargs: object):
        nonlocal regular_file_stat_calls
        if self.suffix == ".bin":
            regular_file_stat_calls += 1
        return original_stat(self, *args, **kwargs)

    with mock.patch.object(Path, "stat", counted_stat):
        inventory = measure_paths(tmp_path, ("artifacts/autonomous_research",))

    assert inventory.bytes == expected_bytes
    assert inventory.file_count == file_count
    assert regular_file_stat_calls <= file_count


def test_project_snapshot_fails_closed_when_directory_cannot_be_observed(
    tmp_path: Path,
) -> None:
    """權限拒絕不可被 os.walk 靜默略過，否則 unknown-write 證據不完整。"""

    locked = tmp_path / "artifacts" / "locked"
    locked.mkdir(parents=True)
    (locked / "payload.json").write_text("{}", encoding="utf-8")
    original_scandir = os.scandir

    def deny_locked_directory(path: os.PathLike[str] | str):
        if Path(path) == locked:
            raise PermissionError(errno.EACCES, "fixture denied", str(locked))
        return original_scandir(path)

    with mock.patch("app.storage_safety.os.scandir", side_effect=deny_locked_directory):
        with pytest.raises(RuntimeError, match="WRITE_SNAPSHOT_PERMISSION_DENIED"):
            project_write_snapshot(tmp_path)


def test_fog_take_sample_applies_bounded_meter_deadline(tmp_path: Path) -> None:
    """Fog live meter 必須在 60 秒 cadence 前保留明確停止餘裕。"""

    policy = _job_policy(job="fog-research-worker", sample_interval_seconds=60)
    with (
        mock.patch.object(
            storage_safety,
            "measure_paths",
            return_value=Inventory(bytes=7, file_count=1),
        ) as meter,
        mock.patch.object(
            storage_safety,
            "_measure_host_capacity",
            return_value=(100_000, 50_000, 50_000, "fixture"),
        ),
        mock.patch.object(storage_safety, "process_tree_rss_snapshot", return_value=(0, ())),
        mock.patch.object(storage_safety, "read_swap_bytes", return_value=0),
        mock.patch.object(storage_safety, "read_memory_pressure_level", return_value=1),
    ):
        sample = take_sample(tmp_path, policy)

    assert (sample.project_bytes, sample.project_file_count) == (7, 1)
    assert meter.call_args.kwargs["deadline_seconds"] == 15.0


def test_meter_deadline_has_stable_fail_closed_reason(tmp_path: Path) -> None:
    metered = tmp_path / "artifacts" / "autonomous_research"
    metered.mkdir(parents=True)
    for index in range(8):
        (metered / f"sample-{index}.json").write_text("{}", encoding="utf-8")

    ticks = iter(float(index) for index in range(100))
    with pytest.raises(StorageObservationError) as captured:
        measure_paths(
            tmp_path,
            ("artifacts/autonomous_research",),
            deadline_seconds=2.0,
            monotonic_clock=lambda: next(ticks),
        )

    assert captured.value.reason == "METER_PATHS_PROBE_DEADLINE_EXCEEDED"


def test_guard_persists_observation_reason_without_generic_internal_code(
    tmp_path: Path,
) -> None:
    (tmp_path / "output").mkdir()
    calls = 0

    def sampler(_pid: int | None) -> Sample:
        nonlocal calls
        calls += 1
        raise StorageObservationError("METER_PATHS_PROBE_DEADLINE_EXCEEDED")

    result = run_guarded_job(
        tmp_path,
        _global_policy(),
        _job_policy(),
        (),
        ["/bin/sleep", "30"],
        sampler=sampler,
    )
    receipt = json.loads(
        (tmp_path / "logs/storage_safety/daily_latest.json").read_text(encoding="utf-8")
    )

    assert result == 70
    assert calls == 1
    assert "METER_PATHS_PROBE_DEADLINE_EXCEEDED" in receipt["reasons"]
    assert "GUARD_INTERNAL_ERROR_StorageObservationError" not in receipt["reasons"]


def _global_policy() -> GlobalPolicy:
    return GlobalPolicy(
        start_min_free_bytes=1024,
        start_min_free_percent=0.01,
        runtime_min_free_bytes=512,
        runtime_min_free_percent=0.01,
        require_swap_metric=True,
        log_max_bytes=4096,
        log_backups=2,
    )


def _job_policy(**overrides: object) -> JobPolicy:
    values: dict[str, object] = {
        "job": "daily",
        "launch_verified": True,
        "verification_basis": "bounded fixture",
        "meter_paths": ("output", "logs"),
        "registered_write_paths": ("output", "logs"),
        "cleanup_rule_ids": (),
        "max_bytes": 1024 * 1024,
        "max_file_count": 100,
        "max_process_tree_rss_bytes": 1024 * 1024,
        "max_swap_growth_bytes": 1024 * 1024,
        "expected_growth_bytes_per_hour": 1024 * 1024,
        "spike_window_seconds": 60,
        "stabilize_after_seconds": 60,
        "reclaim_after_seconds": 3600,
        "retention_days": 1,
        "sample_interval_seconds": 1,
    }
    values.update(overrides)
    return JobPolicy(**values)
