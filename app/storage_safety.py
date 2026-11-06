"""TOP10 排程的容量量測、回收與隔離停損核心。

模組只接受 repo 內明列的 meter／cleanup 路徑；不追蹤 symlink，也不會
跨出專案根目錄。正式排程政策在完成代表性兩週期前維持 fail closed。
"""

from __future__ import annotations

import fcntl
import ctypes
import hashlib
import hmac
import json
import math
import os
import plistlib
import re
import shutil
import signal
import stat as stat_module
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from collections import defaultdict, deque
from contextlib import ExitStack
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from app.fog_natural_acceptance import FOG_JOB, evaluate_natural_acceptance
from app.lightgbm_temp_guard import LightGBMTempGuard, PREFIX, PRESERVED_PREFIX
from app.external_cache import ExternalCache, ExternalCacheError, external_environment, runtime_environment


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
_FOG_LIVE_SAMPLE_SCHEDULE_NUMERATOR = 14
_LIVE_SAMPLE_SCHEDULE_DENOMINATOR = 20
_HOST_PROBE_TIMEOUT_SECONDS = 5.0
_MEMORY_PROBE_TIMEOUT_SECONDS = 5.0
_FOG_OBSERVATION_DEADLINE_SECONDS = 15.0
_BOOT_VOLUME_PATH = Path("/System/Volumes/Data") if sys.platform == "darwin" else Path("/")
_SWAP_VOLUME_PATH = Path("/System/Volumes/VM") if sys.platform == "darwin" else Path("/")


@dataclass(frozen=True)
class GlobalPolicy:
    start_min_free_bytes: int
    start_min_free_percent: float
    runtime_min_free_bytes: int
    runtime_min_free_percent: float
    require_swap_metric: bool
    log_max_bytes: int
    log_backups: int
    boot_volume_min_free_bytes: int = 24 * 1024**3
    boot_volume_warn_free_bytes: int = 34 * 1024**3
    memory_sample_interval_seconds: int = 15


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
    host_peak_budget_bytes: int = 0
    boot_volume_swap_headroom_bytes: int = 0


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
    phys_footprint: int | None = None


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
    external_cache: dict[str, Any] | None = None
    # host_free_bytes 為准入／停損可用量；另留實體 raw，避免混淆兩種口徑。
    host_raw_free_bytes: int | None = None
    host_capacity_source: str | None = None
    boot_volume_path: str | None = None
    swap_volume_path: str | None = None
    boot_volume_total_bytes: int | None = None
    boot_volume_free_bytes: int | None = None
    boot_volume_raw_free_bytes: int | None = None
    boot_volume_capacity_source: str | None = None
    capacity_sampled: bool = True
    host_boot_shared_container: bool | None = None
    monotonic_timestamp: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StopDecision:
    triggered: bool
    reasons: tuple[str, ...]
    warnings: tuple[str, ...] = ()


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


class StorageObservationError(RuntimeError):
    """容量／寫入觀測失敗；receipt 只保存固定 reason code。"""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


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
        boot_volume_min_free_bytes=_positive_int(host["boot_volume_min_free_bytes"], "boot_volume_min_free_bytes"),
        boot_volume_warn_free_bytes=_positive_int(host["boot_volume_warn_free_bytes"], "boot_volume_warn_free_bytes"),
        memory_sample_interval_seconds=_positive_int(host["memory_sample_interval_seconds"], "memory_sample_interval_seconds"),
    )
    if (global_policy.boot_volume_min_free_bytes != 24 * 1024**3
            or global_policy.boot_volume_warn_free_bytes != 34 * 1024**3
            or global_policy.memory_sample_interval_seconds > 15):
        raise ValueError("內建卷門檻須為 24／34 GiB，記憶體取樣間隔不得超過 15 秒")
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
        host_peak_budget_bytes=(
            _positive_int(raw["host_peak_budget_bytes"], f"{job}.host_peak_budget_bytes")
            if job == "daily" else 0
        ),
        boot_volume_swap_headroom_bytes=(
            _positive_int(raw["boot_volume_swap_headroom_bytes"], f"{job}.boot_volume_swap_headroom_bytes")
            if job == "daily" else 0
        ),
    )
    if (job == "daily" and job_policy.host_peak_budget_bytes
            < job_policy.max_bytes + job_policy.boot_volume_swap_headroom_bytes):
        raise ValueError("daily.host_peak_budget_bytes 必須覆蓋專案峰值與獨立內建卷預留")
    if job == "daily" and job_policy.boot_volume_swap_headroom_bytes < 2 * 1024**3:
        raise ValueError("daily 內建卷預留不得低於既有 2 GiB")
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


def _iter_regular_file_stats(
    base: Path,
    *,
    deadline: float | None = None,
    monotonic_clock: Callable[[], float] = time.monotonic,
    permission_reason: str,
    unavailable_reason: str,
    deadline_reason: str,
) -> Iterable[tuple[Path, os.stat_result]]:
    """以單一 DirEntry metadata 遍歷；競態刪除可略過，其餘觀測失敗拒絕。"""

    def check_deadline() -> None:
        if deadline is not None and monotonic_clock() >= deadline:
            raise StorageObservationError(deadline_reason)

    def observation_error(error: OSError) -> StorageObservationError:
        reason = permission_reason if isinstance(error, PermissionError) else unavailable_reason
        return StorageObservationError(reason)

    check_deadline()
    try:
        base_stat = base.lstat()
    except FileNotFoundError:
        return
    except OSError as error:
        raise observation_error(error) from error
    if stat_module.S_ISLNK(base_stat.st_mode):
        raise ValueError(f"meter path 不得是 symlink: {base}")
    if stat_module.S_ISREG(base_stat.st_mode):
        yield base, base_stat
        return
    if not stat_module.S_ISDIR(base_stat.st_mode):
        return

    pending = [base]
    while pending:
        check_deadline()
        directory = pending.pop()
        try:
            with os.scandir(directory) as iterator:
                entries = sorted(iterator, key=lambda entry: entry.name)
        except FileNotFoundError:
            continue
        except OSError as error:
            raise observation_error(error) from error

        child_directories: list[Path] = []
        for entry in entries:
            check_deadline()
            try:
                if entry.is_symlink():
                    continue
                if entry.is_dir(follow_symlinks=False):
                    if entry.name not in IGNORED_PROJECT_DIRS:
                        child_directories.append(Path(entry.path))
                    continue
                if not entry.is_file(follow_symlinks=False):
                    continue
                entry_stat = entry.stat(follow_symlinks=False)
            except FileNotFoundError:
                # child 正在原子 replace／回收；消失後已不再占用容量。
                continue
            except OSError as error:
                raise observation_error(error) from error
            yield Path(entry.path), entry_stat
        pending.extend(reversed(child_directories))


