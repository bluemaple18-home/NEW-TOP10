from __future__ import annotations

import json
from pathlib import Path

import duckdb

from app.research.eligibility import build_projection as build_eligibility, load_policy as load_eligibility_policy
from app.research.failure_classification import build_projection as build_failure, classify_metrics, load_policy
from app.research.observation_ingest import ingest_corpus
from app.research.run_receipts import finish_topic_attempt
from tests.test_autonomous_research_receipts import begin
from tests.test_research_ledger import corpus_with_receipt


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
