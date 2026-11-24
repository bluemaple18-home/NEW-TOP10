#!/usr/bin/env python3
"""只處理 2026-10-07 cycle-1 exact unknown root；不提供通用 recovery authority。"""

from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import importlib.machinery
import json
import os
import platform
import signal
import stat
import subprocess
import sys
import types
import uuid
from pathlib import Path
from typing import Any


AI_CORE = Path(os.environ.get("AI_CORE_DIR", str(Path.home() / "ai-core")))
PROJECT = Path(__file__).resolve().parents[3]
EVIDENCE_BASE = Path(__file__).resolve().parent
ROOT = Path(
    "/Volumes/VibeCode/"
    "ai-core-top10-fog-nofork-c1-6f543c2fef39498695e1cf06491c0341"
)
MARKER = PROJECT / ".git/.ai-core-tmp-artifact-isolation.json"
FAILED_RECEIPT = EVIDENCE_BASE / "fog-nofork-native-cycle-1-20261007.json"
FAILED_LOG = EVIDENCE_BASE / "fog-nofork-native-cycle-1-20261007.log"
V1_RUNNER = EVIDENCE_BASE / "fog-nofork-native-runner-v1-20261007.py"
V1_FREEZE = EVIDENCE_BASE / "fog-nofork-native-freeze-v1-20261007.json"
CURRENT_RUNNER = EVIDENCE_BASE / "fog-nofork-native-runner-20261007.py"
SCRIPTS_DIR = AI_CORE / "scripts"
HOST_CAPACITY_SENSOR_PATH = SCRIPTS_DIR / "host_capacity_sensor.py"
LIFECYCLE_PATH = AI_CORE / "scripts/tmp_artifact_lifecycle.py"
RECOVERED_EVIDENCE = (
    EVIDENCE_BASE / "fog-nofork-native-cycle-1-recovered-20261007"
)
DRY_RUN_DIR = EVIDENCE_BASE / "fog-nofork-native-cycle-1-recovery-dry-run-r5-20261007"
EXECUTE_DIR = EVIDENCE_BASE / "fog-nofork-native-cycle-1-recovery-execute-r2-20261007"

SOURCE_COMMIT = "25348435c5049c5d2ac486fe504c8c0abd4d19fd"
ROOT_DEVICE = 16777240
ROOT_INODE = 2951465
ROOT_MODE = 0o700
ROOT_TREE_SHA256 = "ae890e934b069cae30772f9fde531f11492f25e0d93e7ed38a96d63b6b9382a9"
ROOT_ENTRY_COUNT = 45
ROOT_FILE_COUNT = 31
ROOT_LOGICAL_BYTES = 430122
PRESERVE_TREE_SHA256 = "c282a08a1ad7569014f383c8146f035f8d037944c63ed02c85b65d1200820688"
PRESERVE_ENTRY_COUNT = 41
PRESERVE_FILE_COUNT = 30
PRESERVE_LOGICAL_BYTES = 429731
MANIFEST_SHA256 = "c62ab55cbea9ae7ea8214eefa1dd10cef6c04645a68d6930c0c622771f05fac1"
MARKER_SHA256 = "bc524d088ecf9ffef10f2d51d744d304fbb3756c3e236d63e075217bbddc81b2"
FAILED_RECEIPT_SHA256 = "fb917f082888f64fc309a8c11b03e6f22ad64f0c6e27cb23b02949c141afef74"
FAILED_LOG_SHA256 = "0c9472f739c949eb0336109911f3be07baf46d4301560643425c32f055f7e6cb"
V1_RUNNER_SHA256 = "b1d612fa199216159bc72261021860b114b8c3d1d980ae36bbd711ad5f1718e2"
V1_FREEZE_SHA256 = "868a106470bd4d09342404d82c698d4b1d8033a4ce719d83ddcc71fed5555f68"
CURRENT_RUNNER_SHA256 = "18dccf5e5711d5c05c32f13cb1631751c18bc18c93673ebdff262bba82b26512"
HOST_CAPACITY_SENSOR_SHA256 = "1d02919680653cbb2e656833953389e9308dd7914e5ea182f0284a1ab95ad892"
LIFECYCLE_SHA256 = "1f03d196e07b286792524e7fff9bd784135013d8af18ab90452e1a8080a89d94"
HISTORICAL_PIDS = (19565, 19567)
RUN_NONCE = "e33dad91b3894ab8a6c91493a8c3e17f"
ROOT_QUARANTINE = ROOT.with_name(f".{ROOT.name}.recovered-quarantine-{RUN_NONCE}")
MARKER_QUARANTINE = MARKER.with_name(
    f"{MARKER.name}.recovered-quarantine-{RUN_NONCE}"
)
EXPECTED_MARKER = {
    "git_common_dir": str(PROJECT / ".git"),
    "purpose": "top10-fog-nofork-c1",
    "root": str(ROOT),
    "run_nonce": RUN_NONCE,
    "status": "unknown",
    "version": 1,
}
EXPECTED_MANIFEST = {
    "created_at": 1791308252,
    "expires_at": 1791308552,
    "max_bytes": 67108864,
    "max_file_count": 250,
    "owner_nonce": "332c902f27304306894dcec5ce840ebe",
    "purpose": "top10-fog-nofork-c1",
    "repo_identity": {
        "git_common_dir": str(PROJECT / ".git"),
        "root": str(PROJECT),
    },
    "root": str(ROOT),
    "version": 1,
}

lifecycle: Any | None = None


class RecoveryInterrupted(RuntimeError):
    """把 SIGINT／SIGTERM／SIGHUP 收斂到可留證的失敗路徑。"""


TERMINAL_SIGNALS = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)


