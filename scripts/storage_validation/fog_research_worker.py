#!/usr/bin/env python3
"""在 validation sandbox 內執行固定的 fog-research-worker 入口。"""

from __future__ import annotations

import hashlib
import hmac
import ctypes
import os
import stat
import sys
import tempfile
import argparse
import json
import subprocess
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
    "TOP10_STORAGE_VALIDATION_MODE": "1",
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
    "TOP10_PROCESS_IDENTITY_MODE": "validation-libproc",
}


class ProcBSDInfo(ctypes.Structure):
    """Darwin `proc_bsdinfo` ABI；只讀取 PID 與 process start time。"""

    _fields_ = [
        ("pbi_flags", ctypes.c_uint32),
        ("pbi_status", ctypes.c_uint32),
        ("pbi_xstatus", ctypes.c_uint32),
        ("pbi_pid", ctypes.c_uint32),
        ("pbi_ppid", ctypes.c_uint32),
        ("pbi_uid", ctypes.c_uint32),
        ("pbi_gid", ctypes.c_uint32),
        ("pbi_ruid", ctypes.c_uint32),
        ("pbi_rgid", ctypes.c_uint32),
        ("pbi_svuid", ctypes.c_uint32),
        ("pbi_svgid", ctypes.c_uint32),
        ("rfu_1", ctypes.c_uint32),
        ("pbi_comm", ctypes.c_char * 16),
        ("pbi_name", ctypes.c_char * 32),
        ("pbi_nfiles", ctypes.c_uint32),
        ("pbi_pgid", ctypes.c_uint32),
        ("pbi_pjobc", ctypes.c_uint32),
        ("e_tdev", ctypes.c_uint32),
        ("e_tpgid", ctypes.c_uint32),
        ("pbi_nice", ctypes.c_int32),
        ("pbi_start_tvsec", ctypes.c_uint64),
        ("pbi_start_tvusec", ctypes.c_uint64),
    ]


def darwin_process_start_token(pid: int) -> str:
    """不執行外部命令，以 libproc 取得可防 PID reuse 的 start token。"""

    if pid <= 0:
        raise ValueError("pid 必須為正整數")
    libproc = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
    proc_pidinfo = libproc.proc_pidinfo
    proc_pidinfo.argtypes = [
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_uint64,
        ctypes.c_void_p,
        ctypes.c_int,
    ]
    proc_pidinfo.restype = ctypes.c_int
    info = ProcBSDInfo()
    expected_size = ctypes.sizeof(info)
    actual_size = proc_pidinfo(pid, 3, 0, ctypes.byref(info), expected_size)
    if (
        actual_size != expected_size
        or info.pbi_pid != pid
        or info.pbi_start_tvsec <= 0
    ):
        raise RuntimeError("libproc 無法確認 process identity")
    return f"{info.pbi_start_tvsec}.{info.pbi_start_tvusec:06d}"


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


def checked_source_path(source: Path, relative: str) -> Path:
    """缺席路徑也檢查每層祖先，拒絕包含 dangling symlink 的別名。"""
    part = Path(relative)
    if part.is_absolute() or ".." in part.parts or not part.parts:
        raise ValueError("source manifest 路徑不符")
    path = source / part
    for item in (path, *path.parents):
        if item.is_symlink():
            raise ValueError("source path 不接受 symlink")
    if path.resolve() != path:
        raise ValueError("source path 必須是 lexical path")
    return path


def scan_source_tree(source: Path, relative: str, excluded_names: list[str],
                     excluded_suffixes: list[str]) -> dict:
    """釘住樹存在狀態及檔案／目錄集合；排除前仍檢查 symlink。"""
    root = checked_source_path(source, relative)
    entries = {}
    if root.exists():
        if not root.is_dir():
            raise ValueError("scanned root 必須是目錄")
        def failed(error):
            raise error
        for directory, dirs, names in os.walk(root, followlinks=False, onerror=failed):
            for name in (*dirs, *names):
                path = checked_source_path(source, (Path(directory) / name).relative_to(source).as_posix())
                if name in excluded_names or (path.is_file() and any(name.endswith(s) for s in excluded_suffixes)):
                    continue
                if not path.is_dir() and not path.is_file():
                    raise ValueError("scanned tree 只接受 regular file／directory")
                entries[path.relative_to(source).as_posix()] = "directory" if path.is_dir() else "file"
            dirs[:] = [name for name in dirs if name not in excluded_names]
    return {"root": relative, "exists": root.exists(), "excluded_names": excluded_names,
            "excluded_suffixes": excluded_suffixes, "entries": dict(sorted(entries.items()))}


def optional_source_file(source: Path, relative: str) -> dict:
    """合法缺席與存在內容皆屬釘選契約。"""
    path = checked_source_path(source, relative)
    if not path.exists():
        return {"path": relative, "exists": False, "size": None, "sha256": None}
    if not path.is_file():
        raise ValueError("optional input 必須是 regular file")
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return {"path": relative, "exists": True, "size": path.stat().st_size, "sha256": value.hexdigest()}


