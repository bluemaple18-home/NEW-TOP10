"""Repair 1 的 Git 副作用與有限診斷回歸；不重跑已阻塞的 native FOG probe。"""

import json
import os
from pathlib import Path
import subprocess

import pytest

from app import storage_safety as guard
from scripts import prepare_runtime_checkout as prepare
from tests.test_storage_lifecycle_boundaries import tmp_path, runtime_fixture
from tests.test_storage_safety import fixture_global_policy, fixture_job_policy


@pytest.mark.parametrize("index_state", ["staged", "empty-index", "index-lock"])
def test_shell_rollback_preserves_any_unknown_index(runtime_fixture, monkeypatch, index_state):
    source, runtime, commit, environment = runtime_fixture
    original = prepare.git

    def inject(root, *args):
        result = original(root, *args)
        if args[:2] == ("worktree", "add"):
            index = Path(original(runtime, "rev-parse", "--path-format=absolute", "--git-path", "index"))
            if index_state == "staged":
                unique = runtime / "unique.txt"
                unique.write_text("僅存在 index 的工作")
                original(runtime, "add", "unique.txt")
                unique.unlink()
            else:
                target = index if index_state == "empty-index" else index.with_name("index.lock")
                target.write_bytes(b"")
            raise RuntimeError("add 後注入失敗")
        return result

    monkeypatch.setattr(prepare, "git", inject)
    with pytest.raises(RuntimeError, match="注入失敗"):
        prepare.prepare_runtime(*runtime_fixture)
    assert {path.name for path in runtime.iterdir()} == {".git"}
    assert str(runtime) in original(source, "worktree", "list", "--porcelain")
    if index_state == "staged":
        assert original(runtime, "show", ":unique.txt") == "僅存在 index 的工作"


@pytest.mark.parametrize("phase", ["add", "sparse"])
@pytest.mark.parametrize("replacement", ["symlink", "inode"])
def test_next_git_writer_rejects_path_drift(runtime_fixture, monkeypatch, phase, replacement):
    source, runtime, commit, environment = runtime_fixture
    original = prepare.git
    held = runtime.with_name("held-original")
    writers = []
    before = {}

    def inject(root, *args):
        name = {("worktree", "add"): "add", ("sparse-checkout", "set"): "sparse"}.get(args[:2])
        if args and args[0] == "checkout":
            name = "checkout"
        if name:
            writers.append(name)
        result = original(root, *args)
        if name == phase:
            runtime.rename(held)
            if replacement == "symlink":
                runtime.symlink_to(held, target_is_directory=True)
            else:
                runtime.mkdir()
                (runtime / "unique.txt").write_text("替代 inode 的工作")
            before.update({p.name: p.read_bytes() for p in held.iterdir() if p.is_file()})
        return result

    monkeypatch.setattr(prepare, "git", inject)
    try:
        with pytest.raises(ValueError):
            prepare.prepare_runtime(*runtime_fixture)
        assert writers == (["add"] if phase == "add" else ["add", "sparse"])
        assert before == {p.name: p.read_bytes() for p in held.iterdir() if p.is_file()}
        if replacement == "inode":
            assert (runtime / "unique.txt").read_text() == "替代 inode 的工作"
    finally:
        if runtime.is_symlink():
            runtime.unlink()


@pytest.mark.parametrize("outcome", ["eperm", "timeout", "missing-allowed"])
def test_probe_failure_has_bounded_diagnostics_in_existing_receipt(tmp_path, monkeypatch, outcome):
    """只測診斷與既有失敗收據，不把故障注入當成原生隔離驗收。"""
    source, sandbox = tmp_path / "source", tmp_path / "sandbox"
    source.mkdir()
    sandbox.mkdir()
    calls = []
    original_run = guard.subprocess.run

    def rejected(command, **kwargs):
        if command[0] != str(guard.SANDBOX_EXECUTABLE):
            return original_run(command, **kwargs)
        calls.append(command)
        assert kwargs["timeout"] == 5
        kwargs["stdout"].write(b"o" * 10000)
        kwargs["stderr"].write(b"e" * 10000 + b"sandbox_apply: Operation not permitted\n")
        if outcome == "timeout":
            raise subprocess.TimeoutExpired(command, 5)
        return subprocess.CompletedProcess(command, 0 if outcome == "missing-allowed" else 71)

    with monkeypatch.context() as patch:
        patch.setattr(guard.subprocess, "run", rejected)
        with pytest.raises(RuntimeError, match="VALIDATION_CONFINEMENT_PROBE_FAILED") as caught:
            guard._validation_spawn_command(sandbox, source, ["/usr/bin/true"])
    assert len(calls) == 1
    failure = caught.value
    diagnostic = failure.validation_probe
    assert len(diagnostic["stdout_tail"].encode()) <= 4096
    assert len(diagnostic["stderr_tail"].encode()) <= 4096
    assert diagnostic["stderr_tail"].endswith("Operation not permitted\n")
    assert diagnostic["exit_code"] == {"eperm": 71, "timeout": None, "missing-allowed": 0}[outcome]
    assert diagnostic["timed_out"] == (outcome == "timeout")
    assert not diagnostic["allowed_write"] and not diagnostic["forbidden_write"]

    for key in tuple(os.environ):
        if key.startswith("AI_CORE_CACHE_") or key == "TOP10_EXTERNAL_CACHE_ROOT":
            monkeypatch.delenv(key)

    def failed_sample(_pid):
        raise failure

    result = guard.run_guarded_job(sandbox, fixture_global_policy(), fixture_job_policy(), (),
                                   ["/usr/bin/true"], sampler=failed_sample, external_cache_required=False)
    receipt = json.loads((sandbox / "logs/storage_safety/daily_latest.json").read_text())
    assert result == 70 and receipt["status"] == "STOPPED"
    assert receipt["child_exit_code"] is None
    assert receipt["internal_error"]["validation_probe"] == diagnostic
    evidence = Path(os.environ["TMP_ARTIFACT_ROOT"]) / "evidence" / f"probe-diagnostic-{outcome}.json"
    evidence.write_text(json.dumps({"evidence_type": "fault_injection_only", "receipt": receipt}, indent=2))
