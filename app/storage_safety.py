"""TOP10 排程的容量量測、回收與隔離停損核心。

模組只接受 repo 內明列的 meter／cleanup 路徑；不追蹤 symlink，也不會
跨出專案根目錄。正式排程政策在完成代表性兩週期前維持 fail closed。
"""

from __future__ import annotations

import fcntl
import hashlib
import hmac
import json
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from app.fog_natural_acceptance import FOG_JOB, evaluate_natural_acceptance


POLICY_SCHEMA_VERSION = "top10-storage-policy.v1"
RECEIPT_SCHEMA_VERSION = "top10-storage-guard-receipt.v1"
RESTART_DENIED_SCHEMA_VERSION = "top10-storage-restart-denied.v1"
INVOCATION_CLAIM_SCHEMA_VERSION = "top10-storage-invocation-claim.v1"
IGNORED_PROJECT_DIRS = {".git", ".venv", ".codegraph", "__pycache__"}
SANDBOX_EXECUTABLE = Path("/usr/bin/sandbox-exec")
PROTECTED_SNAPSHOT_MAX_FILES = 50_000
VALIDATION_ENTRYPOINT_SCHEMA_VERSION = "top10-storage-validation-entrypoint.v1"
_TRUSTED_VALIDATION_TOKEN = object()
_LIVE_SAMPLE_SCHEDULE_NUMERATOR = 19
_FOG_LIVE_SAMPLE_SCHEDULE_NUMERATOR = 18
_LIVE_SAMPLE_SCHEDULE_DENOMINATOR = 20
_HOST_PROBE_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class GlobalPolicy:
    start_min_free_bytes: int
    start_min_free_percent: float
    runtime_min_free_bytes: int
    runtime_min_free_percent: float
    require_swap_metric: bool
    log_max_bytes: int
    log_backups: int


@dataclass(frozen=True)
class RetentionRule:
    rule_id: str
    base_path: str
    pattern: str
    retention_seconds: int
    max_files: int
    max_bytes: int
    protect_newest: int = 1


@dataclass(frozen=True)
class JobPolicy:
    job: str
    launch_verified: bool
    verification_basis: str
    meter_paths: tuple[str, ...]
    registered_write_paths: tuple[str, ...]
    cleanup_rule_ids: tuple[str, ...]
    max_bytes: int
    max_file_count: int
    max_process_tree_rss_bytes: int
    max_swap_growth_bytes: int
    expected_growth_bytes_per_hour: int
    spike_window_seconds: int
    stabilize_after_seconds: int
    reclaim_after_seconds: int
    retention_days: int
    sample_interval_seconds: int


@dataclass(frozen=True)
class Inventory:
    bytes: int
    file_count: int


@dataclass(frozen=True)
class ProcessRssAttribution:
    pid: int
    ppid: int
    rss_bytes: int
    command: str


@dataclass(frozen=True)
class ProbeTiming:
    probe: str
    duration_seconds: float
    available: bool


@dataclass(frozen=True)
class Sample:
    timestamp: float
    project_bytes: int
    project_file_count: int
    host_total_bytes: int
    host_free_bytes: int
    rss_bytes: int | None
    swap_bytes: int | None
    phase: str = "live"
    memory_pressure_level: int | None = None
    process_rss_attribution: tuple[ProcessRssAttribution, ...] = ()
    probe_timings: tuple[ProbeTiming, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StopDecision:
    triggered: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ReclaimResult:
    bytes_before: int
    bytes_after: int
    file_count_before: int
    file_count_after: int
    removed_paths: tuple[str, ...]
    dry_run: bool


@dataclass(frozen=True)
class ProcessGroupIdentity:
    leader_pid: int
    group_id: int
    session_id: int
    leader_start_token: str


@dataclass(frozen=True)
class TrustedValidationEntrypoint:
    job: str
    sandbox_root: Path
    contract_path: Path
    contract_sha256: str
    entrypoint_path: Path
    entrypoint_sha256: str
    argv: tuple[str, ...]
    command: tuple[str, ...]
    _trust_token: object


class GuardInterrupted(RuntimeError):
    """guard 收到終止訊號；由主執行路徑轉成 fail-closed marker。"""


class UntrustedValidationEntrypoint(RuntimeError):
    """validation command 未通過結構化 entrypoint trust contract。"""


def _positive_int(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{field} 必須大於 0")
    return value


def _nonnegative_int(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field} 不得小於 0")
    return value


def _strict_bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field} 必須是 JSON boolean")
    return value


def _fraction(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} 必須是數值")
    parsed = float(value)
    if not 0 < parsed <= 1:
        raise ValueError(f"{field} 必須介於 0 與 1 之間")
    return parsed


def _string_list(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field} 必須是非空 JSON array")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{field} 只能包含非空字串")
    return tuple(value)


def _relative_path(value: str, field: str) -> str:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"{field} 必須是 repo-relative 安全路徑: {value}")
    return path.as_posix()


def load_policy(path: Path, job: str) -> tuple[GlobalPolicy, JobPolicy, tuple[RetentionRule, ...]]:
    """讀取並嚴格驗證單一 job 的容量政策。"""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != POLICY_SCHEMA_VERSION:
        raise ValueError("storage policy schema_version 不符")
    host = payload.get("host")
    logging = payload.get("logging")
    jobs = payload.get("jobs")
    rules_payload = payload.get("retention_rules")
    if not isinstance(host, dict) or not isinstance(logging, dict):
        raise ValueError("storage policy 缺少 host／logging")
    if not isinstance(jobs, dict) or job not in jobs or not isinstance(jobs[job], dict):
        raise ValueError(f"storage policy 未登記 job: {job}")
    if not isinstance(rules_payload, dict):
        raise ValueError("storage policy 缺少 retention_rules")

    global_policy = GlobalPolicy(
        start_min_free_bytes=_nonnegative_int(
            host["start_min_free_bytes"], "start_min_free_bytes"
        ),
        start_min_free_percent=_fraction(host["start_min_free_percent"], "start_min_free_percent"),
        runtime_min_free_bytes=_positive_int(host["runtime_min_free_bytes"], "runtime_min_free_bytes"),
        runtime_min_free_percent=_fraction(
            host["runtime_min_free_percent"], "runtime_min_free_percent"
        ),
        require_swap_metric=_strict_bool(host.get("require_swap_metric", True), "require_swap_metric"),
        log_max_bytes=_positive_int(logging["max_bytes"], "logging.max_bytes"),
        log_backups=_positive_int(logging["backups"], "logging.backups"),
    )
    if (
        global_policy.start_min_free_bytes != 0
        or global_policy.start_min_free_percent != 0.10
    ):
        raise ValueError("host 啟動門檻必須只採用全域 10%，不得設定固定 GiB 下限")
    raw = jobs[job]
    meter_paths = tuple(
        _relative_path(item, "meter_paths") for item in _string_list(raw["meter_paths"], "meter_paths")
    )
    write_paths = tuple(
        _relative_path(item, "registered_write_paths")
        for item in _string_list(raw["registered_write_paths"], "registered_write_paths")
    )
    cleanup_rule_ids = _string_list(raw["cleanup_rule_ids"], "cleanup_rule_ids")
    job_policy = JobPolicy(
        job=job,
        launch_verified=_strict_bool(raw["launch_verified"], f"{job}.launch_verified"),
        verification_basis=raw["verification_basis"]
        if isinstance(raw["verification_basis"], str)
        else "",
        meter_paths=meter_paths,
        registered_write_paths=write_paths,
        cleanup_rule_ids=cleanup_rule_ids,
        max_bytes=_positive_int(raw["max_bytes"], f"{job}.max_bytes"),
        max_file_count=_positive_int(raw["max_file_count"], f"{job}.max_file_count"),
        max_process_tree_rss_bytes=_positive_int(
            raw["max_process_tree_rss_bytes"],
            f"{job}.max_process_tree_rss_bytes",
        ),
        max_swap_growth_bytes=_positive_int(
            raw["max_swap_growth_bytes"],
            f"{job}.max_swap_growth_bytes",
        ),
        expected_growth_bytes_per_hour=_positive_int(
            raw["expected_growth_bytes_per_hour"], f"{job}.expected_growth_bytes_per_hour"
        ),
        spike_window_seconds=_positive_int(raw["spike_window_seconds"], f"{job}.spike_window_seconds"),
        stabilize_after_seconds=_positive_int(
            raw["stabilize_after_seconds"], f"{job}.stabilize_after_seconds"
        ),
        reclaim_after_seconds=_positive_int(raw["reclaim_after_seconds"], f"{job}.reclaim_after_seconds"),
        retention_days=_positive_int(raw["retention_days"], f"{job}.retention_days"),
        sample_interval_seconds=_positive_int(
            raw["sample_interval_seconds"], f"{job}.sample_interval_seconds"
        ),
    )
    if job_policy.sample_interval_seconds > 300:
        raise ValueError(f"{job}.sample_interval_seconds 不得超過 300")
    if not job_policy.verification_basis.strip():
        raise ValueError(f"{job}.verification_basis 不得為空")

    rules: list[RetentionRule] = []
    for rule_id in cleanup_rule_ids:
        value = rules_payload.get(rule_id)
        if not isinstance(value, dict):
            raise ValueError(f"找不到 cleanup rule: {rule_id}")
        rule_base_path = str(value["base_path"]).replace("{job}", job)
        if "{" in rule_base_path or "}" in rule_base_path:
            raise ValueError(f"{rule_id}.base_path 含不支援的 placeholder")
        rules.append(
            RetentionRule(
                rule_id=rule_id,
                base_path=_relative_path(rule_base_path, f"{rule_id}.base_path"),
                pattern=value["pattern"] if isinstance(value["pattern"], str) else "",
                retention_seconds=_positive_int(value["retention_seconds"], f"{rule_id}.retention_seconds"),
                max_files=_positive_int(value["max_files"], f"{rule_id}.max_files"),
                max_bytes=_positive_int(value["max_bytes"], f"{rule_id}.max_bytes"),
                protect_newest=max(0, int(value.get("protect_newest", 1))),
            )
        )
        if not rules[-1].pattern:
            raise ValueError(f"{rule_id}.pattern 不得為空")
    return global_policy, job_policy, tuple(rules)


def _safe_root_path(root: Path, relative: str) -> Path:
    root = root.resolve()
    relative_path = _relative_path(relative, "path")
    candidate = root / relative_path
    current = root
    for part in Path(relative_path).parts:
        current /= part
        if current.is_symlink():
            raise ValueError(f"path 不得包含 symlink: {relative_path}")
    candidate = candidate.resolve()
    candidate.relative_to(root)
    return candidate


def _iter_regular_files(base: Path) -> Iterable[Path]:
    if not base.exists():
        return
    if base.is_symlink():
        raise ValueError(f"meter path 不得是 symlink: {base}")
    if base.is_file():
        yield base
        return
    if not base.is_dir():
        return
    for directory, dirnames, filenames in os.walk(base, followlinks=False):
        dirnames[:] = sorted(
            name
            for name in dirnames
            if name not in IGNORED_PROJECT_DIRS and not (Path(directory) / name).is_symlink()
        )
        for name in sorted(filenames):
            path = Path(directory) / name
            if path.is_symlink():
                continue
            if path.is_file():
                yield path


