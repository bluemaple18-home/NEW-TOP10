"""驗證 production runtime checkout 與 active development checkout 的隔離契約。"""

from __future__ import annotations

import subprocess
import shutil
import json
import sys
from pathlib import Path

import pytest

from app.storage_safety import project_write_snapshot, unknown_changed_paths
from scripts.validate_runtime_checkout import (
    RuntimeCheckoutError,
    validate_runtime_checkout,
)
from scripts import activate_automation_runtime as activation
from scripts import prepare_runtime_checkout as prepare
from tests.test_storage_lifecycle_boundaries import runtime_fixture, tmp_path
from tests.test_automation_runtime_activation import FakeCommandRunner, _render_template


REGISTERED_WRITES = ("logs", "artifacts", "data", "models")


@pytest.mark.parametrize("case", ["valid", "valid_outputs", "unknown_source", "missing_environment", "dependency_drift", "wrong_link"])
def test_prepared_runtime_reaches_activation_validation_without_launchd(runtime_fixture, monkeypatch, case):
    """沿真實 prepare→validator 驗環境連結與依賴；在任何 scheduler 操作前停止。"""
    source, runtime, commit, environment = runtime_fixture
    prepare.prepare_runtime(*runtime_fixture)
    if case == "valid_outputs":
        for name in ("data/reference", "logs", "models", "artifacts"):
            folder = runtime / name
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "fixture.txt").write_text("runtime-owned\n")
    elif case == "unknown_source":
        (runtime / "rogue.py").write_text("pass\n")
    if case == "dependency_drift":
        (source / "uv.lock").write_text("drift\n")
    elif case == "wrong_link":
        (runtime / ".venv").unlink()
        (runtime / ".venv").symlink_to(source)
    transaction = activation.ActivationTransaction(
        source_root=source, runtime_root=runtime, accepted_commit=commit,
        environment_root=None if case == "missing_environment" else environment,
        launch_agents_dir=source.parent / "absent-launchagents",
        expected_old_root=source, receipt_path=source.parent / "activation.json",
        target_jobs=("external-review-preflight",),
        command_runner=lambda command: pytest.fail(f"不得呼叫 launchd: {command}"),
    )
    reason = {"valid": "LaunchAgents 目錄不存在", "valid_outputs": "LaunchAgents 目錄不存在", "unknown_source": "非 runtime-owned", "missing_environment": "environment_root",
              "dependency_drift": "環境 uv.lock", "wrong_link": "非 runtime-owned"}[case]
    with pytest.raises((activation.ActivationError, ValueError, RuntimeCheckoutError), match=reason):
        transaction._prepare()
    if case in {"valid", "valid_outputs"}:
        assert transaction.canonical_commit == commit
    assert not transaction.receipt_path.exists()


def test_activation_cli_accepts_explicit_environment_root(monkeypatch):
    monkeypatch.setattr("sys.argv", ["activate", "--runtime-root", "/runtime", "--accepted-commit", "a" * 40,
        "--expected-old-root", "/old", "--receipt", "/receipt", "--environment-root", "/environment/.venv"])
    assert activation.parse_args().environment_root == Path("/environment/.venv")


def test_prepared_daily_with_market_data_and_logs_passes_precheck(runtime_fixture):
    """真實 prepare 與依賴驗證接上 Daily reference；僅 fake probe，不呼叫 launchd。"""
    source, runtime, _, environment = runtime_fixture
    scripts = source / "scripts"
    scripts.mkdir()
    project = Path(__file__).resolve().parents[1]
    for name in ("com.new-top10.daily.plist", "daily_market_reference.py"):
        shutil.copy2(project / "scripts" / name, scripts / name)
    (source / "config").mkdir()
    (source / "config/automation.yaml").write_text(
        "daily:\n  market_coverage_enabled: true\n  required_market_types: [twse, tpex]\n")
    prepare.git(source, "add", "scripts", "config")
    prepare.git(source, "commit", "-m", "daily fixture")
    commit = prepare.git(source, "rev-parse", "HEAD")
    prepare.prepare_runtime(source, runtime, commit, environment)
    reference = runtime / "data/reference/tradable_universe.csv"
    reference.parent.mkdir(parents=True)
    reference.write_text("stock_id,market_type\n2330,twse\n6488,tpex\n")
    (runtime / "logs").mkdir()
    (runtime / "logs/existing.log").write_text("既有 Daily log\n")
    agents = source.parent / "LaunchAgents"
    agents.mkdir()
    (agents / "com.new-top10.daily.plist").write_bytes(_render_template("com.new-top10.daily.plist", source))
    runner = FakeCommandRunner(source)
    transaction = activation.ActivationTransaction(
        source_root=source, runtime_root=runtime, accepted_commit=commit,
        environment_root=environment, launch_agents_dir=agents,
        expected_old_root=source, receipt_path=source.parent / "daily-receipt.json",
        target_jobs=("daily",), command_runner=runner,
    )
    try:
        transaction._prepare()
        assert transaction.canonical_commit == commit
        assert [job.guard_name for job in transaction.jobs] == ["daily"]
        assert all(op not in {"bootout", "bootstrap", "enable", "disable", "kickstart"} for op, _ in runner.calls)
    finally:
        transaction._release_all_denial_locks()
    assert reference.read_text().endswith("6488,tpex\n")
    assert (runtime / "logs/existing.log").read_text() == "既有 Daily log\n"