def read_verified_bytes(path: Path, expected_sha256: str) -> bytes:
    """從同一個 no-follow FD 讀取並驗證來源，避免驗證後再由路徑重讀。"""

    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise RuntimeError(f"frozen path is not a regular file: {path}")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        payload = b"".join(chunks)
        after = os.fstat(descriptor)
        if (before.st_dev, before.st_ino, before.st_size) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
        ):
            raise RuntimeError(f"frozen file identity changed while hashing: {path}")
    finally:
        os.close(descriptor)
    actual = hashlib.sha256(payload).hexdigest()
    if actual != expected_sha256:
        raise RuntimeError(f"frozen file changed: {path}: {actual}")
    return payload


def sha256_file(path: Path) -> str:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise RuntimeError(f"frozen path is not a regular file: {path}")
        digest = hashlib.sha256()
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
        after = os.fstat(descriptor)
        if (before.st_dev, before.st_ino, before.st_size) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
        ):
            raise RuntimeError(f"frozen file identity changed while hashing: {path}")
    finally:
        os.close(descriptor)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"JSON root must be an object: {path}")
    return payload


def execute_verified_module(
    name: str,
    path: Path,
    payload: bytes,
    *,
    package: str | None,
) -> types.ModuleType:
    """只執行已由同一 FD 驗證完成的 bytes，不讓 loader 再按路徑重讀。"""

    module = types.ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = package or ""
    module.__loader__ = None
    module.__spec__ = importlib.machinery.ModuleSpec(name, loader=None)
    code = compile(payload, str(path), "exec", dont_inherit=True)
    sys.modules[name] = module
    try:
        exec(code, module.__dict__)
    except BaseException:
        if sys.modules.get(name) is module:
            sys.modules.pop(name, None)
        raise
    return module


def load_runtime_modules():
    """建立 synthetic package，所有 donor bytes 驗證完成後才執行。"""

    global lifecycle
    module_names = (
        "scripts",
        "scripts.host_capacity_sensor",
        "scripts.tmp_artifact_lifecycle",
        "fog_nofork_native_runner_current",
    )
    occupied = [name for name in module_names if name in sys.modules]
    if occupied:
        raise RuntimeError(f"runtime module already loaded before verification: {occupied}")

    # 三份可執行來源先全部從 no-follow FD 讀入、驗 SHA，再建立任何 module。
    host_source = read_verified_bytes(
        HOST_CAPACITY_SENSOR_PATH,
        HOST_CAPACITY_SENSOR_SHA256,
    )
    lifecycle_source = read_verified_bytes(LIFECYCLE_PATH, LIFECYCLE_SHA256)
    runner_source = read_verified_bytes(CURRENT_RUNNER, CURRENT_RUNNER_SHA256)

    package = types.ModuleType("scripts")
    package.__package__ = "scripts"
    package.__path__ = [str(SCRIPTS_DIR)]
    package.__loader__ = None
    package_spec = importlib.machinery.ModuleSpec("scripts", loader=None, is_package=True)
    package_spec.submodule_search_locations = [str(SCRIPTS_DIR)]
    package.__spec__ = package_spec
    inserted: list[tuple[str, types.ModuleType]] = [("scripts", package)]
    sys.modules["scripts"] = package
    try:
        host = execute_verified_module(
            "scripts.host_capacity_sensor",
            HOST_CAPACITY_SENSOR_PATH,
            host_source,
            package="scripts",
        )
        inserted.append(("scripts.host_capacity_sensor", host))
        package.host_capacity_sensor = host

        loaded_lifecycle = execute_verified_module(
            "scripts.tmp_artifact_lifecycle",
            LIFECYCLE_PATH,
            lifecycle_source,
            package="scripts",
        )
        inserted.append(("scripts.tmp_artifact_lifecycle", loaded_lifecycle))
        package.tmp_artifact_lifecycle = loaded_lifecycle

        runner = execute_verified_module(
            "fog_nofork_native_runner_current",
            CURRENT_RUNNER,
            runner_source,
            package=None,
        )
        inserted.append(("fog_nofork_native_runner_current", runner))
        if runner.lifecycle is not loaded_lifecycle:
            raise RuntimeError("runner loaded a different lifecycle module")
    except BaseException:
        for name, expected in reversed(inserted):
            if sys.modules.get(name) is expected:
                sys.modules.pop(name, None)
        raise

    lifecycle = loaded_lifecycle
    return loaded_lifecycle, runner


def verify_file(path: Path, expected: str) -> None:
    actual = sha256_file(path)
    if actual != expected:
        raise RuntimeError(f"frozen file changed: {path}: {actual}")


def verify_v1_freeze() -> dict[str, str]:
    verify_file(V1_RUNNER, V1_RUNNER_SHA256)
    verify_file(V1_FREEZE, V1_FREEZE_SHA256)
    freeze = load_json(V1_FREEZE)
    if freeze.get("source_commit") != SOURCE_COMMIT:
        raise RuntimeError("v1 source commit changed")
    observed: dict[str, str] = {}
    for name, expected in dict(freeze.get("sha256") or {}).items():
        path = Path(name)
        candidate = V1_RUNNER if path == CURRENT_RUNNER else path
        actual = sha256_file(candidate)
        observed[str(candidate)] = actual
        if actual != expected:
            raise RuntimeError(f"v1 frozen source changed: {candidate}")
    return observed


