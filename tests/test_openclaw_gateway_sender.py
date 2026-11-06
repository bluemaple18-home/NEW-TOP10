from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from scripts import openclaw_gateway_sender as sender


NODE = "/opt/homebrew/opt/node/bin/node"
CLI = "/Users/mattkuo/new clawd/dist/index.js"


def completed(payload: dict, returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=[NODE, str(sender.NODE_ADAPTER)],
        returncode=returncode,
        stdout=json.dumps(payload),
        stderr=stderr,
    )


def test_send_uses_stdin_json_and_validates_message_id() -> None:
    with patch.object(sender.subprocess, "run", return_value=completed({"ok": True, "method": "send", "result": {"messageId": "m-1"}})) as run:
        receipt = sender.gateway_send(
            node_bin=NODE,
            cli_entry=CLI,
            channel="discord",
            target="channel:123",
            message="secret-ish message body",
            namespace="daily-publish:2026-10-13",
        )

    assert receipt["method"] == "send"
    assert receipt["message_id"] == "m-1"
    argv = run.call_args.args[0]
    assert argv == [NODE, str(sender.NODE_ADAPTER)]
    assert "secret-ish message body" not in " ".join(argv)
    request = json.loads(run.call_args.kwargs["input"])
    assert request["operation"] == "send"
    assert request["timeout_ms"] == 60_000
    assert run.call_args.kwargs["timeout"] == 62.0
    assert request["channel"] == "discord"
    assert request["target"] == "channel:123"
    assert request["message"] == "secret-ish message body"
    assert request["idempotency_key"].startswith("top10:daily-publish:2026-10-13:")


def test_gateway_child_inherits_daily_publish_lock_fd(tmp_path: Path) -> None:
    descriptor = os.open(tmp_path / "daily.lock", os.O_CREAT | os.O_RDWR, 0o600)
    directory_descriptor = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        with patch.dict(os.environ, {"TOP10_PUBLISH_LOCK_FD": str(descriptor),
                                  "TOP10_PUBLISH_DIR_LOCK_FD": str(directory_descriptor)}):
            with patch.object(sender.subprocess, "run", return_value=completed({
                "ok": True, "method": "send", "result": {"messageId": "m-1"},
            })) as run:
                sender.gateway_send(node_bin=NODE, cli_entry=CLI, channel="discord",
                    target="channel:123", message="body", namespace="daily-publish:2026-10-15")
        assert run.call_args.kwargs["pass_fds"] == (descriptor, directory_descriptor)
    finally:
        os.close(descriptor)
        os.close(directory_descriptor)


def test_nested_gateway_failure_cannot_be_overridden_by_outer_message_id() -> None:
    assert sender.extract_message_id({"messageId": "m-1", "result": {"ok": False}}) is None
    assert sender.extract_message_id({"messageId": "m-1", "result": {"result": {"ok": False}}}) is None


@pytest.fixture
def local_adapter_paths(tmp_path: Path) -> tuple[str, str]:
    node = tmp_path / "node"
    cli = tmp_path / "index.js"
    node.touch()
    cli.touch()
    return str(node), str(cli)


def test_send_timeout_reports_delivery_outcome_unknown(local_adapter_paths: tuple[str, str]) -> None:
    node, cli = local_adapter_paths
    timeout = subprocess.TimeoutExpired(cmd=[node], timeout=62)
    with patch.object(sender.subprocess, "run", side_effect=timeout):
        with pytest.raises(RuntimeError) as failure:
            sender.gateway_send(
                node_bin=node,
                cli_entry=cli,
                channel="discord",
                target="channel:123",
                message="body",
                namespace="daily-publish:2026-10-15",
            )

    assert type(failure.value).__name__ == "DeliveryOutcomeUnknownError"
    assert failure.value.idempotency_key.startswith("top10:daily-publish:2026-10-15:")


def test_adapter_timeout_reports_delivery_outcome_unknown(local_adapter_paths: tuple[str, str]) -> None:
    node, cli = local_adapter_paths
    adapter_error = completed({}, returncode=1, stderr='{"ok":false,"error":"gateway timeout after 60000ms"}')
    with patch.object(sender.subprocess, "run", return_value=adapter_error):
        with pytest.raises(sender.DeliveryOutcomeUnknownError):
            sender.gateway_send(
                node_bin=node,
                cli_entry=cli,
                channel="discord",
                target="channel:123",
                message="body",
                namespace="ops-report:2026-10-15:daily-2026-10-15",
            )