def external_review_selection(source: Path) -> dict:
    """對齊 sorted(rglob(...))[-1]，不把合法缺席轉成必備檔案。"""
    tree = scan_source_tree(source, "artifacts/external_review", [], [])
    candidates = sorted(
        (p for p in tree["entries"] if Path(p).match("external_review_summary_*.json")),
        key=Path,
    )
    selected = optional_source_file(source, candidates[-1]) if candidates else None
    return {"tree": tree, "pattern": "external_review_summary_*.json",
            "selection": "sorted-path-last", "candidates": candidates, "selected": selected}


def shared_source_main(argv: list[str]) -> None:
    """在既有 Seatbelt 內執行 pinned representative bytes；不啟動完整 shell quota。"""
    if any(os.environ.get(key) for key in (
        "TOP10_EXTERNAL_CACHE_ROOT", "AI_CORE_CACHE_VOLUME", "AI_CORE_CACHE_IMAGE",
        "AI_CORE_CACHE_BACKING_VOLUME", "AI_CORE_CACHE_BACKING_UUID",
        "AI_CORE_CACHE_VOLUME_UUID", "AI_CORE_CACHE_MAX_BYTES",
    )):
        fail("EXTERNAL_CACHE_ISOLATION_UNSUPPORTED", 78)
    parser = argparse.ArgumentParser()
    for flag in ("source-root", "source-commit", "validation-root", "source-manifest",
                 "source-manifest-sha256", "runner-sha256", "representative-sha256"):
        parser.add_argument("--" + flag, required=True)
    args = parser.parse_args(argv)

    def lexical(path: Path) -> Path:
        absolute = Path(os.path.abspath(path))
        if absolute.resolve(strict=True) != absolute:
            raise ValueError("shared path 不得包含 symlink")
        return absolute

    source = lexical(Path(args.source_root))
    sandbox = lexical(Path(args.validation_root))
    if (not source.is_dir() or not sandbox.is_dir() or Path.cwd().resolve() != sandbox
            or source.is_relative_to(sandbox) or sandbox.is_relative_to(source)
            or (sandbox / ".git").exists() or (sandbox / ".git").is_symlink()):
        raise ValueError("shared source／sandbox 邊界不符")
    manifest_path = lexical(Path(args.source_manifest))
    manifest_path.relative_to(sandbox)
    if manifest_path.stat().st_size > 4 * 1024**2:
        raise ValueError("source manifest 過大")
    manifest_bytes = manifest_path.read_bytes()
    if not hmac.compare_digest(hashlib.sha256(manifest_bytes).hexdigest(), args.source_manifest_sha256):
        raise ValueError("source manifest digest 不符")
    manifest = json.loads(manifest_bytes)
    if manifest["source_root"] != str(source) or manifest["source_commit"] != args.source_commit:
        raise ValueError("source manifest identity 不符")
    if len(args.source_commit) not in (40, 64) or any(c not in "0123456789abcdef" for c in args.source_commit):
        raise ValueError("source commit 格式不符")
    actual_commit = subprocess.check_output(
        ["/usr/bin/git", "-C", str(source), "rev-parse", "HEAD"], text=True, timeout=5,
    ).strip()
    if actual_commit != args.source_commit:
        raise ValueError("source commit 已改變")

    for tree in manifest["scanned_trees"]:
        if scan_source_tree(source, tree["root"], tree["excluded_names"], tree["excluded_suffixes"]) != tree:
            raise ValueError("source scanned tree 成員已改變")
    if optional_source_file(source, "artifacts/model_experiments/model_experiment_ledger.json") != manifest["optional_ledger"]:
        raise ValueError("optional ledger 存在狀態／內容已改變")
    if external_review_selection(source) != manifest["external_review"]:
        raise ValueError("external review 候選／選取內容已改變")

    def digest(path: Path) -> str:
        value = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                value.update(chunk)
        return value.hexdigest()

    files = {}
    for row in manifest["files"]:
        relative = Path(row["path"])
        if relative.is_absolute() or ".." in relative.parts or row["path"] in files:
            raise ValueError("source manifest 路徑不符")
        path = lexical(source / relative)
        path.relative_to(source)
        if not path.is_file() or path.stat().st_size != row["size"] or digest(path) != row["sha256"]:
            raise ValueError("source file size／digest 不符")
        files[row["path"]] = path
    for required in (str(RUNNER), "scripts/run_fog_representative_validation.py",
                     "data/clean/features.parquet", "data/reference/stock_industry_map.csv",
                     "artifacts/market_regime_history.json", "config/regime_research_contract.json",
                     "scripts/run_autonomous_research.py", "scripts/publish_research_batch_intent.py",
                     "scripts/verify_research_spine_batch.py", "scripts/run_backtest_strategy_matrix.py"):
        if required not in files:
            raise ValueError("source manifest 缺必要輸入")
    interpreter = manifest["interpreter"]
    python_bin = source / ".venv/bin/python"
    native_python = python_bin.resolve(strict=True)
    if (interpreter["path"] != str(python_bin) or interpreter["resolved"] != str(native_python)
            or interpreter["size"] != native_python.stat().st_size
            or interpreter["sha256"] != digest(native_python)
            or Path(sys.executable).resolve() != native_python
            or Path(sys.prefix).resolve() != (source / ".venv").resolve()):
        raise ValueError("source interpreter identity 不符")
    # runner 保留 pin，但 shared 模式不執行它；rep 採已驗證 bytes，封住重讀接縫。
    pinned_bytes = {}
    for relative, expected in ((str(RUNNER), args.runner_sha256),
                               ("scripts/run_fog_representative_validation.py", args.representative_sha256)):
        path = files[relative]
        if path.stat().st_size > MAX_RUNNER_BYTES:
            raise ValueError("shared runner 過大")
        raw = path.read_bytes()
        if not hmac.compare_digest(hashlib.sha256(raw).hexdigest(), expected):
            raise ValueError("shared runner bytes 不符")
        pinned_bytes[relative] = raw
    runtime = sandbox / RUNTIME_ROOT
    environment = dict(FIXED_ENVIRONMENT)
    for key, suffix in {
        "HOME": "home", "TMPDIR": "tmp", "TMP": "tmp", "TEMP": "tmp", "TEMPDIR": "tmp",
        "UV_CACHE_DIR": "cache/uv", "XDG_CACHE_HOME": "cache/xdg", "XDG_CONFIG_HOME": "config/xdg",
        "XDG_DATA_HOME": "data/xdg", "XDG_STATE_HOME": "state/xdg", "MPLCONFIGDIR": "cache/matplotlib",
        "JOBLIB_TEMP_FOLDER": "tmp/joblib", "PIP_CACHE_DIR": "cache/pip", "NUMBA_CACHE_DIR": "cache/numba",
        "HF_HOME": "cache/huggingface",
    }.items():
        path = runtime / suffix
        if path.resolve() != path:
            raise ValueError("shared runtime 不得包含 symlink")
        path.mkdir(parents=True, exist_ok=True)
        lexical(path)
        environment[key] = str(path)
    environment["TOP10_DAILY_PYTHON"] = str(python_bin)
    environment["TOP10_VALIDATION_SOURCE_COMMIT"] = args.source_commit
    os.environ.clear()
    os.environ.update(environment)
    relative = "scripts/run_fog_representative_validation.py"
    namespace = {"__name__": "fog_shared_representative", "__file__": str(source / relative)}
    exec(compile(pinned_bytes[relative], str(source / relative), "exec"), namespace)
    raise SystemExit(namespace["main"](validation_root=sandbox))


