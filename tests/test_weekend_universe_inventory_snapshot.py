from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import build_weekend_universe_inventory as builder
import verify_weekend_universe_inventory as verifier


RUN_DATE = "2099-01-05"


def row(combo_id: str, status: str) -> dict[str, Any]:
    return {
        "combo_id": combo_id,
        "topic_id": "topic-1",
        "candidate_dir": "artifacts/backtest/candidate",
        "dimensions": {"horizon": "5"},
        "current_status": status,
        "burn_down_status": status if status != "PENDING" else "PENDING_ASSIGNMENT",
        "equivalence_key": combo_id,
        "representative_combo_id": combo_id,
        "eligible_for_replay": status == "PENDING",
        "prune_reason": None,
        "unsupported_reason": None,
        "unsupported_category": None,
        "can_be_unblocked": False,
        "unblock_requirement": None,
        "source_artifact": None,
        "priority_score": 0,
        "production_impact": "NO_PRODUCTION_CHANGE",
    }


def fog_map(processed: int, total: int = 4) -> dict[str, Any]:
    return {"summary": {"expanded_processed": processed, "expanded_pending": total - processed}}


def test_inventory_rebuilds_when_source_snapshot_advances_during_build(monkeypatch: pytest.MonkeyPatch) -> None:
    stale_rows = [row("done-1", "EXECUTED_REPLAY"), row("done-2", "NEXT_STAGE_CANDIDATE"), row("done-3", "LOW_INFORMATION"), row("todo", "PENDING")]
    consistent_rows = [*stale_rows[:3], row("done-4", "REJECTED")]
    attempts = iter([(stale_rows, fog_map(2)), (consistent_rows, fog_map(4))])

    monkeypatch.setattr(builder, "build_initial_rows", lambda date: next(attempts))
    monkeypatch.setattr(builder, "stage2_combo_ids", lambda date: set())
    monkeypatch.setattr(builder, "load_topics", lambda: [{"topic_id": "topic-1"}])
    monkeypatch.setattr(builder, "expanded_universe_total", lambda topic_count: 4)

    payload, rows = builder.build_payload_and_rows(RUN_DATE)

    assert len(rows) == 4
    assert payload["summary"]["current_processed_count"] == 4
    assert payload["summary"]["map_expanded_processed"] == 4
    assert payload["source"]["snapshot_rebuilt_after_mismatch"] is True


def test_inventory_fails_loud_when_source_snapshot_stays_inconsistent(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [row("done-1", "EXECUTED_REPLAY"), row("done-2", "NEXT_STAGE_CANDIDATE"), row("todo-1", "PENDING"), row("todo-2", "PENDING")]

    monkeypatch.setattr(builder, "build_initial_rows", lambda date: (rows, fog_map(1)))
    monkeypatch.setattr(builder, "stage2_combo_ids", lambda date: set())
    monkeypatch.setattr(builder, "load_topics", lambda: [{"topic_id": "topic-1"}])
    monkeypatch.setattr(builder, "expanded_universe_total", lambda topic_count: 4)

    with pytest.raises(builder.SnapshotInconsistentError):
        builder.build_payload_and_rows(RUN_DATE)


def test_verifier_remains_fail_closed_for_stale_inventory_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    artifact = tmp_path / "inventory.json"
    artifact.write_text(
        json.dumps(
            {
                "schema_version": "weekend-universe-inventory.v1",
                "production_impact": "NO_PRODUCTION_CHANGE",
                "summary": {
                    "full_universe_total": 4,
                    "map_expanded_processed": 1,
                    "map_expanded_pending": 3,
                    "current_processed_count": 2,
                    "current_remaining_count": 2,
                    "unsupported_category_counts": {},
                    "burn_down_status_counts": {},
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(verifier, "load_topics", lambda: [{"topic_id": "topic-1"}])
    monkeypatch.setattr(verifier, "expanded_universe_total", lambda topic_count: 4)
    monkeypatch.setattr(verifier, "load_map", lambda: fog_map(2))

    payload = verifier.build_payload(RUN_DATE, artifact)

    assert payload["status"] == "FAILED"
    assert {"current_processed_matches_source_snapshot", "remaining_matches_source_snapshot"} <= {
        error["name"] for error in payload["errors"]
    }
