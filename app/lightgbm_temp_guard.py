"""僅盤點單層 LightGBM 暫存檔；實刪須由持鎖 guard 明確啟用。"""
from contextlib import contextmanager, ExitStack
import os
from pathlib import Path
import stat
import signal
import time
import threading
import uuid

PREFIX = "lightgbm_tmp_"
PRESERVED_PREFIX = ".top10-tempguard-"
MAX_AGE_SECONDS = 24 * 60 * 60


def owned_temp(name: str, info: os.stat_result) -> bool:
    """只接受本使用者的一般單連結檔；symlink 與 hardlink 不納入清理。"""
    return (name.startswith(PREFIX) and stat.S_ISREG(info.st_mode)
            and info.st_nlink == 1 and info.st_uid == os.getuid())


@contextmanager
def directory_fd(path: Path):
    """逐層以 no-follow 開啟，不解析或穿越任何 symlink。"""
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("暫存目錄必須為無上溯的絕對路徑")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open(path.anchor, flags)
    try:
        for part in path.parts[1:]:
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)


@contextmanager
def defer_interrupts():
    """主執行緒短暫記下中斷，完成復原並還原 handler 後再交回原處理器。

    只封鎖主執行緒的 pthread mask 不足：訊號可能先送到背景執行緒，
    然後由 Python 在主執行緒執行 handler，因此需延後 Python handler 本身。
    """
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    pending = []
    try:
        with ExitStack() as restore:
            for signum in (signal.SIGINT, signal.SIGTERM):
                previous = signal.getsignal(signum)
                signal.signal(signum, lambda received, frame: pending.append(received))
                restore.callback(signal.signal, signum, previous)
            yield
    finally:
        for signum in dict.fromkeys(pending):
            signal.raise_signal(signum)


def identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def inventory(fd):
    """只讀本層 entries 的 lstat；不讀檔案內容、不進子目錄。"""
    return {name: os.stat(name, dir_fd=fd, follow_symlinks=False)
            for name in sorted(os.listdir(fd))}


def snapshot(entries):
    files = [name for name, info in entries.items() if stat.S_ISREG(info.st_mode)]
    matching = [name for name in entries if name.startswith(PREFIX)]
    return {"file_count": len(files), "file_names": files,
            "matching_count": len(matching), "matching_names": matching}