def test_adapter_preflight_failure_is_known_not_sent(local_adapter_paths: tuple[str, str]) -> None:
    node, cli = local_adapter_paths
    adapter_error = completed({}, returncode=1, stderr='{"ok":false,"error":"SDK missing","phase":"preflight"}')
    with patch.object(sender.subprocess, "run", return_value=adapter_error):
        with pytest.raises(RuntimeError, match="adapter preflight failed") as failure:
            sender.gateway_send(node_bin=node, cli_entry=cli, channel="discord",
                                target="channel:123", message="body", namespace="daily-publish:2026-10-15")
    assert not isinstance(failure.value, sender.DeliveryOutcomeUnknownError)


def test_post_send_adapter_failure_is_delivery_unknown(local_adapter_paths: tuple[str, str]) -> None:
    node, cli = local_adapter_paths
    adapter_error = completed({}, returncode=1, stderr='{"ok":false,"error":"bad target"}')
    with patch.object(sender.subprocess, "run", return_value=adapter_error):
        with pytest.raises(sender.DeliveryOutcomeUnknownError) as failure:
            sender.gateway_send(
                node_bin=node,
                cli_entry=cli,
                channel="discord",
                target="channel:123",
                message="body",
                namespace="daily-publish:2026-10-15",
            )
    assert failure.value.idempotency_key.startswith("top10:daily-publish:2026-10-15:")


@pytest.mark.parametrize(
    "result",
    [
        subprocess.CompletedProcess(
            args=[NODE], returncode=1, stdout="", stderr='warning before receipt\n{"ok":false,"error":"gateway timeout"}'
        ),
        subprocess.CompletedProcess(args=[NODE], returncode=0, stdout="not-json", stderr=""),
    ],
)
def test_unparseable_post_send_result_is_delivery_unknown(
    local_adapter_paths: tuple[str, str], result: subprocess.CompletedProcess[str]
) -> None:
    node, cli = local_adapter_paths
    with patch.object(sender.subprocess, "run", return_value=result):
        with pytest.raises(sender.DeliveryOutcomeUnknownError):
            sender.gateway_send(
                node_bin=node,
                cli_entry=cli,
                channel="discord",
                target="channel:123",
                message="body",
                namespace="daily-publish:2026-10-15",
            )


def test_presentation_uses_message_action_and_is_never_dropped() -> None:
    response = {"ok": True, "method": "message.action", "result": {"ok": True, "result": {"messageId": "m-2"}}}
    with patch.object(sender.subprocess, "run", return_value=completed(response)) as run:
        receipt = sender.gateway_send(
            node_bin=NODE,
            cli_entry=CLI,
            channel="discord",
            target="channel:ops",
            message="ops",
            presentation={"blocks": [{"type": "text", "text": "review"}]},
            namespace="ops-report:2026-10-13:daily-2026-10-13",
        )

    request = json.loads(run.call_args.kwargs["input"])
    assert request["operation"] == "message_action"
    assert request["presentation"]["blocks"][0]["text"] == "review"
    assert receipt["method"] == "message.action"
    assert receipt["message_id"] == "m-2"


def test_presentation_on_unknown_transport_fails_closed() -> None:
    with pytest.raises(RuntimeError, match="presentation"):
        sender.gateway_send(
            node_bin=NODE,
            cli_entry=CLI,
            channel="slack",
            target="channel:ops",
            message="ops",
            presentation={"blocks": [{"type": "text", "text": "review"}]},
            namespace="ops",
        )


def test_health_is_read_only_operation_and_never_requests_send() -> None:
    with patch.object(sender.subprocess, "run", return_value=completed({"ok": True, "method": "health", "result": {"status": "ok"}})) as run:
        result = sender.gateway_health(node_bin=NODE, cli_entry=CLI)

    assert result["status"] == "ok"
    request = json.loads(run.call_args.kwargs["input"])
    assert request == {"cli_entry": CLI, "timeout_ms": 10000, "operation": "health"}


def test_gateway_failure_is_nonzero_and_not_retried() -> None:
    run = Mock(return_value=completed({"ok": False}, returncode=1, stderr='{"ok":false,"error":"denied"}'))
    with patch.object(sender.subprocess, "run", run):
        with pytest.raises(RuntimeError, match="denied"):
            sender.gateway_health(node_bin=NODE, cli_entry=CLI)
    assert run.call_count == 1


def test_subprocess_file_not_found_keeps_delivery_unknown() -> None:
    with patch.object(sender.subprocess, "run", side_effect=FileNotFoundError("cannot spawn")) as run:
        with pytest.raises(sender.DeliveryOutcomeUnknownError):
            sender.gateway_send(
                node_bin=NODE, cli_entry=CLI, channel="discord", target="channel:123",
                message="body", namespace="daily-publish:2026-10-15",
            )
    assert run.call_count == 1