def verify_failed_receipt() -> dict[str, Any]:
    verify_file(FAILED_RECEIPT, FAILED_RECEIPT_SHA256)
    verify_file(FAILED_LOG, FAILED_LOG_SHA256)
    receipt = load_json(FAILED_RECEIPT)
    required = {
        "status": "BLOCKED_WITH_EVIDENCE",
        "cycle": 1,
        "source_commit": SOURCE_COMMIT,
        "lifecycle_exit": 2,
        "lifecycle_error": None,
        "root": str(ROOT),
        "stop_reason": None,
    }
    for key, expected in required.items():
        if receipt.get(key) != expected:
            raise RuntimeError(f"failed receipt identity mismatch: {key}")
    conditions = receipt.get("pass_conditions")
    if not isinstance(conditions, dict):
        raise RuntimeError("failed receipt lacks pass conditions")
    for name in (
        "observer_stop_absent",
        "two_nofork_proofs",
        "two_zero_exit_steps",
        "source_hashes_unchanged",
        "git_visible_source_status_unchanged",
        "volume_identity_unchanged",
    ):
        if conditions.get(name) is not True:
            raise RuntimeError(f"required completed condition missing: {name}")
    for name in (
        "lifecycle_exit_zero",
        "root_absent_after",
        "marker_absent_after",
        "evidence_bundle_present",
        "validation_pass",
        "verification_pass",
    ):
        if conditions.get(name) is not False:
            raise RuntimeError(f"expected export-failure condition changed: {name}")

    events = receipt.get("events")
    if not isinstance(events, list):
        raise RuntimeError("failed receipt lacks events")
    proofs = [event for event in events if event.get("role") == "native_nofork_proof"]
    stopped = [event for event in events if event.get("role") == "step_stopped"]
    roots = [event for event in events if event.get("role") == "root_created"]
    unknown = [event for event in events if event.get("role") == "marker_unknown"]
    if [event.get("pid") for event in proofs] != list(HISTORICAL_PIDS):
        raise RuntimeError("native no-fork proof identity changed")
    if [(event.get("phase"), event.get("exit")) for event in stopped] != [
        ("prepare", 0),
        ("execute", 0),
    ]:
        raise RuntimeError("leaf stop events changed")
    if len(roots) != 1 or (
        roots[0].get("root"),
        roots[0].get("device"),
        roots[0].get("inode"),
    ) != (str(ROOT), ROOT_DEVICE, ROOT_INODE):
        raise RuntimeError("root-created identity changed")
    if len(unknown) != 1 or unknown[0].get("root") != str(ROOT):
        raise RuntimeError("unknown marker event changed")
    return receipt


def tree_identity_snapshot(
    root: Path,
    rows: list[dict[str, object]],
) -> dict[str, dict[str, int | str]]:
    """把 frozen manifest 的每個節點綁到 device／inode；不接受額外 path 形式。"""

    snapshot: dict[str, dict[str, int | str]] = {}
    for row in rows:
        relative_text = str(row.get("path", ""))
        relative = Path(relative_text)
        if (
            not relative_text
            or relative.is_absolute()
            or ".." in relative.parts
            or str(relative) != relative_text
        ):
            raise RuntimeError(f"unsafe frozen tree path: {relative_text}")
        node = os.lstat(root / relative)
        kind = str(row.get("kind"))
        if kind == "dir":
            if not stat.S_ISDIR(node.st_mode):
                raise RuntimeError(f"frozen directory identity changed: {relative_text}")
        elif kind == "file":
            if not stat.S_ISREG(node.st_mode) or node.st_size != int(row.get("size", -1)):
                raise RuntimeError(f"frozen file identity changed: {relative_text}")
        else:
            raise RuntimeError(f"unsupported frozen tree kind: {relative_text}")
        snapshot[relative_text] = {
            "device": node.st_dev,
            "inode": node.st_ino,
            "mode": stat.S_IMODE(node.st_mode),
            "kind": kind,
            "size": node.st_size,
        }
    return snapshot


def verify_root(
    runner,
    root_fd: int,
) -> tuple[dict[str, Any], list[dict[str, object]], dict[str, dict[str, int | str]]]:
    lexical = Path(os.path.abspath(ROOT))
    if lexical != ROOT or ROOT.is_symlink() or ROOT.resolve(strict=True) != ROOT:
        raise RuntimeError("exact recovery root is unavailable")
    info = os.fstat(root_fd)
    current = os.stat(ROOT, follow_symlinks=False)
    expected = (ROOT_DEVICE, ROOT_INODE)
    if (info.st_dev, info.st_ino) != expected or (current.st_dev, current.st_ino) != expected:
        raise RuntimeError("exact recovery root identity changed")
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != ROOT_MODE:
        raise RuntimeError("exact recovery root permissions changed")
    verify_file(ROOT / ".tmp-artifact-manifest.json", MANIFEST_SHA256)
    if load_json(ROOT / ".tmp-artifact-manifest.json") != EXPECTED_MANIFEST:
        raise RuntimeError("root manifest changed")
    rows = runner.tree_manifest(ROOT)
    identities = tree_identity_snapshot(ROOT, rows)
    digest = runner.manifest_sha256(rows)
    files = [row for row in rows if row.get("kind") == "file"]
    logical = sum(int(row.get("size", 0)) for row in files)
    if (digest, len(rows), len(files), logical) != (
        ROOT_TREE_SHA256,
        ROOT_ENTRY_COUNT,
        ROOT_FILE_COUNT,
        ROOT_LOGICAL_BYTES,
    ):
        raise RuntimeError("root tree identity changed")
    for path in ROOT.rglob("*"):
        node = os.lstat(path)
        if node.st_dev != ROOT_DEVICE or not (
            stat.S_ISDIR(node.st_mode) or stat.S_ISREG(node.st_mode)
        ):
            raise RuntimeError(f"unsafe root node: {path}")

    preserve = ROOT / runner.PRESERVE_PATH
    preserve_rows = runner.tree_manifest(preserve)
    preserve_digest = runner.manifest_sha256(preserve_rows)
    preserve_files = [row for row in preserve_rows if row.get("kind") == "file"]
    preserve_logical = sum(int(row.get("size", 0)) for row in preserve_files)
    if (preserve_digest, len(preserve_rows), len(preserve_files), preserve_logical) != (
        PRESERVE_TREE_SHA256,
        PRESERVE_ENTRY_COUNT,
        PRESERVE_FILE_COUNT,
        PRESERVE_LOGICAL_BYTES,
    ):
        raise RuntimeError("preserved validation tree changed")
    validation = load_json(preserve / "fog_representative_validation_2026-08-31.json")
    verification = load_json(
        preserve / "fog_representative_batch_verification_2026-08-31.json"
    )
    if (
        validation.get("status") != "PASS"
        or validation.get("production_promotion_allowed") is not False
        or len(validation.get("topic_runs") or []) != 1
        or verification.get("status") != "PASS"
    ):
        raise RuntimeError("preserved representative outputs are not accepted")
    return (
        {
            "device": info.st_dev,
            "inode": info.st_ino,
            "mode": oct(stat.S_IMODE(info.st_mode)),
            "tree_manifest_sha256": digest,
            "entry_count": len(rows),
            "file_count": len(files),
            "logical_bytes": logical,
            "preserve_manifest_sha256": preserve_digest,
            "preserve_entry_count": len(preserve_rows),
            "preserve_file_count": len(preserve_files),
            "preserve_logical_bytes": preserve_logical,
        },
        rows,
        identities,
    )


