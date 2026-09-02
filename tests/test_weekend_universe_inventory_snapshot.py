from __future__ import annotations

import json
import sys
import tracemalloc
from argparse import Namespace
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import build_weekend_universe_inventory as builder
import weekend_training_common as common
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


def test_development_lifecycle_topic_does_not_expand_hypothesis_universe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = tmp_path / "topic_registry.json"
    registry.write_text(
        json.dumps(
            {
                "topics": [
                    {
                        "topic_id": "topic-1",
                        "candidate_dir": "artifacts/backtest/candidate",
                        "manager_status": "candidate",
                    },
                    {
                        "topic_id": "topic-1:development_screen",
                        "candidate_dir": "artifacts/backtest/candidate",
                        "manager_status": "development_screen_passed",
                        "selection_rationale": {
                            "research_stage": "DEVELOPMENT_SCREEN",
                            "parent_topic_id": "topic-1",
                        },
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(common, "TOPIC_REGISTRY_PATH", registry)

    topics = common.load_topics()

    assert len(topics) == 1
    assert topics[0]["topic_id"] == "topic-1"
    assert topics[0]["lifecycle_topic_id"] == "topic-1:development_screen"
    assert topics[0]["manager_status"] == "development_screen_passed"


def fog_map(processed: int, total: int = 4) -> dict[str, Any]:
    return {"summary": {"expanded_processed": processed, "expanded_pending": total - processed}}


def test_inventory_reuses_research_map_v2_completion_predicate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    topic = {"topic_id": "topic-1", "candidate_dir": "artifacts/backtest/candidate"}
    default = {
        "horizon": "3",
        "stop_loss": "none",
        "take_profit": "0.15",
        "group_exposure": "none",
        "regime_gate": "ALL",
        "risk_guard": "NONE",
        "entry_filter": "TOPIC_DEFAULT",
    }
    valid = {**default, "regime_gate": "BIG_BULL_ONLY"}
    incomplete = {**default, "risk_guard": "RISK_OFF_CASH"}
    missing_artifact = {**default, "entry_filter": "LOG_GATE"}

    def history_row(dimensions: dict[str, str], **overrides: Any) -> dict[str, Any]:
        return {
            "schema_version": "research-map-run-history.v2",
            "map_version": "v2",
            "combo_id": builder.v2_combo_id(topic, dimensions),
            "status": "completed",
            "artifact_path": "artifacts/backtest/result.json",
            "dimensions": dimensions,
            "decision": "LOW_INFORMATION",
            "insight_level": "low_information",
            **overrides,
        }

    history = [
        history_row(valid),
        history_row(default),
        history_row(incomplete, status="running"),
        history_row(missing_artifact, artifact_path=None),
    ]
    monkeypatch.setattr(builder, "load_topics", lambda: [topic])
    monkeypatch.setattr(builder, "load_map", lambda: fog_map(1))
    monkeypatch.setattr(builder, "load_history", lambda: history)
    monkeypatch.setattr(builder, "base_scenarios_by_v2_combo", lambda topics, records: {})
    monkeypatch.setattr(builder, "stage2_combo_ids", lambda date: set())
    monkeypatch.setattr(builder, "all_v2_dimensions", lambda dimensions: [valid, default, incomplete, missing_artifact])
    monkeypatch.setattr(
        __import__("research_map_contract"),
        "SCENARIO_DIMENSION_GRID",
        [{"horizon": "3", "stop_loss": "none", "take_profit": "0.15", "group_exposure": "none"}],
    )

    rows, _ = builder.build_initial_rows(RUN_DATE)
    statuses = {item["combo_id"]: item["current_status"] for item in rows}

    assert statuses[builder.v2_combo_id(topic, valid)] == "LOW_INFORMATION"
    assert statuses[builder.v2_combo_id(topic, default)] == "PENDING"
    assert statuses[builder.v2_combo_id(topic, incomplete)] == "PENDING"
    assert statuses[builder.v2_combo_id(topic, missing_artifact)] == "PENDING"


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


def test_summary_only_bounded_cli_does_not_materialize_full_inventory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row_count = 50_000
    topic = {"topic_id": "topic-1", "candidate_dir": "artifacts/backtest/candidate"}

    def dimensions(_: dict[str, Any]):
        for index in range(row_count):
            yield {
                "horizon": str(index),
                "stop_loss": "none",
                "take_profit": "0.15",
                "group_exposure": "none",
                "regime_gate": "ALL",
                "risk_guard": "NONE",
                "entry_filter": "TOPIC_DEFAULT",
            }

    monkeypatch.setattr(builder, "parse_args", lambda: Namespace(
        date=RUN_DATE,
        include_records=False,
        write_bounded_frontier_queue=True,
        max_frontier_representatives=144,
    ))
    monkeypatch.setattr(builder, "load_topics", lambda: [topic])
    monkeypatch.setattr(builder, "load_map", lambda: fog_map(0, row_count))
    monkeypatch.setattr(builder, "load_history", lambda: [])
    monkeypatch.setattr(builder, "base_scenarios_by_v2_combo", lambda topics, records: {})
    monkeypatch.setattr(builder, "stage2_combo_ids", lambda date: set())
    monkeypatch.setattr(builder, "all_v2_dimensions", dimensions)
    monkeypatch.setattr(builder, "v2_combo_id", lambda topic, item: f"combo-{item['horizon']}")
    monkeypatch.setattr(builder, "is_default_coordinate", lambda item: False)
    monkeypatch.setattr(builder, "unsupported_reason", lambda topic, item: None)
    monkeypatch.setattr(builder, "rule_prune_reason", lambda item: None)
    monkeypatch.setattr(builder, "equivalence_key", lambda topic, item: f"group-{int(item['horizon']) // 6}")
    monkeypatch.setattr(builder, "priority_score", lambda row, stage2_ids: int(row["dimensions"]["horizon"]) % 11)
    monkeypatch.setattr(builder, "expanded_universe_total", lambda topic_count: row_count)
    monkeypatch.setattr(__import__("research_map_contract"), "SCENARIO_DIMENSION_GRID", [{}])
    monkeypatch.setattr(builder, "inventory_paths", lambda date: (tmp_path / "inventory.json", tmp_path / "inventory.md"))
    monkeypatch.setattr(builder, "queue_paths", lambda date: (tmp_path / "queue.json", tmp_path / "queue.md"))

    tracemalloc.start()
    try:
        assert builder.main() == 0
        _, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert peak_bytes < 35_000_000


def test_streaming_summary_matches_full_record_semantics(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [
        {**row("processed", "EXECUTED_REPLAY"), "equivalence_key": "g1", "priority_score": 1},
        {**row("inherited", "PENDING"), "equivalence_key": "g1", "priority_score": 9},
        {**row("low", "PENDING"), "equivalence_key": "g2", "priority_score": 2},
        {**row("high", "PENDING"), "equivalence_key": "g2", "priority_score": 8},
        {
            **row("unsupported", "PENDING"),
            "equivalence_key": "g3",
            "eligible_for_replay": False,
            "unsupported_reason": "MISSING_BASELINE_RANKINGS_DIR:test",
        },
    ]
    source = builder.InventorySource(
        topics=[{"topic_id": "topic-1"}],
        fog_map=fog_map(1, len(rows)),
        latest_records={},
        base_by_v2={},
        stage2_ids=set(),
    )
    monkeypatch.setattr(builder, "build_initial_rows", lambda date: (deepcopy(rows), source.fog_map))
    monkeypatch.setattr(builder, "load_inventory_source", lambda date: source)
    monkeypatch.setattr(builder, "iter_initial_rows", lambda loaded: iter(deepcopy(rows)))
    monkeypatch.setattr(builder, "load_topics", lambda: source.topics)
    monkeypatch.setattr(builder, "expanded_universe_total", lambda topic_count: len(rows))

    full_payload, _ = builder.build_payload_and_rows_once(RUN_DATE)
    streaming_payload, frontier = builder.build_summary_and_bounded_frontier_once(RUN_DATE, 1)

    assert streaming_payload["summary"] == full_payload["summary"]
    assert [item["combo_id"] for item in frontier["items"]] == ["high"]


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