def _iter_regular_files(base: Path) -> Iterable[Path]:
    """保留既有內部接點；新量測直接使用同一次取得的 stat。"""

    for path, _path_stat in _iter_regular_file_stats(
        base,
        permission_reason="STORAGE_OBSERVATION_PERMISSION_DENIED",
        unavailable_reason="STORAGE_OBSERVATION_UNAVAILABLE",
        deadline_reason="STORAGE_OBSERVATION_DEADLINE_EXCEEDED",
    ):
        yield path


def measure_paths(
    root: Path,
    meter_paths: Sequence[str],
    *,
    deadline_seconds: float | None = None,
    monotonic_clock: Callable[[], float] = time.monotonic,
) -> Inventory:
    """量測登記 scope；重疊的 meter path 只計一次。"""

    if deadline_seconds is not None and deadline_seconds <= 0:
        raise ValueError("deadline_seconds 必須大於 0")
    deadline = (
        monotonic_clock() + deadline_seconds
        if deadline_seconds is not None
        else None
    )
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
        for path, path_stat in _iter_regular_file_stats(
            base,
            deadline=deadline,
            monotonic_clock=monotonic_clock,
            permission_reason="METER_PATHS_PERMISSION_DENIED",
            unavailable_reason="METER_PATHS_PROBE_UNAVAILABLE",
            deadline_reason="METER_PATHS_PROBE_DEADLINE_EXCEEDED",
        ):
            identity = path.relative_to(canonical_root).as_posix()
            if identity in seen:
                continue
            seen.add(identity)
            total_bytes += path_stat.st_size
    return Inventory(bytes=total_bytes, file_count=len(seen))


def project_write_snapshot(
    root: Path,
    *,
    max_files: int | None = None,
    deadline_seconds: float | None = None,
    monotonic_clock: Callable[[], float] = time.monotonic,
) -> dict[str, tuple[int, int]]:
    """建立 repo 內可觀察檔案快照，用於偵測未登記寫入。"""

    if deadline_seconds is not None and deadline_seconds <= 0:
        raise ValueError("deadline_seconds 必須大於 0")
    deadline = (
        monotonic_clock() + deadline_seconds
        if deadline_seconds is not None
        else None
    )
    root = root.resolve()
    snapshot: dict[str, tuple[int, int]] = {}
    for path, path_stat in _iter_regular_file_stats(
        root,
        deadline=deadline,
        monotonic_clock=monotonic_clock,
        permission_reason="WRITE_SNAPSHOT_PERMISSION_DENIED",
        unavailable_reason="WRITE_SNAPSHOT_UNAVAILABLE",
        deadline_reason="WRITE_SNAPSHOT_DEADLINE_EXCEEDED",
    ):
        relative = path.relative_to(root)
        if relative.parts and relative.parts[0] in IGNORED_PROJECT_DIRS:
            continue
        if max_files is not None and len(snapshot) >= max_files:
            raise RuntimeError("protected root snapshot 超過檔案上限")
        snapshot[relative.as_posix()] = (path_stat.st_size, path_stat.st_mtime_ns)
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


def read_swap_bytes(*, timeout_seconds: float = _HOST_PROBE_TIMEOUT_SECONDS) -> int | None:
    """讀取 macOS swap；不可讀時回傳 None，由 fail-closed policy 判定。"""

    try:
        completed = subprocess.run(
            ["/usr/sbin/sysctl", "-n", "vm.swapusage"],
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
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
    *, timeout_seconds: float = _HOST_PROBE_TIMEOUT_SECONDS,
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
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    raw = completed.stdout.strip()
    if not re.fullmatch(r"[0-4]", raw):
        return None
    return int(raw)


class _RusageInfoV0(ctypes.Structure):
    """macOS SDK sys/resource.h 的 RUSAGE_INFO_V0 固定 ABI。"""

    _fields_ = [("ri_uuid", ctypes.c_uint8 * 16)] + [
        (name, ctypes.c_uint64) for name in (
            "ri_user_time", "ri_system_time", "ri_pkg_idle_wkups", "ri_interrupt_wkups",
            "ri_pageins", "ri_wired_size", "ri_resident_size", "ri_phys_footprint",
            "ri_proc_start_abstime", "ri_proc_exit_abstime",
        )
    ]


def read_process_phys_footprint(pid: int) -> int | None:
    """讀取指定 process 的實體足跡；權限不足／process 已退出時保留未知。"""

    if sys.platform != "darwin":
        return None
    try:
        probe = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True).proc_pid_rusage
        probe.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_void_p]
        probe.restype = ctypes.c_int
        info = _RusageInfoV0()
        if probe(pid, 0, ctypes.byref(info)) != 0:
            return None
        return int(info.ri_phys_footprint)
    except (OSError, AttributeError, ValueError):
        return None


