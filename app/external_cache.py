"""TOP10 job cache 的薄接點；原生身分與容量仍由 ai-core 唯讀 gate 裁決。"""

from __future__ import annotations

import hashlib
import errno
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time


from app.lightgbm_temp_guard import owned_temp


FIELDS = ("AI_CORE_CACHE_VOLUME", "AI_CORE_CACHE_IMAGE", "AI_CORE_CACHE_BACKING_VOLUME",
          "AI_CORE_CACHE_BACKING_UUID", "AI_CORE_CACHE_VOLUME_UUID", "AI_CORE_CACHE_MAX_BYTES")

MANAGED_FIELDS = ("AI_CORE_CACHE_VOLUME", "AI_CORE_CACHE_VOLUME_UUID", "AI_CORE_CACHE_ROOT",
                  "AI_CORE_CACHE_MAX_BYTES", "AI_CORE_CACHE_MAX_FILES", "AI_CORE_CACHE_RESERVED_OTHER_BYTES")


class ExternalCacheError(RuntimeError):
    """只把固定 reason code 交給既有 receipt；不外洩路徑或 subprocess stderr。"""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def external_requested() -> bool:
    return any(os.environ.get(key) for key in (*FIELDS, *MANAGED_FIELDS, "AI_CORE_CACHE_MODE", "TOP10_EXTERNAL_CACHE_ROOT"))


def reject_external_isolation(*, configured: bool = True) -> None:
    """舊隔離入口只允許原 sandbox；不把共享快取偷偷加入 Seatbelt。"""
    if os.environ.get("TOP10_EXTERNAL_CACHE_ROOT") or (configured and external_requested()):
        raise ExternalCacheError("EXTERNAL_CACHE_ISOLATION_UNSUPPORTED")


def runtime_environment(root: Path) -> dict[str, str]:
    return {key: str(root / suffix) for key, suffix in {
        "TMPDIR": "tmp", "TMP": "tmp", "TEMP": "tmp", "TEMPDIR": "tmp",
        "UV_CACHE_DIR": "cache/uv", "XDG_CACHE_HOME": "cache/xdg",
        "MPLCONFIGDIR": "cache/matplotlib", "JOBLIB_TEMP_FOLDER": "tmp/joblib",
    }.items()}


def external_environment(root: Path) -> dict[str, str]:
    """只對本次 Python child 套用標準啟動接點；保留既有 import 路徑。"""
    hook = str(Path(__file__).resolve().parent / "_storage_python")
    previous = os.environ.get("PYTHONPATH", "").split(os.pathsep)
    python_path = os.pathsep.join([hook, *(path for path in previous if path and path != hook)])
    return {**runtime_environment(root), "TOP10_EXTERNAL_CACHE_ROOT": str(root),
            "PYTHONPATH": python_path}


