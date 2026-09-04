"""A4 三條核心 launchd transaction 的 failure-state regression。"""

from __future__ import annotations

import json
import multiprocessing
import os
import plistlib
import shutil
import signal
import stat
from pathlib import Path
from typing import Callable

import pytest

from scripts import activate_automation_runtime as activation


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ACCEPTED_SHA = "a" * 40


def _project_root_from_plist(path: Path) -> Path:
    payload = plistlib.loads(path.read_bytes())
    for raw in payload["ProgramArguments"]:
        if isinstance(raw, str) and "/scripts/" in raw:
            return Path(raw.split("/scripts/", 1)[0]).resolve()
    raise AssertionError(f"missing project root in {path}")


class FakeCommandRunner:
    """模擬 launchctl 的非 idempotent mutation，重複操作會直接失敗。"""

    def __init__(self, old_root: Path) -> None:
        self.states = {
            label: {"loaded": True, "running": False, "root": old_root.resolve()}
            for _, label, _ in activation.TARGET_JOBS
        }
        self.calls: list[tuple[str, str | None]] = []
        self.failures: dict[tuple[str, str], str] = {}
        self.fail_plutil = False

    def fail(self, operation: str, label: str, *, when: str) -> None:
        self.failures[(operation, label)] = when

    def _label_from_plist(self, path: str) -> str:
        return str(plistlib.loads(Path(path).read_bytes())["Label"])

    def _failure(self, operation: str, label: str) -> str | None:
        return self.failures.get((operation, label))

    def __call__(self, command: list[str] | tuple[str, ...]) -> activation.CommandResult:
        operation = command[1]
        if operation == "-lint":
            self.calls.append(("plutil", None))
            return activation.CommandResult(1 if self.fail_plutil else 0, "", "lint failed")

        if operation == "print":
            label = command[2].rsplit("/", 1)[-1]
            state = self.states[label]
            self.calls.append(("print", label))
            if not state["loaded"]:
                return activation.CommandResult(113, "", "not loaded")
            run_state = "running" if state["running"] else "waiting"
            root = state["root"]
            output = (
                f"service = {{\n"
                f"    state = {run_state}\n"
                f"    arguments = {{ {root}/scripts/fake-entrypoint.sh }}\n"
                f"}}\n"
            )
            return activation.CommandResult(0, output, "")

        if operation == "bootout":
            label = self._label_from_plist(command[3])
            self.calls.append(("bootout", label))
            failure = self._failure("bootout", label)
            if failure == "before":
                return activation.CommandResult(5, "", "injected bootout-before")
            state = self.states[label]
            if not state["loaded"]:
                return activation.CommandResult(37, "", "duplicate bootout rejected")
            state["loaded"] = False
            state["running"] = False
            if failure == "interrupt_after":
                raise activation.ActivationError(
                    "injected signal after bootout mutation before probe"
                )
            if failure == "after":
                return activation.CommandResult(5, "", "injected bootout-after")
            return activation.CommandResult(0, "", "")

        if operation == "bootstrap":
            label = self._label_from_plist(command[3])
            self.calls.append(("bootstrap", label))
            failure = self._failure("bootstrap", label)
            if failure == "before":
                # 只讓第一次 bootstrap 失敗；rollback restore 必須仍可成功。
                del self.failures[("bootstrap", label)]
                return activation.CommandResult(5, "", "injected bootstrap-before")
            state = self.states[label]
            if state["loaded"]:
                return activation.CommandResult(37, "", "duplicate bootstrap rejected")
            state["loaded"] = True
            state["running"] = False
            state["root"] = _project_root_from_plist(Path(command[3]))
            if failure == "interrupt_after":
                del self.failures[("bootstrap", label)]
                raise activation.ActivationError(
                    "injected signal after bootstrap mutation before probe"
                )
            if failure == "after":
                del self.failures[("bootstrap", label)]
                return activation.CommandResult(5, "", "injected bootstrap-after")
            return activation.CommandResult(0, "", "")

        if operation == "kickstart":
            label = command[2].rsplit("/", 1)[-1]
            self.calls.append(("kickstart", label))
            state = self.states[label]
            if not state["loaded"]:
                return activation.CommandResult(37, "", "not loaded")
            state["running"] = True
            return activation.CommandResult(0, "", "")

        raise AssertionError(f"unexpected command: {command}")


def _render_template(template_name: str, root: Path) -> bytes:
    template = (PROJECT_ROOT / "scripts" / template_name).read_text(encoding="utf-8")
    return template.replace("__PROJECT_DIR__", str(root.resolve())).encode("utf-8")


@pytest.fixture
def activation_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    old_root = tmp_path / "old-runtime"
    runtime_root = tmp_path / "new-runtime"
    launch_agents = tmp_path / "LaunchAgents"
    scripts_dir = runtime_root / "scripts"
    python_bin = runtime_root / ".venv" / "bin" / "python"
    launch_agents.mkdir(parents=True)
    scripts_dir.mkdir(parents=True)
    python_bin.parent.mkdir(parents=True)
    python_bin.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    python_bin.chmod(0o755)

    for guard_name, label, template_name in activation.TARGET_JOBS:
        shutil.copy2(PROJECT_ROOT / "scripts" / template_name, scripts_dir / template_name)
        (launch_agents / f"{label}.plist").write_bytes(
            _render_template(template_name, old_root)
        )

    untouched = launch_agents / "com.new-top10.external-review.plist"
    untouched.write_bytes(b"out-of-scope-must-remain-identical\n")

    for guard_name in ("daily", "fog-research-worker"):
        marker = old_root / "logs" / "storage_safety" / "restart_denied" / f"{guard_name}.json"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(
            json.dumps({"job": guard_name, "reason": "UNREGISTERED_WRITE_PATH"}),
            encoding="utf-8",
        )

    monkeypatch.setattr(
        activation,
        "validate_runtime_checkout",
        lambda source_root, runtime_root, accepted_commit: ACCEPTED_SHA,
    )
    runner = FakeCommandRunner(old_root)
    receipt = tmp_path / "evidence" / "activation.json"

    def build(
        *,
        hook: activation.FaultHook = activation.noop_fault_hook,
    ) -> activation.ActivationTransaction:
        return activation.ActivationTransaction(
            source_root=PROJECT_ROOT,
            runtime_root=runtime_root,
            accepted_commit=ACCEPTED_SHA,
            launch_agents_dir=launch_agents,
            expected_old_root=old_root,
            receipt_path=receipt,
            launchctl_bin="launchctl",
            plutil_bin="plutil",
            domain="gui/999",
            command_runner=runner,
            fault_hook=hook,
        )

    return {
        "old_root": old_root,
        "runtime_root": runtime_root,
        "launch_agents": launch_agents,
        "untouched": untouched,
        "runner": runner,
        "receipt": receipt,
        "build": build,
    }


def _target_bytes(env: dict[str, object]) -> dict[str, bytes]:
    launch_agents = env["launch_agents"]
    assert isinstance(launch_agents, Path)
    return {
        label: (launch_agents / f"{label}.plist").read_bytes()
        for _, label, _ in activation.TARGET_JOBS
    }


def _assert_old_topology(env: dict[str, object]) -> None:
    old_root = env["old_root"]
    runner = env["runner"]
    assert isinstance(old_root, Path)
    assert isinstance(runner, FakeCommandRunner)
    for _, label, _ in activation.TARGET_JOBS:
        assert runner.states[label] == {
            "loaded": True,
            "running": False,
            "root": old_root.resolve(),
        }


def test_preflight_failure_occurs_before_first_bootout_and_cleans_stage(
    activation_env: dict[str, object],
) -> None:
    runner = activation_env["runner"]
    build = activation_env["build"]
    launch_agents = activation_env["launch_agents"]
    assert isinstance(runner, FakeCommandRunner)
    assert callable(build)
    assert isinstance(launch_agents, Path)
    runner.fail_plutil = True
    before = _target_bytes(activation_env)

    transaction = build()
    # staging 寫入與 lint 都在 arm 後，故任何失敗都走唯一 rollback path。
    assert transaction.run() == "ROLLED_BACK_NO_GO"

    assert not any(operation == "bootout" for operation, _ in runner.calls)
    assert _target_bytes(activation_env) == before
    assert not list(launch_agents.glob(".*.a4-stage-*.plist"))
    _assert_old_topology(activation_env)


