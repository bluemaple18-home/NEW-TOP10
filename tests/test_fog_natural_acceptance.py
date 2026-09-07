from __future__ import annotations

import hashlib
import json
import os
import plistlib
import stat
import tempfile
from pathlib import Path

import pytest

from app.fog_natural_acceptance import (
    evaluate_natural_acceptance,
    evaluate_terminal_evidence,
    terminal_evidence_path,
    write_terminal_evidence,
)


RUN_DATE = "2026-09-07"
RUN_ID = "fog-research-2026-09-07-20260907010000000000-b1"
SCHEDULED_AT = "2026-09-07T01:00:00+00:00"
INVOCATION_ID = "fog-research-worker-20260907T010000Z-test"


def write_event(root: Path, *, run_date: str = RUN_DATE, run_id: str = RUN_ID) -> Path:
    path = (
        root
        / "artifacts"
        / "harness_status"
        / run_date
        / run_id
        / "events"
        / "fog_map.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "top10-agent-status-event.v1",
                "run_id": run_id,
                "run_date": run_date,
                "agent_id": "fog_map",
                "status": "ok",
                "decision": "pass",
            }
        ),
        encoding="utf-8",
    )
    return path


def valid_evidence(root: Path) -> dict[str, object]:
    event = write_event(root)
    return {
        "schema_version": "top10-fog-terminal-evidence.v1",
        "job": "fog-research-worker",
        "scheduled_at": SCHEDULED_AT,
        "invocation_id": INVOCATION_ID,
        "run_id": RUN_ID,
        "artifact_run_date": RUN_DATE,
        "terminal_result": "OK",
        "canonical_artifact_path": event.relative_to(root).as_posix(),
        "canonical_artifact_sha256": hashlib.sha256(event.read_bytes()).hexdigest(),
        "event_status": "ok",
        "event_decision": "pass",
    }


def write_evidence(root: Path, payload: dict[str, object]) -> Path:
    path = terminal_evidence_path(root, INVOCATION_ID)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def write_anchor(root: Path) -> None:
    plist_path = root / "scripts" / "com.new-top10.fog-research-worker.plist"
    plist_path.parent.mkdir(parents=True)
    plist_path.write_bytes(plistlib.dumps({"StartInterval": 3600}))
    invocation_id = "fog-research-worker-20260907T000000Z-test"
    receipt_path = (
        root
        / "logs"
        / "storage_safety"
        / "receipts"
        / "fog-research-worker"
        / f"{invocation_id}.json"
    )
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(
        json.dumps(
            {
                "schema_version": "top10-storage-guard-receipt.v1",
                "job": "fog-research-worker",
                "status": "OK",
                "trigger_type": "natural",
                "scheduled_at": "2026-09-07T00:00:00+00:00",
                "invocation_id": invocation_id,
                "child_exit_code": 0,
                "final_process_group_quiescent": True,
                "terminal_evidence_verified": True,
                "terminal_evidence_status": "VALID",
                "artifact_run_date": RUN_DATE,
                "publish_or_provider_result": "OK",
                "accepted_natural_cycles": 0,
            }
        ),
        encoding="utf-8",
    )


def test_writer_atomically_publishes_immutable_exact_evidence() -> None:
    with tempfile.TemporaryDirectory(prefix="top10-fog-evidence-writer-") as tmp:
        root = Path(tmp)
        write_event(root)

        path = write_terminal_evidence(
            root,
            job="fog-research-worker",
            scheduled_at=SCHEDULED_AT,
            invocation_id=INVOCATION_ID,
            run_id=RUN_ID,
            artifact_run_date=RUN_DATE,
        )
        original = path.read_bytes()
        payload = json.loads(original)

        assert path.name == f"{INVOCATION_ID}.json"
        assert not path.is_symlink()
        assert payload["canonical_artifact_path"].endswith("/events/fog_map.json")
        assert payload["canonical_artifact_sha256"] == hashlib.sha256(
            (root / payload["canonical_artifact_path"]).read_bytes()
        ).hexdigest()
        with pytest.raises(FileExistsError):
            write_terminal_evidence(
                root,
                job="fog-research-worker",
                scheduled_at=SCHEDULED_AT,
                invocation_id=INVOCATION_ID,
                run_id=RUN_ID,
                artifact_run_date=RUN_DATE,
            )
        assert path.read_bytes() == original


