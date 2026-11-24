"""一般目錄入口與真正 child 等待期間的 cache 停損契約。"""
import os
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest
from app.external_cache import ExternalCache, ExternalCacheError


def test_directory_contract_needs_no_image_and_keeps_job_accounting(tmp_path, monkeypatch):
    volume = tmp_path / "VibeCode"
    root = volume / "Development/Managed-Caches/ai-core"
    root.mkdir(parents=True)
    calls = []
    managed = SimpleNamespace(volume=volume, root=root, device=root.stat().st_dev,
        sample=lambda: calls.append("sample") or {"decision": "PASS", "volume_uuid": "volume-uuid", "device": root.stat().st_dev, "aggregate": {"logical_bytes": 0, "allocated_bytes": 0, "files": 0}},
        materialize=lambda paths: [path.mkdir(parents=True, exist_ok=True) for path in paths],
        close=lambda: calls.append("close"))
    monkeypatch.setitem(sys.modules, "runtime_cache_capacity_gate", SimpleNamespace(ManagedCache=SimpleNamespace(from_env=lambda: managed)))
    for key in ("AI_CORE_CACHE_IMAGE", "AI_CORE_CACHE_BACKING_VOLUME", "AI_CORE_CACHE_BACKING_UUID"):
        monkeypatch.delenv(key, raising=False)
    for key, value in {"AI_CORE_DIR": str(tmp_path / "core"), "AI_CORE_CACHE_MODE": "directory", "AI_CORE_CACHE_VOLUME": str(volume), "AI_CORE_CACHE_VOLUME_UUID": "volume-uuid", "AI_CORE_CACHE_ROOT": str(root), "AI_CORE_CACHE_MAX_BYTES": str(2 * 1024**3), "AI_CORE_CACHE_MAX_FILES": "50000", "AI_CORE_CACHE_RESERVED_OTHER_BYTES": "11195506688"}.items():
        monkeypatch.setenv(key, value)
    real_mount = Path.is_mount
    monkeypatch.setattr(Path, "is_mount", lambda path: path == volume or real_mount(path))
    cache = ExternalCache(tmp_path / "project", "daily", 4096, 32, 86400)
    try:
        assert cache.root.is_relative_to(root / "top10")
        cache.root.mkdir(parents=True)
        (cache.root / "owned.bin").write_bytes(b"cache")
        result = cache.sample()
        assert result["decision"] == "PASS"
        assert result["image_contract"] is None
        assert result["managed_contract"]["volume_uuid"] == "volume-uuid"
        assert result["roots"][0]["bytes"] >= 5
        assert len(result["roots"]) == 1
    finally:
        cache.close()
    assert "sample" in calls and "close" in calls


def test_managed_wait_samples_between_waits_and_stops_on_drift():
    import subprocess
    from app.storage_safety import _wait_with_managed_cache
    calls = []
    def wait(*, timeout):
        calls.append(timeout)
        raise subprocess.TimeoutExpired("owned-child", timeout)
    count = [0]
    def checked():
        count[0] += 1
        if count[0] == 2:
            raise ExternalCacheError("EXTERNAL_CACHE_MANAGED_ADMISSION_DENIED")
    with pytest.raises(ExternalCacheError, match="ADMISSION_DENIED"):
        _wait_with_managed_cache(SimpleNamespace(wait=wait), 30, SimpleNamespace(sample=checked))
    assert count[0] == 2
    assert calls == [1.0]
