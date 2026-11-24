#!/usr/bin/env python3
"""建立外接程式碼 worktree 並重用既有環境；不安裝套件或啟用服務。"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
import signal
from pathlib import Path
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.storage_validation.boundary import external_paths, readonly_source
from scripts.validate_runtime_checkout import FULL_SHA_PATTERN, validate_runtime_checkout

EXCLUDED = ("data", "models", "artifacts", "archive", ".venv")
DEPENDENCIES = ("uv.lock", "pyproject.toml")


@contextmanager
def record_side_effect():
    """只在 mkdir/link 與記錄 ownership 的極短區間延後訊號。"""
    previous = signal.pthread_sigmask(signal.SIG_BLOCK, (signal.SIGTERM, signal.SIGINT))
    try:
        yield
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, previous)


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True,
                                   env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"}).strip()


def dependency_contract(source: Path, commit: str, environment: Path) -> dict[str, str]:
    """既有環境由 operator 明示；其所屬 checkout 的依賴檔須等於 accepted commit。"""
    if not environment.is_dir() or not (environment / "pyvenv.cfg").is_file():
        raise ValueError("需明示既有外接 .venv；不會執行 uv sync")
    if environment.name != ".venv" or not os.access(environment / "bin/python", os.X_OK):
        raise ValueError("可重用環境須為所屬 Git checkout 的 .venv")
    owner = environment.parent
    if Path(git(owner, "rev-parse", "--show-toplevel")) != owner:
        raise ValueError("環境必須具有明確 Git checkout 依賴契約")
    result = {}
    for name in DEPENDENCIES:
        expected = subprocess.check_output(["git", "-C", str(source), "show", f"{commit}:{name}"])
        path = owner / name
        if path.is_symlink() or not path.is_file() or path.read_bytes() != expected:
            raise ValueError(f"環境 {name} 與 accepted commit 不同")
        if git(owner, "status", "--porcelain", "--", name):
            raise ValueError(f"環境 {name} 有未提交修改")
        result[name] = hashlib.sha256(expected).hexdigest()
    return result


def clean_code(root: Path, environment: Path, *, linked: bool) -> None:
    """包含 ignored 檔檢查；唯一例外是本入口的環境連結。"""
    if git(root, "diff", "HEAD", "--name-only"):
        raise ValueError("runtime checkout dirty，保留 unique 工作")
    others = git(root, "ls-files", "--others", "--exclude-standard").splitlines()
    ignored = git(root, "ls-files", "--others", "--ignored", "--exclude-standard").splitlines()
    if any(name != ".venv" for name in (*others, *ignored)):
        raise ValueError("runtime 含未知或 ignored 工作，禁止覆寫或清理")
    for name in EXCLUDED:
        path = root / name
        if name == ".venv" and linked:
            if not path.is_symlink() or path.resolve(strict=True) != environment:
                raise ValueError("runtime .venv 必須連至明示的外接環境")
        elif path.exists() or path.is_symlink():
            raise ValueError(f"runtime 不得複製 {name}")


def validate_runtime_environment(source: Path, runtime: Path, commit: str, environment: Path) -> dict:
    """重驗 runtime 與既有環境依賴；保留 validator 原有 runtime-owned 輸出契約。"""
    source = readonly_source(source)
    with external_paths(runtime, environment):
        canonical = validate_runtime_checkout(source, runtime, commit, environment_root=environment)
        contract = dependency_contract(source, canonical, environment)
        if not (runtime / ".venv").is_symlink() or (runtime / ".venv").resolve(strict=True) != environment:
            raise ValueError("runtime .venv 必須連至明示的外接環境")
        for name in DEPENDENCIES:
            path = runtime / name
            if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != contract[name]:
                raise ValueError(f"runtime {name} 契約不符")
    return {"commit": canonical, "runtime_root": str(runtime),
            "environment_root": str(environment), "dependency_sha256": contract}


def validate_prepared_runtime(source: Path, runtime: Path, commit: str, environment: Path) -> dict:
    result = validate_runtime_environment(source, runtime, commit, environment)
    with external_paths(runtime, environment):
        clean_code(runtime, environment, linked=True)
    return result


def prepare_runtime(source: Path, runtime: Path, commit: str, environment: Path) -> dict:
    if not FULL_SHA_PATTERN.fullmatch(commit):
        raise ValueError("accepted commit 必須是完整 40 字元 SHA")
    source = readonly_source(source)
    if runtime == source or runtime.is_relative_to(source) or source.is_relative_to(runtime):
        raise ValueError("runtime 與 source 不得重疊")
    if environment.is_relative_to(runtime):
        raise ValueError("環境必須位於 runtime 外部，不得自建環境")
    with external_paths(runtime, environment) as cache:
        canonical = git(source, "rev-parse", "--verify", f"{commit}^{{commit}}")
        dependency_contract(source, canonical, environment)
        if runtime.exists():
            result = validate_prepared_runtime(source, runtime, canonical, environment)
            return {**result, "reused": True}
        if not runtime.parent.is_dir():
            raise ValueError("runtime 父目錄須已存在於外接卷")
        # 以 Git tree 實際程式碼 bytes 准入，避免把 data/model blob checkout 出來。
        tree = git(source, "ls-tree", "-rl", canonical)
        code_bytes = 0
        for line in tree.splitlines():
            meta, name = line.split("\t", 1)
            if Path(name).parts[0] not in EXCLUDED:
                size = meta.split()[-1]
                if size.isdigit():
                    code_bytes += int(size)
        # exact-root child 沿 parent admission，不另取 child 容量控制權。
        with external_paths(runtime, environment, reserve_bytes=code_bytes + 1024**2):
            pass
        created = False
        linked = False
        identity = None

        @contextmanager
        def owned_runtime():
            """每個 writer 前重驗 lexical 外接邊界與本輪原 inode，不追隨替代路徑。"""
            with external_paths(runtime, environment):
                current = runtime.lstat()
                if identity is None or identity != (current.st_dev, current.st_ino):
                    raise ValueError("本輪 worktree inode 已改變，保留")
                yield

        try:
            with external_paths(runtime, environment):
                with record_side_effect():
                    runtime.mkdir()
                    created = True
                    stat = runtime.stat()
                    identity = (stat.st_dev, stat.st_ino)
            with owned_runtime():
                git(source, "worktree", "add", "--detach", "--no-checkout", str(runtime), canonical)
            with owned_runtime():
                git(runtime, "sparse-checkout", "set", "--no-cone", "/*", *(f"!/{name}/" for name in EXCLUDED))
            with owned_runtime():
                git(runtime, "checkout", "--detach", canonical)
            clean_code(runtime, environment, linked=False)
            with owned_runtime():
                with record_side_effect():
                    (runtime / ".venv").symlink_to(environment, target_is_directory=True)
                    linked = True
            with owned_runtime():
                result = validate_prepared_runtime(source, runtime, canonical, environment)
            return {**result, "reused": False}
        except BaseException:
            # 只撤回本輪 inode；未 checkout 空殼與已 checkout 內容分開核對。
            if created:
                try:
                    with owned_runtime():
                        entries = {path.name for path in runtime.iterdir()}
                        if not entries:
                            with owned_runtime():
                                runtime.rmdir()
                        elif entries == {".git"} and (runtime / ".git").is_file() and not (runtime / ".git").is_symlink():
                            if (git(runtime, "rev-parse", "HEAD") != canonical or
                                    git(runtime, "rev-parse", "--path-format=absolute", "--git-common-dir") !=
                                    git(source, "rev-parse", "--path-format=absolute", "--git-common-dir")):
                                raise ValueError("未 checkout 空殼的 Git 身分不符")
                            # 工作檔消失不代表沒有 unique staged 工作；未知 index 一律保留。
                            index = Path(git(runtime, "rev-parse", "--path-format=absolute", "--git-path", "index"))
                            with owned_runtime():
                                for candidate in (index, index.with_name(index.name + ".lock")):
                                    if candidate.exists() or candidate.is_symlink():
                                        raise ValueError("空殼含未知 index 或 index.lock，保留 staged 工作")
                                git(source, "worktree", "remove", "--force", str(runtime))
                        else:
                            validate_runtime_checkout(source, runtime, canonical,
                                                      environment_root=environment if linked else None)
                            clean_code(runtime, environment, linked=linked)
                            if linked:
                                with owned_runtime():
                                    (runtime / ".venv").unlink()
                            with owned_runtime():
                                git(source, "worktree", "remove", str(runtime))
                except Exception as cleanup_error:
                    print(f"KEEP_UNIQUE: {runtime}: {cleanup_error}", file=sys.stderr)
            raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--accepted-commit", required=True)
    parser.add_argument("--environment-root", type=Path, required=True)
    args = parser.parse_args(argv)
    def interrupted(signum, _frame):
        raise SystemExit(128 + signum)

    previous = signal.signal(signal.SIGTERM, interrupted)
    try:
        result = prepare_runtime(args.source_root, args.runtime_root, args.accepted_commit, args.environment_root)
    except Exception as error:
        print(f"RUNTIME_PREPARE_NO_GO: {error}", file=sys.stderr)
        return 64
    finally:
        signal.signal(signal.SIGTERM, previous)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    raise SystemExit(main())