def test_existing_receipt_path_is_rejected_before_any_mutation(
    activation_env: dict[str, object],
) -> None:
    build = activation_env["build"]
    receipt = activation_env["receipt"]
    runner = activation_env["runner"]
    assert callable(build)
    assert isinstance(receipt, Path)
    assert isinstance(runner, FakeCommandRunner)
    stale = b'{"status":"ACTIVATED_PARTIAL_ACCEPTANCE_PENDING","stale":true}\n'
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_bytes(stale)
    before = _target_bytes(activation_env)

    transaction = build()
    assert transaction.run() == "PRECHECK_FAILED"

    assert receipt.read_bytes() == stale
    assert not any(operation == "bootout" for operation, _ in runner.calls)
    assert _target_bytes(activation_env) == before
    _assert_old_topology(activation_env)


@pytest.mark.parametrize("when", ["before", "after"])
def test_first_bootout_failure_restores_exact_prestate_without_duplicate_mutation(
    activation_env: dict[str, object], when: str
) -> None:
    runner = activation_env["runner"]
    build = activation_env["build"]
    assert isinstance(runner, FakeCommandRunner)
    assert callable(build)
    before = _target_bytes(activation_env)
    runner.fail("bootout", "com.new-top10.daily", when=when)

    transaction = build()
    assert transaction.run() == "ROLLED_BACK_NO_GO"

    assert _target_bytes(activation_env) == before
    _assert_old_topology(activation_env)
    if when == "before":
        assert ("bootstrap", "com.new-top10.daily") not in runner.calls
    else:
        assert runner.calls.count(("bootstrap", "com.new-top10.daily")) == 1


def test_bootout_interruption_after_mutation_before_probe_restores_exact_prestate(
    activation_env: dict[str, object],
) -> None:
    runner = activation_env["runner"]
    build = activation_env["build"]
    assert isinstance(runner, FakeCommandRunner)
    assert callable(build)
    before = _target_bytes(activation_env)
    runner.fail("bootout", "com.new-top10.daily", when="interrupt_after")

    transaction = build()
    assert transaction.run() == "ROLLED_BACK_NO_GO"

    assert _target_bytes(activation_env) == before
    _assert_old_topology(activation_env)
    assert runner.calls.count(("bootstrap", "com.new-top10.daily")) == 1


@pytest.mark.parametrize("when", ["before", "after"])
def test_plist_replace_failure_restores_exact_bytes_and_topology(
    activation_env: dict[str, object], when: str
) -> None:
    build = activation_env["build"]
    assert callable(build)
    before = _target_bytes(activation_env)

    def hook(event: str, job: str | None) -> None:
        if job == "daily" and event == f"{when}_plist_replace":
            raise OSError(f"injected replace-{when}")

    transaction = build(hook=hook)
    assert transaction.run() == "ROLLED_BACK_NO_GO"
    assert _target_bytes(activation_env) == before
    _assert_old_topology(activation_env)


def test_plist_replace_interruption_after_mutation_before_verify_restores_exact_prestate(
    activation_env: dict[str, object],
) -> None:
    build = activation_env["build"]
    assert callable(build)
    before = _target_bytes(activation_env)

    def hook(event: str, job: str | None) -> None:
        if job == "daily" and event == "after_plist_replace_mutation_before_verify":
            raise activation.ActivationError(
                "injected signal after plist mutation before verify"
            )

    transaction = build(hook=hook)
    assert transaction.run() == "ROLLED_BACK_NO_GO"
    assert _target_bytes(activation_env) == before
    _assert_old_topology(activation_env)