@pytest.mark.parametrize("run_date", ["2026-09-06", "2026-02-30"])
def test_writer_rejects_run_date_outside_time_authority(run_date: str) -> None:
    """Writer 必須由 scheduled_at 推導市場日，不能信任 caller 的日期。"""

    with tempfile.TemporaryDirectory(prefix="top10-fog-date-authority-writer-") as tmp:
        root = Path(tmp)
        run_id = f"fog-research-{run_date}-probe-b1"
        write_event(root, run_date=run_date, run_id=run_id)

        with pytest.raises(ValueError):
            write_terminal_evidence(
                root,
                job="fog-research-worker",
                scheduled_at=SCHEDULED_AT,
                invocation_id=INVOCATION_ID,
                run_id=run_id,
                artifact_run_date=run_date,
            )


@pytest.mark.parametrize("run_date", ["2026-09-06", "2026-02-30"])
def test_reader_rejects_self_consistent_date_outside_time_authority(
    run_date: str,
) -> None:
    """Evidence 與 event 即使自洽，錯市場日或不存在日期仍須 fail closed。"""

    with tempfile.TemporaryDirectory(prefix="top10-fog-date-authority-reader-") as tmp:
        root = Path(tmp)
        run_id = f"fog-research-{run_date}-probe-b1"
        event = write_event(root, run_date=run_date, run_id=run_id)
        payload = {
            "schema_version": "top10-fog-terminal-evidence.v1",
            "job": "fog-research-worker",
            "scheduled_at": SCHEDULED_AT,
            "invocation_id": INVOCATION_ID,
            "run_id": run_id,
            "artifact_run_date": run_date,
            "terminal_result": "OK",
            "canonical_artifact_path": event.relative_to(root).as_posix(),
            "canonical_artifact_sha256": hashlib.sha256(event.read_bytes()).hexdigest(),
            "event_status": "ok",
            "event_decision": "pass",
        }
        write_evidence(root, payload)

        result = evaluate_terminal_evidence(
            root,
            scheduled_at=SCHEDULED_AT,
            invocation_id=INVOCATION_ID,
        )

        assert result["terminal_evidence_verified"] is False
        assert result["terminal_evidence_status"] == "INVALID"


def test_writer_uses_time_authority_market_timezone_at_utc_date_boundary() -> None:
    with tempfile.TemporaryDirectory(prefix="top10-fog-market-date-boundary-") as tmp:
        root = Path(tmp)
        scheduled_at = "2026-09-06T16:30:00Z"
        invocation_id = "fog-research-worker-20260906T163000Z-test"
        run_id = "fog-research-2026-09-07-boundary-b1"
        write_event(root, run_id=run_id)

        write_terminal_evidence(
            root,
            job="fog-research-worker",
            scheduled_at=scheduled_at,
            invocation_id=invocation_id,
            run_id=run_id,
            artifact_run_date=RUN_DATE,
        )
        result = evaluate_terminal_evidence(
            root,
            scheduled_at=scheduled_at,
            invocation_id=invocation_id,
        )

        assert result["terminal_evidence_verified"] is True
        assert result["artifact_run_date"] == RUN_DATE


def test_terminal_evidence_hostile_bindings_fail_closed() -> None:
    mutations = {
        "wrong_invocation": lambda payload: payload.update(invocation_id="wrong"),
        "wrong_date": lambda payload: payload.update(artifact_run_date="2026-09-06"),
        "wrong_hash": lambda payload: payload.update(canonical_artifact_sha256="0" * 64),
        "wrong_path": lambda payload: payload.update(canonical_artifact_path="latest.json"),
        "path_traversal": lambda payload: payload.update(
            canonical_artifact_path="../../fog_map.json"
        ),
        "wrong_event_status": lambda payload: payload.update(event_status="failed"),
    }
    for name, mutate in mutations.items():
        with tempfile.TemporaryDirectory(prefix=f"top10-fog-{name}-") as tmp:
            root = Path(tmp)
            payload = valid_evidence(root)
            mutate(payload)
            write_evidence(root, payload)

            result = evaluate_terminal_evidence(
                root,
                scheduled_at=SCHEDULED_AT,
                invocation_id=INVOCATION_ID,
            )

            assert result["terminal_evidence_verified"] is False, name
            assert result["terminal_evidence_status"] == "INVALID", name


