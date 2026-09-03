#!/usr/bin/env python3
"""以 bounded transaction 切換三條核心 launchd 排程到獨立 runtime checkout。"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import plistlib
import re
import signal
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Sequence, TextIO


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from validate_runtime_checkout import RuntimeCheckoutError, validate_runtime_checkout  # noqa: E402


SCHEMA_VERSION = "top10.automation-runtime-activation.v1"
TARGET_JOBS = (
    ("daily", "com.new-top10.daily", "com.new-top10.daily.plist"),
    (
        "external-review-preflight",
        "com.new-top10.external-review-preflight",
        "com.new-top10.external-review-preflight.plist",
    ),
    (
        "fog-research-worker",
        "com.new-top10.fog-research-worker",
        "com.new-top10.fog-research-worker.plist",
    ),
)


class ActivationError(RuntimeError):
    """activation transaction 無法安全完成。"""


class RollbackVerificationError(ActivationError):
    """rollback 後外部狀態無法證明已回復。"""


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


CommandRunner = Callable[[Sequence[str]], CommandResult]
FaultHook = Callable[[str, str | None], None]


@dataclass
class JobState:
    guard_name: str
    label: str
    template_name: str
    installed_path: Path
    staged_path: Path
    old_bytes: bytes
    old_sha256: str
    new_bytes: bytes
    new_sha256: str
    old_root: Path
    pre_loaded: bool
    pre_running: bool
    pre_print_sha256: str | None
    old_denial_sha256: str | None
    snapshot_path: Path | None = None
    # 以下旗標代表「rollback obligation 已武裝」，必須早於可能的外部 mutation 設定。
    # 它們不是 mutation 已成功完成的 receipt；rollback 會再 probe 真實狀態後才決定是否反向操作。
    denial_mirrored_sha256: str | None = None
    denial_mirrored_identity: tuple[int, int] | None = None
    denial_cleared: bool = False
    booted_out: bool = False
    replaced: bool = False
    bootstrapped: bool = False


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def default_command_runner(command: Sequence[str]) -> CommandResult:
    completed = subprocess.run(
        list(command),
        text=True,
        capture_output=True,
        check=False,
    )
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def noop_fault_hook(event: str, job: str | None) -> None:
    del event, job


class ActivationTransaction:
    """只處理 daily / external-review-preflight / fog-research-worker。"""

    def __init__(
        self,
        *,
        source_root: Path,
        runtime_root: Path,
        accepted_commit: str,
        launch_agents_dir: Path,
        expected_old_root: Path,
        receipt_path: Path,
        launchctl_bin: str = "/bin/launchctl",
        plutil_bin: str = "/usr/bin/plutil",
        domain: str | None = None,
        command_runner: CommandRunner = default_command_runner,
        fault_hook: FaultHook = noop_fault_hook,
    ) -> None:
        self.source_root = source_root.resolve()
        self.runtime_root = runtime_root.resolve()
        self.accepted_commit = accepted_commit
        self.launch_agents_dir = launch_agents_dir.resolve()
        self.expected_old_root = expected_old_root.resolve()
        self.receipt_path = receipt_path.resolve()
        self.launchctl_bin = launchctl_bin
        self.plutil_bin = plutil_bin
        self.domain = domain or f"gui/{os.getuid()}"
        self.command_runner = command_runner
        self.fault_hook = fault_hook
        self.jobs: list[JobState] = []
        self.staging_paths: list[Path] = []
        self.out_of_scope_plists_before: dict[str, str] = {}
        self.events: list[dict[str, object]] = []
        self.rollback_errors: list[str] = []
        self.new_denial_preserved: list[dict[str, str]] = []
        self._denial_lock_handles: dict[str, TextIO] = {}
        self.armed = False
        self._old_signal_handlers: dict[int, object] = {}
        self.status = "INITIALIZING"
        self.failure: str | None = None
        self.canonical_commit: str | None = None

    def _event(
        self,
        name: str,
        *,
        job: str | None = None,
        result: str = "OK",
        detail: str | None = None,
    ) -> None:
        payload: dict[str, object] = {
            "at": utc_now(),
            "name": name,
            "result": result,
        }
        if job is not None:
            payload["job"] = job
        if detail:
            payload["detail"] = detail
        self.events.append(payload)

    def _run(self, command: Sequence[str]) -> CommandResult:
        return self.command_runner(command)

    def _probe(self, label: str) -> tuple[bool, bool, str]:
        result = self._run(
            [self.launchctl_bin, "print", f"{self.domain}/{label}"]
        )
        if result.returncode != 0:
            return False, False, result.stdout + result.stderr
        text = result.stdout + result.stderr
        running = bool(re.search(r"(?m)^\s*state\s*=\s*running\s*$", text))
        return True, running, text

    @staticmethod
    def _plist_project_root(data: bytes) -> Path:
        payload = plistlib.loads(data)
        arguments = payload.get("ProgramArguments")
        if not isinstance(arguments, list):
            raise ActivationError("installed plist 缺 ProgramArguments")
        roots: set[Path] = set()
        for raw in arguments:
            if not isinstance(raw, str) or "/scripts/" not in raw:
                continue
            roots.add(Path(raw.split("/scripts/", 1)[0]).resolve())
        if len(roots) != 1:
            raise ActivationError(
                f"installed plist 無法唯一判定 scheduler project root: {sorted(map(str, roots))}"
            )
        return next(iter(roots))

    def _render_and_validate_plist(
        self,
        *,
        label: str,
        template_name: str,
        staged_path: Path,
    ) -> bytes:
        template_path = self.runtime_root / "scripts" / template_name
        if not template_path.is_file():
            raise ActivationError(f"runtime template 不存在: {template_path}")
        rendered = template_path.read_text(encoding="utf-8").replace(
            "__PROJECT_DIR__", str(self.runtime_root)
        )
        if "__PROJECT_DIR__" in rendered:
            raise ActivationError(f"plist placeholder 未完全替換: {template_name}")
        staged_path.write_text(rendered, encoding="utf-8")
        lint = self._run([self.plutil_bin, "-lint", str(staged_path)])
        if lint.returncode != 0:
            raise ActivationError(
                f"plutil lint 失敗: {template_name}: {(lint.stderr or lint.stdout).strip()}"
            )
        payload = plistlib.loads(staged_path.read_bytes())
        if payload.get("Label") != label:
            raise ActivationError(
                f"plist label mismatch: expected={label} actual={payload.get('Label')}"
            )
        arguments = payload.get("ProgramArguments")
        if not isinstance(arguments, list):
            raise ActivationError(f"plist ProgramArguments 無效: {template_name}")
        script_args = [item for item in arguments if isinstance(item, str) and "/scripts/" in item]
        if not script_args or any(
            not item.startswith(f"{self.runtime_root}/scripts/") for item in script_args
        ):
            raise ActivationError(
                f"plist runtime path 未全部指向 accepted runtime: {template_name}"
            )
        return staged_path.read_bytes()

    def _snapshot_out_of_scope_plists(self) -> dict[str, str]:
        target_names = {f"{label}.plist" for _, label, _ in TARGET_JOBS}
        return {
            path.name: sha256_file(path)
            for path in sorted(self.launch_agents_dir.glob("com.new-top10.*.plist"))
            if path.name not in target_names and path.is_file()
        }

    def _denial_path(self, root: Path, guard_name: str) -> Path:
        return root / "logs" / "storage_safety" / "restart_denied" / f"{guard_name}.json"

    def _prepare(self) -> None:
        self.status = "PREPARING"
        self.canonical_commit = validate_runtime_checkout(
            self.source_root,
            self.runtime_root,
            self.accepted_commit,
        )
        runtime_python = self.runtime_root / ".venv" / "bin" / "python"
        if not runtime_python.is_file() or not os.access(runtime_python, os.X_OK):
            raise ActivationError("runtime checkout 缺可執行 .venv/bin/python")
        if not self.launch_agents_dir.is_dir():
            raise ActivationError(f"LaunchAgents 目錄不存在: {self.launch_agents_dir}")

        self.out_of_scope_plists_before = self._snapshot_out_of_scope_plists()
        self.jobs.clear()
        self.staging_paths.clear()
        for guard_name, label, template_name in TARGET_JOBS:
            installed_path = self.launch_agents_dir / f"{label}.plist"
            if not installed_path.is_file():
                raise ActivationError(f"缺少既有 installed plist: {installed_path}")
            old_bytes = installed_path.read_bytes()
            old_root = self._plist_project_root(old_bytes)
            if old_root != self.expected_old_root:
                raise ActivationError(
                    f"舊 scheduler root drift: job={guard_name} expected={self.expected_old_root} actual={old_root}"
                )

            loaded, running, print_text = self._probe(label)
            if not loaded:
                raise ActivationError(f"A4 前置拓樸不符：{label} 目前未載入")
            if running:
                raise ActivationError(f"A4 拒絕中斷正在執行的 job: {label}")

            staged_path = self.launch_agents_dir / f".{label}.a4-stage-{os.getpid()}.plist"
            if staged_path.exists():
                raise ActivationError(f"staging path 已存在: {staged_path}")
            self.staging_paths.append(staged_path)
            new_bytes = self._render_and_validate_plist(
                label=label,
                template_name=template_name,
                staged_path=staged_path,
            )

            old_denial = self._denial_path(old_root, guard_name)
            new_denial = self._denial_path(self.runtime_root, guard_name)
            if new_denial.exists():
                raise ActivationError(
                    f"accepted runtime 已有 restart-denied；拒絕覆寫或隱藏新證據: {new_denial}"
                )

            self.jobs.append(
                JobState(
                    guard_name=guard_name,
                    label=label,
                    template_name=template_name,
                    installed_path=installed_path,
                    staged_path=staged_path,
                    old_bytes=old_bytes,
                    old_sha256=sha256_bytes(old_bytes),
                    new_bytes=new_bytes,
                    new_sha256=sha256_bytes(new_bytes),
                    old_root=old_root,
                    pre_loaded=loaded,
                    pre_running=running,
                    pre_print_sha256=sha256_bytes(print_text.encode("utf-8")),
                    old_denial_sha256=(sha256_file(old_denial) if old_denial.is_file() else None),
                )
            )

        self._event("preflight_complete", detail=f"commit={self.canonical_commit}")

    def _persist_prestate_evidence(self) -> None:
        snapshot_dir = self.receipt_path.parent / f"{self.receipt_path.stem}.prestate"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        for job in self.jobs:
            snapshot_path = snapshot_dir / f"{job.label}.plist"
            if snapshot_path.exists() and snapshot_path.read_bytes() != job.old_bytes:
                raise ActivationError(f"prestate snapshot collision: {snapshot_path}")
            self._atomic_write(snapshot_path, job.old_bytes)
            if sha256_file(snapshot_path) != job.old_sha256:
                raise ActivationError(f"prestate snapshot hash mismatch: {job.label}")
            job.snapshot_path = snapshot_path
        self.status = "PREPARED_NO_MUTATION"
        self._event("prestate_evidence_persisted")
        self._write_receipt()

    def _signal_abort(self, signum: int, frame: object) -> None:
        del frame
        raise ActivationError(f"received signal {signum} after rollback handler armed")

    def _arm(self) -> None:
        for signum in (signal.SIGINT, signal.SIGTERM):
            self._old_signal_handlers[signum] = signal.getsignal(signum)
            signal.signal(signum, self._signal_abort)
        self.armed = True
        self._event("rollback_handler_armed")

    def _disarm(self) -> None:
        for signum, handler in self._old_signal_handlers.items():
            signal.signal(signum, handler)
        self._old_signal_handlers.clear()
        self.armed = False

    def _atomic_write(self, path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, raw_tmp = tempfile.mkstemp(prefix=f".{path.name}.a4-", dir=str(path.parent))
        tmp = Path(raw_tmp)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, path)
        finally:
            if tmp.exists():
                tmp.unlink()

    def _create_owned_denial_mirror(self, job: JobState, path: Path, data: bytes) -> None:
        """以 no-replace hard-link 建立 mirror，並在 mutation 前武裝 inode ownership。"""

        path.parent.mkdir(parents=True, exist_ok=True)
        fd, raw_tmp = tempfile.mkstemp(prefix=f".{path.name}.a4-", dir=str(path.parent))
        tmp = Path(raw_tmp)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            stat_result = tmp.stat()
            job.denial_mirrored_identity = (stat_result.st_dev, stat_result.st_ino)
            os.link(tmp, path)
        finally:
            if tmp.exists():
                tmp.unlink()

    @staticmethod
    def _path_identity(path: Path) -> tuple[int, int] | None:
        try:
            stat_result = path.stat()
        except FileNotFoundError:
            return None
        return stat_result.st_dev, stat_result.st_ino

    def _acquire_denial_locks(self) -> None:
        runtime_dir = self.runtime_root / "logs" / "storage_safety"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        for job in self.jobs:
            lock_path = runtime_dir / f"{job.guard_name}.lock"
            handle = lock_path.open("a+")
            self._denial_lock_handles[job.guard_name] = handle
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                self._denial_lock_handles.pop(job.guard_name, None)
                handle.close()
                raise ActivationError(
                    f"accepted runtime storage guard lock 正被持有: {job.guard_name}"
                ) from exc
            new_marker = self._denial_path(self.runtime_root, job.guard_name)
            if new_marker.exists():
                raise ActivationError(
                    f"accepted runtime denial 在 preflight 後出現，拒絕覆寫: {job.guard_name}"
                )
        self._event("denial_writer_locks_acquired")

    def _release_denial_lock(self, job: JobState) -> None:
        handle = self._denial_lock_handles.get(job.guard_name)
        if handle is None:
            return
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()
            self._denial_lock_handles.pop(job.guard_name, None)
        self._event("denial_writer_lock_released", job=job.guard_name)

    def _release_all_denial_locks(self) -> None:
        for job in self.jobs:
            self._release_denial_lock(job)

    def _mirror_and_clear_denials(self) -> None:
        for job in self.jobs:
            old_marker = self._denial_path(job.old_root, job.guard_name)
            if not old_marker.is_file():
                continue
            old_bytes = old_marker.read_bytes()
            old_hash = sha256_bytes(old_bytes)
            if old_hash != job.old_denial_sha256:
                raise ActivationError(
                    f"舊 denial marker 在 transaction snapshot 後改變: {job.guard_name}"
                )
            new_marker = self._denial_path(self.runtime_root, job.guard_name)
            self.fault_hook("before_denial_mirror", job.guard_name)
            # accepted runtime 在 _prepare() 已驗證 marker 不存在；先登記 ownership，避免
            # atomic write 完成後、Python bookkeeping 前收到 signal 時遺失 rollback 責任。
            job.denial_mirrored_sha256 = old_hash
            try:
                self._create_owned_denial_mirror(job, new_marker, old_bytes)
            except FileExistsError as exc:
                raise ActivationError(
                    f"accepted runtime denial 在 preflight 後出現，拒絕覆寫: {job.guard_name}"
                ) from exc
            self.fault_hook(
                "after_denial_mirror_write_before_verify", job.guard_name
            )
            self._event("denial_mirrored", job=job.guard_name, detail=f"sha256={old_hash}")
            self.fault_hook("after_denial_mirror", job.guard_name)
            if self._path_identity(new_marker) != job.denial_mirrored_identity:
                raise ActivationError(f"denial mirror ownership changed: {job.guard_name}")
            if sha256_file(new_marker) != old_hash:
                raise ActivationError(f"denial mirror hash mismatch: {job.guard_name}")
            self.fault_hook("before_denial_clear", job.guard_name)
            if self._path_identity(new_marker) != job.denial_mirrored_identity:
                raise ActivationError(
                    f"new denial ownership changed before explicit clear: {job.guard_name}"
                )
            if sha256_file(new_marker) != old_hash:
                raise ActivationError(
                    f"new denial evidence appeared before explicit clear: {job.guard_name}"
                )
            new_marker.unlink()
            job.denial_cleared = True
            self._event(
                "denial_explicitly_cleared_for_activation",
                job=job.guard_name,
                detail=f"preserved_old_sha256={old_hash}",
            )
            self.fault_hook("after_denial_clear", job.guard_name)

    def _bootout(self, job: JobState) -> None:
        self.fault_hook("before_bootout", job.guard_name)
        # 先武裝 restore obligation；若 signal 落在 launchctl mutation 與 probe 之間，
        # rollback 仍會依真實 loaded state 決定是否需要 bootstrap 舊 job。
        job.booted_out = True
        result = self._run(
            [self.launchctl_bin, "bootout", self.domain, str(job.installed_path)]
        )
        self.fault_hook("after_bootout_mutation_before_probe", job.guard_name)
        loaded_after, _, _ = self._probe(job.label)
        if result.returncode != 0:
            raise ActivationError(
                f"bootout failed: {job.label}: {(result.stderr or result.stdout).strip()}"
            )
        if loaded_after:
            raise ActivationError(f"bootout returned success but job still loaded: {job.label}")
        self._event("bootout_complete", job=job.guard_name)
        self.fault_hook("after_bootout", job.guard_name)

    def _replace_plist(self, job: JobState) -> None:
        self.fault_hook("before_plist_replace", job.guard_name)
        # 先武裝 exact-bytes restore obligation。即使 os.replace 尚未 mutation 就失敗，
        # rollback 也會先比對 hash，old bytes 未變時不做多餘 rewrite。
        job.replaced = True
        os.replace(job.staged_path, job.installed_path)
        self.fault_hook(
            "after_plist_replace_mutation_before_verify", job.guard_name
        )
        if sha256_file(job.installed_path) != job.new_sha256:
            raise ActivationError(f"atomic plist replace hash mismatch: {job.label}")
        self._event("plist_replace_complete", job=job.guard_name, detail=f"sha256={job.new_sha256}")
        self.fault_hook("after_plist_replace", job.guard_name)

    def _bootstrap(self, job: JobState) -> None:
        self.fault_hook("before_bootstrap", job.guard_name)
        # 與 bootout 相同：先登記 rollback obligation，再做外部 mutation。
        job.bootstrapped = True
        result = self._run(
            [self.launchctl_bin, "bootstrap", self.domain, str(job.installed_path)]
        )
        self.fault_hook("after_bootstrap_mutation_before_probe", job.guard_name)
        loaded_after, _, print_text = self._probe(job.label)
        if result.returncode != 0:
            raise ActivationError(
                f"bootstrap failed: {job.label}: {(result.stderr or result.stdout).strip()}"
            )
        if not loaded_after:
            raise ActivationError(f"bootstrap returned success but job not loaded: {job.label}")
        if str(self.runtime_root) not in print_text:
            raise ActivationError(
                f"launchctl owner path 未指向 accepted runtime: {job.label}"
            )
        self._event("bootstrap_complete", job=job.guard_name)
        self.fault_hook("after_bootstrap", job.guard_name)

    def _verify_success(self) -> None:
        for job in self.jobs:
            if sha256_file(job.installed_path) != job.new_sha256:
                raise ActivationError(f"installed plist hash drift after bootstrap: {job.label}")
            loaded, _, print_text = self._probe(job.label)
            if not loaded or str(self.runtime_root) not in print_text:
                raise ActivationError(f"post-activation topology mismatch: {job.label}")
            old_marker = self._denial_path(job.old_root, job.guard_name)
            current_old_hash = sha256_file(old_marker) if old_marker.is_file() else None
            if current_old_hash != job.old_denial_sha256:
                raise ActivationError(f"old denial evidence changed during activation: {job.guard_name}")
            new_marker = self._denial_path(self.runtime_root, job.guard_name)
            if new_marker.exists():
                raise ActivationError(
                    f"accepted runtime 在 activation 期間出現新 denial: {job.guard_name}"
                )
        if self._snapshot_out_of_scope_plists() != self.out_of_scope_plists_before:
            raise ActivationError("out-of-scope launchd plist changed during bounded activation")
        self._event("activation_verification_complete")

    def _rollback_job(self, job: JobState) -> None:
        if job.bootstrapped:
            loaded_now, _, _ = self._probe(job.label)
            if loaded_now:
                result = self._run(
                    [self.launchctl_bin, "bootout", self.domain, str(job.installed_path)]
                )
                loaded_after, _, _ = self._probe(job.label)
                if result.returncode != 0 and loaded_after:
                    self.rollback_errors.append(
                        f"rollback bootout failed and job remains loaded: {job.label}"
                    )
                elif not loaded_after:
                    job.bootstrapped = False
            else:
                job.bootstrapped = False

        if job.replaced:
            try:
                current_hash = (
                    sha256_file(job.installed_path)
                    if job.installed_path.is_file()
                    else None
                )
                if current_hash != job.old_sha256:
                    self._atomic_write(job.installed_path, job.old_bytes)
                job.replaced = False
            except Exception as exc:  # noqa: BLE001 - rollback 要繼續收集所有 failure state。
                self.rollback_errors.append(f"restore plist failed {job.label}: {exc}")

        if job.booted_out:
            loaded_now, _, _ = self._probe(job.label)
            if not loaded_now:
                result = self._run(
                    [self.launchctl_bin, "bootstrap", self.domain, str(job.installed_path)]
                )
                loaded_after, _, _ = self._probe(job.label)
                if result.returncode != 0 or not loaded_after:
                    self.rollback_errors.append(f"restore bootstrap failed: {job.label}")
                else:
                    job.booted_out = False
            else:
                job.booted_out = False

        if job.pre_running:
            loaded_now, running_now, _ = self._probe(job.label)
            if loaded_now and not running_now:
                result = self._run(
                    [self.launchctl_bin, "kickstart", f"{self.domain}/{job.label}"]
                )
                if result.returncode != 0:
                    self.rollback_errors.append(f"restore running state failed: {job.label}")

        new_marker = self._denial_path(self.runtime_root, job.guard_name)
        if new_marker.is_file() and job.denial_mirrored_identity and not job.denial_cleared:
            if self._path_identity(new_marker) == job.denial_mirrored_identity:
                new_marker.unlink()
                self._event("transaction_denial_mirror_removed_on_rollback", job=job.guard_name)

    def _verify_rollback(self) -> None:
        self.fault_hook("before_rollback_verification", None)
        mismatches: list[str] = []
        for job in self.jobs:
            if not job.installed_path.is_file() or sha256_file(job.installed_path) != job.old_sha256:
                mismatches.append(f"plist:{job.label}")
            loaded, running, print_text = self._probe(job.label)
            if loaded != job.pre_loaded:
                mismatches.append(f"loaded:{job.label}")
            if running != job.pre_running:
                mismatches.append(f"running:{job.label}")
            if loaded and str(job.old_root) not in print_text:
                mismatches.append(f"root:{job.label}")

            old_marker = self._denial_path(job.old_root, job.guard_name)
            current_old_hash = sha256_file(old_marker) if old_marker.is_file() else None
            if current_old_hash != job.old_denial_sha256:
                mismatches.append(f"old-denial:{job.guard_name}")

            new_marker = self._denial_path(self.runtime_root, job.guard_name)
            if new_marker.is_file():
                preserved_hash = sha256_file(new_marker)
                self.new_denial_preserved.append(
                    {"job": job.guard_name, "sha256": preserved_hash, "path": str(new_marker)}
                )
                self._event(
                    "new_denial_preserved_during_rollback",
                    job=job.guard_name,
                    detail=f"sha256={preserved_hash}",
                )

        if self._snapshot_out_of_scope_plists() != self.out_of_scope_plists_before:
            mismatches.append("out-of-scope-plists")
        for staged_path in self.staging_paths:
            if staged_path.exists():
                mismatches.append(f"staging-residue:{staged_path.name}")
        if self.rollback_errors:
            mismatches.extend(f"rollback-error:{item}" for item in self.rollback_errors)
        if mismatches:
            raise RollbackVerificationError(
                "ROLLBACK_VERIFICATION_FAILED: " + ", ".join(mismatches)
            )
        self._event("rollback_verification_complete")

    def _rollback(self) -> None:
        self.status = "ROLLING_BACK"
        self._event("rollback_started")
        self.fault_hook("rollback_started", None)
        for job in reversed(self.jobs):
            try:
                self._rollback_job(job)
            except Exception as exc:  # noqa: BLE001 - 後續 job 仍要盡力 restore。
                self.rollback_errors.append(f"rollback exception {job.label}: {exc}")
        self._cleanup_staging(record_errors=True)
        self._verify_rollback()
        self.status = "ROLLED_BACK_NO_GO"

    def _cleanup_staging(self, *, record_errors: bool = False) -> None:
        for staged_path in self.staging_paths:
            if staged_path.exists():
                try:
                    staged_path.unlink()
                except OSError as exc:
                    if record_errors:
                        self.rollback_errors.append(
                            f"staging cleanup failed {staged_path.name}: {exc}"
                        )

    def _receipt_payload(self) -> dict[str, object]:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": self.status,
            "failure": self.failure,
            "source_root": str(self.source_root),
            "runtime_root": str(self.runtime_root),
            "accepted_commit": self.accepted_commit,
            "canonical_commit": self.canonical_commit,
            "domain": self.domain,
            "target_labels": [label for _, label, _ in TARGET_JOBS],
            "jobs": {
                job.guard_name: {
                    "label": job.label,
                    "installed_path": str(job.installed_path),
                    "old_sha256": job.old_sha256,
                    "new_sha256": job.new_sha256,
                    "old_root": str(job.old_root),
                    "pre_loaded": job.pre_loaded,
                    "pre_running": job.pre_running,
                    "old_denial_sha256": job.old_denial_sha256,
                    "snapshot_path": str(job.snapshot_path) if job.snapshot_path else None,
                }
                for job in self.jobs
            },
            "out_of_scope_plists_before": self.out_of_scope_plists_before,
            "rollback_errors": self.rollback_errors,
            "new_denial_preserved": self.new_denial_preserved,
            "events": self.events,
            "finished_at": utc_now(),
        }

    def _write_receipt(self) -> None:
        self.receipt_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            self._receipt_payload(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ).encode("utf-8") + b"\n"
        self._atomic_write(self.receipt_path, payload)

    def run(self) -> str:
        try:
            self._prepare()
            self._persist_prestate_evidence()
            self._arm()
            self._acquire_denial_locks()
            self._mirror_and_clear_denials()
            for job in self.jobs:
                self._bootout(job)
                self._replace_plist(job)
                self._release_denial_lock(job)
                self._bootstrap(job)
            self._verify_success()
            self.status = "ACTIVATED_PARTIAL_ACCEPTANCE_PENDING"
            self._event("transaction_committed")
            self._write_receipt()
            return self.status
        except Exception as exc:  # noqa: BLE001 - transaction boundary 必須統一進 rollback。
            self.failure = f"{type(exc).__name__}: {exc}"
            if self.armed:
                try:
                    self._rollback()
                except RollbackVerificationError as rollback_exc:
                    self.status = "ROLLBACK_VERIFICATION_FAILED"
                    self.failure = f"{self.failure}; {rollback_exc}"
                except Exception as rollback_exc:  # noqa: BLE001
                    self.status = "ROLLBACK_VERIFICATION_FAILED"
                    self.failure = (
                        f"{self.failure}; rollback exception: "
                        f"{type(rollback_exc).__name__}: {rollback_exc}"
                    )
            else:
                self.status = "PRECHECK_FAILED"
            self._cleanup_staging(record_errors=self.armed)
            self._write_receipt()
            return self.status
        finally:
            self._cleanup_staging()
            self._release_all_denial_locks()
            if self.armed:
                self._disarm()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--accepted-commit", required=True)
    parser.add_argument("--expected-old-root", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument(
        "--launch-agents-dir",
        type=Path,
        default=Path.home() / "Library" / "LaunchAgents",
    )
    parser.add_argument("--activate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.activate:
        print("A4_ACTIVATION_NO_GO: 缺 --activate 明確 mutation flag", file=sys.stderr)
        return 64
    source_root = SCRIPT_DIR.parent
    transaction = ActivationTransaction(
        source_root=source_root,
        runtime_root=args.runtime_root,
        accepted_commit=args.accepted_commit,
        launch_agents_dir=args.launch_agents_dir,
        expected_old_root=args.expected_old_root,
        receipt_path=args.receipt,
    )
    try:
        status = transaction.run()
    except RuntimeCheckoutError as exc:
        print(f"A4_ACTIVATION_NO_GO: {exc}", file=sys.stderr)
        return 64
    print(status)
    if status == "ACTIVATED_PARTIAL_ACCEPTANCE_PENDING":
        return 0
    if status == "ROLLBACK_VERIFICATION_FAILED":
        return 74
    return 75


if __name__ == "__main__":
    raise SystemExit(main())
