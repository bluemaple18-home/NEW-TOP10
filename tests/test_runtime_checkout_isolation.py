"""驗證 production runtime checkout 與 active development checkout 的隔離契約。"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from app.storage_safety import project_write_snapshot, unknown_changed_paths
from scripts.validate_runtime_checkout import (
    RuntimeCheckoutError,
    validate_runtime_checkout,
)


REGISTERED_WRITES = ("logs", "artifacts", "data", "models")


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
