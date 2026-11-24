#!/usr/bin/env python3
"""以繼承的檔案描述元鎖住整輪 Daily publish 及其子程序。"""

from __future__ import annotations

import fcntl
import os
import signal
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path


def inherited_path_matches(descriptor: int, lock_path: Path) -> bool:
    """鎖 FD 必須仍指向正式路徑的實體檔案。"""
    try:
        held = os.fstat(descriptor)
        current = os.stat(lock_path, follow_symlinks=False)
        return ((held.st_dev, held.st_ino) == (current.st_dev, current.st_ino)
                and not lock_path.is_symlink())
    except OSError:
        return False


def inherited_lock_valid(lock_path: Path) -> bool:
    """核對目前程序繼承的是同一個已持有的 Daily 鎖。"""
    try:
        descriptor = int(os.environ.get("TOP10_PUBLISH_LOCK_FD") or "")
        directory_descriptor = int(os.environ.get("TOP10_PUBLISH_DIR_LOCK_FD") or "")
        if not inherited_path_matches(descriptor, lock_path):
            return False
        if not inherited_path_matches(directory_descriptor, lock_path.parents[1]):
            return False
        # 對繼承 FD 本身取非阻塞鎖；別的程序持鎖時，此 FD 不得冒用。
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(directory_descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return (inherited_path_matches(descriptor, lock_path)
                and inherited_path_matches(directory_descriptor, lock_path.parents[1]))
    except (OSError, ValueError, BlockingIOError):
        return False


def open_directory_lock(project: Path) -> int:
    """鎖住 runtime 目錄 inode；檔名遭替換仍不能開第二輪。"""
    if project.is_symlink() or (project / "logs").is_symlink():
        raise RuntimeError("daily publish project/logs symlink rejected")
    descriptor = os.open(project, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        if not inherited_path_matches(descriptor, project):
            raise RuntimeError("daily publish project directory changed")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("daily publish overlap blocked by directory lock") from error
        if not inherited_path_matches(descriptor, project):
            raise RuntimeError("daily publish project directory changed after acquisition")
        os.set_inheritable(descriptor, True)
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


@contextmanager
def exclusive_publish_access(project: Path):
    """獨立 sender 與整輪 wrapper 共用鎖，避免 Daily 重建已嘗試訊息。"""
    lock_path = project / "logs" / "daily_publish.lock"
    if os.environ.get("TOP10_PUBLISH_LOCK_FD"):
        if not inherited_lock_valid(lock_path):
            raise RuntimeError("daily publish inherited lock verification failed")
        yield
        return
    directory_descriptor = open_directory_lock(project)
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        if lock_path.parent.is_symlink():
            raise RuntimeError("daily publish logs symlink rejected")
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    except BaseException:
        os.close(directory_descriptor)
        raise
    try:
        if not inherited_path_matches(descriptor, lock_path):
            raise RuntimeError("daily publish lock inode changed")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("daily publish overlap blocked by lock") from error
        if not inherited_path_matches(descriptor, lock_path):
            raise RuntimeError("daily publish lock inode changed after acquisition")
        os.set_inheritable(descriptor, True)
        os.environ["TOP10_PUBLISH_LOCK_FD"] = str(descriptor)
        os.environ["TOP10_PUBLISH_DIR_LOCK_FD"] = str(directory_descriptor)
        try:
            yield
        finally:
            os.environ.pop("TOP10_PUBLISH_LOCK_FD", None)
            os.environ.pop("TOP10_PUBLISH_DIR_LOCK_FD", None)
    finally:
        os.close(descriptor)
        os.close(directory_descriptor)


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "--verify":
        lock_path = Path(sys.argv[2])
        if inherited_lock_valid(lock_path):
            return 0
        print("daily publish inherited lock verification failed", file=sys.stderr)
        return 75
    if len(sys.argv) < 2:
        print("daily publish lock requires wrapper path", file=sys.stderr)
        return 64
    wrapper = Path(sys.argv[1]).resolve(strict=True)
    project = wrapper.parents[1]
    directory_descriptor = open_directory_lock(project)
    lock_path = project / "logs" / "daily_publish.lock"
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
    except BaseException:
        os.close(directory_descriptor)
        raise
    if lock_path.parent.is_symlink():
        os.close(directory_descriptor)
        raise RuntimeError("daily publish logs symlink rejected")
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    except BaseException:
        os.close(directory_descriptor)
        raise
    if not inherited_path_matches(descriptor, lock_path):
        os.close(descriptor)
        os.close(directory_descriptor)
        raise RuntimeError("daily publish lock inode changed")
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("daily publish overlap blocked by lock", file=sys.stderr)
        os.close(descriptor)
        os.close(directory_descriptor)
        return 75
    if not inherited_path_matches(descriptor, lock_path):
        os.close(descriptor)
        os.close(directory_descriptor)
        raise RuntimeError("daily publish lock inode changed after acquisition")
    # supervisor 持鎖直到整個程序群結束；子程序也繼承 FD，避免 supervisor 意外退出後提早釋鎖。
    os.set_inheritable(descriptor, True)
    env = os.environ.copy()
    env["TOP10_PUBLISH_LOCK_FD"] = str(descriptor)
    env["TOP10_PUBLISH_DIR_LOCK_FD"] = str(directory_descriptor)
    try:
        child = subprocess.Popen(
            ["/bin/bash", str(wrapper), *sys.argv[2:]], env=env,
            start_new_session=True, pass_fds=(descriptor, directory_descriptor),
        )
    except BaseException:
        os.close(descriptor)
        os.close(directory_descriptor)
        raise
    group = child.pid
    stopping = False
    stop_started: float | None = None

    def stop(_signal: int, _frame: object) -> None:
        nonlocal stopping, stop_started
        stopping = True
        if stop_started is None:
            stop_started = time.monotonic()
        try:
            os.killpg(group, signal.SIGTERM)
        except ProcessLookupError:
            pass

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    orphan_started: float | None = None
    while True:
        child_status = child.poll()
        try:
            os.killpg(group, 0)
            group_alive = True
        except ProcessLookupError:
            group_alive = False
        if child_status is not None and not group_alive:
            break
        if stopping and stop_started is None:
            stop_started = time.monotonic()
        if stop_started is not None and time.monotonic() - stop_started > 5:
            try:
                os.killpg(group, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if child_status is not None and group_alive and orphan_started is None:
            # shell 已結束但子程序未退出，給同一程序群最多 70 秒。
            orphan_started = time.monotonic()
        if orphan_started is not None and time.monotonic() - orphan_started > 65:
            try:
                os.killpg(group, signal.SIGTERM)
            except ProcessLookupError:
                pass
        if orphan_started is not None and time.monotonic() - orphan_started > 70:
            try:
                os.killpg(group, signal.SIGKILL)
            except ProcessLookupError:
                pass
        time.sleep(0.05)
    os.close(descriptor)
    os.close(directory_descriptor)
    return child.returncode if child.returncode is not None else 70


if __name__ == "__main__":
    raise SystemExit(main())
