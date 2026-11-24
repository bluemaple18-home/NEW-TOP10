"""驗證入口的薄邊界；卷身分與生命週期仍由 ai-core 管理。"""

from __future__ import annotations

from contextlib import contextmanager
import importlib
import hashlib
import fcntl
import json
import os
from pathlib import Path
import sys
import time
from datetime import datetime
from types import SimpleNamespace


def core_module(name: str):
    core = Path(os.environ.get("AI_CORE_DIR", str(Path.home() / "ai-core")))
    sys.path.insert(0, str(core / "scripts"))
    try:
        return importlib.import_module(name)
    finally:
        sys.path.pop(0)


def lexical_path(path: Path, volume: Path, device: int) -> Path:
    """首次寫入前逐層拒絕 symlink、內建與跨 device；不建立目錄。"""
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts or not path.is_relative_to(volume):
        raise ValueError("寫入目標必須是外接卷內的絕對路徑")
    current = volume
    for part in path.relative_to(volume).parts:
        current /= part
        if current.is_symlink():
            raise ValueError("外接寫入路徑不得含 symlink")
        if current.exists() and current.stat().st_dev != device:
            raise ValueError("外接寫入路徑 device 不符")
    return path


def readonly_source(path: Path) -> Path:
    """唯讀 source 可在內建，但不能以 resolve 隱藏 symlink 或相對路徑。"""
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts or path.resolve(strict=True) != path:
        raise ValueError("source 必須是無 symlink 的 canonical 絕對路徑")
    return path


@contextmanager
def external_paths(*paths: Path, reserve_bytes: int = 0):
    """沿 ManagedCache 唯讀取樣，不自行建立 cache 或替代卷。"""
    contract = owned_write_contract(Path(os.environ.get("TMP_ARTIFACT_ROOT", "")))
    if contract is not None:
        # admission 是 parent 真實收據，不是 child 的即時容量；parent 原監測持續停損。
        snapshot = contract["parent_capacity_admission"]
        if type(reserve_bytes) is not int or reserve_bytes < 0 or (
                snapshot["effective_available_bytes"] < snapshot["required_available_bytes"] + reserve_bytes):
            raise ValueError("parent admission 未涵蓋要求的保留量")
        volume = Path(snapshot["volume"])
        for path in paths:
            lexical_path(path, volume, snapshot["device"])
        yield SimpleNamespace(volume=volume, device=snapshot["device"])
        return
    environment = core_module("cache_tool").load_environment(dict(os.environ))
    cache = core_module("runtime_cache_capacity_gate").ManagedCache.from_env(environment, scope="volume")
    try:
        snapshot = cache.sample()
        if snapshot["effective_available_bytes"] < snapshot["required_available_bytes"] + reserve_bytes:
            raise ValueError("外接卷容量不足")
        for path in paths:
            lexical_path(path, cache.volume, cache.device)
        yield cache
    finally:
        cache.close()


def owned_validation_paths(*paths: Path) -> Path:
    """確認 child 仍處於既有 lifecycle 的 active root；不取得清理權。"""
    root = Path(os.environ.get("TMP_ARTIFACT_ROOT", ""))
    owner = Path(os.environ.get("AI_CORE_EXTERNAL_DEV_REPO", ""))
    if os.environ.get("AI_CORE_TMP_ARTIFACT_ACTIVE") != "1" or not root.is_absolute() or not owner.is_absolute():
        raise ValueError("驗證寫入必須由 tmp_artifact_lifecycle --external-only 管理")
    lifecycle = core_module("tmp_artifact_lifecycle")
    with external_paths(root, owner, *paths) as cache:
        if root.parent != lifecycle.MANAGED_TMP_PARENT or not root.is_dir():
            raise ValueError("驗證 root 不是受管外接 sandbox")
        identity = lifecycle.repo_identity(owner)
        common = Path(identity["git_common_dir"])
        lexical_path(common, cache.volume, cache.device)
        manifest_path = root / ".tmp-artifact-manifest.json"
        marker_path = common / lifecycle.ISOLATION_MARKER_NAME
        for path in (manifest_path, marker_path):
            lexical_path(path, cache.volume, cache.device)
            if path.stat().st_size > 65536:
                raise ValueError("lifecycle owner 證據超限")
        manifest = json.loads(manifest_path.read_text())
        marker = json.loads(marker_path.read_text())
        if (manifest.get("root") != str(root) or manifest.get("repo_identity") != identity
                or not manifest.get("owner_nonce") or manifest.get("expires_at", 0) <= time.time()
                or marker.get("root") != str(root) or marker.get("status") != "active"
                or marker.get("git_common_dir") != str(common)):
            raise ValueError("lifecycle owner 身分或 active 契約不符")
        for path in paths:
            if not path.is_relative_to(root):
                raise ValueError("驗證目標不屬於本輪 owned sandbox；未知 output 保留")
    return root