def process_tree_rss_snapshot(
    root_pid: int | None,
    *, timeout_seconds: float = _HOST_PROBE_TIMEOUT_SECONDS,
) -> tuple[int | None, tuple[ProcessRssAttribution, ...]]:
    if root_pid is None or root_pid <= 0:
        return 0, ()
    try:
        completed = subprocess.run(
            ["/bin/ps", "-axo", "pid=,ppid=,rss=,command="],
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
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
            attribution.append(replace(process, phys_footprint=read_process_phys_footprint(pid)))
        queue.extend(parents.get(pid, []))
    return sum(process.rss_bytes for process in attribution), tuple(attribution)


def process_tree_rss_bytes(root_pid: int | None) -> int | None:
    rss_bytes, _ = process_tree_rss_snapshot(root_pid)
    return rss_bytes


def _measure_host_capacity(path: Path) -> tuple[int, int, int, str]:
    """薄接既有 ai-core sensor；macOS 失敗直接拒絕，不以 raw 降級。"""
    if sys.platform != "darwin":
        disk = shutil.disk_usage(path)
        return disk.total, disk.free, disk.free, "shutil.disk_usage"
    core = Path(os.environ.get("AI_CORE_DIR", str(Path.home() / "ai-core")))
    if not core.is_absolute():
        raise RuntimeError("HOST_CAPACITY_TOOLCHAIN_REQUIRED")
    # 沿外接 gate 既有跨 repo CLI 方式；-B 禁止在共用 repo 產生 bytecode。
    script = (
        "import sys,json,dataclasses; from pathlib import Path; "
        "sys.path.insert(0,sys.argv[1]); "
        "from host_capacity_sensor import measure_host_capacity; "
        "print(json.dumps(dataclasses.asdict(measure_host_capacity(Path(sys.argv[2])))))"
    )
    try:
        result = subprocess.run(
            [str(core / ".venv/bin/python"), "-B", "-c", script,
             str(core / "scripts"), str(path)],
            check=True, capture_output=True, text=True, timeout=15,
        )
        payload = json.loads(result.stdout)
        total, raw, admission = (payload[key] for key in (
            "total_bytes", "physical_available_bytes", "admission_available_bytes"
        ))
        source = payload["source"]
        if (any(type(value) is not int for value in (total, raw, admission))
                or not 0 < raw <= admission <= total
                or source != "macos_foundation_important_usage"):
            raise ValueError("共用 sensor 回傳無效容量或來源")
        return total, raw, admission, source
    except (OSError, subprocess.SubprocessError, ValueError, TypeError, KeyError) as error:
        raise RuntimeError("HOST_CAPACITY_UNAVAILABLE") from error


def _measure_boot_volume_capacity() -> tuple[int, int, int, str] | None:
    """固定量 swapfile 所在內建卷；不沿 workload 的外接 root，也不回退 raw。"""

    try:
        if sys.platform == "darwin":
            data = _volume_container(_BOOT_VOLUME_PATH)
            vm = _volume_container(_SWAP_VOLUME_PATH)
            # VM 專用卷不提供 Foundation admission；僅在原生證明共用內建
            # APFS container 時，使用 Data 的同容量池准入量，否則保留未知。
            if data is None or vm is None or data != vm or not data[1]:
                return None
        return _measure_host_capacity(_BOOT_VOLUME_PATH)
    except (OSError, RuntimeError):
        return None


def _volume_container(path: Path) -> tuple[str, bool] | None:
    """diskutil info 接受掛載點；先沿實際 mount 邊界解析，不能直接傳任意子目錄。"""

    try:
        mount = path.resolve()
        while not os.path.ismount(mount):
            if mount.parent == mount:
                return None
            mount = mount.parent
        result = subprocess.run(["/usr/sbin/diskutil", "info", "-plist", str(mount)],
                                capture_output=True, check=True, timeout=_HOST_PROBE_TIMEOUT_SECONDS)
        info = plistlib.loads(result.stdout)
        if not isinstance(info, dict):
            return None
        value = info.get("APFSContainerReference")
        internal = info.get("Internal")
        return (value, internal) if isinstance(value, str) and value and type(internal) is bool else None
    except (OSError, subprocess.SubprocessError, ValueError, plistlib.InvalidFileException):
        return None


def _shares_boot_container(host_path: Path) -> bool | None:
    """辨識是否共用容量池；未知時保守保留合併峰值，避免同卷重用餘量。"""

    try:
        if sys.platform != "darwin":
            return host_path.stat().st_dev == _BOOT_VOLUME_PATH.stat().st_dev
        host = _volume_container(host_path)
        boot = _volume_container(_BOOT_VOLUME_PATH)
        return host[0] == boot[0] if host is not None and boot is not None else None
    except (OSError, subprocess.SubprocessError, ValueError, plistlib.InvalidFileException):
        return None


def take_sample(
    root: Path, policy: JobPolicy, process_pid: int | None = None, *, host_root: Path | None = None,
) -> Sample:
    """meter 維持 output root；host_root 只選主機量測卷，准入沿原生口徑。"""
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
        lambda: measure_paths(
            root,
            policy.meter_paths,
            deadline_seconds=(
                _FOG_OBSERVATION_DEADLINE_SECONDS
                if policy.job == FOG_JOB
                else None
            ),
        ),
        available=lambda _value: True,
    )
    host_total, host_raw, host_admission, host_source = timed_probe(
        "host_capacity",
        lambda: _measure_host_capacity(root if host_root is None else host_root),
        available=lambda _value: True,
    )
    boot = timed_probe("boot_volume_capacity", _measure_boot_volume_capacity)
    shared_container = timed_probe("volume_identity", lambda: _shares_boot_container(root if host_root is None else host_root))
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
        monotonic_timestamp=time.monotonic(),
        project_bytes=inventory.bytes,
        project_file_count=inventory.file_count,
        host_total_bytes=host_total,
        host_free_bytes=host_admission,
        host_raw_free_bytes=host_raw,
        host_capacity_source=host_source,
        boot_volume_path=str(_BOOT_VOLUME_PATH),
        swap_volume_path=str(_SWAP_VOLUME_PATH),
        boot_volume_total_bytes=boot[0] if boot else None,
        boot_volume_raw_free_bytes=boot[1] if boot else None,
        boot_volume_free_bytes=boot[2] if boot else None,
        boot_volume_capacity_source=boot[3] if boot else None,
        host_boot_shared_container=shared_container,
        rss_bytes=rss_bytes,
        swap_bytes=swap_bytes,
        memory_pressure_level=memory_pressure_level,
        process_rss_attribution=process_rss_attribution,
        probe_timings=tuple(timings),
    )


