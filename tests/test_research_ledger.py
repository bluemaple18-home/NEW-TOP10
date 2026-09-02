from __future__ import annotations

import json
import shutil
from pathlib import Path

import duckdb
import pytest

from app.research.observation_ingest import (
    DUCKDB_INGEST_MEMORY_LIMIT,
    _configure_write_connection,
    ingest_corpus,
    ledger_snapshot,
)
from app.research.run_receipts import finish_topic_attempt
from tests.test_autonomous_research_receipts import (
    begin,
    write_development_authority,
    write_matrix,
)


def test_write_connection_is_resource_bounded_and_spills_under_tmpdir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TMPDIR", str(tmp_path / "runtime-tmp"))
    ledger = tmp_path / "ledger.duckdb"
    connection = duckdb.connect(str(ledger))
    try:
        spill_path = _configure_write_connection(connection, ledger_path=ledger)
        settings = connection.execute(
            "SELECT current_setting('threads'), "
            "current_setting('preserve_insertion_order'), "
            "current_setting('memory_limit'), current_setting('temp_directory')"
        ).fetchone()
    finally:
        connection.close()

    assert settings == (1, False, "976.5 MiB", str(spill_path))
    assert spill_path.is_relative_to(tmp_path / "runtime-tmp")
    assert DUCKDB_INGEST_MEMORY_LIMIT == "1024MB"


def corpus_with_receipt(tmp_path: Path, *, total_return: float = 0.08) -> tuple[Path, str]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    context = begin(tmp_path)
    baseline = tmp_path / "baseline.json"
    candidate = tmp_path / "candidate.json"
    authority = tmp_path / "development.json"
    write_matrix(baseline, context, "baseline")
    write_matrix(candidate, context, "candidate")
    for path in (baseline, candidate):
        payload = json.loads(path.read_text())
        payload["scenarios"][0].update(
            {
                "scenario_id": "h5_sl0p08_tp0p15_gc0p35",
                "total_return": total_return,
                "max_drawdown": -0.12,
                "win_rate": 0.55,
                "avg_trade_return": 0.01,
                "trade_count": 25,
                "score": 0.2,
                "p_value": 0.04,
                "robust_neighbor_pass_count": 0,
            }
        )
        path.write_text(json.dumps(payload), encoding="utf-8")
    write_development_authority(authority, context)
    receipt = finish_topic_attempt(
        context,
        terminal_status="SUCCEEDED",
        matrix_paths=[baseline, candidate],
        lineage_authority_paths=[authority],
    )
    return context.root, receipt["receipt_id"]


def merge_corpus(target: Path, source: Path) -> None:
    for directory in ("trial_specs", "intents", "attempts", "receipts", "source_corpus/sha256"):
        (target / directory).mkdir(parents=True, exist_ok=True)
        for path in (source / directory).glob("*"):
            destination = target / directory / path.name
            if not destination.exists():
                shutil.copy2(path, destination)


def counts(path: Path) -> dict[str, int]:
    connection = duckdb.connect(str(path), read_only=True)
    try:
        return {
            table: connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in (
                "trial_specs", "research_intents", "run_attempts", "run_receipts",
                "trial_parameters", "execution_units", "execution_unit_parameters",
                "execution_unit_episodes", "observations", "observation_provenance",
            )
        }
    finally:
        connection.close()


def test_receipt_ingest_is_idempotent_and_normalized(tmp_path: Path) -> None:
    corpus, _ = corpus_with_receipt(tmp_path)
    ledger = tmp_path / "ledger.duckdb"
    first = ingest_corpus(corpus_root=corpus, ledger_path=ledger)
    before = counts(ledger)
    second = ingest_corpus(corpus_root=corpus, ledger_path=ledger)
    assert before == counts(ledger) == {
        "trial_specs": 2,
        "trial_parameters": 14,
        "research_intents": 1,
        "run_attempts": 1,
        "run_receipts": 1,
        "execution_units": 2,
        "execution_unit_parameters": 14,
        "execution_unit_episodes": 2,
        "observations": 2,
        "observation_provenance": 2,
    }
    assert first.receipts_inserted == 1
    assert second.receipts_inserted == 0
    assert second.observations_inserted == 0
    assert first.snapshot_hash == second.snapshot_hash


