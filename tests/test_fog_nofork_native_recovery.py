from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import signal
import stat
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RECOVERY_PATH = (
    PROJECT_ROOT
    / "tests/fixtures/fog_nofork_native"
    / "fog-nofork-native-recover-cycle1-20261007.py"
)


def load_recovery():
    spec = importlib.util.spec_from_file_location(
        "fog_nofork_native_recovery_20261007",
        RECOVERY_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FixtureRunner:
    @staticmethod
    def tree_manifest(root: Path) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for path in sorted(root.rglob("*")):
            relative = str(path.relative_to(root))
            info = os.lstat(path)
            if path.is_dir():
                rows.append({"path": relative, "kind": "dir"})
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            rows.append(
                {
                    "path": relative,
                    "kind": "file",
                    "size": info.st_size,
                    "sha256": digest,
                }
            )
        return rows

    @staticmethod
    def manifest_sha256(rows: list[dict[str, object]]) -> str:
        encoded = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def build_tree(root: Path) -> None:
    (root / "nested").mkdir(parents=True)
    (root / "first.txt").write_text("第一份固定證據\n", encoding="utf-8")
    (root / "nested/second.txt").write_text("第二份固定證據\n", encoding="utf-8")


def fixture_rename_no_replace(source: Path, destination: Path) -> None:
    if destination.exists() or destination.is_symlink():
        raise RuntimeError("fixture destination already exists")
    os.rename(source, destination)


def pin_fixture_root(
    module,
    monkeypatch: pytest.MonkeyPatch,
    root: Path,
    rows: list[dict[str, object]],
) -> Path:
    info = os.stat(root, follow_symlinks=False)
    quarantine = root.with_name(f".{root.name}.recovery-quarantine")
    monkeypatch.setattr(module, "ROOT", root)
    monkeypatch.setattr(module, "ROOT_DEVICE", info.st_dev)
    monkeypatch.setattr(module, "ROOT_INODE", info.st_ino)
    monkeypatch.setattr(module, "ROOT_MODE", stat.S_IMODE(info.st_mode))
    monkeypatch.setattr(module, "ROOT_TREE_SHA256", FixtureRunner.manifest_sha256(rows))
    monkeypatch.setattr(module, "ROOT_QUARANTINE", quarantine)
    monkeypatch.setattr(module, "rename_no_replace_path", fixture_rename_no_replace)
    return quarantine


def pin_fixture_marker(
    module,
    monkeypatch: pytest.MonkeyPatch,
    marker: Path,
    expected: dict[str, str],
    raw: bytes,
) -> Path:
    quarantine = marker.with_name(f".{marker.name}.recovery-quarantine")
    monkeypatch.setattr(module, "MARKER", marker)
    monkeypatch.setattr(module, "MARKER_QUARANTINE", quarantine)
    monkeypatch.setattr(module, "EXPECTED_MARKER", expected)
    monkeypatch.setattr(module, "MARKER_SHA256", hashlib.sha256(raw).hexdigest())
    monkeypatch.setattr(module, "rename_no_replace_path", fixture_rename_no_replace)
    return quarantine


def test_manifest_bound_quarantine_refuses_late_entry_before_rename(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_recovery()
    root = tmp_path / "owned-root"
    build_tree(root)
    rows = FixtureRunner.tree_manifest(root)
    quarantine = pin_fixture_root(module, monkeypatch, root, rows)
    identities = module.tree_identity_snapshot(root, rows)
    (root / "late.txt").write_text("未列入 frozen manifest\n", encoding="utf-8")

    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        with pytest.raises(RuntimeError, match="exact root tree changed before quarantine"):
            module.quarantine_exact_root(FixtureRunner, root_fd, rows, identities)
    finally:
        os.close(root_fd)

    assert not quarantine.exists()
    assert (root / "first.txt").is_file()
    assert (root / "nested/second.txt").is_file()
    assert (root / "late.txt").is_file()


def test_manifest_bound_quarantine_preserves_late_entry_added_after_rename(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_recovery()
    root = tmp_path / "owned-root"
    build_tree(root)
    rows = FixtureRunner.tree_manifest(root)
    quarantine = pin_fixture_root(module, monkeypatch, root, rows)
    identities = module.tree_identity_snapshot(root, rows)
    original_rename = module.rename_no_replace_path

    def rename_then_inject(source: Path, destination: Path) -> None:
        original_rename(source, destination)
        (destination / "late-after-rename.txt").write_text(
            "quarantine 後出現的未知內容\n",
            encoding="utf-8",
        )

    monkeypatch.setattr(module, "rename_no_replace_path", rename_then_inject)
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        with pytest.raises(RuntimeError, match="quarantined root tree changed"):
            module.quarantine_exact_root(FixtureRunner, root_fd, rows, identities)
    finally:
        os.close(root_fd)

    assert not root.exists()
    assert (quarantine / "first.txt").is_file()
    assert (quarantine / "nested/second.txt").is_file()
    assert (quarantine / "late-after-rename.txt").read_text(encoding="utf-8").startswith(
        "quarantine 後"
    )


def test_manifest_bound_quarantine_moves_and_preserves_only_the_frozen_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_recovery()
    root = tmp_path / "owned-root"
    build_tree(root)
    rows = FixtureRunner.tree_manifest(root)
    quarantine = pin_fixture_root(module, monkeypatch, root, rows)
    identities = module.tree_identity_snapshot(root, rows)

    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        result = module.quarantine_exact_root(FixtureRunner, root_fd, rows, identities)
    finally:
        os.close(root_fd)

    assert result["path"] == str(quarantine)
    assert result["tree_manifest_sha256"] == FixtureRunner.manifest_sha256(rows)
    assert not root.exists()
    assert (quarantine / "first.txt").read_text(encoding="utf-8") == "第一份固定證據\n"
    assert (quarantine / "nested/second.txt").read_text(encoding="utf-8") == "第二份固定證據\n"


def test_exact_marker_quarantine_refuses_replaced_inode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_recovery()
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    marker = git_dir / "marker.json"
    expected = {"nonce": "fixed", "status": "unknown"}
    raw = (json.dumps(expected, sort_keys=True) + "\n").encode("utf-8")
    marker.write_bytes(raw)
    quarantine = pin_fixture_marker(module, monkeypatch, marker, expected, raw)

    git_fd = os.open(git_dir, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        _, identity, observed_raw = module.read_marker_state(git_fd)
        marker.unlink()
        replacement = b'{"nonce":"replacement","status":"active"}\n'
        marker.write_bytes(replacement)
        with pytest.raises(RuntimeError, match="marker bytes changed"):
            module.quarantine_exact_marker(git_fd, identity, observed_raw)
    finally:
        os.close(git_fd)

    assert marker.read_bytes() == replacement
    assert not quarantine.exists()


def test_exact_marker_quarantine_moves_and_preserves_verified_marker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_recovery()
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    marker = git_dir / "marker.json"
    expected = {"nonce": "fixed", "status": "unknown"}
    raw = (json.dumps(expected, sort_keys=True) + "\n").encode("utf-8")
    marker.write_bytes(raw)
    quarantine = pin_fixture_marker(module, monkeypatch, marker, expected, raw)

    git_fd = os.open(git_dir, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        _, identity, observed_raw = module.read_marker_state(git_fd)
        result = module.quarantine_exact_marker(git_fd, identity, observed_raw)
    finally:
        os.close(git_fd)

    assert not marker.exists()
    assert result["path"] == str(quarantine)
    assert result["sha256"] == hashlib.sha256(raw).hexdigest()
    assert quarantine.read_bytes() == raw


def test_exact_marker_quarantine_never_unlinks_new_active_marker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_recovery()
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    marker = git_dir / "marker.json"
    expected = {"nonce": "fixed", "status": "unknown"}
    raw = (json.dumps(expected, sort_keys=True) + "\n").encode("utf-8")
    replacement = b'{"nonce":"new","status":"active"}\n'
    marker.write_bytes(raw)
    quarantine = pin_fixture_marker(module, monkeypatch, marker, expected, raw)
    original_rename = module.rename_no_replace_path

    def rename_then_recreate(source: Path, destination: Path) -> None:
        original_rename(source, destination)
        if source == marker:
            marker.write_bytes(replacement)

    monkeypatch.setattr(module, "rename_no_replace_path", rename_then_recreate)
    git_fd = os.open(git_dir, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        _, identity, observed_raw = module.read_marker_state(git_fd)
        with pytest.raises(RuntimeError, match="new active marker appeared"):
            module.quarantine_exact_marker(git_fd, identity, observed_raw)
    finally:
        os.close(git_fd)

    assert marker.read_bytes() == replacement
    assert quarantine.read_bytes() == raw


def test_exact_marker_restore_is_create_only_and_verified(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_recovery()
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    marker = git_dir / "marker.json"
    expected = {"nonce": "fixed", "status": "unknown"}
    raw = (json.dumps(expected, sort_keys=True) + "\n").encode("utf-8")
    monkeypatch.setattr(module, "MARKER", marker)
    monkeypatch.setattr(module, "EXPECTED_MARKER", expected)
    monkeypatch.setattr(module, "MARKER_SHA256", hashlib.sha256(raw).hexdigest())

    git_fd = os.open(git_dir, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        assert module.restore_exact_marker(git_fd, raw) is True
        observed, _, observed_raw = module.read_marker_state(git_fd)
        assert observed == expected
        assert observed_raw == raw
        assert module.restore_exact_marker(git_fd, raw) is False
    finally:
        os.close(git_fd)


def test_interrupt_handler_routes_signal_to_failure_exception() -> None:
    module = load_recovery()
    previous = module.install_interrupt_handlers()
    try:
        handler = signal.getsignal(signal.SIGTERM)
        assert callable(handler)
        with pytest.raises(module.RecoveryInterrupted, match="signal"):
            handler(signal.SIGTERM, None)
    finally:
        module.restore_interrupt_handlers(previous)


def test_lifecycle_hash_failure_happens_before_lifecycle_import() -> None:
    script = f"""
import importlib.util
import sys
from pathlib import Path

path = Path({str(RECOVERY_PATH)!r})
spec = importlib.util.spec_from_file_location('isolated_recovery_order_test', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

original_read = module.read_verified_bytes
def refuse(path, expected):
    if path == module.HOST_CAPACITY_SENSOR_PATH:
        return b'# fixture: verified host source is not executed before lifecycle validation\\n'
    if path == module.LIFECYCLE_PATH:
        raise RuntimeError('fixture lifecycle drift')
    return original_read(path, expected)

module.read_verified_bytes = refuse
try:
    module.load_runtime_modules()
except RuntimeError as error:
    assert str(error) == 'fixture lifecycle drift'
else:
    raise AssertionError('expected lifecycle drift refusal')
assert 'scripts.tmp_artifact_lifecycle' not in sys.modules
"""
    completed = subprocess.run(
        [sys.executable, "-I", "-B", "-c", script],
        text=True,
        capture_output=True,
        check=False,
        cwd=PROJECT_ROOT,
    )
    assert completed.returncode == 0, completed.stderr


def test_success_receipt_is_written_only_after_lock_release(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_recovery()
    project = tmp_path / "repo"
    git_dir = project / ".git"
    volume = tmp_path / "volume"
    root = volume / "owned-root"
    git_dir.mkdir(parents=True)
    root.mkdir(parents=True)
    dry_run_dir = project / "dry-run"
    root_quarantine = volume / ".owned-root.recovery-quarantine"
    marker_path = git_dir / "marker.json"
    marker_quarantine = git_dir / ".marker.json.recovery-quarantine"
    recovered_evidence = project / "recovered-evidence"
    events: list[str] = []

    class FakeLifecycle:
        @staticmethod
        def acquire_repo_lock(_project, _purpose, _limits):
            descriptor = os.open(git_dir, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            return {"fd": descriptor, "target": git_dir}

        @staticmethod
        def release_repo_lock(lock):
            events.append("release")
            os.close(int(lock["fd"]))
            return True

    runner = SimpleNamespace(
        VOLUME=volume,
        check_volume=lambda _fd, _identity: {"volume": "fixture"},
    )

    def load_modules():
        module.lifecycle = FakeLifecycle
        return FakeLifecycle, runner

    def prepare(path: Path):
        path.mkdir()
        return path, os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)

    def write(_directory: int, name: str, _payload) -> None:
        events.append(f"write:{name}")

    def write_terminal(_directory: int, _payload) -> dict[str, object]:
        events.append("write:terminal-result")
        return {"result_name": "result.json"}

    rows = [{"path": "fixed.txt", "kind": "file", "size": 1, "sha256": "x"}]
    identities = {"fixed.txt": {"device": 1, "inode": 2, "mode": 0o600, "kind": "file", "size": 1}}
    marker = {"nonce": "fixed"}
    marker_identity = {"device": 1, "inode": 3, "size": 4, "mode": 0o600}
    marker_raw = b"fixed"

    monkeypatch.setattr(module, "PROJECT", project)
    monkeypatch.setattr(module, "ROOT", root)
    monkeypatch.setattr(module, "ROOT_QUARANTINE", root_quarantine)
    monkeypatch.setattr(module, "MARKER", marker_path)
    monkeypatch.setattr(module, "MARKER_QUARANTINE", marker_quarantine)
    monkeypatch.setattr(module, "RECOVERED_EVIDENCE", recovered_evidence)
    monkeypatch.setattr(module, "DRY_RUN_DIR", dry_run_dir)
    monkeypatch.setattr(module, "EXPECTED_MARKER", marker)
    monkeypatch.setattr(module, "verify_v1_freeze", lambda: {"fixture": "ok"})
    monkeypatch.setattr(module, "verify_failed_receipt", lambda: {"status": "fixture"})
    monkeypatch.setattr(module, "load_runtime_modules", load_modules)
    monkeypatch.setattr(
        module,
        "verify_marker",
        lambda _lock, _expected=None: (marker, marker_identity, marker_raw),
    )
    monkeypatch.setattr(
        module,
        "verify_root",
        lambda _runner, _root_fd: ({"root": "fixture"}, rows, identities),
    )
    monkeypatch.setattr(module, "observe_no_processes", lambda: {"status": "fixture"})
    monkeypatch.setattr(module, "prepare_receipt_dir", prepare)
    monkeypatch.setattr(module, "write_receipt", write)
    monkeypatch.setattr(module, "write_terminal_receipt", write_terminal)
    monkeypatch.setattr(
        module,
        "read_marker_state",
        lambda _git_fd: (marker, marker_identity, marker_raw),
    )

    assert module.main(["--dry-run", "--owner-authorization-ref", "fixture"]) == 0
    assert events.index("release") < events.index("write:terminal-result")
