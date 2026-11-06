"""送出逾時時，兩條正式 sender 都保留未知結果且禁止直接重送。"""

from __future__ import annotations

import json
import hashlib
import os
import stat
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from threading import Event
from zoneinfo import ZoneInfo

import pytest

from scripts import send_clawd_publish_message as top10
from scripts import send_top10_ops_report as ops
from scripts import record_top10_publish_event
from scripts import build_top10_agent_status_rollup as rollup_cli
from scripts import verify_daily_publish_workflow
from scripts.top10_agent_status import event_record_complete, rollup_lock
from scripts.daily_publish_lock import exclusive_publish_access, inherited_lock_valid
from scripts import daily_publish_lock as publish_lock
from scripts.openclaw_gateway_sender import DeliveryOutcomeUnknownError, claim_send_attempt, protected_delivery_receipt, stable_idempotency_key, write_non_send_status


def _today() -> str:
    return datetime.now(ZoneInfo("Asia/Taipei")).date().isoformat()


def test_top10_timeout_writes_unknown_receipt_without_retry(tmp_path: Path, monkeypatch) -> None:
    today = _today()
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    message = artifacts / f"clawd_publish_message_{today}.md"
    payload_path = artifacts / f"clawd_publish_payload_{today}.json"
    status_path = artifacts / f"clawd_send_status_{today}.json"
    config_path = tmp_path / "automation.yaml"
    node_bin = tmp_path / "node"
    cli_entry = tmp_path / "index.js"
    node_bin.touch()
    cli_entry.touch()
    message.write_text("Top10 測試內容", encoding="utf-8")
    payload_path.write_text(json.dumps({
        "ranking_date": today,
        "delivery": {"status": "READY_FOR_CLAWD", "channel": "discord", "to": "channel:123"},
        "artifacts": {"message": str(message)},
    }), encoding="utf-8")
    config_path.write_text(
        "notify:\n  clawd_enabled: true\n  clawd_dry_run: false\n  clawd_channel: discord\n"
        f"  clawd_to: channel:123\n  clawd_cli_node: {node_bin}\n  clawd_cli_entry: {cli_entry}\n",
        encoding="utf-8",
    )
    calls = []

    def fail_send(**kwargs):
        calls.append(kwargs)
        pending = json.loads(status_path.read_text(encoding="utf-8"))
        assert pending["status"] == "DELIVERY_PENDING"
        assert pending["retry_allowed"] is False
        raise top10.DeliveryOutcomeUnknownError(idempotency_key="top10:daily-publish:test-key", timeout_ms=60_000)

    monkeypatch.setattr(top10, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(top10, "gateway_send", fail_send)
    monkeypatch.setattr(sys, "argv", [
        "send_clawd_publish_message.py", "--message", str(message), "--payload", str(payload_path),
        "--config", str(config_path), "--output", str(status_path), "--send",
    ])
    canonical_argv = sys.argv.copy()
    alias = status_path.parent / "alias.json"
    alias.parent.mkdir(parents=True, exist_ok=True)
    alias.symlink_to(status_path)
    monkeypatch.setattr(sys, "argv", [*canonical_argv[:-3], "--output", str(alias), "--send"])
    assert top10.main() == 2
    assert not status_path.exists() and not calls
    monkeypatch.setattr(sys, "argv", canonical_argv)
    assert top10.main() == 1
    status = json.loads(status_path.read_text(encoding="utf-8"))
    assert len(calls) == 1
    assert status["status"] == "DELIVERY_UNKNOWN"
    assert status["delivery_outcome"] == "UNKNOWN"
    assert status["retry_allowed"] is False
    assert status["idempotency_key"] == "top10:daily-publish:test-key"
    assert status["receipt"] is None and status["exit_code"] == 1
    preserved = status_path.read_bytes()
    assert top10.main() == 2
    assert len(calls) == 1 and status_path.read_bytes() == preserved
    monkeypatch.setattr(sys, "argv", sys.argv[:-1])
    assert top10.main() == 2
    assert len(calls) == 1 and status_path.read_bytes() == preserved
    status["status"] = "OK"
    status["delivery_outcome"] = "CONFIRMED"
    status_path.write_text(json.dumps(status), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [*sys.argv, "--send"])
    assert top10.main() == 2
    assert len(calls) == 1
    monkeypatch.setattr(sys, "argv", [*sys.argv, "--output", str(tmp_path / "alternate.json")])
    assert top10.main() == 2
    assert len(calls) == 1


def test_ops_timeout_writes_unknown_receipt_without_retry(tmp_path: Path, monkeypatch) -> None:
    today = _today()
    message = tmp_path / f"ops_progress_message_{today}.md"
    rollup_root = tmp_path / "harness_status" / today
    rollup_root.mkdir(parents=True)
    rollup = rollup_root / "latest_rollup.json"
    (rollup_root / "latest_run_id.txt").write_text(f"daily-{today}\n", encoding="utf-8")
    status_path = tmp_path / f"ops_progress_send_status_{today}.json"
    config_path = tmp_path / "automation.yaml"
    node_bin = tmp_path / "node"
    cli_entry = tmp_path / "index.js"
    node_bin.touch()
    cli_entry.touch()
    message.write_text("進度測試內容", encoding="utf-8")
    rollup.write_text(json.dumps({"run_date": today, "run_id": f"daily-{today}"}), encoding="utf-8")
    config_path.write_text(
        "notify:\n  ops_clawd_enabled: true\n  ops_clawd_dry_run: false\n  ops_clawd_channel: discord\n"
        f"  ops_clawd_to: channel:456\n  clawd_cli_node: {node_bin}\n  clawd_cli_entry: {cli_entry}\n",
        encoding="utf-8",
    )
    calls = []
    events = []
    builds = []

    def fail_send(**kwargs):
        calls.append(kwargs)
        pending = json.loads(status_path.read_text(encoding="utf-8"))
        assert pending["status"] == "DELIVERY_PENDING"
        assert pending["retry_allowed"] is False
        raise ops.DeliveryOutcomeUnknownError(idempotency_key="top10:ops-report:test-key", timeout_ms=60_000)

    monkeypatch.setattr(ops, "resolve_rollup_path", lambda *_: rollup)
    monkeypatch.setattr(ops, "build_strategy_archetype_evidence_map", lambda **_: builds.append("evidence"))
    monkeypatch.setattr(ops, "build_research_decision_brief", lambda **_: builds.append("brief"))
    monkeypatch.setattr(ops, "gateway_send", fail_send)
    monkeypatch.setattr(ops, "ARTIFACTS_DIR", tmp_path)
    monkeypatch.setattr(ops, "_write_ops_event_locked", lambda status, **_: events.append(status.copy()))
    monkeypatch.setattr(sys, "argv", [
        "send_top10_ops_report.py", "--run-date", today, "--artifacts-dir", str(tmp_path),
        "--message", str(message), "--config", str(config_path), "--output", str(status_path), "--send",
    ])
    assert ops.main() == 1
    status = json.loads(status_path.read_text(encoding="utf-8"))
    assert len(calls) == 1 and len(events) == 1
    assert status["status"] == "DELIVERY_UNKNOWN"
    assert status["delivery_outcome"] == "UNKNOWN"
    assert status["retry_allowed"] is False
    assert status["idempotency_key"] == "top10:ops-report:test-key"
    assert status["receipt"] is None and status["exit_code"] == 1
    preserved = status_path.read_bytes()
    assert ops.main() == 2
    assert len(calls) == 1 and status_path.read_bytes() == preserved and builds == ["evidence", "brief"]
    monkeypatch.setattr(sys, "argv", sys.argv[:-1])
    assert ops.main() == 2
    assert len(calls) == 1 and status_path.read_bytes() == preserved
    monkeypatch.setattr(sys, "argv", [*sys.argv, "--send", "--output", str(tmp_path / "alternate.json")])
    assert ops.main() == 2
    assert len(calls) == 1


def test_unknown_delivery_cannot_pass_publish_verification_or_recommend_retry(tmp_path: Path, monkeypatch) -> None:
    today = _today()
    (tmp_path / f"clawd_publish_payload_{today}.json").write_text(json.dumps({
        "ranking_date": today, "delivery": {"status": "READY_FOR_CLAWD"}
    }), encoding="utf-8")
    (tmp_path / f"clawd_publish_message_{today}.md").write_text(f"Top10 {today}\n", encoding="utf-8")
    status = {
        "schema_version": "clawd-send-status.v1",
        "status": "DELIVERY_UNKNOWN",
        "message_date": today,
        "dry_run": False,
        "send_attempted": True,
        "receipt": None,
    }
    (tmp_path / f"clawd_send_status_{today}.json").write_text(json.dumps(status), encoding="utf-8")
    monkeypatch.setattr(verify_daily_publish_workflow, "ARTIFACTS_DIR", tmp_path)
    errors: list[str] = []
    verify_daily_publish_workflow.check_publish_artifacts(today, True, errors, [], {})
    assert any("send_status.status must be OK" in item for item in errors)
    assert record_top10_publish_event.default_decision("degraded") == "stop"
    assert "核對" in record_top10_publish_event.next_action("degraded", "delivery outcome unknown")
    assert "重送" in record_top10_publish_event.next_action("degraded", "delivery outcome unknown")


def test_live_verifier_binds_receipt_to_current_message_and_target(tmp_path: Path, monkeypatch) -> None:
    today = _today()
    message = tmp_path / f"clawd_publish_message_{today}.md"
    payload = tmp_path / f"clawd_publish_payload_{today}.json"
    send_status = tmp_path / f"clawd_send_status_{today}.json"
    message.write_text(f"Top10 {today}\n", encoding="utf-8")
    payload.write_text(json.dumps({
        "ranking_date": today,
        "delivery": {"status": "READY_FOR_CLAWD", "channel": "discord", "to": "channel:123"},
    }), encoding="utf-8")
    key = stable_idempotency_key(
        f"daily-publish:{today}", channel="discord", target="channel:123", message=message.read_text()
    )
    send_status.write_text(json.dumps({
        "schema_version": "clawd-send-status.v2", "status": "OK", "message_date": today,
            "run_id": f"daily-{today}",
        "dry_run": False, "send_attempted": True, "message_path": str(message),
        "message_sha256": hashlib.sha256(message.read_bytes()).hexdigest(),
        "channel": "discord", "target": "channel:123", "idempotency_key": key,
        "receipt": {"message_id": "m-123", "idempotency_key": key},
    }), encoding="utf-8")
    monkeypatch.setattr(verify_daily_publish_workflow, "ARTIFACTS_DIR", tmp_path)
    errors: list[str] = []
    verify_daily_publish_workflow.check_publish_artifacts(today, True, errors, [], {})
    assert "daily_push event and rollup must be complete for confirmed live publish" in errors
    root = tmp_path / "harness_status" / today / f"daily-{today}"
    (root / "events").mkdir(parents=True)
    event = {"agent_id": "daily_push", "run_date": today, "run_id": f"daily-{today}",
             "status": "ok", "decision": "pass"}
    (root / "events" / "daily_push.json").write_text(json.dumps(event), encoding="utf-8")
    (root / "events.jsonl").write_text(json.dumps(event) + "\n", encoding="utf-8")
    (root.parent / "latest_run_id.txt").write_text(f"daily-{today}\n", encoding="utf-8")
    rollup = {"run_date": today, "run_id": f"daily-{today}",
              "agents": [{"agent_id": "daily_push", "status": "ok"}]}
    (root / "rollup.json").write_text(json.dumps(rollup), encoding="utf-8")
    (root.parent / "latest_rollup.json").write_text(json.dumps(rollup), encoding="utf-8")
    errors = []
    verify_daily_publish_workflow.check_publish_artifacts(today, True, errors, [], {})
    assert errors == []
    message.write_text(f"Top10 {today}\n內容已改變\n", encoding="utf-8")
    errors = []
    verify_daily_publish_workflow.check_publish_artifacts(today, True, errors, [], {})
    assert any("message_sha256" in item for item in errors)
    assert any("idempotency_key" in item for item in errors)


def test_process_crash_after_send_started_keeps_pending_receipt(tmp_path: Path, monkeypatch) -> None:
    today = _today()
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    message = artifacts / f"clawd_publish_message_{today}.md"
    payload = artifacts / f"clawd_publish_payload_{today}.json"
    status_path = artifacts / f"clawd_send_status_{today}.json"
    node = tmp_path / "node"
    cli = tmp_path / "index.js"
    config = tmp_path / "config.yaml"
    node.touch()
    cli.touch()
    message.write_text(f"Top10 {today}\n", encoding="utf-8")
    payload.write_text(json.dumps({
        "ranking_date": today,
        "delivery": {"status": "READY_FOR_CLAWD", "channel": "discord", "to": "channel:123"},
        "artifacts": {"message": str(message)},
    }), encoding="utf-8")
    config.write_text(
        "notify:\n  clawd_enabled: true\n  clawd_dry_run: false\n  clawd_channel: discord\n"
        f"  clawd_to: channel:123\n  clawd_cli_node: {node}\n  clawd_cli_entry: {cli}\n",
        encoding="utf-8",
    )
    calls = []

    def crash_after_start(**kwargs):
        calls.append(kwargs)
        raise SystemExit(99)

    monkeypatch.setattr(top10, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(top10, "gateway_send", crash_after_start)
    monkeypatch.setattr(sys, "argv", [
        "send_clawd_publish_message.py", "--message", str(message), "--payload", str(payload),
        "--config", str(config), "--send",
    ])
    with pytest.raises(SystemExit, match="99"):
        top10.main()
    pending = status_path.read_bytes()
    assert json.loads(pending)["status"] == "DELIVERY_PENDING"
    assert top10.main() == 2
    assert len(calls) == 1 and status_path.read_bytes() == pending


def test_concurrent_claim_and_dry_run_cannot_replace_pending(tmp_path: Path) -> None:
    receipt = tmp_path / "send.json"
    pending = {"status": "DELIVERY_PENDING", "send_attempted": True, "retry_allowed": False}
    with ThreadPoolExecutor(max_workers=8) as pool:
        claims = list(pool.map(lambda _: claim_send_attempt(receipt, pending), range(8)))
    assert claims.count(True) == 1
    assert write_non_send_status(receipt, {"status": "OK", "dry_run": True, "send_attempted": False}) is False
    assert json.loads(receipt.read_text())["status"] == "DELIVERY_PENDING"


def test_semantically_incomplete_receipt_blocks_claim(tmp_path: Path) -> None:
    receipt = tmp_path / "send.json"
    receipt.write_text('{"status":"DELIVERY_PENDING"}', encoding="utf-8")
    assert protected_delivery_receipt(receipt)
    assert not claim_send_attempt(receipt, {"status": "DELIVERY_PENDING", "send_attempted": True})


def test_dry_run_and_proven_not_sent_are_replaceable(tmp_path: Path) -> None:
    receipt = tmp_path / "send.json"
    for previous in (
        {"status": "DRY_RUN", "dry_run": True, "send_attempted": False},
        {"status": "FAILED", "preflight_failed": True, "send_attempted": False,
         "delivery_outcome": "NOT_SENT"},
    ):
        receipt.write_text(json.dumps(previous), encoding="utf-8")
        assert claim_send_attempt(receipt, {"status": "DELIVERY_PENDING", "send_attempted": True})
    assert json.loads(receipt.read_text())["status"] == "DELIVERY_PENDING"


def test_confirmed_top10_receipt_can_recover_only_same_message_event(tmp_path: Path) -> None:
    today = _today()
    message = tmp_path / f"clawd_publish_message_{today}.md"
    message.write_text("Top10 測試內容", encoding="utf-8")
    key = stable_idempotency_key(
        f"daily-publish:{today}", channel="discord", target="channel:123", message=message.read_text()
    )
    (tmp_path / f"clawd_publish_payload_{today}.json").write_text(json.dumps({
        "ranking_date": today, "delivery": {"channel": "discord", "to": "channel:123"},
    }), encoding="utf-8")
    (tmp_path / f"clawd_send_status_{today}.json").write_text(json.dumps({
        "schema_version": "clawd-send-status.v2", "status": "OK", "message_date": today,
        "run_id": f"daily-{today}",
        "dry_run": False, "send_attempted": True, "message_path": str(message),
        "message_sha256": hashlib.sha256(message.read_bytes()).hexdigest(),
        "channel": "discord", "target": "channel:123", "idempotency_key": key,
        "receipt": {"message_id": "m-123", "idempotency_key": key},
    }), encoding="utf-8")
    assert record_top10_publish_event.confirmed_send_matches(tmp_path, today, message)
    assert not record_top10_publish_event.confirmed_send_matches(tmp_path, today, message, run_id="daily-new")
    assert record_top10_publish_event.confirmed_delivery_exists(tmp_path, today)
    message.write_text("Top10 改變內容", encoding="utf-8")
    assert not record_top10_publish_event.confirmed_send_matches(tmp_path, today, message)


def test_late_degraded_event_cannot_replace_confirmed_delivery(tmp_path: Path, monkeypatch) -> None:
    today = _today()
    receipt = tmp_path / "artifacts" / f"clawd_send_status_{today}.json"
    receipt.parent.mkdir()
    receipt.write_text(json.dumps({"status": "OK", "message_date": today,
        "dry_run": False, "send_attempted": True, "receipt": {"message_id": "m-123"}}), encoding="utf-8")
    monkeypatch.setattr(record_top10_publish_event, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(record_top10_publish_event, "ARTIFACTS_DIR", receipt.parent)
    monkeypatch.setattr(record_top10_publish_event, "write_agent_event", lambda *_ , **__: pytest.fail("overwrote success"))
    monkeypatch.setattr(sys, "argv", ["record_top10_publish_event.py", "--run-date", today,
        "--status", "degraded"])
    assert record_top10_publish_event.main() == 2


@pytest.mark.parametrize("unresolved", ["DELIVERY_PENDING", "DELIVERY_UNKNOWN"])
def test_later_skip_cannot_hide_unresolved_delivery(
    tmp_path: Path, monkeypatch, unresolved: str,
) -> None:
    today = _today()
    receipt = tmp_path / "artifacts" / f"clawd_send_status_{today}.json"
    receipt.parent.mkdir()
    receipt.write_text(json.dumps({"status": unresolved, "message_date": today,
        "retry_allowed": False, "send_attempted": True}), encoding="utf-8")
    monkeypatch.setattr(record_top10_publish_event, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(record_top10_publish_event, "ARTIFACTS_DIR", receipt.parent)
    monkeypatch.setattr(record_top10_publish_event, "write_agent_event", lambda *_, **__: pytest.fail("hid pending send"))
    monkeypatch.setattr(sys, "argv", ["record_top10_publish_event.py", "--run-date", today,
        "--status", "skipped"])
    assert record_top10_publish_event.main() == 2


def test_pending_receipt_can_restore_degraded_publish_event(tmp_path: Path, monkeypatch) -> None:
    today = _today()
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / f"clawd_send_status_{today}.json").write_text(json.dumps({
        "status": "DELIVERY_PENDING", "message_date": today,
        "send_attempted": True, "retry_allowed": False,
    }), encoding="utf-8")
    events: list[dict] = []
    monkeypatch.setattr(record_top10_publish_event, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(record_top10_publish_event, "ARTIFACTS_DIR", artifacts)
    monkeypatch.setattr(record_top10_publish_event, "write_agent_event", lambda event, **_: events.append(event))
    monkeypatch.setattr(record_top10_publish_event, "read_manifest", lambda *_: {})
    monkeypatch.setattr(record_top10_publish_event, "build_rollup", lambda *_, **__: {"status": "degraded"})
    monkeypatch.setattr(record_top10_publish_event, "write_rollup", lambda *_: None)
    monkeypatch.setattr(sys, "argv", ["record_top10_publish_event.py", "--run-date", today,
        "--status", "degraded", "--decision", "stop", "--reason", "delivery unresolved"])
    assert record_top10_publish_event.main() == 0
    assert len(events) == 1 and events[0]["status"] == "degraded"


def test_event_recovery_requires_consistent_event_history_and_rollups(tmp_path: Path) -> None:
    today = _today()
    run_id = f"daily-{today}"
    root = tmp_path / "harness_status" / today / run_id
    events = root / "events"
    events.mkdir(parents=True)
    event = {"agent_id": "daily_push", "run_date": today, "run_id": run_id,
             "status": "failed", "decision": "stop"}
    (events / "daily_push.json").write_text(json.dumps(event), encoding="utf-8")
    assert not event_record_complete(tmp_path, today, run_id, "daily_push")
    event["status"] = "ok"
    event["decision"] = "pass"
    (events / "daily_push.json").write_text(json.dumps(event), encoding="utf-8")
    (root / "events.jsonl").write_text(json.dumps(event) + "\n", encoding="utf-8")
    (root.parent / "latest_run_id.txt").write_text(run_id + "\n", encoding="utf-8")
    assert not event_record_complete(tmp_path, today, run_id, "daily_push")
    rollup = {"run_date": today, "run_id": run_id,
              "agents": [{"agent_id": "daily_push", "status": "ok"}]}
    (root / "rollup.json").write_text(json.dumps(rollup), encoding="utf-8")
    (root.parent / "latest_rollup.json").write_text(json.dumps(rollup), encoding="utf-8")
    assert event_record_complete(tmp_path, today, run_id, "daily_push")
    (root.parent / "latest_run_id.txt").write_text("daily-later\n", encoding="utf-8")
    (root.parent / "latest_rollup.json").write_text('{"run_id":"daily-later"}\n', encoding="utf-8")
    assert event_record_complete(tmp_path, today, run_id, "daily_push")


def test_daily_and_ops_rollup_writers_serialize(tmp_path: Path) -> None:
    observed = []
    def writer(name: str) -> None:
        with rollup_lock(tmp_path, "2026-10-15", "daily-2026-10-15"):
            observed.append((name, "start"))
            time.sleep(0.02)
            observed.append((name, "end"))
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(writer, ("daily_push", "ops_reporter")))
    assert observed in ([('daily_push', 'start'), ('daily_push', 'end'), ('ops_reporter', 'start'), ('ops_reporter', 'end')],
                        [('ops_reporter', 'start'), ('ops_reporter', 'end'), ('daily_push', 'start'), ('daily_push', 'end')])


def test_distinct_run_ids_share_date_rollup_lock(tmp_path: Path) -> None:
    observed = []
    def writer(run_id: str) -> None:
        with rollup_lock(tmp_path, "2026-10-15", run_id):
            observed.append((run_id, "start"))
            time.sleep(0.02)
            observed.append((run_id, "end"))
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(writer, ("daily-a", "daily-b")))
    assert observed in ([('daily-a', 'start'), ('daily-a', 'end'), ('daily-b', 'start'), ('daily-b', 'end')],
                        [('daily-b', 'start'), ('daily-b', 'end'), ('daily-a', 'start'), ('daily-a', 'end')])


def test_independent_sender_cannot_enter_while_daily_publish_lock_is_held(tmp_path: Path) -> None:
    command = [sys.executable, "-c", "from pathlib import Path; import sys; "
               "from scripts.daily_publish_lock import exclusive_publish_access; "
               "\nwith exclusive_publish_access(Path(sys.argv[1])): pass", str(tmp_path)]
    env = os.environ.copy()
    env.pop("TOP10_PUBLISH_LOCK_FD", None)
    with exclusive_publish_access(tmp_path):
        with exclusive_publish_access(tmp_path):
            pass
        blocked = subprocess.run(command, cwd=Path(__file__).resolve().parents[1], env=env,
                                 text=True, capture_output=True, check=False)
        assert blocked.returncode != 0
        assert "daily publish overlap blocked" in blocked.stderr
    allowed = subprocess.run(command, cwd=Path(__file__).resolve().parents[1], env=env,
                             text=True, capture_output=True, check=False)
    assert allowed.returncode == 0, allowed.stderr


def test_old_run_rebuild_cannot_replace_latest_rollup(tmp_path: Path, monkeypatch) -> None:
    date = "2026-10-15"
    owner = tmp_path / "harness_status" / date
    owner.mkdir(parents=True)
    (owner / "latest_run_id.txt").write_text("daily-new\n", encoding="utf-8")
    latest = owner / "latest_rollup.json"
    latest.write_text('{"run_id":"daily-new"}\n', encoding="utf-8")
    monkeypatch.setattr(rollup_cli, "read_manifest", lambda *_: {})
    monkeypatch.setattr(rollup_cli, "build_rollup", lambda *_, **__: {
        "status": "ok", "summary": {"failed_count": 0}, "run_date": date, "run_id": "daily-old",
    })
    monkeypatch.setattr(sys, "argv", ["build_top10_agent_status_rollup.py", "--run-date", date,
        "--run-id", "daily-old", "--artifacts-dir", str(tmp_path)])
    assert rollup_cli.main() == 0
    assert json.loads(latest.read_text())["run_id"] == "daily-new"


def test_ops_event_recovery_uses_confirmed_same_run_receipt(tmp_path: Path, monkeypatch) -> None:
    today = _today()
    run_id = f"daily-{today}"
    message = "進度內容"
    key = stable_idempotency_key(
        f"ops-report:{today}:{run_id}", channel="discord", target="channel:456",
        message=message, presentation=None,
    )
    current = {"run_date": today, "run_id": run_id, "message_path": "ops_progress_message.md",
               "channel": "discord", "target": "channel:456"}
    previous = {**current, "schema_version": ops.STATUS_SCHEMA_VERSION, "status": "OK",
        "dry_run": False, "send_attempted": True,
        "message_sha256": hashlib.sha256(message.encode()).hexdigest(),
        "idempotency_key": key, "receipt": {"message_id": "m-456", "idempotency_key": key}}
    path = tmp_path / "ops_progress_send_status.json"
    path.write_text(json.dumps(previous), encoding="utf-8")
    events = []
    monkeypatch.setattr(ops, "_write_ops_event_locked", lambda status, **_: events.append(status.copy()))
    assert ops.recover_confirmed_ops_event(path, current, message, None,
        artifacts_dir=tmp_path, manifest_path=tmp_path / "manifest.yaml")
    assert len(events) == 1
    assert not ops.recover_confirmed_ops_event(path, current, message + "改", None,
        artifacts_dir=tmp_path, manifest_path=tmp_path / "manifest.yaml")
    assert len(events) == 1
    previous["receipt"]["message_id"] = "unknown"
    path.write_text(json.dumps(previous), encoding="utf-8")
    assert not ops.recover_confirmed_ops_event(path, current, message, None,
        artifacts_dir=tmp_path, manifest_path=tmp_path / "manifest.yaml")
    assert len(events) == 1


def test_ops_live_alternate_artifacts_directory_is_blocked(tmp_path: Path, monkeypatch) -> None:
    today = _today()
    official = tmp_path / "official"
    other = tmp_path / "other"
    official.mkdir()
    other.mkdir()
    rollup = other / "rollup.json"
    rollup.write_text(json.dumps({"run_date": today, "run_id": f"daily-{today}"}), encoding="utf-8")
    config = tmp_path / "automation.yaml"
    config.write_text("notify:\n  ops_clawd_enabled: true\n  ops_clawd_dry_run: false\n", encoding="utf-8")
    monkeypatch.setattr(ops, "ARTIFACTS_DIR", official)
    monkeypatch.setattr(ops, "resolve_rollup_path", lambda *_: rollup)
    monkeypatch.setattr(ops, "build_strategy_archetype_evidence_map", lambda **_: None)
    monkeypatch.setattr(ops, "build_research_decision_brief", lambda **_: None)
    monkeypatch.setattr(ops, "run_checked", lambda *_: None)
    monkeypatch.setattr(sys, "argv", ["send_top10_ops_report.py", "--run-date", today,
        "--artifacts-dir", str(other), "--config", str(config), "--send"])
    assert ops.main() == 2
    assert not list(other.glob("ops_progress_send_status_*.json"))


def test_ops_pending_receipt_restores_degraded_event_without_resend(tmp_path: Path, monkeypatch) -> None:
    today = _today()
    run_id = f"daily-{today}"
    message = tmp_path / f"ops_progress_message_{today}.md"
    message.write_text("進度訊息", encoding="utf-8")
    config = tmp_path / "automation.yaml"
    config.write_text("notify:\n  ops_clawd_enabled: true\n  ops_clawd_dry_run: false\n", encoding="utf-8")
    prior = {"schema_version": ops.STATUS_SCHEMA_VERSION, "generated_at": "2026-10-15T00:00:00+00:00",
             "run_date": today, "run_id": run_id, "message_path": message.name,
             "output_path": f"ops_progress_send_status_{today}.json", "rollup_path": "rollup.json",
             "status": "DELIVERY_PENDING", "send_attempted": True, "dry_run": False, "errors": [],
             "exit_code": None}
    (tmp_path / f"ops_progress_send_status_{today}.json").write_text(json.dumps(prior), encoding="utf-8")
    latest = tmp_path / "harness_status" / today
    latest.mkdir(parents=True)
    (latest / "latest_run_id.txt").write_text("daily-later\n", encoding="utf-8")
    (latest / "latest_rollup.json").write_text('{"run_id":"daily-later"}\n', encoding="utf-8")
    monkeypatch.setattr(ops, "ARTIFACTS_DIR", tmp_path)
    monkeypatch.setattr(ops, "gateway_send", lambda **_: pytest.fail("protected receipt retried gateway"))
    monkeypatch.setattr(sys, "argv", ["send_top10_ops_report.py", "--run-date", today,
        "--artifacts-dir", str(tmp_path), "--message", str(message), "--config", str(config),
        "--manifest", str(ops.PROJECT_ROOT / "docs/architecture/top10_harness_team.dashboard.json"), "--send"])
    assert ops.main() == 2
    event_path = latest / run_id / "events" / "ops_reporter.json"
    assert json.loads(event_path.read_text())["status"] == "degraded"
    assert (latest / run_id / "rollup.json").exists()
    assert json.loads((latest / "latest_rollup.json").read_text())["run_id"] == "daily-later"


def test_ops_confirmed_receipt_recovers_event_after_send_disabled(tmp_path: Path, monkeypatch) -> None:
    today = _today()
    run_id = f"daily-{today}"
    rollup = tmp_path / "rollup.json"
    rollup.write_text(json.dumps({"run_date": today, "run_id": run_id}), encoding="utf-8")
    message = tmp_path / f"ops_progress_message_{today}.md"
    message.write_text("已送達進度", encoding="utf-8")
    config = tmp_path / "automation.yaml"
    config.write_text("notify:\n  ops_clawd_enabled: false\n  ops_clawd_dry_run: true\n"
                      "  ops_clawd_channel: discord\n  ops_clawd_to: channel:456\n", encoding="utf-8")
    prior = {"status": "OK", "run_date": today, "run_id": run_id, "message_path": message.name,
             "send_attempted": True, "dry_run": False}
    (tmp_path / f"ops_progress_send_status_{today}.json").write_text(json.dumps(prior), encoding="utf-8")
    calls: list[dict] = []
    monkeypatch.setattr(ops, "ARTIFACTS_DIR", tmp_path)
    monkeypatch.setattr(ops, "resolve_rollup_path", lambda *_: rollup)
    monkeypatch.setattr(ops, "recover_confirmed_ops_event", lambda *a, **k: calls.append(k) or True)
    monkeypatch.setattr(ops, "gateway_send", lambda **_: pytest.fail("disabled sender called gateway"))
    monkeypatch.setattr(sys, "argv", ["send_top10_ops_report.py", "--run-date", today,
        "--artifacts-dir", str(tmp_path), "--message", str(message), "--config", str(config)])
    assert ops.main() == 2
    assert len(calls) == 1


def test_old_ops_confirmed_receipt_recovers_without_latest_or_current_target(tmp_path: Path, monkeypatch) -> None:
    today = (datetime.now(ZoneInfo("Asia/Taipei")).date() - timedelta(days=1)).isoformat()
    run_id = "daily-old"
    message = tmp_path / f"ops_progress_message_{today}.md"
    body = "原輪進度"
    message.write_text(body, encoding="utf-8")
    key = stable_idempotency_key(f"ops-report:{today}:{run_id}", channel="discord",
                                 target="channel:456", message=body, presentation=None)
    prior = {"schema_version": ops.STATUS_SCHEMA_VERSION, "generated_at": "2026-10-15T00:00:00+00:00",
             "run_date": today, "run_id": run_id, "message_path": message.name,
             "presentation_path": None, "output_path": f"ops_progress_send_status_{today}.json",
             "rollup_path": "rollup.json", "channel": "discord", "target": "channel:456",
             "status": "OK", "send_attempted": True, "dry_run": False,
             "message_sha256": hashlib.sha256(body.encode()).hexdigest(),
             "idempotency_key": key, "receipt": {"message_id": "m-456", "idempotency_key": key},
             "errors": [], "exit_code": 0}
    (tmp_path / f"ops_progress_send_status_{today}.json").write_text(json.dumps(prior), encoding="utf-8")
    latest = tmp_path / "harness_status" / today
    latest.mkdir(parents=True)
    (latest / "latest_run_id.txt").write_text("daily-new\n", encoding="utf-8")
    (latest / "latest_rollup.json").write_text(json.dumps({"run_date": today, "run_id": "daily-new"}), encoding="utf-8")
    current_date = _today()
    current = tmp_path / "harness_status" / current_date
    current.mkdir(parents=True)
    (current / "latest_rollup.json").write_text(json.dumps({"run_date": current_date,
                                                            "run_id": "daily-current"}), encoding="utf-8")
    config = tmp_path / "automation.yaml"
    config.write_text("notify:\n  ops_clawd_enabled: false\n  ops_clawd_dry_run: true\n", encoding="utf-8")
    monkeypatch.setattr(ops, "ARTIFACTS_DIR", tmp_path)
    monkeypatch.setattr(ops, "_run_locked", lambda *_, **__: 2)
    monkeypatch.setattr(ops, "gateway_send", lambda **_: pytest.fail("historical recovery sent to gateway"))
    monkeypatch.setattr(sys, "argv", ["send_top10_ops_report.py",
        "--artifacts-dir", str(tmp_path), "--config", str(config),
        "--manifest", str(ops.PROJECT_ROOT / "docs/architecture/top10_harness_team.dashboard.json")])
    assert ops.main() == 2
    event = json.loads((latest / run_id / "events" / "ops_reporter.json").read_text())
    assert event["status"] == "ok"
    assert event_record_complete(tmp_path, today, run_id, "ops_reporter")
    assert (latest / "latest_run_id.txt").read_text().strip() == "daily-new"


def test_ops_run_id_without_date_is_rejected_before_latest_selection(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["send_top10_ops_report.py", "--run-id", "daily-old", "--send"])
    assert ops.main() == 2


@pytest.mark.parametrize("explicit_date", [False, True])
def test_no_date_ops_recovers_historical_pending_event_once(tmp_path: Path, monkeypatch, explicit_date: bool) -> None:
    old_date = (datetime.now(ZoneInfo("Asia/Taipei")).date() - timedelta(days=1)).isoformat()
    current_date = _today()
    run_id = f"daily-{old_date}"
    prior = {"schema_version": ops.STATUS_SCHEMA_VERSION, "generated_at": "2026-10-14T00:00:00+00:00",
             "run_date": old_date, "run_id": run_id,
             "message_path": f"ops_progress_message_{old_date}.md",
             "output_path": f"ops_progress_send_status_{old_date}.json", "rollup_path": "rollup.json",
             "status": "DELIVERY_UNKNOWN", "send_attempted": True, "dry_run": False,
             "errors": [], "exit_code": 1}
    (tmp_path / f"ops_progress_send_status_{old_date}.json").write_text(json.dumps(prior), encoding="utf-8")
    latest = tmp_path / "harness_status" / current_date
    latest.mkdir(parents=True)
    (latest / "latest_rollup.json").write_text(json.dumps({"run_date": current_date,
                                                            "run_id": f"daily-{current_date}"}), encoding="utf-8")
    config = tmp_path / "automation.yaml"
    config.write_text("notify: {}\n", encoding="utf-8")
    monkeypatch.setattr(ops, "ARTIFACTS_DIR", tmp_path)
    monkeypatch.setattr(ops, "_run_locked", lambda *_, **__: 2)
    monkeypatch.setattr(sys, "argv", ["send_top10_ops_report.py", *(["--run-date", current_date] if explicit_date else []), "--artifacts-dir", str(tmp_path),
        "--config", str(config),
        "--manifest", str(ops.PROJECT_ROOT / "docs/architecture/top10_harness_team.dashboard.json")])
    assert ops.main() == 2
    old_root = tmp_path / "harness_status" / old_date / run_id
    event = json.loads((old_root / "events" / "ops_reporter.json").read_text())
    assert event["status"] == "degraded"
    before = len((old_root / "events.jsonl").read_text().splitlines())
    assert ops.main() == 2
    assert len((old_root / "events.jsonl").read_text().splitlines()) == before


def test_ops_rollup_identity_and_symlink_must_match_live_owner(tmp_path: Path, monkeypatch) -> None:
    today = _today()
    run_id = f"daily-{today}"
    root = tmp_path / "harness_status" / today
    root.mkdir(parents=True)
    latest = root / "latest_rollup.json"
    (root / "latest_run_id.txt").write_text(run_id + "\n", encoding="utf-8")
    latest.write_text(json.dumps({"run_date": today, "run_id": run_id}), encoding="utf-8")
    assert ops.selected_rollup_is_canonical(latest, tmp_path, today, run_id, explicit_run=False)
    (root / "latest_run_id.txt").write_text("different\n", encoding="utf-8")
    assert not ops.selected_rollup_is_canonical(latest, tmp_path, today, run_id, explicit_run=False)
    exact = root / run_id / "rollup.json"
    exact.parent.mkdir()
    exact.write_text(latest.read_text(encoding="utf-8"))
    assert not ops.selected_rollup_is_canonical(exact, tmp_path, today, run_id, explicit_run=True)
    (root / "latest_run_id.txt").write_text(run_id + "\n", encoding="utf-8")
    assert ops.selected_rollup_is_canonical(exact, tmp_path, today, run_id, explicit_run=True)
    owner = root / "latest_run_id.txt"
    owner.unlink()
    outside_owner = tmp_path.parent / "outside-owner.txt"
    outside_owner.write_text(run_id + "\n", encoding="utf-8")
    owner.symlink_to(outside_owner)
    assert not ops.selected_rollup_is_canonical(latest, tmp_path, today, run_id, explicit_run=False)
    owner.unlink()
    owner.write_text(run_id + "\n", encoding="utf-8")
    outside = tmp_path.parent / "outside-rollup.json"
    outside.write_text(latest.read_text(encoding="utf-8"), encoding="utf-8")
    latest.unlink()
    latest.symlink_to(outside)
    assert not ops.selected_rollup_is_canonical(latest, tmp_path, today, run_id, explicit_run=False)
    config = tmp_path / "automation.yaml"
    config.write_text("notify:\n  ops_clawd_enabled: true\n  ops_clawd_dry_run: false\n", encoding="utf-8")
    monkeypatch.setattr(ops, "ARTIFACTS_DIR", tmp_path)
    monkeypatch.setattr(ops, "gateway_send", lambda **_: pytest.fail("mismatched rollup sent"))
    monkeypatch.setattr(sys, "argv", ["send_top10_ops_report.py", "--run-date", today,
        "--artifacts-dir", str(tmp_path), "--config", str(config), "--send"])
    assert ops.main() == 2
    latest.unlink()
    latest.write_text(json.dumps({"run_date": "2026-10-14", "run_id": run_id}), encoding="utf-8")
    assert ops.main() == 2


def test_historical_ops_scan_above_500_never_blocks_live_date(tmp_path: Path, monkeypatch) -> None:
    today = _today()
    for index in range(501):
        (tmp_path / f"ops_progress_send_status_2024-01-{index:04d}.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(ops, "recover_protected_ops_event", lambda *_, **__: False)
    ops.recover_historical_ops_receipts(today, artifacts_dir=tmp_path, manifest_path=tmp_path / "manifest.json")


def test_concurrent_pending_ops_recovery_writes_one_event(tmp_path: Path, monkeypatch) -> None:
    today = _today()
    run_id = f"daily-{today}"
    path = tmp_path / f"ops_progress_send_status_{today}.json"
    prior = {"schema_version": ops.STATUS_SCHEMA_VERSION, "generated_at": "2026-10-15T00:00:00+00:00",
             "run_date": today, "run_id": run_id, "message_path": "ops.md",
             "output_path": path.name, "rollup_path": "rollup.json",
             "status": "DELIVERY_UNKNOWN", "send_attempted": True, "dry_run": False,
             "errors": [], "exit_code": 1}
    path.write_text(json.dumps(prior), encoding="utf-8")
    original = ops._write_ops_event_locked

    def delayed_write(*args, **kwargs):
        time.sleep(0.05)
        return original(*args, **kwargs)

    monkeypatch.setattr(ops, "_write_ops_event_locked", delayed_write)
    manifest = ops.PROJECT_ROOT / "docs/architecture/top10_harness_team.dashboard.json"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: ops.recover_protected_ops_event(
            path, today, artifacts_dir=tmp_path, manifest_path=manifest), range(2)))
    assert results == [True, True]
    history = (tmp_path / "harness_status" / today / run_id / "events.jsonl").read_text().splitlines()
    assert len([row for row in history if json.loads(row).get("agent_id") == "ops_reporter"]) == 1


def test_inherited_unlocked_fd_cannot_borrow_other_process_lock(tmp_path: Path, monkeypatch) -> None:
    lock_path = tmp_path / "logs" / "daily_publish.lock"
    lock_path.parent.mkdir()
    lock_path.touch()
    holder = subprocess.Popen([sys.executable, "-c",
        "import fcntl,os,sys; f=os.open(sys.argv[1],os.O_RDWR); fcntl.flock(f,fcntl.LOCK_EX); "
        "print('READY',flush=True); sys.stdin.read()", str(lock_path)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout is not None and holder.stdout.readline().strip() == "READY"
        descriptor = os.open(lock_path, os.O_RDWR)
        try:
            monkeypatch.setenv("TOP10_PUBLISH_LOCK_FD", str(descriptor))
            assert not inherited_lock_valid(lock_path)
            with pytest.raises(RuntimeError, match="inherited lock verification failed"):
                with exclusive_publish_access(tmp_path):
                    pass
        finally:
            os.close(descriptor)
    finally:
        assert holder.stdin is not None
        holder.stdin.close()
        holder.wait(timeout=5)


def test_lock_path_replacement_during_acquisition_is_rejected(tmp_path: Path, monkeypatch) -> None:
    lock_path = tmp_path / "logs" / "daily_publish.lock"
    original = publish_lock.fcntl.flock
    replaced = False

    def replace_before_lock(descriptor: int, operation: int) -> None:
        nonlocal replaced
        if not replaced and stat.S_ISREG(os.fstat(descriptor).st_mode):
            replaced = True
            lock_path.rename(lock_path.with_suffix(".old"))
            lock_path.touch()
        original(descriptor, operation)

    monkeypatch.delenv("TOP10_PUBLISH_LOCK_FD", raising=False)
    monkeypatch.setattr(publish_lock.fcntl, "flock", replace_before_lock)
    with pytest.raises(RuntimeError, match="inode changed after acquisition"):
        with exclusive_publish_access(tmp_path):
            pass


def test_replacing_lock_filename_cannot_start_second_sender(tmp_path: Path) -> None:
    with exclusive_publish_access(tmp_path):
        lock_path = tmp_path / "logs" / "daily_publish.lock"
        lock_path.rename(lock_path.with_suffix(".old"))
        lock_path.touch()
        env = os.environ.copy()
        env.pop("TOP10_PUBLISH_LOCK_FD", None)
        env.pop("TOP10_PUBLISH_DIR_LOCK_FD", None)
        child = subprocess.run([sys.executable, "-c",
            "from pathlib import Path\nfrom scripts.daily_publish_lock import exclusive_publish_access\n"
            "import sys\nwith exclusive_publish_access(Path(sys.argv[1])):\n    pass\n", str(tmp_path)],
            env=env, cwd=Path(__file__).resolve().parents[1], text=True, capture_output=True)
        assert child.returncode != 0
        assert "directory lock" in child.stderr


def test_symlinked_logs_directory_is_rejected(tmp_path: Path) -> None:
    real = tmp_path / "real-logs"
    real.mkdir()
    (tmp_path / "logs").symlink_to(real, target_is_directory=True)
    with pytest.raises(RuntimeError, match="symlink rejected"):
        with exclusive_publish_access(tmp_path):
            pass


def test_ops_owner_change_during_message_build_blocks_before_claim(tmp_path: Path, monkeypatch) -> None:
    today = _today()
    run_id = f"daily-{today}"
    root = tmp_path / "harness_status" / today
    root.mkdir(parents=True)
    latest = root / "latest_run_id.txt"
    latest.write_text(run_id + "\n")
    (root / "latest_rollup.json").write_text(json.dumps({"run_date": today, "run_id": run_id}))
    message = tmp_path / f"ops_progress_message_{today}.md"
    message.write_text("進度測試")
    config = tmp_path / "automation.yaml"
    config.write_text("notify:\n  ops_clawd_enabled: true\n  ops_clawd_dry_run: false\n"
                      "  ops_clawd_channel: discord\n  ops_clawd_to: channel:123\n")
    monkeypatch.setattr(ops, "ARTIFACTS_DIR", tmp_path)
    monkeypatch.setattr(ops, "build_strategy_archetype_evidence_map", lambda **_: None)
    monkeypatch.setattr(ops, "build_research_decision_brief", lambda **_: latest.write_text("daily-other\n"))
    monkeypatch.setattr(ops, "gateway_send", lambda **_: pytest.fail("owner changed before send"))
    monkeypatch.setattr(sys, "argv", ["send_top10_ops_report.py", "--run-date", today,
        "--artifacts-dir", str(tmp_path), "--message", str(message),
        "--config", str(config), "--send"])
    assert ops.main() == 2
    assert not (tmp_path / f"ops_progress_send_status_{today}.json").exists()


def test_ops_owner_change_at_claim_blocks_gateway(tmp_path: Path, monkeypatch) -> None:
    today = _today()
    run_id = f"daily-{today}"
    root = tmp_path / "harness_status" / today
    root.mkdir(parents=True)
    latest = root / "latest_run_id.txt"
    latest.write_text(run_id + "\n")
    (root / "latest_rollup.json").write_text(json.dumps({"run_date": today, "run_id": run_id}))
    message = tmp_path / f"ops_progress_message_{today}.md"
    message.write_text("進度測試")
    node = tmp_path / "node"
    cli = tmp_path / "index.js"
    node.touch()
    cli.touch()
    config = tmp_path / "automation.yaml"
    config.write_text("notify:\n  ops_clawd_enabled: true\n  ops_clawd_dry_run: false\n"
                      "  ops_clawd_channel: discord\n  ops_clawd_to: channel:123\n"
                      f"  clawd_cli_node: {node}\n  clawd_cli_entry: {cli}\n")
    original_check = ops.selected_rollup_is_canonical
    checks = 0

    def change_owner_at_final_check(*args, **kwargs):
        nonlocal checks
        checks += 1
        if checks == 4:
            latest.write_text("daily-newer\n")
        return original_check(*args, **kwargs)

    monkeypatch.setattr(ops, "ARTIFACTS_DIR", tmp_path)
    monkeypatch.setattr(ops, "build_strategy_archetype_evidence_map", lambda **_: None)
    monkeypatch.setattr(ops, "build_research_decision_brief", lambda **_: None)
    monkeypatch.setattr(ops, "selected_rollup_is_canonical", change_owner_at_final_check)
    monkeypatch.setattr(ops, "gateway_send", lambda **_: pytest.fail("stale owner sent"))
    monkeypatch.setattr(sys, "argv", ["send_top10_ops_report.py", "--run-date", today,
        "--artifacts-dir", str(tmp_path), "--message", str(message),
        "--config", str(config), "--send"])
    assert ops.main() == 2
    assert not (tmp_path / f"ops_progress_send_status_{today}.json").exists()


def test_ops_owner_writer_waits_until_gateway_dispatch_returns(tmp_path: Path, monkeypatch) -> None:
    today = _today()
    run_id = f"daily-{today}"
    root = tmp_path / "harness_status" / today
    root.mkdir(parents=True)
    latest = root / "latest_run_id.txt"
    latest.write_text(run_id + "\n")
    (root / "latest_rollup.json").write_text(json.dumps({"run_date": today, "run_id": run_id}))
    message = tmp_path / f"ops_progress_message_{today}.md"
    message.write_text("進度測試")
    node = tmp_path / "node"
    cli = tmp_path / "index.js"
    node.touch()
    cli.touch()
    config = tmp_path / "automation.yaml"
    config.write_text("notify:\n  ops_clawd_enabled: true\n  ops_clawd_dry_run: false\n"
                      "  ops_clawd_channel: discord\n  ops_clawd_to: channel:123\n"
                      f"  clawd_cli_node: {node}\n  clawd_cli_entry: {cli}\n")
    pending = []
    writer_started = Event()
    with ThreadPoolExecutor(max_workers=1) as pool:
        def during_gateway(**kwargs):
            def change_owner():
                writer_started.set()
                with rollup_lock(tmp_path, today, "daily-newer"):
                    latest.write_text("daily-newer\n")
            pending.append(pool.submit(change_owner))
            assert writer_started.wait(timeout=5)
            time.sleep(0.05)
            assert not pending[0].done()
            raise ops.DeliveryOutcomeUnknownError(idempotency_key="top10:ops-report:test", timeout_ms=60_000)

        monkeypatch.setattr(ops, "ARTIFACTS_DIR", tmp_path)
        monkeypatch.setattr(ops, "build_strategy_archetype_evidence_map", lambda **_: None)
        monkeypatch.setattr(ops, "build_research_decision_brief", lambda **_: None)
        monkeypatch.setattr(ops, "gateway_send", during_gateway)
        monkeypatch.setattr(ops, "write_ops_event", lambda *_, **__: None)
        monkeypatch.setattr(sys, "argv", ["send_top10_ops_report.py", "--run-date", today,
            "--artifacts-dir", str(tmp_path), "--message", str(message),
            "--config", str(config), "--send"])
        assert ops.main() == 1
        pending[0].result(timeout=5)
    assert latest.read_text().strip() == "daily-newer"


def test_non_discord_presentation_rejected_before_send_claim(tmp_path: Path, monkeypatch) -> None:
    node = tmp_path / "node"
    cli = tmp_path / "index.js"
    message = tmp_path / "message.md"
    presentation = tmp_path / "presentation.json"
    for path in (node, cli, message, presentation):
        path.touch()
    monkeypatch.setattr(ops, "read_presentation_payload", lambda *_: {})
    with pytest.raises(RuntimeError, match="requires Discord channel before send claim"):
        ops.validate_preflight(
            node_bin=str(node), cli_entry=str(cli), channel="slack", target="channel:456",
            message_path=message, presentation_path=presentation,
            run_date=_today(), send_allowed=True, allow_stale_send=False,
            timezone_name="Asia/Taipei", artifacts_dir=tmp_path,
        )


@pytest.mark.parametrize("external", ["message", "presentation"])
def test_live_ops_rejects_unrecoverable_external_artifact_before_claim(
    tmp_path: Path, monkeypatch, external: str,
) -> None:
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    node = tmp_path / "node"
    cli = tmp_path / "index.js"
    message = (tmp_path if external == "message" else artifacts) / "message.md"
    presentation = (tmp_path if external == "presentation" else artifacts) / "presentation.json"
    for path in (node, cli, message, presentation):
        path.touch()
    monkeypatch.setattr(ops, "read_presentation_payload", lambda *_: {})
    with pytest.raises(RuntimeError, match=f"live {external} must remain inside artifacts"):
        ops.validate_preflight(
            node_bin=str(node), cli_entry=str(cli), channel="discord", target="channel:456",
            message_path=message, presentation_path=presentation,
            run_date=_today(), send_allowed=True, allow_stale_send=False,
            timezone_name="Asia/Taipei", artifacts_dir=artifacts,
        )


@pytest.mark.parametrize("external", ["message", "payload"])
def test_live_top10_rejects_unrecoverable_external_artifact_before_claim(
    tmp_path: Path, external: str,
) -> None:
    today = _today()
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    node = tmp_path / "node"
    cli = tmp_path / "index.js"
    message = (tmp_path if external == "message" else artifacts) / f"clawd_publish_message_{today}.md"
    payload_path = (tmp_path if external == "payload" else artifacts) / f"clawd_publish_payload_{today}.json"
    for path in (node, cli, message, payload_path):
        path.touch()
    payload = {"ranking_date": today,
               "delivery": {"status": "READY_FOR_CLAWD", "channel": "discord", "to": "channel:123"},
               "artifacts": {"message": str(message)}}
    with pytest.raises(RuntimeError, match=f"live {external} must use canonical artifacts path"):
        top10.validate_preflight(
            node_bin=str(node), cli_entry=str(cli), channel="discord", target="channel:123",
            message_path=message, message_date=today, payload_path=payload_path, payload=payload,
            send_allowed=True, allow_stale_send=False, timezone_name="Asia/Taipei",
            artifacts_dir=artifacts,
        )


def test_live_top10_rejects_symlink_alias_before_claim(tmp_path: Path) -> None:
    today = _today()
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    canonical = artifacts / f"clawd_publish_message_{today}.md"
    canonical.write_text("今日 Top10", encoding="utf-8")
    alias = tmp_path / canonical.name
    alias.symlink_to(canonical)
    payload = artifacts / f"clawd_publish_payload_{today}.json"
    payload.touch()
    node = tmp_path / "node"
    cli = tmp_path / "index.js"
    node.touch()
    cli.touch()
    with pytest.raises(RuntimeError, match="canonical artifacts path"):
        top10.validate_preflight(
            node_bin=str(node), cli_entry=str(cli), channel="discord", target="channel:123",
            message_path=alias, message_date=today, payload_path=payload,
            payload={"ranking_date": today, "delivery": {"status": "READY_FOR_CLAWD"},
                     "artifacts": {"message": str(alias)}},
            send_allowed=True, allow_stale_send=False, timezone_name="Asia/Taipei",
            artifacts_dir=artifacts,
        )
    canonical.unlink()
    external = tmp_path / "external-message.md"
    external.write_text("外部訊息", encoding="utf-8")
    canonical.symlink_to(external)
    # 即使傳入標準路徑，檔案本身若為連結也不得產生不可恢復的送達收據。
    with pytest.raises(RuntimeError, match="canonical artifacts path"):
        top10.validate_preflight(
            node_bin=str(node), cli_entry=str(cli), channel="discord", target="channel:123",
            message_path=canonical, message_date=today, payload_path=payload,
            payload={"ranking_date": today, "delivery": {"status": "READY_FOR_CLAWD"},
                     "artifacts": {"message": str(canonical)}},
            send_allowed=True, allow_stale_send=False, timezone_name="Asia/Taipei",
            artifacts_dir=artifacts,
        )


def test_ops_dry_run_cannot_claim_delivery_success(tmp_path: Path, monkeypatch) -> None:
    today = _today()
    rollup = tmp_path / "rollup.json"
    message = tmp_path / f"ops_progress_message_{today}.md"
    rollup.write_text(json.dumps({"run_date": today, "run_id": f"daily-{today}"}), encoding="utf-8")
    message.write_text("測試進度", encoding="utf-8")
    node = tmp_path / "node"
    cli = tmp_path / "index.js"
    node.touch()
    cli.touch()
    config = tmp_path / "automation.yaml"
    config.write_text("notify:\n  ops_clawd_enabled: true\n  ops_clawd_dry_run: true\n"
        f"  ops_clawd_channel: discord\n  ops_clawd_to: channel:123\n"
        f"  clawd_cli_node: {node}\n  clawd_cli_entry: {cli}\n", encoding="utf-8")
    events = []
    monkeypatch.setattr(ops, "ARTIFACTS_DIR", tmp_path)
    monkeypatch.setattr(ops, "resolve_rollup_path", lambda *_: rollup)
    monkeypatch.setattr(ops, "build_strategy_archetype_evidence_map", lambda **_: None)
    monkeypatch.setattr(ops, "build_research_decision_brief", lambda **_: None)
    monkeypatch.setattr(ops, "gateway_health", lambda **_: {"ok": True})
    monkeypatch.setattr(ops, "write_ops_event", lambda status, **_: events.append(status.copy()))
    monkeypatch.setattr(ops, "gateway_send", lambda **_: pytest.fail("dry-run called gateway_send"))
    monkeypatch.setattr(sys, "argv", ["send_top10_ops_report.py", "--run-date", today,
        "--artifacts-dir", str(tmp_path), "--message", str(message), "--config", str(config), "--send"])
    assert ops.main() == 1
    status = json.loads((tmp_path / f"ops_progress_send_status_{today}.json").read_text())
    assert status["status"] == "DRY_RUN" and status["send_attempted"] is False
    assert events[0]["status"] == "DRY_RUN"


def test_top10_send_flag_with_dry_run_config_fails_closed(tmp_path: Path, monkeypatch) -> None:
    today = _today()
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    message = artifacts / f"clawd_publish_message_{today}.md"
    payload = artifacts / f"clawd_publish_payload_{today}.json"
    node = tmp_path / "node"
    cli = tmp_path / "index.js"
    node.touch()
    cli.touch()
    message.write_text("Top10 測試內容", encoding="utf-8")
    payload.write_text(json.dumps({"ranking_date": today,
        "delivery": {"status": "READY_FOR_CLAWD", "channel": "discord", "to": "channel:123"},
        "artifacts": {"message": str(message)}}), encoding="utf-8")
    config = tmp_path / "automation.yaml"
    config.write_text("notify:\n  clawd_enabled: true\n  clawd_dry_run: true\n"
        f"  clawd_channel: discord\n  clawd_to: channel:123\n"
        f"  clawd_cli_node: {node}\n  clawd_cli_entry: {cli}\n", encoding="utf-8")
    monkeypatch.setattr(top10, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(top10, "gateway_health", lambda **_: {"ok": True})
    monkeypatch.setattr(top10, "gateway_send", lambda **_: pytest.fail("dry-run sent"))
    monkeypatch.setattr(sys, "argv", ["send_clawd_publish_message.py", "--message", str(message),
        "--payload", str(payload), "--config", str(config), "--send"])
    assert top10.main() == 1
    status = json.loads((artifacts / f"clawd_send_status_{today}.json").read_text())
    assert status["status"] == "DRY_RUN" and status["send_attempted"] is False
