#!/usr/bin/env python3
"""TOP10 對 OpenClaw 官方 gateway SDK 的薄傳輸層。"""

from __future__ import annotations

import hashlib
import json
import os
import fcntl
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
NODE_ADAPTER = PROJECT_ROOT / "scripts" / "openclaw_gateway_adapter.mjs"
INVALID_MESSAGE_ID_SENTINELS = {
    "unknown",
    "invalid",
    "none",
    "null",
    "undefined",
    "n/a",
    "na",
}


class DeliveryOutcomeUnknownError(RuntimeError):
    """送出逾時後無法判定遠端結果；保留去重鍵供唯讀核對。"""

    def __init__(self, *, idempotency_key: str, timeout_ms: int) -> None:
        super().__init__(
            f"OpenClaw send delivery outcome unknown; no reliable receipt (timeout budget {timeout_ms}ms); "
            "do not retry before remote readback"
        )
        self.idempotency_key = idempotency_key
        self.timeout_ms = timeout_ms


class GatewayPreflightError(RuntimeError):
    """Adapter 已確認在呼叫 gateway 前失敗，遠端尚未送出。"""


def protected_delivery_receipt(path: Path) -> bool:
    """既有成功或未決送出收據不可由重跑／dry-run 覆寫。"""
    if not path.exists():
        return False
    try:
        previous = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Existing send receipt unreadable; refuse to overwrite: {path}") from exc
    if not isinstance(previous, dict):
        raise RuntimeError(f"Existing send receipt invalid; refuse to overwrite: {path}")
    if previous.get("status") in {"OK", "DRY_RUN"} and previous.get("dry_run") is True and previous.get("send_attempted") is False:
        return False
    if previous.get("status") == "FAILED" and previous.get("preflight_failed") is True and previous.get("send_attempted") is False and previous.get("delivery_outcome") in {None, "NOT_SENT"}:
        return False
    return True


@contextmanager
def receipt_lock(path: Path):
    """同日收據的短時排他鎖；檢查與 claim 必須在同一臨界區。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(str(path) + ".lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def claim_send_attempt(
    path: Path, status: dict[str, Any], *, precondition: Callable[[], bool] | None = None,
) -> bool:
    """先持久化未決送出；同一收據只准一個程序取得發送權。"""
    with receipt_lock(path):
        if protected_delivery_receipt(path):
            return False
        if precondition is not None and not precondition():
            return False
        write_send_status(path, status)
        return True


def write_non_send_status(path: Path, status: dict[str, Any]) -> bool:
    """dry-run 與前置失敗不得覆寫已送出或未決收據。"""
    with receipt_lock(path):
        if protected_delivery_receipt(path):
            return False
        write_send_status(path, status)
        return True


def write_send_status(path: Path, status: dict[str, Any]) -> None:
    """原子且持久地記錄送出狀態；外送前須先記未決狀態。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
            temporary = handle.name
            json.dump(status, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)


def finalize_send_status(path: Path, status: dict[str, Any]) -> None:
    """最終收據與事件寫入共用同日鎖，避免晚到失敗事件覆寫成功。"""
    with receipt_lock(path):
        write_send_status(path, status)


