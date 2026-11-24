"""exact-root 的有界介面負例；native 首次 apply 由外接 runner 獨立驗證。"""
import hashlib
import json
import os
from dataclasses import replace
from pathlib import Path
import subprocess
import time
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app import storage_safety as guard
from scripts import run_external_fog_revalidation as launcher
from scripts.storage_validation import boundary
from tests.test_fog_shared_source import shared
from tests.test_storage_lifecycle_boundaries import tmp_path


def trusted(shared):
    _, root, marker, contract = shared
    return guard.load_trusted_validation_entrypoint(root, launcher.JOB, json.loads(marker.read_text()), contract)


def test_immutable_bytes_survive_entrypoint_mutation(shared):
    value = trusted(shared)
    body = b"from pathlib import Path\nimport sys\nassert __name__=='__main__'\nPath(sys.argv[1]).write_text(__file__)\n"
    value.entrypoint_path.write_bytes(body)
    target = value.sandbox_root / "result"
    value = replace(value, entrypoint_sha256=hashlib.sha256(body).hexdigest(), argv=(str(target),))
    command = guard._immutable_validation_command(value)
    value.entrypoint_path.write_text("raise RuntimeError('mutable file executed')")
    subprocess.run(command, check=True)
    assert target.read_text() == str(value.entrypoint_path)
    assert command[1:4] == ["-I", "-B", "-c"]


@pytest.mark.parametrize("case", ["digest", "bytes", "argv"])
def test_immutable_limits_and_digest(shared, case):
    value = trusted(shared)
    if case == "digest":
        value.entrypoint_path.write_text("changed")
    elif case == "bytes":
        value.entrypoint_path.write_bytes(b"#" * (guard.IMMUTABLE_ENTRYPOINT_MAX_BYTES + 1))
    else:
        value = replace(value, argv=("x" * guard.IMMUTABLE_COMMAND_MAX_BYTES,))
    with pytest.raises(guard.UntrustedValidationEntrypoint):
        guard._immutable_validation_command(value)


@pytest.fixture
def parent_contract(tmp_path, monkeypatch):
    root = tmp_path / "root"
    root.mkdir()
    owner = tmp_path / "owner"
    common = owner / ".git"
    common.mkdir(parents=True)
    monkeypatch.setenv("AI_CORE_EXTERNAL_DEV_REPO", str(owner))
    monkeypatch.setenv("TMP_ARTIFACT_ROOT", str(root))
    monkeypatch.setenv("AI_CORE_TMP_ARTIFACT_ACTIVE", "1")
    lifecycle = boundary.core_module("tmp_artifact_lifecycle")
    gate = boundary.core_module("runtime_cache_capacity_gate")
    identity = {"git_common_dir": str(common), "root": str(owner)}
    monkeypatch.setattr(lifecycle, "repo_identity", lambda _: identity)
    monkeypatch.setattr(lifecycle, "MANAGED_TMP_PARENT", tmp_path)
    monkeypatch.setattr(gate, "MANAGED_VOLUME", tmp_path)
    monkeypatch.setattr(Path, "is_mount", lambda _: True)
    monkeypatch.setattr(gate, "mounted_identity", lambda _: dict(VolumeUUID="uuid", TotalSize=10000, device=root.stat().st_dev))
    now = int(time.time())
    manifest = dict(owner_nonce="nonce", root=str(root), repo_identity=identity, created_at=now - 5, expires_at=now + 100)
    (root / ".tmp-artifact-manifest.json").write_text(json.dumps(manifest))
    profile = gate.ManagedCache.owned_root_profile(root)
    contract = dict(scope="owned-root-only.v1", root=str(root), root_device=root.stat().st_dev,
                    root_inode=root.stat().st_ino, owner_nonce="nonce",
                    profile_sha256=hashlib.sha256(profile.encode()).hexdigest(),
                    evidence_destination=str(owner / "export"), preserve=["validation_evidence"],
                    expires_at=now + 100, parent_pid=os.getpid(), parent_start=[100, 0],
                    control_device=common.stat().st_dev, control_inode=common.stat().st_ino)
    contract["parent_capacity_admission"] = dict(decision="PASS", scope="cache", volume=str(tmp_path),
        root=str(gate.MANAGED_ROOT), volume_uuid="uuid", foundation_volume_uuid="uuid", device=root.stat().st_dev,
        max_bytes=100, max_files=100, reserve_bytes=100, reserved_other_bytes=0, remaining_budget_bytes=100,
        required_available_bytes=200, effective_available_bytes=9000, container_free_bytes=9000,
        captured_at=datetime.now(timezone.utc).isoformat(), foundation=dict(source="macos_foundation_important_usage",
        total_bytes=10000, physical_available_bytes=8000, admission_available_bytes=9000))
    monkeypatch.setattr(lifecycle, "darwin_process_info", lambda pid: SimpleNamespace(pid=pid, start_seconds=100, start_microseconds=0, status=2))
    def busy(*_):
        raise BlockingIOError()
    monkeypatch.setattr(boundary.fcntl, "flock", busy)
    marker = dict(root=str(root), status="active", git_common_dir=str(common), write_confinement=contract)
    path = common / lifecycle.ISOLATION_MARKER_NAME
    path.write_text(json.dumps(marker))
    return root, path, marker