def test_post_spawn_io_error_keeps_delivery_unknown() -> None:
    with patch.object(sender.subprocess, "run", side_effect=BrokenPipeError("after spawn")):
        with pytest.raises(sender.DeliveryOutcomeUnknownError):
            sender.gateway_send(
                node_bin=NODE, cli_entry=CLI, channel="discord", target="channel:123",
                message="body", namespace="daily-publish:2026-10-15",
            )


def test_missing_adapter_is_proven_not_sent(tmp_path: Path) -> None:
    with patch.object(sender, "NODE_ADAPTER", tmp_path / "missing.mjs"):
        with pytest.raises(sender.GatewayPreflightError, match="adapter missing"):
            sender.gateway_send(
                node_bin=NODE, cli_entry=CLI, channel="discord", target="channel:123",
                message="body", namespace="daily-publish:2026-10-15",
            )


def test_gateway_timeout_is_nonzero_and_not_retried() -> None:
    run = Mock(side_effect=subprocess.TimeoutExpired(cmd=[NODE], timeout=12))
    with patch.object(sender.subprocess, "run", run):
        with pytest.raises(RuntimeError, match="timeout after 10000ms"):
            sender.gateway_health(node_bin=NODE, cli_entry=CLI)
    assert run.call_count == 1


def test_live_send_rejects_invalid_receipt() -> None:
    with patch.object(sender.subprocess, "run", return_value=completed({"ok": True, "method": "send", "result": {"channel": "discord"}})):
        with pytest.raises(sender.DeliveryOutcomeUnknownError):
            sender.gateway_send(
                node_bin=NODE,
                cli_entry=CLI,
                channel="discord",
                target="channel:123",
                message="body",
                namespace="daily",
            )


@pytest.mark.parametrize("message_id", ["unknown", " invalid ", " ", True, 123, None])
def test_live_send_rejects_invalid_message_id_values(message_id: object) -> None:
    response = {"ok": True, "method": "send", "result": {"messageId": message_id}}
    with patch.object(sender.subprocess, "run", return_value=completed(response)):
        with pytest.raises(sender.DeliveryOutcomeUnknownError):
            sender.gateway_send(
                node_bin=NODE,
                cli_entry=CLI,
                channel="discord",
                target="channel:123",
                message="body",
                namespace="daily",
            )


def test_live_send_rejects_nested_failed_payload_even_with_message_id() -> None:
    response = {
        "ok": True,
        "method": "message.action",
        "result": {"ok": False, "result": {"messageId": "m-should-not-pass"}},
    }
    with patch.object(sender.subprocess, "run", return_value=completed(response)):
        with pytest.raises(sender.DeliveryOutcomeUnknownError):
            sender.gateway_send(
                node_bin=NODE,
                cli_entry=CLI,
                channel="discord",
                target="channel:123",
                message="body",
                namespace="daily",
                presentation={"blocks": []},
            )


def test_stable_idempotency_key_changes_only_with_request_content() -> None:
    kwargs = {"channel": "discord", "target": "channel:123", "message": "body"}
    first = sender.stable_idempotency_key("daily", **kwargs)
    second = sender.stable_idempotency_key("daily", **kwargs)
    changed = sender.stable_idempotency_key("daily", **{**kwargs, "message": "different"})
    assert first == second
    assert first != changed


def test_node_adapter_derives_plugin_sdk_path_from_cli_entry(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    sdk = dist / "plugin-sdk"
    sdk.mkdir(parents=True)
    (dist / "index.js").write_text("// fixture\n", encoding="utf-8")
    (dist / "package.json").write_text('{"type":"module"}\n', encoding="utf-8")
    (sdk / "gateway-runtime.js").write_text(
        "export async function callGatewayFromCli(method, opts, params, extra) {\n"
        "  return {method, timeout: opts.timeout, params, extra};\n"
        "}\n",
        encoding="utf-8",
    )
    request = {
        "cli_entry": str(dist / "index.js"),
        "timeout_ms": 4321,
        "operation": "health",
    }
    proc = subprocess.run(
        [NODE, str(sender.NODE_ADAPTER)],
        input=json.dumps(request),
        text=True,
        capture_output=True,
        check=False,
    )
    payload = json.loads(proc.stdout)
    assert proc.returncode == 0, proc.stderr
    assert payload["result"]["method"] == "health"
    assert payload["result"]["extra"]["clientName"] == "gateway-client"
    assert payload["result"]["extra"]["mode"] == "backend"
    assert payload["result"]["extra"]["deviceIdentity"] is None
    assert payload["result"]["extra"]["scopes"] == ["operator.read"]