def test_latest_and_symlink_terminal_evidence_fail_closed() -> None:
    with tempfile.TemporaryDirectory(prefix="top10-fog-latest-") as tmp:
        root = Path(tmp)
        payload = valid_evidence(root)
        latest = terminal_evidence_path(root, INVOCATION_ID).with_name("latest.json")
        latest.parent.mkdir(parents=True, exist_ok=True)
        latest.write_text(json.dumps(payload), encoding="utf-8")
        result = evaluate_terminal_evidence(
            root,
            scheduled_at=SCHEDULED_AT,
            invocation_id=INVOCATION_ID,
        )
        assert result["terminal_evidence_status"] == "MISSING"

    with tempfile.TemporaryDirectory(prefix="top10-fog-symlink-") as tmp:
        root = Path(tmp)
        payload = valid_evidence(root)
        target = root / "evidence-target.json"
        target.write_text(json.dumps(payload), encoding="utf-8")
        path = terminal_evidence_path(root, INVOCATION_ID)
        path.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(target, path)
        result = evaluate_terminal_evidence(
            root,
            scheduled_at=SCHEDULED_AT,
            invocation_id=INVOCATION_ID,
        )
        assert result["terminal_evidence_verified"] is False
        assert result["terminal_evidence_status"] == "INVALID"