def measure_paths(root: Path, meter_paths: Sequence[str]) -> Inventory:
    """量測登記 scope；重疊的 meter path 只計一次。"""

    canonical_root = root.resolve()
    bases: list[Path] = []
    for relative in meter_paths:
        base = _safe_root_path(canonical_root, relative)
        if any(base == existing or base.is_relative_to(existing) for existing in bases):
            continue
        bases = [
            existing
            for existing in bases
            if existing == base or not existing.is_relative_to(base)
        ]
        bases.append(base)

    seen: set[str] = set()
    total_bytes = 0
    for base in sorted(bases, key=lambda item: (len(item.parts), item.as_posix())):
        for path in _iter_regular_files(base):
            identity = path.relative_to(canonical_root).as_posix()
            if identity in seen:
                continue
            seen.add(identity)
            total_bytes += path.stat().st_size
    return Inventory(bytes=total_bytes, file_count=len(seen))


def project_write_snapshot(
    root: Path,
    *,
    max_files: int | None = None,
) -> dict[str, tuple[int, int]]:
    """建立 repo 內可觀察檔案快照，用於偵測未登記寫入。"""

    root = root.resolve()
    snapshot: dict[str, tuple[int, int]] = {}
    for path in _iter_regular_files(root):
        relative = path.relative_to(root)
        if relative.parts and relative.parts[0] in IGNORED_PROJECT_DIRS:
            continue
        if max_files is not None and len(snapshot) >= max_files:
            raise RuntimeError("protected root snapshot 超過檔案上限")
        stat = path.stat()
        snapshot[relative.as_posix()] = (stat.st_size, stat.st_mtime_ns)
    return snapshot


def unknown_changed_paths(
    before: dict[str, tuple[int, int]],
    after: dict[str, tuple[int, int]],
    registered_write_paths: Sequence[str],
) -> tuple[str, ...]:
    prefixes = tuple(Path(item).parts for item in registered_write_paths)
    changed: list[str] = []
    for relative in before.keys() | after.keys():
        if before.get(relative) == after.get(relative):
            continue
        parts = Path(relative).parts
        if not any(parts[: len(prefix)] == prefix for prefix in prefixes):
            changed.append(relative)
    return tuple(sorted(changed))


def registered_changed_paths_outside_meter(
    before: dict[str, tuple[int, int]],
    after: dict[str, tuple[int, int]],
    registered_write_paths: Sequence[str],
    meter_paths: Sequence[str],
) -> tuple[str, ...]:
    """找出已登記 write root 內、卻未受任何 meter 管理的變更。"""

    registered_prefixes = tuple(Path(item).parts for item in registered_write_paths)
    meter_prefixes = tuple(Path(item).parts for item in meter_paths)
    changed: list[str] = []
    for relative in before.keys() | after.keys():
        if before.get(relative) == after.get(relative):
            continue
        parts = Path(relative).parts
        is_registered = any(
            parts[: len(prefix)] == prefix for prefix in registered_prefixes
        )
        is_metered = any(parts[: len(prefix)] == prefix for prefix in meter_prefixes)
        if is_registered and not is_metered:
            changed.append(relative)
    return tuple(sorted(changed))


_SWAP_PATTERN = re.compile(r"used\s*=\s*([0-9.]+)([KMGTP])", re.IGNORECASE)


