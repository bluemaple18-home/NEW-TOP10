#!/usr/bin/env python3
"""驗證 launchd 專用 runtime checkout 與開發 checkout 已隔離。"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


FULL_SHA_PATTERN = re.compile(r"^[0-9a-fA-F]{40}$")
RUNTIME_MUTABLE_ROOTS = ("logs", "artifacts", "data", "models")


class RuntimeCheckoutError(RuntimeError):
    """runtime checkout 不符合 production isolation contract。"""


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
        capture_output=True,
        check=check,
    )


def _repo_root(root: Path) -> Path:
    completed = _git(root, "rev-parse", "--show-toplevel")
    return Path(completed.stdout.strip()).resolve()


def _git_common_dir(root: Path) -> Path:
    completed = _git(root, "rev-parse", "--path-format=absolute", "--git-common-dir")
    return Path(completed.stdout.strip()).resolve()


def _is_runtime_mutable(relative: str) -> bool:
    parts = Path(relative).parts
    return bool(parts) and parts[0] in RUNTIME_MUTABLE_ROOTS


def validate_runtime_checkout(
    source_root: Path,
    runtime_root: Path,
    accepted_commit: str,
) -> str:
    """回傳 canonical commit；不符合隔離或 pinning 契約時 fail closed。"""

    source_root = source_root.resolve()
    runtime_root = runtime_root.resolve()
    if runtime_root == source_root:
        raise RuntimeCheckoutError("runtime checkout 不得與開發 checkout 相同")
    if not FULL_SHA_PATTERN.fullmatch(accepted_commit):
        raise RuntimeCheckoutError("TOP10_RUNTIME_COMMIT 必須是完整 40 字元 commit SHA")
    if not runtime_root.is_dir():
        raise RuntimeCheckoutError("runtime checkout 不存在；請先以 git worktree add --detach 建立")

    try:
        if _repo_root(source_root) != source_root:
            raise RuntimeCheckoutError("source root 必須是 Git working tree 根目錄")
        if _repo_root(runtime_root) != runtime_root:
            raise RuntimeCheckoutError("runtime root 必須是 Git working tree 根目錄")
        if _git_common_dir(source_root) != _git_common_dir(runtime_root):
            raise RuntimeCheckoutError("runtime checkout 必須是同一 canonical repo 的 linked worktree")
        canonical_commit = _git(
            source_root,
            "rev-parse",
            "--verify",
            f"{accepted_commit}^{{commit}}",
        ).stdout.strip()
        runtime_head = _git(runtime_root, "rev-parse", "HEAD").stdout.strip()
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout).strip()
        raise RuntimeCheckoutError(f"Git runtime checkout 驗證失敗: {detail}") from exc

    if runtime_head != canonical_commit:
        raise RuntimeCheckoutError(
            f"runtime HEAD 未 pin 到 accepted commit: expected={canonical_commit} actual={runtime_head}"
        )
    if _git(runtime_root, "symbolic-ref", "-q", "HEAD", check=False).returncode == 0:
        raise RuntimeCheckoutError("runtime checkout 必須使用 detached HEAD，避免 branch 漂移")

    changed = {
        item
        for item in _git(runtime_root, "diff", "HEAD", "--name-only").stdout.splitlines()
        if item
    }
    untracked = {
        item
        for item in _git(
            runtime_root,
            "ls-files",
            "--others",
            "--exclude-standard",
        ).stdout.splitlines()
        if item
    }
    unexpected = sorted(
        item for item in changed | untracked if not _is_runtime_mutable(item)
    )
    if unexpected:
        preview = ", ".join(unexpected[:8])
        raise RuntimeCheckoutError(f"runtime checkout 含非 runtime-owned 變更: {preview}")

    return canonical_commit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--accepted-commit", required=True)
    args = parser.parse_args()
    try:
        canonical_commit = validate_runtime_checkout(
            args.source_root,
            args.runtime_root,
            args.accepted_commit,
        )
    except RuntimeCheckoutError as exc:
        print(f"RUNTIME_CHECKOUT_NO_GO: {exc}", file=sys.stderr)
        return 64
    print(
        "RUNTIME_CHECKOUT_GO "
        f"runtime_root={args.runtime_root.resolve()} commit={canonical_commit}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