def test_activation_plist_replace_flushes_file_and_fsyncs_parent_directory(
    activation_env: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    """每個 target plist replace 都必須由 file fsync 與 parent fsync 夾住。"""

    build = activation_env["build"]
    launch_agents = activation_env["launch_agents"]
    assert callable(build)
    assert isinstance(launch_agents, Path)
    original_fsync = activation.os.fsync
    original_replace = activation.os.replace
    observed: list[tuple[str, str]] = []

    def fd_path(fd: int) -> Path:
        raw = activation.fcntl.fcntl(fd, 50, b"\0" * 1024)
        return Path(os.fsdecode(raw.split(b"\0", 1)[0])).resolve()

    def observe_fsync(fd: int) -> None:
        path = fd_path(fd)
        if path == launch_agents:
            observed.append(("fsync-directory", path.name))
        elif path.parent == launch_agents and ".a4-stage-" in path.name:
            observed.append(("fsync-staged-file", path.name))
        original_fsync(fd)

    def observe_replace(source: Path, destination: Path) -> None:
        source_path = Path(source)
        destination_path = Path(destination)
        if destination_path.parent == launch_agents:
            observed.append(("replace", destination_path.name))
            assert ".a4-stage-" in source_path.name
        original_replace(source, destination)

    monkeypatch.setattr(activation.os, "fsync", observe_fsync)
    monkeypatch.setattr(activation.os, "replace", observe_replace)
    transaction = build()
    assert transaction.run() == "ACTIVATED_PARTIAL_ACCEPTANCE_PENDING"

    expected = [
        ("fsync-staged-file", f".{label}.a4-stage-{os.getpid()}.plist")
        for _, label, _ in activation.TARGET_JOBS
    ]
    for _, label, _ in activation.TARGET_JOBS:
        expected.extend(
            [
                ("replace", f"{label}.plist"),
                ("fsync-directory", launch_agents.name),
            ]
        )
    assert observed == expected


def test_activation_plist_parent_fsync_failure_rolls_back_durably_once(
    activation_env: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    """一次性 LaunchAgents fsync failure 必須完成 durable exact rollback。"""

    build = activation_env["build"]
    launch_agents = activation_env["launch_agents"]
    runtime_root = activation_env["runtime_root"]
    receipt = activation_env["receipt"]
    assert callable(build)
    assert isinstance(launch_agents, Path)
    assert isinstance(runtime_root, Path)
    assert isinstance(receipt, Path)
    before = _target_bytes(activation_env)
    original_fsync = activation.os.fsync
    original_replace = activation.os.replace
    directory_fsync_calls = 0
    plist_replaces: list[str] = []

    def fail_first_launch_agents_fsync(fd: int) -> None:
        nonlocal directory_fsync_calls
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            raw = activation.fcntl.fcntl(fd, 50, b"\0" * 1024)
            path = Path(os.fsdecode(raw.split(b"\0", 1)[0])).resolve()
            if path == launch_agents:
                directory_fsync_calls += 1
                if directory_fsync_calls == 1:
                    raise OSError("injected one-shot LaunchAgents fsync failure")
        original_fsync(fd)

    def count_plist_replace(source: Path, destination: Path) -> None:
        destination_path = Path(destination)
        if destination_path.parent == launch_agents:
            plist_replaces.append(destination_path.name)
        original_replace(source, destination)

    monkeypatch.setattr(activation.os, "fsync", fail_first_launch_agents_fsync)
    monkeypatch.setattr(activation.os, "replace", count_plist_replace)
    transaction = build()
    assert transaction.run() == "ROLLED_BACK_NO_GO"

    daily_plist = "com.new-top10.daily.plist"
    assert directory_fsync_calls == 2
    assert plist_replaces == [daily_plist, daily_plist]
    assert _target_bytes(activation_env) == before
    _assert_old_topology(activation_env)
    durable = json.loads(receipt.read_text(encoding="utf-8"))
    assert durable["status"] == "ROLLED_BACK_NO_GO"
    assert not list(launch_agents.glob(".*.a4-stage-*.plist"))
    for guard_name, _, _ in activation.TARGET_JOBS:
        lock_path = runtime_root / "logs" / "storage_safety" / f"{guard_name}.lock"
        with lock_path.open("a+") as handle:
            activation.fcntl.flock(handle.fileno(), activation.fcntl.LOCK_EX | activation.fcntl.LOCK_NB)
            activation.fcntl.flock(handle.fileno(), activation.fcntl.LOCK_UN)


def test_persistent_plist_parent_fsync_failure_is_rollback_verification_failed(
    activation_env: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rollback bytes 可見但 parent fsync 未確認時不得宣稱 exact restore。"""

    build = activation_env["build"]
    launch_agents = activation_env["launch_agents"]
    runtime_root = activation_env["runtime_root"]
    receipt = activation_env["receipt"]
    assert callable(build)
    assert isinstance(launch_agents, Path)
    assert isinstance(runtime_root, Path)
    assert isinstance(receipt, Path)
    before = _target_bytes(activation_env)
    original_fsync = activation.os.fsync
    original_replace = activation.os.replace
    directory_fsync_calls = 0
    plist_replaces: list[str] = []

    def fail_launch_agents_fsync(fd: int) -> None:
        nonlocal directory_fsync_calls
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            raw = activation.fcntl.fcntl(fd, 50, b"\0" * 1024)
            path = Path(os.fsdecode(raw.split(b"\0", 1)[0])).resolve()
            if path == launch_agents:
                directory_fsync_calls += 1
                raise OSError("injected persistent LaunchAgents fsync failure")
        original_fsync(fd)

    def count_plist_replace(source: Path, destination: Path) -> None:
        destination_path = Path(destination)
        if destination_path.parent == launch_agents:
            plist_replaces.append(destination_path.name)
        original_replace(source, destination)

    monkeypatch.setattr(activation.os, "fsync", fail_launch_agents_fsync)
    monkeypatch.setattr(activation.os, "replace", count_plist_replace)
    transaction = build()
    assert transaction.run() == "ROLLBACK_VERIFICATION_FAILED"

    daily_plist = "com.new-top10.daily.plist"
    assert directory_fsync_calls == 2
    assert plist_replaces == [daily_plist, daily_plist]
    assert _target_bytes(activation_env) == before
    _assert_old_topology(activation_env)
    durable = json.loads(receipt.read_text(encoding="utf-8"))
    assert durable["status"] == "ROLLBACK_VERIFICATION_FAILED"
    assert any("persistent LaunchAgents fsync failure" in item for item in durable["rollback_errors"])
    assert not list(launch_agents.glob(".*.a4-stage-*.plist"))
    for guard_name, _, _ in activation.TARGET_JOBS:
        lock_path = runtime_root / "logs" / "storage_safety" / f"{guard_name}.lock"
        with lock_path.open("a+") as handle:
            activation.fcntl.flock(handle.fileno(), activation.fcntl.LOCK_EX | activation.fcntl.LOCK_NB)
            activation.fcntl.flock(handle.fileno(), activation.fcntl.LOCK_UN)


@pytest.mark.parametrize("when", ["before", "after"])
def test_bootstrap_failure_before_or_after_mutation_is_detected_and_reversed(
    activation_env: dict[str, object], when: str
) -> None:
    runner = activation_env["runner"]
    build = activation_env["build"]
    assert isinstance(runner, FakeCommandRunner)
    assert callable(build)
    before = _target_bytes(activation_env)
    runner.fail("bootstrap", "com.new-top10.daily", when=when)

    transaction = build()
    assert transaction.run() == "ROLLED_BACK_NO_GO"

    assert _target_bytes(activation_env) == before
    _assert_old_topology(activation_env)
    # 一次是 activation 嘗試，一次是 rollback restore；fake runtime 會拒絕重複 bootstrap。
    assert runner.calls.count(("bootstrap", "com.new-top10.daily")) == 2


def test_bootstrap_interruption_after_mutation_before_probe_restores_exact_prestate(
    activation_env: dict[str, object],
) -> None:
    runner = activation_env["runner"]
    build = activation_env["build"]
    assert isinstance(runner, FakeCommandRunner)
    assert callable(build)
    before = _target_bytes(activation_env)
    runner.fail("bootstrap", "com.new-top10.daily", when="interrupt_after")

    transaction = build()
    assert transaction.run() == "ROLLED_BACK_NO_GO"

    assert _target_bytes(activation_env) == before
    _assert_old_topology(activation_env)
    assert runner.calls.count(("bootstrap", "com.new-top10.daily")) == 2


def test_cross_signal_is_captured_at_safe_point_then_rolls_back_once(
    activation_env: dict[str, object],
) -> None:
    """兩種 signal 只更新 bounded state，下一個 safe point 才進 rollback。"""

    build = activation_env["build"]
    receipt = activation_env["receipt"]
    assert callable(build)
    assert isinstance(receipt, Path)
    before = _target_bytes(activation_env)
    transaction: activation.ActivationTransaction

    def hook(event: str, job: str | None) -> None:
        if job == "daily" and event == "after_bootout_mutation_before_probe":
            transaction._signal_abort(signal.SIGINT, None)
            transaction._signal_abort(signal.SIGTERM, None)

    transaction = build(hook=hook)
    assert transaction.run() == "ROLLED_BACK_NO_GO"

    durable = json.loads(receipt.read_text(encoding="utf-8"))
    assert durable["signal_state"] == {
        "count": 2,
        "first": signal.SIGINT,
        "last": signal.SIGTERM,
        "saturated": False,
    }
    assert "safe point" in (durable["failure"] or "")
    assert _target_bytes(activation_env) == before
    _assert_old_topology(activation_env)


def test_signal_between_arm_handler_installations_is_captured_without_raise(
    activation_env: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    build = activation_env["build"]
    receipt = activation_env["receipt"]
    runner = activation_env["runner"]
    assert callable(build)
    assert isinstance(receipt, Path)
    assert isinstance(runner, FakeCommandRunner)
    transaction = build()
    original_signal = activation.signal.signal
    injected = False

    def install_with_cross_signal(signum: int, handler: object) -> object:
        nonlocal injected
        previous = original_signal(signum, handler)
        if signum == signal.SIGINT and handler == transaction._signal_abort and not injected:
            injected = True
            transaction._signal_abort(signal.SIGINT, None)
        return previous

    monkeypatch.setattr(activation.signal, "signal", install_with_cross_signal)
    assert transaction.run() == "ROLLED_BACK_NO_GO"

    durable = json.loads(receipt.read_text(encoding="utf-8"))
    assert injected
    assert durable["signal_state"]["first"] == signal.SIGINT
    assert not any(operation == "bootout" for operation, _ in runner.calls)


@pytest.mark.parametrize(
    "mutation_event",
    [
        "after_denial_mirror_write_before_verify",
        "after_denial_clear",
        "after_bootout_mutation_before_probe",
        "after_plist_replace_mutation_before_verify",
        "after_bootstrap_mutation_before_probe",
    ],
)
def test_signal_after_each_mutation_rolls_back_at_next_safe_point(
    activation_env: dict[str, object], mutation_event: str
) -> None:
    build = activation_env["build"]
    assert callable(build)
    before = _target_bytes(activation_env)
    transaction: activation.ActivationTransaction

    def hook(event: str, job: str | None) -> None:
        if job == "daily" and event == mutation_event:
            transaction._signal_abort(signal.SIGINT, None)

    transaction = build(hook=hook)
    assert transaction.run() == "ROLLED_BACK_NO_GO"

    assert _target_bytes(activation_env) == before
    _assert_old_topology(activation_env)


def test_signal_storm_is_bounded_and_rollback_resources_are_released(
    activation_env: dict[str, object],
) -> None:
    build = activation_env["build"]
    runtime_root = activation_env["runtime_root"]
    launch_agents = activation_env["launch_agents"]
    receipt = activation_env["receipt"]
    assert callable(build)
    assert isinstance(runtime_root, Path)
    assert isinstance(launch_agents, Path)
    assert isinstance(receipt, Path)
    transaction: activation.ActivationTransaction

    def hook(event: str, job: str | None) -> None:
        if job == "daily" and event == "after_bootout_mutation_before_probe":
            for signum in (signal.SIGINT, signal.SIGTERM) * 5:
                transaction._signal_abort(signum, None)

    transaction = build(hook=hook)
    assert transaction.run() == "ROLLED_BACK_NO_GO"

    durable = json.loads(receipt.read_text(encoding="utf-8"))
    assert durable["signal_state"] == {
        "count": 2,
        "first": signal.SIGINT,
        "last": signal.SIGTERM,
        "saturated": True,
    }
    assert not list(launch_agents.glob(".*.a4-stage-*.plist"))
    for guard_name, _, _ in activation.TARGET_JOBS:
        lock_path = runtime_root / "logs" / "storage_safety" / f"{guard_name}.lock"
        with lock_path.open("a+") as handle:
            activation.fcntl.flock(handle.fileno(), activation.fcntl.LOCK_EX | activation.fcntl.LOCK_NB)
            activation.fcntl.flock(handle.fileno(), activation.fcntl.LOCK_UN)


def test_terminal_receipt_write_failure_rolls_back_and_releases_locks(
    activation_env: dict[str, object],
) -> None:
    build = activation_env["build"]
    runtime_root = activation_env["runtime_root"]
    receipt = activation_env["receipt"]
    assert callable(build)
    assert isinstance(runtime_root, Path)
    assert isinstance(receipt, Path)
    before = _target_bytes(activation_env)

    transaction = build()
    attempts = 0

    def fail_terminal_receipt(staged: Path) -> None:
        nonlocal attempts
        del staged
        attempts += 1
        raise OSError("injected terminal receipt failure")

    transaction._commit_receipt = fail_terminal_receipt  # type: ignore[method-assign]
    assert transaction.run() == "ROLLED_BACK_NO_GO"

    assert attempts == 1
    assert not receipt.exists()
    assert _target_bytes(activation_env) == before
    _assert_old_topology(activation_env)
    for guard_name, _, _ in activation.TARGET_JOBS:
        lock_path = runtime_root / "logs" / "storage_safety" / f"{guard_name}.lock"
        with lock_path.open("a+") as handle:
            activation.fcntl.flock(handle.fileno(), activation.fcntl.LOCK_EX | activation.fcntl.LOCK_NB)
            activation.fcntl.flock(handle.fileno(), activation.fcntl.LOCK_UN)


def test_parent_directory_fsync_failure_is_post_rename_durability_no_go(
    activation_env: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pending signal 只能在 durability NO-GO 裁決與 outer cleanup 後交付。"""

    build = activation_env["build"]
    receipt = activation_env["receipt"]
    runtime_root = activation_env["runtime_root"]
    assert callable(build)
    assert isinstance(receipt, Path)
    assert isinstance(runtime_root, Path)
    transaction = build()
    original_fsync = activation.os.fsync
    previous_handler = signal.getsignal(signal.SIGTERM)
    delivered: list[tuple[str, bool, bool]] = []
    injected = False

    class InjectedOriginalSignal(Exception):
        """證明 original raising handler 不得搶先 outer teardown。"""

    def original_handler(signum: int, frame: object) -> None:
        del signum, frame
        delivered.append(
            (
                transaction.status,
                bool(transaction._denial_lock_handles),
                all(not path.exists() for path in transaction.staging_paths),
            )
        )
        raise InjectedOriginalSignal("injected original handler")

    def fail_directory_fsync(fd: int) -> None:
        nonlocal injected
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            raw = activation.fcntl.fcntl(fd, 50, b"\0" * 1024)
            path = Path(os.fsdecode(raw.split(b"\0", 1)[0])).resolve()
            if path == receipt.parent and not injected:
                injected = True
                assert receipt.exists()
                os.kill(os.getpid(), signal.SIGTERM)
                raise OSError("injected parent directory fsync failure")
        original_fsync(fd)

    monkeypatch.setattr(activation.os, "fsync", fail_directory_fsync)
    signal.signal(signal.SIGTERM, original_handler)
    try:
        assert transaction.run() == "ACTIVATED_RECEIPT_DURABILITY_UNCONFIRMED_NO_GO"
    finally:
        signal.signal(signal.SIGTERM, previous_handler)

    durable = json.loads(receipt.read_text(encoding="utf-8"))
    assert injected
    assert delivered == []
    assert transaction._signal_state_snapshot()["first"] == signal.SIGTERM
    assert durable["status"] == "ACTIVATED_PARTIAL_ACCEPTANCE_PENDING"
    runner = activation_env["runner"]
    assert isinstance(runner, FakeCommandRunner)
    assert all(state["root"] == runtime_root.resolve() for state in runner.states.values())
    assert not any(event["name"] == "rollback_started" for event in transaction.events)
    for guard_name, _, _ in activation.TARGET_JOBS:
        lock_path = runtime_root / "logs" / "storage_safety" / f"{guard_name}.lock"
        with lock_path.open("a+") as handle:
            activation.fcntl.flock(handle.fileno(), activation.fcntl.LOCK_EX | activation.fcntl.LOCK_NB)
            activation.fcntl.flock(handle.fileno(), activation.fcntl.LOCK_UN)


def test_parent_directory_fsync_failure_drains_default_sigterm_after_cleanup(
    activation_env: dict[str, object],
) -> None:
    """子行程的 default SIGTERM 不得搶先 durability NO-GO teardown。"""

    build = activation_env["build"]
    receipt = activation_env["receipt"]
    runtime_root = activation_env["runtime_root"]
    assert callable(build)
    assert isinstance(receipt, Path)
    assert isinstance(runtime_root, Path)
    context = multiprocessing.get_context("fork")
    receiver, sender = context.Pipe(duplex=False)

    def run_with_default_sigterm() -> None:
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        transaction = build()
        original_fsync = activation.os.fsync
        injected = False

        def fail_directory_fsync(fd: int) -> None:
            nonlocal injected
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                raw = activation.fcntl.fcntl(fd, 50, b"\0" * 1024)
                path = Path(os.fsdecode(raw.split(b"\0", 1)[0])).resolve()
                if path == receipt.parent and not injected:
                    injected = True
                    assert receipt.exists()
                    os.kill(os.getpid(), signal.SIGTERM)
                    raise OSError("injected parent directory fsync failure")
            original_fsync(fd)

        activation.os.fsync = fail_directory_fsync
        result = transaction.run()
        sender.send(
            (
                result,
                injected,
                transaction._signal_state_snapshot()["first"],
                bool(transaction._denial_lock_handles),
                all(not path.exists() for path in transaction.staging_paths),
            )
        )
        sender.close()

    process = context.Process(target=run_with_default_sigterm)
    process.start()
    sender.close()
    process.join(timeout=10)
    if process.is_alive():
        process.terminate()
        process.join(timeout=5)
        pytest.fail("default SIGTERM subprocess timed out")

    assert process.exitcode == 0
    assert receiver.poll()
    assert receiver.recv() == (
        "ACTIVATED_RECEIPT_DURABILITY_UNCONFIRMED_NO_GO",
        True,
        signal.SIGTERM,
        False,
        True,
    )
    receiver.close()
    for guard_name, _, _ in activation.TARGET_JOBS:
        lock_path = runtime_root / "logs" / "storage_safety" / f"{guard_name}.lock"
        with lock_path.open("a+") as handle:
            activation.fcntl.flock(handle.fileno(), activation.fcntl.LOCK_EX | activation.fcntl.LOCK_NB)
            activation.fcntl.flock(handle.fileno(), activation.fcntl.LOCK_UN)


def test_authoritative_receipt_rename_failure_rolls_back_without_receipt(
    activation_env: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    build = activation_env["build"]
    receipt = activation_env["receipt"]
    assert callable(build)
    assert isinstance(receipt, Path)
    before = _target_bytes(activation_env)
    original_replace = activation.os.replace
    injected = False

    def fail_receipt_rename(source: Path, destination: Path) -> None:
        nonlocal injected
        if Path(destination) == receipt:
            injected = True
            raise OSError("injected authoritative receipt rename failure")
        original_replace(source, destination)

    monkeypatch.setattr(activation.os, "replace", fail_receipt_rename)
    transaction = build()
    assert transaction.run() == "ROLLED_BACK_NO_GO"

    assert injected
    assert not receipt.exists()
    assert _target_bytes(activation_env) == before
    _assert_old_topology(activation_env)


def test_second_signal_during_rollback_does_not_interrupt_exact_restore(
    activation_env: dict[str, object],
) -> None:
    """rollback 已開始後的第二次 signal 不得中斷已武裝的 restore。"""

    build = activation_env["build"]
    assert callable(build)
    before = _target_bytes(activation_env)

    def hook(event: str, job: str | None) -> None:
        if job == "daily" and event == "after_bootout_mutation_before_probe":
            raise activation.ActivationError("injected first signal after bootout")

    transaction = build(hook=hook)
    original_run = transaction._run

    def run_with_second_signal(command: list[str]) -> activation.CommandResult:
        result = original_run(command)
        if command[1] == "bootstrap" and command[3].endswith("com.new-top10.daily.plist"):
            transaction._signal_abort(signal.SIGTERM, None)
        return result

    transaction._run = run_with_second_signal  # type: ignore[method-assign]
    assert transaction.run() == "ROLLED_BACK_NO_GO"

    assert _target_bytes(activation_env) == before
    _assert_old_topology(activation_env)


def test_second_signal_matrix_does_not_interrupt_rollback_side_effects(
    activation_env: dict[str, object],
) -> None:
    """plist restore、bootout/bootstrap、cleanup、verification 均不受後續 signal 中斷。"""

    build = activation_env["build"]
    launch_agents = activation_env["launch_agents"]
    assert callable(build)
    assert isinstance(launch_agents, Path)
    before = _target_bytes(activation_env)
    transaction: activation.ActivationTransaction

    def hook(event: str, job: str | None) -> None:
        if job == "external-review-preflight" and event == "after_bootstrap_mutation_before_probe":
            raise activation.ActivationError("injected rollback matrix trigger")
        if event == "before_rollback_verification":
            os.kill(os.getpid(), signal.SIGTERM)

    transaction = build(hook=hook)
    original_run = transaction._run
    original_atomic_write = transaction._atomic_write
    original_cleanup = transaction._cleanup_staging

    def run_with_signals(command: list[str]) -> activation.CommandResult:
        if transaction.status == "ROLLING_BACK" and command[1] in {"bootout", "bootstrap"}:
            os.kill(os.getpid(), signal.SIGINT)
        result = original_run(command)
        if transaction.status == "ROLLING_BACK" and command[1] in {"bootout", "bootstrap"}:
            os.kill(os.getpid(), signal.SIGTERM)
        return result

    def atomic_write_with_signals(path: Path, data: bytes) -> None:
        if transaction.status == "ROLLING_BACK" and path.parent == launch_agents:
            os.kill(os.getpid(), signal.SIGINT)
        original_atomic_write(path, data)
        if transaction.status == "ROLLING_BACK" and path.parent == launch_agents:
            os.kill(os.getpid(), signal.SIGTERM)

    def cleanup_with_signals(*, record_errors: bool = False) -> None:
        if transaction.status == "ROLLING_BACK":
            os.kill(os.getpid(), signal.SIGINT)
        original_cleanup(record_errors=record_errors)
        if transaction.status == "ROLLING_BACK":
            os.kill(os.getpid(), signal.SIGTERM)

    transaction._run = run_with_signals  # type: ignore[method-assign]
    transaction._atomic_write = atomic_write_with_signals  # type: ignore[method-assign]
    transaction._cleanup_staging = cleanup_with_signals  # type: ignore[method-assign]
    assert transaction.run() == "ROLLED_BACK_NO_GO"

    assert _target_bytes(activation_env) == before
    assert not list(launch_agents.glob(".*.a4-stage-*.plist"))
    _assert_old_topology(activation_env)


def test_second_signal_does_not_interrupt_transaction_marker_restore(
    activation_env: dict[str, object],
) -> None:
    build = activation_env["build"]
    runtime_root = activation_env["runtime_root"]
    assert callable(build)
    assert isinstance(runtime_root, Path)
    transaction: activation.ActivationTransaction

    def hook(event: str, job: str | None) -> None:
        if job == "daily" and event == "after_denial_mirror_write_before_verify":
            raise activation.ActivationError("injected marker rollback trigger")

    transaction = build(hook=hook)
    original_identity = transaction._path_identity
    marker = runtime_root / "logs" / "storage_safety" / "restart_denied" / "daily.json"

    def identity_with_signal(path: Path) -> tuple[int, int] | None:
        if transaction._rollback_in_progress and path == marker:
            os.kill(os.getpid(), signal.SIGTERM)
        return original_identity(path)

    transaction._path_identity = identity_with_signal  # type: ignore[method-assign]
    assert transaction.run() == "ROLLED_BACK_NO_GO"

    assert not marker.exists()
    _assert_old_topology(activation_env)


def test_signal_pending_at_arm_mask_restore_aborts_before_first_mutation(
    activation_env: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    """arm 完成 state 後才 restore mask；pending signal 由下一個 safe point 處理。"""

    build = activation_env["build"]
    receipt = activation_env["receipt"]
    runner = activation_env["runner"]
    assert callable(build)
    assert isinstance(receipt, Path)
    assert isinstance(runner, FakeCommandRunner)
    before = _target_bytes(activation_env)
    original_sigint_handler = signal.getsignal(signal.SIGINT)
    original_sigterm_handler = signal.getsignal(signal.SIGTERM)
    original_pthread_sigmask = activation.signal.pthread_sigmask
    injected = False
    restore_calls = 0
    transaction = build()

    def restore_mask_with_pending_signal(how: int, mask: set[signal.Signals]) -> set[signal.Signals]:
        nonlocal injected, restore_calls
        previous = original_pthread_sigmask(how, mask)
        if how == signal.SIG_SETMASK:
            restore_calls += 1
            if not injected:
                injected = True
                transaction._signal_abort(signal.SIGTERM, None)
            elif restore_calls == 2:
                assert signal.getsignal(signal.SIGTERM) == original_sigterm_handler
        return previous

    monkeypatch.setattr(activation.signal, "pthread_sigmask", restore_mask_with_pending_signal)
    assert transaction.run() == "ROLLED_BACK_NO_GO"

    durable = json.loads(receipt.read_text(encoding="utf-8"))
    assert injected
    # receipt 不再 unmask；只有 arm restore 與 outer disarm restore。
    assert restore_calls == 2
    assert durable["signal_state"]["first"] == signal.SIGTERM
    assert _target_bytes(activation_env) == before
    _assert_old_topology(activation_env)
    assert not any(operation == "bootout" for operation, _ in runner.calls)
    assert signal.getsignal(signal.SIGINT) == original_sigint_handler


def test_signal_during_final_receipt_write_is_excluded_after_seal_cutoff(
    activation_env: dict[str, object],
) -> None:
    """seal 後 signal 不得觸發 receipt rewrite 或被誤稱為已收錄。"""

    build = activation_env["build"]
    receipt = activation_env["receipt"]
    assert callable(build)
    assert isinstance(receipt, Path)

    def hook(event: str, job: str | None) -> None:
        if job == "daily" and event == "after_bootout_mutation_before_probe":
            raise activation.ActivationError("injected first signal after bootout")

    transaction = build(hook=hook)
    original_commit_receipt = transaction._commit_receipt
    injected = False

    def commit_with_signal(staged: Path) -> None:
        nonlocal injected
        if transaction.status == "ROLLED_BACK_NO_GO" and not injected:
            injected = True
            transaction._signal_abort(signal.SIGTERM, None)
        original_commit_receipt(staged)

    transaction._commit_receipt = commit_with_signal  # type: ignore[method-assign]
    assert transaction.run() == "ROLLED_BACK_NO_GO"
    assert injected

    durable = json.loads(receipt.read_text(encoding="utf-8"))
    assert durable["signal_state"] == {
        "count": 0,
        "first": None,
        "last": None,
        "saturated": False,
    }
    assert transaction._signal_state_snapshot()["first"] == signal.SIGTERM
    assert "excluded from the sealed receipt" in durable["receipt_seal"]["post_seal_signal_policy"]


@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM])
def test_release_to_commit_window_keeps_signal_blocked_until_durable_receipt(
    activation_env: dict[str, object], signum: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """真 pending signal 只能在 durable receipt 與 outer cleanup 後交付。"""

    build = activation_env["build"]
    runtime_root = activation_env["runtime_root"]
    receipt = activation_env["receipt"]
    assert callable(build)
    assert isinstance(runtime_root, Path)
    assert isinstance(receipt, Path)
    delivered: list[tuple[int, bool, bool, bool, bool]] = []
    commit_masks: list[set[signal.Signals]] = []
    parent_fsync_completed = False
    previous_handler = signal.getsignal(signum)
    original_fsync = activation.os.fsync

    def track_parent_fsync(fd: int) -> None:
        nonlocal parent_fsync_completed
        original_fsync(fd)
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            parent_fsync_completed = True

    def original_handler(received: int, frame: object) -> None:
        del frame
        delivered.append(
            (
                received,
                receipt.exists(),
                parent_fsync_completed,
                bool(transaction._denial_lock_handles),
                all(not path.exists() for path in transaction.staging_paths),
            )
        )

    monkeypatch.setattr(activation.os, "fsync", track_parent_fsync)
    signal.signal(signum, original_handler)
    try:
        transaction = build()
        original_commit = transaction._commit_receipt

        def queue_during_release_to_commit(staged: Path) -> None:
            commit_masks.append(signal.pthread_sigmask(signal.SIG_BLOCK, set()))
            assert signal.getsignal(signum) == original_handler
            os.kill(os.getpid(), signum)
            original_commit(staged)

        transaction._commit_receipt = queue_during_release_to_commit  # type: ignore[method-assign]
        assert transaction.run() == "ACTIVATED_PARTIAL_ACCEPTANCE_PENDING"
    finally:
        signal.signal(signum, previous_handler)

    durable = json.loads(receipt.read_text(encoding="utf-8"))
    assert commit_masks and signum in commit_masks[0]
    assert delivered == [(signum, True, True, False, True)]
    assert durable["signal_state"]["count"] == 0
    runner = activation_env["runner"]
    assert isinstance(runner, FakeCommandRunner)
    assert all(
        state["loaded"] and state["root"] == runtime_root.resolve()
        for state in runner.states.values()
    )


def test_precommit_handoff_retries_before_unmasking_pending_success_signal(
    activation_env: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Precommit handoff 暫時失敗時，固定 retry 後才可 seal success。"""

    build = activation_env["build"]
    receipt = activation_env["receipt"]
    assert callable(build)
    assert isinstance(receipt, Path)
    previous_handler = signal.getsignal(signal.SIGTERM)
    original_signal = activation.signal.signal
    delivered: list[tuple[int, str, bool, bool]] = []
    restore_attempts = 0

    def original_handler(signum: int, frame: object) -> None:
        del frame
        delivered.append(
            (
                signum,
                transaction.status,
                receipt.exists(),
                bool(transaction._denial_lock_handles),
            )
        )

    original_signal(signal.SIGTERM, original_handler)
    transaction = build()
    original_commit_receipt = transaction._commit_receipt

    def fail_first_precommit_handler_restore(signum: int, handler: object) -> object:
        nonlocal restore_attempts
        if (
            signum == signal.SIGTERM
            and handler == original_handler
            and transaction._receipt_seal_cutoff is not None
            and not transaction._receipt_sealed
        ):
            restore_attempts += 1
            if restore_attempts == 1:
                raise OSError("injected pre-syscall precommit handler restore failure")
        return original_signal(signum, handler)

    def queue_pending_at_commit(staged_receipt: Path) -> None:
        os.kill(os.getpid(), signal.SIGTERM)
        original_commit_receipt(staged_receipt)

    monkeypatch.setattr(activation.signal, "signal", fail_first_precommit_handler_restore)
    monkeypatch.setattr(transaction, "_commit_receipt", queue_pending_at_commit)
    try:
        assert transaction.run() == "ACTIVATED_PARTIAL_ACCEPTANCE_PENDING"
        assert restore_attempts == 2
        assert delivered == [
            (
                signal.SIGTERM,
                "ACTIVATED_PARTIAL_ACCEPTANCE_PENDING",
                True,
                False,
            )
        ]
        assert signal.getsignal(signal.SIGTERM) == original_handler
    finally:
        original_signal(signal.SIGTERM, previous_handler)


def test_persistent_precommit_handler_handoff_failure_rolls_back_without_success_receipt(
    activation_env: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Success seal 前 handoff 持續失敗時必須 rollback 並保留 blocked obligation。"""

    build = activation_env["build"]
    receipt = activation_env["receipt"]
    runtime_root = activation_env["runtime_root"]
    assert callable(build)
    assert isinstance(receipt, Path)
    assert isinstance(runtime_root, Path)
    before = _target_bytes(activation_env)
    original_signal = activation.signal.signal
    original_pthread_sigmask = activation.signal.pthread_sigmask
    previous_handler = signal.getsignal(signal.SIGTERM)
    initial_mask = original_pthread_sigmask(signal.SIG_BLOCK, set())
    restore_attempts = 0
    commit_statuses: list[str] = []

    def original_handler(signum: int, frame: object) -> None:
        del signum, frame

    original_signal(signal.SIGTERM, original_handler)
    transaction = build()
    original_commit_receipt = transaction._commit_receipt

    def fail_persistent_handler_restore(signum: int, handler: object) -> object:
        nonlocal restore_attempts
        if signum == signal.SIGTERM and handler == original_handler:
            restore_attempts += 1
            raise OSError("injected persistent precommit handler restore failure")
        return original_signal(signum, handler)

    def record_commit_status(staged_receipt: Path) -> None:
        commit_statuses.append(transaction.status)
        original_commit_receipt(staged_receipt)

    monkeypatch.setattr(activation.signal, "signal", fail_persistent_handler_restore)
    monkeypatch.setattr(transaction, "_commit_receipt", record_commit_status)
    try:
        assert transaction.run() == "ROLLED_BACK_NO_GO"
        durable = json.loads(receipt.read_text(encoding="utf-8"))
        final_mask = original_pthread_sigmask(signal.SIG_BLOCK, set())
        assert commit_statuses == ["ROLLED_BACK_NO_GO"]
        assert durable["status"] == "ROLLED_BACK_NO_GO"
        assert restore_attempts == 4
        assert signal.SIGTERM in transaction._old_signal_handlers
        assert signal.getsignal(signal.SIGTERM) == transaction._signal_abort
        assert {signal.SIGINT, signal.SIGTERM}.issubset(final_mask)
        assert transaction._old_signal_mask is not None
        assert not transaction._denial_lock_handles
        assert _target_bytes(activation_env) == before
        _assert_old_topology(activation_env)
        for guard_name, _, _ in activation.TARGET_JOBS:
            lock_path = runtime_root / "logs" / "storage_safety" / f"{guard_name}.lock"
            with lock_path.open("a+") as handle:
                activation.fcntl.flock(
                    handle.fileno(), activation.fcntl.LOCK_EX | activation.fcntl.LOCK_NB
                )
                activation.fcntl.flock(handle.fileno(), activation.fcntl.LOCK_UN)
    finally:
        original_signal(signal.SIGTERM, previous_handler)
        original_pthread_sigmask(signal.SIG_SETMASK, initial_mask)


@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM])
def test_signal_after_final_safe_point_before_seal_cutoff_rolls_back(
    activation_env: dict[str, object], signum: int
) -> None:
    """cutoff 前捕獲的 signal 不得留下 activation success。"""

    build = activation_env["build"]
    receipt = activation_env["receipt"]
    assert callable(build)
    assert isinstance(receipt, Path)
    before = _target_bytes(activation_env)

    transaction = build()
    original_write_receipt = transaction._write_receipt
    injected = False

    def capture_signal_before_cutoff() -> None:
        nonlocal injected
        if not injected:
            injected = True
            transaction._signal_abort(signum, None)
        original_write_receipt()

    transaction._write_receipt = capture_signal_before_cutoff  # type: ignore[method-assign]
    assert transaction.run() == "ROLLED_BACK_NO_GO"

    durable = json.loads(receipt.read_text(encoding="utf-8"))
    assert injected
    assert durable["status"] == "ROLLED_BACK_NO_GO"
    assert durable["signal_state"]["first"] == signum
    assert _target_bytes(activation_env) == before
    _assert_old_topology(activation_env)


@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM])
def test_pending_signal_at_seal_transition_rolls_back(
    activation_env: dict[str, object], signum: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """block 前已 pending 而尚未進 handler 的 signal 也必須阻止 success seal。"""

    build = activation_env["build"]
    receipt = activation_env["receipt"]
    assert callable(build)
    assert isinstance(receipt, Path)
    before = _target_bytes(activation_env)
    transaction = build()
    original_sigpending = activation.signal.sigpending

    def pending_at_success_seal() -> set[signal.Signals]:
        if transaction.status == "ACTIVATED_PARTIAL_ACCEPTANCE_PENDING":
            return {signum}
        return original_sigpending()

    monkeypatch.setattr(activation.signal, "sigpending", pending_at_success_seal)
    assert transaction.run() == "ROLLED_BACK_NO_GO"

    durable = json.loads(receipt.read_text(encoding="utf-8"))
    assert durable["status"] == "ROLLED_BACK_NO_GO"
    assert durable["signal_state"]["first"] == signum
    assert _target_bytes(activation_env) == before
    _assert_old_topology(activation_env)


def test_partial_arm_handoffs_unresolved_handler_before_receipt_unmask(
    activation_env: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Partial arm 的 pending signal 只能在 durable receipt 後交回原 handler。"""

    build = activation_env["build"]
    receipt = activation_env["receipt"]
    assert callable(build)
    assert isinstance(receipt, Path)
    transaction = build()
    original_signal = activation.signal.signal
    previous_sigint_handler = signal.getsignal(signal.SIGINT)
    original_commit_receipt = transaction._commit_receipt
    delivered: list[tuple[int, bool]] = []
    commit_masks: list[set[signal.Signals]] = []
    commit_handlers: list[object] = []
    install_failed = False
    first_restore_failed = False
    restore_attempts = 0

    def original_sigint_handler(signum: int, frame: object) -> None:
        del frame
        delivered.append((signum, receipt.exists()))

    def fail_install_then_first_restore(signum: int, handler: object) -> object:
        nonlocal install_failed, first_restore_failed, restore_attempts
        if signum == signal.SIGTERM and handler == transaction._signal_abort:
            install_failed = True
            raise RuntimeError("injected handler install failure")
        if signum == signal.SIGINT and handler == original_sigint_handler and install_failed:
            restore_attempts += 1
            if not first_restore_failed:
                first_restore_failed = True
                raise OSError("injected pre-syscall handler restore failure")
        return original_signal(signum, handler)

    def queue_pending_at_receipt_commit(staged_receipt: Path) -> None:
        commit_masks.append(signal.pthread_sigmask(signal.SIG_BLOCK, set()))
        commit_handlers.append(signal.getsignal(signal.SIGINT))
        os.kill(os.getpid(), signal.SIGINT)
        original_commit_receipt(staged_receipt)

    original_signal(signal.SIGINT, original_sigint_handler)
    monkeypatch.setattr(activation.signal, "signal", fail_install_then_first_restore)
    monkeypatch.setattr(transaction, "_commit_receipt", queue_pending_at_receipt_commit)
    try:
        assert transaction.run() == "PRECHECK_FAILED"
        assert install_failed and first_restore_failed
        assert restore_attempts == 2
        assert len(commit_masks) == 1
        assert signal.SIGINT in commit_masks[0]
        assert commit_handlers == [transaction._signal_abort]
        assert delivered == [(signal.SIGINT, True)]
        assert signal.getsignal(signal.SIGINT) == original_sigint_handler
    finally:
        original_signal(signal.SIGINT, previous_sigint_handler)

    durable = json.loads(receipt.read_text(encoding="utf-8"))
    assert durable["status"] == "PRECHECK_FAILED"
    assert durable["signal_state"]["count"] == 0
    assert (transaction.failure or "").startswith("RuntimeError: injected handler install failure")


def test_disarm_mask_restore_error_preserves_transaction_failure(
    activation_env: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    """_disarm 的 mask restore error 不得覆蓋既有 rollback failure result。"""

    build = activation_env["build"]
    assert callable(build)
    before = _target_bytes(activation_env)

    def hook(event: str, job: str | None) -> None:
        if job == "daily" and event == "after_bootout_mutation_before_probe":
            raise activation.ActivationError("injected primary transaction failure")

    transaction = build(hook=hook)
    original_pthread_sigmask = activation.signal.pthread_sigmask
    restore_calls = 0

    def fail_disarm_mask_restore(how: int, mask: set[signal.Signals]) -> set[signal.Signals]:
        nonlocal restore_calls
        previous = original_pthread_sigmask(how, mask)
        if how == signal.SIG_SETMASK:
            restore_calls += 1
            if restore_calls == 2:
                raise OSError("injected disarm mask restore failure")
        return previous

    monkeypatch.setattr(activation.signal, "pthread_sigmask", fail_disarm_mask_restore)
    assert transaction.run() == "ROLLED_BACK_NO_GO"

    assert restore_calls == 3
    assert (transaction.failure or "").startswith(
        "ActivationError: injected primary transaction failure"
    )
    assert _target_bytes(activation_env) == before
    _assert_old_topology(activation_env)


def test_post_commit_mask_restore_failure_keeps_success_topology_and_retries(
    activation_env: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    """durable commit 後 restore 失敗不得 rollback，finally 必須 bounded retry。"""

    build = activation_env["build"]
    receipt = activation_env["receipt"]
    assert callable(build)
    assert isinstance(receipt, Path)
    transaction = build()
    original_pthread_sigmask = activation.signal.pthread_sigmask
    injected = False

    def fail_once_after_cutoff(how: int, mask: set[signal.Signals]) -> set[signal.Signals]:
        nonlocal injected
        if (
            how == signal.SIG_SETMASK
            and transaction._receipt_seal_cutoff is not None
            and not injected
        ):
            injected = True
            raise OSError("injected receipt mask restore failure")
        return original_pthread_sigmask(how, mask)

    monkeypatch.setattr(activation.signal, "pthread_sigmask", fail_once_after_cutoff)
    assert transaction.run() == "ACTIVATED_PARTIAL_ACCEPTANCE_PENDING"

    durable = json.loads(receipt.read_text(encoding="utf-8"))
    assert injected
    assert durable["status"] == "ACTIVATED_PARTIAL_ACCEPTANCE_PENDING"
    runtime_root = activation_env["runtime_root"]
    runner = activation_env["runner"]
    assert isinstance(runtime_root, Path)
    assert isinstance(runner, FakeCommandRunner)
    assert all(state["root"] == runtime_root.resolve() for state in runner.states.values())


def test_original_signal_mask_is_restored_after_pre_syscall_release_failure(
    activation_env: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    """teardown 必須使用 arm-time mask，不可把 failure 後的 blocked mask 當原狀。"""

    build = activation_env["build"]
    assert callable(build)
    transaction = build()
    original_pthread_sigmask = activation.signal.pthread_sigmask
    initial_mask = original_pthread_sigmask(signal.SIG_BLOCK, set())
    expected_mask = initial_mask - {signal.SIGINT, signal.SIGTERM}
    original_pthread_sigmask(signal.SIG_SETMASK, expected_mask)
    injected = False

    def fail_before_release_syscall(
        how: int, mask: set[signal.Signals]
    ) -> set[signal.Signals]:
        nonlocal injected
        if (
            how == signal.SIG_SETMASK
            and transaction._receipt_seal_cutoff is not None
            and not injected
        ):
            injected = True
            raise OSError("injected pre-syscall mask restore failure")
        return original_pthread_sigmask(how, mask)

    monkeypatch.setattr(activation.signal, "pthread_sigmask", fail_before_release_syscall)
    try:
        assert transaction.run() == "ACTIVATED_PARTIAL_ACCEPTANCE_PENDING"
        final_mask = original_pthread_sigmask(signal.SIG_BLOCK, set())
        assert injected
        assert final_mask == expected_mask
        runtime_root = activation_env["runtime_root"]
        runner = activation_env["runner"]
        assert isinstance(runtime_root, Path)
        assert isinstance(runner, FakeCommandRunner)
        assert all(state["root"] == runtime_root.resolve() for state in runner.states.values())
    finally:
        original_pthread_sigmask(signal.SIG_SETMASK, initial_mask)


def test_denial_root_switch_is_explicitly_mirrored_then_cleared_before_bootout(
    activation_env: dict[str, object],
) -> None:
    build = activation_env["build"]
    old_root = activation_env["old_root"]
    runtime_root = activation_env["runtime_root"]
    assert callable(build)
    assert isinstance(old_root, Path)
    assert isinstance(runtime_root, Path)
    old_hashes = {
        job: activation.sha256_file(
            old_root / "logs" / "storage_safety" / "restart_denied" / f"{job}.json"
        )
        for job in ("daily", "fog-research-worker")
    }

    transaction = build()
    assert transaction.run() == "ACTIVATED_PARTIAL_ACCEPTANCE_PENDING"

    names = [(event["name"], event.get("job")) for event in transaction.events]
    first_bootout = names.index(("bootout_complete", "daily"))
    for job in ("daily", "fog-research-worker"):
        assert names.index(("denial_mirrored", job)) < first_bootout
        assert names.index(("denial_explicitly_cleared_for_activation", job)) < first_bootout
        old_marker = old_root / "logs" / "storage_safety" / "restart_denied" / f"{job}.json"
        new_marker = runtime_root / "logs" / "storage_safety" / "restart_denied" / f"{job}.json"
        assert activation.sha256_file(old_marker) == old_hashes[job]
        assert not new_marker.exists()


def test_new_denial_after_preflight_before_mirror_is_preserved_and_blocks_activation(
    activation_env: dict[str, object],
) -> None:
    build = activation_env["build"]
    runtime_root = activation_env["runtime_root"]
    assert callable(build)
    assert isinstance(runtime_root, Path)
    new_marker = (
        runtime_root
        / "logs"
        / "storage_safety"
        / "restart_denied"
        / "daily.json"
    )
    payload = {"reason": "NEW_DENIAL_AFTER_PREFLIGHT"}

    def hook(event: str, job: str | None) -> None:
        if job == "daily" and event == "before_denial_mirror":
            new_marker.parent.mkdir(parents=True, exist_ok=True)
            new_marker.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    transaction = build(hook=hook)
    assert transaction.run() == "ROLLED_BACK_NO_GO"

    assert new_marker.is_file()
    assert json.loads(new_marker.read_text(encoding="utf-8")) == payload
    _assert_old_topology(activation_env)


def test_same_hash_external_denial_before_mirror_completion_is_preserved_on_rollback(
    activation_env: dict[str, object],
) -> None:
    build = activation_env["build"]
    old_root = activation_env["old_root"]
    runtime_root = activation_env["runtime_root"]
    assert callable(build)
    assert isinstance(old_root, Path)
    assert isinstance(runtime_root, Path)
    old_marker = (
        old_root / "logs" / "storage_safety" / "restart_denied" / "daily.json"
    )
    old_bytes = old_marker.read_bytes()
    new_marker = (
        runtime_root
        / "logs"
        / "storage_safety"
        / "restart_denied"
        / "daily.json"
    )

    transaction = build()
    original_create = transaction._create_owned_denial_mirror

    def fail_before_ownership(
        job_state: activation.JobState, path: Path, data: bytes
    ) -> None:
        if path == new_marker:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            raise OSError("injected external same-hash denial before mirror completion")
        original_create(job_state, path, data)

    transaction._create_owned_denial_mirror = fail_before_ownership  # type: ignore[method-assign]
    assert transaction.run() == "ROLLED_BACK_NO_GO"

    assert new_marker.is_file()
    assert new_marker.read_bytes() == old_bytes
    assert transaction.new_denial_preserved[0]["job"] == "daily"
    _assert_old_topology(activation_env)


def test_same_hash_external_replacement_after_mirror_is_preserved_on_rollback(
    activation_env: dict[str, object],
) -> None:
    build = activation_env["build"]
    runtime_root = activation_env["runtime_root"]
    assert callable(build)
    assert isinstance(runtime_root, Path)
    new_marker = (
        runtime_root
        / "logs"
        / "storage_safety"
        / "restart_denied"
        / "daily.json"
    )
    replaced_identity: tuple[int, int] | None = None

    def hook(event: str, job: str | None) -> None:
        nonlocal replaced_identity
        if job == "daily" and event == "after_denial_mirror_write_before_verify":
            mirrored_bytes = new_marker.read_bytes()
            replacement = new_marker.with_name("daily.external.json")
            replacement.write_bytes(mirrored_bytes)
            os.replace(replacement, new_marker)
            stat_result = new_marker.stat()
            replaced_identity = (stat_result.st_dev, stat_result.st_ino)
            raise activation.ActivationError(
                "injected same-hash external replacement after mirror"
            )

    transaction = build(hook=hook)
    assert transaction.run() == "ROLLED_BACK_NO_GO"

    assert new_marker.is_file()
    current = new_marker.stat()
    assert replaced_identity == (current.st_dev, current.st_ino)
    assert transaction.new_denial_preserved[0]["job"] == "daily"
    _assert_old_topology(activation_env)


def test_runtime_storage_guard_lock_contention_blocks_activation_before_bootout(
    activation_env: dict[str, object],
) -> None:
    build = activation_env["build"]
    runtime_root = activation_env["runtime_root"]
    runner = activation_env["runner"]
    assert callable(build)
    assert isinstance(runtime_root, Path)
    assert isinstance(runner, FakeCommandRunner)
    lock_path = runtime_root / "logs" / "storage_safety" / "daily.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+")
    activation.fcntl.flock(handle.fileno(), activation.fcntl.LOCK_EX | activation.fcntl.LOCK_NB)
    try:
        transaction = build()
        assert transaction.run() == "ROLLED_BACK_NO_GO"
    finally:
        activation.fcntl.flock(handle.fileno(), activation.fcntl.LOCK_UN)
        handle.close()

    assert not any(operation == "bootout" for operation, _ in runner.calls)
    _assert_old_topology(activation_env)


def test_storage_guard_locks_remain_held_through_bootstrap_verification_and_commit(
    activation_env: dict[str, object],
) -> None:
    build = activation_env["build"]
    assert callable(build)

    transaction = build()
    assert transaction.run() == "ACTIVATED_PARTIAL_ACCEPTANCE_PENDING"

    event_names = [event["name"] for event in transaction.events]
    commit_index = event_names.index("transaction_committed")
    release_indexes = [
        index
        for index, name in enumerate(event_names)
        if name == "denial_writer_lock_released"
    ]
    assert len(release_indexes) == len(activation.TARGET_JOBS)
    assert all(index > commit_index for index in release_indexes)


def test_denial_mirror_interruption_after_write_before_verify_removes_transaction_marker(
    activation_env: dict[str, object],
) -> None:
    build = activation_env["build"]
    old_root = activation_env["old_root"]
    runtime_root = activation_env["runtime_root"]
    assert callable(build)
    assert isinstance(old_root, Path)
    assert isinstance(runtime_root, Path)
    old_marker = (
        old_root / "logs" / "storage_safety" / "restart_denied" / "daily.json"
    )
    old_hash = activation.sha256_file(old_marker)
    new_marker = (
        runtime_root / "logs" / "storage_safety" / "restart_denied" / "daily.json"
    )

    def hook(event: str, job: str | None) -> None:
        if job == "daily" and event == "after_denial_mirror_write_before_verify":
            raise activation.ActivationError(
                "injected signal after denial mirror write before verify"
            )

    transaction = build(hook=hook)
    assert transaction.run() == "ROLLED_BACK_NO_GO"

    assert activation.sha256_file(old_marker) == old_hash
    assert not new_marker.exists()
    _assert_old_topology(activation_env)


def test_new_denial_created_during_rollback_is_preserved(
    activation_env: dict[str, object],
) -> None:
    runner = activation_env["runner"]
    build = activation_env["build"]
    runtime_root = activation_env["runtime_root"]
    assert isinstance(runner, FakeCommandRunner)
    assert callable(build)
    assert isinstance(runtime_root, Path)
    runner.fail("bootout", "com.new-top10.daily", when="before")
    new_marker = (
        runtime_root
        / "logs"
        / "storage_safety"
        / "restart_denied"
        / "daily.json"
    )

    def hook(event: str, job: str | None) -> None:
        del job
        if event == "rollback_started":
            new_marker.parent.mkdir(parents=True, exist_ok=True)
            new_marker.write_text('{"reason":"NEW_DENIAL_DURING_ROLLBACK"}\n', encoding="utf-8")

    transaction = build(hook=hook)
    assert transaction.run() == "ROLLED_BACK_NO_GO"

    assert new_marker.is_file()
    assert json.loads(new_marker.read_text(encoding="utf-8"))["reason"] == "NEW_DENIAL_DURING_ROLLBACK"
    assert transaction.new_denial_preserved[0]["job"] == "daily"


def test_rollback_verification_mismatch_is_terminal_no_go(
    activation_env: dict[str, object],
) -> None:
    runner = activation_env["runner"]
    build = activation_env["build"]
    launch_agents = activation_env["launch_agents"]
    assert isinstance(runner, FakeCommandRunner)
    assert callable(build)
    assert isinstance(launch_agents, Path)
    runner.fail("bootout", "com.new-top10.daily", when="after")

    def hook(event: str, job: str | None) -> None:
        del job
        if event == "before_rollback_verification":
            target = launch_agents / "com.new-top10.daily.plist"
            target.write_bytes(target.read_bytes() + b"\n<!-- injected rollback drift -->\n")

    transaction = build(hook=hook)
    assert transaction.run() == "ROLLBACK_VERIFICATION_FAILED"
    assert "ROLLBACK_VERIFICATION_FAILED" in (transaction.failure or "")


def test_bounded_activation_never_changes_out_of_scope_plist(
    activation_env: dict[str, object],
) -> None:
    build = activation_env["build"]
    untouched = activation_env["untouched"]
    runner = activation_env["runner"]
    assert callable(build)
    assert isinstance(untouched, Path)
    assert isinstance(runner, FakeCommandRunner)
    before = untouched.read_bytes()

    transaction = build()
    assert transaction.run() == "ACTIVATED_PARTIAL_ACCEPTANCE_PENDING"

    assert untouched.read_bytes() == before
    touched_labels = {
        label
        for operation, label in runner.calls
        if operation in {"bootout", "bootstrap", "kickstart"}
    }
    assert touched_labels <= {label for _, label, _ in activation.TARGET_JOBS}