def _free_threshold(total: int, minimum_bytes: int, minimum_percent: float) -> int:
    return max(minimum_bytes, int(total * minimum_percent))


def _take_memory_sample(capacity: Sample, process_pid: int) -> Sample:
    """只更新記憶體訊號，明記未重掃容量，避免以舊容量計算增長率。"""

    started = time.monotonic()
    rss, attribution = process_tree_rss_snapshot(process_pid, timeout_seconds=_MEMORY_PROBE_TIMEOUT_SECONDS)
    swap = read_swap_bytes(timeout_seconds=_MEMORY_PROBE_TIMEOUT_SECONDS)
    pressure = read_memory_pressure_level(timeout_seconds=_MEMORY_PROBE_TIMEOUT_SECONDS)
    return replace(
        capacity, timestamp=time.time(), monotonic_timestamp=time.monotonic(), rss_bytes=rss, process_rss_attribution=attribution,
        swap_bytes=swap, memory_pressure_level=pressure, capacity_sampled=False,
        probe_timings=(ProbeTiming("memory_total", time.monotonic() - started,
                                  rss is not None and swap is not None),),
    )


def _memory_cadence_decision(interval: float, gap: float, consecutive_overruns: int) -> tuple[int, StopDecision]:
    """單次遲到警示；連續兩次或單次超過兩倍間隔才判定持續失明。"""

    if gap <= interval:
        return 0, StopDecision(False, ())
    consecutive_overruns += 1
    reasons = (("MEMORY_SAMPLE_CADENCE_EXCEEDED",)
               if consecutive_overruns >= 2 or gap > 2 * interval else ())
    return consecutive_overruns, StopDecision(bool(reasons), reasons, ("MEMORY_SAMPLE_CADENCE_LOW",))