def test_deleted_ledger_rebuild_has_identical_logical_snapshot(tmp_path: Path) -> None:
    corpus, _ = corpus_with_receipt(tmp_path)
    ledger = tmp_path / "ledger.duckdb"
    first = ingest_corpus(corpus_root=corpus, ledger_path=ledger)
    rebuilt = ingest_corpus(corpus_root=corpus, ledger_path=ledger, rebuild=True)
    assert first.snapshot_hash == rebuilt.snapshot_hash
    assert counts(ledger)["observations"] == 2


def test_copy_path_does_not_increase_evidence_weight(tmp_path: Path) -> None:
    corpus, _ = corpus_with_receipt(tmp_path)
    ledger = tmp_path / "ledger.duckdb"
    ingest_corpus(corpus_root=corpus, ledger_path=ledger)
    connection = duckdb.connect(str(ledger))
    try:
        observations, evidence = connection.execute(
            "SELECT count(*), count(DISTINCT evidence_unit_id) FROM observations"
        ).fetchone()
    finally:
        connection.close()
    assert observations == evidence == 2


def test_corrupt_cas_rolls_back_whole_ingestion(tmp_path: Path) -> None:
    corpus, _ = corpus_with_receipt(tmp_path)
    cas = next((corpus / "source_corpus" / "sha256").iterdir())
    cas.write_bytes(b"corrupt")
    ledger = tmp_path / "ledger.duckdb"
    with pytest.raises(ValueError, match="CAS artifact mismatch"):
        ingest_corpus(corpus_root=corpus, ledger_path=ledger)
    connection = duckdb.connect(str(ledger), read_only=True)
    try:
        assert connection.execute("SELECT count(*) FROM run_receipts").fetchone()[0] == 0
    finally:
        connection.close()


def test_failed_atomic_rebuild_preserves_previous_ledger(tmp_path: Path) -> None:
    corpus, _ = corpus_with_receipt(tmp_path)
    ledger = tmp_path / "ledger.duckdb"
    ingest_corpus(corpus_root=corpus, ledger_path=ledger)
    before = counts(ledger)
    cas = next((corpus / "source_corpus" / "sha256").iterdir())
    cas.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="CAS artifact mismatch"):
        ingest_corpus(corpus_root=corpus, ledger_path=ledger, rebuild=True)
    assert counts(ledger) == before


def test_schema_invalid_receipt_is_quarantined_without_observations(tmp_path: Path) -> None:
    corpus, _ = corpus_with_receipt(tmp_path)
    receipt_path = next((corpus / "receipts").glob("*.json"))
    payload = json.loads(receipt_path.read_text())
    payload["requested"].pop("execution_profile_by_trial")
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")
    ledger = tmp_path / "ledger.duckdb"
    result = ingest_corpus(corpus_root=corpus, ledger_path=ledger)
    assert result.rejections == 1
    assert result.receipts_inserted == 0
    assert counts(ledger)["observations"] == 0


def test_rerun_same_semantic_evidence_does_not_increase_weight(tmp_path: Path) -> None:
    first_corpus, _ = corpus_with_receipt(tmp_path / "first")
    second_corpus, _ = corpus_with_receipt(tmp_path / "second")
    merge_corpus(first_corpus, second_corpus)
    ledger = tmp_path / "ledger.duckdb"
    ingest_corpus(corpus_root=first_corpus, ledger_path=ledger)
    connection = duckdb.connect(str(ledger), read_only=True)
    try:
        observations, units, evidence = connection.execute(
            "SELECT (SELECT count(*) FROM observations), "
            "(SELECT count(*) FROM execution_units), "
            "(SELECT count(DISTINCT evidence_unit_id) FROM observations)"
        ).fetchone()
    finally:
        connection.close()
    assert observations == evidence == 2
    assert units == 4


