from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import build_weekend_universe_inventory as builder
import research_map_contract as map_contract
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


def test_inventory_uses_research_map_processed_id_semantics_for_default_v2_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    topic = {
        "topic_id": "strategy-matrix:fixture:long_horizon",
        "candidate_dir": "artifacts/backtest/fixture",
    }
    base_dimensions = [
        {"horizon": "3", "stop_loss": "none", "take_profit": "0.15", "group_exposure": "none"},
        {"horizon": "3", "stop_loss": "none", "take_profit": "0.25", "group_exposure": "none"},
    ]
    default_rows = []
    for dimensions in base_dimensions:
        expanded = {**dimensions, **map_contract.V2_DEFAULT_COORDINATES}
        default_rows.append(
            {
                "schema_version": "research-map-run-history.v2",
                "map_version": "v2",
                "combo_id": map_contract.v2_combo_id(topic, expanded),
                "topic_id": topic["topic_id"],
                "dimensions": expanded,
                "status": "completed",
                "artifact_path": "artifacts/weekend_training/weekend_representative_replay_fixture.json",
                "decision": "LOW_INFORMATION",
                "insight_level": "ordinary",
                "finished_at": "2099-01-05T00:00:00+00:00",
            }
        )

    monkeypatch.setattr(map_contract, "SCENARIO_DIMENSION_GRID", base_dimensions)
    monkeypatch.setattr(builder, "load_topics", lambda: [topic])
    monkeypatch.setattr(builder, "load_map", lambda: fog_map(0, total=2))
    monkeypatch.setattr(builder, "load_history", lambda: default_rows)
    monkeypatch.setattr(builder, "stage2_combo_ids", lambda date: set())
    monkeypatch.setattr(
        builder,
        "all_v2_dimensions",
        lambda dimensions: [{**dimensions, **map_contract.V2_DEFAULT_COORDINATES}],
    )
    monkeypatch.setattr(builder, "unsupported_reason", lambda topic, dimensions: None)
    monkeypatch.setattr(builder, "rule_prune_reason", lambda dimensions: None)

    rows, _ = builder.build_initial_rows(RUN_DATE)
    inventory_processed_ids = {
        item["combo_id"] for item in rows if item["current_status"] != "PENDING"
    }

    assert inventory_processed_ids == set()
