"""A4 三條核心 launchd transaction 的 failure-state regression。"""

from __future__ import annotations

import json
import multiprocessing
import os
import plistlib
import shutil
import signal
import stat
import subprocess
import sys
from pathlib import Path
from typing import Callable

import pytest

from scripts import activate_automation_runtime as activation


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ACCEPTED_SHA = "a" * 40
FOG_ONLY = ("fog-research-worker",)
RETRAIN_ONLY = ("retrain-monitor",)
RETRAIN_LABEL = "com.new-top10.retrain"
LEGACY_DEFAULT_LABELS = {
    "com.new-top10.daily",
    "com.new-top10.external-review-preflight",
    "com.new-top10.fog-research-worker",
}
MACOS_PRINT_DISABLED_FIXTURE = """disabled services = {
    "com.new-top10.daily" => enabled
    "com.new-top10.external-review-preflight" => enabled
    "com.new-top10.fog-research-worker" => enabled
    "com.new-top10.retrain" => __RETRAIN_STATE__
}
"""


def _legacy_target_rows() -> tuple[tuple[str, str, str], ...]:
    return tuple(
        job
        for job in activation.TARGET_JOBS
        if job[0] in activation.LEGACY_DEFAULT_TARGET_JOBS
    )


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
            label: {
                "loaded": guard_name != "retrain-monitor",
                "running": False,
                "root": old_root.resolve(),
                "disabled": guard_name == "retrain-monitor",
            }
            for guard_name, label, _ in activation.TARGET_JOBS
        }
        self.calls: list[tuple[str, str | None]] = []
        self.failures: dict[tuple[str, str], str] = {}
        self.fail_plutil = False
        self.print_disabled_style = "macos"
        self.print_disabled_overrides: dict[str, str] = {}
        self.print_results: dict[str, list[activation.CommandResult | None]] = {}

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
            queued = self.print_results.get(label)
            if queued:
                override = queued.pop(0)
                if override is not None:
                    return override
            if not state["loaded"]:
                return activation.CommandResult(
                    113,
                    "",
                    f'Could not find service "{label}" in domain for user gui: 999',
                )
            run_state = "running" if state["running"] else "waiting"
            root = state["root"]
            output = (
                f"service = {{\n"
                f"    state = {run_state}\n"
                f"    arguments = {{ {root}/scripts/fake-entrypoint.sh }}\n"
                f"}}\n"
            )
            return activation.CommandResult(0, output, "")

        if operation == "print-disabled":
            self.calls.append(("print-disabled", None))
            if self.print_disabled_style == "macos":
                retrain_state = self.print_disabled_overrides.get(
                    RETRAIN_LABEL,
                    self._disabled_value(self.states[RETRAIN_LABEL]),
                )
                output = MACOS_PRINT_DISABLED_FIXTURE.replace(
                    "__RETRAIN_STATE__", retrain_state
                )
            else:
                entries = "\n".join(
                    f'    "{label}" => {self.print_disabled_overrides.get(label, self._disabled_value(state))}'
                    for label, state in self.states.items()
                )
                output = f"disabled services = {{\n{entries}\n}}\n"
            return activation.CommandResult(0, output, "")

        if operation in {"enable", "disable"}:
            label = command[2].rsplit("/", 1)[-1]
            self.calls.append((operation, label))
            failure = self._failure(operation, label)
            if failure == "before":
                del self.failures[(operation, label)]
                return activation.CommandResult(5, "", f"injected {operation}-before")
            self.states[label]["disabled"] = operation == "disable"
            if failure in {"after", "interrupt_after"}:
                del self.failures[(operation, label)]
                if failure == "interrupt_after":
                    raise activation.ActivationError(f"injected {operation} interruption")
                return activation.CommandResult(5, "", f"injected {operation}-after")
            return activation.CommandResult(0, "", "")

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
            if state["disabled"]:
                return activation.CommandResult(5, "", "service disabled")
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

    def _disabled_value(self, state: dict[str, object]) -> str:
        if self.print_disabled_style == "bool":
            return str(state["disabled"]).lower()
        return "disabled" if state["disabled"] else "enabled"


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
    universe_path = runtime_root / "data" / "reference" / "tradable_universe.csv"
    universe_path.parent.mkdir(parents=True)
    universe_path.write_text("stock_id,market_type\n2330,twse\n6488,tpex\n", encoding="utf-8")
    config_path = runtime_root / "config" / "automation.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        "daily:\n  market_coverage_enabled: true\n  required_market_types: [twse, tpex]\n",
        encoding="utf-8",
    )
    shutil.copy2(PROJECT_ROOT / "scripts" / "daily_market_reference.py", scripts_dir)

    for guard_name, label, template_name in activation.TARGET_JOBS:
        shutil.copy2(PROJECT_ROOT / "scripts" / template_name, scripts_dir / template_name)
        installed_bytes = _render_template(template_name, old_root)
        if guard_name == "retrain-monitor":
            installed_payload = plistlib.loads(installed_bytes)
            installed_payload["ProgramArguments"][2] = "retrain"
            installed_bytes = plistlib.dumps(installed_payload)
        (launch_agents / f"{label}.plist").write_bytes(installed_bytes)

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
        target_jobs: tuple[str, ...] | None = None,
        allow_dormant_target_activation: bool = False,
        allow_enabled_unloaded_target_activation: bool = False,
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
            target_jobs=target_jobs,
            allow_dormant_target_activation=allow_dormant_target_activation,
            allow_enabled_unloaded_target_activation=(
                allow_enabled_unloaded_target_activation
            ),
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


def _install_legacy_unguarded_retrain(env: dict[str, object]) -> None:
    launch_agents = env["launch_agents"]
    old_root = env["old_root"]
    assert isinstance(launch_agents, Path)
    assert isinstance(old_root, Path)
    installed = launch_agents / f"{RETRAIN_LABEL}.plist"
    payload = plistlib.loads(installed.read_bytes())
    payload["ProgramArguments"] = [
        "/bin/bash",
        str(old_root / "scripts" / "daily_retrain.sh"),
        "monitor",
        "--trigger",
        "scheduled",
    ]
    installed.write_bytes(plistlib.dumps(payload))


def _assert_old_topology(env: dict[str, object]) -> None:
    old_root = env["old_root"]
    runner = env["runner"]
    assert isinstance(old_root, Path)
    assert isinstance(runner, FakeCommandRunner)
    for _, label, _ in activation.TARGET_JOBS:
        expected_dormant = label == RETRAIN_LABEL
        assert runner.states[label] == {
            "loaded": not expected_dormant,
            "running": False,
            "root": old_root.resolve(),
            "disabled": expected_dormant,
        }


def _assert_fog_only_never_created_unselected_artifacts(
    env: dict[str, object],
) -> None:
    """未選 job 不得產生 runtime marker、lock 或 prestate snapshot。"""

    runtime_root = env["runtime_root"]
    receipt = env["receipt"]
    assert isinstance(runtime_root, Path)
    assert isinstance(receipt, Path)
    prestate_dir = receipt.parent / f"{receipt.stem}.prestate"
    for guard_name, label in (
        ("daily", "com.new-top10.daily"),
        ("external-review-preflight", "com.new-top10.external-review-preflight"),
    ):
        assert not (
            runtime_root
            / "logs"
            / "storage_safety"
            / "restart_denied"
            / f"{guard_name}.json"
        ).exists()
        assert not (
            runtime_root / "logs" / "storage_safety" / f"{guard_name}.lock"
        ).exists()
        assert not (prestate_dir / f"{label}.plist").exists()


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


@pytest.mark.parametrize("invalid", ["missing", "empty", "header_only", "missing_tpex", "blank_ids", "invalid_ids"])
def test_daily_activation_rejects_invalid_market_reference_before_mutation(
    activation_env: dict[str, object], invalid: str,
) -> None:
    """Daily 的忽略檔未備妥時，正式切換必須在任何 launchd 副作用前停止。"""
    build = activation_env["build"]
    runner = activation_env["runner"]
    runtime_root = activation_env["runtime_root"]
    assert callable(build)
    assert isinstance(runner, FakeCommandRunner)
    assert isinstance(runtime_root, Path)
    reference = runtime_root / "data" / "reference" / "tradable_universe.csv"
    if invalid == "missing":
        reference.unlink()
    elif invalid == "empty":
        reference.write_bytes(b"")
    elif invalid == "header_only":
        reference.write_text("stock_id,market_type\n", encoding="utf-8")
    elif invalid == "blank_ids":
        reference.write_text("stock_id,market_type\n ,twse\n ,tpex\n", encoding="utf-8")
    elif invalid == "invalid_ids":
        reference.write_text("stock_id,market_type\nx,twse\ny,tpex\n", encoding="utf-8")
    else:
        reference.write_text("stock_id,market_type\n2330,twse\n", encoding="utf-8")
    before = _target_bytes(activation_env)

    transaction = build(target_jobs=("daily",))
    assert transaction.run() == "PRECHECK_FAILED"
    assert "缺必要市場參考檔" in (transaction.failure or "")
    assert not any(
        operation in {"bootout", "bootstrap", "enable", "disable", "kickstart"}
        for operation, _ in runner.calls
    )
    assert _target_bytes(activation_env) == before
    _assert_old_topology(activation_env)


def test_daily_activation_respects_disabled_market_coverage(
    activation_env: dict[str, object],
) -> None:
    """市場覆蓋 gate 明確關閉時，activation 與 Daily 使用相同設定。"""
    build = activation_env["build"]
    runtime_root = activation_env["runtime_root"]
    assert callable(build)
    assert isinstance(runtime_root, Path)
    (runtime_root / "data" / "reference" / "tradable_universe.csv").unlink()
    (runtime_root / "config" / "automation.yaml").write_text(
        "daily:\n  market_coverage_enabled: false\n", encoding="utf-8"
    )
    assert build(target_jobs=("daily",)).run() == "ACTIVATED_PARTIAL_ACCEPTANCE_PENDING"


def test_daily_activation_requires_candidate_market_validator(
    activation_env: dict[str, object],
) -> None:
    """activation 必須使用 candidate 自己的市場驗證器，缺少時安全停止。"""
    build = activation_env["build"]
    runner = activation_env["runner"]
    runtime_root = activation_env["runtime_root"]
    assert callable(build)
    assert isinstance(runner, FakeCommandRunner)
    assert isinstance(runtime_root, Path)
    (runtime_root / "scripts" / "daily_market_reference.py").unlink()
    before = _target_bytes(activation_env)
    transaction = build(target_jobs=("daily",))
    assert transaction.run() == "PRECHECK_FAILED"
    assert "缺市場參考驗證器" in (transaction.failure or "")
    assert _target_bytes(activation_env) == before
    assert not any(
        operation in {"bootout", "bootstrap", "enable", "disable", "kickstart"}
        for operation, _ in runner.calls
    )


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
        for _, label, _ in _legacy_target_rows()
    ]
    for _, label, _ in _legacy_target_rows():
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
    assert all(
        runner.states[label]["root"] == runtime_root.resolve()
        for label in LEGACY_DEFAULT_LABELS
    )
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
        # 排除 prepare helper 的短 mask scope；只計 arm 完成後及注入後的 outer disarm。
        if how == signal.SIG_SETMASK and (injected or transaction.armed):
            restore_calls += 1
            if not injected:
                assert transaction.armed
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
    initial_pending = signal.sigpending()
    initial_mask = signal.pthread_sigmask(signal.SIG_BLOCK, set())
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
        status = transaction.run()
        assert status == "ACTIVATED_PARTIAL_ACCEPTANCE_PENDING", (
            f"initial_pending={initial_pending}; initial_mask={initial_mask}\n"
            f"failure={transaction.failure}\n"
            f"receipt={receipt.read_text(encoding='utf-8') if receipt.exists() else None}"
        )
    finally:
        signal.signal(signum, previous_handler)

    durable = json.loads(receipt.read_text(encoding="utf-8"))
    assert commit_masks and signum in commit_masks[0]
    assert delivered == [(signum, True, True, False, True)]
    assert durable["signal_state"]["count"] == 0
    runner = activation_env["runner"]
    assert isinstance(runner, FakeCommandRunner)
    assert all(
        runner.states[label]["loaded"]
        and runner.states[label]["root"] == runtime_root.resolve()
        for label in LEGACY_DEFAULT_LABELS
    )


