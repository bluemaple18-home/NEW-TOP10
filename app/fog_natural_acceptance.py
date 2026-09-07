"""Fog 自然週期驗收的 invocation-bound 證據驗證。"""

from __future__ import annotations

import hashlib
import json
import os
import plistlib
import re
import secrets
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.fog_runtime_time_authority import (
    TimeAuthorityError,
    derive_market_run_date,
    validate_date,
)


FOG_JOB = "fog-research-worker"
TERMINAL_EVIDENCE_SCHEMA_VERSION = "top10-fog-terminal-evidence.v1"
EVENT_SCHEMA_VERSION = "top10-agent-status-event.v1"
RECEIPT_SCHEMA_VERSION = "top10-storage-guard-receipt.v1"
CADENCE_DRIFT_LIMIT_SECONDS = 60
NATURAL_PROVENANCE_METHOD = "ARCHIVED_RECEIPT_CADENCE_V1"
_INVOCATION_TIMESTAMP = re.compile(
    r"^fog-research-worker-(\d{8}T\d{6}Z)-[A-Za-z0-9._-]+$"
)
_SAFE_INVOCATION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_DIRECTORY_FLAGS = (
    os.O_RDONLY
    | os.O_DIRECTORY
    | os.O_NOFOLLOW
    | getattr(os, "O_CLOEXEC", 0)
)
_READ_FLAGS = (
    os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0)
)
_WRITE_FLAGS = (
    os.O_WRONLY
    | os.O_CREAT
    | os.O_EXCL
    | os.O_NOFOLLOW
    | getattr(os, "O_CLOEXEC", 0)
)


def terminal_evidence_path(root: Path, invocation_id: str) -> Path:
    """回傳由 guard 決定、不可經由 latest 替代的 exact evidence 路徑。"""

    return (
        root
        / "logs"
        / "storage_safety"
        / "runtime"
        / FOG_JOB
        / "terminal_evidence"
        / f"{invocation_id}.json"
    )


def _absolute_root(root: Path) -> Path:
    """保留 lexical root，後續以 O_NOFOLLOW directory FD 錨定。"""

    return Path(os.path.abspath(os.fspath(root)))


def _relative_parts(relative: Path | str) -> tuple[str, ...]:
    path = Path(relative)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError("acceptance path 必須是安全 relative path")
    return path.parts


def _open_directory(root: Path, relative: Path | str, *, create: bool = False) -> int:
    """逐層以 anchored dirfd 開啟目錄；ancestor 變更不會改變後續 I/O target。"""

    parts = () if str(relative) in {"", "."} else _relative_parts(relative)
    current_fd = os.open(root, _DIRECTORY_FLAGS)
    try:
        if not stat.S_ISDIR(os.fstat(current_fd).st_mode):
            raise NotADirectoryError(root)
        for part in parts:
            try:
                next_fd = os.open(part, _DIRECTORY_FLAGS, dir_fd=current_fd)
            except FileNotFoundError:
                if not create:
                    raise
                try:
                    os.mkdir(part, mode=0o700, dir_fd=current_fd)
                except FileExistsError:
                    pass
                next_fd = os.open(part, _DIRECTORY_FLAGS, dir_fd=current_fd)
            if not stat.S_ISDIR(os.fstat(next_fd).st_mode):
                os.close(next_fd)
                raise NotADirectoryError(part)
            os.close(current_fd)
            current_fd = next_fd
        return current_fd
    except BaseException:
        os.close(current_fd)
        raise


def _read_from_fd(descriptor: int) -> bytes:
    chunks: list[bytes] = []
    while True:
        chunk = os.read(descriptor, 1024 * 1024)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def _read_regular_at(directory_fd: int, name: str) -> bytes:
    descriptor = os.open(name, _READ_FLAGS, dir_fd=directory_fd)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError(f"acceptance leaf 不是 regular file：{name}")
        return _read_from_fd(descriptor)
    finally:
        os.close(descriptor)