@pytest.mark.parametrize("case", ["scope", "root", "digest", "nonce", "device", "inode", "destination", "preserve"])
def test_owner_scope_rejects_fake_contract(parent_contract, case):
    root, path, marker = parent_contract
    contract = marker["write_confinement"]
    assert boundary.owned_write_contract(root) == contract
    field = {"digest": "profile_sha256", "nonce": "owner_nonce", "device": "root_device",
             "inode": "root_inode", "destination": "evidence_destination"}.get(case, case)
    contract[field] = ["../outside"] if case == "preserve" else "invalid"
    path.write_text(json.dumps(marker))
    with pytest.raises(ValueError):
        boundary.owned_write_contract(root)


@pytest.mark.parametrize("case", ["status", "uuid", "device", "budget", "capacity", "expiry", "parent", "lock", "control"])
def test_parent_admission_rejects_invalid_authority(parent_contract, monkeypatch, case):
    root, path, marker = parent_contract
    contract = marker["write_confinement"]
    assert boundary.owned_write_contract(root) == contract
    admission = contract["parent_capacity_admission"]
    if case == "status": admission["decision"] = "FAIL"
    elif case == "uuid": admission["volume_uuid"] = "other"
    elif case == "device": admission["device"] = -1
    elif case == "budget": admission["max_bytes"] = float("inf")
    elif case == "capacity": admission["effective_available_bytes"] = 1
    elif case == "expiry": contract["expires_at"] = 1
    elif case == "parent": contract["parent_start"] = [99, 0]
    elif case == "control": contract["control_inode"] = -1
    else: monkeypatch.setattr(boundary.fcntl, "flock", lambda *_: None)
    path.write_text(json.dumps(marker))
    with pytest.raises(ValueError): boundary.owned_write_contract(root)


def test_exact_child_uses_parent_admission_without_second_sample(parent_contract, monkeypatch):
    root, _, _ = parent_contract
    gate = boundary.core_module("runtime_cache_capacity_gate")
    monkeypatch.setattr(gate.ManagedCache, "from_env", lambda *_a, **_k: pytest.fail("不得另立 capacity authority"))
    with boundary.external_paths(root) as context:
        assert context.device == root.stat().st_dev


def test_native_group_permission_error_is_not_empty(monkeypatch):
    import ctypes
    import errno
    lifecycle = boundary.core_module("tmp_artifact_lifecycle")
    def denied(*_):
        ctypes.set_errno(errno.EPERM)
        return 0
    monkeypatch.setattr(lifecycle, "darwin_libproc", lambda: SimpleNamespace(proc_listpids=denied))
    with pytest.raises(RuntimeError):
        guard._native_process_ids(2, os.getpid())


def test_native_rss_short_read_is_not_zero(monkeypatch):
    lifecycle = boundary.core_module("tmp_artifact_lifecycle")
    monkeypatch.setattr(lifecycle, "darwin_libproc", lambda: SimpleNamespace(proc_pidinfo=lambda *_: 0))
    monkeypatch.setattr(guard, "_native_process_info", lambda _: SimpleNamespace(start_seconds=1, start_microseconds=0))
    assert guard._native_process_tree_rss(os.getpid()) == (None, ())


def test_claimed_scope_still_requires_native_probe(shared, monkeypatch):
    source, root, _, _ = shared
    monkeypatch.setattr(boundary, "owned_write_contract", lambda _: {"scope": "owned-root-only.v1"})
    def deny(*_):
        raise RuntimeError("VALIDATION_INHERITED_PROBE_FAILED")
    monkeypatch.setattr(guard, "_inherited_validation_probe", deny)
    with pytest.raises(RuntimeError, match="INHERITED"):
        guard._validation_spawn_command(root, source, ["ignored"])


@pytest.mark.parametrize("case", ["destination", "preserve", "size", "symlink", "success"])
def test_exact_evidence_stays_owned(tmp_path, monkeypatch, case):
    root = tmp_path / "root"
    source = root / launcher.EVIDENCE_DIR
    source.mkdir(parents=True)
    destination = tmp_path / "export"
    monkeypatch.setenv("TMP_ARTIFACT_ROOT", str(root))
    contract = {"evidence_destination": str(destination), "preserve": [launcher.EVIDENCE_DIR]}
    monkeypatch.setattr(launcher, "owned_write_contract", lambda _: contract)
    monkeypatch.setattr(launcher, "owned_validation_paths", lambda _: root)
    if case == "destination":
        contract["evidence_destination"] = str(tmp_path / "other")
    elif case == "preserve":
        contract["preserve"] = ["elsewhere"]
    elif case == "size":
        with (source / "oversize").open("wb") as stream:
            stream.truncate(8 * 1024**2 + 1)
    elif case == "symlink":
        (source / "link").symlink_to(tmp_path)
    if case == "success":
        (source / "receipt.json").write_text("{}")
        launcher.publish_evidence(source, destination)
    else:
        with pytest.raises(ValueError):
            launcher.publish_evidence(source, destination)
    assert not destination.exists()
