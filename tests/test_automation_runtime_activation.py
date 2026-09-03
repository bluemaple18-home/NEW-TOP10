"""A4 三條核心 launchd transaction 的 failure-state regression。"""

from __future__ import annotations

import json
import os
import plistlib
import shutil
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
    assert transaction.run() == "PRECHECK_FAILED"

    assert not any(operation == "bootout" for operation, _ in runner.calls)
    assert _target_bytes(activation_env) == before
    assert not list(launch_agents.glob(".*.a4-stage-*.plist"))
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