def _read_regular_bytes(root: Path, relative: Path | str) -> bytes:
    parts = _relative_parts(relative)
    directory_fd = _open_directory(root, Path(*parts[:-1]))
    try:
        return _read_regular_at(directory_fd, parts[-1])
    finally:
        os.close(directory_fd)


def _read_regular_directory(
    root: Path, relative: Path | str
) -> list[tuple[str, bytes]]:
    directory_fd = _open_directory(root, relative)
    try:
        documents: list[tuple[str, bytes]] = []
        for name in sorted(os.listdir(directory_fd)):
            if name.endswith(".json"):
                documents.append((name, _read_regular_at(directory_fd, name)))
        return documents
    finally:
        os.close(directory_fd)


def _path_is_absent(root: Path, relative: Path | str) -> bool:
    """只有安全 ancestry 下的確實缺檔才算 absent；symlink／錯誤皆 fail closed。"""

    parts = _relative_parts(relative)
    try:
        directory_fd = _open_directory(root, Path(*parts[:-1]))
    except FileNotFoundError:
        return True
    except OSError:
        return False
    try:
        descriptor = os.open(parts[-1], _READ_FLAGS, dir_fd=directory_fd)
    except FileNotFoundError:
        return True
    except OSError:
        return False
    else:
        os.close(descriptor)
        return False
    finally:
        os.close(directory_fd)


def _write_all(descriptor: int, encoded: bytes) -> None:
    view = memoryview(encoded)
    while view:
        written = os.write(descriptor, view)
        if written <= 0:
            raise OSError("terminal evidence write 未前進")
        view = view[written:]


def _publish_immutable_bytes(root: Path, relative: Path | str, encoded: bytes) -> None:
    parts = _relative_parts(relative)
    directory_fd = _open_directory(root, Path(*parts[:-1]), create=True)
    temporary_name = f".{parts[-1]}.{secrets.token_hex(8)}.tmp"
    descriptor: int | None = None
    try:
        descriptor = os.open(temporary_name, _WRITE_FLAGS, 0o600, dir_fd=directory_fd)
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError("terminal evidence temporary leaf 不是 regular file")
        _write_all(descriptor, encoded)
        os.fsync(descriptor)
        os.fchmod(descriptor, 0o444)
        final_stat = os.fstat(descriptor)
        if not stat.S_ISREG(final_stat.st_mode) or final_stat.st_size != len(encoded):
            raise OSError("terminal evidence temporary leaf 不完整")
        os.link(
            temporary_name,
            parts[-1],
            src_dir_fd=directory_fd,
            dst_dir_fd=directory_fd,
            follow_symlinks=False,
        )
        os.fsync(directory_fd)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            os.unlink(temporary_name, dir_fd=directory_fd)
        except FileNotFoundError:
            pass
        os.close(directory_fd)


def _invalid_result(relative_path: str, status: str, reason: str) -> dict[str, Any]:
    return {
        "terminal_evidence_verified": False,
        "terminal_evidence_status": status,
        "terminal_evidence_path": relative_path,
        "terminal_evidence_reason": reason,
        "cadence_verified": False,
    }


def _event_relative_path(run_date: str, run_id: str) -> str:
    return (
        Path("artifacts")
        / "harness_status"
        / run_date
        / run_id
        / "events"
        / "fog_map.json"
    ).as_posix()


def _validate_identity(
    *, scheduled_at: str, invocation_id: str, run_id: str, artifact_run_date: str
) -> None:
    try:
        parsed_scheduled_at = datetime.fromisoformat(scheduled_at)
    except ValueError as exc:
        raise ValueError("scheduled_at 必須是 ISO-8601 timestamp") from exc
    if parsed_scheduled_at.tzinfo is None:
        raise ValueError("scheduled_at 必須包含 timezone")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", invocation_id):
        raise ValueError("invocation_id 格式不安全")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,191}", run_id):
        raise ValueError("run_id 格式不安全")
    try:
        validate_date(artifact_run_date, "artifact_run_date")
        expected_run_date = derive_market_run_date(parsed_scheduled_at)
    except TimeAuthorityError as exc:
        raise ValueError("artifact_run_date 無法通過 Fog time authority") from exc
    if artifact_run_date != expected_run_date:
        raise ValueError("artifact_run_date 不等於 scheduled_at 的市場日")