def read_marker_name_state(
    git_fd: int,
    name: str,
) -> tuple[dict[str, Any], dict[str, int], bytes]:
    descriptor = os.open(
        name,
        os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
        dir_fd=git_fd,
    )
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise RuntimeError("exact marker is not a regular file")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 65536)
            if not chunk:
                break
            chunks.append(chunk)
        raw = b"".join(chunks)
        after = os.fstat(descriptor)
        if (before.st_dev, before.st_ino, before.st_size) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
        ):
            raise RuntimeError("exact marker identity changed while reading")
    finally:
        os.close(descriptor)
    if hashlib.sha256(raw).hexdigest() != MARKER_SHA256:
        raise RuntimeError("exact marker bytes changed")
    marker = json.loads(raw.decode("utf-8"))
    if marker != EXPECTED_MARKER:
        raise RuntimeError("exact unknown marker changed")
    return (
        marker,
        {
            "device": before.st_dev,
            "inode": before.st_ino,
            "size": before.st_size,
            "mode": stat.S_IMODE(before.st_mode),
        },
        raw,
    )


def read_marker_state(git_fd: int) -> tuple[dict[str, Any], dict[str, int], bytes]:
    return read_marker_name_state(git_fd, MARKER.name)


def verify_marker(
    lock: dict[str, object],
    expected_identity: dict[str, int] | None = None,
) -> tuple[dict[str, Any], dict[str, int], bytes]:
    marker, identity, raw = read_marker_state(int(lock["fd"]))
    if expected_identity is not None and identity != expected_identity:
        raise RuntimeError("exact marker inode changed")
    return marker, identity, raw