def test_standalone_cli_validates_prepared_environment_from_external_cwd(runtime_fixture):
    """直接跑原 CLI；隔離 sys.path 與 cwd，確認環境驗證先於缺 LaunchAgents 的預期早退。"""
    source, runtime, _, environment = runtime_fixture
    project = Path(__file__).resolve().parents[1]
    for relative in ("scripts/activate_automation_runtime.py", "scripts/prepare_runtime_checkout.py",
                     "scripts/validate_runtime_checkout.py", "scripts/storage_validation/boundary.py"):
        target = source / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(project / relative, target)
    prepare.git(source, "add", "scripts")
    prepare.git(source, "commit", "-m", "standalone CLI fixture")
    commit = prepare.git(source, "rev-parse", "HEAD")
    prepare.prepare_runtime(source, runtime, commit, environment)
    receipt = source.parent / "standalone-activation.json"
    script = source / "scripts/activate_automation_runtime.py"
    completed = subprocess.run([
        sys.executable, "-I", "-B", str(script), "--activate",
        "--runtime-root", str(runtime), "--accepted-commit", commit,
        "--environment-root", str(environment), "--expected-old-root", str(source),
        "--receipt", str(receipt), "--launch-agents-dir", str(source.parent / "absent-agents"),
        "--job", "external-review-preflight",
    ], cwd=source.parent, capture_output=True, text=True, check=False)
    assert completed.returncode == 75, completed.stdout + completed.stderr
    payload = json.loads(receipt.read_text())
    assert payload["status"] == "PRECHECK_FAILED"
    assert "LaunchAgents 目錄不存在" in payload["failure"], payload


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
        capture_output=True,
        check=True,
    )
    return completed.stdout.strip()


def _linked_worktrees(tmp_path: Path) -> tuple[Path, Path, str]:
    source = tmp_path / "source"
    runtime = tmp_path / "runtime"
    source.mkdir()
    _git(source, "init", "-b", "main")
    _git(source, "config", "user.email", "top10-test@example.invalid")
    _git(source, "config", "user.name", "TOP10 Test")
    (source / "app").mkdir()
    (source / "app" / "runtime.txt").write_text("pinned\n", encoding="utf-8")
    _git(source, "add", "app/runtime.txt")
    _git(source, "commit", "-m", "fixture")
    head = _git(source, "rev-parse", "HEAD")
    _git(source, "worktree", "add", "--detach", str(runtime), head)
    return source, runtime, head


def test_runtime_checkout_requires_same_repo_detached_exact_commit(tmp_path: Path) -> None:
    source, runtime, head = _linked_worktrees(tmp_path)

    assert validate_runtime_checkout(source, runtime, head) == head


def test_runtime_checkout_rejects_wrong_pinned_commit(tmp_path: Path) -> None:
    source, runtime, head = _linked_worktrees(tmp_path)
    (source / "app" / "runtime.txt").write_text("next\n", encoding="utf-8")
    _git(source, "add", "app/runtime.txt")
    _git(source, "commit", "-m", "next")
    newer_head = _git(source, "rev-parse", "HEAD")
    assert newer_head != head

    with pytest.raises(RuntimeCheckoutError, match="未 pin 到 accepted commit"):
        validate_runtime_checkout(source, runtime, newer_head)


def test_runtime_checkout_rejects_branch_head(tmp_path: Path) -> None:
    source, runtime, head = _linked_worktrees(tmp_path)
    _git(runtime, "switch", "-c", "runtime-drift")

    with pytest.raises(RuntimeCheckoutError, match="detached HEAD"):
        validate_runtime_checkout(source, runtime, head)


def test_runtime_checkout_rejects_non_runtime_owned_dirty_path(tmp_path: Path) -> None:
    source, runtime, head = _linked_worktrees(tmp_path)
    (runtime / "docs").mkdir()
    (runtime / "docs" / "rogue.md").write_text("rogue\n", encoding="utf-8")

    with pytest.raises(RuntimeCheckoutError, match="非 runtime-owned 變更"):
        validate_runtime_checkout(source, runtime, head)


def test_runtime_checkout_allows_runtime_owned_outputs(tmp_path: Path) -> None:
    source, runtime, head = _linked_worktrees(tmp_path)
    (runtime / "artifacts").mkdir()
    (runtime / "artifacts" / "receipt.json").write_text("{}\n", encoding="utf-8")

    assert validate_runtime_checkout(source, runtime, head) == head


def test_dev_worktree_write_is_invisible_but_runtime_rogue_write_fails_closed(
    tmp_path: Path,
) -> None:
    source, runtime, _head = _linked_worktrees(tmp_path)
    before = project_write_snapshot(runtime)

    (source / "docs").mkdir()
    (source / "docs" / "mainline-task.md").write_text("dev mutation\n", encoding="utf-8")
    after_dev_write = project_write_snapshot(runtime)
    assert unknown_changed_paths(before, after_dev_write, REGISTERED_WRITES) == ()

    (runtime / "docs").mkdir()
    (runtime / "docs" / "runtime-rogue.md").write_text("runtime mutation\n", encoding="utf-8")
    after_runtime_write = project_write_snapshot(runtime)
    assert unknown_changed_paths(
        before,
        after_runtime_write,
        REGISTERED_WRITES,
    ) == ("docs/runtime-rogue.md",)