def write_terminal_evidence(
    root: Path,
    *,
    job: str,
    scheduled_at: str,
    invocation_id: str,
    run_id: str,
    artifact_run_date: str,
) -> Path:
    """Atomic、immutable 地發布 exact invocation terminal evidence。"""

    root = _absolute_root(root)
    if job != FOG_JOB:
        raise ValueError("terminal evidence 只允許 fog-research-worker")
    _validate_identity(
        scheduled_at=scheduled_at,
        invocation_id=invocation_id,
        run_id=run_id,
        artifact_run_date=artifact_run_date,
    )
    event_relative = _event_relative_path(artifact_run_date, run_id)
    try:
        event_bytes = _read_regular_bytes(root, event_relative)
        event = json.loads(event_bytes)
    except (OSError, ValueError) as exc:
        raise ValueError("Fog terminal event 不是安全 regular file") from exc
    expected_event = {
        "schema_version": EVENT_SCHEMA_VERSION,
        "run_id": run_id,
        "run_date": artifact_run_date,
        "agent_id": "fog_map",
        "status": "ok",
        "decision": "pass",
    }
    if not isinstance(event, dict) or any(
        event.get(key) != value for key, value in expected_event.items()
    ):
        raise ValueError("Fog terminal event binding 不符")
    payload = {
        "schema_version": TERMINAL_EVIDENCE_SCHEMA_VERSION,
        "job": job,
        "scheduled_at": scheduled_at,
        "invocation_id": invocation_id,
        "run_id": run_id,
        "artifact_run_date": artifact_run_date,
        "terminal_result": "OK",
        "canonical_artifact_path": event_relative,
        "canonical_artifact_sha256": hashlib.sha256(event_bytes).hexdigest(),
        "event_status": event["status"],
        "event_decision": event["decision"],
        "written_at": datetime.now(timezone.utc).isoformat(),
    }
    target = terminal_evidence_path(root, invocation_id)
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    _publish_immutable_bytes(root, target.relative_to(root), encoded)
    return target