def _boot_volume_decision(global_policy: GlobalPolicy, sample: Sample, *, headroom: int = 0) -> StopDecision:
    """內建卷使用 admission 餘量；觀測缺失不可被外接餘量替代。"""

    values = (sample.boot_volume_total_bytes, sample.boot_volume_raw_free_bytes, sample.boot_volume_free_bytes)
    if (any(type(value) is not int for value in values)
            or not 0 <= values[1] <= values[2] <= values[0]
            or values[0] <= 0
            or sample.boot_volume_path != str(_BOOT_VOLUME_PATH)
            or sample.boot_volume_capacity_source != (
                "macos_foundation_important_usage" if sys.platform == "darwin" else "shutil.disk_usage")):
        return StopDecision(True, ("BOOT_VOLUME_CAPACITY_UNAVAILABLE",))
    reasons = []
    if sample.boot_volume_free_bytes < global_policy.boot_volume_min_free_bytes:
        reasons.append("BOOT_VOLUME_FREE_SPACE_BELOW_THRESHOLD")
    if headroom and sample.boot_volume_free_bytes - headroom < global_policy.boot_volume_min_free_bytes:
        reasons.append("BOOT_VOLUME_START_HEADROOM_INSUFFICIENT")
    warnings = (("BOOT_VOLUME_FREE_SPACE_LOW",)
                if sample.boot_volume_free_bytes < global_policy.boot_volume_warn_free_bytes else ())
    return StopDecision(bool(reasons), tuple(reasons), warnings)


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
    if policy.host_peak_budget_bytes:
        reserve = max(threshold, _free_threshold(
            sample.host_total_bytes,
            global_policy.runtime_min_free_bytes,
            global_policy.runtime_min_free_percent,
        ))
        # 使用實際寫入主機的 Foundation 口徑，預留整輪 bounded 峰值。
        project_peak = policy.host_peak_budget_bytes - (
            policy.boot_volume_swap_headroom_bytes if sample.host_boot_shared_container is False else 0)
        if sample.host_free_bytes - project_peak < reserve:
            reasons.append("HOST_PEAK_BUDGET_INSUFFICIENT")
        if sys.platform == "darwin" and sample.host_capacity_source != "macos_foundation_important_usage":
            reasons.append("HOST_CAPACITY_SOURCE_UNVERIFIED")
    if global_policy.require_swap_metric and sample.swap_bytes is None:
        reasons.append("SWAP_METRIC_UNAVAILABLE")
    if sample.memory_pressure_level is not None and sample.memory_pressure_level >= 3:
        reasons.append("HOST_MEMORY_PRESSURE_CRITICAL_OR_JETSAM")
    boot = _boot_volume_decision(global_policy, sample, headroom=policy.boot_volume_swap_headroom_bytes)
    reasons.extend(boot.reasons)
    return StopDecision(bool(reasons), tuple(reasons), boot.warnings)


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
    capacity_samples = [sample for sample in samples if sample.capacity_sampled]
    if not capacity_samples:
        return StopDecision(True, ("MISSING_RUNTIME_CAPACITY_SAMPLE",))
    latest = capacity_samples[-1]
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
    swap_peak_growth_bytes = (
        max(observed_swap) - baseline_swap
        if baseline_swap is not None and observed_swap else None
    )
    swap_fallback_threshold_exceeded = (
        swap_peak_growth_bytes is not None
        and swap_peak_growth_bytes > policy.max_swap_growth_bytes
    )
    latest_live = live_samples[-1] if live_samples else None
    if (
        swap_fallback_threshold_exceeded
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

    if len(capacity_samples) >= 3:
        recent = capacity_samples[-3:]
        rates = [_growth_rate(recent[0], recent[1]), _growth_rate(recent[1], recent[2])]
        over_rate = all(rate > policy.expected_growth_bytes_per_hour * 2 for rate in rates)
        elapsed = max(0.0, latest.timestamp - samples[0].timestamp)
        seconds_to_reclaim = max(0.0, policy.reclaim_after_seconds - elapsed)
        projected_growth = max(rates) * seconds_to_reclaim / 3600
        # job 總量仍含外接；內建餘量投影只扣同卷的持久資料增長。
        host_recent = list(recent)
        if any(sample.external_cache is not None for sample in recent):
            try:
                identities = []
                host_recent = []
                for sample in recent:
                    cache = sample.external_cache
                    if not isinstance(cache, dict) or len(cache["roots"]) != 1:
                        raise ValueError("缺少單一外接歸屬觀測")
                    owned = cache["roots"][0]
                    size = owned["bytes"]
                    managed = cache.get("managed_contract")
                    device = managed["device"] if managed is not None else cache["image_contract"]["image_device"]
                    path = owned["path"]
                    if (type(size) is not int or not 0 <= size <= sample.project_bytes
                            or type(device) is not int or device <= 0
                            or not isinstance(path, str) or not Path(path).is_absolute()):
                        raise ValueError("外接計量資料無效")
                    identities.append((path, device))
                    host_recent.append(replace(sample, project_bytes=sample.project_bytes - size))
                if len(set(identities)) != 1:
                    raise ValueError("外接歸屬觀測改變")
            except (KeyError, TypeError, ValueError, IndexError):
                reasons.append("EXTERNAL_CACHE_ACCOUNTING_UNAVAILABLE")
                host_recent = []
        host_rates = ([_growth_rate(host_recent[0], host_recent[1]),
                       _growth_rate(host_recent[1], host_recent[2])] if host_recent else [0.0, 0.0])
        host_over_rate = all(rate > policy.expected_growth_bytes_per_hour * 2 for rate in host_rates)
        host_projected_growth = max(host_rates) * seconds_to_reclaim / 3600
        if elapsed >= policy.spike_window_seconds and (
            (over_rate and latest.project_bytes + projected_growth > policy.max_bytes)
            or (host_over_rate and latest.host_free_bytes - host_projected_growth < reserve)
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
    boot = _boot_volume_decision(global_policy, latest)
    reasons.extend(boot.reasons)
    return StopDecision(bool(reasons), tuple(dict.fromkeys(reasons)), boot.warnings)


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
            # LightGBM 單層暫存清理由獨立明確旗標控制，不被通用 retention 偷刪。
            lightgbm_owned_scope = (path.name.startswith((PREFIX, PRESERVED_PREFIX)) and path.parent.name == "tmp"
                                   and path.parent.parent.parent == root / "logs/storage_safety/runtime")
            protected = index < rule.protect_newest or lightgbm_owned_scope
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

    if os.environ.get("TOP10_EXTERNAL_CACHE_ROOT"):
        raise ExternalCacheError("EXTERNAL_CACHE_REQUIRES_VERIFIED_MATERIALIZATION")
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


def _external_cache_spawn_command(
    root: Path, policy: JobPolicy, cache: ExternalCache, command: Sequence[str],
) -> list[str]:
    """沿既有原生隔離入口封住 /tmp、HOME 與 source 的隱性快取 fallback。"""
    if not SANDBOX_EXECUTABLE.is_file() or not os.access(SANDBOX_EXECUTABLE, os.X_OK):
        raise ExternalCacheError("EXTERNAL_CACHE_CONFINEMENT_UNAVAILABLE")
    # 受控寫入入口不得關掉標準 Python 啟動接點；唯讀 identity helper 不走此入口。
    if Path(command[0]).name.startswith("python") or Path(command[0]).resolve() == Path(sys.executable).resolve():
        arguments = iter(command[1:])
        for argument in arguments:
            if argument in {"-c", "-m", "--"} or not argument.startswith("-"):
                break
            if argument in {"-W", "-X", "--check-hash-based-pycs"}:
                next(arguments, None)
                continue
            if argument.startswith(("-W", "-X", "--")):
                continue
            if set(argument[1:]) & {"I", "E", "S"}:
                raise ExternalCacheError("EXTERNAL_CACHE_PYTHON_ISOLATION_UNSUPPORTED")
    outputs = [_safe_root_path(root, relative) for relative in policy.registered_write_paths]
    # production child 原有非寫入行為不變；不挪用／放寬 validation-only profile。
    profile = "\n".join([
        "(version 1)", "(allow default)", "(deny file-write*)",
        '(allow file-write* (literal "/dev/null"))',
        *(f"(allow file-write* (subpath {json.dumps(str(path))}))"
          for path in [*outputs, cache.root]),
    ])
    if cache.directory_mode:
        # 即使缺碟後有工具 mkdir -p，也不能重建 mount/root 的任一 ancestor。
        profile += "\n" + "\n".join(
            f"(deny file-write-create (literal {json.dumps(str(path))}))"
            for path in [cache._managed.root, *cache._managed.root.parents])
    cache.sample()
    # 小型單一 child：標準庫必須已固定外接，合法外接可寫；路徑失效時即使
    # cwd 是合法輸出目錄也不得 fallback。不重設 tempdir 為 None 開回搜尋模式。
    # context manager 只移除本次 exclusive 建立的測試檔，不掃描／清理 owned root。
    probe = (
        "import os,sys,tempfile\n"
        "if tempfile.tempdir != sys.argv[1]: sys.exit(92)\n"
        "with tempfile.TemporaryFile(dir=sys.argv[1]) as f: f.write(b'x'); f.flush()\n"
        "tempfile.tempdir=sys.argv[2]\n"
        "for directory in sys.argv[3:]:\n"
        " if not os.path.isdir(directory): continue\n"
        " os.chdir(directory)\n"
        " try:\n"
        "  with tempfile.TemporaryFile() as f: f.write(b'x'); f.flush()\n"
        " except FileNotFoundError: continue\n"
        " sys.exit(91)\n"
    )
    missing = str(cache.root / ("missing-probe-" + uuid.uuid4().hex))
    probe_env = {**os.environ, **external_environment(cache.root)}
    completed = subprocess.run(
        [str(SANDBOX_EXECUTABLE), "-p", profile, sys.executable, "-B", "-c", probe,
         str(cache.root / "tmp"), missing, str(root), *(str(path) for path in outputs)],
        cwd=root, env=probe_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        timeout=5, check=False,
    )
    cache.sample()
    if completed.returncode != 0:
        raise ExternalCacheError("EXTERNAL_CACHE_CONFINEMENT_PROBE_FAILED")
    return [str(SANDBOX_EXECUTABLE), "-p", profile, *command]


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
    capacity_samples = [sample for sample in samples if sample.capacity_sampled]
    first = capacity_samples[0] if capacity_samples else None
    last = capacity_samples[-1] if capacity_samples else None
    live_swaps = [sample.swap_bytes for sample in samples if sample.phase == "live" and sample.swap_bytes is not None]
    footprints = [
        sum(row.phys_footprint for row in sample.process_rss_attribution)
        for sample in samples if sample.phase == "live" and sample.process_rss_attribution
        and all(row.phys_footprint is not None for row in sample.process_rss_attribution)
    ]
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
            "expected_growth_bytes_per_hour": policy.expected_growth_bytes_per_hour,
            "spike_window_seconds": policy.spike_window_seconds,
            "stabilize_after_seconds": policy.stabilize_after_seconds,
            "reclaim_after_seconds": policy.reclaim_after_seconds,
            "retention_days": policy.retention_days,
            "sample_interval_seconds": policy.sample_interval_seconds,
        },
        "diagnostic_thresholds": {
            "pressure_sensor_failure_swap_growth_bytes": policy.max_swap_growth_bytes,
            "source_policy_key": "max_swap_growth_bytes",
            "semantics": "pressure 感測器失效時的備援門檻",
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
            "swap_end_delta_bytes": (
                last.swap_bytes - first.swap_bytes
                if first and last and first.swap_bytes is not None and last.swap_bytes is not None
                else None
            ),
            "swap_peak_growth_bytes": (max(live_swaps) - first.swap_bytes
                                       if live_swaps and first and first.swap_bytes is not None else None),
            "swap_attributable_hint": max(footprints, default=None),
            "phys_footprint_unavailable_live_samples": sum(
                sample.phase == "live" and (not sample.process_rss_attribution or any(
                    row.phys_footprint is None for row in sample.process_rss_attribution))
                for sample in samples),
            "swap_attributable_hint_semantics": "完整 process tree 的 phys_footprint 峰值（bytes），僅診斷，不等於可歸因 swap",
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


def _wait_with_managed_cache(child, timeout: float, cache: ExternalCache):
    """只加 cache cadence；專案大範圍量測與原生 PGID 停損沿原 guard。"""
    deadline = time.monotonic() + timeout
    while True:
        cache.sample()
        remaining = deadline - time.monotonic()
        try:
            return child.wait(timeout=max(0.0, min(1.0, remaining)))
        except subprocess.TimeoutExpired:
            if time.monotonic() >= deadline:
                raise


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
    external_cache_required: bool = False,
    startup_failure: bool = False,
    lightgbm_temp_cleanup: bool = False,
) -> int:
    """執行單一排程週期；停損時留下 marker，後續嘗試一律拒絕。"""

    if not command:
        raise ValueError("child command 不得為空")
    if max_runtime_seconds is not None and (
        not math.isfinite(max_runtime_seconds) or max_runtime_seconds <= 0
    ):
        raise ValueError("max_runtime_seconds 必須大於 0")
    root = root.resolve()
    observation_deadline_seconds = (
        _FOG_OBSERVATION_DEADLINE_SECONDS
        if policy.job == FOG_JOB
        else None
    )
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
    temp_guard: LightGBMTempGuard | None = None
    memory_samples: list[Sample] = []
    memory_errors: list[str] = []
    memory_warnings: list[str] = []
    memory_lock = threading.Lock()
    memory_stop = threading.Event()
    memory_thread: threading.Thread | None = None

    def observed_samples(capacity_samples: Sequence[Sample]) -> list[Sample]:
        with memory_lock:
            if not memory_samples:
                return list(capacity_samples)
            return sorted([*capacity_samples, *memory_samples], key=lambda sample: (
                sample.monotonic_timestamp if sample.monotonic_timestamp is not None else sample.timestamp))

    def runtime_decision(**kwargs: Any) -> StopDecision:
        decision = evaluate_runtime(global_policy, policy, observed_samples(samples), **kwargs)
        with memory_lock:
            reasons = tuple(dict.fromkeys((*decision.reasons, *memory_errors)))
        return StopDecision(bool(reasons), reasons, decision.warnings)

    def stop_memory_monitor() -> None:
        memory_stop.set()
        if memory_thread is not None:
            memory_thread.join(timeout=3 * _MEMORY_PROBE_TIMEOUT_SECONDS + 1)
            if memory_thread.is_alive():
                raise RuntimeError("MEMORY_MONITOR_NOT_QUIESCENT")

    def receipt_payload(**kwargs: Any) -> dict[str, Any]:
        kwargs["samples"] = observed_samples(kwargs["samples"])
        payload = _receipt_payload(
            **kwargs,
            trigger_type=resolved_trigger,
            scheduled_at=resolved_scheduled_at,
            invocation_id=resolved_invocation_id,
        )
        payload["warnings"] = list(dict.fromkeys(
            warning for sample in kwargs["samples"] if sample.capacity_sampled
            for warning in _boot_volume_decision(global_policy, sample).warnings
        ))
        with memory_lock:
            payload["warnings"] = list(dict.fromkeys((*payload["warnings"], *memory_warnings)))
        payload["limits"].update({
            "boot_volume_min_free_bytes": global_policy.boot_volume_min_free_bytes,
            "boot_volume_warn_free_bytes": global_policy.boot_volume_warn_free_bytes,
            "boot_volume_swap_headroom_bytes": policy.boot_volume_swap_headroom_bytes,
            "project_peak_budget_bytes": policy.host_peak_budget_bytes - policy.boot_volume_swap_headroom_bytes,
            "memory_sample_interval_seconds": global_policy.memory_sample_interval_seconds,
        })
        if temp_guard is not None:
            payload["lightgbm_temp"] = temp_guard.finish()
            if temp_guard.report["warnings"]:
                payload["warnings"] = list(dict.fromkeys((*payload["warnings"], *temp_guard.report["warnings"])))
        return payload

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
    base_take = sampler or (lambda pid: take_sample(root, policy, pid))
    take = base_take
    external: ExternalCache | None = None
    saved_environment: dict[str, str | None] = {}

    def take_external(pid: int | None, *, enforce_retention: bool = True) -> Sample:
        sample = base_take(pid)
        if external is None:
            return sample
        measured = external.sample(enforce_retention=enforce_retention)
        owned = measured["roots"][0]
        return replace(
            sample, project_bytes=sample.project_bytes + owned["bytes"],
            project_file_count=sample.project_file_count + owned["files"],
            external_cache=measured,
        )
    monotonic_now = monotonic_clock or time.monotonic
    wait_for_process = process_waiter or (
        lambda child, timeout: (_wait_with_managed_cache(child, timeout, external)
            if external is not None and external.directory_mode else child.wait(timeout=timeout))
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
        if startup_failure:
            raise ExternalCacheError("EXTERNAL_CACHE_STARTUP_FAILED")
        if external_cache_required:
            if validation_only:
                raise ExternalCacheError("EXTERNAL_CACHE_ISOLATION_UNSUPPORTED")
            runtime_rule = next((rule for rule in rules if rule.rule_id == "runtime_workspace"), None)
            if runtime_rule is None:
                raise ExternalCacheError("EXTERNAL_CACHE_RETENTION_CONTRACT_REQUIRED")
            external = ExternalCache(
                root, policy.job, min(policy.max_bytes, runtime_rule.max_bytes),
                min(policy.max_file_count, runtime_rule.max_files), runtime_rule.retention_seconds,
            )
            take = take_external
        elif os.environ.get("TOP10_EXTERNAL_CACHE_ROOT"):
            raise ExternalCacheError("EXTERNAL_CACHE_ISOLATION_UNSUPPORTED")
        # TTL 的准入修復必須在主機容量預檢通過後，且 child 尚未啟動時進行。
        preflight = replace(
            take_external(None, enforce_retention=False) if external is not None else take(None),
            phase="preflight",
        )
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

        reclaimed = reclaim_allowlisted(root, rules, execute=os.environ.get("AI_CORE_CACHE_MODE") != "directory")
        if external is not None:
            external.reclaim_expired_before_child(exclusive_lock_fd=lock_handle.fileno())
            environment = external.materialize()
        else:
            _materialize_active_runtime_workspace(root, policy.job)
            environment = runtime_environment(root / "logs/storage_safety/runtime" / policy.job)
        temp_guard = LightGBMTempGuard(Path(environment["TMPDIR"]))
        temp_guard.start(execute=lightgbm_temp_cleanup)
        for key, value in environment.items():
            saved_environment[key] = os.environ.get(key)
            os.environ[key] = value
        before_writes = project_write_snapshot(
            root,
            deadline_seconds=observation_deadline_seconds,
        )
        spawn_command = list(command)
        if external is not None:
            spawn_command = _external_cache_spawn_command(root, policy, external, command)
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
                deadline_seconds=observation_deadline_seconds,
            )
            spawn_command = _validation_spawn_command(root, protected_root, trusted_command)
        rotating_log = RotatingLog(
            runtime_dir / f"{policy.job}.log",
            global_policy.log_max_bytes,
            global_policy.log_backups,
        )
        process, process_group = _spawn_verified_process_group(spawn_command, cwd=root)
        started_at = monotonic_now()
        # Fog 目標使用 hard maximum 的 70%，其餘 job 維持 95%。
        # 2026-09-14 production meter_paths 在 DuckDB rebuild I/O 競爭時曾達
        # 14.25 秒、sample_total 14.79 秒；80% target 的 12 秒 completion
        # headroom 已被合法 probe 打穿。70% target 留 18 秒，涵蓋目前實測尖峰
        # 與 scheduler lateness；60 秒 hard maximum 本身不變，真實 completion
        # overrun 仍會 fail closed。
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
            immediate_decision = runtime_decision()
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
        def monitor_memory() -> None:
            """獨立唯讀取樣；單次卡頓警示，持續失明才停損。"""

            interval = min(global_policy.memory_sample_interval_seconds, policy.sample_interval_seconds)
            last_completed = time.monotonic()
            consecutive_overruns = 0
            target = last_completed + interval * 0.8
            while not memory_stop.wait(max(0.0, target - time.monotonic())):
                if process is None or process.poll() is not None:
                    return
                template = samples[-1]
                try:
                    current = _take_memory_sample(template, process.pid)
                except Exception:
                    with memory_lock:
                        memory_errors.append("MEMORY_SAMPLE_UNAVAILABLE")
                    return
                completed = time.monotonic()
                consecutive_overruns, cadence = _memory_cadence_decision(
                    interval, completed - last_completed, consecutive_overruns)
                with memory_lock:
                    memory_errors.extend(cadence.reasons)
                    memory_warnings.extend(cadence.warnings)
                    memory_samples.append(replace(current, phase=("live" if process.poll() is None else "final")))
                last_completed = completed
                target += interval * 0.8
                if target <= completed:
                    target = completed + interval * 0.8

        # 密集完整取樣已涵蓋記憶體；較慢容量週期另取樣，也適用 shared-source sampler。
        # 既有注入時鐘仍由呼叫端控制觀測與 waiter，不混入真實時間執行緒。
        if (monotonic_clock is None and not stop_reasons
                and policy.sample_interval_seconds > global_policy.memory_sample_interval_seconds):
            memory_thread = threading.Thread(target=monitor_memory, name=f"storage-memory-{policy.job}", daemon=True)
            memory_thread.start()
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
            if memory_thread is not None:
                memory_decision = runtime_decision()
                if memory_decision.triggered:
                    stop_reasons = memory_decision.reasons
                    terminate_process_group(process, identity=process_group)
                    break
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
                output_decision = runtime_decision()
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
            if memory_thread is not None:
                wait_seconds = min(wait_seconds, global_policy.memory_sample_interval_seconds)
            deadline_reached = wait_seconds <= 0
            if not deadline_reached:
                try:
                    wait_for_process(process, wait_seconds)
                except subprocess.TimeoutExpired:
                    deadline_reached = True
            if deadline_reached:
                now = monotonic_now()
                if memory_thread is not None and now < wake_deadline:
                    continue
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
                after_writes = project_write_snapshot(
                    root,
                    deadline_seconds=observation_deadline_seconds,
                )
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
                decision = runtime_decision(
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

        stop_memory_monitor()
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
        after_writes = project_write_snapshot(
            root,
            deadline_seconds=observation_deadline_seconds,
        )
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
        final_decision = runtime_decision(
            unknown_paths=observed_unknown_paths,
            registered_unmetered_paths=observed_registered_unmetered_paths,
        )
        stop_reasons = tuple(dict.fromkeys((*stop_reasons, *final_decision.reasons)))
        if protected_root is not None and protected_before is not None:
            protected_after = project_write_snapshot(
                protected_root,
                max_files=PROTECTED_SNAPSHOT_MAX_FILES,
                deadline_seconds=observation_deadline_seconds,
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

        if temp_guard is not None:
            temp_guard.finish()
        final_reclaim = reclaim_allowlisted(root, rules, execute=os.environ.get("AI_CORE_CACHE_MODE") != "directory")
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
            else (exc.reason,)
            if isinstance(exc, (ExternalCacheError, StorageObservationError))
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
        # 僅保留 guard 本檔最內側四個位置；不格式化例外或讀取原始碼、locals。
        # 執行根目錄可能是隔離 fixture，因此用程式檔身分比對並輸出固定相對路徑。
        error_frames: deque[dict[str, Any]] = deque(maxlen=4)
        error_traceback = exc.__traceback__
        while error_traceback is not None:
            code = error_traceback.tb_frame.f_code
            if code.co_filename == run_guarded_job.__code__.co_filename:
                error_frames.append(
                    {
                        "filename": "app/storage_safety.py",
                        "function": code.co_name,
                        "line": error_traceback.tb_lineno,
                    }
                )
            error_traceback = error_traceback.tb_next
        internal_error: dict[str, Any] = {
            "type": type(exc).__name__,
            "frames": list(error_frames),
        }
        error_errno = getattr(exc, "errno", None)
        if type(error_errno) is int:
            internal_error["errno"] = error_errno
        stopped_receipt["internal_error"] = internal_error
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
        # 標準庫 ExitStack 各自執行清理；close 失敗仍須還原環境、handler 並解鎖。
        # 清理例外保留向外傳播，不把未完成清理宣稱成功。
        with ExitStack() as cleanup:
            cleanup.callback(lock_handle.close)
            cleanup.callback(stop_memory_monitor)
            cleanup.callback(fcntl.flock, lock_handle.fileno(), fcntl.LOCK_UN)
            for signum, previous in previous_signal_handlers.items():
                cleanup.callback(signal.signal, signum, previous)
            for key, value in saved_environment.items():
                if value is None:
                    cleanup.callback(os.environ.pop, key, None)
                else:
                    cleanup.callback(os.environ.__setitem__, key, value)
            if external is not None:
                cleanup.callback(external.close)
            if trusted_entrypoint_runtime is not None:
                cleanup.callback(trusted_entrypoint_runtime.cleanup)
            if rotating_log is not None:
                cleanup.callback(rotating_log.close)
            if process is not None and process.stdout is not None:
                cleanup.callback(process.stdout.close)
            if pump_thread is not None and pump_thread.is_alive():
                cleanup.callback(pump_thread.join, timeout=5)
            if process is not None and process_group is not None:
                try:
                    terminate_process_group(process, identity=process_group)
                except (OSError, RuntimeError, subprocess.TimeoutExpired):
                    pass
