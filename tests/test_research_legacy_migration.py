from __future__ import annotations

import json
from pathlib import Path

from app.research.legacy_migration import LegacySource, build_migration
from app.research.observation_ingest import ingest_corpus
import duckdb


def write_matrix(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "schema_version": "backtest-strategy-matrix.v1",
        "scenarios": [{
            "scenario_id": "h5", "horizon": 5, "stop_loss_pct": 0.08,
            "take_profit_pct": 0.15, "max_group_exposure": 0.35,
            "total_return": 0.04, "max_drawdown": -0.1, "win_rate": 0.55,
            "avg_trade_return": 0.01, "trade_count": 20, "score": 0.2,
            "p_value": 0.04,
        }],
    }), encoding="utf-8")


def test_matrix_record_is_diagnostic_only_without_proven_lineage(tmp_path: Path) -> None:
    source = tmp_path / "legacy" / "matrix.json"
    write_matrix(source)
    result = build_migration(
        corpus_root=tmp_path / "corpus",
        sources=[LegacySource(source, "STRATEGY_MATRIX")],
    )
    record = result["records"][0]
    assert record["record_kind"] == "PARAMETER_RESULT"
    assert record["preliminary_classification"] == "LEGACY_DIAGNOSTIC_ONLY"
    assert record["parameters"]["regime_gate"] is None
    assert record["parameters"]["risk_guard"] is None
    assert record["parameters"]["entry_filter"] is None


def test_topic_level_and_unsupported_never_become_negative_observations(tmp_path: Path) -> None:
    source = tmp_path / "run_history.jsonl"
    source.write_text(
        json.dumps({"topic_id": "t1", "status": "REJECTED"}) + "\n"
        + json.dumps({
            "topic_id": "t2", "status": "UNSUPPORTED",
            "dimensions": {"horizon": "5", "stop_loss": "0.08", "take_profit": "0.15", "group_exposure": "0.35"},
        }) + "\n",
        encoding="utf-8",
    )
    result = build_migration(
        corpus_root=tmp_path / "corpus",
        sources=[LegacySource(source, "RUN_HISTORY_JSONL")],
    )
    assert [row["preliminary_classification"] for row in result["records"]] == [
        "TOPIC_LEVEL_NOT_PARAMETER_EVIDENCE", "UNSUPPORTED_NOT_AN_OBSERVATION"
    ]


def test_same_source_is_idempotent_and_content_addressed(tmp_path: Path) -> None:
    source = tmp_path / "matrix.json"
    write_matrix(source)
    kwargs = {
        "corpus_root": tmp_path / "corpus",
        "sources": [LegacySource(source, "STRATEGY_MATRIX")],
    }
    first = build_migration(**kwargs)
    second = build_migration(**kwargs)
    assert first["manifest"]["migration_id"] == second["manifest"]["migration_id"]
    entry = first["manifest"]["sources"][0]
    assert (kwargs["corpus_root"] / entry["corpus_artifact_path"]).is_file()
    assert (kwargs["corpus_root"] / entry["record_mapping_path"]).is_file()


def test_source_path_does_not_change_record_semantic_identity(tmp_path: Path) -> None:
    first = tmp_path / "a" / "matrix.json"
    second = tmp_path / "b" / "copy.json"
    write_matrix(first)
    second.parent.mkdir(parents=True)
    second.write_bytes(first.read_bytes())
    result = build_migration(
        corpus_root=tmp_path / "corpus",
        sources=[LegacySource(first, "STRATEGY_MATRIX"), LegacySource(second, "STRATEGY_MATRIX")],
    )
    assert len({record["semantic_evidence_id"] for record in result["records"]}) == 1
    assert len({entry["source_artifact_hash"] for entry in result["manifest"]["sources"]}) == 1


def test_migration_manifest_ingests_and_rebuilds_idempotently(tmp_path: Path) -> None:
    source = tmp_path / "matrix.json"
    write_matrix(source)
    corpus = tmp_path / "corpus"
    build_migration(
        corpus_root=corpus,
        sources=[LegacySource(source, "STRATEGY_MATRIX")],
    )
    ledger = tmp_path / "ledger.duckdb"
    first = ingest_corpus(corpus_root=corpus, ledger_path=ledger)
    second = ingest_corpus(corpus_root=corpus, ledger_path=ledger)
    rebuilt = ingest_corpus(corpus_root=corpus, ledger_path=ledger, rebuild=True)
    assert first.snapshot_hash == second.snapshot_hash == rebuilt.snapshot_hash
    connection = duckdb.connect(str(ledger), read_only=True)
    try:
        assert connection.execute("SELECT count(*) FROM migration_manifests").fetchone()[0] == 1
        assert connection.execute("SELECT count(*) FROM migrated_records").fetchone()[0] == 1
        status = connection.execute(
            "SELECT preliminary_classification FROM migrated_records"
        ).fetchone()[0]
    finally:
        connection.close()
    assert status == "LEGACY_DIAGNOSTIC_ONLY"


def test_mixed_scalar_record_is_counted_as_excluded(tmp_path: Path) -> None:
    source = tmp_path / "run_history.jsonl"
    source.write_text("42\n" + json.dumps({"topic_id": "t"}) + "\n", encoding="utf-8")
    result = build_migration(
        corpus_root=tmp_path / "corpus",
        sources=[LegacySource(source, "RUN_HISTORY_JSONL")],
    )
    counts = result["manifest"]["sources"][0]["record_counts"]
    assert counts == {"seen": 2, "mapped": 1, "excluded": 1}


