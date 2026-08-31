from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from app.research.contracts import CANONICALIZATION_VERSION, content_hash, validate_migrated_record
from app.research.legacy_migration import LegacySource, build_migration
from app.research.observation_ingest import ingest_corpus
import duckdb


def canonical_trial() -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "research-trial-spec.v1",
        "canonicalization_version": CANONICALIZATION_VERSION,
        "trial_spec_id": "sha256:" + "0" * 64,
        "topic_id": "topic-a",
        "topic_family_id": "topic-family-a",
        "parameter_catalog_version": "research-parameter-catalog.v1",
        "parameter_catalog_hash": "sha256:" + "1" * 64,
        "parameters": {
            "horizon": 5, "stop_loss_pct": 0.08, "take_profit_pct": 0.15,
            "max_group_exposure": 0.35, "regime_gate": None,
            "risk_guard": None, "entry_filter": None,
        },
        "research_stage": "DEVELOPMENT_SCREEN",
        "regime_scope": {"regime_id": "RISK_OFF|"},
        "dataset_authority": {"dataset_hash": "sha256:" + "2" * 64},
        "ranking_source_authority": {"ranking_source_hash": "sha256:" + "3" * 64},
        "execution_profile": {"runner": "strategy_matrix", "profile": "exact_trial"},
        "safety": {
            "does_not_train_model": True,
            "does_not_change_production_ranking": True,
            "production_promotion_allowed": False,
        },
    }
    payload["trial_spec_id"] = content_hash(payload, omit={"trial_spec_id"})
    return payload


def publish_trial(corpus: Path, trial: dict[str, object]) -> None:
    path = corpus / "trial_specs" / f"{str(trial['trial_spec_id'])[7:]}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(trial), encoding="utf-8")


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


def test_declared_sealed_matrix_without_canonical_target_is_diagnostic_only(tmp_path: Path) -> None:
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
    assert result["records"][0]["preliminary_classification"] == "LEGACY_DIAGNOSTIC_ONLY"
    assert result["records"][0]["migration_disposition"] == "LEGACY_INCOMPLETE"


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


def test_every_row_has_one_independent_disposition_envelope(tmp_path: Path) -> None:
    source = tmp_path / "run_history.jsonl"
    source.write_text(
        "42\n" + json.dumps({"topic_id": "topic-only"}) + "\n",
        encoding="utf-8",
    )
    result = build_migration(
        corpus_root=tmp_path / "corpus",
        sources=[LegacySource(source, "RUN_HISTORY_JSONL")],
    )
    records = result["records"]
    assert len(records) == 2
    assert {record["migration_disposition"] for record in records} == {
        "EXCLUDED_NON_RESEARCH", "LEGACY_INCOMPLETE"
    }
    assert records[0]["record_kind"] != records[0]["migration_disposition"]
    assert all(record["reason_codes"] and record["evidence_refs"] for record in records)
    source_entry = result["manifest"]["sources"][0]
    assert sum(source_entry["disposition_counts"].values()) == 2
    assert source_entry["record_counts"] == {"seen": 2, "mapped": 1, "excluded": 1}
    assert source_entry["artifact_disposition_record"]["record_locator"] == "$artifact"