def evaluate_terminal_evidence(
    root: Path,
    *,
    scheduled_at: str,
    invocation_id: str,
) -> dict[str, Any]:
    """驗證 exact evidence 與其指向的 terminal Fog event。"""

    root = _absolute_root(root)
    if _SAFE_INVOCATION_ID.fullmatch(invocation_id) is None:
        return _invalid_result("", "INVALID", "INVOCATION_ID_INVALID")
    path = terminal_evidence_path(root, invocation_id)
    relative_path = path.relative_to(root).as_posix()
    try:
        evidence_bytes = _read_regular_bytes(root, Path(relative_path))
    except FileNotFoundError:
        return _invalid_result(relative_path, "MISSING", "EXACT_EVIDENCE_MISSING")
    except (OSError, ValueError):
        return _invalid_result(relative_path, "INVALID", "EVIDENCE_NOT_SAFE_REGULAR_FILE")
    try:
        evidence = json.loads(evidence_bytes)
    except ValueError:
        return _invalid_result(relative_path, "INVALID", "EVIDENCE_JSON_INVALID")
    if not isinstance(evidence, dict):
        return _invalid_result(relative_path, "INVALID", "EVIDENCE_ROOT_INVALID")
    run_id = evidence.get("run_id")
    run_date = evidence.get("artifact_run_date")
    if not isinstance(run_id, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]{0,191}", run_id
    ):
        return _invalid_result(relative_path, "INVALID", "RUN_ID_INVALID")
    if not isinstance(run_date, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", run_date):
        return _invalid_result(relative_path, "INVALID", "ARTIFACT_RUN_DATE_INVALID")
    try:
        validate_date(run_date, "artifact_run_date")
        scheduled = _parse_timestamp(scheduled_at)
        if scheduled is None or run_date != derive_market_run_date(scheduled):
            return _invalid_result(
                relative_path, "INVALID", "ARTIFACT_RUN_DATE_AUTHORITY_MISMATCH"
            )
    except TimeAuthorityError:
        return _invalid_result(relative_path, "INVALID", "ARTIFACT_RUN_DATE_INVALID")
    expected_event_relative = _event_relative_path(run_date, run_id)
    expected_fields = {
        "schema_version": TERMINAL_EVIDENCE_SCHEMA_VERSION,
        "job": FOG_JOB,
        "scheduled_at": scheduled_at,
        "invocation_id": invocation_id,
        "terminal_result": "OK",
        "canonical_artifact_path": expected_event_relative,
        "event_status": "ok",
        "event_decision": "pass",
    }
    if any(evidence.get(key) != value for key, value in expected_fields.items()):
        return _invalid_result(relative_path, "INVALID", "EVIDENCE_BINDING_MISMATCH")
    expected_hash = evidence.get("canonical_artifact_sha256")
    if not isinstance(expected_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
        return _invalid_result(relative_path, "INVALID", "ARTIFACT_HASH_INVALID")
    try:
        event_bytes = _read_regular_bytes(root, expected_event_relative)
        event = json.loads(event_bytes)
    except (OSError, ValueError):
        return _invalid_result(relative_path, "INVALID", "EVENT_NOT_SAFE_OR_INVALID")
    if hashlib.sha256(event_bytes).hexdigest() != expected_hash:
        return _invalid_result(relative_path, "INVALID", "ARTIFACT_HASH_MISMATCH")
    if not isinstance(event, dict) or any(
        event.get(key) != value
        for key, value in {
            "schema_version": EVENT_SCHEMA_VERSION,
            "run_id": run_id,
            "run_date": run_date,
            "agent_id": "fog_map",
            "status": "ok",
            "decision": "pass",
        }.items()
    ):
        return _invalid_result(relative_path, "INVALID", "EVENT_BINDING_MISMATCH")
    return {
        "terminal_evidence_verified": True,
        "terminal_evidence_status": "VALID",
        "terminal_evidence_path": relative_path,
        "terminal_evidence_reason": None,
        "terminal_evidence_run_id": run_id,
        "artifact_run_date": run_date,
        "publish_or_provider_result": evidence["terminal_result"],
        "cadence_verified": False,
    }


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _invocation_timestamp(invocation_id: Any) -> datetime | None:
    if not isinstance(invocation_id, str):
        return None
    match = _INVOCATION_TIMESTAMP.fullmatch(invocation_id)
    if match is None:
        return None
    return datetime.strptime(match.group(1), "%Y%m%dT%H%M%SZ").replace(
        tzinfo=timezone.utc
    )


def _timestamp_binding_valid(scheduled_at: Any, invocation_id: Any) -> bool:
    scheduled = _parse_timestamp(scheduled_at)
    invoked = _invocation_timestamp(invocation_id)
    return bool(
        scheduled is not None
        and invoked is not None
        and abs((scheduled - invoked).total_seconds()) <= CADENCE_DRIFT_LIMIT_SECONDS
    )


def _accepted_cycle_counter(payload: dict[str, Any]) -> int | None:
    counter = payload.get("accepted_natural_cycles")
    if isinstance(counter, int) and not isinstance(counter, bool) and counter >= 0:
        return counter
    return None


def _cadence_anchor_qualified_receipt(payload: dict[str, Any]) -> bool:
    """Counter=0 的既有 live receipt 可證相鄰 cadence，但不可證 accepted。"""

    return bool(
        payload.get("schema_version") == RECEIPT_SCHEMA_VERSION
        and payload.get("job") == FOG_JOB
        and payload.get("status") == "OK"
        and payload.get("trigger_type") == "natural"
        and payload.get("child_exit_code") == 0
        and payload.get("final_process_group_quiescent") is True
        and _accepted_cycle_counter(payload) is not None
    )


def _completion_anchor(payload: dict[str, Any]) -> datetime | None:
    """回傳可信的上一輪 terminal completion anchor。"""

    scheduled = _parse_timestamp(payload.get("scheduled_at"))
    completed = _parse_timestamp(payload.get("final_process_group_checked_at"))
    if scheduled is None or completed is None or completed < scheduled:
        return None
    return completed


def _accepted_chain_qualified_receipt(payload: dict[str, Any]) -> bool:
    """非零 counter 必須重新通過完整 archived receipt chain 驗證。"""

    counter = _accepted_cycle_counter(payload)
    scheduled = _parse_timestamp(payload.get("scheduled_at"))
    artifact_run_date = payload.get("artifact_run_date")
    if (
        counter is None
        or counter <= 0
        or scheduled is None
        or not isinstance(artifact_run_date, str)
    ):
        return False
    try:
        validate_date(artifact_run_date, "artifact_run_date")
        date_valid = artifact_run_date == derive_market_run_date(scheduled)
    except TimeAuthorityError:
        return False
    return bool(
        _cadence_anchor_qualified_receipt(payload)
        and payload.get("terminal_evidence_verified") is True
        and payload.get("terminal_evidence_status") == "VALID"
        and date_valid
        and payload.get("publish_or_provider_result") == "OK"
        and payload.get("cadence_verified") is True
        and payload.get("natural_trigger_verified") is True
        and payload.get("natural_provenance_method") == NATURAL_PROVENANCE_METHOD
        and payload.get("denial_marker_absent") is True
        and payload.get("fog_worker_lock_absent") is True
        and payload.get("research_queue_lock_absent") is True
        and payload.get("consecutive_natural_guard_cycles") == counter
        and payload.get("acceptance_status")
        == ("ACCEPTED" if counter >= 2 else "NATURAL_ACCEPTANCE_PENDING")
    )


def _cadence_result(
    root: Path, *, scheduled_at: str, invocation_id: str
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    base = {
        "cadence_verified": False,
        "cadence_status": "UNVERIFIED",
        "cadence_reason": None,
        "cadence_start_interval_seconds": None,
        "cadence_drift_limit_seconds": CADENCE_DRIFT_LIMIT_SECONDS,
        "previous_invocation_id": None,
    }
    try:
        plist_bytes = _read_regular_bytes(
            root, Path("scripts") / "com.new-top10.fog-research-worker.plist"
        )
        plist = plistlib.loads(plist_bytes)
    except FileNotFoundError:
        return {**base, "cadence_reason": "PLIST_NOT_SAFE_REGULAR_FILE"}, None
    except (OSError, ValueError, plistlib.InvalidFileException):
        return {**base, "cadence_reason": "PLIST_INVALID"}, None
    interval = plist.get("StartInterval") if isinstance(plist, dict) else None
    if not isinstance(interval, int) or isinstance(interval, bool) or interval <= 0:
        return {**base, "cadence_reason": "START_INTERVAL_INVALID"}, None
    base["cadence_start_interval_seconds"] = interval
    if not _timestamp_binding_valid(scheduled_at, invocation_id):
        return {**base, "cadence_reason": "CURRENT_INVOCATION_TIME_MISMATCH"}, None

    try:
        archived_receipts = _read_regular_directory(
            root, Path("logs") / "storage_safety" / "receipts" / FOG_JOB
        )
    except FileNotFoundError:
        return {**base, "cadence_reason": "PREVIOUS_RECEIPT_MISSING"}, None
    except (OSError, ValueError):
        return {**base, "cadence_reason": "ARCHIVED_RECEIPT_UNSAFE"}, None
    current_scheduled = _parse_timestamp(scheduled_at)
    candidates: list[tuple[datetime, dict[str, Any]]] = []
    for name, raw_receipt in archived_receipts:
        if name == f"{invocation_id}.json":
            continue
        try:
            payload = json.loads(raw_receipt)
        except ValueError:
            return {**base, "cadence_reason": "ARCHIVED_RECEIPT_INVALID"}, None
        if not isinstance(payload, dict) or payload.get("schema_version") != RECEIPT_SCHEMA_VERSION:
            continue
        prior_scheduled = _parse_timestamp(payload.get("scheduled_at"))
        prior_invocation = payload.get("invocation_id")
        if (
            prior_scheduled is None
            or current_scheduled is None
            or name != f"{prior_invocation}.json"
        ):
            return {**base, "cadence_reason": "ARCHIVED_RECEIPT_BINDING_INVALID"}, None
        if prior_scheduled < current_scheduled:
            candidates.append((prior_scheduled, payload))
    if not candidates:
        return {**base, "cadence_reason": "PREVIOUS_RECEIPT_MISSING"}, None
    previous_scheduled, previous = max(candidates, key=lambda item: item[0])
    base["previous_invocation_id"] = previous.get("invocation_id")
    if not _cadence_anchor_qualified_receipt(previous):
        return {**base, "cadence_reason": "PREVIOUS_RECEIPT_NOT_CADENCE_ANCHOR"}, previous
    if not _timestamp_binding_valid(
        previous.get("scheduled_at"), previous.get("invocation_id")
    ):
        return {**base, "cadence_reason": "PREVIOUS_INVOCATION_TIME_MISMATCH"}, previous
    previous_completion = _completion_anchor(previous)
    if previous_completion is None:
        return {
            **base,
            "cadence_reason": "PREVIOUS_COMPLETION_ANCHOR_INVALID",
        }, previous
    actual_interval = (current_scheduled - previous_completion).total_seconds()
    if abs(actual_interval - interval) > CADENCE_DRIFT_LIMIT_SECONDS:
        return {**base, "cadence_reason": "CADENCE_INTERVAL_MISMATCH"}, previous
    return {
        **base,
        "cadence_verified": True,
        "cadence_status": "VERIFIED",
        "cadence_reason": None,
    }, previous


def evaluate_natural_acceptance(
    root: Path,
    *,
    scheduled_at: str,
    invocation_id: str,
    child_exit_code: int | None,
    final_process_group_quiescent: bool | None,
) -> dict[str, Any]:
    """只以 exact terminal evidence 與既有 receipt cadence 累加驗收。"""

    result = evaluate_terminal_evidence(
        root,
        scheduled_at=scheduled_at,
        invocation_id=invocation_id,
    )
    root = _absolute_root(root)
    denial_absent = _path_is_absent(
        root, Path("logs") / "storage_safety" / "restart_denied" / f"{FOG_JOB}.json"
    )
    fog_lock_absent = _path_is_absent(root, Path("logs") / "fog_research_worker.lock")
    queue_lock_absent = _path_is_absent(root, Path("logs") / "research_queue_owner.lock")
    result.update(
        {
            "denial_marker_absent": denial_absent,
            "fog_worker_lock_absent": fog_lock_absent,
            "research_queue_lock_absent": queue_lock_absent,
            "natural_provenance_method": NATURAL_PROVENANCE_METHOD,
            "natural_trigger_verified": False,
            "consecutive_natural_guard_cycles": 0,
            "accepted_natural_cycles": 0,
            "acceptance_status": "NATURAL_ACCEPTANCE_PENDING",
        }
    )
    if result.get("terminal_evidence_verified") is not True:
        return result
    cadence, previous = _cadence_result(
        root,
        scheduled_at=scheduled_at,
        invocation_id=invocation_id,
    )
    result.update(cadence)
    if not (
        child_exit_code == 0
        and final_process_group_quiescent is True
        and denial_absent
        and fog_lock_absent
        and queue_lock_absent
        and cadence["cadence_verified"] is True
        and previous is not None
    ):
        return result
    previous_counter = _accepted_cycle_counter(previous)
    if previous_counter is None:
        return result
    if previous_counter > 0 and not _accepted_chain_qualified_receipt(previous):
        result["accepted_chain_reason"] = "PREVIOUS_ACCEPTED_CHAIN_INVALID"
        return result
    accepted = previous_counter + 1
    result.update(
        {
            "natural_trigger_verified": True,
            "consecutive_natural_guard_cycles": accepted,
            "accepted_natural_cycles": accepted,
            "acceptance_status": (
                "ACCEPTED" if accepted >= 2 else "NATURAL_ACCEPTANCE_PENDING"
            ),
        }
    )
    return result