class ExternalCache:
    def __init__(self, root: Path, job: str, max_bytes: int, max_files: int,
                 retention_seconds: int = 86400):
        self.directory_mode = os.environ.get("AI_CORE_CACHE_MODE") == "directory"
        if os.environ.get("AI_CORE_CACHE_MODE", "image") not in {"image", "directory"}:
            raise ExternalCacheError("EXTERNAL_CACHE_CONTRACT_INCOMPLETE")
        fields = MANAGED_FIELDS if self.directory_mode else FIELDS
        if not all(os.environ.get(key) for key in fields):
            raise ExternalCacheError("EXTERNAL_CACHE_CONTRACT_INCOMPLETE")
        if not job or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789-" for char in job):
            raise ValueError("外接 cache job 名稱不符")
        self.config = {key: os.environ[key] for key in fields}
        self.project_root = root.resolve()
        self.job = job
        self.volume = Path(self.config["AI_CORE_CACHE_VOLUME"])
        identity = hashlib.sha256(str(root.resolve()).encode()).hexdigest()[:24]
        self.root = self.volume / "Caches" / "top10" / identity / job
        self.max_bytes, self.max_files = max_bytes, max_files
        if min(max_bytes, max_files, retention_seconds) <= 0:
            raise ValueError("外接 cache 必須有正值容量、檔案數與保留期限")
        self.retention_seconds = retention_seconds
        core = Path(os.environ.get("AI_CORE_DIR", ""))
        if not core.is_absolute():
            raise ExternalCacheError("EXTERNAL_CACHE_TOOLCHAIN_REQUIRED")
        self.command = [str(core / ".venv/bin/python"), "-B",
                        str(core / "scripts/runtime_cache_capacity_gate.py")]
        self.device: int | None = None
        self.fd: int | None = None
        self.root_identity: tuple[int, int] | None = None
        self._managed = None
        if self.directory_mode:
            sys.path.insert(0, str(core / "scripts"))
            try:
                from runtime_cache_capacity_gate import ManagedCache
                self._managed = ManagedCache.from_env()
            except (ImportError, OSError, ValueError, RuntimeError) as error:
                raise ExternalCacheError("EXTERNAL_CACHE_MANAGED_ADMISSION_DENIED") from error
            self.volume = self._managed.volume
            self.root = self._managed.root / "top10" / identity / job


    def sample(self, *, enforce_retention: bool = True) -> dict:
        """首次用 Foundation 准入 backing；之後用原生 mapping 重驗三方身分。"""
        if self.directory_mode:
            try:
                measured = self._managed.sample()
                device = measured["device"]
                size = count = 0
                for directory, dirs, files in os.walk(self.root, followlinks=False):
                    for name in (*dirs, *files):
                        info = (Path(directory) / name).lstat()
                        size += info.st_size
                        count += 1
                        if size > self.max_bytes or count > self.max_files:
                            raise ExternalCacheError("EXTERNAL_CACHE_JOB_BUDGET_EXCEEDED")
                payload = {**measured, "roots": [{"name": "top10-job", "path": str(self.root),
                    "bytes": size, "files": count, "max_bytes": self.max_bytes, "max_files": self.max_files}],
                    "image_contract": None,
                    "managed_contract": {"device": device, "volume_uuid": measured["volume_uuid"]},
                    "full_capacity_admission": True}
            except ExternalCacheError:
                raise
            except (OSError, ValueError, RuntimeError, KeyError) as error:
                raise ExternalCacheError("EXTERNAL_CACHE_MANAGED_ADMISSION_DENIED") from error
        else:
            c = self.config
            args = [*self.command,
                    "--volume", str(self.volume), "--image", c["AI_CORE_CACHE_IMAGE"],
                    "--backing-volume", c["AI_CORE_CACHE_BACKING_VOLUME"],
                    "--backing-volume-uuid", c["AI_CORE_CACHE_BACKING_UUID"],
                    "--volume-uuid", c["AI_CORE_CACHE_VOLUME_UUID"],
                    "--max-image-bytes", c["AI_CORE_CACHE_MAX_BYTES"],
                    "--min-container-free-bytes", "0", "--min-backing-free-bytes", "50000000000",
                    "--min-free-bytes", str(2 * 1024**3),
                    "--root", "top10-job", str(self.root), str(self.max_bytes), str(self.max_files),
                    "--write-path", "top10-job", str(self.root)]
            if self.device is not None:
                args.append("--mapping-only")
                if self.fd is not None and os.fstat(self.fd).st_dev != self.device:
                    raise ExternalCacheError("EXTERNAL_CACHE_IDENTITY_DRIFT")
            result = subprocess.run(args, capture_output=True, text=True, timeout=20, check=False)
            if result.returncode:
                raise ExternalCacheError(f"EXTERNAL_CACHE_GATE_DENIED_{result.returncode}")
            payload = json.loads(result.stdout)
            device = payload["image_contract"]["image_device"]
            if payload["decision"] not in {"PASS", "MAPPING_VALID"} or type(device) is not int:
                raise ExternalCacheError("EXTERNAL_CACHE_GATE_INVALID")
        if self.device is not None and self.device != device:
            raise ExternalCacheError("EXTERNAL_CACHE_IDENTITY_DRIFT")
        if self.volume.is_symlink() or not self.volume.is_mount() or self.volume.stat().st_dev != device:
            raise ExternalCacheError("EXTERNAL_CACHE_IDENTITY_DRIFT")
        self.device = device
        current = self.volume
        for part in self.root.relative_to(self.volume).parts:
            current /= part
            if current.is_symlink():
                raise ExternalCacheError("EXTERNAL_CACHE_SYMLINK_DRIFT")
        if self.root_identity is not None:
            stat = self.root.stat()
            if (stat.st_dev, stat.st_ino) != self.root_identity:
                raise ExternalCacheError("EXTERNAL_CACHE_IDENTITY_DRIFT")
        # 僅 guard 的獨占、child 啟動前階段可略過 TTL 來計入既有容量。
        cutoff = time.time() - self.retention_seconds
        for directory, dirs, files in os.walk(self.root, followlinks=False):
            for name in (*dirs, *files):
                path = Path(directory) / name
                if path.is_symlink():
                    if not self.directory_mode or not path.resolve(strict=True).is_relative_to(self.root):
                        raise ExternalCacheError("EXTERNAL_CACHE_SYMLINK_DRIFT")
            if enforce_retention:
                for name in files:
                    item = Path(directory) / name
                    info = item.lstat()
                    # 本層 LightGBM 檔交由 guard 的明確 dry-run/execute 契約管理。
                    if item.parent == self.root / "tmp" and owned_temp(name, info):
                        continue
                    if info.st_mtime < cutoff:
                        raise ExternalCacheError("EXTERNAL_CACHE_RETENTION_EXPIRED")
        payload["retention"] = {"seconds": self.retention_seconds, "automatic_cleanup": False,
                                "expired_action": "deny-and-preserve"}
        return payload

    def reclaim_expired_before_child(self, *, exclusive_lock_fd: int) -> dict[str, int]:
        """兩種快取模式皆須持有 job 獨占鎖，才可回收白名單內的過期字型索引。"""
        lock_path = self.project_root / "logs/storage_safety" / f"{self.job}.lock"
        try:
            held = os.fstat(exclusive_lock_fd)
            current = lock_path.lstat()
            if (not stat.S_ISREG(held.st_mode) or not stat.S_ISREG(current.st_mode)
                    or (held.st_dev, held.st_ino) != (current.st_dev, current.st_ino)
                    or held.st_uid != os.getuid()):
                raise ExternalCacheError("EXTERNAL_CACHE_RECLAIM_NOT_EXCLUSIVE")
            # 另開 descriptor 驗證鎖已被持有；不自行取得鎖來掩蓋未鎖狀態。
            probe_fd = os.open(lock_path, os.O_RDONLY | os.O_NOFOLLOW)
            try:
                try:
                    fcntl.flock(probe_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    pass
                else:
                    fcntl.flock(probe_fd, fcntl.LOCK_UN)
                    raise ExternalCacheError("EXTERNAL_CACHE_RECLAIM_NOT_EXCLUSIVE")
            finally:
                os.close(probe_fd)
        except (OSError, ValueError) as error:
            raise ExternalCacheError("EXTERNAL_CACHE_RECLAIM_NOT_EXCLUSIVE") from error
        self.sample(enforce_retention=False)
        if not self.root.exists():
            return {"files": 0, "bytes": 0}
        root_before = self.root.lstat()
        if (not stat.S_ISDIR(root_before.st_mode) or root_before.st_dev != self.device
                or root_before.st_uid != os.getuid()):
            raise ExternalCacheError("EXTERNAL_CACHE_RETENTION_UNOWNED")
        cutoff = time.time() - self.retention_seconds
        # 在動到任何檔案前完整盤點：未知的過期資料一律保留並拒絕。
        candidates: list[tuple[tuple[str, ...], int, int, int]] = []
        def scan_failed(error: OSError) -> None:
            raise ExternalCacheError("EXTERNAL_CACHE_RETENTION_SCAN_FAILED") from error

        for directory, dirs, files in os.walk(self.root, followlinks=False, onerror=scan_failed):
            for name in (*dirs, *files):
                if (Path(directory) / name).is_symlink():
                    raise ExternalCacheError("EXTERNAL_CACHE_SYMLINK_DRIFT")
            for name in files:
                item = Path(directory) / name
                info = item.lstat()
                if info.st_mtime >= cutoff:
                    continue
                parts = item.relative_to(self.root).parts
                if parts == ("tmp", name) and owned_temp(name, info):
                    continue
                if (len(parts) != 3 or parts[:2] != ("cache", "matplotlib")
                        or not re.fullmatch(r"fontlist-v[0-9]+(?:\.[0-9]+)*\.json", name)):
                    raise ExternalCacheError("EXTERNAL_CACHE_RETENTION_UNOWNED")
                if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                        or info.st_uid != os.getuid() or info.st_dev != self.device):
                    raise ExternalCacheError("EXTERNAL_CACHE_RETENTION_UNOWNED")
                candidates.append((parts, info.st_ino, info.st_size, info.st_mtime_ns))
                if len(candidates) > 16:
                    raise ExternalCacheError("EXTERNAL_CACHE_RETENTION_UNOWNED")
        if not candidates:
            self.sample()
            return {"files": 0, "bytes": 0}

        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        volume_fd = os.open(self.volume, flags)
        try:
            if os.fstat(volume_fd).st_dev != self.device:
                raise ExternalCacheError("EXTERNAL_CACHE_IDENTITY_DRIFT")
            root_fd = os.dup(volume_fd)
            try:
                for part in self.root.relative_to(self.volume).parts:
                    child_fd = os.open(part, flags, dir_fd=root_fd)
                    os.close(root_fd)
                    root_fd = child_fd
                    if os.fstat(root_fd).st_dev != self.device:
                        raise ExternalCacheError("EXTERNAL_CACHE_IDENTITY_DRIFT")
                pinned_root = os.fstat(root_fd)
                if (pinned_root.st_dev, pinned_root.st_ino) != (root_before.st_dev, root_before.st_ino):
                    raise ExternalCacheError("EXTERNAL_CACHE_RETENTION_RACE")
                # 預先 pin 每個索引，確保不存在 unknown/hardlink/race 後才回收。
                pinned: list[tuple[int, int, tuple[int, int, int]]] = []
                try:
                    for parts, inode, size, mtime_ns in candidates:
                        parent_fd = os.dup(root_fd)
                        try:
                            for part in parts[:-1]:
                                next_fd = os.open(part, flags, dir_fd=parent_fd)
                                os.close(parent_fd)
                                parent_fd = next_fd
                            file_fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd)
                            info = os.fstat(file_fd)
                            expected = (inode, size, mtime_ns)
                            if ((info.st_ino, info.st_size, info.st_mtime_ns) != expected
                                    or info.st_dev != self.device or info.st_nlink != 1
                                    or info.st_uid != os.getuid() or not stat.S_ISREG(info.st_mode)):
                                os.close(file_fd)
                                raise ExternalCacheError("EXTERNAL_CACHE_RETENTION_RACE")
                            pinned.append((parent_fd, file_fd, expected))
                        except BaseException:
                            if not any(entry[0] == parent_fd for entry in pinned):
                                os.close(parent_fd)
                            raise
                    for (parts, _, _, _), (parent_fd, file_fd, expected) in zip(candidates, pinned):
                        root_now = self.root.lstat()
                        if (root_now.st_dev, root_now.st_ino) != (pinned_root.st_dev, pinned_root.st_ino):
                            raise ExternalCacheError("EXTERNAL_CACHE_RETENTION_RACE")
                        info = os.stat(parts[-1], dir_fd=parent_fd, follow_symlinks=False)
                        if ((info.st_ino, info.st_size, info.st_mtime_ns) != expected
                                or info.st_nlink != 1 or info.st_dev != self.device
                                or info.st_uid != os.getuid() or not stat.S_ISREG(info.st_mode)):
                            raise ExternalCacheError("EXTERNAL_CACHE_RETENTION_RACE")
                        os.unlink(parts[-1], dir_fd=parent_fd)
                finally:
                    for parent_fd, file_fd, _ in pinned:
                        os.close(file_fd)
                        os.close(parent_fd)
            finally:
                os.close(root_fd)
        finally:
            os.close(volume_fd)
        # 清理後重新執行原生身分／容量 gate 與 TTL 檢查。
        self.sample()
        return {"files": len(candidates), "bytes": sum(item[2] for item in candidates)}

    def materialize(self) -> dict[str, str]:
        """以已驗證 device 的 dirfd 建立子目錄；卸載時不依名稱重建內建替代根。"""
        self.sample()
        if self.directory_mode:
            try:
                self._managed.materialize([Path(p) for p in set(runtime_environment(self.root).values())])
                info = self.root.lstat()
                self.root_identity = (info.st_dev, info.st_ino)
                self.sample()
                return external_environment(self.root)
            except (OSError, ValueError, RuntimeError) as error:
                raise ExternalCacheError("EXTERNAL_CACHE_MANAGED_MATERIALIZE_DENIED") from error
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        volume_fd = os.open(self.volume, flags)
        try:
            if os.fstat(volume_fd).st_dev != self.device:
                raise ExternalCacheError("EXTERNAL_CACHE_IDENTITY_DRIFT")
            paths = runtime_environment(self.root)
            for path in set(paths.values()):
                current = os.dup(volume_fd)
                try:
                    for part in Path(path).relative_to(self.volume).parts:
                        try:
                            child = os.open(part, flags, dir_fd=current)
                        except FileNotFoundError:
                            os.mkdir(part, mode=0o700, dir_fd=current)
                            child = os.open(part, flags, dir_fd=current)
                        if os.fstat(child).st_dev != self.device:
                            os.close(child)
                            raise ExternalCacheError("EXTERNAL_CACHE_IDENTITY_DRIFT")
                        os.close(current)
                        current = child
                finally:
                    os.close(current)
            self.fd = os.dup(volume_fd)
            stat = self.root.stat()
            self.root_identity = (stat.st_dev, stat.st_ino)
        finally:
            os.close(volume_fd)
        self.sample()
        return external_environment(self.root)

    def close(self) -> None:
        if self._managed is not None:
            self._managed.close()
            self._managed = None
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None


