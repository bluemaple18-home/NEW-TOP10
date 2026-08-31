from __future__ import annotations

import json
from pathlib import Path

import duckdb

from app.research.contracts import content_hash
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
        context.requested_dataset_bundle_id, context.requested_dataset_bundle_manifest_ref,
        context.requested_dataset_bundle_manifest,
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


def test_empty_run_artifact_cannot_mask_existing_attempt_receipt_membership(
    tmp_path: Path,
) -> None:
    context = batch_attempt(tmp_path, "batch-empty-mask")
    receipt = finish_topic_attempt(
        context,
        terminal_status="FAILED",
        matrix_paths=[],
        failure_reason="RUNNER_STEP_FAILED",
    )
    run = tmp_path / "run.json"
    run.write_text(json.dumps({
        "inputs": {"research_batch_id": "batch-empty-mask"},
        "topic_runs": [],
        "outcome": {"decision": "NO_EXECUTABLE_TOPIC"},
    }), encoding="utf-8")

    result = verify_batch(
        corpus_root=context.root,
        batch_id="batch-empty-mask",
        run_artifact=run,
    )
    assert result["status"] == "FAIL"
    assert result["attempt_count"] == 1
    assert result["receipt_count"] == 1
    assert result["empty_outcome"] is False
    assert receipt["receipt_id"] in result["receipt_ids"]
    assert any(
        error["reason"] == "RUN_ARTIFACT_EMPTY_OUTCOME_CONFLICTS_WITH_CORPUS_MEMBERSHIP"
        for error in result["errors"]
    )


def test_missing_terminal_receipt_fails_closed(tmp_path: Path) -> None:
    context = batch_attempt(tmp_path, "batch-orphan")
    result = verify_batch(corpus_root=context.root, batch_id="batch-orphan")
    assert result["status"] == "FAIL"
    assert any(error["reason"] == "TERMINAL_RECEIPT_MISSING" for error in result["errors"])


def test_batch_verifier_rejects_attempt_bundle_identity_tampering(tmp_path: Path) -> None:
    context = batch_attempt(tmp_path, "batch-tamper")
    baseline = tmp_path / "baseline_strategy_matrix.json"
    candidate = tmp_path / "candidate_strategy_matrix.json"
    authority = tmp_path / "development.json"
    write_matrix(baseline, context, "baseline")
    write_matrix(candidate, context, "candidate")
    write_development_authority(authority, context)
    finish_topic_attempt(
        context,
        terminal_status="SUCCEEDED",
        matrix_paths=[baseline, candidate],
        lineage_authority_paths=[authority],
    )

    attempt_path = context.root / "attempts" / f"{context.run_id}.started.json"
    attempt = json.loads(attempt_path.read_text(encoding="utf-8"))
    attempt["requested_dataset_bundle_id"] = "sha256:" + "a" * 64
    attempt["requested_dataset_bundle_manifest_ref"] = "dataset_bundles/" + "a" * 64 + ".json"
    attempt["attempt_event_id"] = content_hash(attempt, omit={"attempt_event_id"})
    attempt_path.write_text(json.dumps(attempt), encoding="utf-8")

    result = verify_batch(corpus_root=context.root, batch_id="batch-tamper")
    assert result["status"] == "FAIL"
    assert any(error["reason"] == "BATCH_BUNDLE_BINDING_MISMATCH" for error in result["errors"])


def test_batch_verifier_rejects_receipt_attempt_event_tampering(tmp_path: Path) -> None:
    context = batch_attempt(tmp_path, "batch-receipt-tamper")
    receipt = finish_topic_attempt(
        context,
        terminal_status="FAILED",
        matrix_paths=[],
        failure_reason="RUNNER_STEP_FAILED",
    )
    receipt_path = context.root / "receipts" / f"{context.run_id}.json"
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    payload["attempt_event_id"] = "sha256:" + "b" * 64
    payload["receipt_id"] = content_hash(payload, omit={"receipt_id"})
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    result = verify_batch(corpus_root=context.root, batch_id="batch-receipt-tamper")
    assert result["status"] == "FAIL"
    assert receipt["receipt_id"] not in result["receipt_ids"]
    assert any(error["reason"] == "RECEIPT_ATTEMPT_EVENT_MISMATCH" for error in result["errors"])


def test_batch_verifier_rejects_run_artifact_membership_tampering(tmp_path: Path) -> None:
    context = batch_attempt(tmp_path, "batch-run-artifact")
    receipt = finish_topic_attempt(
        context,
        terminal_status="FAILED",
        matrix_paths=[],
        failure_reason="RUNNER_STEP_FAILED",
    )
    run_artifact = tmp_path / "run.json"
    run_artifact.write_text(json.dumps({
        "inputs": {"research_batch_id": "batch-run-artifact"},
        "topic_runs": [{
            "research_spine": {
                "run_id": "run-forged",
                "intent_id": context.intent_id,
                "receipt_id": receipt["receipt_id"],
                "receipt_path": str(context.root / "receipts" / f"{context.run_id}.json"),
            },
        }],
        "outcome": {"decision": "PARTIAL_SCORE_ONLY"},
    }), encoding="utf-8")

    result = verify_batch(
        corpus_root=context.root,
        batch_id="batch-run-artifact",
        run_artifact=run_artifact,
    )
    assert result["status"] == "FAIL"
    assert any(error["reason"] == "RUN_ARTIFACT_RUN_MISMATCH" for error in result["errors"])


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