def test_reader_rejects_evidence_leaf_swap_after_safety_check(monkeypatch) -> None:
    """Leaf 在檢查後換成 symlink 時，不得改讀攻擊者提供的有效內容。"""

    with tempfile.TemporaryDirectory(prefix="top10-fog-evidence-leaf-swap-") as tmp:
        root = Path(tmp)
        valid_payload = valid_evidence(root)
        path = write_evidence(root, {**valid_payload, "terminal_result": "FAILED"})
        attacker = root / "attacker-evidence.json"
        attacker.write_text(json.dumps(valid_payload), encoding="utf-8")
        original_read_text = Path.read_text

        def swap_then_read(candidate: Path, *args, **kwargs):  # noqa: ANN002, ANN003
            if candidate == path and not candidate.is_symlink():
                candidate.unlink()
                os.symlink(attacker, candidate)
            return original_read_text(candidate, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", swap_then_read)
        result = evaluate_terminal_evidence(
            root,
            scheduled_at=SCHEDULED_AT,
            invocation_id=INVOCATION_ID,
        )

        assert result["terminal_evidence_verified"] is False


def test_reader_rejects_event_leaf_swap_after_safety_check(monkeypatch) -> None:
    """Artifact hash 與 event 驗證必須綁同一個已開啟的 regular-file FD。"""

    with tempfile.TemporaryDirectory(prefix="top10-fog-event-leaf-swap-") as tmp:
        root = Path(tmp)
        event_path = write_event(root)
        valid_event = event_path.read_bytes()
        attacker = root / "attacker-event.json"
        attacker.write_bytes(valid_event)
        event_path.write_text("{}", encoding="utf-8")
        payload = valid_evidence(root)
        payload["canonical_artifact_sha256"] = hashlib.sha256(valid_event).hexdigest()
        write_evidence(root, payload)
        event_path.write_text("{}", encoding="utf-8")
        original_read_bytes = Path.read_bytes

        def swap_then_read(candidate: Path, *args, **kwargs):  # noqa: ANN002, ANN003
            if candidate == event_path and not candidate.is_symlink():
                candidate.unlink()
                os.symlink(attacker, candidate)
            return original_read_bytes(candidate, *args, **kwargs)

        monkeypatch.setattr(Path, "read_bytes", swap_then_read)
        result = evaluate_terminal_evidence(
            root,
            scheduled_at=SCHEDULED_AT,
            invocation_id=INVOCATION_ID,
        )

        assert result["terminal_evidence_verified"] is False


def test_cadence_rejects_plist_leaf_swap_after_safety_check(monkeypatch) -> None:
    with tempfile.TemporaryDirectory(prefix="top10-fog-plist-leaf-swap-") as tmp:
        root = Path(tmp)
        write_anchor(root)
        write_evidence(root, valid_evidence(root))
        plist_path = root / "scripts" / "com.new-top10.fog-research-worker.plist"
        attacker = root / "attacker.plist"
        attacker.write_bytes(plistlib.dumps({"StartInterval": 3600}))
        plist_path.write_bytes(plistlib.dumps({"StartInterval": 1}))
        original_read_bytes = Path.read_bytes

        def swap_then_read(candidate: Path, *args, **kwargs):  # noqa: ANN002, ANN003
            if candidate == plist_path and not candidate.is_symlink():
                candidate.unlink()
                os.symlink(attacker, candidate)
            return original_read_bytes(candidate, *args, **kwargs)

        monkeypatch.setattr(Path, "read_bytes", swap_then_read)
        result = evaluate_natural_acceptance(
            root,
            scheduled_at=SCHEDULED_AT,
            invocation_id=INVOCATION_ID,
            child_exit_code=0,
            final_process_group_quiescent=True,
        )

        assert result["cadence_verified"] is False


def test_cadence_rejects_archive_leaf_swap_after_safety_check(monkeypatch) -> None:
    with tempfile.TemporaryDirectory(prefix="top10-fog-archive-leaf-swap-") as tmp:
        root = Path(tmp)
        write_anchor(root)
        write_evidence(root, valid_evidence(root))
        receipts = root / "logs" / "storage_safety" / "receipts" / "fog-research-worker"
        receipt_path = next(receipts.glob("*.json"))
        attacker = root / "attacker-receipt.json"
        attacker.write_bytes(receipt_path.read_bytes())
        receipt_path.write_text("{}", encoding="utf-8")
        original_read_text = Path.read_text

        def swap_then_read(candidate: Path, *args, **kwargs):  # noqa: ANN002, ANN003
            if candidate == receipt_path and not candidate.is_symlink():
                candidate.unlink()
                os.symlink(attacker, candidate)
            return original_read_text(candidate, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", swap_then_read)
        result = evaluate_natural_acceptance(
            root,
            scheduled_at=SCHEDULED_AT,
            invocation_id=INVOCATION_ID,
            child_exit_code=0,
            final_process_group_quiescent=True,
        )

        assert result["cadence_verified"] is False


def test_writer_anchors_publish_directory_against_ancestor_swap(monkeypatch) -> None:
    """Publish 中途替換 ancestor 時，不得把 evidence 寫到替代目錄。"""

    with tempfile.TemporaryDirectory(prefix="top10-fog-writer-ancestor-swap-") as tmp:
        root = Path(tmp)
        write_event(root)
        target = terminal_evidence_path(root, INVOCATION_ID)
        attacker_dir = root / "attacker-terminal-evidence"
        attacker_dir.mkdir()
        held_dir = target.parent.with_name(f"{target.parent.name}.held")
        original_link = os.link

        def swap_then_link(*args, **kwargs):  # noqa: ANN002, ANN003
            target.parent.rename(held_dir)
            os.symlink(attacker_dir, target.parent)
            return original_link(*args, **kwargs)

        monkeypatch.setattr(os, "link", swap_then_link)
        write_terminal_evidence(
            root,
            job="fog-research-worker",
            scheduled_at=SCHEDULED_AT,
            invocation_id=INVOCATION_ID,
            run_id=RUN_ID,
            artifact_run_date=RUN_DATE,
        )

        assert not (attacker_dir / target.name).exists()
        assert (held_dir / target.name).is_file()
        result = evaluate_terminal_evidence(
            root,
            scheduled_at=SCHEDULED_AT,
            invocation_id=INVOCATION_ID,
        )
        assert result["terminal_evidence_verified"] is False


@pytest.mark.parametrize(
    ("failure_point", "published"),
    [("before_write", False), ("mid_write", False), ("before_link", False), ("after_link", True)],
)
def test_writer_failures_never_leave_reader_acceptable_partial_evidence(
    monkeypatch, failure_point: str, published: bool
) -> None:
    """失敗點只能留下無 target 或完整 target，不能留下可接受的 partial。"""

    with tempfile.TemporaryDirectory(prefix=f"top10-fog-writer-{failure_point}-") as tmp:
        root = Path(tmp)
        write_event(root)
        target = terminal_evidence_path(root, INVOCATION_ID)
        original_write = os.write
        original_fsync = os.fsync

        if failure_point == "before_write":
            def fail_before_write(*_args, **_kwargs):  # noqa: ANN002, ANN003
                raise OSError("before write")

            monkeypatch.setattr(os, "write", fail_before_write)
        elif failure_point == "mid_write":
            calls = 0

            def partial_then_fail(descriptor: int, data) -> int:  # noqa: ANN001
                nonlocal calls
                calls += 1
                if calls == 1:
                    return original_write(descriptor, data[:8])
                raise OSError("mid write")

            monkeypatch.setattr(os, "write", partial_then_fail)
        elif failure_point == "before_link":
            def fail_before_link(*_args, **_kwargs):  # noqa: ANN002, ANN003
                raise OSError("before link")

            monkeypatch.setattr(os, "link", fail_before_link)
        else:
            def fail_directory_fsync(descriptor: int) -> None:
                if stat.S_ISDIR(os.fstat(descriptor).st_mode):
                    raise OSError("after link")
                original_fsync(descriptor)

            monkeypatch.setattr(os, "fsync", fail_directory_fsync)

        with pytest.raises(OSError):
            write_terminal_evidence(
                root,
                job="fog-research-worker",
                scheduled_at=SCHEDULED_AT,
                invocation_id=INVOCATION_ID,
                run_id=RUN_ID,
                artifact_run_date=RUN_DATE,
            )

        assert target.exists() is published
        assert not list(target.parent.glob(".*.tmp"))
        result = evaluate_terminal_evidence(
            root,
            scheduled_at=SCHEDULED_AT,
            invocation_id=INVOCATION_ID,
        )
        assert result["terminal_evidence_verified"] is published


def test_cadence_denial_and_residual_locks_reset_counter() -> None:
    blockers = (
        "wrong_cadence",
        "denial_marker",
        "fog_worker_lock",
        "research_queue_lock",
        "child_failed",
        "not_quiescent",
    )
    for blocker in blockers:
        with tempfile.TemporaryDirectory(prefix=f"top10-fog-{blocker}-") as tmp:
            root = Path(tmp)
            write_anchor(root)
            payload = valid_evidence(root)
            scheduled_at = SCHEDULED_AT
            invocation_id = INVOCATION_ID
            child_exit_code = 0
            quiescent = True
            if blocker == "wrong_cadence":
                scheduled_at = "2026-09-07T02:00:00+00:00"
                invocation_id = "fog-research-worker-20260907T020000Z-test"
                payload["scheduled_at"] = scheduled_at
                payload["invocation_id"] = invocation_id
            path = terminal_evidence_path(root, invocation_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload), encoding="utf-8")
            if blocker == "denial_marker":
                denial = (
                    root
                    / "logs"
                    / "storage_safety"
                    / "restart_denied"
                    / "fog-research-worker.json"
                )
                denial.parent.mkdir(parents=True, exist_ok=True)
                denial.write_text("{}", encoding="utf-8")
            elif blocker == "fog_worker_lock":
                (root / "logs" / "fog_research_worker.lock").mkdir()
            elif blocker == "research_queue_lock":
                (root / "logs" / "research_queue_owner.lock").mkdir()
            elif blocker == "child_failed":
                child_exit_code = 1
            elif blocker == "not_quiescent":
                quiescent = False

            result = evaluate_natural_acceptance(
                root,
                scheduled_at=scheduled_at,
                invocation_id=invocation_id,
                child_exit_code=child_exit_code,
                final_process_group_quiescent=quiescent,
            )

            assert result["accepted_natural_cycles"] == 0, blocker
            assert result["acceptance_status"] == "NATURAL_ACCEPTANCE_PENDING", blocker


def test_pending_zero_receipt_is_cadence_anchor_for_first_new_cycle() -> None:
    """既有 live pending receipt 只證 cadence；第一個新合格週期必須從 1 開始。"""

    with tempfile.TemporaryDirectory(prefix="top10-fog-pending-anchor-") as tmp:
        root = Path(tmp)
        write_anchor(root)
        receipt_path = next(
            (root / "logs" / "storage_safety" / "receipts" / "fog-research-worker").glob(
                "*.json"
            )
        )
        previous = json.loads(receipt_path.read_text(encoding="utf-8"))
        previous.update(
            terminal_evidence_verified=False,
            terminal_evidence_status="MISSING",
            artifact_run_date=None,
            publish_or_provider_result=None,
            accepted_natural_cycles=0,
        )
        receipt_path.write_text(json.dumps(previous), encoding="utf-8")
        write_evidence(root, valid_evidence(root))

        result = evaluate_natural_acceptance(
            root,
            scheduled_at=SCHEDULED_AT,
            invocation_id=INVOCATION_ID,
            child_exit_code=0,
            final_process_group_quiescent=True,
        )

        assert result["cadence_verified"] is True
        assert result["accepted_natural_cycles"] == 1
        assert result["acceptance_status"] == "NATURAL_ACCEPTANCE_PENDING"
        assert result["natural_provenance_method"] == "ARCHIVED_RECEIPT_CADENCE_V1"


def test_cadence_drift_over_sixty_seconds_fails_closed() -> None:
    with tempfile.TemporaryDirectory(prefix="top10-fog-tight-cadence-") as tmp:
        root = Path(tmp)
        write_anchor(root)
        scheduled_at = "2026-09-07T01:01:01+00:00"
        invocation_id = "fog-research-worker-20260907T010101Z-test"
        run_id = "fog-research-2026-09-07-tight-drift-b1"
        write_event(root, run_id=run_id)
        write_terminal_evidence(
            root,
            job="fog-research-worker",
            scheduled_at=scheduled_at,
            invocation_id=invocation_id,
            run_id=run_id,
            artifact_run_date=RUN_DATE,
        )

        result = evaluate_natural_acceptance(
            root,
            scheduled_at=scheduled_at,
            invocation_id=invocation_id,
            child_exit_code=0,
            final_process_group_quiescent=True,
        )

        assert result["cadence_verified"] is False
        assert result["cadence_drift_limit_seconds"] == 60
        assert result["accepted_natural_cycles"] == 0


@pytest.mark.parametrize(
    ("field", "invalid_value", "cadence_still_valid"),
    [
        ("cadence_verified", False, True),
        ("natural_trigger_verified", False, True),
        ("artifact_run_date", "2026-09-06", True),
        ("denial_marker_absent", False, True),
        ("fog_worker_lock_absent", False, True),
        ("research_queue_lock_absent", False, True),
        ("terminal_evidence_verified", False, True),
        ("publish_or_provider_result", "FAILED", True),
        ("natural_provenance_method", "CALLER_CLAIM", True),
        ("consecutive_natural_guard_cycles", 0, True),
        ("acceptance_status", "ACCEPTED", True),
        ("status", "CHILD_FAILED", False),
        ("child_exit_code", 1, False),
        ("final_process_group_quiescent", False, False),
    ],
)
def test_unverified_previous_counter_cannot_be_used_as_acceptance_authority(
    field: str, invalid_value: object, cadence_still_valid: bool
) -> None:
    with tempfile.TemporaryDirectory(prefix="top10-fog-forged-counter-") as tmp:
        root = Path(tmp)
        write_anchor(root)
        receipt_path = next(
            (root / "logs" / "storage_safety" / "receipts" / "fog-research-worker").glob(
                "*.json"
            )
        )
        previous = json.loads(receipt_path.read_text(encoding="utf-8"))
        previous.update(
            accepted_natural_cycles=1,
            cadence_verified=True,
            natural_trigger_verified=True,
            natural_provenance_method="ARCHIVED_RECEIPT_CADENCE_V1",
            denial_marker_absent=True,
            fog_worker_lock_absent=True,
            research_queue_lock_absent=True,
            consecutive_natural_guard_cycles=1,
            acceptance_status="NATURAL_ACCEPTANCE_PENDING",
        )
        previous[field] = invalid_value
        receipt_path.write_text(json.dumps(previous), encoding="utf-8")
        write_evidence(root, valid_evidence(root))

        result = evaluate_natural_acceptance(
            root,
            scheduled_at=SCHEDULED_AT,
            invocation_id=INVOCATION_ID,
            child_exit_code=0,
            final_process_group_quiescent=True,
        )

        assert result["cadence_verified"] is cadence_still_valid
        assert result["accepted_natural_cycles"] == 0