def test_exact_and_inferred_require_validated_canonical_target_evidence(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    trial = canonical_trial()
    publish_trial(corpus, trial)
    source = tmp_path / "run_history.jsonl"
    base = {
        "combo_id": "legacy-combo", "topic_id": "topic-a", "horizon": 5,
        "stop_loss_pct": 0.08, "take_profit_pct": 0.15,
        "max_group_exposure": 0.35, "score": 0.2,
    }
    exact = {
        **base,
        "migration_evidence": {
            "mapping_mode": "EXACT", "confidence": "EXACT",
            "reason_codes": ["DIRECT_A1_TRIAL_SPEC_BINDING"],
            "evidence_refs": [trial["trial_spec_id"]],
            "candidates": [{
                "combo_id": "legacy-combo", "canonical_trial_spec_id": trial["trial_spec_id"],
                "reason_codes": ["DIRECT_A1_TRIAL_SPEC_BINDING"],
                "evidence_refs": [trial["trial_spec_id"]],
            }],
        },
    }
    inferred = deepcopy(exact)
    inferred["combo_id"] = "legacy-inferred"
    inferred["migration_evidence"]["mapping_mode"] = "INFERRED"
    inferred["migration_evidence"]["confidence"] = "HIGH"
    inferred["migration_evidence"]["reason_codes"] = ["VERSIONED_DETERMINISTIC_POLICY_MATCH"]
    inferred["migration_evidence"]["candidates"][0]["combo_id"] = "legacy-inferred"
    inferred["migration_evidence"]["candidates"][0]["reason_codes"] = [
        "VERSIONED_DETERMINISTIC_POLICY_MATCH"
    ]
    source.write_text(json.dumps(exact) + "\n" + json.dumps(inferred) + "\n", encoding="utf-8")
    result = build_migration(corpus_root=corpus, sources=[LegacySource(source, "RUN_HISTORY_JSONL")])
    assert [row["migration_disposition"] for row in result["records"]] == [
        "MIGRATED_EXACT", "MIGRATED_INFERRED"
    ]
    assert result["records"][1]["preliminary_classification"] == "LEGACY_DIAGNOSTIC_ONLY"
    assert result["records"][0]["combo_mapping"]["cardinality"] == "ONE"


def test_ambiguous_candidates_are_sorted_and_never_choose_winner(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    first = canonical_trial()
    second = deepcopy(first)
    second["dataset_authority"] = {"dataset_hash": "sha256:" + "4" * 64}
    second["trial_spec_id"] = content_hash(second, omit={"trial_spec_id"})
    publish_trial(corpus, first)
    publish_trial(corpus, second)
    candidates = [
        {
            "combo_id": "z", "canonical_trial_spec_id": second["trial_spec_id"],
            "reason_codes": ["AMBIGUOUS_CANONICAL_TARGET"],
            "evidence_refs": [second["trial_spec_id"]],
        },
        {
            "combo_id": "a", "canonical_trial_spec_id": first["trial_spec_id"],
            "reason_codes": ["AMBIGUOUS_CANONICAL_TARGET"],
            "evidence_refs": [first["trial_spec_id"]],
        },
    ]
    row = {
        "topic_id": "topic-a", "horizon": 5, "stop_loss_pct": 0.08,
        "take_profit_pct": 0.15, "max_group_exposure": 0.35, "score": 0.2,
        "migration_evidence": {
            "mapping_mode": "INFERRED", "confidence": "LOW",
            "reason_codes": ["AMBIGUOUS_CANONICAL_TARGET"],
            "evidence_refs": [first["trial_spec_id"], second["trial_spec_id"]],
            "candidates": candidates,
        },
    }
    source = tmp_path / "run_history.jsonl"
    source.write_text(json.dumps(row) + "\n", encoding="utf-8")
    record = build_migration(
        corpus_root=corpus, sources=[LegacySource(source, "RUN_HISTORY_JSONL")]
    )["records"][0]
    assert record["migration_disposition"] == "LEGACY_UNRESOLVED"
    assert record["combo_mapping"]["mapping_status"] == "AMBIGUOUS_NO_WINNER"
    assert record["combo_mapping"]["cardinality"] == "ONE_TO_MANY"
    assert [edge["combo_id"] for edge in record["combo_mapping"]["candidates"]] == ["a", "z"]
    row["migration_evidence"]["mapping_mode"] = "EXACT"
    row["migration_evidence"]["confidence"] = "EXACT"
    row["migration_evidence"]["multi_target_resolution"] = "ALL_TARGETS_PROVEN"
    row["migration_evidence"]["reason_codes"] = ["DIRECT_MULTI_TARGET_BINDING"]
    for candidate in row["migration_evidence"]["candidates"]:
        candidate["reason_codes"] = ["DIRECT_MULTI_TARGET_BINDING"]
    source.write_text(json.dumps(row) + "\n", encoding="utf-8")
    resolved = build_migration(
        corpus_root=corpus, sources=[LegacySource(source, "RUN_HISTORY_JSONL")]
    )["records"][0]
    assert resolved["migration_disposition"] == "MIGRATED_EXACT"
    assert resolved["combo_mapping"]["mapping_status"] == "RESOLVED_ONE_TO_MANY"
    assert resolved["combo_mapping"]["cardinality"] == "ONE_TO_MANY"


def test_disposition_validator_rejects_axis_and_evidence_mismatch(tmp_path: Path) -> None:
    source = tmp_path / "matrix.json"
    write_matrix(source)
    record = build_migration(
        corpus_root=tmp_path / "corpus", sources=[LegacySource(source, "STRATEGY_MATRIX")]
    )["records"][0]
    tampered = deepcopy(record)
    tampered["migration_disposition"] = "MIGRATED_EXACT"
    tampered["confidence"] = "LOW"
    errors = validate_migrated_record(tampered)
    assert "MIGRATED_EXACT requires EXACT confidence" in errors
    assert any("combo_mapping" in error for error in errors)


def test_quality_report_reconciles_counts_and_ingest_rejects_tamper_atomically(tmp_path: Path) -> None:
    source = tmp_path / "run_history.jsonl"
    source.write_text("42\n" + json.dumps({"topic_id": "t"}) + "\n", encoding="utf-8")
    corpus = tmp_path / "corpus"
    result = build_migration(corpus_root=corpus, sources=[LegacySource(source, "RUN_HISTORY_JSONL")])
    report = result["quality_report"]
    assert report["totals"]["rows_seen"] == 2
    assert report["totals"]["new_migrated_records"] + report["totals"][
        "excluded_disposition_records"
    ] == 2
    assert report["totals"]["unexplained_delta"] == 0
    ledger = tmp_path / "ledger.duckdb"
    ingest_corpus(corpus_root=corpus, ledger_path=ledger)
    before = duckdb.connect(str(ledger), read_only=True)
    try:
        before_count = before.execute("SELECT count(*) FROM migration_manifests").fetchone()[0]
    finally:
        before.close()
    report_path = corpus / result["manifest"]["quality_report_path"]
    report_path.unlink()
    report_path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="MIGRATION_QUALITY_REPORT_HASH_MISMATCH"):
        ingest_corpus(corpus_root=corpus, ledger_path=ledger)
    after = duckdb.connect(str(ledger), read_only=True)
    try:
        assert after.execute("SELECT count(*) FROM migration_manifests").fetchone()[0] == before_count
    finally:
        after.close()


def test_empty_inventory_has_zero_reconciled_quality_report(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    result = build_migration(corpus_root=corpus, sources=[])
    assert result["manifest"]["sources"] == []
    assert result["quality_report"]["totals"]["rows_seen"] == 0
    assert result["quality_report"]["totals"]["unexplained_delta"] == 0
    ingest_corpus(corpus_root=corpus, ledger_path=tmp_path / "ledger.duckdb")