def marker_name_exists(git_fd: int, name: str) -> bool:
    try:
        os.stat(name, dir_fd=git_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    return True


def marker_exists(git_fd: int) -> bool:
    return marker_name_exists(git_fd, MARKER.name)


def path_exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def rename_no_replace_path(source: Path, destination: Path) -> None:
    if platform.system() != "Darwin":
        raise RuntimeError("no-replace recovery rename is unavailable")
    libc = ctypes.CDLL(None, use_errno=True)
    renamex_np = getattr(libc, "renamex_np", None)
    if renamex_np is None:
        raise RuntimeError("no-replace recovery rename is unavailable")
    renamex_np.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
    renamex_np.restype = ctypes.c_int
    result = renamex_np(
        os.fsencode(source),
        os.fsencode(destination),
        0x00000004,
    )
    if result == 0:
        return
    error_number = ctypes.get_errno()
    if error_number in {errno.EEXIST, errno.ENOTEMPTY, errno.EISDIR}:
        raise RuntimeError("no-replace recovery destination already exists")
    raise OSError(error_number, os.strerror(error_number), os.fspath(destination))


def verify_marker_quarantine(
    git_fd: int,
    identity: dict[str, int],
    raw: bytes,
) -> dict[str, int | str]:
    marker, current_identity, current_raw = read_marker_name_state(
        git_fd,
        MARKER_QUARANTINE.name,
    )
    if marker != EXPECTED_MARKER or current_identity != identity or current_raw != raw:
        raise RuntimeError("quarantined marker identity changed")
    if marker_exists(git_fd):
        raise RuntimeError("new active marker appeared during quarantine")
    return {
        "path": str(MARKER_QUARANTINE),
        **current_identity,
        "sha256": hashlib.sha256(current_raw).hexdigest(),
    }


def quarantine_exact_marker(
    git_fd: int,
    identity: dict[str, int],
    raw: bytes,
) -> dict[str, int | str]:
    """原子移動 exact marker 並永久保留；任何新 marker 都不刪除。"""

    marker, current_identity, current_raw = read_marker_state(git_fd)
    if marker != EXPECTED_MARKER or current_identity != identity or current_raw != raw:
        raise RuntimeError("exact marker changed before quarantine")
    if marker_name_exists(git_fd, MARKER_QUARANTINE.name):
        raise RuntimeError("marker quarantine destination already exists")
    rename_no_replace_path(MARKER, MARKER_QUARANTINE)
    os.fsync(git_fd)
    return verify_marker_quarantine(git_fd, identity, raw)


def restore_exact_marker(git_fd: int, raw: bytes) -> bool:
    if marker_exists(git_fd):
        marker, _, current_raw = read_marker_state(git_fd)
        if marker != EXPECTED_MARKER or current_raw != raw:
            raise RuntimeError("different marker prevents exact restore")
        return False
    descriptor = os.open(
        MARKER.name,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o600,
        dir_fd=git_fd,
    )
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as output:
            output.write(raw)
            output.flush()
            os.fsync(output.fileno())
    finally:
        os.close(descriptor)
    os.fsync(git_fd)
    marker, _, current_raw = read_marker_state(git_fd)
    if marker != EXPECTED_MARKER or current_raw != raw:
        raise RuntimeError("exact marker restore verification failed")
    return True


def verify_root_quarantine(
    runner,
    root_fd: int,
    expected_rows: list[dict[str, object]],
    expected_identities: dict[str, dict[str, int | str]],
) -> dict[str, int | str]:
    if path_exists(ROOT):
        raise RuntimeError("active root path reappeared after quarantine")
    descriptor = os.open(
        ROOT_QUARANTINE,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
    )
    try:
        opened_root = os.fstat(root_fd)
        quarantined = os.fstat(descriptor)
        expected_root = (ROOT_DEVICE, ROOT_INODE)
        if (
            (opened_root.st_dev, opened_root.st_ino) != expected_root
            or (quarantined.st_dev, quarantined.st_ino) != expected_root
            or stat.S_IMODE(quarantined.st_mode) != ROOT_MODE
            or quarantined.st_uid != os.getuid()
        ):
            raise RuntimeError("quarantined root identity changed")
        current_rows = runner.tree_manifest(ROOT_QUARANTINE)
        current_identities = tree_identity_snapshot(ROOT_QUARANTINE, current_rows)
        if current_rows != expected_rows or current_identities != expected_identities:
            raise RuntimeError("quarantined root tree changed")
        digest = runner.manifest_sha256(current_rows)
        if digest != ROOT_TREE_SHA256:
            raise RuntimeError("quarantined root manifest changed")
    finally:
        os.close(descriptor)
    return {
        "path": str(ROOT_QUARANTINE),
        "device": ROOT_DEVICE,
        "inode": ROOT_INODE,
        "mode": oct(ROOT_MODE),
        "tree_manifest_sha256": ROOT_TREE_SHA256,
        "entry_count": len(expected_rows),
    }


def quarantine_exact_root(
    runner,
    root_fd: int,
    expected_rows: list[dict[str, object]],
    expected_identities: dict[str, dict[str, int | str]],
) -> dict[str, int | str]:
    """同卷原子移動 exact root；不刪除任何 frozen 或 unknown 內容。"""

    current_rows = runner.tree_manifest(ROOT)
    if current_rows != expected_rows:
        raise RuntimeError("exact root tree changed before quarantine")
    current_identities = tree_identity_snapshot(ROOT, current_rows)
    if current_identities != expected_identities:
        raise RuntimeError("exact root node identity changed before quarantine")
    if path_exists(ROOT_QUARANTINE):
        raise RuntimeError("root quarantine destination already exists")
    rename_no_replace_path(ROOT, ROOT_QUARANTINE)
    fsync_directory(ROOT.parent)
    return verify_root_quarantine(
        runner,
        root_fd,
        expected_rows,
        expected_identities,
    )


def install_interrupt_handlers() -> dict[int, Any]:
    previous: dict[int, Any] = {}

    def interrupt(signum: int, _frame: Any) -> None:
        raise RecoveryInterrupted(f"interrupted by signal {signum}")

    for signum in TERMINAL_SIGNALS:
        previous[signum] = signal.getsignal(signum)
        signal.signal(signum, interrupt)
    return previous


def suppress_interrupts() -> None:
    for signum in TERMINAL_SIGNALS:
        signal.signal(signum, signal.SIG_IGN)


def restore_interrupt_handlers(previous: dict[int, Any]) -> None:
    for signum, handler in previous.items():
        signal.signal(signum, handler)


def block_terminal_signals() -> set[signal.Signals]:
    if not hasattr(signal, "pthread_sigmask"):
        raise RuntimeError("terminal signal masking is unavailable")
    return signal.pthread_sigmask(signal.SIG_BLOCK, set(TERMINAL_SIGNALS))


def restore_signal_mask(previous: set[signal.Signals]) -> None:
    signal.pthread_sigmask(signal.SIG_SETMASK, previous)


def observe_no_processes() -> dict[str, Any]:
    observations = [
        lifecycle.recovery_process_observation(ROOT, pid) for pid in HISTORICAL_PIDS
    ]
    lsof_path = Path("/usr/sbin/lsof")
    if not lsof_path.exists():
        lsof_path = Path("/usr/bin/lsof")
    completed = subprocess.run(
        [str(lsof_path), "-F", "pcfnt", "+D", str(ROOT)],
        text=True,
        capture_output=True,
        check=False,
        timeout=15,
    )
    if completed.returncode not in {0, 1} or completed.stderr.strip():
        raise RuntimeError("open file observation prevents exact-root recovery")
    records: list[dict[str, Any]] = []
    process_id: int | None = None
    command: str | None = None
    current: dict[str, Any] | None = None
    for line in completed.stdout.splitlines():
        if not line:
            continue
        tag, value = line[0], line[1:]
        if tag == "p":
            if current is not None:
                records.append(current)
                current = None
            if not value.isdecimal():
                raise RuntimeError("malformed lsof process identity")
            process_id = int(value)
            command = None
        elif tag == "c":
            command = value
        elif tag == "f":
            if current is not None:
                records.append(current)
            if process_id is None:
                raise RuntimeError("lsof file lacks process identity")
            current = {
                "pid": process_id,
                "command": command,
                "fd": value,
                "type": None,
                "name": None,
            }
        elif tag in {"t", "n"}:
            if current is None:
                raise RuntimeError("lsof attribute lacks file identity")
            current["type" if tag == "t" else "name"] = value
        else:
            raise RuntimeError(f"unsupported lsof field: {tag}")
    if current is not None:
        records.append(current)
    unexpected = [
        record
        for record in records
        if not (
            record.get("pid") == os.getpid()
            and record.get("type") == "DIR"
            and record.get("name") == str(ROOT)
        )
    ]
    if unexpected:
        raise RuntimeError(f"open file observation prevents exact-root recovery: {unexpected}")
    return {
        "process_observations": observations,
        "lsof_returncode": completed.returncode,
        "lsof_records": records,
        "only_self_root_directory_fd": not unexpected,
        "lsof_stderr_empty": not completed.stderr.strip(),
    }


def prepare_receipt_dir(path: Path) -> tuple[Path, int]:
    destination = lifecycle.lexical_absolute(path)
    repo = PROJECT.resolve(strict=True)
    lifecycle.ensure_within(
        destination,
        repo,
        "NO_GO: recovery receipt must be repo-local",
    )
    lifecycle.reject_existing_symlink_components(
        destination.parent,
        repo,
        "NO_GO: recovery receipt contains symlink ancestor",
    )
    if destination.exists() or destination.is_symlink():
        raise RuntimeError("recovery receipt destination already exists")
    destination.mkdir(mode=0o700)
    descriptor = os.open(destination, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    return destination, descriptor


def write_receipt(directory: int, name: str, payload: dict[str, Any]) -> None:
    lifecycle.recovery_receipt(directory, name, payload)


def receipt_bytes(payload: dict[str, Any]) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def write_terminal_receipt(directory: int, payload: dict[str, Any]) -> dict[str, int | str]:
    """完整 staged file fsync 後，以 hard-link 原子發布 result；保留 stage 作證。"""

    stage_name = "terminal-result-staged.json"
    result_name = "result.json"
    for name in (stage_name, result_name):
        try:
            os.stat(name, dir_fd=directory, follow_symlinks=False)
        except FileNotFoundError:
            continue
        raise RuntimeError(f"terminal receipt path already exists: {name}")

    encoded = receipt_bytes(payload)
    descriptor = os.open(
        stage_name,
        os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o600,
        dir_fd=directory,
    )
    try:
        offset = 0
        while offset < len(encoded):
            written = os.write(descriptor, encoded[offset:])
            if written <= 0:
                raise RuntimeError("terminal receipt write made no progress")
            offset += written
        os.fsync(descriptor)
        staged = os.fstat(descriptor)
        if not stat.S_ISREG(staged.st_mode) or staged.st_size != len(encoded):
            raise RuntimeError("terminal staged receipt identity changed")
        os.link(
            stage_name,
            result_name,
            src_dir_fd=directory,
            dst_dir_fd=directory,
            follow_symlinks=False,
        )
        os.fsync(directory)
        result = os.stat(result_name, dir_fd=directory, follow_symlinks=False)
        if (result.st_dev, result.st_ino, result.st_size) != (
            staged.st_dev,
            staged.st_ino,
            staged.st_size,
        ):
            raise RuntimeError("terminal result does not reference staged receipt")
        os.lseek(descriptor, 0, os.SEEK_SET)
        observed = b""
        while len(observed) < len(encoded):
            chunk = os.read(descriptor, min(65536, len(encoded) - len(observed)))
            if not chunk:
                break
            observed += chunk
        if observed != encoded:
            raise RuntimeError("terminal staged receipt bytes changed")
    finally:
        os.close(descriptor)
    return {
        "result_name": result_name,
        "stage_name": stage_name,
        "device": staged.st_dev,
        "inode": staged.st_ino,
        "size": staged.st_size,
        "sha256": hashlib.sha256(encoded).hexdigest(),
    }


def verify_recovered_evidence(runner) -> dict[str, int | str]:
    preserved = RECOVERED_EVIDENCE / runner.PRESERVE_PATH
    rows = runner.tree_manifest(preserved)
    digest = runner.manifest_sha256(rows)
    files = [row for row in rows if row.get("kind") == "file"]
    logical = sum(int(row.get("size", 0)) for row in files)
    if (digest, len(rows), len(files), logical) != (
        PRESERVE_TREE_SHA256,
        PRESERVE_ENTRY_COUNT,
        PRESERVE_FILE_COUNT,
        PRESERVE_LOGICAL_BYTES,
    ):
        raise RuntimeError("recovered evidence tree changed")
    return {
        "path": str(preserved),
        "manifest_sha256": digest,
        "entry_count": len(rows),
        "file_count": len(files),
        "logical_bytes": logical,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", dest="execute", action="store_false")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--owner-authorization-ref", required=True)
    args = parser.parse_args(argv)
    if not args.owner_authorization_ref.strip():
        parser.error("owner authorization reference is required")

    previous_handlers = install_interrupt_handlers()
    previous_mask: set[signal.Signals] | None = None
    receipt_path = EXECUTE_DIR if args.execute else DRY_RUN_DIR
    receipt_fd = root_fd = volume_fd = git_fd = None
    lock: dict[str, object] | None = None
    runner: Any | None = None
    marker_identity: dict[str, int] | None = None
    marker_raw: bytes | None = None
    frozen_rows: list[dict[str, object]] | None = None
    frozen_identities: dict[str, dict[str, int | str]] | None = None
    marker_verified = False
    root_quarantined = False
    marker_quarantined = False
    lock_released = False
    terminal_committed = False
    terminal_receipt: dict[str, int | str] | None = None
    receipt: dict[str, Any] = {
        "schema_version": "top10-fog-nofork-exact-recovery.v2",
        "status": "refused",
        "mode": "execute" if args.execute else "dry-run",
        "root": str(ROOT),
        "root_quarantine": str(ROOT_QUARANTINE),
        "marker": str(MARKER),
        "marker_quarantine": str(MARKER_QUARANTINE),
        "owner_authorization_ref": args.owner_authorization_ref,
        "recovered_evidence": str(RECOVERED_EVIDENCE),
        "receipt_dir": str(receipt_path),
        "terminal_receipt_protocol": "fsynced-stage-plus-atomic-hardlink",
    }
    code = 2
    try:
        v1_sources = verify_v1_freeze()
        failed_receipt = verify_failed_receipt()
        loaded_lifecycle, runner = load_runtime_modules()
        if loaded_lifecycle is not lifecycle:
            raise RuntimeError("verified lifecycle binding changed")
        if path_exists(ROOT_QUARANTINE):
            raise RuntimeError("root quarantine destination already exists")
        if path_exists(MARKER_QUARANTINE):
            raise RuntimeError("marker quarantine destination already exists")
        if path_exists(RECOVERED_EVIDENCE):
            raise RuntimeError("recovered evidence destination already exists")

        lock = lifecycle.acquire_repo_lock(PROJECT, "recovery", {"max_bytes": 0})
        if Path(lock["target"]).resolve(strict=True) != (PROJECT / ".git").resolve(strict=True):
            raise RuntimeError("repo lock target changed")
        git_fd = os.dup(int(lock["fd"]))
        volume_fd = os.open(
            runner.VOLUME,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
        )
        volume_identity = os.fstat(volume_fd)
        volume = runner.check_volume(volume_fd, volume_identity)
        root_fd = os.open(ROOT, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        marker, marker_identity, marker_raw = verify_marker(lock)
        marker_verified = True
        root_identity, frozen_rows, frozen_identities = verify_root(runner, root_fd)
        receipt.update(
            {
                "volume": volume,
                "v1_source_sha256": v1_sources,
                "failed_receipt": failed_receipt,
                "marker_payload": marker,
                "marker_identity": marker_identity,
                "root_identity": root_identity,
                "observation": observe_no_processes(),
            }
        )
        receipt_path, receipt_fd = prepare_receipt_dir(receipt_path)
        receipt["status"] = "authorized-execute" if args.execute else "dry-run"
        write_receipt(receipt_fd, "preflight.json", receipt)

        if args.execute:
            assert marker_identity is not None
            assert marker_raw is not None
            assert frozen_rows is not None
            assert frozen_identities is not None

            verify_marker(lock, marker_identity)
            _, current_rows, current_identities = verify_root(runner, root_fd)
            if current_rows != frozen_rows or current_identities != frozen_identities:
                raise RuntimeError("exact root changed before quarantine")
            receipt["before_quarantine_observation"] = observe_no_processes()
            receipt["status"] = "root-quarantine-ready"
            write_receipt(receipt_fd, "root-quarantine-plan.json", receipt)

            receipt["root_quarantine_identity"] = quarantine_exact_root(
                runner,
                root_fd,
                frozen_rows,
                frozen_identities,
            )
            root_quarantined = True
            receipt["status"] = "root-quarantined-marker-retained"
            write_receipt(receipt_fd, "root-quarantined.json", receipt)

            verify_marker(lock, marker_identity)
            receipt["root_quarantine_identity"] = verify_root_quarantine(
                runner,
                root_fd,
                frozen_rows,
                frozen_identities,
            )
            published = runner.publish_cross_volume_evidence(
                root=ROOT_QUARANTINE,
                destination=RECOVERED_EVIDENCE,
                paths=[runner.PRESERVE_PATH],
                repo_root=PROJECT,
                limits={"max_bytes": 64 * 1024**2, "max_file_count": 250},
            )
            if published.get("manifest_sha256") != PRESERVE_TREE_SHA256:
                raise RuntimeError("published evidence manifest changed")
            receipt["published_evidence"] = published
            receipt["verified_recovered_evidence"] = verify_recovered_evidence(runner)
            receipt["status"] = "evidence-published-marker-retained"
            write_receipt(receipt_fd, "evidence-published.json", receipt)

            verify_marker(lock, marker_identity)
            receipt["root_quarantine_identity"] = verify_root_quarantine(
                runner,
                root_fd,
                frozen_rows,
                frozen_identities,
            )
            receipt["marker_quarantine_identity"] = quarantine_exact_marker(
                git_fd,
                marker_identity,
                marker_raw,
            )
            marker_quarantined = True
            receipt["verified_recovered_evidence"] = verify_recovered_evidence(runner)
            receipt["status"] = "effects-complete-lock-held"
            receipt["root_present_before_lock_release"] = path_exists(ROOT)
            receipt["marker_present_before_lock_release"] = marker_exists(git_fd)
            write_receipt(receipt_fd, "effects-complete-lock-held.json", receipt)
        else:
            receipt["status"] = "dry-run-lock-held"

        # 從 lock release 到完整 terminal receipt 發布期間封鎖終止 signal。
        previous_mask = block_terminal_signals()
        suppress_interrupts()
        release_target = lock
        try:
            released = lifecycle.release_repo_lock(release_target)
        finally:
            lock = None
        if not released:
            raise RuntimeError("repo lock release failed")
        lock_released = True

        if args.execute:
            assert marker_identity is not None
            assert marker_raw is not None
            assert frozen_rows is not None
            assert frozen_identities is not None
            receipt["root_quarantine_identity"] = verify_root_quarantine(
                runner,
                root_fd,
                frozen_rows,
                frozen_identities,
            )
            receipt["marker_quarantine_identity"] = verify_marker_quarantine(
                git_fd,
                marker_identity,
                marker_raw,
            )
            receipt["verified_recovered_evidence"] = verify_recovered_evidence(runner)
            if path_exists(ROOT) or marker_exists(git_fd):
                raise RuntimeError("active recovery paths reappeared after lock release")
            receipt["status"] = "recovered-quarantined"
            receipt["root_present_after"] = False
            receipt["marker_present_after"] = False
            receipt["root_quarantine_present_after"] = path_exists(ROOT_QUARANTINE)
            receipt["marker_quarantine_present_after"] = marker_name_exists(
                git_fd,
                MARKER_QUARANTINE.name,
            )
        else:
            marker_after, identity_after, raw_after = read_marker_state(git_fd)
            if (
                marker_after != EXPECTED_MARKER
                or identity_after != marker_identity
                or raw_after != marker_raw
            ):
                raise RuntimeError("dry-run marker changed after lock release")
            _, current_rows, current_identities = verify_root(runner, root_fd)
            if current_rows != frozen_rows or current_identities != frozen_identities:
                raise RuntimeError("dry-run root changed after lock release")
            if (
                path_exists(ROOT_QUARANTINE)
                or marker_name_exists(git_fd, MARKER_QUARANTINE.name)
                or path_exists(RECOVERED_EVIDENCE)
            ):
                raise RuntimeError("dry-run created a recovery side effect")
            receipt["status"] = "dry-run-pass"
        receipt["lock_released"] = True
        terminal_receipt = write_terminal_receipt(receipt_fd, receipt)
        terminal_committed = True
        code = 0
    except BaseException as error:
        if previous_mask is None:
            try:
                previous_mask = block_terminal_signals()
            except BaseException:
                previous_mask = None
        suppress_interrupts()
        if not terminal_committed:
            receipt["status"] = "failed"
            receipt["error"] = f"{type(error).__name__}: {error}"
            receipt["root_present"] = path_exists(ROOT)
            receipt["root_quarantine_present"] = path_exists(ROOT_QUARANTINE)
            receipt["marker_present"] = (
                marker_exists(git_fd)
                if git_fd is not None
                else path_exists(MARKER)
            )
            receipt["marker_quarantine_present"] = (
                marker_name_exists(git_fd, MARKER_QUARANTINE.name)
                if git_fd is not None
                else path_exists(MARKER_QUARANTINE)
            )
            receipt["recovered_evidence_present"] = path_exists(RECOVERED_EVIDENCE)
            if (
                marker_verified
                and marker_raw is not None
                and git_fd is not None
                and not marker_exists(git_fd)
            ):
                try:
                    receipt["marker_restored_after_failure"] = restore_exact_marker(
                        git_fd,
                        marker_raw,
                    )
                except BaseException as marker_error:
                    receipt["marker_restore_error"] = (
                        f"{type(marker_error).__name__}: {marker_error}"
                    )
            if receipt_fd is not None:
                try:
                    write_receipt(receipt_fd, "failure.json", receipt)
                except BaseException as evidence_error:
                    receipt["failure_receipt_error"] = (
                        f"{type(evidence_error).__name__}: {evidence_error}"
                    )
            print(json.dumps(receipt, ensure_ascii=False, sort_keys=True), file=sys.stderr)
    finally:
        suppress_interrupts()
        if lock is not None and lifecycle is not None:
            release_target = lock
            try:
                released = lifecycle.release_repo_lock(release_target)
            finally:
                lock = None
            if not released:
                code = 2
                receipt["status"] = "failed"
                receipt["error"] = "repo lock release failed"
                if (
                    marker_verified
                    and marker_raw is not None
                    and git_fd is not None
                    and not marker_exists(git_fd)
                ):
                    try:
                        receipt["marker_restored_after_lock_failure"] = restore_exact_marker(
                            git_fd,
                            marker_raw,
                        )
                    except BaseException as marker_error:
                        receipt["marker_restore_error"] = (
                            f"{type(marker_error).__name__}: {marker_error}"
                        )
                if receipt_fd is not None:
                    try:
                        write_receipt(receipt_fd, "lock-release-failure.json", receipt)
                    except BaseException as evidence_error:
                        receipt["lock_release_receipt_error"] = (
                            f"{type(evidence_error).__name__}: {evidence_error}"
                        )

        summary = {
            "status": receipt.get("status"),
            "mode": receipt.get("mode"),
            "root_quarantined": root_quarantined,
            "marker_quarantined": marker_quarantined,
            "lock_released": lock_released,
            "terminal_committed": terminal_committed,
            "terminal_receipt": terminal_receipt,
            "receipt_dir": str(receipt_path),
        }
        try:
            print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        except OSError:
            pass
        for descriptor in (root_fd, volume_fd, git_fd, receipt_fd):
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError as close_error:
                    print(
                        json.dumps(
                            {
                                "status": "descriptor-close-warning",
                                "error": f"{type(close_error).__name__}: {close_error}",
                            },
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                        file=sys.stderr,
                    )
        if previous_mask is not None:
            try:
                restore_signal_mask(previous_mask)
            except BaseException as mask_error:
                print(
                    json.dumps(
                        {
                            "status": "signal-mask-restore-warning",
                            "error": f"{type(mask_error).__name__}: {mask_error}",
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    file=sys.stderr,
                )
        restore_interrupt_handlers(previous_handlers)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