def test_tampered_mapping_is_rejected_even_after_ingest(tmp_path: Path) -> None:
    source = tmp_path / "matrix.json"
    write_matrix(source)
    corpus = tmp_path / "corpus"
    result = build_migration(
        corpus_root=corpus,
        sources=[LegacySource(source, "STRATEGY_MATRIX")],
    )
    ledger = tmp_path / "ledger.duckdb"
    ingest_corpus(corpus_root=corpus, ledger_path=ledger)
    mapping = corpus / result["manifest"]["sources"][0]["record_mapping_path"]
    mapping.unlink()
    mapping.write_text("CORRUPT\n", encoding="utf-8")
    import pytest

    with pytest.raises(ValueError, match="MIGRATION_MAPPING_HASH_MISMATCH"):
        ingest_corpus(corpus_root=corpus, ledger_path=ledger)


def test_migrated_record_cannot_claim_adaptive_eligible(tmp_path: Path) -> None:
    source = tmp_path / "matrix.json"
    write_matrix(source)
    corpus = tmp_path / "corpus"
    result = build_migration(
        corpus_root=corpus,
        sources=[LegacySource(source, "STRATEGY_MATRIX")],
    )
    mapping = corpus / result["manifest"]["sources"][0]["record_mapping_path"]
    record = json.loads(mapping.read_text())
    record["preliminary_classification"] = "ADAPTIVE_ELIGIBLE"
    from app.research.contracts import validate_migrated_record

    assert "preliminary_classification is invalid" in validate_migrated_record(record)


def test_declared_sealed_matrix_is_validation_only(tmp_path: Path) -> None:
    source = tmp_path / "sealed.json"
    write_matrix(source)
    payload = json.loads(source.read_text())
    payload["contract"] = {
        "research_stage": "SEALED_VALIDATION",
        "sealed_data_read_allowed": True,
    }
    source.write_text(json.dumps(payload), encoding="utf-8")
    result = build_migration(
        corpus_root=tmp_path / "corpus",
        sources=[LegacySource(source, "STRATEGY_MATRIX")],
    )
    assert result["records"][0]["preliminary_classification"] == "SEALED_VALIDATION_ONLY"


def test_semantic_duplicate_is_deweighted_and_conflict_is_quarantined(tmp_path: Path) -> None:
    first = tmp_path / "a.json"
    duplicate = tmp_path / "b.json"
    conflict = tmp_path / "c.json"
    write_matrix(first)
    duplicate.write_text(json.dumps(json.loads(first.read_text()), indent=4), encoding="utf-8")
    conflict_payload = json.loads(first.read_text())
    conflict_payload["scenarios"][0]["score"] = 9.9
    conflict.write_text(json.dumps(conflict_payload), encoding="utf-8")
    corpus = tmp_path / "corpus"
    build_migration(
        corpus_root=corpus,
        sources=[
            LegacySource(first, "STRATEGY_MATRIX"),
            LegacySource(duplicate, "STRATEGY_MATRIX"),
            LegacySource(conflict, "STRATEGY_MATRIX"),
        ],
    )
    ledger = tmp_path / "ledger.duckdb"
    ingest_corpus(corpus_root=corpus, ledger_path=ledger)
    connection = duckdb.connect(str(ledger), read_only=True)
    try:
        semantic_count, status, weight = connection.execute(
            "SELECT count(*), min(conflict_status), min(evidence_weight) "
            "FROM legacy_semantic_evidence"
        ).fetchone()
        provenance_count = connection.execute(
            "SELECT count(*) FROM legacy_semantic_provenance"
        ).fetchone()[0]
    finally:
        connection.close()
    assert semantic_count == 1
    assert status == "CONFLICTED"
    assert weight == 0
    assert provenance_count == 3


def test_incremental_manifests_preserve_many_to_many_record_attribution(tmp_path: Path) -> None:
    first = tmp_path / "a.json"
    second = tmp_path / "b.json"
    write_matrix(first)
    write_matrix(second)
    second_payload = json.loads(second.read_text())
    second_payload["scenarios"][0]["scenario_id"] = "h5-second"
    second.write_text(json.dumps(second_payload), encoding="utf-8")
    corpus = tmp_path / "corpus"
    one = build_migration(
        corpus_root=corpus,
        sources=[LegacySource(first, "STRATEGY_MATRIX")],
    )
    two = build_migration(
        corpus_root=corpus,
        sources=[
            LegacySource(first, "STRATEGY_MATRIX"),
            LegacySource(second, "STRATEGY_MATRIX"),
        ],
    )
    ledger = tmp_path / "ledger.duckdb"
    first_ingest = ingest_corpus(corpus_root=corpus, ledger_path=ledger)
    rebuilt = ingest_corpus(corpus_root=corpus, ledger_path=ledger, rebuild=True)
    connection = duckdb.connect(str(ledger), read_only=True)
    try:
        counts = dict(connection.execute(
            "SELECT migration_id, count(*) FROM migration_manifest_records GROUP BY migration_id"
        ).fetchall())
        record_count = connection.execute("SELECT count(*) FROM migrated_records").fetchone()[0]
    finally:
        connection.close()
    assert counts[one["manifest"]["migration_id"]] == 1
    assert counts[two["manifest"]["migration_id"]] == 2
    assert record_count == 2
    assert first_ingest.snapshot_hash == rebuilt.snapshot_hash
