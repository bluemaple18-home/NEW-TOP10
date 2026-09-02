#!/usr/bin/env python3
"""在 validation sandbox 內執行固定的 fog-research-worker 入口。"""

from __future__ import annotations

import hashlib
import hmac
import os
import stat
import sys
import tempfile
from pathlib import Path


RUNNER = Path("scripts/run_fog_research_worker.sh")
RUNTIME_ROOT = Path("logs/storage_safety/runtime/fog-research-worker")
MAX_RUNNER_BYTES = 1024 * 1024
FIXED_ENVIRONMENT = {
    "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
    "LANG": "C",
    "LC_ALL": "C",
    "TZ": "Asia/Taipei",
    "PYTHONDONTWRITEBYTECODE": "1",
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
    "TOP10_DAILY_PYTHON": ".venv/bin/python",
    "TOP10_FOG_RESEARCH_ENABLED": "1",
    "TOP10_FOG_RESEARCH_QUOTA": "5",
    "TOP10_RESEARCH_QUOTA": "5",
    "TOP10_FOG_RESEARCH_MAX_BATCHES": "6",
    "TOP10_FOG_RESEARCH_MAX_SECONDS": "7200",
    "TOP10_FOG_RESEARCH_BATCH_SLEEP_SECONDS": "30",
    "TOP10_FOG_RESEARCH_MAX_RETRIES": "1",
    "TOP10_FOG_RESEARCH_RETRY_BACKOFF_SECONDS": "0",
    "TOP10_FOG_RESEARCH_RECOVER_CIRCUIT": "0",
    "TOP10_RESEARCH_FROM_QUEUE": "0",
    # 代表性驗證不可因正式 queue 已消耗而退化成數秒空跑；只在 fresh sandbox 允許重跑。
    "TOP10_RESEARCH_ALLOW_RERUN": "1",
    "TOP10_REFRESH_RESEARCH_MAP": "1",
    "TOP10_REPLAY_DRAIN_ENABLED": "1",
    "TOP10_REPLAY_DRAIN_BATCH_SIZE": "24",
    "TOP10_REPLAY_DRAIN_MAX_BATCHES": "6",
    "TOP10_REPLAY_DRAIN_MAX_SECONDS": "7200",
}


def fail(message: str, code: int) -> None:
    print(f"fog validation entrypoint rejected: {message}", file=sys.stderr)
    raise SystemExit(code)


def read_verified_runner_bytes(sandbox: Path, expected_digest: str) -> bytes:
    """從固定目錄 FD 讀取 runner，後續只信任這份已驗證 bytes。"""

    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    root_fd = os.open(sandbox, directory_flags)
    scripts_fd = -1
    runner_fd = -1
    try:
        scripts_fd = os.open("scripts", directory_flags | nofollow, dir_fd=root_fd)
        runner_fd = os.open(RUNNER.name, os.O_RDONLY | nofollow, dir_fd=scripts_fd)
        metadata = os.fstat(runner_fd)
        if not stat.S_ISREG(metadata.st_mode):
            fail("fog runner 不是 regular file", 65)
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(runner_fd, min(65536, MAX_RUNNER_BYTES + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > MAX_RUNNER_BYTES:
                fail("fog runner 超過允許大小", 65)
        source = b"".join(chunks)
        if not hmac.compare_digest(hashlib.sha256(source).hexdigest(), expected_digest):
            fail("fog runner digest 不符", 65)
        return source
    except OSError:
        fail("fog runner 不存在、含 symlink 或無法安全開啟", 65)
    finally:
        for descriptor in (runner_fd, scripts_fd, root_fd):
            if descriptor >= 0:
                os.close(descriptor)


def materialize_verified_runner(runtime_root: Path, source: bytes) -> int:
    """建立無路徑、唯讀 FD；Bash 無法重新解析或改寫原 runner path。"""

    materialize_root = runtime_root / "tmp" / "trusted-runner"
    materialize_root.mkdir(parents=True, exist_ok=True)
    write_fd, temporary_name = tempfile.mkstemp(
        prefix="runner-",
        suffix=".sh",
        dir=materialize_root,
    )
    temporary_path = Path(temporary_name)
    read_fd = -1
    try:
        with os.fdopen(write_fd, "wb") as handle:
            handle.write(source)
            handle.flush()
            os.fsync(handle.fileno())
            os.fchmod(handle.fileno(), 0o400)
        read_fd = os.open(temporary_path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        temporary_path.unlink()
        materialized_source = b"".join(iter(lambda: os.read(read_fd, 65536), b""))
        if not hmac.compare_digest(
            hashlib.sha256(materialized_source).digest(),
            hashlib.sha256(source).digest(),
        ):
            fail("materialized runner digest 不符", 65)
        os.lseek(read_fd, 0, os.SEEK_SET)
        os.set_inheritable(read_fd, True)
        return read_fd
    except BaseException:
        if read_fd >= 0:
            os.close(read_fd)
        raise
    finally:
        temporary_path.unlink(missing_ok=True)


def main() -> None:
    if len(sys.argv) != 3 or sys.argv[1] != "--runner-sha256":
        fail("argv 必須由 pinned contract 固定為 runner digest", 64)
    expected_digest = sys.argv[2]
    if len(expected_digest) != 64 or any(
        character not in "0123456789abcdef" for character in expected_digest
    ):
        fail("runner digest 格式不符", 64)

    sandbox = Path.cwd().resolve()
    if (sandbox / ".git").exists() or (sandbox / ".git").is_symlink():
        fail("不得在 git checkout 執行", 65)
    runner_source = read_verified_runner_bytes(sandbox, expected_digest)

    python_bin = sandbox / ".venv" / "bin" / "python"
    if not python_bin.exists() or not os.access(python_bin, os.X_OK):
        fail("sandbox .venv Python 不可執行", 69)

    runtime_root = sandbox / RUNTIME_ROOT
    runtime_paths = {
        "HOME": runtime_root / "home",
        "TMPDIR": runtime_root / "tmp",
        "TMP": runtime_root / "tmp",
        "TEMP": runtime_root / "tmp",
        "TEMPDIR": runtime_root / "tmp",
        "UV_CACHE_DIR": runtime_root / "cache" / "uv",
        "XDG_CACHE_HOME": runtime_root / "cache" / "xdg",
        "XDG_CONFIG_HOME": runtime_root / "config" / "xdg",
        "XDG_DATA_HOME": runtime_root / "data" / "xdg",
        "XDG_STATE_HOME": runtime_root / "state" / "xdg",
        "MPLCONFIGDIR": runtime_root / "cache" / "matplotlib",
        "JOBLIB_TEMP_FOLDER": runtime_root / "tmp" / "joblib",
        "PIP_CACHE_DIR": runtime_root / "cache" / "pip",
        "NUMBA_CACHE_DIR": runtime_root / "cache" / "numba",
        "HF_HOME": runtime_root / "cache" / "huggingface",
    }
    for path in set(runtime_paths.values()):
        path.mkdir(parents=True, exist_ok=True)

    environment = dict(FIXED_ENVIRONMENT)
    environment.update({key: str(path) for key, path in runtime_paths.items()})
    environment["TOP10_DAILY_PYTHON"] = str(python_bin)
    runner_fd = materialize_verified_runner(runtime_root, runner_source)
    try:
        os.dup2(runner_fd, 0, inheritable=True)
    finally:
        os.close(runner_fd)
    os.execve(
        "/bin/bash",
        [RUNNER.as_posix(), "-s"],
        environment,
    )


if __name__ == "__main__":
    main()