def probe() -> None:
    """只寫一個 4096-byte owned 檔；不啟動 guard、正式工作或修改 denial。"""
    import shutil
    import sys
    import uuid

    cache = ExternalCache(Path(__file__).resolve().parents[1], "cache-io-probe", 65536, 64)
    target: Path | None = None
    parent_fd: int | None = None
    file_fd: int | None = None
    try:
        before = cache.sample()
        environment = cache.materialize()
        target = Path(environment["TMPDIR"]) / ("probe-" + uuid.uuid4().hex)
        parent_fd = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        if os.fstat(parent_fd).st_dev != cache.device:
            raise ExternalCacheError("EXTERNAL_CACHE_IDENTITY_DRIFT")
        # 檔案由 pinned dirfd exclusive 建立，child 只寫傳入的 owned fd。
        file_fd = os.open(target.name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                          0o600, dir_fd=parent_fd)
        code = (
            "import json,os,sys; "
            "fd=int(sys.argv[1]); "
            "os.write(fd,b'x'*4096); os.fsync(fd); os.close(fd); "
            "print(json.dumps({k:os.environ[k] for k in sys.argv[2:]}))"
        )
        child = subprocess.run([sys.executable, "-B", "-c", code, str(file_fd), *environment],
                               env={**os.environ, **environment}, capture_output=True,
                               text=True, timeout=10, check=True, pass_fds=(file_fd,))
        after = cache.sample()
        os.lseek(file_fd, 0, os.SEEK_SET)
        if os.read(file_fd, 4097) != b"x" * 4096:
            raise RuntimeError("EXTERNAL_CACHE_PROBE_CONTENT_MISMATCH")
        if os.stat(target.name, dir_fd=parent_fd, follow_symlinks=False).st_ino != os.fstat(file_fd).st_ino:
            raise ExternalCacheError("EXTERNAL_CACHE_IDENTITY_DRIFT")
        os.unlink(target.name, dir_fd=parent_fd)
        target = None
        final = cache.sample()
        print(json.dumps({"scope": "owned-small-io-only", "child_environment": json.loads(child.stdout),
                          "internal_physical": shutil.disk_usage(Path(__file__).resolve())._asdict(),
                          "before": before, "after": after, "final": final,
                          "owned_file_removed": True}, ensure_ascii=False))
    finally:
        # 身分不明時不依名稱刪除；保留 exact path 供人工核對。
        if target is not None and file_fd is not None and parent_fd is not None:
            try:
                cache.sample()
                if os.stat(target.name, dir_fd=parent_fd, follow_symlinks=False).st_ino != os.fstat(file_fd).st_ino:
                    raise ExternalCacheError("EXTERNAL_CACHE_IDENTITY_DRIFT")
                os.unlink(target.name, dir_fd=parent_fd)
            except (OSError, RuntimeError, subprocess.SubprocessError):
                print(f"owned probe 保留待核對：{target}", file=sys.stderr)
        if file_fd is not None:
            os.close(file_fd)
        if parent_fd is not None:
            os.close(parent_fd)
        cache.close()


if __name__ == "__main__":
    probe()