def stable_idempotency_key(
    namespace: str,
    *,
    channel: str,
    target: str,
    message: str,
    presentation: dict[str, Any] | None = None,
) -> str:
    """同一份 logical send 產生固定 key，供 Gateway 去重。"""
    material = json.dumps(
        {
            "namespace": namespace,
            "channel": channel,
            "target": target,
            "message": message,
            "presentation": presentation,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"top10:{namespace}:{hashlib.sha256(material).hexdigest()}"


def gateway_health(*, node_bin: str, cli_entry: str, timeout_ms: int = 10_000) -> dict[str, Any]:
    """唯讀 SDK/auth 健康檢查；不觸發 message send。"""
    response = _invoke(
        node_bin=node_bin,
        cli_entry=cli_entry,
        timeout_ms=timeout_ms,
        request={"operation": "health"},
    )
    return _result_object(response)


def gateway_send(
    *,
    node_bin: str,
    cli_entry: str,
    channel: str,
    target: str,
    message: str,
    namespace: str,
    presentation: dict[str, Any] | None = None,
    timeout_ms: int = 60_000,
) -> dict[str, Any]:
    """送出一次 transport request；不自動重送，成功必須取得實際 message id。"""
    if presentation is not None and channel != "discord":
        raise RuntimeError("presentation 僅允許走已確認的 Discord message.action seam")
    idempotency_key = stable_idempotency_key(
        namespace,
        channel=channel,
        target=target,
        message=message,
        presentation=presentation,
    )
    operation = "message_action" if presentation is not None else "send"
    response = _invoke(
        node_bin=node_bin,
        cli_entry=cli_entry,
        timeout_ms=timeout_ms,
        request={
            "operation": operation,
            "channel": channel,
            "target": target,
            "message": message,
            "presentation": presentation,
            "idempotency_key": idempotency_key,
        },
    )
    try:
        result = _result_object(response)
        message_id = extract_message_id(result)
    except RuntimeError as exc:
        raise DeliveryOutcomeUnknownError(idempotency_key=idempotency_key, timeout_ms=timeout_ms) from exc
    if message_id is None:
        raise DeliveryOutcomeUnknownError(idempotency_key=idempotency_key, timeout_ms=timeout_ms)
    return {
        "method": str(response.get("method") or operation),
        "message_id": message_id,
        "idempotency_key": idempotency_key,
    }


def extract_message_id(result: dict[str, Any]) -> str | None:
    """只接受已知 send/message.action receipt 位置，未知 shape 直接失敗。"""
    if result.get("ok") is False:
        return None

    nested = result.get("result")
    if isinstance(nested, dict):
        if nested.get("ok") is False:
            return None
        second = nested.get("result")
        if isinstance(second, dict) and second.get("ok") is False:
            return None

    message_id = normalize_message_id(result.get("messageId"))
    if message_id is not None:
        return message_id

    if isinstance(nested, dict):
        message_id = normalize_message_id(nested.get("messageId"))
        if message_id is not None:
            return message_id

        second = nested.get("result")
        if isinstance(second, dict):
            return normalize_message_id(second.get("messageId"))
    return None


def normalize_message_id(value: Any) -> str | None:
    """共用 receipt ID 驗證：只接受非空且不是 vendor sentinel 的字串。"""
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized or normalized.casefold() in INVALID_MESSAGE_ID_SENTINELS:
        return None
    return normalized


def adapter_command(node_bin: str) -> list[str]:
    """供 status receipt 記錄，不含 message、presentation 或 secret。"""
    return [node_bin, str(NODE_ADAPTER), "<stdin-json>"]


def _invoke(
    *,
    node_bin: str,
    cli_entry: str,
    timeout_ms: int,
    request: dict[str, Any],
) -> dict[str, Any]:
    node_path = Path(node_bin)
    cli_path = Path(cli_entry)
    if not node_path.exists():
        raise GatewayPreflightError(f"OpenClaw node binary missing: {node_bin}")
    if not cli_path.exists():
        raise GatewayPreflightError(f"OpenClaw CLI entry missing: {cli_entry}")
    if not NODE_ADAPTER.exists():
        raise GatewayPreflightError(f"OpenClaw gateway adapter missing: {NODE_ADAPTER}")
    payload = {"cli_entry": str(cli_path), "timeout_ms": timeout_ms, **request}
    inherited_lock = os.environ.get("TOP10_PUBLISH_LOCK_FD")
    pass_fds: tuple[int, ...] = ()
    if inherited_lock is not None:
        try:
            descriptor = int(inherited_lock)
            os.fstat(descriptor)
            directory_descriptor = int(os.environ["TOP10_PUBLISH_DIR_LOCK_FD"])
            os.fstat(directory_descriptor)
            pass_fds = (descriptor, directory_descriptor)
        except (ValueError, OSError):
            raise GatewayPreflightError("Daily publish lock descriptor unavailable")
    try:
        completed = subprocess.run(
            [str(node_path), str(NODE_ADAPTER)],
            cwd=cli_path.resolve().parent,
            input=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            text=True,
            capture_output=True,
            pass_fds=pass_fds,
            timeout=max(1.0, timeout_ms / 1000 + 2.0),
            check=False,
        )
    except OSError as exc:
        # subprocess.run 的例外無法證明 child 從未啟動；只允許上方顯式檢查判定未送出。
        if request.get("operation") in {"send", "message_action"}:
            raise DeliveryOutcomeUnknownError(
                idempotency_key=str(request["idempotency_key"]), timeout_ms=timeout_ms
            ) from exc
        raise RuntimeError(f"OpenClaw adapter I/O error: {type(exc).__name__}") from exc
    except subprocess.TimeoutExpired as exc:
        if request.get("operation") in {"send", "message_action"}:
            raise DeliveryOutcomeUnknownError(
                idempotency_key=str(request["idempotency_key"]), timeout_ms=timeout_ms
            ) from exc
        raise RuntimeError(f"OpenClaw gateway SDK timeout after {timeout_ms}ms") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or f"exit_code={completed.returncode}"
        try:
            failure = json.loads(completed.stderr)
        except (json.JSONDecodeError, TypeError):
            failure = None
        if isinstance(failure, dict) and failure.get("phase") == "preflight":
            raise GatewayPreflightError(f"OpenClaw gateway adapter preflight failed: {failure.get('error')}")
        if request.get("operation") in {"send", "message_action"}:
            raise DeliveryOutcomeUnknownError(
                idempotency_key=str(request["idempotency_key"]), timeout_ms=timeout_ms
            )
        raise RuntimeError(f"OpenClaw gateway SDK failed: {detail}")
    try:
        response = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        if request.get("operation") in {"send", "message_action"}:
            raise DeliveryOutcomeUnknownError(
                idempotency_key=str(request["idempotency_key"]), timeout_ms=timeout_ms
            ) from exc
        raise RuntimeError("OpenClaw gateway SDK returned invalid JSON") from exc
    if not isinstance(response, dict) or response.get("ok") is not True:
        if request.get("operation") in {"send", "message_action"}:
            raise DeliveryOutcomeUnknownError(
                idempotency_key=str(request["idempotency_key"]), timeout_ms=timeout_ms
            )
        raise RuntimeError("OpenClaw gateway SDK returned unsuccessful response")
    return response


def _result_object(response: dict[str, Any]) -> dict[str, Any]:
    result = response.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("OpenClaw gateway SDK response missing object result")
    return result
