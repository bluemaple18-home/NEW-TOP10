#!/usr/bin/env python3
"""Issue #10 validation-only bounded observer.

This script creates a fresh no-.git sandbox, verifies the checked-in candidate
storage policy contract without overriding thresholds, runs the existing
digest-pinned daily validation entrypoint for cold/warm cycles, and writes one
machine-readable verdict receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "top10-issue10-bounded-observer.v1"
ENTRYPOINT_SCHEMA_VERSION = "top10-storage-validation-entrypoint.v1"
MARKER_SCHEMA_VERSION = "top10-storage-validation-root.v1"
JOB = "daily"
TWO_GIB = 2 * 1024**3
FOUR_GIB = 4 * 1024**3
WARNING_CADENCE_LIMIT_SECONDS = 30.0
WARNING_CADENCE_TOLERANCE_SECONDS = 0.25
EXPECTED_HOST_START_MIN_FREE_BYTES = 30 * 1024**3
EXPECTED_HOST_START_MIN_FREE_PERCENT = 0.15
EXPECTED_HOST_RUNTIME_MIN_FREE_BYTES = 20 * 1024**3
EXPECTED_HOST_RUNTIME_MIN_FREE_PERCENT = 0.10
EXPECTED_SAMPLE_INTERVAL_SECONDS = 60
DEFAULT_RUN_DATE = "2026-08-27"
DEFAULT_EVIDENCE_DIR = (
    Path(".work")
    / "CARD-NEW-TOP10-ISSUE10-SANDBOX-BOUNDED-OBSERVER-20260829"
)
EXCESSIVE_REASONS = {
    "PROCESS_TREE_RSS_BUDGET_EXCEEDED",
    "SWAP_GROWTH_BUDGET_EXCEEDED",
    "SWAP_EMERGENCY_HARD_STOP",
    "HOST_START_FREE_SPACE_BELOW_THRESHOLD",
    "HOST_RUNTIME_FREE_SPACE_BELOW_THRESHOLD",
    "RSS_AND_SWAP_RISING",
    "NO_STABILIZATION_OR_RECLAIM",
    "SUSTAINED_GROWTH_RATE_WILL_BREAK_BUDGET",
    "LIVE_SAMPLE_CADENCE_EXCEEDED",
    "LIVE_SAMPLE_SCHEDULE_OVERRUN",
    "PROCESS_GROUP_DESCENDANT_SURVIVED_LEADER",
    "PROCESS_GROUP_NOT_QUIESCENT_AT_FINAL_CHECK",
}
IGNORE_COPY_NAMES = {
    ".git",
    ".venv",
    ".codegraph",
    ".mypy_cache",
    ".pytest_cache",
    "__pycache__",
    ".DS_Store",
    "artifacts",
    "data",
    "logs",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def file_identity(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False}
    stat = path.stat()
    return {
        "path": str(path),
        "exists": True,
        "size_bytes": stat.st_size,
        "sha256": sha256_file(path),
    }


def terminate_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=15)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    process.wait(timeout=15)


def run_guard_command(
    command: list[str],
    *,
    cwd: Path,
    timeout_seconds: float,
    cycle_id: str,
) -> subprocess.CompletedProcess[str]:
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []

    def reader(stream: Any, sink: list[str]) -> None:
        if stream is None:
            return
        for chunk in iter(lambda: stream.read(65536), ""):
            if not chunk:
                break
            sink.append(chunk)

    process = subprocess.Popen(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    stdout_thread = threading.Thread(target=reader, args=(process.stdout, stdout_parts), daemon=True)
    stderr_thread = threading.Thread(target=reader, args=(process.stderr, stderr_parts), daemon=True)
    stdout_thread.start()
    stderr_thread.start()
    deadline = time.monotonic() + timeout_seconds
    next_heartbeat = time.monotonic() + 25
    try:
        while process.poll() is None:
            now = time.monotonic()
            if now >= deadline:
                terminate_process_tree(process)
                raise subprocess.TimeoutExpired(command, timeout_seconds)
            if now >= next_heartbeat:
                print(json.dumps({"event": "cycle_running", "cycle_id": cycle_id}, ensure_ascii=False), flush=True)
                next_heartbeat = now + 25
            try:
                process.wait(timeout=min(1.0, max(0.1, deadline - now)))
            except subprocess.TimeoutExpired:
                pass
    except BaseException:
        terminate_process_tree(process)
        raise
    stdout_thread.join(timeout=5)
    stderr_thread.join(timeout=5)
    return subprocess.CompletedProcess(
        command,
        int(process.returncode or 0),
        "".join(stdout_parts),
        "".join(stderr_parts),
    )


def copy_template(template_root: Path, sandbox_root: Path) -> None:
    def ignore(_directory: str, names: list[str]) -> set[str]:
        return {name for name in names if name in IGNORE_COPY_NAMES}

    shutil.copytree(template_root, sandbox_root, ignore=ignore)
    if (sandbox_root / ".git").exists() or (sandbox_root / ".git").is_symlink():
        raise RuntimeError("fresh sandbox unexpectedly contains .git")


def validate_candidate_policy_contract(sandbox_root: Path) -> dict[str, Any]:
    policy_path = sandbox_root / "docs" / "operations" / "top10-storage-policy.json"
    policy = read_json(policy_path)
    host = policy["host"]
    daily = policy["jobs"][JOB]
    exact_contract = {
        "host.start_min_free_bytes": (
            host.get("start_min_free_bytes"),
            EXPECTED_HOST_START_MIN_FREE_BYTES,
        ),
        "host.start_min_free_percent": (
            host.get("start_min_free_percent"),
            EXPECTED_HOST_START_MIN_FREE_PERCENT,
        ),
        "host.runtime_min_free_bytes": (
            host.get("runtime_min_free_bytes"),
            EXPECTED_HOST_RUNTIME_MIN_FREE_BYTES,
        ),
        "host.runtime_min_free_percent": (
            host.get("runtime_min_free_percent"),
            EXPECTED_HOST_RUNTIME_MIN_FREE_PERCENT,
        ),
        "daily.swap_warning_growth_bytes": (
            daily.get("swap_warning_growth_bytes"),
            TWO_GIB,
        ),
        "daily.max_swap_growth_bytes": (
            daily.get("max_swap_growth_bytes"),
            FOUR_GIB,
        ),
        "daily.max_process_tree_rss_bytes": (
            daily.get("max_process_tree_rss_bytes"),
            FOUR_GIB,
        ),
        "daily.sample_interval_seconds": (
            daily.get("sample_interval_seconds"),
            EXPECTED_SAMPLE_INTERVAL_SECONDS,
        ),
        "daily.launch_verified": (daily.get("launch_verified"), False),
    }
    mismatches = [
        {
            "field": field,
            "actual": actual,
            "expected": expected,
        }
        for field, (actual, expected) in exact_contract.items()
        if actual != expected
    ]
    if mismatches:
        raise RuntimeError(
            "candidate policy contract mismatch: "
            + json.dumps(mismatches, ensure_ascii=False, sort_keys=True)
        )
    return {
        "policy_path": str(policy_path),
        "policy_sha256": sha256_file(policy_path),
        "policy_mutated": False,
        "validation_only_allows_launch_verified_false": True,
        "host_contract": host,
        "daily_contract": daily,
        "exact_contract_verified": True,
    }


def materialize_reference_inputs(source_root: Path, sandbox_root: Path) -> dict[str, Any]:
    source = source_root / "data" / "reference" / "tradable_universe.csv"
    target = sandbox_root / "data" / "reference" / "tradable_universe.csv"
    if not source.is_file() or source.is_symlink():
        raise RuntimeError(f"required reference input missing or unsafe: {source}")
    before = file_identity(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    after = file_identity(source)
    if before.get("sha256") != after.get("sha256"):
        raise RuntimeError("reference input changed while materializing")
    return {
        "source_before": before,
        "source_after": after,
        "source_unchanged": True,
        "materialized": file_identity(target),
    }


def build_contract_and_marker(
    *,
    sandbox_root: Path,
    source_root: Path,
    snapshot_input: Path,
    run_date: str,
    cycle_id: str,
) -> tuple[Path, Path, dict[str, Any]]:
    entrypoint = sandbox_root / "scripts" / "storage_validation" / "daily.py"
    contract_path = sandbox_root / f"daily-{cycle_id}-entrypoint-contract.json"
    marker_path = sandbox_root / f"manual-validation-marker-{cycle_id}.json"
    argv = [
        "--source-root",
        str(source_root),
        "--output-root",
        str(sandbox_root),
        "--runtime-root",
        str(sandbox_root / "logs" / "storage_safety" / "runtime" / JOB / cycle_id),
        "--run-date",
        run_date,
        "--cycle-id",
        cycle_id,
        "--snapshot-input",
        str(snapshot_input),
    ]
    contract = {
        "schema_version": ENTRYPOINT_SCHEMA_VERSION,
        "job": JOB,
        "interpreter": "python-isolated",
        "entrypoint": "scripts/storage_validation/daily.py",
        "entrypoint_sha256": sha256_file(entrypoint),
        "argv": argv,
    }
    write_json(contract_path, contract)
    marker = {
        "schema_version": MARKER_SCHEMA_VERSION,
        "sandbox_root": str(sandbox_root),
        "manual_only": True,
        "jobs": [JOB],
        "trusted_entrypoints": {
            JOB: {
                "contract_path": contract_path.relative_to(sandbox_root).as_posix(),
                "contract_sha256": sha256_file(contract_path),
            }
        },
    }
    write_json(marker_path, marker)
    return contract_path, marker_path, contract


def run_cycle(
    *,
    sandbox_root: Path,
    source_root: Path,
    snapshot_input: Path,
    run_date: str,
    cycle_id: str,
    max_runtime_seconds: float,
    python_executable: Path,
    evidence_dir: Path,
) -> dict[str, Any]:
    contract_path, marker_path, contract = build_contract_and_marker(
        sandbox_root=sandbox_root,
        source_root=source_root,
        snapshot_input=snapshot_input,
        run_date=run_date,
        cycle_id=cycle_id,
    )
    command = [
        str(python_executable),
        "scripts/storage_safety.py",
        "--policy",
        "docs/operations/top10-storage-policy.json",
        "validate-run",
        "--job",
        JOB,
        "--marker",
        str(marker_path),
        "--max-runtime-seconds",
        str(max_runtime_seconds),
        "--source-input-root",
        str(source_root),
        "--sandbox-input-root",
        "data/raw/validation_snapshots",
        "--sandbox-output-root",
        ".",
        "--entrypoint-contract",
        str(contract_path),
    ]
    (sandbox_root / "data" / "raw" / "validation_snapshots").mkdir(parents=True, exist_ok=True)
    guard_receipt_path = sandbox_root / "logs" / "storage_safety" / f"{JOB}_latest.json"
    child_receipt_path = (
        sandbox_root
        / "logs"
        / "storage_safety"
        / "runtime"
        / JOB
        / cycle_id
        / f"daily_validation_{cycle_id}.json"
    )
    guard_copy = evidence_dir / f"{cycle_id}_guard_receipt.json"
    child_copy = evidence_dir / f"{cycle_id}_child_receipt.json"
    for stale_copy in (guard_copy, child_copy):
        if stale_copy.exists():
            stale_copy.unlink()
    print(json.dumps({"event": "cycle_started", "cycle_id": cycle_id}, ensure_ascii=False), flush=True)
    completed = run_guard_command(
        command,
        cwd=sandbox_root,
        timeout_seconds=max_runtime_seconds + 120,
        cycle_id=cycle_id,
    )
    print(
        json.dumps(
            {
                "event": "cycle_finished",
                "cycle_id": cycle_id,
                "exit_code": completed.returncode,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    if guard_receipt_path.exists():
        shutil.copy2(guard_receipt_path, guard_copy)
    if child_receipt_path.exists():
        shutil.copy2(child_receipt_path, child_copy)
    return {
        "cycle_id": cycle_id,
        "command": command,
        "exit_code": completed.returncode,
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
        "contract": contract,
        "contract_path": str(contract_path),
        "contract_sha256": sha256_file(contract_path),
        "marker_path": str(marker_path),
        "marker_sha256": sha256_file(marker_path),
        "guard_receipt_path": str(guard_receipt_path),
        "guard_receipt_copy": str(guard_copy) if guard_copy.exists() else None,
        "child_receipt_path": str(child_receipt_path),
        "child_receipt_copy": str(child_copy) if child_copy.exists() else None,
    }


def summarize_warning_cadence(
    *,
    receipt: dict[str, Any],
    samples: list[dict[str, Any]],
    max_swap_delta: int | None,
) -> dict[str, Any]:
    warnings = receipt.get("warnings") if isinstance(receipt.get("warnings"), list) else []
    limits = receipt.get("limits") if isinstance(receipt.get("limits"), dict) else {}
    warning_threshold = limits.get("swap_warning_growth_bytes")
    warning_threshold_crossed = (
        isinstance(max_swap_delta, int)
        and isinstance(warning_threshold, int)
        and max_swap_delta >= warning_threshold
    )
    warning_path_exercised = "SOFT_SWAP_WARNING" in warnings
    summary: dict[str, Any] = {
        "warning_threshold_bytes": warning_threshold,
        "warning_threshold_crossed": warning_threshold_crossed,
        "warning_path_exercised": warning_path_exercised,
        "warning_cadence_checked": False,
        "warning_cadence_pass": None,
        "warning_cadence_limit_seconds": WARNING_CADENCE_LIMIT_SECONDS,
        "warning_cadence_tolerance_seconds": WARNING_CADENCE_TOLERANCE_SECONDS,
        "actual_max_warning_live_sample_gap_seconds": None,
    }
    if not warning_path_exercised:
        return summary
    baseline_swap = samples[0].get("swap_bytes") if samples else None
    if not isinstance(baseline_swap, int) or not isinstance(warning_threshold, int):
        summary["warning_cadence_pass"] = False
        return summary
    live_after_warning: list[dict[str, Any]] = []
    warning_seen = False
    for sample in samples:
        if sample.get("phase") != "live":
            continue
        timestamp = sample.get("timestamp")
        swap_bytes = sample.get("swap_bytes")
        if not isinstance(timestamp, (int, float)) or not isinstance(swap_bytes, int):
            continue
        if not warning_seen and swap_bytes - baseline_swap >= warning_threshold:
            warning_seen = True
        if warning_seen:
            live_after_warning.append(sample)
    if len(live_after_warning) < 2:
        summary["warning_cadence_pass"] = False
        return summary
    timestamps = [float(sample["timestamp"]) for sample in live_after_warning]
    gaps = [right - left for left, right in zip(timestamps, timestamps[1:])]
    max_gap = max(gaps) if gaps else None
    summary["warning_cadence_checked"] = True
    summary["actual_max_warning_live_sample_gap_seconds"] = max_gap
    summary["warning_cadence_pass"] = (
        max_gap is not None
        and max_gap <= WARNING_CADENCE_LIMIT_SECONDS + WARNING_CADENCE_TOLERANCE_SECONDS
    )
    return summary


def summarize_guard_receipt(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "verdict_hint": "INCONCLUSIVE"}
    receipt = read_json(path)
    samples = receipt.get("samples") if isinstance(receipt.get("samples"), list) else []
    live = [sample for sample in samples if sample.get("phase") == "live"]
    rss_values = [
        sample.get("rss_bytes")
        for sample in live
        if isinstance(sample.get("rss_bytes"), int)
    ]
    swap_values = [
        sample.get("swap_bytes")
        for sample in samples
        if isinstance(sample.get("swap_bytes"), int)
    ]
    host_ratios = [
        sample["host_free_bytes"] / sample["host_total_bytes"]
        for sample in samples
        if isinstance(sample.get("host_free_bytes"), int)
        and isinstance(sample.get("host_total_bytes"), int)
        and sample["host_total_bytes"] > 0
    ]
    baseline_swap = swap_values[0] if swap_values else None
    max_swap_delta = (
        max(value - baseline_swap for value in swap_values)
        if baseline_swap is not None and swap_values
        else None
    )
    reasons = receipt.get("reasons") if isinstance(receipt.get("reasons"), list) else []
    warnings = receipt.get("warnings") if isinstance(receipt.get("warnings"), list) else []
    limits = receipt.get("limits") if isinstance(receipt.get("limits"), dict) else {}
    summary = receipt.get("summary") if isinstance(receipt.get("summary"), dict) else {}
    preflight = next(
        (
            sample
            for sample in samples
            if isinstance(sample, dict) and sample.get("phase") == "preflight"
        ),
        samples[0] if samples else None,
    )
    warning_cadence = summarize_warning_cadence(
        receipt=receipt,
        samples=samples,
        max_swap_delta=max_swap_delta,
    )
    return {
        "exists": True,
        "status": receipt.get("status"),
        "reasons": reasons,
        "warnings": warnings,
        "child_exit_code": receipt.get("child_exit_code"),
        "sample_count": len(samples),
        "live_sample_count": len(live),
        "peak_live_rss_bytes": max(rss_values) if rss_values else None,
        "max_swap_delta_bytes": max_swap_delta,
        "peak_swap_growth_bytes": summary.get("peak_swap_growth_bytes"),
        "min_host_free_ratio": min(host_ratios) if host_ratios else None,
        "unknown_changed_paths": receipt.get(
            "unknown_changed_paths",
            summary.get("unknown_changed_paths"),
        ),
        "final_process_group_quiescent": receipt.get("process_group", {}).get(
            "final_quiescent"
        ),
        "policy_limits": limits,
        "limits": limits,
        "preflight_host_facts": (
            {
                "host_free_bytes": preflight.get("host_free_bytes"),
                "host_total_bytes": preflight.get("host_total_bytes"),
                "swap_bytes": preflight.get("swap_bytes"),
                "rss_bytes": preflight.get("rss_bytes"),
            }
            if isinstance(preflight, dict)
            else None
        ),
        **warning_cadence,
    }


def summarize_child_receipt(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False}
    receipt = read_json(path)
    artifacts = receipt.get("artifacts") if isinstance(receipt.get("artifacts"), dict) else {}
    artifact_status = {
        name: bool(value.get("exists")) if isinstance(value, dict) else False
        for name, value in artifacts.items()
    }
    return {
        "exists": True,
        "status": receipt.get("status"),
        "child_exit_code": receipt.get("child_exit_code"),
        "source_identity_unchanged": receipt.get("source_identity_unchanged"),
        "artifact_status": artifact_status,
        "all_required_artifacts_exist": bool(artifact_status)
        and all(artifact_status.values()),
    }


def decide(cycles: list[dict[str, Any]]) -> tuple[str, list[str]]:
    explanations: list[str] = []
    excessive_found = False
    acceptable = True
    if len(cycles) != 2:
        acceptable = False
        explanations.append("expected exactly two cycles")
    for cycle in cycles:
        guard = cycle["guard_summary"]
        child = cycle["child_summary"]
        cycle_id = cycle["cycle_id"]
        if not guard.get("exists") or not child.get("exists"):
            acceptable = False
            explanations.append(f"{cycle_id}: missing receipt")
            continue
        reasons = set(guard.get("reasons") or [])
        if reasons & EXCESSIVE_REASONS:
            excessive_found = True
            explanations.append(f"{cycle_id}: excessive reason {sorted(reasons & EXCESSIVE_REASONS)}")
        if guard.get("status") != "OK":
            acceptable = False
            explanations.append(f"{cycle_id}: guard status {guard.get('status')}")
        if child.get("status") != "OK":
            acceptable = False
            explanations.append(f"{cycle_id}: child status {child.get('status')}")
        if child.get("source_identity_unchanged") is not True:
            acceptable = False
            explanations.append(f"{cycle_id}: source identity not proven unchanged")
        if child.get("all_required_artifacts_exist") is not True:
            acceptable = False
            explanations.append(f"{cycle_id}: required artifacts missing")
        peak_rss = guard.get("peak_live_rss_bytes")
        if not isinstance(peak_rss, int):
            acceptable = False
            explanations.append(f"{cycle_id}: missing live RSS sample")
        elif peak_rss >= FOUR_GIB:
            excessive_found = True
            acceptable = False
            explanations.append(f"{cycle_id}: peak RSS >= 4GiB")
        swap_delta = guard.get("max_swap_delta_bytes")
        if not isinstance(swap_delta, int):
            acceptable = False
            explanations.append(f"{cycle_id}: missing swap delta")
        elif swap_delta >= FOUR_GIB:
            excessive_found = True
            acceptable = False
            explanations.append(f"{cycle_id}: swap delta >= 4GiB")
        warnings = set(guard.get("warnings") or [])
        if guard.get("warning_threshold_crossed") and "SOFT_SWAP_WARNING" not in warnings:
            acceptable = False
            explanations.append(f"{cycle_id}: warning threshold crossed without SOFT_SWAP_WARNING")
        if "SOFT_SWAP_WARNING" in warnings and guard.get("warning_cadence_pass") is not True:
            acceptable = False
            explanations.append(
                f"{cycle_id}: warning cadence not proven <= {WARNING_CADENCE_LIMIT_SECONDS}s"
            )
        host_ratio = guard.get("min_host_free_ratio")
        if not isinstance(host_ratio, float):
            acceptable = False
            explanations.append(f"{cycle_id}: missing host free ratio")
        elif host_ratio < 0.10:
            excessive_found = True
            acceptable = False
            explanations.append(f"{cycle_id}: host free ratio < 10%")
        if guard.get("final_process_group_quiescent") is not True:
            acceptable = False
            explanations.append(f"{cycle_id}: process group not quiescent")
        unknown = guard.get("unknown_changed_paths")
        if unknown:
            acceptable = False
            explanations.append(f"{cycle_id}: unknown writes observed")
    if excessive_found:
        return "EXCESSIVE_GROWTH", explanations
    if acceptable:
        return "BOUNDED_ACCEPTABLE", explanations or ["both cycles completed within bounded criteria"]
    return "INCONCLUSIVE", explanations


def run_self_test() -> int:
    def cycle(cycle_id: str, guard: dict[str, Any], child: dict[str, Any]) -> dict[str, Any]:
        return {"cycle_id": cycle_id, "guard_summary": guard, "child_summary": child}

    no_warning_cadence = summarize_warning_cadence(
        receipt={"warnings": [], "limits": {"swap_warning_growth_bytes": TWO_GIB}},
        samples=[
            {"phase": "preflight", "timestamp": -1.0, "swap_bytes": 0},
            {"phase": "live", "timestamp": 0.0, "swap_bytes": 1 * 1024**3},
        ],
        max_swap_delta=1 * 1024**3,
    )
    warning_pass_cadence = summarize_warning_cadence(
        receipt={
            "warnings": ["SOFT_SWAP_WARNING"],
            "limits": {"swap_warning_growth_bytes": TWO_GIB},
        },
        samples=[
            {"phase": "preflight", "timestamp": -1.0, "swap_bytes": 0},
            {"phase": "live", "timestamp": 0.0, "swap_bytes": TWO_GIB},
            {"phase": "live", "timestamp": 29.9, "swap_bytes": TWO_GIB + 1},
        ],
        max_swap_delta=TWO_GIB + 1,
    )
    warning_fail_cadence = summarize_warning_cadence(
        receipt={
            "warnings": ["SOFT_SWAP_WARNING"],
            "limits": {"swap_warning_growth_bytes": TWO_GIB},
        },
        samples=[
            {"phase": "preflight", "timestamp": -1.0, "swap_bytes": 0},
            {"phase": "live", "timestamp": 0.0, "swap_bytes": TWO_GIB},
            {"phase": "live", "timestamp": 31.0, "swap_bytes": TWO_GIB + 1},
        ],
        max_swap_delta=TWO_GIB + 1,
    )
    good_guard = {
        "exists": True,
        "status": "OK",
        "reasons": [],
        "peak_live_rss_bytes": 2 * 1024**3,
        "max_swap_delta_bytes": 1 * 1024**3,
        "warnings": [],
        "warning_threshold_crossed": False,
        "warning_path_exercised": False,
        "warning_cadence_checked": False,
        "warning_cadence_pass": None,
        "actual_max_warning_live_sample_gap_seconds": None,
        "min_host_free_ratio": 0.12,
        "final_process_group_quiescent": True,
        "unknown_changed_paths": [],
        **no_warning_cadence,
    }
    good_child = {
        "exists": True,
        "status": "OK",
        "source_identity_unchanged": True,
        "all_required_artifacts_exist": True,
    }
    bounded_without_warning, _ = decide(
        [
            cycle("cold", good_guard, good_child),
            cycle("warm", good_guard, good_child),
        ]
    )
    warning_pass_guard = {
        **good_guard,
        "max_swap_delta_bytes": 3 * 1024**3,
        "warnings": ["SOFT_SWAP_WARNING"],
        **warning_pass_cadence,
    }
    warning_cadence_pass, _ = decide(
        [
            cycle("cold", warning_pass_guard, good_child),
            cycle("warm", good_guard, good_child),
        ]
    )
    warning_fail_guard = {
        **warning_pass_guard,
        "warning_cadence_pass": False,
        "actual_max_warning_live_sample_gap_seconds": 31.0,
    }
    warning_cadence_fail, _ = decide(
        [cycle("cold", warning_fail_guard, good_child), cycle("warm", good_guard, good_child)]
    )
    emergency_guard = {
        **good_guard,
        "reasons": ["SWAP_EMERGENCY_HARD_STOP"],
        "max_swap_delta_bytes": FOUR_GIB,
        "warnings": ["SOFT_SWAP_WARNING"],
        **warning_pass_cadence,
    }
    emergency, _ = decide(
        [cycle("cold", emergency_guard, good_child), cycle("warm", good_guard, good_child)]
    )
    missing_child = dict(good_child)
    missing_child["exists"] = False
    missing_receipt, _ = decide(
        [cycle("cold", good_guard, missing_child), cycle("warm", good_guard, good_child)]
    )
    forbidden_modules = ("matplotlib", "pandas", "pyarrow")
    ok = (
        bounded_without_warning == "BOUNDED_ACCEPTABLE"
        and warning_cadence_pass == "BOUNDED_ACCEPTABLE"
        and warning_cadence_fail == "INCONCLUSIVE"
        and emergency == "EXCESSIVE_GROWTH"
        and missing_receipt == "INCONCLUSIVE"
        and no_warning_cadence["warning_path_exercised"] is False
        and warning_pass_cadence["warning_cadence_pass"] is True
        and warning_fail_cadence["warning_cadence_pass"] is False
        and all(module not in sys.modules for module in forbidden_modules)
    )
    print(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "self_test": "PASS" if ok else "FAIL",
                "bounded_without_warning": bounded_without_warning,
                "warning_cadence_pass": warning_cadence_pass,
                "warning_cadence_fail": warning_cadence_fail,
                "emergency_4gib": emergency,
                "missing_receipt": missing_receipt,
                "matplotlib_imported": "matplotlib" in sys.modules,
                "parquet_modules_imported": any(
                    module in sys.modules for module in ("pandas", "pyarrow")
                ),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if ok else 1


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Issue #10 bounded daily observer")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--run-observer", action="store_true")
    parser.add_argument("--template-root", type=Path, default=Path.cwd())
    parser.add_argument("--source-root", type=Path, required=False)
    parser.add_argument("--snapshot-input", type=Path, default=None)
    parser.add_argument("--run-date", default=DEFAULT_RUN_DATE)
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument("--max-runtime-seconds", type=float, default=3600.0)
    parser.add_argument("--sandbox-root", type=Path, default=None)
    parser.add_argument("--python-executable", type=Path, default=Path(sys.executable))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.self_test:
        return run_self_test()
    if not args.run_observer:
        raise SystemExit("refusing to run without explicit --run-observer")
    template_root = args.template_root.resolve()
    source_root = (args.source_root or template_root).resolve()
    snapshot_input = (
        args.snapshot_input.resolve()
        if args.snapshot_input is not None
        else source_root / "data" / "clean" / "features.parquet"
    )
    if (template_root / ".git").exists() and template_root == source_root:
        raise SystemExit("source-root must be explicit when template-root is a git checkout")
    if not snapshot_input.is_file() or snapshot_input.is_symlink():
        raise SystemExit(f"snapshot input missing or unsafe: {snapshot_input}")
    evidence_dir = args.evidence_dir.resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    sandbox_root = (
        args.sandbox_root.resolve()
        if args.sandbox_root is not None
        else Path(tempfile.mkdtemp(prefix="top10-issue10-bounded-observer-")).resolve()
    )
    if sandbox_root.exists() and any(sandbox_root.iterdir()):
        raise SystemExit(f"sandbox root must be empty: {sandbox_root}")
    if sandbox_root.exists():
        sandbox_root.rmdir()

    started_at = utc_now()
    source_before = file_identity(snapshot_input)
    source_policy_path = source_root / "docs" / "operations" / "top10-storage-policy.json"
    source_policy_before = file_identity(source_policy_path)
    observer_before = file_identity(template_root / "scripts" / "run_daily_bounded_observer.py")
    copy_template(template_root, sandbox_root)
    policy_info = validate_candidate_policy_contract(sandbox_root)
    reference_inputs = materialize_reference_inputs(source_root, sandbox_root)
    static_identity = {
        "observer": observer_before,
        "storage_guard_cli": file_identity(sandbox_root / "scripts" / "storage_safety.py"),
        "storage_guard_core": file_identity(sandbox_root / "app" / "storage_safety.py"),
        "daily_validation_entrypoint": file_identity(
            sandbox_root / "scripts" / "storage_validation" / "daily.py"
        ),
        "sandbox_policy": file_identity(
            sandbox_root / "docs" / "operations" / "top10-storage-policy.json"
        ),
        "source_policy_before": source_policy_before,
        "source_snapshot_before": source_before,
        "source_reference_before": reference_inputs["source_before"],
    }

    cycles: list[dict[str, Any]] = []
    for cycle_id in ("cold", "warm"):
        cycle = run_cycle(
            sandbox_root=sandbox_root,
            source_root=source_root,
            snapshot_input=snapshot_input,
            run_date=args.run_date,
            cycle_id=cycle_id,
            max_runtime_seconds=args.max_runtime_seconds,
            python_executable=args.python_executable,
            evidence_dir=evidence_dir,
        )
        cycle["guard_summary"] = summarize_guard_receipt(Path(cycle["guard_receipt_path"]))
        cycle["child_summary"] = summarize_child_receipt(Path(cycle["child_receipt_path"]))
        cycles.append(cycle)
        if cycle["guard_summary"].get("status") != "OK":
            break

    source_after = file_identity(snapshot_input)
    source_policy_after = file_identity(source_policy_path)
    observer_after = file_identity(template_root / "scripts" / "run_daily_bounded_observer.py")
    verdict, explanations = decide(cycles)
    denied_marker = sandbox_root / "logs" / "storage_safety" / "restart_denied" / f"{JOB}.json"
    if verdict == "BOUNDED_ACCEPTABLE" and denied_marker.exists():
        verdict = "INCONCLUSIVE"
        explanations = [*explanations, "sandbox restart-denied marker exists"]
    if source_policy_before.get("sha256") != source_policy_after.get("sha256"):
        verdict = "INCONCLUSIVE"
        explanations = [*explanations, "source policy changed during observer run"]
    if observer_before.get("sha256") != observer_after.get("sha256"):
        verdict = "INCONCLUSIVE"
        explanations = [*explanations, "observer source changed during observer run"]
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "fresh_s1": True,
        "supersedes_run2": False,
        "status": "OK",
        "verdict": verdict,
        "explanations": explanations,
        "started_at": started_at,
        "finished_at": utc_now(),
        "issue": "NEW-TOP10 Issue #10",
        "production_candidate_policy_sha": source_policy_before.get("sha256"),
        "scope": {
            "validation_only": True,
            "production_run": False,
            "network_send": False,
            "production_policy_changed": False,
            "restart_marker_cleared": False,
            "git_operation": False,
        },
        "roots": {
            "template_root": str(template_root),
            "source_root": str(source_root),
            "snapshot_input": str(snapshot_input),
            "sandbox_root": str(sandbox_root),
            "evidence_dir": str(evidence_dir),
        },
        "candidate_policy_contract": policy_info,
        "reference_inputs": reference_inputs,
        "static_identity": static_identity,
        "preflight_host_facts": {
            cycle["cycle_id"]: cycle["guard_summary"].get("preflight_host_facts")
            for cycle in cycles
        },
        "source_snapshot_after": source_after,
        "source_snapshot_unchanged": source_before.get("sha256") == source_after.get("sha256"),
        "source_policy_after": source_policy_after,
        "source_policy_unchanged": source_policy_before.get("sha256") == source_policy_after.get("sha256"),
        "observer_after": observer_after,
        "observer_unchanged": observer_before.get("sha256") == observer_after.get("sha256"),
        "source_code_policy_identity_unchanged": (
            source_before.get("sha256") == source_after.get("sha256")
            and source_policy_before.get("sha256") == source_policy_after.get("sha256")
            and observer_before.get("sha256") == observer_after.get("sha256")
        ),
        "sandbox_restart_denied_marker": file_identity(denied_marker),
        "cycles": cycles,
    }
    receipt_path = evidence_dir / "bounded_observer_receipt.json"
    write_json(receipt_path, receipt)
    print(json.dumps({"verdict": verdict, "receipt_path": str(receipt_path)}, ensure_ascii=False))
    return 0 if verdict == "BOUNDED_ACCEPTABLE" else 2


if __name__ == "__main__":
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    raise SystemExit(main())