@pytest.mark.parametrize("seal_fails", [False, True])
def test_prearm_failure_restores_signal_mask(activation_env, monkeypatch, seal_fails):
    """prepare 早退的失敗收據也須歸還 mask，不得污染下一筆 transaction。"""
    transaction = activation_env["build"]()
    initial = signal.pthread_sigmask(signal.SIG_BLOCK, set())

    def reject_prepare():
        raise activation.ActivationError("injected prearm failure")

    def reject_seal(_staged):
        raise OSError("injected failure receipt commit")

    monkeypatch.setattr(transaction, "_prepare", reject_prepare)
    if seal_fails:
        monkeypatch.setattr(transaction, "_commit_receipt", reject_seal)
    try:
        assert transaction.run() == "PRECHECK_FAILED"
        assert signal.pthread_sigmask(signal.SIG_BLOCK, set()) == initial, transaction.failure
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, initial)


@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM])
@pytest.mark.parametrize("durability_failure", [False, True])
def test_fresh_cli_daily_import_and_process_signal(tmp_path, signum, durability_failure, record_testsuite_property):
    """fresh CLI 真載 pandas；核對建立期 mask，並以 process kill 驗成功及 durability NO-GO。"""
    import subprocess
    import sys

    script = r'''
import ctypes, importlib.util, json, os, signal, stat, sys, tempfile
from pathlib import Path
sys.path.insert(0, sys.argv[1])
tempfile.tempdir = os.environ['TMPDIR']
import pytest
from scripts import activate_automation_runtime as activation
from tests.test_automation_runtime_activation import activation_env

root = Path(sys.argv[2])
signum = int(sys.argv[3])
durability_failure = sys.argv[4] == '1'
watch = {signal.SIGINT, signal.SIGTERM}
initial = signal.pthread_sigmask(signal.SIG_BLOCK, set())
observed, delivered = {}, []

class TaskInfo(ctypes.Structure):
    _fields_ = [('u' + str(i), ctypes.c_uint64) for i in range(6)] + [('i' + str(i), ctypes.c_int32) for i in range(12)]

def threads():
    info = TaskInfo()
    lib = ctypes.CDLL('/usr/lib/libproc.dylib', use_errno=True)
    assert lib.proc_pidinfo(os.getpid(), 4, 0, ctypes.byref(info), ctypes.sizeof(info)) == ctypes.sizeof(info)
    return info.i9

mp = pytest.MonkeyPatch()
env = activation_env.__wrapped__(root, mp)
runner, receipt = env['runner'], env['receipt']
original_spec = activation.importlib.util.spec_from_file_location

def helper_spec(name, path, *args, **kwargs):
    spec = original_spec(name, path, *args, **kwargs)
    if name == 'candidate_daily_market_reference':
        execute = spec.loader.exec_module
        def observed_import(module):
            mask = signal.pthread_sigmask(signal.SIG_BLOCK, set())
            assert watch <= mask
            observed['import_mask'] = sorted(mask)
            observed['threads_before_import'] = threads()
            execute(module)
            observed['threads_after_import'] = threads()
            assert watch <= signal.pthread_sigmask(signal.SIG_BLOCK, set())
            count = module.expected_market_counts
            def observed_count(*a, **k):
                mask = signal.pthread_sigmask(signal.SIG_BLOCK, set())
                assert watch <= mask
                observed['count_mask'] = sorted(mask)
                value = count(*a, **k)
                assert value == {'twse': 1, 'tpex': 1}
                observed['threads_after_count'] = threads()
                return value
            module.expected_market_counts = observed_count
        spec.loader.exec_module = observed_import
    return spec

mp.setattr(activation.importlib.util, 'spec_from_file_location', helper_spec)
factory = activation.ActivationTransaction
transaction = None

def original_handler(received, _frame):
    delivered.append([received, receipt.exists(), bool(transaction._denial_lock_handles),
                      all(not path.exists() for path in transaction.staging_paths)])

previous_handler = signal.signal(signum, original_handler)

def build(**kwargs):
    global transaction
    transaction = factory(**kwargs, command_runner=runner)
    arm, commit = transaction._arm, transaction._commit_receipt
    def observed_arm():
        assert signal.pthread_sigmask(signal.SIG_BLOCK, set()) == initial
        arm()
    def process_signal(staged):
        assert watch <= signal.pthread_sigmask(signal.SIG_BLOCK, set())
        assert signal.getsignal(signum) == original_handler
        os.kill(os.getpid(), signum)
        assert delivered == [], 'native thread 在主線解除 mask 前交付了 original handler'
        commit(staged)
    transaction._arm, transaction._commit_receipt = observed_arm, process_signal
    return transaction

mp.setattr(activation, 'ActivationTransaction', build)
original_fsync = activation.os.fsync
def fsync(fd):
    if durability_failure and stat.S_ISDIR(os.fstat(fd).st_mode):
        raw = activation.fcntl.fcntl(fd, 50, b'\0' * 1024)
        path = Path(os.fsdecode(raw.split(b'\0', 1)[0])).resolve()
        if path == receipt.parent and receipt.exists():
            raise OSError('injected parent directory fsync failure')
    original_fsync(fd)
mp.setattr(activation.os, 'fsync', fsync)
sys.argv = ['activate', '--activate', '--runtime-root', str(env['runtime_root']),
            '--accepted-commit', 'a' * 40, '--expected-old-root', str(env['old_root']),
            '--launch-agents-dir', str(env['launch_agents']), '--receipt', str(receipt), '--job', 'daily']
try:
    cli_exit = activation.main()
    assert cli_exit == (75 if durability_failure else 0), transaction.failure
    assert signal.pthread_sigmask(signal.SIG_BLOCK, set()) == initial
    assert observed['threads_before_import'] == 1
    assert delivered == ([] if durability_failure else [[signum, True, False, True]])
    observed.update(cli_exit=cli_exit, delivered=delivered, status=transaction.status)
    print(json.dumps(observed))
finally:
    signal.signal(signum, previous_handler)
    mp.undo()
'''
    completed = subprocess.run(
        [sys.executable, "-I", "-B", "-c", script, str(PROJECT_ROOT), str(tmp_path),
         str(int(signum)), "1" if durability_failure else "0"],
        capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    observed = json.loads(completed.stdout.splitlines()[-1])
    record_testsuite_property(f"fresh_cli_signum_{int(signum)}_durability_{durability_failure}", json.dumps(observed))
    assert observed["threads_after_import"] >= observed["threads_before_import"]
    assert observed["threads_after_count"] >= observed["threads_before_import"]


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
        assert transaction.run() == "SIGNAL_TEARDOWN_UNCONFIRMED_NO_GO"
        assert transaction.status == "SIGNAL_TEARDOWN_UNCONFIRMED_NO_GO"
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
        # 排除 prepare scope；arm 開始計數後，outer disarm 與 bounded retry 仍納入。
        if how == signal.SIG_SETMASK and (transaction.armed or restore_calls > 0):
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
    assert all(
        runner.states[label]["root"] == runtime_root.resolve()
        for label in LEGACY_DEFAULT_LABELS
    )


def test_persistent_post_seal_mask_failure_returns_generic_no_go(
    activation_env: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Durable success 後 mask teardown 未確認時，run/main 必須 generic NO-GO。"""

    build = activation_env["build"]
    receipt = activation_env["receipt"]
    runtime_root = activation_env["runtime_root"]
    launch_agents = activation_env["launch_agents"]
    old_root = activation_env["old_root"]
    assert callable(build)
    assert isinstance(receipt, Path)
    assert isinstance(runtime_root, Path)
    assert isinstance(launch_agents, Path)
    assert isinstance(old_root, Path)
    transaction = build()
    original_pthread_sigmask = activation.signal.pthread_sigmask
    initial_mask = original_pthread_sigmask(signal.SIG_BLOCK, set())
    expected_mask = initial_mask - {signal.SIGINT, signal.SIGTERM}
    original_pthread_sigmask(signal.SIG_SETMASK, expected_mask)
    restore_attempts = 0

    def fail_persistent_post_seal_restore(
        how: int, mask: set[signal.Signals]
    ) -> set[signal.Signals]:
        nonlocal restore_attempts
        if how == signal.SIG_SETMASK and transaction._receipt_sealed:
            restore_attempts += 1
            raise OSError("injected persistent post-seal mask restore failure")
        return original_pthread_sigmask(how, mask)

    monkeypatch.setattr(
        activation.signal,
        "pthread_sigmask",
        fail_persistent_post_seal_restore,
    )
    try:
        assert transaction.run() == "SIGNAL_TEARDOWN_UNCONFIRMED_NO_GO"
        current_mask = original_pthread_sigmask(signal.SIG_BLOCK, set())
        durable = json.loads(receipt.read_text(encoding="utf-8"))
        assert transaction.status == "SIGNAL_TEARDOWN_UNCONFIRMED_NO_GO"
        assert restore_attempts == 2
        assert current_mask != expected_mask
        assert durable["status"] == "ACTIVATED_PARTIAL_ACCEPTANCE_PENDING"
        assert durable["signal_teardown"] == {
            "attestation": "REQUIRES_PROCESS_EXIT_STATUS",
            "confirmed_in_receipt": False,
        }

        class TeardownNoGoTransaction:
            def __init__(self, **kwargs: object) -> None:
                del kwargs

            def run(self) -> str:
                return "SIGNAL_TEARDOWN_UNCONFIRMED_NO_GO"

        monkeypatch.setattr(
            activation,
            "parse_args",
            lambda: activation.argparse.Namespace(
                activate=True,
                runtime_root=runtime_root,
                accepted_commit=ACCEPTED_SHA,
                launch_agents_dir=launch_agents,
                expected_old_root=old_root,
                receipt=receipt,
            ),
        )
        monkeypatch.setattr(activation, "ActivationTransaction", TeardownNoGoTransaction)
        assert activation.main() == 75
    finally:
        original_pthread_sigmask(signal.SIG_SETMASK, initial_mask)


def test_persistent_rollback_teardown_mask_failure_returns_generic_no_go(
    activation_env: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rollback topology完成但mask未確認時，不得回傳topology business status。"""

    build = activation_env["build"]
    receipt = activation_env["receipt"]
    assert callable(build)
    assert isinstance(receipt, Path)
    before = _target_bytes(activation_env)

    def hook(event: str, job: str | None) -> None:
        if job == "daily" and event == "after_bootout_mutation_before_probe":
            raise activation.ActivationError("injected rollback trigger")

    transaction = build(hook=hook)
    original_pthread_sigmask = activation.signal.pthread_sigmask
    initial_mask = original_pthread_sigmask(signal.SIG_BLOCK, set())
    expected_mask = initial_mask - {signal.SIGINT, signal.SIGTERM}
    original_pthread_sigmask(signal.SIG_SETMASK, expected_mask)
    restore_attempts = 0

    def fail_persistent_rollback_restore(
        how: int, mask: set[signal.Signals]
    ) -> set[signal.Signals]:
        nonlocal restore_attempts
        if how == signal.SIG_SETMASK and transaction._rollback_in_progress:
            restore_attempts += 1
            raise OSError("injected persistent rollback mask restore failure")
        return original_pthread_sigmask(how, mask)

    monkeypatch.setattr(
        activation.signal,
        "pthread_sigmask",
        fail_persistent_rollback_restore,
    )
    try:
        assert transaction.run() == "SIGNAL_TEARDOWN_UNCONFIRMED_NO_GO"
        current_mask = original_pthread_sigmask(signal.SIG_BLOCK, set())
        durable = json.loads(receipt.read_text(encoding="utf-8"))
        assert transaction.status == "SIGNAL_TEARDOWN_UNCONFIRMED_NO_GO"
        assert restore_attempts == 2
        assert current_mask != expected_mask
        assert durable["status"] == "ROLLED_BACK_NO_GO"
        assert durable["signal_teardown"] == {
            "attestation": "REQUIRES_PROCESS_EXIT_STATUS",
            "confirmed_in_receipt": False,
        }
        assert _target_bytes(activation_env) == before
        _assert_old_topology(activation_env)

        class TeardownNoGoTransaction:
            def __init__(self, **kwargs: object) -> None:
                del kwargs

            def run(self) -> str:
                return transaction.status

        monkeypatch.setattr(
            activation,
            "parse_args",
            lambda: activation.argparse.Namespace(
                activate=True,
                runtime_root=activation_env["runtime_root"],
                accepted_commit=ACCEPTED_SHA,
                launch_agents_dir=activation_env["launch_agents"],
                expected_old_root=activation_env["old_root"],
                receipt=receipt,
            ),
        )
        monkeypatch.setattr(activation, "ActivationTransaction", TeardownNoGoTransaction)
        assert activation.main() == 75
    finally:
        original_pthread_sigmask(signal.SIG_SETMASK, initial_mask)


def test_mask_restore_without_postcondition_change_returns_generic_no_go(
    activation_env: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    """SIG_SETMASK 無 exception但未改state時，readback必須判定teardown失敗。"""

    build = activation_env["build"]
    receipt = activation_env["receipt"]
    assert callable(build)
    assert isinstance(receipt, Path)
    transaction = build()
    original_pthread_sigmask = activation.signal.pthread_sigmask
    initial_mask = original_pthread_sigmask(signal.SIG_BLOCK, set())
    expected_mask = initial_mask - {signal.SIGINT, signal.SIGTERM}
    original_pthread_sigmask(signal.SIG_SETMASK, expected_mask)
    ignored_restores = 0

    def ignore_post_seal_mask_restore(
        how: int, mask: set[signal.Signals]
    ) -> set[signal.Signals]:
        nonlocal ignored_restores
        if how == signal.SIG_SETMASK and transaction._receipt_sealed:
            ignored_restores += 1
            return original_pthread_sigmask(signal.SIG_BLOCK, set())
        return original_pthread_sigmask(how, mask)

    monkeypatch.setattr(
        activation.signal,
        "pthread_sigmask",
        ignore_post_seal_mask_restore,
    )
    try:
        assert transaction.run() == "SIGNAL_TEARDOWN_UNCONFIRMED_NO_GO"
        current_mask = original_pthread_sigmask(signal.SIG_BLOCK, set())
        durable = json.loads(receipt.read_text(encoding="utf-8"))
        assert transaction.status == "SIGNAL_TEARDOWN_UNCONFIRMED_NO_GO"
        assert ignored_restores == 1
        assert current_mask != expected_mask
        assert durable["status"] == "ACTIVATED_PARTIAL_ACCEPTANCE_PENDING"
        assert durable["signal_teardown"] == {
            "attestation": "REQUIRES_PROCESS_EXIT_STATUS",
            "confirmed_in_receipt": False,
        }
    finally:
        original_pthread_sigmask(signal.SIG_SETMASK, initial_mask)


def test_confirmed_signal_teardown_preserves_success_status_and_exit_zero(
    activation_env: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Handler與mask post-condition exact時，成功status與exit 0維持不變。"""

    build = activation_env["build"]
    receipt = activation_env["receipt"]
    assert callable(build)
    assert isinstance(receipt, Path)
    original_signal = activation.signal.signal
    original_pthread_sigmask = activation.signal.pthread_sigmask
    previous_handlers = {
        signum: signal.getsignal(signum)
        for signum in (signal.SIGINT, signal.SIGTERM)
    }
    initial_mask = original_pthread_sigmask(signal.SIG_BLOCK, set())
    expected_mask = initial_mask - {signal.SIGINT, signal.SIGTERM}
    original_pthread_sigmask(signal.SIG_SETMASK, expected_mask)

    def original_handler(signum: int, frame: object) -> None:
        del signum, frame

    for signum in (signal.SIGINT, signal.SIGTERM):
        original_signal(signum, original_handler)
    transaction = build()
    try:
        assert transaction.run() == "ACTIVATED_PARTIAL_ACCEPTANCE_PENDING"
        assert transaction.status == "ACTIVATED_PARTIAL_ACCEPTANCE_PENDING"
        assert all(
            signal.getsignal(signum) == original_handler
            for signum in (signal.SIGINT, signal.SIGTERM)
        )
        assert original_pthread_sigmask(signal.SIG_BLOCK, set()) == expected_mask
        durable = json.loads(receipt.read_text(encoding="utf-8"))
        assert durable["status"] == "ACTIVATED_PARTIAL_ACCEPTANCE_PENDING"
        assert durable["signal_teardown"] == {
            "attestation": "REQUIRES_PROCESS_EXIT_STATUS",
            "confirmed_in_receipt": False,
        }

        class SuccessfulTransaction:
            def __init__(self, **kwargs: object) -> None:
                del kwargs

            def run(self) -> str:
                return transaction.status

        monkeypatch.setattr(
            activation,
            "parse_args",
            lambda: activation.argparse.Namespace(
                activate=True,
                runtime_root=activation_env["runtime_root"],
                accepted_commit=ACCEPTED_SHA,
                launch_agents_dir=activation_env["launch_agents"],
                expected_old_root=activation_env["old_root"],
                receipt=receipt,
            ),
        )
        monkeypatch.setattr(activation, "ActivationTransaction", SuccessfulTransaction)
        assert activation.main() == 0
    finally:
        for signum, handler in previous_handlers.items():
            original_signal(signum, handler)
        original_pthread_sigmask(signal.SIG_SETMASK, initial_mask)


def test_lock_release_failure_cannot_skip_signal_teardown_or_cli_no_go(
    activation_env: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lock cleanup 失敗仍須完成 signal teardown，CLI 並以 75 fail closed。"""

    build = activation_env["build"]
    receipt = activation_env["receipt"]
    runtime_root = activation_env["runtime_root"]
    launch_agents = activation_env["launch_agents"]
    old_root = activation_env["old_root"]
    assert callable(build)
    assert isinstance(receipt, Path)
    assert isinstance(runtime_root, Path)
    assert isinstance(launch_agents, Path)
    assert isinstance(old_root, Path)

    transaction = build()
    original_flock = activation.fcntl.flock
    original_pthread_sigmask = activation.signal.pthread_sigmask
    previous_handlers = {
        signum: signal.getsignal(signum)
        for signum in (signal.SIGINT, signal.SIGTERM)
    }
    initial_mask = original_pthread_sigmask(signal.SIG_BLOCK, set())
    expected_mask = initial_mask - {signal.SIGINT, signal.SIGTERM}
    original_pthread_sigmask(signal.SIG_SETMASK, expected_mask)
    unlock_failed = False

    def fail_first_unlock(fd: int, operation: int) -> object:
        nonlocal unlock_failed
        if operation == activation.fcntl.LOCK_UN and not unlock_failed:
            unlock_failed = True
            raise OSError("injected denial lock release failure")
        return original_flock(fd, operation)

    monkeypatch.setattr(activation.fcntl, "flock", fail_first_unlock)
    try:
        with pytest.raises(activation.ActivationError, match="denial lock release failed"):
            transaction.run()

        durable = json.loads(receipt.read_text(encoding="utf-8"))
        assert unlock_failed
        assert durable["status"] == "ACTIVATED_PARTIAL_ACCEPTANCE_PENDING"
        assert durable["signal_teardown"] == {
            "attestation": "REQUIRES_PROCESS_EXIT_STATUS",
            "confirmed_in_receipt": False,
        }
        assert all(
            signal.getsignal(signum) == previous_handlers[signum]
            for signum in (signal.SIGINT, signal.SIGTERM)
        )
        assert original_pthread_sigmask(signal.SIG_BLOCK, set()) == expected_mask
        assert not transaction._denial_lock_handles
        for guard_name, _, _ in activation.TARGET_JOBS:
            lock_path = runtime_root / "logs" / "storage_safety" / f"{guard_name}.lock"
            with lock_path.open("a+") as handle:
                original_flock(
                    handle.fileno(),
                    activation.fcntl.LOCK_EX | activation.fcntl.LOCK_NB,
                )
                original_flock(handle.fileno(), activation.fcntl.LOCK_UN)

        class CleanupFailureTransaction:
            def __init__(self, **kwargs: object) -> None:
                del kwargs

            def run(self) -> str:
                raise activation.ActivationError("injected protection release failure")

        monkeypatch.setattr(
            activation,
            "parse_args",
            lambda: activation.argparse.Namespace(
                activate=True,
                runtime_root=runtime_root,
                accepted_commit=ACCEPTED_SHA,
                launch_agents_dir=launch_agents,
                expected_old_root=old_root,
                receipt=receipt,
            ),
        )
        monkeypatch.setattr(
            activation,
            "ActivationTransaction",
            CleanupFailureTransaction,
        )
        assert activation.main() == 75
    finally:
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)
        original_pthread_sigmask(signal.SIG_SETMASK, initial_mask)


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
        assert all(
            runner.states[label]["root"] == runtime_root.resolve()
            for label in LEGACY_DEFAULT_LABELS
        )
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
    assert len(release_indexes) == len(activation.LEGACY_DEFAULT_TARGET_JOBS)
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


def test_fog_only_activation_keeps_other_core_jobs_byte_and_runtime_identical(
    activation_env: dict[str, object],
) -> None:
    """Fog-only 成功路徑不得 mutation 另外兩條核心 job。"""

    build = activation_env["build"]
    runner = activation_env["runner"]
    receipt = activation_env["receipt"]
    assert callable(build)
    assert isinstance(runner, FakeCommandRunner)
    assert isinstance(receipt, Path)
    before = _target_bytes(activation_env)
    before_states = {label: dict(state) for label, state in runner.states.items()}

    transaction = build(target_jobs=FOG_ONLY)
    assert transaction.run() == "ACTIVATED_PARTIAL_ACCEPTANCE_PENDING"

    fog_label = "com.new-top10.fog-research-worker"
    for label, old_bytes in before.items():
        if label != fog_label:
            assert _target_bytes(activation_env)[label] == old_bytes
            assert runner.states[label] == before_states[label]
    touched_labels = {
        label
        for operation, label in runner.calls
        if operation in {"bootout", "bootstrap", "kickstart"}
    }
    assert touched_labels == {fog_label}
    _assert_fog_only_never_created_unselected_artifacts(activation_env)
    daily_marker = (
        activation_env["old_root"]
        / "logs"
        / "storage_safety"
        / "restart_denied"
        / "daily.json"
    )
    assert isinstance(daily_marker, Path)
    assert json.loads(daily_marker.read_text(encoding="utf-8"))["job"] == "daily"
    durable = json.loads(receipt.read_text(encoding="utf-8"))
    assert durable["target_labels"] == [fog_label]
    assert set(durable["jobs"]) == {"fog-research-worker"}
    assert {
        "com.new-top10.daily.plist",
        "com.new-top10.external-review-preflight.plist",
    } <= set(durable["out_of_scope_plists_before"])


@pytest.mark.parametrize(
    ("fault_event", "expected_bootout", "expected_bootstrap"),
    [
        ("before_denial_mirror", 0, 0),
        ("after_denial_mirror_write_before_verify", 0, 0),
        ("after_denial_clear", 0, 0),
        ("before_bootout", 0, 0),
        ("after_bootout_mutation_before_probe", 1, 1),
        ("before_plist_replace", 1, 1),
        ("after_plist_replace", 1, 1),
        ("after_bootstrap", 2, 2),
    ],
)
def test_fog_only_failure_states_restore_exactly_without_touching_other_jobs(
    activation_env: dict[str, object],
    fault_event: str,
    expected_bootout: int,
    expected_bootstrap: int,
) -> None:
    """Fog-only 在 mutation 前、中、後失敗都只 rollback Fog 且精確一次。"""

    build = activation_env["build"]
    runner = activation_env["runner"]
    assert callable(build)
    assert isinstance(runner, FakeCommandRunner)
    before = _target_bytes(activation_env)
    before_states = {label: dict(state) for label, state in runner.states.items()}

    def hook(event: str, job: str | None) -> None:
        if event == fault_event and job == "fog-research-worker":
            raise activation.ActivationError(f"injected {fault_event}")

    transaction = build(hook=hook, target_jobs=FOG_ONLY)
    assert transaction.run() == "ROLLED_BACK_NO_GO"

    assert _target_bytes(activation_env) == before
    assert runner.states == before_states
    fog_label = "com.new-top10.fog-research-worker"
    mutation_calls = [
        (operation, label)
        for operation, label in runner.calls
        if operation in {"bootout", "bootstrap", "kickstart"}
    ]
    assert {label for _, label in mutation_calls} <= {fog_label}
    assert mutation_calls.count(("bootout", fog_label)) == expected_bootout
    assert mutation_calls.count(("bootstrap", fog_label)) == expected_bootstrap
    _assert_fog_only_never_created_unselected_artifacts(activation_env)


def test_fog_only_detects_unselected_core_plist_drift_and_returns_no_go(
    activation_env: dict[str, object],
) -> None:
    """未選核心 plist 在 transaction 中漂移時不得宣稱 bounded success。"""

    build = activation_env["build"]
    launch_agents = activation_env["launch_agents"]
    runner = activation_env["runner"]
    assert callable(build)
    assert isinstance(launch_agents, Path)
    assert isinstance(runner, FakeCommandRunner)
    daily_path = launch_agents / "com.new-top10.daily.plist"

    def hook(event: str, job: str | None) -> None:
        if event == "after_bootstrap" and job == "fog-research-worker":
            daily_path.write_bytes(daily_path.read_bytes() + b"\n<!-- injected drift -->\n")

    transaction = build(hook=hook, target_jobs=FOG_ONLY)
    assert transaction.run() == "ROLLBACK_VERIFICATION_FAILED"
    assert "out-of-scope launchd plist changed" in (transaction.failure or "")
    assert runner.states["com.new-top10.daily"]["root"] == activation_env["old_root"]
    _assert_fog_only_never_created_unselected_artifacts(activation_env)


def test_fog_only_receipt_seal_failure_rolls_back_only_fog(
    activation_env: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    """成功拓樸後 receipt seal 失敗，仍只可 rollback Fog。"""

    build = activation_env["build"]
    runner = activation_env["runner"]
    assert callable(build)
    assert isinstance(runner, FakeCommandRunner)
    before = _target_bytes(activation_env)
    before_states = {label: dict(state) for label, state in runner.states.items()}
    transaction = build(target_jobs=FOG_ONLY)

    def fail_receipt_stage(payload: bytes) -> Path:
        del payload
        raise activation.ActivationError("injected receipt stage failure")

    monkeypatch.setattr(transaction, "_stage_receipt_payload", fail_receipt_stage)
    assert transaction.run() == "ROLLED_BACK_NO_GO"
    assert _target_bytes(activation_env) == before
    assert runner.states == before_states
    _assert_fog_only_never_created_unselected_artifacts(activation_env)


@pytest.mark.parametrize(
    ("target_jobs", "message"),
    [
        ((), "不得為空"),
        (("fog-research-worker", "fog-research-worker"), "不得重複"),
        (("unknown-job",), "未知 target_jobs"),
    ],
)
def test_target_job_selection_rejects_invalid_scope_before_preflight(
    activation_env: dict[str, object],
    target_jobs: tuple[str, ...],
    message: str,
) -> None:
    """空、重複或未知 selector 必須在任何 runtime probe 前 fail closed。"""

    build = activation_env["build"]
    runner = activation_env["runner"]
    assert callable(build)
    assert isinstance(runner, FakeCommandRunner)

    with pytest.raises(activation.ActivationError, match=message):
        build(target_jobs=target_jobs)
    assert runner.calls == []


def test_parse_args_accepts_repeatable_bounded_job_selector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CLI 只接受 allowlist job，並保留使用者明確選取範圍。"""

    monkeypatch.setattr(
        activation.sys,
        "argv",
        [
            "activate_automation_runtime.py",
            "--runtime-root",
            "/tmp/runtime",
            "--accepted-commit",
            ACCEPTED_SHA,
            "--expected-old-root",
            "/tmp/old",
            "--receipt",
            "/tmp/receipt.json",
            "--job",
            "retrain-monitor",
            "--allow-dormant-target-activation",
            "--activate",
        ],
    )

    args = activation.parse_args()
    assert args.target_jobs == ["retrain-monitor"]
    assert args.allow_dormant_target_activation is True


def test_parse_args_accepts_enabled_unloaded_target_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """enabled/unloaded 模式必須由 CLI 明確旗標啟用。"""

    monkeypatch.setattr(
        activation.sys,
        "argv",
        [
            "activate_automation_runtime.py",
            "--runtime-root",
            "/tmp/runtime",
            "--accepted-commit",
            ACCEPTED_SHA,
            "--expected-old-root",
            "/tmp/old",
            "--receipt",
            "/tmp/receipt.json",
            "--job",
            "fog-research-worker",
            "--allow-enabled-unloaded-target-activation",
            "--activate",
        ],
    )

    args = activation.parse_args()
    assert args.target_jobs == ["fog-research-worker"]
    assert args.allow_enabled_unloaded_target_activation is True


def test_enabled_unloaded_mode_requires_explicit_job_selector(
    activation_env: dict[str, object],
) -> None:
    """不得用 enabled/unloaded 旗標隱式擴大到 legacy 三條預設 job。"""

    build = activation_env["build"]
    runner = activation_env["runner"]
    assert callable(build)
    assert isinstance(runner, FakeCommandRunner)

    with pytest.raises(activation.ActivationError, match="必須明確指定 --job"):
        build(allow_enabled_unloaded_target_activation=True)
    assert runner.calls == []


def test_enabled_unloaded_fog_requires_explicit_flag_before_mutation(
    activation_env: dict[str, object],
) -> None:
    """一般 target 意外 unloaded 時，未帶旗標仍維持原 fail-closed 契約。"""

    build = activation_env["build"]
    runner = activation_env["runner"]
    before = _target_bytes(activation_env)
    assert callable(build)
    assert isinstance(runner, FakeCommandRunner)
    runner.states["com.new-top10.fog-research-worker"]["loaded"] = False

    transaction = build(target_jobs=FOG_ONLY)
    assert transaction.run() == "PRECHECK_FAILED"
    assert "目前未載入" in (transaction.failure or "")
    assert _target_bytes(activation_env) == before
    assert all(
        operation not in {"bootout", "bootstrap", "enable", "disable", "kickstart"}
        for operation, _ in runner.calls
    )


def test_enabled_unloaded_fog_happy_path_bootstraps_without_bootout(
    activation_env: dict[str, object],
) -> None:
    """已證明 enabled+unloaded 的 Fog 只 replace/bootstrap，receipt 保留真實 prestate。"""

    build = activation_env["build"]
    runner = activation_env["runner"]
    receipt = activation_env["receipt"]
    runtime_root = activation_env["runtime_root"]
    assert callable(build)
    assert isinstance(runner, FakeCommandRunner)
    assert isinstance(receipt, Path)
    assert isinstance(runtime_root, Path)
    label = "com.new-top10.fog-research-worker"
    runner.states[label]["loaded"] = False

    transaction = build(
        target_jobs=FOG_ONLY,
        allow_enabled_unloaded_target_activation=True,
    )
    assert transaction.run() == "ACTIVATED_PARTIAL_ACCEPTANCE_PENDING"
    assert runner.states[label]["loaded"] is True
    assert runner.states[label]["root"] == runtime_root.resolve()
    mutation_calls = [
        (operation, target)
        for operation, target in runner.calls
        if operation in {"bootout", "bootstrap", "enable", "disable", "kickstart"}
    ]
    assert mutation_calls == [("bootstrap", label)]

    durable = json.loads(receipt.read_text(encoding="utf-8"))
    assert durable["jobs"]["fog-research-worker"]["pre_loaded"] is False
    assert durable["jobs"]["fog-research-worker"]["pre_disabled"] is False


def test_enabled_unloaded_fog_rejects_disabled_prestate_before_mutation(
    activation_env: dict[str, object],
) -> None:
    """unloaded 但 disabled 的 target 不得冒充 enabled+unloaded。"""

    build = activation_env["build"]
    runner = activation_env["runner"]
    before = _target_bytes(activation_env)
    assert callable(build)
    assert isinstance(runner, FakeCommandRunner)
    label = "com.new-top10.fog-research-worker"
    runner.states[label]["loaded"] = False
    runner.print_disabled_style = "bool"
    runner.print_disabled_overrides[label] = "disabled"

    transaction = build(
        target_jobs=FOG_ONLY,
        allow_enabled_unloaded_target_activation=True,
    )
    assert transaction.run() == "PRECHECK_FAILED"
    assert "實際為 disabled" in (transaction.failure or "")
    assert _target_bytes(activation_env) == before
    assert all(
        operation not in {"bootout", "bootstrap", "enable", "disable", "kickstart"}
        for operation, _ in runner.calls
    )


def test_enabled_unloaded_fog_bootstrap_failure_restores_unloaded_prestate(
    activation_env: dict[str, object],
) -> None:
    """bootstrap 已 mutation 後失敗時，rollback 必須回復 old plist 與 enabled+unloaded。"""

    build = activation_env["build"]
    runner = activation_env["runner"]
    before = _target_bytes(activation_env)
    assert callable(build)
    assert isinstance(runner, FakeCommandRunner)
    label = "com.new-top10.fog-research-worker"
    runner.states[label]["loaded"] = False
    runner.fail("bootstrap", label, when="after")

    transaction = build(
        target_jobs=FOG_ONLY,
        allow_enabled_unloaded_target_activation=True,
    )
    assert transaction.run() == "ROLLED_BACK_NO_GO"
    assert _target_bytes(activation_env) == before
    assert runner.states[label]["loaded"] is False
    assert runner.states[label]["disabled"] is False


def test_enabled_unloaded_fog_replace_failure_restores_unloaded_prestate(
    activation_env: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """plist replace mutation 失敗時，rollback 必須保留 enabled+unloaded prestate。"""

    build = activation_env["build"]
    runner = activation_env["runner"]
    before = _target_bytes(activation_env)
    assert callable(build)
    assert isinstance(runner, FakeCommandRunner)
    label = "com.new-top10.fog-research-worker"
    runner.states[label]["loaded"] = False

    real_replace = activation.os.replace
    calls = 0

    def fail_first_replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("injected replace failure")
        real_replace(src, dst)

    monkeypatch.setattr(activation.os, "replace", fail_first_replace)
    transaction = build(
        target_jobs=FOG_ONLY,
        allow_enabled_unloaded_target_activation=True,
    )
    assert transaction.run() == "ROLLED_BACK_NO_GO"
    assert _target_bytes(activation_env) == before
    assert runner.states[label]["loaded"] is False
    assert runner.states[label]["disabled"] is False


def test_enabled_unloaded_fog_verify_failure_restores_unloaded_prestate(
    activation_env: dict[str, object],
) -> None:
    """bootstrap 成功後 verify 失敗時，rollback 必須回到 enabled+unloaded。"""

    build = activation_env["build"]
    runner = activation_env["runner"]
    before = _target_bytes(activation_env)
    assert callable(build)
    assert isinstance(runner, FakeCommandRunner)
    label = "com.new-top10.fog-research-worker"
    runner.states[label]["loaded"] = False

    def fail_verify(event: str, job: str | None) -> None:
        if event == "after_bootstrap" and job == "fog-research-worker":
            runner.states[label]["root"] = Path("/private/tmp/injected-wrong-root")

    transaction = build(
        target_jobs=FOG_ONLY,
        allow_enabled_unloaded_target_activation=True,
        hook=fail_verify,
    )
    assert transaction.run() == "ROLLED_BACK_NO_GO"
    assert _target_bytes(activation_env) == before
    assert runner.states[label]["loaded"] is False
    assert runner.states[label]["disabled"] is False


def test_cli_duplicate_job_selector_uses_uniform_no_go_boundary(
    activation_env: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """重複 selector 不得洩漏 traceback 或繞過 CLI exit contract。"""

    monkeypatch.setattr(
        activation,
        "parse_args",
        lambda: activation.argparse.Namespace(
            activate=True,
            runtime_root=activation_env["runtime_root"],
            accepted_commit=ACCEPTED_SHA,
            launch_agents_dir=activation_env["launch_agents"],
            expected_old_root=activation_env["old_root"],
            receipt=activation_env["receipt"],
            target_jobs=["fog-research-worker", "fog-research-worker"],
        ),
    )

    assert activation.main() == 75
    captured = capsys.readouterr()
    assert "A4_ACTIVATION_NO_GO: ActivationError: target_jobs 不得重複" in captured.err
    assert "Traceback" not in captured.err


def test_legacy_default_scope_remains_exactly_three_loaded_jobs(
    activation_env: dict[str, object],
) -> None:
    """擴充 allowlist 不得把 dormant retrain 偷渡進 legacy default。"""

    build = activation_env["build"]
    runner = activation_env["runner"]
    assert callable(build)
    assert isinstance(runner, FakeCommandRunner)

    transaction = build()
    assert {label for _, label, _ in transaction.target_jobs} == LEGACY_DEFAULT_LABELS
    assert transaction.run() == "ACTIVATED_PARTIAL_ACCEPTANCE_PENDING"
    assert not any(label == RETRAIN_LABEL for _, label in runner.calls)


def test_dormant_retrain_requires_explicit_flag_before_any_mutation(
    activation_env: dict[str, object],
) -> None:
    """只給 selector 不足以授權 disabled/unloaded job activation。"""

    build = activation_env["build"]
    runner = activation_env["runner"]
    before = _target_bytes(activation_env)
    assert callable(build)
    assert isinstance(runner, FakeCommandRunner)

    with pytest.raises(activation.ActivationError, match="dormant target"):
        build(target_jobs=RETRAIN_ONLY)

    assert runner.calls == []
    assert _target_bytes(activation_env) == before
    assert runner.states[RETRAIN_LABEL]["disabled"] is True
    assert runner.states[RETRAIN_LABEL]["loaded"] is False


def test_dormant_retrain_explicit_flag_requires_observed_disabled_prestate(
    activation_env: dict[str, object],
) -> None:
    """顯式旗標仍須由 print-disabled 證明 target 當下確實 disabled。"""

    build = activation_env["build"]
    runner = activation_env["runner"]
    before = _target_bytes(activation_env)
    assert callable(build)
    assert isinstance(runner, FakeCommandRunner)
    runner.states[RETRAIN_LABEL]["disabled"] = False

    transaction = build(
        target_jobs=RETRAIN_ONLY,
        allow_dormant_target_activation=True,
    )
    assert transaction.run() == "PRECHECK_FAILED"
    assert _target_bytes(activation_env) == before
    assert all(
        operation not in {"bootout", "bootstrap", "enable", "disable", "kickstart"}
        for operation, _ in runner.calls
    )
    assert ("print-disabled", None) in runner.calls


def test_dormant_retrain_accepts_boolean_print_disabled_compatibility(
    activation_env: dict[str, object],
) -> None:
    """舊 bool 形式仍可相容，但 selector identity 必須是 retrain-monitor。"""

    build = activation_env["build"]
    runner = activation_env["runner"]
    assert callable(build)
    assert isinstance(runner, FakeCommandRunner)
    runner.print_disabled_style = "bool"

    transaction = build(
        target_jobs=RETRAIN_ONLY,
        allow_dormant_target_activation=True,
    )
    assert transaction.run() == "ACTIVATED_PARTIAL_ACCEPTANCE_PENDING"
    assert transaction.jobs[0].guard_name == "retrain-monitor"


def test_dormant_retrain_unknown_print_disabled_value_fails_closed(
    activation_env: dict[str, object],
) -> None:
    """未知 launchctl disabled state 不得被猜成 enabled 或 disabled。"""

    build = activation_env["build"]
    runner = activation_env["runner"]
    before = _target_bytes(activation_env)
    assert callable(build)
    assert isinstance(runner, FakeCommandRunner)
    runner.print_disabled_overrides[RETRAIN_LABEL] = "unknown-state"

    transaction = build(
        target_jobs=RETRAIN_ONLY,
        allow_dormant_target_activation=True,
    )
    assert transaction.run() == "PRECHECK_FAILED"
    assert "未知 disabled state" in (transaction.failure or "")
    assert _target_bytes(activation_env) == before
    assert all(
        operation not in {"bootout", "bootstrap", "enable", "disable", "kickstart"}
        for operation, _ in runner.calls
    )


def test_dormant_retrain_transient_launchctl_print_fails_preflight_closed(
    activation_env: dict[str, object],
) -> None:
    """launchctl 暫時錯誤不得被誤判成明確 unloaded。"""

    build = activation_env["build"]
    runner = activation_env["runner"]
    before = _target_bytes(activation_env)
    assert callable(build)
    assert isinstance(runner, FakeCommandRunner)
    runner.print_results[RETRAIN_LABEL] = [
        activation.CommandResult(5, "", "Input/output error")
    ]

    transaction = build(
        target_jobs=RETRAIN_ONLY,
        allow_dormant_target_activation=True,
    )
    assert transaction.run() == "PRECHECK_FAILED"
    assert "launchctl print 無法判定 service state" in (transaction.failure or "")
    assert _target_bytes(activation_env) == before
    assert all(
        operation not in {"bootout", "bootstrap", "enable", "disable", "kickstart"}
        for operation, _ in runner.calls
    )


def test_dormant_retrain_unknown_rollback_readback_is_verification_failed(
    activation_env: dict[str, object],
) -> None:
    """rollback 中 launchctl readback 不明時不得宣稱已回復。"""

    build = activation_env["build"]
    runner = activation_env["runner"]
    assert callable(build)
    assert isinstance(runner, FakeCommandRunner)
    runner.fail("bootstrap", RETRAIN_LABEL, when="after")
    runner.print_results[RETRAIN_LABEL] = [
        None,
        None,
        activation.CommandResult(5, "", "Input/output error during rollback"),
    ]

    transaction = build(
        target_jobs=RETRAIN_ONLY,
        allow_dormant_target_activation=True,
    )
    assert transaction.run() == "ROLLBACK_VERIFICATION_FAILED"
    assert "launchctl print 無法判定 service state" in (transaction.failure or "")


def test_dormant_retrain_rendered_program_arguments_drift_fails_closed(
    activation_env: dict[str, object],
) -> None:
    """retrain-monitor rendered argv 必須逐項完整符合核准命令。"""

    build = activation_env["build"]
    runner = activation_env["runner"]
    runtime_root = activation_env["runtime_root"]
    before = _target_bytes(activation_env)
    assert callable(build)
    assert isinstance(runner, FakeCommandRunner)
    assert isinstance(runtime_root, Path)
    template = runtime_root / "scripts" / "com.new-top10.retrain.plist"
    payload = plistlib.loads(template.read_bytes())
    payload["ProgramArguments"].append("--unexpected")
    template.write_bytes(plistlib.dumps(payload))

    transaction = build(
        target_jobs=RETRAIN_ONLY,
        allow_dormant_target_activation=True,
    )
    assert transaction.run() == "PRECHECK_FAILED"
    assert "retrain-monitor ProgramArguments drift" in (transaction.failure or "")
    assert _target_bytes(activation_env) == before
    assert all(
        operation not in {"bootout", "bootstrap", "enable", "disable", "kickstart"}
        for operation, _ in runner.calls
    )


def test_dormant_retrain_accepts_exact_legacy_unguarded_monitor_prestate(
    activation_env: dict[str, object],
) -> None:
    """既有 direct monitor plist 應安全映射至舊 retrain identity。"""

    build = activation_env["build"]
    assert callable(build)
    _install_legacy_unguarded_retrain(activation_env)

    transaction = build(
        target_jobs=RETRAIN_ONLY,
        allow_dormant_target_activation=True,
    )

    assert transaction.run() == "ACTIVATED_PARTIAL_ACCEPTANCE_PENDING"
    durable = json.loads(transaction.receipt_path.read_text(encoding="utf-8"))
    retrain = durable["jobs"]["retrain-monitor"]
    assert retrain["old_storage_identity"] == "retrain"
    assert retrain["new_storage_identity"] == "retrain-monitor"


def test_dormant_retrain_rejects_legacy_unguarded_command_drift(
    activation_env: dict[str, object],
) -> None:
    """legacy 例外不得接納非 canonical direct monitor argv。"""

    build = activation_env["build"]
    launch_agents = activation_env["launch_agents"]
    runner = activation_env["runner"]
    assert callable(build)
    assert isinstance(launch_agents, Path)
    assert isinstance(runner, FakeCommandRunner)
    _install_legacy_unguarded_retrain(activation_env)
    installed = launch_agents / f"{RETRAIN_LABEL}.plist"
    payload = plistlib.loads(installed.read_bytes())
    payload["ProgramArguments"][-1] = "manual"
    installed.write_bytes(plistlib.dumps(payload))
    before = _target_bytes(activation_env)

    transaction = build(
        target_jobs=RETRAIN_ONLY,
        allow_dormant_target_activation=True,
    )

    assert transaction.run() == "PRECHECK_FAILED"
    assert "retrain plist prestate argv 未核准" in (transaction.failure or "")
    assert _target_bytes(activation_env) == before
    assert all(
        operation not in {"bootout", "bootstrap", "enable", "disable", "kickstart"}
        for operation, _ in runner.calls
    )


@pytest.mark.parametrize("wrong_identity", ["daily", "reference", "unknown", "../retrain"])
def test_dormant_retrain_rejects_guard_shaped_identity_drift(
    activation_env: dict[str, object],
    wrong_identity: str,
) -> None:
    """retrain label 不得用 generic guard 將舊 identity 偽裝成其他 job。"""

    build = activation_env["build"]
    launch_agents = activation_env["launch_agents"]
    old_root = activation_env["old_root"]
    runner = activation_env["runner"]
    assert callable(build)
    assert isinstance(launch_agents, Path)
    assert isinstance(old_root, Path)
    assert isinstance(runner, FakeCommandRunner)
    installed = launch_agents / f"{RETRAIN_LABEL}.plist"
    payload = plistlib.loads(installed.read_bytes())
    payload["ProgramArguments"] = [
        "/bin/bash",
        str(old_root / "scripts" / "run_with_storage_guard.sh"),
        wrong_identity,
        "/bin/bash",
        str(old_root / "scripts" / "daily_retrain.sh"),
        "monitor",
        "--trigger",
        "scheduled",
    ]
    installed.write_bytes(plistlib.dumps(payload))
    marker = (
        old_root
        / "logs"
        / "storage_safety"
        / "restart_denied"
        / "retrain.json"
    )
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text('{"reason":"LEGACY_RETRAIN_DENIAL"}\n', encoding="utf-8")
    before = _target_bytes(activation_env)

    transaction = build(
        target_jobs=RETRAIN_ONLY,
        allow_dormant_target_activation=True,
    )

    assert transaction.run() == "PRECHECK_FAILED"
    assert "retrain plist prestate argv 未核准" in (transaction.failure or "")
    assert _target_bytes(activation_env) == before
    assert all(
        operation not in {"bootout", "bootstrap", "enable", "disable", "kickstart"}
        for operation, _ in runner.calls
    )


def test_dormant_retrain_rejects_guarded_child_argv_drift(
    activation_env: dict[str, object],
) -> None:
    """即使 identity 正確，guarded child argv 漂移也必須拒絕。"""

    build = activation_env["build"]
    launch_agents = activation_env["launch_agents"]
    runner = activation_env["runner"]
    assert callable(build)
    assert isinstance(launch_agents, Path)
    assert isinstance(runner, FakeCommandRunner)
    installed = launch_agents / f"{RETRAIN_LABEL}.plist"
    payload = plistlib.loads(installed.read_bytes())
    payload["ProgramArguments"].append("--unexpected")
    installed.write_bytes(plistlib.dumps(payload))
    before = _target_bytes(activation_env)

    transaction = build(
        target_jobs=RETRAIN_ONLY,
        allow_dormant_target_activation=True,
    )

    assert transaction.run() == "PRECHECK_FAILED"
    assert "retrain plist prestate argv 未核准" in (transaction.failure or "")
    assert _target_bytes(activation_env) == before
    assert all(
        operation not in {"bootout", "bootstrap", "enable", "disable", "kickstart"}
        for operation, _ in runner.calls
    )


def test_dormant_retrain_old_identity_marker_blocks_before_mutation(
    activation_env: dict[str, object],
) -> None:
    """舊 retrain denial 不得因 identity 遷移而被略過或清除。"""

    build = activation_env["build"]
    runner = activation_env["runner"]
    old_root = activation_env["old_root"]
    before = _target_bytes(activation_env)
    assert callable(build)
    assert isinstance(runner, FakeCommandRunner)
    assert isinstance(old_root, Path)
    _install_legacy_unguarded_retrain(activation_env)
    before = _target_bytes(activation_env)
    marker = (
        old_root
        / "logs"
        / "storage_safety"
        / "restart_denied"
        / "retrain.json"
    )
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text('{"reason":"LEGACY_RETRAIN_DENIAL"}\n', encoding="utf-8")
    marker_hash = activation.sha256_file(marker)

    transaction = build(
        target_jobs=RETRAIN_ONLY,
        allow_dormant_target_activation=True,
    )
    assert transaction.run() == "PRECHECK_FAILED"
    assert "舊 storage identity 已有 restart-denied" in (transaction.failure or "")
    assert activation.sha256_file(marker) == marker_hash
    receipt = activation_env["receipt"]
    assert isinstance(receipt, Path)
    durable = json.loads(receipt.read_text(encoding="utf-8"))
    retrain = durable["jobs"]["retrain-monitor"]
    assert retrain["old_storage_identity"] == "retrain"
    assert retrain["new_storage_identity"] == "retrain-monitor"
    assert retrain["old_storage_marker_sha256"] == marker_hash
    assert retrain["new_storage_marker_sha256"] is None
    assert _target_bytes(activation_env) == before
    assert all(
        operation not in {"bootout", "bootstrap", "enable", "disable", "kickstart"}
        for operation, _ in runner.calls
    )


def test_dormant_retrain_old_identity_held_lock_blocks_before_mutation(
    activation_env: dict[str, object],
) -> None:
    """舊 retrain writer lock 被持有時不得開始 activation mutation。"""

    build = activation_env["build"]
    runner = activation_env["runner"]
    old_root = activation_env["old_root"]
    before = _target_bytes(activation_env)
    assert callable(build)
    assert isinstance(runner, FakeCommandRunner)
    assert isinstance(old_root, Path)
    _install_legacy_unguarded_retrain(activation_env)
    before = _target_bytes(activation_env)
    lock_path = old_root / "logs" / "storage_safety" / "retrain.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+")
    activation.fcntl.flock(
        handle.fileno(), activation.fcntl.LOCK_EX | activation.fcntl.LOCK_NB
    )
    try:
        transaction = build(
            target_jobs=RETRAIN_ONLY,
            allow_dormant_target_activation=True,
        )
        assert transaction.run() == "PRECHECK_FAILED"
    finally:
        activation.fcntl.flock(handle.fileno(), activation.fcntl.LOCK_UN)
        handle.close()

    assert "舊 storage identity lock 正被持有" in (transaction.failure or "")
    assert _target_bytes(activation_env) == before
    assert all(
        operation not in {"bootout", "bootstrap", "enable", "disable", "kickstart"}
        for operation, _ in runner.calls
    )


def test_disabled_retrain_happy_path_is_explicit_and_bounded(
    activation_env: dict[str, object],
) -> None:
    """顯式 dormant selector 只 enable/bootstrap retrain 並留下完整 receipt。"""

    build = activation_env["build"]
    runner = activation_env["runner"]
    receipt = activation_env["receipt"]
    before = _target_bytes(activation_env)
    before_states = {label: dict(state) for label, state in runner.states.items()}
    assert callable(build)
    assert isinstance(runner, FakeCommandRunner)
    assert isinstance(receipt, Path)

    transaction = build(
        target_jobs=RETRAIN_ONLY,
        allow_dormant_target_activation=True,
    )
    assert transaction.run() == "ACTIVATED_PARTIAL_ACCEPTANCE_PENDING"

    for label in LEGACY_DEFAULT_LABELS:
        assert _target_bytes(activation_env)[label] == before[label]
        assert runner.states[label] == before_states[label]
    assert runner.states[RETRAIN_LABEL]["disabled"] is False
    assert runner.states[RETRAIN_LABEL]["loaded"] is True
    assert runner.states[RETRAIN_LABEL]["root"] == activation_env["runtime_root"]
    launch_agents = activation_env["launch_agents"]
    runtime_root = activation_env["runtime_root"]
    assert isinstance(launch_agents, Path)
    assert isinstance(runtime_root, Path)
    installed = launch_agents / f"{RETRAIN_LABEL}.plist"
    assert plistlib.loads(installed.read_bytes())["ProgramArguments"] == [
        "/bin/bash",
        str(runtime_root / "scripts" / "run_with_storage_guard.sh"),
        "retrain-monitor",
        "/bin/bash",
        str(runtime_root / "scripts" / "daily_retrain.sh"),
        "monitor",
        "--trigger",
        "scheduled",
    ]
    mutation_calls = [
        (operation, label)
        for operation, label in runner.calls
        if operation in {"bootout", "bootstrap", "enable", "disable", "kickstart"}
    ]
    assert mutation_calls == [
        ("enable", RETRAIN_LABEL),
        ("bootstrap", RETRAIN_LABEL),
    ]

    durable = json.loads(receipt.read_text(encoding="utf-8"))
    assert durable["target_labels"] == [RETRAIN_LABEL]
    assert set(durable["jobs"]) == {"retrain-monitor"}
    assert durable["jobs"]["retrain-monitor"]["pre_disabled"] is True
    assert durable["jobs"]["retrain-monitor"]["disabled_state_mutated"] is True
    assert durable["jobs"]["retrain-monitor"]["old_storage_identity"] == "retrain"
    assert (
        durable["jobs"]["retrain-monitor"]["new_storage_identity"]
        == "retrain-monitor"
    )
    assert durable["jobs"]["retrain-monitor"]["old_storage_marker_sha256"] is None
    assert durable["jobs"]["retrain-monitor"]["new_storage_marker_sha256"] is None
    assert (
        runtime_root / "logs" / "storage_safety" / "retrain-monitor.lock"
    ).is_file()
    assert not (
        runtime_root / "logs" / "storage_safety" / "retrain.lock"
    ).exists()
    assert {
        "com.new-top10.daily.plist",
        "com.new-top10.external-review-preflight.plist",
        "com.new-top10.fog-research-worker.plist",
    } <= set(durable["out_of_scope_plists_before"])


@pytest.mark.parametrize(
    ("operation", "when", "expected_disabled_mutation"),
    [
        ("enable", "before", False),
        ("enable", "after", True),
        ("bootstrap", "after", True),
    ],
)
def test_dormant_retrain_mutation_failure_restores_disabled_unloaded_prestate(
    activation_env: dict[str, object],
    operation: str,
    when: str,
    expected_disabled_mutation: bool,
) -> None:
    """enable/bootstrap 任一步失敗都須回復舊 bytes 與 disabled/unloaded。"""

    build = activation_env["build"]
    runner = activation_env["runner"]
    receipt = activation_env["receipt"]
    before = _target_bytes(activation_env)
    legacy_states = {
        label: dict(runner.states[label]) for label in LEGACY_DEFAULT_LABELS
    }
    assert callable(build)
    assert isinstance(runner, FakeCommandRunner)
    assert isinstance(receipt, Path)
    runner.fail(operation, RETRAIN_LABEL, when=when)

    transaction = build(
        target_jobs=RETRAIN_ONLY,
        allow_dormant_target_activation=True,
    )
    assert transaction.run() == "ROLLED_BACK_NO_GO"

    assert _target_bytes(activation_env) == before
    assert runner.states[RETRAIN_LABEL]["disabled"] is True
    assert runner.states[RETRAIN_LABEL]["loaded"] is False
    for label, state in legacy_states.items():
        assert runner.states[label] == state
    durable = json.loads(receipt.read_text(encoding="utf-8"))
    assert durable["jobs"]["retrain-monitor"]["pre_disabled"] is True
    assert (
        durable["jobs"]["retrain-monitor"]["disabled_state_mutated"]
        is expected_disabled_mutation
    )
    assert set(durable["out_of_scope_plists_before"]) >= {
        f"{label}.plist" for label in LEGACY_DEFAULT_LABELS
    }


@pytest.fixture
def source_transition_env(tmp_path: Path) -> dict:
    """真 Git linked worktree；launchd 使用可觀察非冪等 fake，不碰正式服務。"""
    source = tmp_path / "source"
    runtime = tmp_path / "runtime"
    agents = tmp_path / "LaunchAgents"
    source.mkdir()
    agents.mkdir()
    git_env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}

    def git(*args: str, root: Path = source) -> str:
        return subprocess.check_output(
            ["git", "-C", str(root), *args], env=git_env, text=True,
            stderr=subprocess.STDOUT,
        ).strip()

    git("init")
    git("config", "user.name", "activation fixture")
    git("config", "user.email", "activation@example.invalid")
    git("config", "core.hooksPath", os.devnull)
    (source / ".gitignore").write_text(".venv/\nlogs/\ndata/\nmodels/\nartifacts/\nignored-collision\n")
    (source / "scripts").mkdir()
    (source / "config").mkdir()
    (source / "config/automation.yaml").write_text("daily:\n  market_coverage_enabled: false\n")
    for _, _, template in activation.TARGET_JOBS:
        shutil.copy2(PROJECT_ROOT / "scripts" / template, source / "scripts" / template)
    (source / "uv.lock").write_text("fixture-lock\n")
    (source / "pyproject.toml").write_text("[project]\nname='fixture'\nversion='0.0.0'\n")
    (source / "code.txt").write_text("old\n")
    git("add", ".")
    git("commit", "-m", "fixture old")
    old = git("rev-parse", "HEAD")
    (source / "code.txt").write_text("accepted\n")
    git("commit", "-am", "fixture accepted")
    accepted = git("rev-parse", "HEAD")
    git("worktree", "add", "--detach", str(runtime), old)
    python = runtime / ".venv/bin/python"
    python.parent.mkdir(parents=True)
    python.write_text("#!/bin/sh\nexit 0\n")
    python.chmod(0o755)
    from dataclasses import asdict
    from app.storage_safety import _spawn_verified_process_group

    completed_child, completed_identity = _spawn_verified_process_group(
        [sys.executable, "-B", "-c", "pass"], cwd=runtime,
    )
    assert completed_child.wait(timeout=5) == 0
    completed_child.stdout.close()
    for guard, label, template in activation.TARGET_JOBS[:2]:
        (agents / f"{label}.plist").write_bytes(_render_template(template, runtime))
        latest = runtime / "logs/storage_safety" / f"{guard}_latest.json"
        latest.parent.mkdir(parents=True, exist_ok=True)
        # 真 child 已退出／reap；每次驗證仍須由原 observer 核對同一 PG。
        latest.write_text(json.dumps({"job": guard, "child_spawned": True,
                                      "process_group_identity": asdict(completed_identity), "status": "OK"}))
    hold = runtime / "logs/storage_safety/restart_denied/external-review-preflight.json"
    hold.parent.mkdir()
    hold.write_text('{"reason":"RECOVERY_READINESS_OWNER_HOLD"}\n')
    runner = FakeCommandRunner(runtime)
    for label in ("com.new-top10.fog-research-worker", RETRAIN_LABEL):
        runner.states[label]["root"] = tmp_path / "unrelated-runtime"
    before = {label: dict(state) for label, state in runner.states.items()}
    receipt = tmp_path / "evidence/activation.json"

    def run(command):
        if command[0] == "git":
            result = subprocess.run(command, env=git_env, text=True, capture_output=True)
            return activation.CommandResult(result.returncode, result.stdout, result.stderr)
        if command[1:] == ["print", "gui/999"]:
            labels = "\n".join("0 - " + label for label, state in runner.states.items() if state["loaded"])
            return activation.CommandResult(0, "services = {\n" + labels + "\n}\n")
        return runner(command)

    def build(**kwargs):
        return activation.ActivationTransaction(
            source_root=source, runtime_root=runtime, accepted_commit=accepted,
            previous_commit=old, launch_agents_dir=agents, expected_old_root=runtime,
            receipt_path=receipt, target_jobs=("daily",), launchctl_bin="launchctl",
            plutil_bin="plutil", domain="gui/999", command_runner=run, **kwargs,
        )

    return dict(source=source, runtime=runtime, agents=agents, git=git, old=old,
                accepted=accepted, runner=runner, before=before, receipt=receipt,
                hold=hold, hold_bytes=hold.read_bytes(), build=build)


def _assert_source_old(env: dict) -> None:
    assert env["git"]("rev-parse", "HEAD", root=env["runtime"]) == env["old"]
    assert (env["runtime"] / "code.txt").read_text() == "old\n"
    assert env["runner"].states == env["before"]
    assert env["hold"].read_bytes() == env["hold_bytes"]


@pytest.mark.parametrize("native_status", ["(pe)", "(unknown)"])
def test_source_inventory_native_pe_preserves_fail_closed(source_transition_env: dict, native_status: str) -> None:
    """真 host 的原生 pe 欄位仍須盤點服務；未知欄位不可放行。"""
    env = source_transition_env
    transaction = env["build"]()
    original = transaction.command_runner

    def run(command):
        result = original(command)
        if command[1:] == ["print", "gui/999"]:
            return activation.CommandResult(0, result.stdout.replace("0 - ", f"0 {native_status} "))
        return result

    transaction.command_runner = run
    result = transaction.run()
    if native_status == "(pe)":
        assert result == "ACTIVATED_PARTIAL_ACCEPTANCE_PENDING", transaction.failure
        assert env["git"]("rev-parse", "HEAD", root=env["runtime"]) == env["accepted"]
    else:
        assert result == "ROLLED_BACK_NO_GO", transaction.failure
        assert "inventory" in transaction.failure
        _assert_source_old(env)
    assert env["runner"].states == env["before"]
    assert env["hold"].read_bytes() == env["hold_bytes"]


def _source_no_child_hold(env: dict) -> Path:
    """重現真 host 的 legacy owner hold；不虛構 process group。"""
    env["hold"].write_text(json.dumps({
        "schema_version": "top10-storage-restart-denied.v1",
        "job": "external-review-preflight", "automatic_clear_allowed": False,
        "reasons": ["RECOVERY_READINESS_OWNER_HOLD"],
    }))
    env["hold_bytes"] = env["hold"].read_bytes()
    latest = env["runtime"] / "logs/storage_safety/external-review-preflight_latest.json"
    latest.write_text(json.dumps({
        "schema_version": "top10-storage-guard-receipt.v1",
        "job": "external-review-preflight", "status": "RESTART_DENIED",
        "child_spawned": False, "process_group_identity": None,
        "child_pid": None, "child_exit_code": None, "child_terminal_status": None,
        "restart_denied": True, "lock_owner_status": "HELD", "launch_verified": True,
        "invocation_id": "external-review-preflight-legacy-hold",
        "reasons": ["RECOVERY_READINESS_OWNER_HOLD", "PERSISTENT_RESTART_DENIED_MARKER"],
    }))
    return latest


@pytest.mark.parametrize("failure_event", [None, "after_source_checkout", "after_bootstrap"])
def test_source_transition_no_child_hold(source_transition_env: dict, failure_event: str | None) -> None:
    env = source_transition_env
    latest = _source_no_child_hold(env)
    original = latest.read_bytes()

    def fault(event, job):
        if event == failure_event:
            raise RuntimeError("no-child rollback 反例")

    transaction = env["build"](fault_hook=fault)
    result = transaction.run()
    if failure_event is None:
        assert result == "ACTIVATED_PARTIAL_ACCEPTANCE_PENDING", transaction.failure
        assert env["git"]("rev-parse", "HEAD", root=env["runtime"]) == env["accepted"]
    else:
        assert result == "ROLLED_BACK_NO_GO", transaction.failure
        _assert_source_old(env)
    assert env["hold"].read_bytes() == env["hold_bytes"]
    assert latest.read_bytes() == original
    assert env["runner"].states == env["before"]
    assert not transaction._source_locks


@pytest.mark.parametrize("failure", [
    "status", "child_spawned", "child_pid", "job", "invocation_id", "lock_owner_status",
    "launch_verified", "restart_denied", "hold_job", "hold_clear", "hold_reasons",
    "root_binding", "unresolved", "unloaded", "running", "missing_pg", "missing_child_pid",
    "guard_lock", "hold_drift", "receipt_drift",
])
def test_source_transition_no_child_rejects_missing_evidence(source_transition_env: dict, failure: str) -> None:
    env = source_transition_env
    latest = _source_no_child_hold(env)
    receipt = json.loads(latest.read_bytes())
    hold = json.loads(env["hold"].read_bytes())
    bad = {"status": "OVERLAP_BLOCKED", "child_spawned": True, "child_pid": 123,
           "job": "daily", "invocation_id": "", "lock_owner_status": "NOT_HELD",
           "launch_verified": False, "restart_denied": False}
    if failure in bad:
        receipt[failure] = bad[failure]
    elif failure == "hold_job":
        hold["job"] = "daily"
    elif failure == "hold_clear":
        hold["automatic_clear_allowed"] = True
    elif failure == "hold_reasons":
        hold["reasons"] = ["unrelated"]
    elif failure == "root_binding":
        hold["root_invocation_id"] = "other"
    elif failure == "unresolved":
        claim = latest.parent / "receipts/external-review-preflight/unfinished.json"
        claim.parent.mkdir(parents=True)
        claim.write_text('{"schema_version":"top10-storage-invocation-claim.v1"}')
    elif failure == "unloaded":
        env["runner"].states["com.new-top10.external-review-preflight"]["loaded"] = False
    elif failure == "running":
        env["runner"].states["com.new-top10.external-review-preflight"]["running"] = True
    elif failure == "missing_pg":
        receipt.pop("process_group_identity")
    elif failure == "missing_child_pid":
        receipt.pop("child_pid")
    latest.write_text(json.dumps(receipt))
    env["hold"].write_text(json.dumps(hold))

    def fault(event, job):
        if event == "after_source_quiesce":
            if failure == "hold_drift":
                env["hold"].write_bytes(env["hold"].read_bytes() + b"\n")
            elif failure == "receipt_drift":
                latest.write_bytes(latest.read_bytes() + b"\n")

    transaction = env["build"](fault_hook=fault)
    held = None
    if failure == "guard_lock":
        import fcntl
        held = (latest.parent / "external-review-preflight.lock").open("a+")
        fcntl.flock(held.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        assert transaction.run() != "ACTIVATED_PARTIAL_ACCEPTANCE_PENDING"
    finally:
        if held is not None:
            held.close()
    assert env["git"]("rev-parse", "HEAD", root=env["runtime"]) == env["old"]
    if not failure.endswith("drift"):
        assert not any(op == "bootout" for op, _ in env["runner"].calls)
    assert not transaction._source_locks


@pytest.mark.parametrize("owner", ["venv", "cwd", "both", "alias"])
def test_source_transition_module_helper_inventory(source_transition_env: dict, owner: str) -> None:
    """未知 python -m helper 即使不含 /scripts 也必須在 mutation 前拒絕。"""
    env = source_transition_env
    label = "local.top10-module-helper"
    root = env["runtime"]
    if owner == "alias":
        root = root.parent / "module-helper-alias"
        root.symlink_to(env["runtime"], target_is_directory=True)
    env["runner"].states[label] = dict(loaded=True, running=False, root=root, disabled=False)
    transaction = env["build"]()
    original = transaction.command_runner

    def run(command):
        if list(command[1:]) == ["print", f"gui/999/{label}"]:
            program = root / ".venv/bin/python" if owner != "cwd" else Path("/usr/bin/python3")
            cwd = f"working directory = {root}\n" if owner != "venv" else ""
            return activation.CommandResult(0, f"service = {{\nstate = waiting\nprogram = {program}\n"
                                             f"arguments = {{\n{program}\n-m\nhelper\n}}\n{cwd}}}\n")
        return original(command)

    transaction.command_runner = run
    assert transaction.run() != "ACTIVATED_PARTIAL_ACCEPTANCE_PENDING"
    assert "live same-root job" in transaction.failure
    assert env["git"]("rev-parse", "HEAD", root=env["runtime"]) == env["old"]
    assert not any(op == "bootout" for op, _ in env["runner"].calls)


def test_source_transition_real_git_alias_sibling(source_transition_env: dict) -> None:
    """真 symlink alias sibling 必須先卸載，hold 與 plist bytes 全程保留。"""
    env = source_transition_env
    alias = env["runtime"].parent / "legacy-runtime-alias"
    alias.symlink_to(env["runtime"], target_is_directory=True)
    label = "com.new-top10.external-review-preflight"
    path = env["agents"] / f"{label}.plist"
    # 不呼叫會 resolve root 的 fixture renderer，保留真實 alias argv。
    path.write_text((PROJECT_ROOT / "scripts/com.new-top10.external-review-preflight.plist")
                    .read_text().replace("__PROJECT_DIR__", str(alias)))
    before = path.read_bytes()
    transaction = env["build"]()
    assert transaction.run() == "ACTIVATED_PARTIAL_ACCEPTANCE_PENDING"
    assert label in transaction.source_jobs
    assert ("bootout", label) in env["runner"].calls
    assert ("bootstrap", label) in env["runner"].calls
    assert env["git"]("rev-parse", "HEAD", root=env["runtime"]) == env["accepted"]
    assert env["runner"].states == env["before"]
    assert env["hold"].read_bytes() == env["hold_bytes"]
    assert path.read_bytes() == before
    assert not any(op in {"enable", "disable", "kickstart"} for op, _ in env["runner"].calls)
    assert all(label not in {"com.new-top10.retrain", "com.new-top10.fog-research-worker"}
               for op, label in env["runner"].calls if op in {"bootout", "bootstrap"})


@pytest.mark.parametrize("event", ["after_source_bootout", "after_source_quiesce",
                                  "after_source_checkout", "after_bootstrap",
                                  "after_source_teardown"])
def test_source_transition_real_git_failure(source_transition_env: dict, event: str) -> None:
    env = source_transition_env
    injected = False

    def hook(actual, job):
        nonlocal injected
        if actual == event and not injected:
            injected = True
            raise activation.ActivationError("fixture source failure")

    transaction = env["build"](fault_hook=hook)
    assert transaction.run() == "ROLLED_BACK_NO_GO"
    assert injected
    _assert_source_old(env)
    assert not transaction._source_locks


@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM])
@pytest.mark.parametrize("event", ["after_source_bootout", "after_source_checkout", "after_bootstrap", "after_source_teardown"])
def test_source_transition_real_git_signal(source_transition_env: dict, event: str, signum: int) -> None:
    """真 OS signal 送進既有 handler，checkout 前後均需退回 old。"""
    env = source_transition_env
    injected = False
    handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}

    def hook(actual, job):
        nonlocal injected
        if actual == event and not injected:
            injected = True
            os.kill(os.getpid(), signum)

    transaction = env["build"](fault_hook=hook)
    assert transaction.run() == "ROLLED_BACK_NO_GO"
    assert injected
    _assert_source_old(env)
    assert {sig: signal.getsignal(sig) for sig in handlers} == handlers


@pytest.mark.parametrize("failure", ["seal", "durability", "teardown", "post_seal_signal"])
def test_source_transition_real_git_terminal_failure(source_transition_env: dict, monkeypatch, failure: str) -> None:
    env = source_transition_env
    transaction = env["build"]()
    commit = transaction._commit_receipt
    disarm = transaction._disarm
    injected = False

    def fail_commit(staged):
        nonlocal injected
        if not injected:
            injected = True
            if failure == "seal":
                raise OSError("fixture seal failed")
            commit(staged)
            if failure == "durability":
                raise activation.ReceiptDurabilityError("fixture post-rename failure")
            os.kill(os.getpid(), signal.SIGTERM)
            return
        commit(staged)

    def fail_disarm():
        nonlocal injected
        if not injected:
            injected = True
            return False
        return disarm()

    if failure == "teardown":
        monkeypatch.setattr(transaction, "_disarm", fail_disarm)
    else:
        monkeypatch.setattr(transaction, "_commit_receipt", fail_commit)
    assert transaction.run() == "ROLLED_BACK_NO_GO"
    assert injected
    _assert_source_old(env)
    assert not transaction._source_locks


@pytest.mark.parametrize("failure", ["dirty", "dependency", "running", "missing_receipt", "guard_lock", "ignored_collision"])
def test_source_transition_real_git_admission(source_transition_env: dict, failure: str) -> None:
    env = source_transition_env
    held = None
    if failure == "dirty":
        (env["runtime"] / "code.txt").write_text("unique dirty source\n")
    elif failure == "dependency":
        (env["source"] / "uv.lock").write_text("changed dependency\n")
        env["git"]("commit", "-am", "fixture dependency drift")
    elif failure == "running":
        env["runner"].states["com.new-top10.external-review-preflight"]["running"] = True
    elif failure == "missing_receipt":
        (env["runtime"] / "logs/storage_safety/daily_latest.json").unlink()
    elif failure == "guard_lock":
        import fcntl
        held = (env["runtime"] / "logs/storage_safety/daily.lock").open("a+")
        fcntl.flock(held.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    else:
        (env["source"] / "ignored-collision").write_text("new tracked file\n")
        env["git"]("add", "-f", "ignored-collision")
        env["git"]("commit", "-m", "fixture ignored collision")
        (env["runtime"] / "ignored-collision").write_text("unique ignored bytes\n")
    transaction = env["build"]()
    if failure in {"dependency", "ignored_collision"}:
        transaction.accepted_commit = env["git"]("rev-parse", "HEAD")
    try:
        assert transaction.run() != "ACTIVATED_PARTIAL_ACCEPTANCE_PENDING"
    finally:
        if held is not None:
            held.close()
    assert env["git"]("rev-parse", "HEAD", root=env["runtime"]) == env["old"]
    if failure != "ignored_collision":
        assert not any(op == "bootout" for op, _ in env["runner"].calls)
    else:
        assert (env["runtime"] / "ignored-collision").read_text() == "unique ignored bytes\n"
        assert all(not env["runner"].states[label]["loaded"] for label in transaction.source_jobs)
    assert env["hold"].read_bytes() == env["hold_bytes"]


def test_source_transition_real_git_release_failure(source_transition_env: dict, monkeypatch) -> None:
    """Seal 後 lock cleanup 失敗也必須先卸載／退 source，不能只回 nonzero。"""
    env = source_transition_env
    transaction = env["build"]()

    def fail_release():
        raise OSError("fixture release failure")

    monkeypatch.setattr(transaction, "_release_all_denial_locks", fail_release)
    assert transaction.run() == "ROLLED_BACK_NO_GO"
    _assert_source_old(env)
    assert not transaction._source_locks


def test_source_transition_real_git_unloaded_disabled_sibling(source_transition_env: dict) -> None:
    env = source_transition_env
    label = "com.new-top10.external-review-preflight"
    env["runner"].states[label].update(loaded=False, disabled=True)
    env["runner"].print_disabled_style = "explicit"
    transaction = env["build"]()
    assert transaction.run() == "ACTIVATED_PARTIAL_ACCEPTANCE_PENDING"
    assert env["runner"].states[label]["loaded"] is False
    assert env["runner"].states[label]["disabled"] is True
    assert ("bootstrap", label) not in env["runner"].calls
    assert env["hold"].read_bytes() == env["hold_bytes"]


@pytest.mark.parametrize("failure", ["no_pg", "missing_live_plist", "unresolved_claim", "live_owner_drift", "other_label_alias"])
def test_source_transition_real_git_inventory_evidence(source_transition_env: dict, failure: str) -> None:
    env = source_transition_env
    if failure == "no_pg":
        (env["runtime"] / "logs/storage_safety/daily_latest.json").write_text(json.dumps({
            "job": "daily", "status": "OVERLAP_BLOCKED", "child_spawned": False,
            "process_group_identity": None,
        }))
    elif failure == "missing_live_plist":
        env["runner"].states["com.new-top10.fog-research-worker"]["root"] = env["runtime"]
    elif failure == "live_owner_drift":
        env["runner"].states["com.new-top10.external-review-preflight"]["root"] = env["runtime"].parent / "other-runtime"
    elif failure == "other_label_alias":
        alias = env["runtime"].parent / "unknown-helper-alias"
        alias.symlink_to(env["runtime"], target_is_directory=True)
        env["runner"].states["local.top10-helper"] = dict(
            loaded=True, running=False, root=alias, disabled=False,
        )
    else:
        archive = env["runtime"] / "logs/storage_safety/receipts/daily/unfinished.json"
        archive.parent.mkdir(parents=True)
        archive.write_text('{"schema_version":"top10-storage-invocation-claim.v1"}')
    transaction = env["build"]()
    assert transaction.run() != "ACTIVATED_PARTIAL_ACCEPTANCE_PENDING"
    assert env["git"]("rev-parse", "HEAD", root=env["runtime"]) == env["old"]
    assert not any(op == "bootout" for op, _ in env["runner"].calls)


def test_source_transition_real_git_persistent_mask_failure(source_transition_env: dict, monkeypatch) -> None:
    """Seal 後 SIG_BLOCK 持續壞掉也不得短路卸載／source 回退。"""
    env = source_transition_env
    transaction = env["build"]()
    original = signal.pthread_sigmask

    def fail_block(how, mask):
        if transaction._receipt_sealed and how == signal.SIG_BLOCK and mask:
            raise OSError("fixture persistent SIG_BLOCK failure")
        return original(how, mask)

    try:
        with monkeypatch.context() as patch:
            patch.setattr(signal, "pthread_sigmask", fail_block)
            assert transaction.run() == "ROLLED_BACK_NO_GO"
        _assert_source_old(env)
        assert "signal teardown still failed" in transaction.failure
        assert not transaction._source_locks
    finally:
        # 模擬 syscall 恢復後只還原測試程序的原 handler/mask，不補做 activation。
        transaction._disarm()


@pytest.mark.parametrize("deny_checkout", [1, 2])
def test_source_transition_real_git_volume_recheck(source_transition_env: dict, monkeypatch, deny_checkout: int) -> None:
    from contextlib import contextmanager
    from scripts.storage_validation import boundary

    env = source_transition_env
    original = boundary.external_paths
    calls = []

    @contextmanager
    def checked(*paths, **kwargs):
        calls.append(paths)
        if len(calls) == deny_checkout:
            raise ValueError("fixture external UUID/device changed")
        with original(*paths, **kwargs) as cache:
            yield cache

    def hook(event, job):
        if deny_checkout == 2 and event == "after_bootstrap":
            raise activation.ActivationError("fixture rollback volume recheck")

    monkeypatch.setattr(boundary, "external_paths", checked)
    transaction = env["build"](fault_hook=hook)
    assert transaction.run() == "ROLLBACK_VERIFICATION_FAILED"
    assert len(calls) == deny_checkout
    assert calls == [(env["runtime"],)] * deny_checkout
    expected = env["old"] if deny_checkout == 1 else env["accepted"]
    assert env["git"]("rev-parse", "HEAD", root=env["runtime"]) == expected
    assert all(not env["runner"].states[label]["loaded"] for label in transaction.source_jobs)


@pytest.mark.parametrize("failure", ["rollback_checkout", "live_pg", "new_marker"])
def test_source_transition_real_git_rollback_boundary(source_transition_env: dict, monkeypatch, failure: str) -> None:
    from dataclasses import asdict
    from app.storage_safety import _spawn_verified_process_group

    env = source_transition_env
    child = None
    transaction = env["build"]()
    source_git = transaction._source_git

    def git(*args):
        if failure == "rollback_checkout" and args[0] == "checkout" and args[-1] == env["old"]:
            raise activation.ActivationError("fixture rollback checkout failure")
        return source_git(*args)

    def hook(event, job):
        nonlocal child
        if event == "after_bootstrap" and job == "daily":
            if failure == "live_pg":
                child, identity = _spawn_verified_process_group(
                    [sys.executable, "-B", "-c", "import time; time.sleep(60)"], cwd=env["runtime"],
                )
                (env["runtime"] / "logs/storage_safety/daily_latest.json").write_text(json.dumps({
                    "job": "daily", "child_spawned": True, "process_group_identity": asdict(identity),
                }))
            elif failure == "new_marker":
                (env["runtime"] / "logs/storage_safety/restart_denied/daily.json").write_text("new failure evidence\n")
            raise activation.ActivationError("fixture rollback boundary")

    monkeypatch.setattr(transaction, "_source_git", git)
    transaction.fault_hook = hook
    try:
        status = transaction.run()
        if failure == "new_marker":
            assert status == "ROLLED_BACK_NO_GO"
            _assert_source_old(env)
            assert (env["runtime"] / "logs/storage_safety/restart_denied/daily.json").read_text() == "new failure evidence\n"
        else:
            assert status == "ROLLBACK_VERIFICATION_FAILED"
            assert env["git"]("rev-parse", "HEAD", root=env["runtime"]) == env["accepted"]
            assert all(not env["runner"].states[label]["loaded"] for label in transaction.source_jobs)
    finally:
        if child is not None:
            child.terminate()
            child.wait(timeout=5)
            child.stdout.close()
