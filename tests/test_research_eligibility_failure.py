from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest

import app.research.eligibility as eligibility_module
import app.research.failure_classification as failure_module
from app.research.contracts import content_hash
from app.research.eligibility import build_projection as build_eligibility, load_policy as load_eligibility_policy
from app.research.failure_classification import build_projection as build_failure, classify_metrics, load_policy
from app.research.legacy_migration import LegacySource, build_migration
from app.research.native_evidence_replay import verify_bundle
from app.research.observation_ingest import ingest_corpus
from app.research.run_receipts import finish_topic_attempt
from app.research.receipt_store import ImmutableCollisionError
from scripts.verify_research_spine_batch import verify_projection_rebuild
from tests.test_autonomous_research_receipts import begin
from tests.test_research_ledger import corpus_with_receipt
from tests.test_research_legacy_migration import write_matrix


def migration_ledger(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "matrix.json"
    write_matrix(source)
    corpus = tmp_path / "corpus"
    build_migration(
        corpus_root=corpus,
        sources=[LegacySource(source, "STRATEGY_MATRIX")],
    )
    ledger = tmp_path / "ledger.duckdb"
    ingest_corpus(corpus_root=corpus, ledger_path=ledger)
    return ledger, tmp_path / "eligibility"


def commit_failing_duckdb(real_connect: object) -> SimpleNamespace:
    class CommitFailConnection:
        def __init__(self, connection: object) -> None:
            self.connection = connection

        def execute(self, query: str, *args: object, **kwargs: object) -> object:
            if query == "COMMIT":
                raise RuntimeError("COMMIT_FAILURE")
            return self.connection.execute(query, *args, **kwargs)

        def __getattr__(self, name: str) -> object:
            return getattr(self.connection, name)

    def connect(*args: object, **kwargs: object) -> CommitFailConnection:
        return CommitFailConnection(real_connect(*args, **kwargs))

    return SimpleNamespace(connect=connect)


def test_valid_development_observations_are_eligible_and_reproducible(tmp_path: Path) -> None:
    corpus, _ = corpus_with_receipt(tmp_path)
    ledger = tmp_path / "ledger.duckdb"
    ingest_corpus(corpus_root=corpus, ledger_path=ledger)
    output = tmp_path / "projections" / "eligibility"
    first = build_eligibility(ledger_path=ledger, output_root=output)
    second = build_eligibility(ledger_path=ledger, output_root=output)
    assert first["projection_id"] == second["projection_id"]
    assert first["counts"] == {"ADAPTIVE_ELIGIBLE": 2}
    assert all(item["evidence_weight"] == 1 for item in first["decisions"])


def test_clean_delete_rebuild_reproduces_projection_artifacts_exactly(
    tmp_path: Path,
) -> None:
    corpus, _ = corpus_with_receipt(tmp_path / "source")
    result = verify_projection_rebuild(corpus_root=corpus)
    assert result["status"] == "PASS"
    assert all(result["checks"].values())


def test_v2_rebuild_preserves_generated_at_v1_artifacts_side_by_side(
    tmp_path: Path,
) -> None:
    corpus, _ = corpus_with_receipt(tmp_path)
    ledger = tmp_path / "ledger.duckdb"
    ingest_corpus(corpus_root=corpus, ledger_path=ledger)
    eligibility_root = tmp_path / "eligibility"
    failure_root = tmp_path / "failure"
    first_failure = build_failure(
        ledger_path=ledger,
        eligibility_output_root=eligibility_root,
        output_root=failure_root,
    )
    first_eligibility = json.loads(
        (eligibility_root / f"{first_failure['eligibility_projection_id'][7:]}.json")
        .read_text(encoding="utf-8")
    )

    old_eligibility = json.loads(json.dumps(first_eligibility))
    old_eligibility["schema_version"] = "research-eligibility-projection.v1"
    old_eligibility["projection_schema_version"] = "research-eligibility-projection.v1"
    eligibility_identity = {
        key: old_eligibility[key]
        for key in (
            "projection_schema_version", "input_corpus_hash", "ledger_snapshot_hash",
            "policy_version", "policy_hash", "parameter_catalog_hash",
            "canonicalization_version", "activation_exclusion_policy_version",
            "activation_exclusion_policy_hash",
        )
    }
    old_eligibility["projection_id"] = content_hash(eligibility_identity)
    old_eligibility["generated_at"] = "2026-08-31T00:00:00+00:00"
    old_eligibility_path = eligibility_root / f"{old_eligibility['projection_id'][7:]}.json"
    old_eligibility_path.write_text(
        json.dumps(old_eligibility, sort_keys=True) + "\n", encoding="utf-8"
    )

    old_failure = json.loads(json.dumps(first_failure))
    old_failure["schema_version"] = "research-failure-projection.v1"
    old_failure["projection_schema_version"] = "research-failure-projection.v1"
    old_failure["eligibility_projection_id"] = old_eligibility["projection_id"]
    failure_identity = {
        key: old_failure[key]
        for key in (
            "projection_schema_version", "eligibility_projection_id",
            "policy_version", "policy_hash",
        )
    }
    old_failure["projection_id"] = content_hash(failure_identity)
    old_failure["generated_at"] = "2026-08-31T00:00:00+00:00"
    old_failure_path = failure_root / f"{old_failure['projection_id'][7:]}.json"
    old_failure_path.write_text(json.dumps(old_failure, sort_keys=True) + "\n", encoding="utf-8")
    old_bytes = (old_eligibility_path.read_bytes(), old_failure_path.read_bytes())

    second_failure = build_failure(
        ledger_path=ledger,
        eligibility_output_root=eligibility_root,
        output_root=failure_root,
    )

    assert first_eligibility["schema_version"] == "research-eligibility-projection.v2"
    assert first_failure["schema_version"] == "research-failure-projection.v2"
    assert second_failure == first_failure
    assert old_eligibility_path.read_bytes() == old_bytes[0]
    assert old_failure_path.read_bytes() == old_bytes[1]


@pytest.mark.parametrize("tamper", ["counts", "projection_id", "activation_ref"])
def test_tampered_eligibility_artifact_is_rejected(
    tmp_path: Path, tamper: str,
) -> None:
    corpus, _ = corpus_with_receipt(tmp_path)
    ledger = tmp_path / "ledger.duckdb"
    ingest_corpus(corpus_root=corpus, ledger_path=ledger)
    output = tmp_path / "eligibility"
    first = build_eligibility(ledger_path=ledger, output_root=output)
    target = output / f"{first['projection_id'][7:]}.json"
    tampered = json.loads(target.read_text(encoding="utf-8"))
    if tamper == "counts":
        tampered["counts"] = {}
    elif tamper == "projection_id":
        tampered["projection_id"] = "sha256:" + "0" * 64
    else:
        tampered["activation_exclusions"]["policy_hash"] = "sha256:" + "0" * 64
    target.write_text(json.dumps(tampered), encoding="utf-8")

    with pytest.raises(ValueError, match="ELIGIBILITY_PROJECTION_COLLISION"):
        build_eligibility(ledger_path=ledger, output_root=output)


@pytest.mark.parametrize("tamper", ["classifications", "projection_id", "eligibility_ref"])
def test_tampered_failure_artifact_is_rejected(tmp_path: Path, tamper: str) -> None:
    corpus, _ = corpus_with_receipt(tmp_path, total_return=-0.08)
    ledger = tmp_path / "ledger.duckdb"
    ingest_corpus(corpus_root=corpus, ledger_path=ledger)
    eligibility_root = tmp_path / "eligibility"
    output = tmp_path / "failure"
    first = build_failure(
        ledger_path=ledger,
        eligibility_output_root=eligibility_root,
        output_root=output,
    )
    target = output / f"{first['projection_id'][7:]}.json"
    tampered = json.loads(target.read_text(encoding="utf-8"))
    if tamper == "classifications":
        tampered["classifications"] = []
    elif tamper == "projection_id":
        tampered["projection_id"] = "sha256:" + "0" * 64
    else:
        tampered["eligibility_projection_id"] = "sha256:" + "0" * 64
    target.write_text(json.dumps(tampered), encoding="utf-8")

    with pytest.raises(ValueError, match="FAILURE_PROJECTION_COLLISION"):
        build_failure(
            ledger_path=ledger,
            eligibility_output_root=eligibility_root,
            output_root=output,
        )


def test_projection_db_row_collision_fails_without_partial_write(tmp_path: Path) -> None:
    corpus, _ = corpus_with_receipt(tmp_path)
    ledger = tmp_path / "ledger.duckdb"
    ingest_corpus(corpus_root=corpus, ledger_path=ledger)
    output = tmp_path / "eligibility"
    first = build_eligibility(ledger_path=ledger, output_root=output)
    connection = duckdb.connect(str(ledger))
    try:
        subject_id = connection.execute(
            "SELECT subject_id FROM eligibility_decisions WHERE projection_id=? ORDER BY subject_id LIMIT 1",
            [first["projection_id"]],
        ).fetchone()[0]
        connection.execute(
            "UPDATE eligibility_decisions SET evidence_weight=0 WHERE projection_id=? AND subject_id=?",
            [first["projection_id"], subject_id],
        )
        before = connection.execute(
            "SELECT * FROM eligibility_decisions WHERE projection_id=? ORDER BY subject_type,subject_id",
            [first["projection_id"]],
        ).fetchall()
    finally:
        connection.close()

    collision_output = tmp_path / "eligibility-collision"
    collision_target = collision_output / f"{first['projection_id'][7:]}.json"
    with pytest.raises(ValueError, match="ELIGIBILITY_DB_PROJECTION_COLLISION"):
        build_eligibility(ledger_path=ledger, output_root=collision_output)
    assert not collision_target.exists()

    connection = duckdb.connect(str(ledger), read_only=True)
    try:
        after = connection.execute(
            "SELECT * FROM eligibility_decisions WHERE projection_id=? ORDER BY subject_type,subject_id",
            [first["projection_id"]],
        ).fetchall()
    finally:
        connection.close()
    assert after == before


def test_eligibility_write_failure_rolls_back_db_and_new_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    corpus, _ = corpus_with_receipt(tmp_path)
    ledger = tmp_path / "ledger.duckdb"
    ingest_corpus(corpus_root=corpus, ledger_path=ledger)
    output = tmp_path / "eligibility"
    real_connect = eligibility_module.duckdb.connect
    monkeypatch.setattr(eligibility_module, "duckdb", commit_failing_duckdb(real_connect))
    with pytest.raises(RuntimeError, match="COMMIT_FAILURE"):
        build_eligibility(ledger_path=ledger, output_root=output)

    assert list(output.glob("*.json")) == []
    connection = duckdb.connect(str(ledger), read_only=True)
    try:
        assert connection.execute("SELECT count(*) FROM eligibility_projection_runs").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM eligibility_decisions").fetchone()[0] == 0
    finally:
        connection.close()


def test_eligibility_collision_preserves_concurrent_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    corpus, _ = corpus_with_receipt(tmp_path)
    ledger = tmp_path / "ledger.duckdb"
    ingest_corpus(corpus_root=corpus, ledger_path=ledger)
    output = tmp_path / "eligibility"
    concurrent_bytes = b'{"concurrent_writer":true}\n'
    real_write = eligibility_module.write_immutable_json

    def concurrent_then_write(target: Path, *args: object, **kwargs: object) -> object:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(concurrent_bytes)
        return real_write(target, *args, **kwargs)

    monkeypatch.setattr(eligibility_module, "write_immutable_json", concurrent_then_write)
    with pytest.raises(ImmutableCollisionError):
        build_eligibility(ledger_path=ledger, output_root=output)

    targets = list(output.glob("*.json"))
    assert len(targets) == 1
    assert targets[0].read_bytes() == concurrent_bytes
    connection = duckdb.connect(str(ledger), read_only=True)
    try:
        assert connection.execute("SELECT count(*) FROM eligibility_projection_runs").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM eligibility_decisions").fetchone()[0] == 0
    finally:
        connection.close()


def test_missing_legacy_decision_is_a_db_projection_collision(tmp_path: Path) -> None:
    ledger, output = migration_ledger(tmp_path)
    first = build_eligibility(ledger_path=ledger, output_root=output)
    connection = duckdb.connect(str(ledger))
    try:
        connection.execute(
            "DELETE FROM eligibility_decisions WHERE projection_id=? "
            "AND subject_type='MIGRATED_RECORD'",
            [first["projection_id"]],
        )
    finally:
        connection.close()

    with pytest.raises(ValueError, match="ELIGIBILITY_DB_PROJECTION_COLLISION"):
        build_eligibility(ledger_path=ledger, output_root=output)


def test_missing_legacy_reason_is_a_db_projection_collision(tmp_path: Path) -> None:
    ledger, output = migration_ledger(tmp_path)
    first = build_eligibility(ledger_path=ledger, output_root=output)
    connection = duckdb.connect(str(ledger))
    try:
        connection.execute(
            "DELETE FROM eligibility_reason_codes WHERE projection_id=? "
            "AND subject_type='MIGRATED_RECORD'",
            [first["projection_id"]],
        )
    finally:
        connection.close()

    with pytest.raises(ValueError, match="ELIGIBILITY_DB_PROJECTION_COLLISION"):
        build_eligibility(ledger_path=ledger, output_root=output)


def test_no_run_legacy_orphan_rows_fail_before_artifact_publication(
    tmp_path: Path,
) -> None:
    ledger, output = migration_ledger(tmp_path)
    first = build_eligibility(ledger_path=ledger, output_root=output)
    target = output / f"{first['projection_id'][7:]}.json"
    target.unlink()
    connection = duckdb.connect(str(ledger))
    try:
        connection.execute(
            "DELETE FROM eligibility_projection_runs WHERE projection_id=?",
            [first["projection_id"]],
        )
        connection.execute(
            "DELETE FROM eligibility_decisions WHERE projection_id=?",
            [first["projection_id"]],
        )
        connection.execute(
            "DELETE FROM eligibility_reason_codes WHERE projection_id=?",
            [first["projection_id"]],
        )
        connection.execute(
            "INSERT INTO eligibility_decisions VALUES (?,?,?,?,?,?)",
            [first["projection_id"], "MIGRATED_RECORD", "orphan", "INVALID_LINEAGE", 0,
             "sha256:" + "0" * 64],
        )
    finally:
        connection.close()

    with pytest.raises(ValueError, match="ELIGIBILITY_DB_PROJECTION_COLLISION"):
        build_eligibility(ledger_path=ledger, output_root=output)
    assert not target.exists()


def test_failure_projection_db_collision_fails_loudly(tmp_path: Path) -> None:
    corpus, _ = corpus_with_receipt(tmp_path)
    ledger = tmp_path / "ledger.duckdb"
    ingest_corpus(corpus_root=corpus, ledger_path=ledger)
    kwargs = {
        "ledger_path": ledger,
        "eligibility_output_root": tmp_path / "eligibility",
        "output_root": tmp_path / "failure",
    }
    first = build_failure(**kwargs)
    connection = duckdb.connect(str(ledger))
    try:
        connection.execute(
            "UPDATE failure_projection_runs SET canonical_payload_hash=? WHERE projection_id=?",
            ["sha256:" + "0" * 64, first["projection_id"]],
        )
        before = connection.execute(
            "SELECT * FROM failure_projection_runs WHERE projection_id=?",
            [first["projection_id"]],
        ).fetchall()
    finally:
        connection.close()

    collision_kwargs = {**kwargs, "output_root": tmp_path / "failure-collision"}
    collision_target = collision_kwargs["output_root"] / f"{first['projection_id'][7:]}.json"
    with pytest.raises(ValueError, match="FAILURE_DB_PROJECTION_COLLISION"):
        build_failure(**collision_kwargs)
    assert not collision_target.exists()
    connection = duckdb.connect(str(ledger), read_only=True)
    try:
        after = connection.execute(
            "SELECT * FROM failure_projection_runs WHERE projection_id=?",
            [first["projection_id"]],
        ).fetchall()
    finally:
        connection.close()
    assert after == before


def test_failure_write_failure_rolls_back_db_and_new_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    corpus, _ = corpus_with_receipt(tmp_path)
    ledger = tmp_path / "ledger.duckdb"
    ingest_corpus(corpus_root=corpus, ledger_path=ledger)
    eligibility_root = tmp_path / "eligibility"
    build_eligibility(ledger_path=ledger, output_root=eligibility_root)
    output = tmp_path / "failure"
    real_connect = failure_module.duckdb.connect
    monkeypatch.setattr(failure_module, "duckdb", commit_failing_duckdb(real_connect))
    with pytest.raises(RuntimeError, match="COMMIT_FAILURE"):
        build_failure(
            ledger_path=ledger,
            eligibility_output_root=eligibility_root,
            output_root=output,
        )

    assert list(output.glob("*.json")) == []
    connection = duckdb.connect(str(ledger), read_only=True)
    try:
        assert connection.execute("SELECT count(*) FROM failure_projection_runs").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM failure_classifications").fetchone()[0] == 0
    finally:
        connection.close()


def test_failure_collision_preserves_concurrent_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    corpus, _ = corpus_with_receipt(tmp_path)
    ledger = tmp_path / "ledger.duckdb"
    ingest_corpus(corpus_root=corpus, ledger_path=ledger)
    eligibility_root = tmp_path / "eligibility"
    build_eligibility(ledger_path=ledger, output_root=eligibility_root)
    output = tmp_path / "failure"
    concurrent_bytes = b'{"concurrent_writer":true}\n'
    real_write = failure_module.write_immutable_json

    def concurrent_then_write(target: Path, *args: object, **kwargs: object) -> object:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(concurrent_bytes)
        return real_write(target, *args, **kwargs)

    monkeypatch.setattr(failure_module, "write_immutable_json", concurrent_then_write)
    with pytest.raises(ImmutableCollisionError):
        build_failure(
            ledger_path=ledger,
            eligibility_output_root=eligibility_root,
            output_root=output,
        )

    targets = list(output.glob("*.json"))
    assert len(targets) == 1
    assert targets[0].read_bytes() == concurrent_bytes
    connection = duckdb.connect(str(ledger), read_only=True)
    try:
        assert connection.execute("SELECT count(*) FROM failure_projection_runs").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM failure_classifications").fetchone()[0] == 0
    finally:
        connection.close()


def test_exact_regime_components_and_legal_null_parameters_are_eligible(
    tmp_path: Path,
) -> None:
    corpus, _ = corpus_with_receipt(tmp_path)
    ledger = tmp_path / "ledger.duckdb"
    ingest_corpus(corpus_root=corpus, ledger_path=ledger)
    connection = duckdb.connect(str(ledger))
    try:
        connection.execute(
            "UPDATE trial_specs SET regime_scope_json=?",
            [json.dumps({"base_regime": "RISK_OFF", "family_tags": []})],
        )
        connection.execute(
            "UPDATE trial_specs SET parameters_json=?",
            [
                json.dumps(
                    {
                        "horizon": 5,
                        "stop_loss_pct": None,
                        "take_profit_pct": None,
                        "max_group_exposure": None,
                        "regime_gate": None,
                        "risk_guard": None,
                        "entry_filter": None,
                    }
                )
            ],
        )
    finally:
        connection.close()

    result = build_eligibility(
        ledger_path=ledger,
        output_root=tmp_path / "projection",
    )

    assert result["counts"] == {"ADAPTIVE_ELIGIBLE": 2}


def test_sealed_and_unknown_never_become_eligible(tmp_path: Path) -> None:
    corpus, _ = corpus_with_receipt(tmp_path)
    ledger = tmp_path / "ledger.duckdb"
    ingest_corpus(corpus_root=corpus, ledger_path=ledger)
    connection = duckdb.connect(str(ledger))
    try:
        units = [row[0] for row in connection.execute("SELECT execution_unit_id FROM execution_units ORDER BY 1").fetchall()]
        connection.execute("UPDATE execution_units SET sealed_usage_status='SEALED' WHERE execution_unit_id=?", [units[0]])
        connection.execute("UPDATE execution_units SET sealed_usage_status='UNKNOWN' WHERE execution_unit_id=?", [units[1]])
    finally:
        connection.close()
    result = build_eligibility(ledger_path=ledger, output_root=tmp_path / "projection")
    assert result["counts"] == {"INVALID_LINEAGE": 1, "SEALED_VALIDATION_ONLY": 1}
    assert sum(item["evidence_weight"] for item in result["decisions"]) == 0


def test_failed_receipt_and_legacy_subjects_are_classified_without_fake_observation(tmp_path: Path) -> None:
    ledger = tmp_path / "empty.duckdb"
    corpus = tmp_path / "empty-corpus"
    ingest_corpus(corpus_root=corpus, ledger_path=ledger)
    result = build_eligibility(ledger_path=ledger, output_root=tmp_path / "projection")
    assert result["status"] == "NO_ELIGIBLE_OBSERVATIONS"
    assert result["counts"] == {}


def test_versioned_activation_exclusion_quarantines_known_non_observation(
    tmp_path: Path,
) -> None:
    context = begin(tmp_path)
    receipt = finish_topic_attempt(
        context,
        terminal_status="FAILED",
        matrix_paths=[],
        failure_reason="INCOMPLETE_EXECUTION_FACTS",
    )
    ledger = tmp_path / "ledger.duckdb"
    ingest_corpus(corpus_root=context.root, ledger_path=ledger)
    exclusions = tmp_path / "activation_exclusions.json"
    exclusions.write_text(json.dumps({
        "schema_version": "research-spine-activation-exclusions.v1",
        "policy_version": "native-activation-exclusions.fixture.v1",
        "activation_success_allowed": False,
        "immutable_source_action": "PRESERVE",
        "entries": [{
            "receipt_id": receipt["receipt_id"],
            "run_id": receipt["run_id"],
            "source_topic_id": "topic:fixture",
            "classification": "TEST_FIXTURE_NON_OBSERVATION_POLLUTION",
            "reason_codes": ["NO_EXECUTION_FACTS"],
        }],
    }), encoding="utf-8")

    result = build_eligibility(
        ledger_path=ledger,
        activation_exclusions_path=exclusions,
        output_root=tmp_path / "projection",
    )

    decision = next(
        item for item in result["decisions"]
        if item["subject_id"] == receipt["receipt_id"]
    )
    assert decision["eligibility_status"] == "INVALID_LINEAGE"
    assert decision["evidence_weight"] == 0
    assert "ACTIVATION_EVIDENCE_QUARANTINED" in decision["reason_codes"]
    assert result["activation_exclusions"] == {
        "policy_version": "native-activation-exclusions.fixture.v1",
        "policy_hash": result["activation_exclusion_policy_hash"],
        "immutable_source_action": "PRESERVE",
        "configured_receipt_count": 1,
        "matched_receipt_count": 1,
        "matched_receipt_ids": [receipt["receipt_id"]],
        "activation_success_count": 0,
    }


def test_repo_activation_exclusions_match_preserved_pollution_receipts() -> None:
    root = Path("artifacts/autonomous_research/research_spine")
    policy = json.loads(
        Path("config/research_spine_activation_exclusions_v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert len(policy["entries"]) == 14
    if not root.exists():
        bundle = json.loads(
            Path(
                "docs/evidence/CARD-NEW-TOP10-NATIVE-EVIDENCE-REPLAY-BUNDLE-V1/bundle.json"
            ).read_text(encoding="utf-8")
        )
        report = verify_bundle(bundle, project_root=Path.cwd())
        excluded_receipts = {entry["receipt_id"] for entry in policy["entries"]}
        replay_receipts = {cycle["receipt_id"] for cycle in bundle["cycles"]}
        assert report["status"] == "PASS"
        assert replay_receipts.isdisjoint(excluded_receipts)
        assert all(
            row["sealed_usage_status"] == "PROVEN_NON_SEALED"
            and row["eligibility"]["status"] == "ADAPTIVE_ELIGIBLE"
            for row in bundle["observations"]
        )
        return
    for entry in policy["entries"]:
        receipt = json.loads(
            (root / "receipts" / f"{entry['run_id']}.json").read_text(encoding="utf-8")
        )
        assert receipt["receipt_id"] == entry["receipt_id"]
        assert receipt["terminal_status"] == "FAILED"
        assert receipt["execution_observation_status"] == "UNKNOWN"
        assert receipt["executed_units"] == []
        first_spec = receipt["requested"]["trial_spec_ids"][0].removeprefix("sha256:")
        spec = json.loads(
            (root / "trial_specs" / f"{first_spec}.json").read_text(encoding="utf-8")
        )
        assert spec["topic_id"] == entry["source_topic_id"]


def test_drawdown_direction_and_failure_evidence_semantics() -> None:
    policy = load_policy()
    safe = {
        "total_return": 0.0, "max_drawdown": -0.08, "win_rate": 0.4,
        "trade_count": 10, "p_value": None, "research_stage": "DEVELOPMENT_SCREEN",
    }
    safe_codes = {item["reason_code"] for item in classify_metrics(safe, policy)}
    assert "EXCESS_DRAWDOWN" not in safe_codes
    assert "LOW_SAMPLE_SIZE" in safe_codes
    assert "LOW_WIN_RATE" not in safe_codes
    assert "STATISTICAL_EVIDENCE_UNAVAILABLE" in safe_codes
    bad = {**safe, "total_return": -0.01, "max_drawdown": -0.30, "trade_count": 30}
    bad_codes = {item["reason_code"] for item in classify_metrics(bad, policy)}
    assert {"NEGATIVE_RETURN", "EXCESS_DRAWDOWN", "LOW_WIN_RATE"}.issubset(bad_codes)


def test_failure_projection_only_classifies_eligible_strategy_results(tmp_path: Path) -> None:
    corpus, _ = corpus_with_receipt(tmp_path, total_return=-0.08)
    ledger = tmp_path / "ledger.duckdb"
    ingest_corpus(corpus_root=corpus, ledger_path=ledger)
    result = build_failure(
        ledger_path=ledger,
        eligibility_output_root=tmp_path / "eligibility",
        output_root=tmp_path / "failure",
    )
    assert result["counts"]["NEGATIVE_RETURN"] >= 1
    forbidden = {"REGIME_SPECIFIC_ONLY", "OVERFIT_SHARP_PEAK", "NO_IMPROVEMENT", "NEIGHBOR_INSTABILITY"}
    assert forbidden.isdisjoint(result["counts"])


def test_policy_content_change_produces_new_projection_identity(tmp_path: Path) -> None:
    corpus, _ = corpus_with_receipt(tmp_path)
    ledger = tmp_path / "ledger.duckdb"
    ingest_corpus(corpus_root=corpus, ledger_path=ledger)
    base = json.loads(Path("config/research_eligibility_policy_v1.json").read_text())
    first_policy = tmp_path / "first.json"
    second_policy = tmp_path / "second.json"
    first_policy.write_text(json.dumps(base))
    base["allowed_research_stages"] = ["DEVELOPMENT_SCREEN"]
    second_policy.write_text(json.dumps(base))
    first = build_eligibility(ledger_path=ledger, policy_path=first_policy, output_root=tmp_path / "p")
    second = build_eligibility(ledger_path=ledger, policy_path=second_policy, output_root=tmp_path / "p")
    assert first["projection_id"] != second["projection_id"]


def test_policy_cannot_allow_unknown_sealed_or_reverse_drawdown(tmp_path: Path) -> None:
    import pytest

    eligibility = json.loads(Path("config/research_eligibility_policy_v1.json").read_text())
    eligibility["required_sealed_usage_status"] = "UNKNOWN"
    eligibility_path = tmp_path / "bad-eligibility.json"
    eligibility_path.write_text(json.dumps(eligibility))
    with pytest.raises(ValueError, match="MUST_BE_PROVEN_NON_SEALED"):
        load_eligibility_policy(eligibility_path)

    failure = json.loads(Path("config/research_failure_policy_v1.json").read_text())
    failure["max_drawdown_limit"] = 0.25
    failure_path = tmp_path / "bad-failure.json"
    failure_path.write_text(json.dumps(failure))
    with pytest.raises(ValueError, match="MAX_DRAWDOWN_LIMIT"):
        load_policy(failure_path)
