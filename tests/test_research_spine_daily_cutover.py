from __future__ import annotations

import json
from pathlib import Path

import duckdb

from app.research.history_compatibility_projection import build_projection, _select_latest_rows
from app.research.legacy_migration import LegacySource, build_migration
from app.research.observation_ingest import ingest_corpus
from app.research.run_receipts import finish_topic_attempt
from scripts.verify_research_spine_batch import verify_batch
from tests.test_autonomous_research_receipts import (
    begin as begin_fixture,
    write_development_authority,
    write_matrix,
)


def batch_attempt(tmp_path: Path, batch_id: str):
    context = begin_fixture(tmp_path)
    intent_path = context.root / "intents" / f"{context.intent_id}.json"
    attempt_path = context.root / "attempts" / f"{context.run_id}.started.json"
    intent = json.loads(intent_path.read_text())
    attempt = json.loads(attempt_path.read_text())
    # Fixture begin predates daily caller；rebuild canonical attempt for isolated verifier test.
    intent["selection_reason"]["research_batch_id"] = batch_id
    attempt["executor"]["research_batch_id"] = batch_id
    from app.research.contracts import content_hash
    intent_path.write_text(json.dumps(intent), encoding="utf-8")
    attempt["attempt_event_id"] = content_hash(attempt, omit={"attempt_event_id"})
    attempt_path.write_text(json.dumps(attempt), encoding="utf-8")
    context = context.__class__(
        context.root, context.run_id, context.intent_id, attempt["attempt_event_id"],
        context.started_at, context.trial_specs, context.requested, context.trial_ids_by_role,
    )
    return context


def test_batch_verifier_and_ledger_use_exact_receipt_membership(tmp_path: Path) -> None:
    context = batch_attempt(tmp_path, "batch-a")
    baseline = tmp_path / "baseline_strategy_matrix.json"
    candidate = tmp_path / "candidate_strategy_matrix.json"
    authority = tmp_path / "development.json"
    write_matrix(baseline, context, "baseline")
    write_matrix(candidate, context, "candidate")
    write_development_authority(authority, context)
    receipt = finish_topic_attempt(
        context,
        terminal_status="SUCCEEDED",
        matrix_paths=[baseline, candidate],
        lineage_authority_paths=[authority],
    )
    result = verify_batch(corpus_root=context.root, batch_id="batch-a")
    assert result["status"] == "PASS"
    assert result["receipt_ids"] == [receipt["receipt_id"]]
    assert verify_batch(corpus_root=context.root, batch_id="batch-b")["status"] == "FAIL"
    ledger = tmp_path / "ledger.duckdb"
    ingest_corpus(corpus_root=context.root, ledger_path=ledger)
    connection = duckdb.connect(str(ledger), read_only=True)
    try:
        assert connection.execute(
            "SELECT count(*) FROM run_receipts WHERE receipt_id = ?", [receipt["receipt_id"]]
        ).fetchone()[0] == 1
    finally:
        connection.close()


def test_empty_batch_requires_explicit_runner_outcome(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    run = tmp_path / "run.json"
    run.write_text(json.dumps({
        "inputs": {"research_batch_id": "empty-batch"},
        "topic_runs": [],
        "outcome": {"decision": "NO_EXECUTABLE_TOPIC"},
    }), encoding="utf-8")
    result = verify_batch(corpus_root=corpus, batch_id="empty-batch", run_artifact=run)
    assert result["status"] == "PASS"
    assert result["empty_outcome"] is True


def test_missing_terminal_receipt_fails_closed(tmp_path: Path) -> None:
    context = batch_attempt(tmp_path, "batch-orphan")
    result = verify_batch(corpus_root=context.root, batch_id="batch-orphan")
    assert result["status"] == "FAIL"
    assert any(error["reason"] == "TERMINAL_RECEIPT_MISSING" for error in result["errors"])


def test_ledger_history_projection_preserves_frozen_legacy_and_is_deterministic(
    tmp_path: Path,
) -> None:
    legacy = tmp_path / "run_history.jsonl"
    legacy_row = {
        "combo_id": "legacy|horizon_3|stop_none|take_profit_none|group_exposure_none",
        "topic_id": "legacy:topic",
        "dimensions": {
            "horizon": "3", "stop_loss": "none", "take_profit": "none",
            "group_exposure": "none",
        },
        "status": "OK",
    }
    legacy.write_text(json.dumps(legacy_row) + "\n", encoding="utf-8")
    corpus = tmp_path / "corpus"
    build_migration(
        corpus_root=corpus,
        sources=[LegacySource(legacy, "RUN_HISTORY_JSONL")],
    )
    ledger = tmp_path / "ledger.duckdb"
    ingest_corpus(corpus_root=corpus, ledger_path=ledger)
    output = tmp_path / "projected.jsonl"
    manifest = tmp_path / "manifest.json"
    first = build_projection(
        ledger_path=ledger, corpus_root=corpus, output=output, manifest_output=manifest,
    )
    first_bytes = output.read_bytes()
    second = build_projection(
        ledger_path=ledger, corpus_root=corpus, output=output, manifest_output=manifest,
    )
    assert output.read_bytes() == first_bytes
    assert first["projection_id"] == second["projection_id"]
    assert json.loads(output.read_text()) == legacy_row


def test_history_projection_selects_latest_completed_combo_not_identity_order() -> None:
    rows = [
        {
            "combo_id": "same-combo", "finished_at": "2026-08-14T02:00:00+00:00",
            "canonical_observation_id": "sha256:" + "0" * 64, "score_delta": 8,
        },
        {
            "combo_id": "same-combo", "finished_at": "2026-08-14T01:00:00+00:00",
            "canonical_observation_id": "sha256:" + "f" * 64, "score_delta": 5,
        },
    ]
    assert _select_latest_rows(rows)[0]["score_delta"] == 8