def read_swap_bytes() -> int | None:
    """讀取 macOS swap；不可讀時回傳 None，由 fail-closed policy 判定。"""

    try:
        completed = subprocess.run(
            ["/usr/sbin/sysctl", "-n", "vm.swapusage"],
            text=True,
            capture_output=True,
            check=False,
            timeout=_HOST_PROBE_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    match = _SWAP_PATTERN.search(completed.stdout)
    if not match:
        return None
    scales = {"K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4, "P": 1024**5}
    return int(float(match.group(1)) * scales[match.group(2).upper()])


def read_memory_pressure_level(
    command: Sequence[str] = ("/usr/sbin/sysctl", "-n", "kern.memorystatus_vm_pressure_level"),
) -> int | None:
    """讀取 macOS XNU memory pressure level；不可讀或非 0..4 時回傳 None。"""

    if sys.platform != "darwin":
        return None
    try:
        completed = subprocess.run(
            list(command),
            text=True,
            capture_output=True,
            check=False,
            timeout=_HOST_PROBE_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    raw = completed.stdout.strip()
    if not re.fullmatch(r"[0-4]", raw):
        return None
    return int(raw)


def process_tree_rss_snapshot(
    root_pid: int | None,
) -> tuple[int | None, tuple[ProcessRssAttribution, ...]]:
    if root_pid is None or root_pid <= 0:
        return 0, ()
    try:
        completed = subprocess.run(
            ["/bin/ps", "-axo", "pid=,ppid=,rss=,command="],
            text=True,
            capture_output=True,
            check=False,
            timeout=_HOST_PROBE_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None, ()
    if completed.returncode != 0:
        return None, ()
    parents: dict[int, list[int]] = defaultdict(list)
    processes: dict[int, ProcessRssAttribution] = {}
    for line in completed.stdout.splitlines():
        fields = line.split(maxsplit=3)
        if len(fields) != 4:
            continue
        try:
            pid, parent, rss_kib = (int(item) for item in fields[:3])
        except ValueError:
            continue
        parents[parent].append(pid)
        processes[pid] = ProcessRssAttribution(
            pid=pid,
            ppid=parent,
            rss_bytes=rss_kib * 1024,
            command=fields[3],
        )
    if root_pid not in processes:
        return None, ()
    queue = deque([root_pid])
    seen: set[int] = set()
    attribution: list[ProcessRssAttribution] = []
    while queue:
        pid = queue.popleft()
        if pid in seen:
            continue
        seen.add(pid)
        process = processes.get(pid)
        if process is not None:
            attribution.append(process)
        queue.extend(parents.get(pid, []))
    return sum(process.rss_bytes for process in attribution), tuple(attribution)


def process_tree_rss_bytes(root_pid: int | None) -> int | None:
    rss_bytes, _ = process_tree_rss_snapshot(root_pid)
    return rss_bytes


def take_sample(root: Path, policy: JobPolicy, process_pid: int | None = None) -> Sample:
    sample_started_at = time.monotonic()
    timings: list[ProbeTiming] = []

    def timed_probe(
        name: str,
        operation: Callable[[], Any],
        *,
        available: Callable[[Any], bool] = lambda value: value is not None,
    ) -> Any:
        started_at = time.monotonic()
        value = operation()
        timings.append(
            ProbeTiming(
                probe=name,
                duration_seconds=max(0.0, time.monotonic() - started_at),
                available=available(value),
            )
        )
        return value

    inventory = timed_probe(
        "meter_paths",
        lambda: measure_paths(root, policy.meter_paths),
        available=lambda _value: True,
    )
    disk = timed_probe(
        "disk_usage",
        lambda: shutil.disk_usage(root),
        available=lambda _value: True,
    )
    rss_bytes, process_rss_attribution = timed_probe(
        "process_tree_rss",
        lambda: process_tree_rss_snapshot(process_pid),
        available=lambda value: value[0] is not None,
    )
    swap_bytes = timed_probe("swap", read_swap_bytes)
    memory_pressure_level = timed_probe(
        "memory_pressure",
        read_memory_pressure_level,
    )
    timings.append(
        ProbeTiming(
            probe="sample_total",
            duration_seconds=max(0.0, time.monotonic() - sample_started_at),
            available=True,
        )
    )
    return Sample(
        timestamp=time.time(),
        project_bytes=inventory.bytes,
        project_file_count=inventory.file_count,
        host_total_bytes=disk.total,
        host_free_bytes=disk.free,
        rss_bytes=rss_bytes,
        swap_bytes=swap_bytes,
        memory_pressure_level=memory_pressure_level,
        process_rss_attribution=process_rss_attribution,
        probe_timings=tuple(timings),
    )


def _free_threshold(total: int, minimum_bytes: int, minimum_percent: float) -> int:
    return max(minimum_bytes, int(total * minimum_percent))


def evaluate_preflight(
    global_policy: GlobalPolicy,
    policy: JobPolicy,
    sample: Sample,
    *,
    validation_only: bool = False,
) -> StopDecision:
    """判斷是否可啟動；validation-only 只略過 production launch 驗證旗標。"""

    reasons: list[str] = []
    if not policy.launch_verified and not validation_only:
        reasons.append("POLICY_NOT_LIVE_VERIFIED")
    if sample.project_bytes > policy.max_bytes:
        reasons.append("PROJECT_BYTES_BUDGET_EXCEEDED")
    if sample.project_file_count > policy.max_file_count:
        reasons.append("PROJECT_FILE_COUNT_BUDGET_EXCEEDED")
    threshold = _free_threshold(
        sample.host_total_bytes,
        global_policy.start_min_free_bytes,
        global_policy.start_min_free_percent,
    )
    if sample.host_free_bytes < threshold:
        reasons.append("HOST_START_FREE_SPACE_BELOW_THRESHOLD")
    if global_policy.require_swap_metric and sample.swap_bytes is None:
        reasons.append("SWAP_METRIC_UNAVAILABLE")
    if sample.memory_pressure_level is not None and sample.memory_pressure_level >= 3:
        reasons.append("HOST_MEMORY_PRESSURE_CRITICAL_OR_JETSAM")
    return StopDecision(bool(reasons), tuple(reasons))


def _growth_rate(left: Sample, right: Sample) -> float:
    elapsed = right.timestamp - left.timestamp
    if elapsed <= 0:
        return 0.0
    return max(0, right.project_bytes - left.project_bytes) * 3600 / elapsed


def evaluate_runtime(
    global_policy: GlobalPolicy,
    policy: JobPolicy,
    samples: Sequence[Sample],
    *,
    unknown_paths: Sequence[str] = (),
    registered_unmetered_paths: Sequence[str] = (),
) -> StopDecision:
    if not samples:
        return StopDecision(True, ("MISSING_RUNTIME_SAMPLE",))
    latest = samples[-1]
    live_samples = [sample for sample in samples if sample.phase == "live"]
    reasons: list[str] = []
    if latest.project_bytes > policy.max_bytes:
        reasons.append("PROJECT_BYTES_BUDGET_EXCEEDED")
    if latest.project_file_count > policy.max_file_count:
        reasons.append("PROJECT_FILE_COUNT_BUDGET_EXCEEDED")
    reserve = _free_threshold(
        latest.host_total_bytes,
        global_policy.runtime_min_free_bytes,
        global_policy.runtime_min_free_percent,
    )
    if latest.host_free_bytes < reserve:
        reasons.append("HOST_RUNTIME_FREE_SPACE_BELOW_THRESHOLD")
    if global_policy.require_swap_metric and any(
        sample.swap_bytes is None for sample in live_samples
    ):
        reasons.append("SWAP_METRIC_UNAVAILABLE")
    if any(sample.rss_bytes is None for sample in live_samples):
        reasons.append("RSS_METRIC_UNAVAILABLE")
    has_valid_live_sample = any(
        sample.rss_bytes is not None
        and (not global_policy.require_swap_metric or sample.swap_bytes is not None)
        for sample in live_samples
    )
    if not has_valid_live_sample:
        reasons.append("MISSING_VALID_LIVE_RESOURCE_SAMPLE")
    observed_rss = [
        sample.rss_bytes for sample in live_samples if sample.rss_bytes is not None
    ]
    if observed_rss and max(observed_rss) > policy.max_process_tree_rss_bytes:
        reasons.append("PROCESS_TREE_RSS_BUDGET_EXCEEDED")
    baseline_swap = samples[0].swap_bytes
    observed_swap = [
        sample.swap_bytes for sample in live_samples if sample.swap_bytes is not None
    ]
    swap_growth_budget_exceeded = (
        baseline_swap is not None
        and observed_swap
        and max(observed_swap) - baseline_swap > policy.max_swap_growth_bytes
    )
    latest_live = live_samples[-1] if live_samples else None
    if (
        swap_growth_budget_exceeded
        and latest_live is not None
        and latest_live.memory_pressure_level is None
    ):
        reasons.append("MEMORY_PRESSURE_METRIC_UNAVAILABLE_SWAP_GROWTH_BUDGET_EXCEEDED")
    recent_pressure = [sample.memory_pressure_level for sample in live_samples[-2:]]
    if len(recent_pressure) == 2 and all(
        level is not None and level >= 3 for level in recent_pressure
    ):
        reasons.append("MEMORY_PRESSURE_CRITICAL_OR_JETSAM")
    if unknown_paths:
        reasons.append("UNREGISTERED_WRITE_PATH")
    if registered_unmetered_paths:
        reasons.append("REGISTERED_WRITE_OUTSIDE_METER")

    if len(samples) >= 3:
        recent = samples[-3:]
        rates = [_growth_rate(recent[0], recent[1]), _growth_rate(recent[1], recent[2])]
        over_rate = all(rate > policy.expected_growth_bytes_per_hour * 2 for rate in rates)
        elapsed = max(0.0, latest.timestamp - samples[0].timestamp)
        seconds_to_reclaim = max(0.0, policy.reclaim_after_seconds - elapsed)
        projected_growth = max(rates) * seconds_to_reclaim / 3600
        if elapsed >= policy.spike_window_seconds and over_rate and (
            latest.project_bytes + projected_growth > policy.max_bytes
            or latest.host_free_bytes - projected_growth < reserve
        ):
            reasons.append("SUSTAINED_GROWTH_RATE_WILL_BREAK_BUDGET")
        if (
            elapsed >= policy.stabilize_after_seconds
            and recent[0].project_bytes < recent[1].project_bytes < recent[2].project_bytes
        ):
            reasons.append("NO_STABILIZATION_OR_RECLAIM")
        recent_live = live_samples[-3:]
        swaps = [item.swap_bytes for item in recent_live]
        rss_values = [item.rss_bytes for item in recent_live]
        pressure_values = [item.memory_pressure_level for item in recent_live]
        if (
            len(recent_live) == 3
            and all(value is None for value in pressure_values)
            and all(value is not None for value in rss_values)
            and int(rss_values[0]) < int(rss_values[1]) < int(rss_values[2])
            and all(value is not None for value in swaps)
            and int(swaps[0]) < int(swaps[1]) < int(swaps[2])
        ):
            reasons.append("RSS_AND_SWAP_RISING")
    return StopDecision(bool(reasons), tuple(dict.fromkeys(reasons)))


def _rule_files(root: Path, rule: RetentionRule) -> list[Path]:
    base = _safe_root_path(root, rule.base_path)
    if not base.exists():
        return []
    if base.is_symlink():
        raise ValueError(f"cleanup base 不得是 symlink: {rule.base_path}")
    paths = []
    for path in base.glob(rule.pattern):
        if not path.is_file() or path.is_symlink():
            continue
        path.resolve().relative_to(base.resolve())
        paths.append(path)
    return sorted(paths, key=lambda item: (item.stat().st_mtime_ns, item.as_posix()), reverse=True)


def reclaim_allowlisted(
    root: Path,
    rules: Sequence[RetentionRule],
    *,
    execute: bool,
    now: float | None = None,
) -> ReclaimResult:
    """依 allowlist 輪替；只有 execute=True 才會移除可重建檔案。"""

    observed_at = time.time() if now is None else now
    all_files: dict[Path, os.stat_result] = {}
    removable: set[Path] = set()
    for rule in rules:
        kept_count = 0
        kept_bytes = 0
        for index, path in enumerate(_rule_files(root, rule)):
            stat = path.stat()
            all_files[path] = stat
            age = max(0.0, observed_at - stat.st_mtime)
            within_caps = kept_count < rule.max_files and kept_bytes + stat.st_size <= rule.max_bytes
            protected = index < rule.protect_newest
            if protected or (age <= rule.retention_seconds and within_caps):
                kept_count += 1
                kept_bytes += stat.st_size
            else:
                removable.add(path)
    before_bytes = sum(stat.st_size for stat in all_files.values())
    removed_paths = tuple(
        sorted(path.resolve().relative_to(root.resolve()).as_posix() for path in removable)
    )
    if execute:
        for path in sorted(removable, key=lambda item: len(item.parts), reverse=True):
            path.unlink()
        bases = {_safe_root_path(root, rule.base_path) for rule in rules}
        for base in bases:
            directories = sorted(
                (path for path in base.rglob("*") if path.is_dir() and not path.is_symlink()),
                key=lambda item: len(item.parts),
                reverse=True,
            )
            for directory in directories:
                try:
                    directory.rmdir()
                except OSError:
                    pass
    after_bytes = before_bytes - sum(all_files[path].st_size for path in removable) if execute else before_bytes
    after_count = len(all_files) - len(removable) if execute else len(all_files)
    return ReclaimResult(
        bytes_before=before_bytes,
        bytes_after=after_bytes,
        file_count_before=len(all_files),
        file_count_after=after_count,
        removed_paths=removed_paths,
        dry_run=not execute,
    )


def _materialize_active_runtime_workspace(root: Path, job: str) -> None:
    """reclaim 後重建本次 invocation 在 child spawn 前必須存在的 runtime 目錄。"""

    runtime_root = root / "logs" / "storage_safety" / "runtime" / job
    for path in (
        runtime_root / "tmp" / "joblib",
        runtime_root / "cache" / "uv",
        runtime_root / "cache" / "xdg",
        runtime_root / "cache" / "matplotlib",
    ):
        path.mkdir(parents=True, exist_ok=True)


class RotatingLog:
    """在寫入前輪替，確保 guard 自己的 log 有硬上限。"""

    def __init__(self, path: Path, max_bytes: int, backups: int) -> None:
        self.path = path
        self.max_bytes = max_bytes
        self.backups = backups
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("ab")
        self._lock = threading.Lock()

    def _rotate(self) -> None:
        self._handle.close()
        oldest = self.path.with_name(f"{self.path.name}.{self.backups}")
        if oldest.exists():
            oldest.unlink()
        for index in range(self.backups - 1, 0, -1):
            source = self.path.with_name(f"{self.path.name}.{index}")
            if source.exists():
                source.replace(self.path.with_name(f"{self.path.name}.{index + 1}"))
        if self.path.exists():
            self.path.replace(self.path.with_name(f"{self.path.name}.1"))
        self._handle = self.path.open("ab")

    def write(self, data: bytes) -> None:
        with self._lock:
            if len(data) > self.max_bytes:
                data = data[-self.max_bytes :]
            if self._handle.tell() + len(data) > self.max_bytes:
                self._rotate()
            self._handle.write(data)
            self._handle.flush()

    def close(self) -> None:
        with self._lock:
            self._handle.close()


def _existing_lexical_directory(path: Path, field: str) -> Path:
    """拒絕 lexical path 任一 symlink component，避免 resolve 後隱藏跳轉。"""

    lexical = Path(os.path.abspath(path))
    current = Path(lexical.anchor)
    for part in lexical.parts[1:]:
        current /= part
        if current.is_symlink():
            raise ValueError(f"{field} 不得包含 symlink")
    resolved = lexical.resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError(f"{field} 必須是存在的目錄")
    return resolved


def _existing_lexical_file_under_root(root: Path, path: Path, field: str) -> Path:
    lexical_root = Path(os.path.abspath(root))
    candidate = path if path.is_absolute() else lexical_root / path
    lexical = Path(os.path.abspath(candidate))
    try:
        relative = lexical.relative_to(lexical_root)
    except ValueError as exc:
        raise UntrustedValidationEntrypoint(f"{field} 必須位於 sandbox 內") from exc
    current = lexical_root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise UntrustedValidationEntrypoint(f"{field} 不得包含 symlink")
    try:
        resolved = lexical.resolve(strict=True)
    except FileNotFoundError as exc:
        raise UntrustedValidationEntrypoint(f"{field} 不存在") from exc
    resolved.relative_to(lexical_root.resolve())
    if not resolved.is_file():
        raise UntrustedValidationEntrypoint(f"{field} 必須是 regular file")
    return resolved


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_trusted_validation_entrypoint(
    sandbox_root: Path,
    job: str,
    marker: dict[str, Any],
    contract_path: Path,
) -> TrustedValidationEntrypoint:
    """由 marker pin 的 contract 建立固定 Python entrypoint；不接受 raw command。"""

    root = _existing_lexical_directory(sandbox_root, "sandbox_root")
    registrations = marker.get("trusted_entrypoints")
    registration = registrations.get(job) if isinstance(registrations, dict) else None
    if not isinstance(registration, dict):
        raise UntrustedValidationEntrypoint("marker 未登記 trusted entrypoint")
    registered_path = registration.get("contract_path")
    registered_digest = registration.get("contract_sha256")
    if not isinstance(registered_path, str) or not isinstance(registered_digest, str):
        raise UntrustedValidationEntrypoint("marker trusted entrypoint registration 不完整")

    contract = _existing_lexical_file_under_root(root, contract_path, "entrypoint contract")
    relative_contract = contract.relative_to(root).as_posix()
    if relative_contract != registered_path:
        raise UntrustedValidationEntrypoint("entrypoint contract path 未登記")
    actual_contract_digest = _sha256_file(contract)
    if not hmac.compare_digest(actual_contract_digest, registered_digest):
        raise UntrustedValidationEntrypoint("entrypoint contract digest 不符")
    try:
        payload = json.loads(contract.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UntrustedValidationEntrypoint("entrypoint contract 不是有效 JSON") from exc
    if payload.get("schema_version") != VALIDATION_ENTRYPOINT_SCHEMA_VERSION:
        raise UntrustedValidationEntrypoint("entrypoint contract schema_version 不符")
    if payload.get("job") != job:
        raise UntrustedValidationEntrypoint("entrypoint contract job 不符")
    if payload.get("interpreter") != "python-isolated":
        raise UntrustedValidationEntrypoint("entrypoint contract interpreter 不受信任")

    entrypoint_value = payload.get("entrypoint")
    entrypoint_digest = payload.get("entrypoint_sha256")
    argv_value = payload.get("argv")
    if not isinstance(entrypoint_value, str) or not isinstance(entrypoint_digest, str):
        raise UntrustedValidationEntrypoint("entrypoint contract 缺少 entrypoint digest")
    if not isinstance(argv_value, list) or not all(
        isinstance(item, str) and "\0" not in item for item in argv_value
    ):
        raise UntrustedValidationEntrypoint("entrypoint contract argv 必須是 string list")
    entrypoint = _existing_lexical_file_under_root(
        root,
        Path(entrypoint_value),
        "trusted entrypoint",
    )
    if entrypoint.suffix != ".py":
        raise UntrustedValidationEntrypoint("trusted entrypoint 必須是 Python file")
    actual_entrypoint_digest = _sha256_file(entrypoint)
    if not hmac.compare_digest(actual_entrypoint_digest, entrypoint_digest):
        raise UntrustedValidationEntrypoint("trusted entrypoint digest 不符")
    argv = tuple(argv_value)
    command = (sys.executable, "-I", str(entrypoint), *argv)
    return TrustedValidationEntrypoint(
        job=job,
        sandbox_root=root,
        contract_path=contract,
        contract_sha256=actual_contract_digest,
        entrypoint_path=entrypoint,
        entrypoint_sha256=actual_entrypoint_digest,
        argv=argv,
        command=command,
        _trust_token=_TRUSTED_VALIDATION_TOKEN,
    )


def _verify_trusted_validation_entrypoint(
    trusted: TrustedValidationEntrypoint | None,
    *,
    root: Path,
    job: str,
    command: Sequence[str],
) -> TrustedValidationEntrypoint:
    if trusted is None or trusted._trust_token is not _TRUSTED_VALIDATION_TOKEN:
        raise UntrustedValidationEntrypoint("validation-only 禁止 raw command")
    if trusted.job != job or trusted.sandbox_root != root:
        raise UntrustedValidationEntrypoint("trusted entrypoint scope 不符")
    if tuple(command) != trusted.command:
        raise UntrustedValidationEntrypoint("validation command 與 pinned contract 不符")
    if not hmac.compare_digest(_sha256_file(trusted.contract_path), trusted.contract_sha256):
        raise UntrustedValidationEntrypoint("entrypoint contract spawn 前 digest 改變")
    if not hmac.compare_digest(_sha256_file(trusted.entrypoint_path), trusted.entrypoint_sha256):
        raise UntrustedValidationEntrypoint("trusted entrypoint spawn 前 digest 改變")
    expected = (sys.executable, "-I", str(trusted.entrypoint_path), *trusted.argv)
    if trusted.command != expected:
        raise UntrustedValidationEntrypoint("trusted entrypoint command shape 不符")
    return trusted


def _materialize_trusted_validation_entrypoint(
    trusted: TrustedValidationEntrypoint,
) -> tuple[tempfile.TemporaryDirectory[str], list[str]]:
    """以已驗證 bytes 建立 child 不可寫的短命 execution copy，封住 digest TOCTOU。"""

    source = trusted.entrypoint_path.read_bytes()
    if not hmac.compare_digest(hashlib.sha256(source).hexdigest(), trusted.entrypoint_sha256):
        raise UntrustedValidationEntrypoint("trusted entrypoint materialize 前 digest 改變")
    runtime = tempfile.TemporaryDirectory(prefix="top10-storage-trusted-entrypoint-")
    materialized = Path(runtime.name) / "entrypoint.py"
    materialized.write_bytes(source)
    materialized.chmod(0o400)
    command = [sys.executable, "-I", str(materialized), *trusted.argv]
    return runtime, command


def _sandbox_profile(write_root: Path) -> str:
    quoted_root = json.dumps(str(write_root), ensure_ascii=False)
    quoted_dev_null = json.dumps("/dev/null")
    return "\n".join(
        (
            "(version 1)",
            "(deny default)",
            "(allow file-read*)",
            "(allow process-exec)",
            "(allow process-fork)",
            "(allow signal (target same-sandbox))",
            "(allow sysctl-read)",
            "(allow mach-lookup)",
            f"(allow file-read* file-write* (literal {quoted_dev_null}))",
            f"(allow file-write* (subpath {quoted_root}))",
        )
    )


def _validation_spawn_command(
    sandbox_root: Path,
    source_root: Path,
    command: Sequence[str],
) -> list[str]:
    """驗證 macOS Seatbelt 能阻擋 scope 外寫入，再回傳受限 child command。"""

    sandbox_root = _existing_lexical_directory(sandbox_root, "sandbox_root")
    source_root = _existing_lexical_directory(source_root, "source_input_root")
    try:
        source_root.relative_to(sandbox_root)
    except ValueError:
        pass
    else:
        raise ValueError("source_input_root 不得位於可寫 sandbox 內")
    if not SANDBOX_EXECUTABLE.is_file() or not os.access(SANDBOX_EXECUTABLE, os.X_OK):
        raise RuntimeError("VALIDATION_CONFINEMENT_UNAVAILABLE")

    profile = _sandbox_profile(sandbox_root)
    probe_root = sandbox_root / "logs" / "storage_safety" / "confinement_probe"
    probe_root.mkdir(parents=True, exist_ok=True)
    allowed_probe = probe_root / "allowed"
    allowed_probe.unlink(missing_ok=True)
    # validation runtime 會把 TMPDIR 收斂到 sandbox；禁止依賴 tempfile 的
    # process-global cache，否則「禁止寫入」探針也會落入允許寫入的 sandbox。
    with tempfile.TemporaryDirectory(
        prefix="top10-storage-confinement-probe-",
        dir=sandbox_root.parent,
    ) as tmp:
        forbidden_probe = Path(tmp) / "forbidden"
        completed = subprocess.run(
            [
                str(SANDBOX_EXECUTABLE),
                "-p",
                profile,
                "/bin/sh",
                "-c",
                'printf discarded > /dev/null || exit 91; printf allowed > "$1" || exit 92; if printf forbidden > "$2" 2>/dev/null; then exit 93; fi',
                "confinement-probe",
                str(allowed_probe),
                str(forbidden_probe),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        probe_ok = (
            completed.returncode == 0
            and allowed_probe.read_text(encoding="utf-8") == "allowed"
            and not forbidden_probe.exists()
        )
    allowed_probe.unlink(missing_ok=True)
    if not probe_ok:
        raise RuntimeError("VALIDATION_CONFINEMENT_PROBE_FAILED")
    return [str(SANDBOX_EXECUTABLE), "-p", profile, *command]


def _process_start_token(pid: int) -> str:
    completed = subprocess.run(
        ["/bin/ps", "-o", "lstart=", "-p", str(pid)],
        text=True,
        capture_output=True,
        check=False,
    )
    token = completed.stdout.strip()
    if completed.returncode != 0 or not token:
        raise RuntimeError("無法取得 process group leader identity")
    return token


def capture_process_group_identity(process: subprocess.Popen[bytes]) -> ProcessGroupIdentity:
    """在 leader 存活時鎖定 group/session 與 start token。"""

    if process.poll() is not None:
        raise RuntimeError("process group leader 已退出，無法建立 identity")
    group_id = os.getpgid(process.pid)
    session_id = os.getsid(process.pid)
    if group_id != process.pid or session_id != process.pid:
        raise RuntimeError("child process group 不符合隔離契約")
    return ProcessGroupIdentity(
        leader_pid=process.pid,
        group_id=group_id,
        session_id=session_id,
        leader_start_token=_process_start_token(process.pid),
    )


def _verified_process_group_members(identity: ProcessGroupIdentity) -> tuple[int, ...]:
    completed = subprocess.run(
        ["/bin/ps", "-axo", "pid=,pgid=,stat="],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError("無法驗證 process group membership")
    members: list[int] = []
    for line in completed.stdout.splitlines():
        fields = line.split()
        if len(fields) < 3:
            continue
        try:
            pid, group_id = (int(item) for item in fields[:2])
        except ValueError:
            continue
        if group_id != identity.group_id or fields[2].startswith("Z"):
            continue
        try:
            session_id = os.getsid(pid)
        except ProcessLookupError:
            continue
        if session_id != identity.session_id:
            raise RuntimeError("process group identity 不符，拒絕盲目送 signal")
        if pid == identity.leader_pid:
            current_token = _process_start_token(pid)
            if current_token != identity.leader_start_token:
                raise RuntimeError("process group leader PID 已被重用")
        members.append(pid)
    return tuple(sorted(members))


def process_group_is_quiescent(identity: ProcessGroupIdentity) -> bool:
    return not _verified_process_group_members(identity)


def terminate_process_group(
    process: subprocess.Popen[bytes],
    grace_seconds: float = 5.0,
    *,
    identity: ProcessGroupIdentity | None = None,
) -> None:
    """只終止已驗證的 target group；leader 退出後仍追蹤同一 session。"""

    verified = identity or capture_process_group_identity(process)
    if not _verified_process_group_members(verified):
        return

    def signal_verified_group(signum: int) -> None:
        if not _verified_process_group_members(verified):
            return
        try:
            os.killpg(verified.group_id, signum)
        except ProcessLookupError:
            return

    signal_verified_group(signal.SIGTERM)
    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        if process_group_is_quiescent(verified):
            if process.poll() is None:
                process.wait(timeout=max(0.01, deadline - time.monotonic()))
            return
        time.sleep(0.02)
    signal_verified_group(signal.SIGKILL)
    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        if process_group_is_quiescent(verified):
            if process.poll() is None:
                process.wait(timeout=max(0.01, deadline - time.monotonic()))
            return
        time.sleep(0.02)
    raise RuntimeError("target process group 未能 quiesce")


def _spawn_verified_process_group(
    command: Sequence[str],
    *,
    cwd: Path,
) -> tuple[subprocess.Popen[bytes], ProcessGroupIdentity]:
    """先讓可信 bootstrap leader 等待，鎖定 identity 後才 exec 真正 child。"""

    read_fd, write_fd = os.pipe()
    bootstrap = f'IFS= read -r _ <&{read_fd} || exit 125; exec "$@"'
    process: subprocess.Popen[bytes] | None = None
    try:
        process = subprocess.Popen(
            ["/bin/sh", "-c", bootstrap, "storage-guard-bootstrap", *command],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            pass_fds=(read_fd,),
        )
        os.close(read_fd)
        read_fd = -1
        identity = capture_process_group_identity(process)
        os.write(write_fd, b"start\n")
        return process, identity
    except Exception:
        if process is not None:
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=1)
        raise
    finally:
        if read_fd >= 0:
            os.close(read_fd)
        os.close(write_fd)


def _json_document_bytes(payload: dict[str, Any]) -> bytes:
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(_json_document_bytes(payload))
    temporary.replace(path)


def _exclusive_json(path: Path, payload: dict[str, Any]) -> None:
    """以 O_EXCL 建立 invocation claim；殘留 partial file 也必須 fail closed。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(_json_document_bytes(payload))
        handle.flush()
        os.fsync(handle.fileno())


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_invocation_metadata(
    job: str,
    *,
    trigger_type: str | None,
    scheduled_at: str | None,
    invocation_id: str | None,
    validation_only: bool,
) -> tuple[str, str, str]:
    resolved_trigger = "validation" if validation_only else (trigger_type or "manual")
    if resolved_trigger not in {"natural", "manual", "validation"}:
        raise ValueError("trigger_type 必須是 natural／manual／validation")
    resolved_scheduled_at = scheduled_at or _utc_timestamp()
    try:
        parsed_scheduled_at = datetime.fromisoformat(resolved_scheduled_at)
    except ValueError as exc:
        raise ValueError("scheduled_at 必須是 ISO-8601 timestamp") from exc
    if parsed_scheduled_at.tzinfo is None:
        raise ValueError("scheduled_at 必須包含 timezone")
    resolved_invocation_id = invocation_id or (
        f"{job}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}-{os.getpid()}"
    )
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", resolved_invocation_id):
        raise ValueError("invocation_id 格式不安全")
    return resolved_trigger, resolved_scheduled_at, resolved_invocation_id


def _write_receipt(
    runtime_dir: Path,
    receipt_path: Path,
    job: str,
    invocation_id: str,
    payload: dict[str, Any],
    *,
    update_latest: bool = True,
    archive_variant: str | None = None,
    claim_token: str | None = None,
) -> Path:
    archive_path = _receipt_archive_path(
        runtime_dir,
        job,
        invocation_id,
        archive_variant=archive_variant,
    )
    if archive_path.exists():
        if claim_token is None or not _invocation_claim_matches(
            archive_path,
            job=job,
            invocation_id=invocation_id,
            claim_token=claim_token,
        ):
            raise FileExistsError(f"invocation receipt 已存在: {archive_path.stem}")
    elif claim_token is not None:
        raise FileNotFoundError(f"invocation claim 已遺失: {archive_path.stem}")
    _atomic_json(archive_path, payload)
    if update_latest:
        _atomic_json(receipt_path, payload)
    return archive_path


def _receipt_archive_path(
    runtime_dir: Path,
    job: str,
    invocation_id: str,
    *,
    archive_variant: str | None = None,
) -> Path:
    archive_stem = (
        invocation_id
        if archive_variant is None
        else f"{invocation_id}.{archive_variant}"
    )
    return runtime_dir / "receipts" / job / f"{archive_stem}.json"


def _reserve_invocation(
    runtime_dir: Path,
    job: str,
    invocation_id: str,
    *,
    trigger_type: str,
    scheduled_at: str,
) -> str:
    claim_token = uuid.uuid4().hex
    _exclusive_json(
        _receipt_archive_path(runtime_dir, job, invocation_id),
        {
            "schema_version": INVOCATION_CLAIM_SCHEMA_VERSION,
            "job": job,
            "invocation_id": invocation_id,
            "claim_token": claim_token,
            "trigger_type": trigger_type,
            "scheduled_at": scheduled_at,
            "claimed_at": _utc_timestamp(),
            "supervisor_pid": os.getpid(),
        },
    )
    return claim_token


def _invocation_claim_matches(
    path: Path,
    *,
    job: str,
    invocation_id: str,
    claim_token: str,
) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return bool(
        isinstance(payload, dict)
        and payload.get("schema_version") == INVOCATION_CLAIM_SCHEMA_VERSION
        and payload.get("job") == job
        and payload.get("invocation_id") == invocation_id
        and isinstance(payload.get("claim_token"), str)
        and hmac.compare_digest(payload["claim_token"], claim_token)
    )


def _unresolved_invocation_archive(
    runtime_dir: Path,
    job: str,
) -> Path | None:
    """回傳未完成 claim；損壞 archive 也視為可能的 partial claim。"""

    receipts_dir = runtime_dir / "receipts" / job
    if not receipts_dir.is_dir():
        return None
    for candidate in sorted(receipts_dir.glob("*.json")):
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return candidate
        if (
            isinstance(payload, dict)
            and payload.get("schema_version") == INVOCATION_CLAIM_SCHEMA_VERSION
        ):
            return candidate
    return None


def _json_payload_sha256(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_json_document_bytes(payload)).hexdigest()


def _receipt_matches_denial_marker(
    raw_receipt: bytes,
    denial: dict[str, Any],
) -> dict[str, Any] | None:
    expected_digest = denial.get("root_receipt_sha256")
    expected_invocation = denial.get("root_invocation_id")
    if not isinstance(expected_digest, str) or not isinstance(expected_invocation, str):
        return None
    if not hmac.compare_digest(hashlib.sha256(raw_receipt).hexdigest(), expected_digest):
        return None
    try:
        payload = json.loads(raw_receipt)
    except (UnicodeDecodeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("invocation_id") != expected_invocation:
        return None
    if payload.get("job") != denial.get("job"):
        return None
    if payload.get("status") != "STOPPED":
        return None
    return payload


def _marker_bound_root_receipt(
    root: Path,
    denial: dict[str, Any],
) -> dict[str, Any] | None:
    candidate = _marker_root_receipt_path(root, denial)
    if candidate is None:
        return None
    try:
        raw_receipt = candidate.read_bytes()
    except OSError:
        return None
    return _receipt_matches_denial_marker(raw_receipt, denial)


def _marker_root_receipt_path(
    root: Path,
    denial: dict[str, Any],
) -> Path | None:
    relative = denial.get("root_receipt_path")
    job = denial.get("job")
    invocation_id = denial.get("root_invocation_id")
    if not all(isinstance(value, str) for value in (relative, job, invocation_id)):
        return None
    parts = Path(relative).parts
    if (
        len(parts) != 5
        or parts[:4] != ("logs", "storage_safety", "receipts", job)
        or parts[4]
        not in {
            f"{invocation_id}.json",
            f"{invocation_id}.recovery.json",
            f"{invocation_id}.marker-write-failed.json",
        }
    ):
        return None
    try:
        return _safe_root_path(root, relative)
    except ValueError:
        return None


def _marker_embedded_root_receipt(
    denial: dict[str, Any],
) -> dict[str, Any] | None:
    payload = denial.get("root_receipt")
    if not isinstance(payload, dict):
        return None
    return _receipt_matches_denial_marker(_json_document_bytes(payload), denial)


def _receipt_payload(
    *,
    policy: JobPolicy,
    command: Sequence[str],
    status: str,
    samples: Sequence[Sample],
    reasons: Sequence[str],
    child_exit_code: int | None,
    reclaimed: ReclaimResult | None,
    validation_only: bool,
    max_runtime_seconds: float | None,
    unknown_paths: Sequence[str],
    validation_context: dict[str, Any] | None,
    registered_unmetered_paths: Sequence[str] = (),
    process_group_identity: ProcessGroupIdentity | None = None,
    final_process_group_quiescent: bool | None = None,
    final_process_group_checked_at: str | None = None,
    trigger_type: str = "manual",
    scheduled_at: str | None = None,
    invocation_id: str = "unknown",
) -> dict[str, Any]:
    first = samples[0] if samples else None
    last = samples[-1] if samples else None
    elapsed_seconds = max(0.0, last.timestamp - first.timestamp) if first and last else 0.0
    growth_rate = (
        max(0, last.project_bytes - first.project_bytes) * 3600 / elapsed_seconds
        if first and last and elapsed_seconds > 0
        else 0.0
    )
    child_spawned = process_group_identity is not None
    natural_origin_candidate = (
        trigger_type == "natural"
        and status == "OK"
        and child_exit_code == 0
        and final_process_group_quiescent is True
    )
    # launchd 的自然 fire 與 manual kickstart 對 child 都呈現 PPID=1；guard
    # 無法自行證明兩者差異，因此不得累加 natural acceptance 證據。
    natural_trigger_verified = False
    consecutive_natural_guard_cycles = 0
    if natural_origin_candidate:
        acceptance_status = "NATURAL_ACCEPTANCE_PENDING"
    elif status in {"STOPPED", "RESTART_DENIED", "NO-GO", "CHILD_FAILED"}:
        acceptance_status = "NO-GO"
    else:
        acceptance_status = "NOT_APPLICABLE"
    return {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "job": policy.job,
        "status": status,
        "scheduled_at": scheduled_at,
        "trigger_type": trigger_type,
        "invocation_id": invocation_id,
        "child_spawned": child_spawned,
        "child_terminal_status": status if child_spawned else None,
        # Storage Guard 只能證明 scheduler／child／process-group 這一層；artifact
        # run date 與 publish/provider terminal result 尚未核對前不得自稱 ACCEPTED。
        "consecutive_natural_guard_cycles": consecutive_natural_guard_cycles,
        "natural_trigger_verified": natural_trigger_verified,
        "accepted_natural_cycles": 0,
        "acceptance_status": acceptance_status,
        "artifact_run_date": None,
        "publish_or_provider_result": None,
        "restart_denied": status in {"STOPPED", "RESTART_DENIED"},
        "restart_denied_marker_persisted": None,
        "restart_denied_reason": (
            list(reasons) if status in {"STOPPED", "RESTART_DENIED"} else []
        ),
        "supervisor_pid": os.getpid(),
        "child_pid": (
            process_group_identity.leader_pid
            if process_group_identity is not None
            else None
        ),
        "lock_owner_status": "HELD_BY_OTHER" if status == "OVERLAP_BLOCKED" else "HELD",
        "last_progress_at": _utc_timestamp(),
        "command": list(command),
        "launch_verified": policy.launch_verified,
        "validation_only": validation_only,
        "max_runtime_seconds": max_runtime_seconds,
        "verification_basis": policy.verification_basis,
        "limits": {
            "max_bytes": policy.max_bytes,
            "max_file_count": policy.max_file_count,
            "max_process_tree_rss_bytes": policy.max_process_tree_rss_bytes,
            "max_swap_growth_bytes": policy.max_swap_growth_bytes,
            "expected_growth_bytes_per_hour": policy.expected_growth_bytes_per_hour,
            "spike_window_seconds": policy.spike_window_seconds,
            "stabilize_after_seconds": policy.stabilize_after_seconds,
            "reclaim_after_seconds": policy.reclaim_after_seconds,
            "retention_days": policy.retention_days,
            "sample_interval_seconds": policy.sample_interval_seconds,
        },
        "samples": [sample.to_dict() for sample in samples],
        "summary": {
            "elapsed_seconds": elapsed_seconds,
            "project_bytes_delta": (
                last.project_bytes - first.project_bytes if first and last else None
            ),
            "project_file_count_delta": (
                last.project_file_count - first.project_file_count if first and last else None
            ),
            "host_free_bytes_delta": (
                last.host_free_bytes - first.host_free_bytes if first and last else None
            ),
            "peak_rss_bytes": max(
                (
                    sample.rss_bytes
                    for sample in samples
                    if sample.phase == "live" and sample.rss_bytes is not None
                ),
                default=None,
            ),
            "swap_bytes_delta": (
                last.swap_bytes - first.swap_bytes
                if first and last and first.swap_bytes is not None and last.swap_bytes is not None
                else None
            ),
            "first_memory_pressure_level": first.memory_pressure_level if first else None,
            "last_memory_pressure_level": last.memory_pressure_level if last else None,
            "peak_live_memory_pressure_level": max(
                (
                    sample.memory_pressure_level
                    for sample in samples
                    if sample.phase == "live" and sample.memory_pressure_level is not None
                ),
                default=None,
            ),
            "observed_growth_bytes_per_hour": growth_rate,
            "unknown_changed_paths": list(unknown_paths),
            "registered_unmetered_changed_paths": list(registered_unmetered_paths),
        },
        "validation_context": validation_context,
        "reasons": list(reasons),
        "child_exit_code": child_exit_code,
        "process_group_identity": (
            asdict(process_group_identity) if process_group_identity is not None else None
        ),
        "final_process_group_quiescent": final_process_group_quiescent,
        "final_process_group_checked_at": final_process_group_checked_at,
        "process_group": {
            "verified_identity": (
                asdict(process_group_identity)
                if process_group_identity is not None
                else None
            ),
            "final_quiescent": final_process_group_quiescent,
            "final_checked_at": final_process_group_checked_at,
        },
        "reclaim": asdict(reclaimed) if reclaimed else None,
    }


def run_guarded_job(
    root: Path,
    global_policy: GlobalPolicy,
    policy: JobPolicy,
    rules: Sequence[RetentionRule],
    command: Sequence[str],
    *,
    sampler: Callable[[int | None], Sample] | None = None,
    validation_only: bool = False,
    max_runtime_seconds: float | None = None,
    validation_context: dict[str, Any] | None = None,
    trusted_validation_entrypoint: TrustedValidationEntrypoint | None = None,
    monotonic_clock: Callable[[], float] | None = None,
    process_waiter: Callable[[subprocess.Popen[bytes], float], int | None] | None = None,
    trigger_type: str | None = None,
    scheduled_at: str | None = None,
    invocation_id: str | None = None,
) -> int:
    """執行單一排程週期；停損時留下 marker，後續嘗試一律拒絕。"""

    if not command:
        raise ValueError("child command 不得為空")
    if max_runtime_seconds is not None and (
        not math.isfinite(max_runtime_seconds) or max_runtime_seconds <= 0
    ):
        raise ValueError("max_runtime_seconds 必須大於 0")
    root = root.resolve()
    runtime_dir = root / "logs" / "storage_safety"
    receipt_path = runtime_dir / f"{policy.job}_latest.json"
    denied_path = runtime_dir / "restart_denied" / f"{policy.job}.json"
    resolved_trigger, resolved_scheduled_at, resolved_invocation_id = (
        _normalize_invocation_metadata(
            policy.job,
            trigger_type=trigger_type,
            scheduled_at=scheduled_at,
            invocation_id=invocation_id,
            validation_only=validation_only,
        )
    )
    claim_token: str | None = None

    def receipt_payload(**kwargs: Any) -> dict[str, Any]:
        return _receipt_payload(
            **kwargs,
            trigger_type=resolved_trigger,
            scheduled_at=resolved_scheduled_at,
            invocation_id=resolved_invocation_id,
        )

    def write_receipt(
        payload: dict[str, Any],
        *,
        update_latest: bool = True,
        archive_variant: str | None = None,
    ) -> Path:
        return _write_receipt(
            runtime_dir,
            receipt_path,
            policy.job,
            resolved_invocation_id,
            payload,
            update_latest=update_latest,
            archive_variant=archive_variant,
            claim_token=(claim_token if archive_variant is None else None),
        )

    samples: list[Sample] = []
    take = sampler or (lambda pid: take_sample(root, policy, pid))
    monotonic_now = monotonic_clock or time.monotonic
    wait_for_process = process_waiter or (
        lambda child, timeout: child.wait(timeout=timeout)
    )
    runtime_dir.mkdir(parents=True, exist_ok=True)
    process: subprocess.Popen[bytes] | None = None
    process_group: ProcessGroupIdentity | None = None
    pump_thread: threading.Thread | None = None
    rotating_log: RotatingLog | None = None
    reclaimed: ReclaimResult | None = None
    protected_before: dict[str, tuple[int, int]] | None = None
    protected_root: Path | None = None
    trusted_entrypoint_runtime: tempfile.TemporaryDirectory[str] | None = None
    previous_signal_handlers: dict[int, Any] = {}
    final_process_group_quiescent: bool | None = None
    final_process_group_checked_at: str | None = None
    stop_reasons: tuple[str, ...] = ()
    observed_unknown_paths: tuple[str, ...] = ()
    observed_registered_unmetered_paths: tuple[str, ...] = ()

    lock_path = runtime_dir / f"{policy.job}.lock"
    lock_handle = lock_path.open("a+")
    try:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        write_receipt(
            receipt_payload(
                policy=policy,
                command=command,
                status="OVERLAP_BLOCKED",
                samples=[],
                reasons=("JOB_LOCK_HELD",),
                child_exit_code=None,
                reclaimed=None,
                validation_only=validation_only,
                max_runtime_seconds=max_runtime_seconds,
                unknown_paths=(),
                validation_context=validation_context,
            ),
        )
        lock_handle.close()
        return 0

    # marker 必須在取得單一 job 的互斥鎖後才檢查，避免前次檢查與啟動 child
    # 之間由另一個 guard 建立 fail-closed evidence。
    if denied_path.exists():
        try:
            # persistent denial 是前次 STOPPED 的後續結果，不能覆寫唯一一份
            # root-cause receipt。原始 reasons／write evidence 由 marker 保留；
            # latest receipt 必須維持在建立 marker 的失敗 invocation。只有 legacy
            # marker 沒有任何 receipt 時，才補一份 RESTART_DENIED 可觀察狀態。
            try:
                denial = json.loads(denied_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                denial = None
            denial_payload = denial if isinstance(denial, dict) else {}
            latest_exists = receipt_path.exists()
            marker_has_root_binding = all(
                isinstance(denial_payload.get(field), str)
                for field in (
                    "root_invocation_id",
                    "root_receipt_path",
                    "root_receipt_sha256",
                )
            )
            if latest_exists and marker_has_root_binding:
                try:
                    latest_raw = receipt_path.read_bytes()
                except OSError:
                    latest_raw = b""
                if _receipt_matches_denial_marker(latest_raw, denial_payload) is not None:
                    return 75
            if marker_has_root_binding:
                root_receipt = _marker_bound_root_receipt(root, denial_payload)
                if root_receipt is not None:
                    _atomic_json(receipt_path, root_receipt)
                    return 75
                embedded_receipt = _marker_embedded_root_receipt(denial_payload)
                embedded_path = _marker_root_receipt_path(root, denial_payload)
                if embedded_receipt is not None and embedded_path is not None:
                    can_restore = not embedded_path.exists()
                    root_claim_token = denial_payload.get("root_claim_token")
                    if (
                        not can_restore
                        and isinstance(root_claim_token, str)
                        and _invocation_claim_matches(
                            embedded_path,
                            job=policy.job,
                            invocation_id=str(denial_payload["root_invocation_id"]),
                            claim_token=root_claim_token,
                        )
                    ):
                        can_restore = True
                    if can_restore:
                        if embedded_path.exists():
                            _atomic_json(embedded_path, embedded_receipt)
                        else:
                            _exclusive_json(embedded_path, embedded_receipt)
                        _atomic_json(receipt_path, embedded_receipt)
                        return 75
            elif latest_exists:
                # 舊 marker 沒有 hash binding；既有 latest 是唯一可保留的 root evidence。
                try:
                    legacy_latest = json.loads(receipt_path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    legacy_latest = None
                if (
                    isinstance(legacy_latest, dict)
                    and legacy_latest.get("status") in {"STOPPED", "RESTART_DENIED"}
                ):
                    return 75

            def marker_strings(field: str) -> tuple[str, ...]:
                value = denial_payload.get(field)
                if not isinstance(value, list):
                    return ()
                return tuple(item for item in value if isinstance(item, str))

            original_reasons = marker_strings("reasons")
            write_receipt(
                receipt_payload(
                    policy=policy,
                    command=command,
                    status="RESTART_DENIED",
                    samples=[],
                    reasons=tuple(
                        dict.fromkeys(
                            (*original_reasons, "PERSISTENT_RESTART_DENIED_MARKER")
                        )
                    ),
                    child_exit_code=None,
                    reclaimed=None,
                    validation_only=validation_only,
                    max_runtime_seconds=max_runtime_seconds,
                    unknown_paths=marker_strings("unknown_changed_paths"),
                    validation_context=validation_context,
                    registered_unmetered_paths=marker_strings(
                        "registered_unmetered_changed_paths"
                    ),
                ),
            )
            return 75
        finally:
            lock_handle.close()

    # denial marker 若持續無法落盤，exception path 會以 latest STOPPED receipt
    # 明確記錄。只有 exact false 才啟用 fallback，避免擋住已由 activation
    # 正式清除 marker 的舊 STOPPED evidence。
    try:
        receipt_only_denial = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        receipt_only_denial = None
    if (
        isinstance(receipt_only_denial, dict)
        and receipt_only_denial.get("job") == policy.job
        and receipt_only_denial.get("status") == "STOPPED"
        and receipt_only_denial.get("restart_denied") is True
        and receipt_only_denial.get("restart_denied_marker_persisted") is False
    ):
        lock_handle.close()
        return 75

    if _unresolved_invocation_archive(runtime_dir, policy.job) is not None:
        lock_handle.close()
        return 75

    try:
        claim_token = _reserve_invocation(
            runtime_dir,
            policy.job,
            resolved_invocation_id,
            trigger_type=resolved_trigger,
            scheduled_at=resolved_scheduled_at,
        )
    except FileExistsError:
        lock_handle.close()
        return 75

    if threading.current_thread() is threading.main_thread():

        def interrupt_guard(signum: int, _frame: Any) -> None:
            raise GuardInterrupted(f"signal={signum}")

        for signum in (signal.SIGTERM, signal.SIGINT):
            previous_signal_handlers[signum] = signal.getsignal(signum)
            signal.signal(signum, interrupt_guard)

    try:
        preflight = replace(take(None), phase="preflight")
        samples.append(preflight)
        preflight_decision = evaluate_preflight(
            global_policy,
            policy,
            preflight,
            validation_only=validation_only,
        )
        if preflight_decision.triggered:
            write_receipt(
                receipt_payload(
                    policy=policy,
                    command=command,
                    status="NO-GO",
                    samples=samples,
                    reasons=preflight_decision.reasons,
                    child_exit_code=None,
                    reclaimed=None,
                    validation_only=validation_only,
                    max_runtime_seconds=max_runtime_seconds,
                    unknown_paths=(),
                    validation_context=validation_context,
                ),
            )
            return 78

        reclaimed = reclaim_allowlisted(root, rules, execute=True)
        _materialize_active_runtime_workspace(root, policy.job)
        before_writes = project_write_snapshot(root)
        spawn_command = list(command)
        if validation_only:
            trusted_validation_entrypoint = _verify_trusted_validation_entrypoint(
                trusted_validation_entrypoint,
                root=root,
                job=policy.job,
                command=command,
            )
            trusted_entrypoint_runtime, trusted_command = (
                _materialize_trusted_validation_entrypoint(trusted_validation_entrypoint)
            )
            if not isinstance(validation_context, dict):
                raise ValueError("validation_context 必須包含 source_input_root")
            source_value = validation_context.get("source_input_root")
            if not isinstance(source_value, str) or not source_value:
                raise ValueError("validation_context 必須包含 source_input_root")
            protected_root = _existing_lexical_directory(Path(source_value), "source_input_root")
            protected_before = project_write_snapshot(
                protected_root,
                max_files=PROTECTED_SNAPSHOT_MAX_FILES,
            )
            spawn_command = _validation_spawn_command(root, protected_root, trusted_command)
        rotating_log = RotatingLog(
            runtime_dir / f"{policy.job}.log",
            global_policy.log_max_bytes,
            global_policy.log_backups,
        )
        process, process_group = _spawn_verified_process_group(spawn_command, cwd=root)
        started_at = monotonic_now()
        # Fog 目標使用 hard maximum 的 90%，其餘 job 維持 95%。
        # Fog 曾因 probe 從 1.13 秒升至 4.77 秒耗盡原 3 秒餘裕；60 秒
        # policy 現在預留 6 秒。1..300 秒 policy 的餘裕有界於 0.1..30 秒；
        # ceiling 本身不變，真正 completion gap 仍以完整 hard maximum 判斷。
        sample_schedule_interval = (
            policy.sample_interval_seconds
            * (
                _FOG_LIVE_SAMPLE_SCHEDULE_NUMERATOR
                if policy.job == FOG_JOB
                else _LIVE_SAMPLE_SCHEDULE_NUMERATOR
            )
            / _LIVE_SAMPLE_SCHEDULE_DENOMINATOR
        )
        next_sample_target = started_at + sample_schedule_interval
        last_safe_observation_at = started_at
        def sample_live_child() -> tuple[float, float] | None:
            """回傳存活 child 的完成間距與 sampler duration；phase 僅分類 evidence。"""

            nonlocal last_safe_observation_at
            if process is None or process.poll() is not None:
                return None
            sample_started_at = monotonic_now()
            current = take(process.pid)
            sample_completed_at = monotonic_now()
            phase = "live" if process.poll() is None else "final"
            samples.append(replace(current, phase=phase))
            observation_gap = sample_completed_at - last_safe_observation_at
            sample_duration = sample_completed_at - sample_started_at
            last_safe_observation_at = sample_completed_at
            return observation_gap, sample_duration

        def completed_sample_deadline_reason(observation_gap: float) -> str | None:
            """依實際 cadence deadline 與 runtime 的先後決定已完成 sample reason。"""

            sample_hard_deadline = (
                last_safe_observation_at
                - observation_gap
                + policy.sample_interval_seconds
            )
            runtime_deadline = (
                started_at + max_runtime_seconds
                if max_runtime_seconds is not None
                else None
            )
            if observation_gap > policy.sample_interval_seconds:
                if (
                    runtime_deadline is not None
                    and runtime_deadline <= sample_hard_deadline
                ):
                    return "HARD_RUNTIME_EXCEEDED"
                return "LIVE_SAMPLE_CADENCE_EXCEEDED"
            if (
                runtime_deadline is not None
                and last_safe_observation_at >= runtime_deadline
            ):
                return "HARD_RUNTIME_EXCEEDED"
            return None

        def next_sample_action(sample_duration: float) -> str:
            """以有界算術 reconcile target，回傳下一個 sample 或 runtime 動作。"""

            nonlocal next_sample_target
            now = monotonic_now()
            if next_sample_target <= now:
                missed_intervals = (
                    math.floor(
                        (now - next_sample_target) / sample_schedule_interval
                    )
                    + 1
                )
                next_sample_target += missed_intervals * sample_schedule_interval
            sample_hard_deadline = (
                last_safe_observation_at + policy.sample_interval_seconds
            )
            predicted_completion = next_sample_target + sample_duration
            if max_runtime_seconds is not None:
                runtime_deadline = started_at + max_runtime_seconds
                if runtime_deadline <= next_sample_target:
                    return "WAIT_RUNTIME"
                if runtime_deadline < predicted_completion:
                    return "WAIT_RUNTIME"
            if (
                next_sample_target > now
                and predicted_completion <= sample_hard_deadline
            ):
                return "SAMPLE"
            return "SCHEDULE_OVERRUN"

        # child 建立後立刻取樣；快速結束但沒有有效 live 證據時由 final decision fail closed。
        scheduled_action = "SAMPLE"
        immediate_observation = sample_live_child()
        if immediate_observation is not None:
            immediate_gap, immediate_duration = immediate_observation
            deadline_reason = completed_sample_deadline_reason(immediate_gap)
            deadline_reasons = (deadline_reason,) if deadline_reason is not None else ()
            immediate_decision = evaluate_runtime(global_policy, policy, samples)
            stop_reasons = tuple(
                dict.fromkeys((*deadline_reasons, *immediate_decision.reasons))
            )
            if stop_reasons:
                terminate_process_group(process, identity=process_group)
            else:
                scheduled_action = next_sample_action(immediate_duration)
            if scheduled_action == "SCHEDULE_OVERRUN":
                stop_reasons = ("LIVE_SAMPLE_SCHEDULE_OVERRUN",)
                terminate_process_group(process, identity=process_group)
        first_write = threading.Event()
        first_write_lock = threading.Lock()
        first_write_seen = False
        sampled_first_write = False
        pump_errors: list[str] = []

        def pump() -> None:
            nonlocal first_write_seen
            try:
                assert process is not None and process.stdout is not None
                assert rotating_log is not None
                while True:
                    chunk = process.stdout.read(65536)
                    if not chunk:
                        break
                    with first_write_lock:
                        if not first_write_seen:
                            first_write_seen = True
                            first_write.set()
                    rotating_log.write(chunk)
            except (OSError, ValueError) as exc:
                pump_errors.append(type(exc).__name__)

        def claim_pending_first_write() -> bool:
            """以 observation start 為邊界，原子承接唯一 first-write event。"""

            nonlocal sampled_first_write
            with first_write_lock:
                if sampled_first_write or not first_write.is_set():
                    return False
                first_write.clear()
                sampled_first_write = True
                return True

        pump_thread = threading.Thread(target=pump, name=f"storage-log-{policy.job}", daemon=True)
        pump_thread.start()
        defer_first_write_until_scheduled = False
        while process.poll() is None:
            if pump_errors:
                stop_reasons = ("LOG_CAPTURE_FAILED",)
                terminate_process_group(process, identity=process_group)
                break
            if (
                scheduled_action != "WAIT_RUNTIME"
                and not defer_first_write_until_scheduled
                and claim_pending_first_write()
            ):
                first_write_observation = sample_live_child()
                first_write_reason = (
                    completed_sample_deadline_reason(first_write_observation[0])
                    if first_write_observation is not None
                    else None
                )
                if first_write_reason is not None:
                    stop_reasons = tuple(
                        dict.fromkeys((*stop_reasons, first_write_reason))
                    )
                    terminate_process_group(process, identity=process_group)
                    break
                output_decision = evaluate_runtime(global_policy, policy, samples)
                if output_decision.triggered:
                    stop_reasons = output_decision.reasons
                    terminate_process_group(process, identity=process_group)
                    break
                if first_write_observation is not None:
                    scheduled_action = next_sample_action(first_write_observation[1])
                if scheduled_action == "SCHEDULE_OVERRUN":
                    stop_reasons = ("LIVE_SAMPLE_SCHEDULE_OVERRUN",)
                    terminate_process_group(process, identity=process_group)
                    break
            now = monotonic_now()
            sample_hard_deadline = (
                last_safe_observation_at + policy.sample_interval_seconds
            )
            elapsed_runtime = now - started_at
            if max_runtime_seconds is not None and elapsed_runtime >= max_runtime_seconds:
                runtime_deadline = started_at + max_runtime_seconds
                stop_reasons = (
                    "HARD_RUNTIME_EXCEEDED"
                    if runtime_deadline <= sample_hard_deadline
                    else "LIVE_SAMPLE_CADENCE_EXCEEDED",
                )
                terminate_process_group(process, identity=process_group)
                break
            wake_deadline = next_sample_target
            runtime_deadline = None
            if max_runtime_seconds is not None:
                runtime_deadline = started_at + max_runtime_seconds
                wake_deadline = (
                    runtime_deadline
                    if scheduled_action == "WAIT_RUNTIME"
                    else min(wake_deadline, runtime_deadline)
                )
            wait_seconds = wake_deadline - now
            deadline_reached = wait_seconds <= 0
            if not deadline_reached:
                try:
                    wait_for_process(process, wait_seconds)
                except subprocess.TimeoutExpired:
                    deadline_reached = True
            if deadline_reached:
                now = monotonic_now()
                if (
                    runtime_deadline is not None
                    and now >= runtime_deadline
                ):
                    stop_reasons = (
                        "HARD_RUNTIME_EXCEEDED"
                        if runtime_deadline <= sample_hard_deadline
                        else "LIVE_SAMPLE_CADENCE_EXCEEDED",
                    )
                    terminate_process_group(process, identity=process_group)
                    break
                scheduled_owns_first_write = claim_pending_first_write()
                scheduled_observation = sample_live_child()
                if scheduled_owns_first_write:
                    defer_first_write_until_scheduled = False
                elif not sampled_first_write:
                    # Observation start 後才發生的 event 保持 pending；下一個
                    # absolute target 前必須先經過 strictly-positive waiter。
                    defer_first_write_until_scheduled = True
                scheduled_reason = (
                    completed_sample_deadline_reason(scheduled_observation[0])
                    if scheduled_observation is not None
                    else None
                )
                if scheduled_reason is not None:
                    stop_reasons = (scheduled_reason,)
                    terminate_process_group(process, identity=process_group)
                    break
                next_sample_target += sample_schedule_interval
                if scheduled_observation is not None:
                    scheduled_action = next_sample_action(scheduled_observation[1])
                if scheduled_action == "SCHEDULE_OVERRUN":
                    stop_reasons = ("LIVE_SAMPLE_SCHEDULE_OVERRUN",)
                    terminate_process_group(process, identity=process_group)
                    break
                after_writes = project_write_snapshot(root)
                unknown = unknown_changed_paths(
                    before_writes,
                    after_writes,
                    policy.registered_write_paths,
                )
                observed_unknown_paths = tuple(
                    dict.fromkeys((*observed_unknown_paths, *unknown))
                )
                registered_unmetered = registered_changed_paths_outside_meter(
                    before_writes,
                    after_writes,
                    policy.registered_write_paths,
                    policy.meter_paths,
                )
                observed_registered_unmetered_paths = tuple(
                    dict.fromkeys(
                        (*observed_registered_unmetered_paths, *registered_unmetered)
                    )
                )
                decision = evaluate_runtime(
                    global_policy,
                    policy,
                    samples,
                    unknown_paths=unknown,
                    registered_unmetered_paths=registered_unmetered,
                )
                stop_reasons = decision.reasons
                if stop_reasons:
                    terminate_process_group(process, identity=process_group)
                    break
            else:
                completion_time = monotonic_now()
                if (
                    runtime_deadline is not None
                    and runtime_deadline <= sample_hard_deadline
                    and completion_time >= runtime_deadline
                ):
                    stop_reasons = ("HARD_RUNTIME_EXCEEDED",)
                elif completion_time > sample_hard_deadline:
                    stop_reasons = ("LIVE_SAMPLE_CADENCE_EXCEEDED",)
                if stop_reasons:
                    terminate_process_group(process, identity=process_group)
                    break

        if process.poll() is not None and not process_group_is_quiescent(process_group):
            stop_reasons = tuple(
                dict.fromkeys((*stop_reasons, "PROCESS_GROUP_DESCENDANT_SURVIVED_LEADER"))
            )
            terminate_process_group(process, identity=process_group)

        pump_thread.join(timeout=5)
        if pump_thread.is_alive():
            stop_reasons = tuple(dict.fromkeys((*stop_reasons, "OUTPUT_PIPE_NOT_CLOSED")))
        if process.stdout is not None:
            process.stdout.close()
        rotating_log.close()
        rotating_log = None
        if pump_errors:
            stop_reasons = tuple(dict.fromkeys((*stop_reasons, "LOG_CAPTURE_FAILED")))
        if "LIVE_SAMPLE_CADENCE_EXCEEDED" not in stop_reasons:
            samples.append(
                replace(take(process.pid if process.poll() is None else None), phase="final")
            )
        after_writes = project_write_snapshot(root)
        final_unknown_paths = unknown_changed_paths(
            before_writes,
            after_writes,
            policy.registered_write_paths,
        )
        observed_unknown_paths = tuple(
            dict.fromkeys((*observed_unknown_paths, *final_unknown_paths))
        )
        final_registered_unmetered_paths = registered_changed_paths_outside_meter(
            before_writes,
            after_writes,
            policy.registered_write_paths,
            policy.meter_paths,
        )
        observed_registered_unmetered_paths = tuple(
            dict.fromkeys(
                (
                    *observed_registered_unmetered_paths,
                    *final_registered_unmetered_paths,
                )
            )
        )
        final_decision = evaluate_runtime(
            global_policy,
            policy,
            samples,
            unknown_paths=observed_unknown_paths,
            registered_unmetered_paths=observed_registered_unmetered_paths,
        )
        stop_reasons = tuple(dict.fromkeys((*stop_reasons, *final_decision.reasons)))
        if protected_root is not None and protected_before is not None:
            protected_after = project_write_snapshot(
                protected_root,
                max_files=PROTECTED_SNAPSHOT_MAX_FILES,
            )
            if protected_after != protected_before:
                protected_changed_paths = sorted(
                    path
                    for path in set(protected_before) | set(protected_after)
                    if protected_before.get(path) != protected_after.get(path)
                )
                if isinstance(validation_context, dict):
                    validation_context = {
                        **validation_context,
                        "protected_root_changed_paths": protected_changed_paths,
                    }
                stop_reasons = tuple(
                    dict.fromkeys((*stop_reasons, "PROTECTED_ROOT_MUTATED"))
                )
        if process_group is None:
            stop_reasons = tuple(
                dict.fromkeys((*stop_reasons, "PROCESS_GROUP_IDENTITY_MISSING"))
            )
        else:
            final_process_group_checked_at = _utc_timestamp()
            final_process_group_quiescent = process_group_is_quiescent(process_group)
            if final_process_group_quiescent is not True:
                stop_reasons = tuple(
                    dict.fromkeys(
                        (*stop_reasons, "PROCESS_GROUP_NOT_QUIESCENT_AT_FINAL_CHECK")
                    )
                )
        if stop_reasons:
            terminate_process_group(process, identity=process_group)
            if process_group is not None:
                final_process_group_checked_at = _utc_timestamp()
                final_process_group_quiescent = process_group_is_quiescent(process_group)
            stopped_receipt = receipt_payload(
                policy=policy,
                command=command,
                status="STOPPED",
                samples=samples,
                reasons=stop_reasons,
                child_exit_code=process.returncode,
                reclaimed=reclaimed,
                validation_only=validation_only,
                max_runtime_seconds=max_runtime_seconds,
                unknown_paths=observed_unknown_paths,
                validation_context=validation_context,
                registered_unmetered_paths=observed_registered_unmetered_paths,
                process_group_identity=process_group,
                final_process_group_quiescent=final_process_group_quiescent,
                final_process_group_checked_at=final_process_group_checked_at,
            )
            root_receipt_path = _receipt_archive_path(
                runtime_dir,
                policy.job,
                resolved_invocation_id,
            )
            stopped_receipt["restart_denied_marker_persisted"] = True
            _atomic_json(
                denied_path,
                {
                    "schema_version": RESTART_DENIED_SCHEMA_VERSION,
                    "job": policy.job,
                    "reasons": list(stop_reasons),
                    "automatic_clear_allowed": False,
                    "unknown_changed_paths": list(observed_unknown_paths),
                    "registered_unmetered_changed_paths": list(
                        observed_registered_unmetered_paths
                    ),
                    "root_invocation_id": resolved_invocation_id,
                    "root_receipt_path": root_receipt_path.relative_to(root).as_posix(),
                    "root_receipt_sha256": _json_payload_sha256(stopped_receipt),
                    "root_claim_token": claim_token,
                    "root_receipt": stopped_receipt,
                },
            )
            write_receipt(stopped_receipt)
            return 70

        final_reclaim = reclaim_allowlisted(root, rules, execute=True)
        final_receipt = receipt_payload(
            policy=policy,
            command=command,
            status="OK" if process.returncode == 0 else "CHILD_FAILED",
            samples=samples,
            reasons=(),
            child_exit_code=process.returncode,
            reclaimed=final_reclaim,
            validation_only=validation_only,
            max_runtime_seconds=max_runtime_seconds,
            unknown_paths=observed_unknown_paths,
            validation_context=validation_context,
            registered_unmetered_paths=observed_registered_unmetered_paths,
            process_group_identity=process_group,
            final_process_group_quiescent=final_process_group_quiescent,
            final_process_group_checked_at=final_process_group_checked_at,
        )
        if (
            policy.job == FOG_JOB
            and resolved_trigger == "natural"
            and not validation_only
            and process.returncode == 0
        ):
            final_receipt.update(
                evaluate_natural_acceptance(
                    root,
                    scheduled_at=resolved_scheduled_at,
                    invocation_id=resolved_invocation_id,
                    child_exit_code=process.returncode,
                    final_process_group_quiescent=final_process_group_quiescent,
                )
            )
        write_receipt(final_receipt)
        return int(process.returncode or 0)
    except Exception as exc:
        internal_reasons = (
            ("UNTRUSTED_VALIDATION_ENTRYPOINT",)
            if isinstance(exc, UntrustedValidationEntrypoint)
            else (f"GUARD_INTERNAL_ERROR_{type(exc).__name__}",)
        )
        reasons = tuple(dict.fromkeys((*stop_reasons, *internal_reasons)))
        if process is not None and process_group is not None:
            try:
                terminate_process_group(process, identity=process_group)
                final_process_group_checked_at = _utc_timestamp()
                final_process_group_quiescent = process_group_is_quiescent(process_group)
            except (OSError, RuntimeError, subprocess.TimeoutExpired):
                reasons = (*reasons, "PROCESS_GROUP_TERMINATION_FAILED")
        stopped_receipt = receipt_payload(
            policy=policy,
            command=command,
            status="STOPPED",
            samples=samples,
            reasons=reasons,
            child_exit_code=process.returncode if process is not None else None,
            reclaimed=reclaimed,
            validation_only=validation_only,
            max_runtime_seconds=max_runtime_seconds,
            unknown_paths=observed_unknown_paths,
            validation_context=validation_context,
            registered_unmetered_paths=observed_registered_unmetered_paths,
            process_group_identity=process_group,
            final_process_group_quiescent=final_process_group_quiescent,
            final_process_group_checked_at=final_process_group_checked_at,
        )
        base_archive_path = (
            runtime_dir
            / "receipts"
            / policy.job
            / f"{resolved_invocation_id}.json"
        )
        archive_variant = None
        if not (
            isinstance(claim_token, str)
            and _invocation_claim_matches(
                base_archive_path,
                job=policy.job,
                invocation_id=resolved_invocation_id,
                claim_token=claim_token,
            )
        ) and base_archive_path.exists():
            archive_variant = "recovery"
        root_receipt_path = _receipt_archive_path(
            runtime_dir,
            policy.job,
            resolved_invocation_id,
            archive_variant=archive_variant,
        )
        stopped_receipt["restart_denied_marker_persisted"] = True
        denial_payload = {
            "schema_version": RESTART_DENIED_SCHEMA_VERSION,
            "job": policy.job,
            "reasons": list(reasons),
            "automatic_clear_allowed": False,
            "unknown_changed_paths": list(observed_unknown_paths),
            "registered_unmetered_changed_paths": list(
                observed_registered_unmetered_paths
            ),
            "root_invocation_id": resolved_invocation_id,
            "root_receipt_path": root_receipt_path.relative_to(root).as_posix(),
            "root_receipt_sha256": _json_payload_sha256(stopped_receipt),
            "root_claim_token": claim_token,
            "root_receipt": stopped_receipt,
        }
        try:
            _atomic_json(denied_path, denial_payload)
        except OSError:
            try:
                _atomic_json(denied_path, denial_payload)
            except OSError:
                marker_failure_receipt = {
                    **stopped_receipt,
                    "reasons": list(
                        dict.fromkeys(
                            (*reasons, "RESTART_DENIED_MARKER_WRITE_FAILED")
                        )
                    ),
                    "restart_denied_reason": list(
                        dict.fromkeys(
                            (*reasons, "RESTART_DENIED_MARKER_WRITE_FAILED")
                        )
                    ),
                    "restart_denied_marker_persisted": False,
                }
                write_receipt(
                    marker_failure_receipt,
                    archive_variant="marker-write-failed",
                )
                return 70
        try:
            write_receipt(
                stopped_receipt,
                archive_variant=archive_variant,
            )
        except OSError:
            # marker 已內嵌 hash-bound 完整 receipt；下一輪會在 child 前還原。
            return 70
        return 70
    finally:
        if process is not None and process_group is not None:
            try:
                terminate_process_group(process, identity=process_group)
            except (OSError, RuntimeError, subprocess.TimeoutExpired):
                pass
        if pump_thread is not None and pump_thread.is_alive():
            pump_thread.join(timeout=5)
        if process is not None and process.stdout is not None:
            process.stdout.close()
        if rotating_log is not None:
            rotating_log.close()
        if trusted_entrypoint_runtime is not None:
            trusted_entrypoint_runtime.cleanup()
        for signum, previous in previous_signal_handlers.items():
            signal.signal(signum, previous)
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        lock_handle.close()