class LightGBMTempGuard:
    def __init__(self, directory: Path):
        self.directory = directory
        self.report = {"directory": str(directory), "pattern": PREFIX + "*",
                       "age_seconds": MAX_AGE_SECONDS, "status": "PENDING",
                       "warnings": [], "before": None, "after": None,
                       "cleanup": {"dry_run": True, "candidates": [], "deleted": [], "skipped": [], "retained": []}}
        self.baseline = {}
        self.directory_identity = None
        self.finished = False

    def start(self, *, execute=False, now=None):
        """呼叫端已持 job 鎖且尚未 spawn；先記原況，再按明確旗標清理。"""
        observed = time.time() if now is None else now
        cleanup = self.report["cleanup"]
        cleanup["dry_run"] = not execute
        try:
            with directory_fd(self.directory) as fd:
                directory = os.fstat(fd)
                if directory.st_uid != os.getuid():
                    raise PermissionError("暫存目錄非目前使用者所有")
                self.directory_identity = (directory.st_dev, directory.st_ino)
                entries = inventory(fd)
                self.report["before"] = snapshot(entries)
                self.report["before"]["observed_at"] = observed
                preserved = [name for name in entries if name.startswith(PRESERVED_PREFIX)]
                self.report["preserved_names"] = preserved
                if preserved:
                    self.report["warnings"].append("LIGHTGBM_TEMP_PRESERVED_ENTRIES")
                for name, info in entries.items():
                    if not name.startswith(PREFIX):
                        continue
                    if not owned_temp(name, info) or info.st_dev != directory.st_dev:
                        cleanup["skipped"].append({"name": name, "reason": "UNSAFE_ENTRY"})
                        continue
                    if info.st_mtime >= observed - MAX_AGE_SECONDS:
                        continue
                    cleanup["candidates"].append(name)
                    if not execute:
                        continue
                    # 重新確認路徑與 inode/mtime，替換或更新過的檔案保留並告警。
                    with directory_fd(self.directory) as current_fd:
                        current_dir = os.fstat(current_fd)
                        if (current_dir.st_dev, current_dir.st_ino) != self.directory_identity:
                            raise RuntimeError("暫存目錄身分變更")
                    current = os.stat(name, dir_fd=fd, follow_symlinks=False)
                    if not owned_temp(name, current) or identity(current) != identity(info):
                        cleanup["skipped"].append({"name": name, "reason": "ENTRY_CHANGED"})
                        continue
                    # 短暫延後可處理的中斷，讓捕獲／復原與收據保持一致；SIGKILL不可能攔截。
                    with defer_interrupts():
                        staged = PRESERVED_PREFIX + uuid.uuid4().hex
                        reserved = os.open(staged, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                           0o600, dir_fd=fd)
                        reservation = os.fstat(reserved)
                        os.close(reserved)
                        try:
                            os.rename(name, staged, src_dir_fd=fd, dst_dir_fd=fd)
                            pinned = os.stat(staged, dir_fd=fd, follow_symlinks=False)
                            # rename 可更新 ctime；仍核對 inode、大小與 mtime。
                            if owned_temp(name, pinned) and identity(pinned)[:4] == identity(info)[:4]:
                                os.unlink(staged, dir_fd=fd)
                                cleanup["deleted"].append(name)
                            else:
                                cleanup["skipped"].append({"name": name, "reason": "ENTRY_CHANGED"})
                        finally:
                            # 依實際 inode 判斷，不能用 rename 返回前後的布林狀態猜測。
                            try:
                                remaining = os.stat(staged, dir_fd=fd, follow_symlinks=False)
                            except FileNotFoundError:
                                pass
                            else:
                                if identity(remaining) == identity(reservation):
                                    os.unlink(staged, dir_fd=fd)
                                else:
                                    try:
                                        # no-replace 復原；原名已被占用時保留兩份。
                                        os.link(staged, name, src_dir_fd=fd, dst_dir_fd=fd,
                                                follow_symlinks=False)
                                    except OSError as exc:
                                        cleanup["retained"].append({"name": name, "preserved_as": staged,
                                                                   "reason": type(exc).__name__})
                                    else:
                                        os.unlink(staged, dir_fd=fd)
                self.baseline = {name: identity(info) for name, info in inventory(fd).items()
                                 if name.startswith(PREFIX)}
                self.report["baseline_names"] = sorted(self.baseline)
                if self.report["before"]["matching_count"]:
                    self.report["warnings"].append("LIGHTGBM_TEMP_PREEXISTING")
                if cleanup["skipped"]:
                    self.report["warnings"].append("LIGHTGBM_TEMP_CLEANUP_SKIPPED")
                self.report["status"] = "WARNING" if self.report["warnings"] else "OK"
        except (OSError, ValueError, RuntimeError) as exc:
            self.report["status"] = "WARNING"
            self.report["warnings"].append("LIGHTGBM_TEMP_START_FAILED")
            self.report["error"] = {"type": type(exc).__name__, "detail": str(exc)}
            raise
        return self.report

    def finish(self):
        """child 已收束後盤點；失敗也留 WARNING，不遮蔽原本 guard 的失敗原因。"""
        if self.finished:
            return self.report
        self.finished = True
        try:
            with directory_fd(self.directory) as fd:
                directory = os.fstat(fd)
                if (directory.st_dev, directory.st_ino) != self.directory_identity:
                    raise RuntimeError("暫存目錄身分變更")
                entries = inventory(fd)
                self.report["after"] = snapshot(entries)
                self.report["after"]["observed_at"] = time.time()
                added = [name for name, info in entries.items()
                         if name.startswith(PREFIX) and self.baseline.get(name) != identity(info)]
                self.report["new_leftovers"] = {"count": len(added), "names": added[:20]}
                if added:
                    self.report["warnings"].append("LIGHTGBM_TEMP_NEW_LEFTOVERS")
        except (OSError, ValueError, RuntimeError) as exc:
            self.report["warnings"].append("LIGHTGBM_TEMP_FINAL_SCAN_FAILED")
            self.report["final_error"] = {"type": type(exc).__name__, "detail": str(exc)}
        self.report["status"] = "WARNING" if self.report["warnings"] else "OK"
        return self.report