def owned_write_contract(sandbox: Path) -> dict | None:
    """沿既有 owner marker 查 exact scope；此處核契約，原生隔離仍須另驗。"""
    owner = Path(os.environ.get("AI_CORE_EXTERNAL_DEV_REPO", ""))
    if not owner.is_absolute():
        return None
    lifecycle = core_module("tmp_artifact_lifecycle")
    common = Path(lifecycle.repo_identity(owner)["git_common_dir"])
    marker_path = common / lifecycle.ISOLATION_MARKER_NAME
    if marker_path.is_symlink() or marker_path.stat().st_size > 65536:
        raise ValueError("exact-root marker 無效")
    marker = json.loads(marker_path.read_text())
    contract = marker.get("write_confinement")
    if contract is None:
        return None
    root = Path(os.environ.get("TMP_ARTIFACT_ROOT", ""))
    gate = core_module("runtime_cache_capacity_gate")
    volume = gate.MANAGED_VOLUME
    if (os.environ.get("AI_CORE_TMP_ARTIFACT_ACTIVE") != "1" or sandbox != root
            or root.parent != lifecycle.MANAGED_TMP_PARENT or not volume.is_mount()
            or volume.resolve(strict=True) != volume):
        raise ValueError("exact-root 缺少原生掛載或 active owner")
    native = gate.mounted_identity(volume)
    for path in (root, common, root / ".tmp-artifact-manifest.json", marker_path):
        lexical_path(path, volume, native["device"])
    if (root / ".tmp-artifact-manifest.json").stat().st_size > 65536:
        raise ValueError("exact-root manifest 超限")
    manifest = json.loads((root / ".tmp-artifact-manifest.json").read_text())
    info = root.stat()
    profile = gate.ManagedCache.owned_root_profile(root)
    identity = lifecycle.repo_identity(owner)
    if (common.is_relative_to(root) or not isinstance(contract, dict)
            or marker.get("root") != str(root) or marker.get("status") != "active"
            or marker.get("git_common_dir") != str(common)
            or manifest.get("root") != str(root) or manifest.get("repo_identity") != identity
            or contract.get("scope") != "owned-root-only.v1"
            or contract.get("root") != str(root)
            or contract.get("root_device") != info.st_dev or contract.get("root_inode") != info.st_ino
            or contract.get("owner_nonce") != manifest["owner_nonce"]
            or contract.get("profile_sha256") != hashlib.sha256(profile.encode()).hexdigest()):
        raise ValueError("exact-root owner/scope/profile 契約不符")
    admission = contract.get("parent_capacity_admission")
    if not isinstance(admission, dict):
        raise ValueError("exact-root 缺少 parent capacity admission")
    positive = ("max_bytes", "max_files", "required_available_bytes", "effective_available_bytes",
                "container_free_bytes", "reserve_bytes")
    if (admission.get("decision") != "PASS" or admission.get("scope") != "cache"
            or admission.get("volume") != str(volume) or admission.get("root") != str(gate.MANAGED_ROOT)
            or admission.get("volume_uuid") != native["VolumeUUID"]
            or admission.get("foundation_volume_uuid") != native["VolumeUUID"]
            or admission.get("device") != native["device"]
            or any(type(admission.get(k)) is not int or not 0 < admission[k] <= sys.maxsize for k in positive)
            or any(type(admission.get(k)) is not int or not 0 <= admission[k] <= sys.maxsize
                   for k in ("remaining_budget_bytes", "reserved_other_bytes"))):
        raise ValueError("exact-root parent admission 數值／卷身分不符")
    foundation = admission.get("foundation", {})
    if (not isinstance(foundation, dict) or foundation.get("source") != "macos_foundation_important_usage"
            or foundation.get("total_bytes") != native["TotalSize"]
            or any(type(foundation.get(k)) is not int or not 0 < foundation[k] <= native["TotalSize"]
                   for k in ("physical_available_bytes", "admission_available_bytes"))
            or admission["effective_available_bytes"] != min(foundation["admission_available_bytes"], admission["container_free_bytes"])
            or admission["required_available_bytes"] != admission["reserve_bytes"] + admission["reserved_other_bytes"] + admission["remaining_budget_bytes"]
            or admission["effective_available_bytes"] < admission["required_available_bytes"]):
        raise ValueError("exact-root parent admission 容量契約不符")
    captured = datetime.fromisoformat(admission["captured_at"]).timestamp()
    expires = contract.get("expires_at")
    if (type(expires) is not int or expires != manifest.get("expires_at") or expires <= time.time()
            or not manifest.get("created_at", 0) <= captured < expires or captured > time.time() + 1
            or type(contract.get("parent_pid")) is not int or contract["parent_pid"] <= 1):
        raise ValueError("exact-root parent admission 已過期或時間／監督契約不符")
    parent = lifecycle.darwin_process_info(contract["parent_pid"])
    if (parent is None or [parent.start_seconds, parent.start_microseconds] != contract.get("parent_start")
            or parent.status == 5):
        raise ValueError("exact-root lifecycle parent 身分已改變")
    ancestor = os.getpid()
    for _ in range(64):
        if ancestor == parent.pid:
            break
        info = lifecycle.darwin_process_info(ancestor)
        if info is None or info.ppid <= 1 or info.ppid == ancestor:
            raise ValueError("exact-root child 不屬於原 lifecycle parent")
        ancestor = info.ppid
    else:
        raise ValueError("exact-root parent ancestry 超限")
    # 原 owner directory flock 不是新 lease；只接受 Busy，取得鎖代表監督已離開。
    fd = os.open(common, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        control = os.fstat(fd)
        if (control.st_dev, control.st_ino) != (contract.get("control_device"), contract.get("control_inode")):
            raise ValueError("exact-root parent control directory 已改變")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            pass
        else:
            fcntl.flock(fd, fcntl.LOCK_UN)
            raise ValueError("exact-root parent 未持有 lifecycle lock")
    finally:
        os.close(fd)
    destination = Path(contract.get("evidence_destination", ""))
    preserve = contract.get("preserve")
    if (not destination.is_absolute() or destination == owner or not destination.is_relative_to(owner)
            or destination.is_relative_to(root) or not isinstance(preserve, list) or not preserve
            or any(not isinstance(p, str) or Path(p).is_absolute() or ".." in Path(p).parts
                   or Path(p).name in {"", "."} for p in preserve)):
        raise ValueError("exact-root evidence 契約不符")
    lexical_path(destination, volume, native["device"])
    if destination.exists():
        raise ValueError("exact-root evidence destination 已存在")
    return contract