def test_conflicting_semantic_evidence_is_quarantined(tmp_path: Path) -> None:
    first_corpus, _ = corpus_with_receipt(tmp_path / "first")
    second_corpus, _ = corpus_with_receipt(tmp_path / "second", total_return=-0.50)
    merge_corpus(first_corpus, second_corpus)
    ledger = tmp_path / "ledger.duckdb"
    result = ingest_corpus(corpus_root=first_corpus, ledger_path=ledger)
    assert result.conflicts == 2
    assert counts(ledger)["observations"] == 2


def test_mutated_immutable_entity_is_detected_on_incremental_run(tmp_path: Path) -> None:
    corpus, _ = corpus_with_receipt(tmp_path)
    ledger = tmp_path / "ledger.duckdb"
    ingest_corpus(corpus_root=corpus, ledger_path=ledger)
    intent_path = next((corpus / "intents").glob("*.json"))
    payload = json.loads(intent_path.read_text())
    payload["selection_reason"] = {"reason_codes": ["MUTATED"]}
    intent_path.write_text(json.dumps(payload), encoding="utf-8")
    result = ingest_corpus(corpus_root=corpus, ledger_path=ledger)
    assert result.conflicts == 1


def test_dangling_receipt_is_quarantined_without_rolling_back_valid_specs(tmp_path: Path) -> None:
    corpus, _ = corpus_with_receipt(tmp_path)
    next((corpus / "intents").glob("*.json")).unlink()
    ledger = tmp_path / "ledger.duckdb"
    result = ingest_corpus(corpus_root=corpus, ledger_path=ledger)
    assert result.rejections >= 1
    assert counts(ledger)["trial_specs"] == 2
    assert counts(ledger)["run_attempts"] == 0
    assert counts(ledger)["run_receipts"] == 0


def test_intent_with_missing_trial_spec_is_quarantined(tmp_path: Path) -> None:
    corpus, _ = corpus_with_receipt(tmp_path)
    next((corpus / "trial_specs").glob("*.json")).unlink()
    ledger = tmp_path / "ledger.duckdb"
    result = ingest_corpus(corpus_root=corpus, ledger_path=ledger)
    assert result.rejections >= 2
    assert counts(ledger)["research_intents"] == 0
    assert counts(ledger)["run_attempts"] == 0


def test_attempt_trial_set_must_equal_intent(tmp_path: Path) -> None:
    corpus, _ = corpus_with_receipt(tmp_path)
    attempt_path = next((corpus / "attempts").glob("*.json"))
    payload = json.loads(attempt_path.read_text())
    payload["requested_trial_spec_ids"] = payload["requested_trial_spec_ids"][:1]
    payload["attempt_event_id"] = "sha256:" + "0" * 64
    from app.research.contracts import content_hash

    payload["attempt_event_id"] = content_hash(payload, omit={"attempt_event_id"})
    attempt_path.write_text(json.dumps(payload), encoding="utf-8")
    ledger = tmp_path / "ledger.duckdb"
    result = ingest_corpus(corpus_root=corpus, ledger_path=ledger)
    assert result.rejections >= 1
    assert counts(ledger)["run_attempts"] == 0


def test_wrong_canonical_entity_filename_is_quarantined(tmp_path: Path) -> None:
    corpus, _ = corpus_with_receipt(tmp_path)
    intent = next((corpus / "intents").glob("*.json"))
    intent.rename(intent.with_name("wrong-intent.json"))
    result = ingest_corpus(corpus_root=corpus, ledger_path=tmp_path / "ledger.duckdb")
    assert result.rejections >= 1


def test_snapshot_is_stable_without_local_provenance_paths(tmp_path: Path) -> None:
    corpus, _ = corpus_with_receipt(tmp_path)
    ledger = tmp_path / "ledger.duckdb"
    ingest_corpus(corpus_root=corpus, ledger_path=ledger)
    connection = duckdb.connect(str(ledger))
    try:
        first = ledger_snapshot(connection)
        connection.execute("UPDATE run_artifacts SET provenance_path = '/another/machine/path'")
        second = ledger_snapshot(connection)
    finally:
        connection.close()
    assert first["snapshot_hash"] == second["snapshot_hash"]