def main() -> None:
    if len(sys.argv) == 3 and sys.argv[1] == "--process-start-token":
        try:
            pid = int(sys.argv[2])
            print(darwin_process_start_token(pid))
        except (ValueError, OSError, RuntimeError):
            raise SystemExit(1) from None
        return
    # 在讀 runner 或建立任何 sandbox 路徑前拒絕外接配置；身分唯讀查詢除外。
    if any(os.environ.get(key) for key in (
        "TOP10_EXTERNAL_CACHE_ROOT", "AI_CORE_CACHE_VOLUME", "AI_CORE_CACHE_IMAGE",
        "AI_CORE_CACHE_BACKING_VOLUME", "AI_CORE_CACHE_BACKING_UUID",
        "AI_CORE_CACHE_VOLUME_UUID", "AI_CORE_CACHE_MAX_BYTES",
    )):
        fail("EXTERNAL_CACHE_ISOLATION_UNSUPPORTED", 78)
    if len(sys.argv) > 1 and sys.argv[1] == "--shared-source":
        shared_source_main(sys.argv[2:])
        return
    if len(sys.argv) != 5 or sys.argv[1] != "--runner-sha256" or sys.argv[3] != "--source-commit":
        fail("argv 必須由 pinned contract 固定 runner digest 與 source commit", 64)
    expected_digest = sys.argv[2]
    if len(expected_digest) != 64 or any(
        character not in "0123456789abcdef" for character in expected_digest
    ):
        fail("runner digest 格式不符", 64)
    source_commit = sys.argv[4]
    if len(source_commit) not in {40, 64} or any(
        character not in "0123456789abcdef" for character in source_commit
    ):
        fail("source commit 格式不符", 64)

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
    # __file__ 是 parent 已驗證並在 sandbox 外 materialize 的唯讀 entrypoint；
    # child 只能執行，不能用 sandbox 內 workload 改寫 helper。
    environment["TOP10_PROCESS_IDENTITY_HELPER"] = str(Path(__file__).resolve())
    environment["TOP10_PROCESS_IDENTITY_PYTHON_BIN"] = sys.executable
    environment["TOP10_VALIDATION_SOURCE_COMMIT"] = source_commit
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
