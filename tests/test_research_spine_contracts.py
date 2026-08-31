from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

from app.research.contracts import (
    CANONICALIZATION_VERSION,
    TERMINAL_CAUSE_POLICY_VERSION,
    content_hash,
    projection_identity,
    select_terminal_cause,
    validate_attempt_started,
    validate_migration_manifest,
    validate_observation_identity,
    validate_orphan_reconciliation,
    validate_parameter_catalog,
    validate_projection_provenance,
    validate_research_intent,
    validate_run_receipt,
    validate_trial_spec,
)
from app.research.map_contract import V2_DIMENSION_VALUES
from scripts.run_autonomous_research import VALIDATION_PROFILES


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def digest(label: str) -> str:
    return "sha256:" + hashlib.sha256(label.encode()).hexdigest()


def safety() -> dict[str, bool]:
    return {
        "does_not_train_model": True,
        "does_not_change_production_ranking": True,
        "production_promotion_allowed": False,
    }


def trial_spec() -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "research-trial-spec.v1",
        "canonicalization_version": CANONICALIZATION_VERSION,
        "trial_spec_id": digest("placeholder"),
        "topic_id": "topic-a",
        "topic_family_id": "topic-family-a",
        "parameter_catalog_version": "research-parameter-catalog.v1",
        "parameter_catalog_hash": digest("catalog"),
        "parameters": {
            "horizon": 5,
            "stop_loss_pct": 0.08,
            "take_profit_pct": 0.15,
            "max_group_exposure": 0.35,
            "regime_gate": None,
            "risk_guard": None,
            "entry_filter": None,
        },
        "research_stage": "DEVELOPMENT_SCREEN",
        "regime_scope": {"regime_id": "RISK_OFF|"},
        "dataset_authority": {"dataset_hash": digest("dataset")},
        "ranking_source_authority": {"ranking_source_hash": digest("ranking")},
        "execution_profile": {"runner": "strategy_matrix", "profile": "exact_trial"},
        "safety": safety(),
    }
    payload["trial_spec_id"] = content_hash(payload, omit={"trial_spec_id"})
    return payload


def attempt_started(trial_id: str) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "research-run-attempt-started.v1",
        "attempt_event_id": digest("placeholder"),
        "run_id": "run:1",
        "intent_id": "intent:1",
        "requested_trial_spec_ids": [trial_id],
        "requested_dataset_bundle_id": digest("bundle"),
        "requested_dataset_bundle_manifest_ref": "dataset_bundles/" + digest("bundle")[7:] + ".json",
        "started_at": "2026-08-14T00:00:00+00:00",
        "executor": {"runner_id": "autonomous-research", "runner_version": "v1", "code_hash": digest("code")},
        "invocation_hash": digest("invocation"),
    }
    payload["attempt_event_id"] = content_hash(payload, omit={"attempt_event_id"})
    return payload


def receipt() -> dict[str, object]:
    spec = trial_spec()
    trial_id = str(spec["trial_spec_id"])
    attempt = attempt_started(trial_id)
    parameters = deepcopy(spec["parameters"])
    payload: dict[str, object] = {
        "schema_version": "research-run-receipt.v1",
        "run_id": "run:1",
        "intent_id": "intent:1",
        "receipt_id": digest("placeholder"),
        "attempt_event_id": attempt["attempt_event_id"],
        "writer_version": "research-receipt-writer.v1",
        "terminal_status": "SUCCEEDED",
        "started_at": "2026-08-14T00:00:00+00:00",
        "completed_at": "2026-08-14T00:01:00+00:00",
        "terminal_cause": {
            "policy_version": TERMINAL_CAUSE_POLICY_VERSION,
            "status": "SUCCEEDED",
            "reason_code": "RUNNER_COMPLETED",
            "observed_at": "2026-08-14T00:01:00+00:00",
            "observer": "controlled-executor",
            "runner_started": True,
            "evidence_refs": [digest("development-contract")],
        },
        "bundle_binding": {
            "requested_dataset_bundle_id": digest("bundle"),
            "requested_dataset_bundle_manifest_ref": "dataset_bundles/" + digest("bundle")[7:] + ".json",
            "executed_dataset_bundle_id": digest("bundle"),
            "executed_dataset_bundle_manifest_ref": "dataset_bundles/" + digest("bundle")[7:] + ".json",
            "validation_status": "VALID",
        },
        "requested": {
            "trial_spec_ids": [trial_id],
            "dataset_bundle_id": digest("bundle"),
            "dataset_bundle_manifest_ref": "dataset_bundles/" + digest("bundle")[7:] + ".json",
            "parameters_by_trial": {trial_id: parameters},
            "research_stage": "DEVELOPMENT_SCREEN",
            "regime_scope": {"regime_id": "RISK_OFF|"},
            "dataset_authority": {"dataset_hash": digest("dataset")},
            "ranking_source_authority_by_trial": {
                trial_id: {"ranking_source_hash": digest("ranking")}
            },
            "execution_profile_by_trial": {
                trial_id: {"runner": "strategy_matrix", "profile": "exact_trial"}
            },
        },
        "executed_units": [{
            "execution_unit_id": digest("unit"),
            "requested_trial_spec_id": trial_id,
            "executed_trial_spec_id": trial_id,
            "executed_parameters": parameters,
            "executed_research_stage": "DEVELOPMENT_SCREEN",
            "executed_regime_scope": {"regime_id": "RISK_OFF|"},
            "executed_dataset_hash": digest("dataset"),
            "executed_dataset_bundle_id": digest("bundle"),
            "executed_dataset_bundle_manifest_ref": "dataset_bundles/" + digest("bundle")[7:] + ".json",
            "executed_ranking_source_hash": digest("ranking"),
            "executed_execution_profile": {"runner": "strategy_matrix", "profile": "exact_trial"},
            "lineage": {
                "lineage_id": digest("lineage"),
                "sealed_usage_status": "PROVEN_NON_SEALED",
                "episode_ids": ["episode-dev"],
                "episode_authority_hash": digest("episodes"),
            },
            "lineage_assertions": [{
                "authority": "development-contract",
                "authority_hash": digest("development-contract"),
                "facts": {
                    "sealed_usage_status": "PROVEN_NON_SEALED",
                    "research_stage": "DEVELOPMENT_SCREEN",
                    "dataset_hash": digest("dataset"),
                    "ranking_source_hash": digest("ranking"),
                    "regime_scope": {"regime_id": "RISK_OFF|"},
                    "episode_ids": ["episode-dev"],
                },
            }],
            "lineage_resolution_status": "VALID",
            "artifact_refs": [digest("development-contract")],
        }],
        "resolution_events": [],
        "identity_match_status": "EXACT",
        "execution_observation_status": "OBSERVED",
        "artifacts": [{
            "artifact_id": digest("development-contract"),
            "corpus_path": f"source_corpus/sha256/{digest('development-contract')[7:]}",
            "provenance_path": "artifacts/example.json",
            "validation_status": "VALID",
        }],
        "safety": safety(),
    }
    payload["receipt_id"] = content_hash(payload, omit={"receipt_id"})
    return payload


def test_parameter_catalog_matches_current_coverage_and_profiles() -> None:
    catalog = json.loads((PROJECT_ROOT / "config/research_parameter_catalog.json").read_text())
    assert validate_parameter_catalog(catalog) == []
    dimensions = {row["id"]: row for row in catalog["dimensions"]}
    assert dimensions["horizon"]["coverage_values"] == [3, 5, 10]
    assert dimensions["horizon"]["executable_values"] == [3, 5, 10, 20]
    assert dimensions["stop_loss_pct"]["coverage_values"] == [None, "0.08", "0.12"]
    assert dimensions["regime_gate"]["coverage_values"] == [
        "ALL", "BIG_BULL_ONLY", "BIG_BULL_HIGH_CHOPPY", "EXCLUDE_RISK_OFF_PANIC",
        "RISK_OFF_ONLY", "PANIC_SELLING_ONLY", "NEUTRAL_ONLY",
    ]
    assert [profile["id"] for profile in catalog["validation_profiles"]] == [
        "standard", "risk_guard", "long_horizon", "tight_exit",
    ]
    assert 3 * 3 * 3 * 3 == 81
    assert len(dimensions["regime_gate"]["coverage_values"]) * len(
        dimensions["risk_guard"]["coverage_values"]
    ) * len(dimensions["entry_filter"]["coverage_values"]) == 112
    assert {
        key: dimensions[key]["coverage_values"]
        for key in ("regime_gate", "risk_guard", "entry_filter")
    } == V2_DIMENSION_VALUES
    catalog_profiles = {row["id"]: row for row in catalog["validation_profiles"]}
    for current in VALIDATION_PROFILES:
        projected = catalog_profiles[current["name"]]
        assert ",".join("none" if value is None else str(value) for value in projected["horizon"]) == current["horizons"]
        assert ",".join("none" if value is None else str(value) for value in projected["stop_loss_pct"]) == current["stop_loss_pcts"]
        assert ",".join("none" if value is None else str(value) for value in projected["take_profit_pct"]) == current["take_profit_pcts"]
        assert ",".join("none" if value is None else str(value) for value in projected["max_group_exposure"]) == current["max_group_exposures"]


def test_parameter_catalog_rejects_invalid_types_and_profile_values() -> None:
    catalog = json.loads((PROJECT_ROOT / "config/research_parameter_catalog.json").read_text())
    catalog["dimensions"][0]["data_type"] = "banana"
    catalog["validation_profiles"][0]["horizon"] = [999]
    errors = validate_parameter_catalog(catalog)
    assert "dimensions[0].data_type is invalid" in errors
    assert "validation_profiles[0].horizon must use executable values" in errors


def test_trial_spec_has_content_identity_and_strict_nested_shape() -> None:
    payload = trial_spec()
    assert validate_trial_spec(payload) == []
    payload["topic_id"] = None
    payload["trial_spec_id"] = "garbage"
    payload["parameters"] = "bad"
    errors = validate_trial_spec(payload)
    assert "topic_id must be non-empty" in errors
    assert "trial_spec_id must be sha256:<64 lowercase hex>" in errors
    assert "parameters must equal canonical parameter set" in errors


def test_decimal_canonicalization_prevents_float_string_identity_split() -> None:
    assert content_hash({"value": 0.08}) == content_hash({"value": "0.08"})


def test_research_intent_binds_request_to_trial_spec() -> None:
    payload = {
        "schema_version": "research-intent.v1", "intent_id": "intent:1",
        "requested_trial_spec_ids": [trial_spec()["trial_spec_id"]],
        "requested_dataset_bundle_id": digest("bundle"),
        "requested_dataset_bundle_manifest_ref": "dataset_bundles/" + digest("bundle")[7:] + ".json",
        "requested_at": "2026-08-14T00:00:00+00:00", "request_source": "existing_manager",
        "selection_reason": {"reason_codes": ["EXISTING_QUEUE"]},
    }
    assert validate_research_intent(payload) == []


def test_attempt_started_has_recomputable_event_identity() -> None:
    payload = attempt_started(str(trial_spec()["trial_spec_id"]))
    assert validate_attempt_started(payload) == []
    payload["run_id"] = "mutated"
    assert "attempt_event_id does not match canonical content" in validate_attempt_started(payload)


def test_terminal_taxonomy_accepts_six_controlled_states_and_rejects_orphan_status() -> None:
    for status in ("SUCCEEDED", "FAILED", "REJECTED_BEFORE_EXECUTION", "CANCELLED", "TIMED_OUT", "ABORTED"):
        payload = receipt()
        payload["terminal_status"] = status
        payload["terminal_cause"]["status"] = status
        payload["terminal_cause"]["reason_code"] = f"{status}_EVIDENCE"
        payload["terminal_cause"]["runner_started"] = status != "REJECTED_BEFORE_EXECUTION"
        if status != "SUCCEEDED":
            payload["executed_units"] = [] if status == "REJECTED_BEFORE_EXECUTION" else payload["executed_units"]
            payload["execution_observation_status"] = "NOT_STARTED" if status == "REJECTED_BEFORE_EXECUTION" else "OBSERVED"
            payload["identity_match_status"] = "NOT_EXECUTED" if status == "REJECTED_BEFORE_EXECUTION" else "EXACT"
            payload["failure"] = {"reason_code": f"{status}_EVIDENCE"}
            if status == "REJECTED_BEFORE_EXECUTION":
                payload["bundle_binding"]["executed_dataset_bundle_id"] = "UNKNOWN"
                payload["bundle_binding"]["executed_dataset_bundle_manifest_ref"] = "UNKNOWN"
                payload["bundle_binding"]["validation_status"] = "NOT_EXECUTED"
        payload["receipt_id"] = content_hash(payload, omit={"receipt_id"})
        assert validate_run_receipt(payload) == []

    payload = receipt()
    payload["terminal_status"] = "ORPHANED_ATTEMPT"
    payload["terminal_cause"]["status"] = "ORPHANED_ATTEMPT"
    payload["receipt_id"] = content_hash(payload, omit={"receipt_id"})
    assert "terminal_status is invalid" in validate_run_receipt(payload)


def test_terminal_cause_race_uses_observed_time_then_fixed_tie_break() -> None:
    timeout = {
        "status": "TIMED_OUT",
        "reason_code": "DEADLINE_EXCEEDED",
        "observed_at": "2026-08-14T00:01:00+00:00",
    }
    cancel = {
        "status": "CANCELLED",
        "reason_code": "USER_CANCELLED",
        "observed_at": "2026-08-14T00:01:01+00:00",
    }
    assert select_terminal_cause([cancel, timeout])["status"] == "TIMED_OUT"
    cancel["observed_at"] = timeout["observed_at"]
    assert select_terminal_cause([timeout, cancel])["status"] == "CANCELLED"


def test_orphan_reconciliation_is_fail_closed() -> None:
    payload = {
        "schema_version": "research-orphan-reconciliation.v1", "run_id": "run:orphan",
        "intent_id": "intent:1", "attempt_event_id": digest("attempt"),
        "observed_at": "2026-08-14T00:05:00+00:00",
        "reconciliation_policy_version": "research-orphan-reconciliation.v1",
        "status": "ORPHANED_ATTEMPT", "sealed_usage_status": "UNKNOWN",
        "facts_unknown": [
            "executed_parameters",
            "executed_lineage",
            "executed_dataset_bundle",
            "result",
        ],
    }
    assert validate_orphan_reconciliation(payload) == []
    payload["facts_unknown"] = []
    assert "facts_unknown must enumerate all unknowable execution facts" in validate_orphan_reconciliation(payload)


def test_terminal_receipt_records_exact_requested_and_executed_facts() -> None:
    assert validate_run_receipt(receipt()) == []


def test_receipt_rejects_missing_unit_fields_and_silent_substitution() -> None:
    payload = receipt()
    unit = payload["executed_units"][0]
    del unit["executed_dataset_hash"]
    payload["identity_match_status"] = "EXACT"
    payload["receipt_id"] = content_hash(payload, omit={"receipt_id"})
    errors = validate_run_receipt(payload)
    assert "executed_units[0].executed_dataset_hash is required" in errors
    assert "resolution_events must exactly disclose requested/executed differences" in errors


def test_receipt_rejects_duplicate_trial_mapping_and_missing_failure_reason() -> None:
    payload = receipt()
    duplicate = deepcopy(payload["executed_units"][0])
    duplicate["execution_unit_id"] = digest("unit-2")
    payload["executed_units"].append(duplicate)
    payload["receipt_id"] = content_hash(payload, omit={"receipt_id"})
    assert "requested_trial_spec_id must map to exactly one executed unit" in validate_run_receipt(payload)

    failed = receipt()
    failed["terminal_status"] = "FAILED"
    failed["receipt_id"] = content_hash(failed, omit={"receipt_id"})
    assert "non-success receipt requires failure" in validate_run_receipt(failed)


def test_receipt_rejects_empty_parameter_identity_and_unstructured_failure() -> None:
    payload = receipt()
    trial_id = payload["requested"]["trial_spec_ids"][0]
    payload["requested"]["parameters_by_trial"][trial_id] = {}
    payload["executed_units"][0]["executed_parameters"] = {}
    payload["receipt_id"] = content_hash(payload, omit={"receipt_id"})
    errors = validate_run_receipt(payload)
    assert any("must equal canonical parameter set" in error for error in errors)

    payload = receipt()
    payload["terminal_status"] = "FAILED"
    payload["failure"] = {"x": 1}
    payload["receipt_id"] = content_hash(payload, omit={"receipt_id"})
    assert "failure.reason_code is required" in validate_run_receipt(payload)


def test_authority_conflict_is_valid_fact_but_forced_invalid_lineage() -> None:
    payload = receipt()
    unit = payload["executed_units"][0]
    unit["lineage_assertions"] = [
        {
            "authority": "development-contract",
            "facts": deepcopy(unit["lineage_assertions"][0]["facts"]),
        },
        {
            "authority": "matrix-input",
            "facts": {**deepcopy(unit["lineage_assertions"][0]["facts"]), "research_stage": "SEALED_VALIDATION"},
        },
    ]
    for assertion in unit["lineage_assertions"]:
        assertion["authority_hash"] = digest(assertion["authority"])
    payload["artifacts"] = [
        {
            "artifact_id": assertion["authority_hash"],
            "corpus_path": f"source_corpus/sha256/{assertion['authority_hash'][7:]}",
            "provenance_path": f"artifacts/{assertion['authority']}.json",
            "validation_status": "VALID",
        }
        for assertion in unit["lineage_assertions"]
    ]
    unit["artifact_refs"] = [item["artifact_id"] for item in payload["artifacts"]]
    unit["lineage_resolution_status"] = "INVALID_LINEAGE"
    unit["lineage"]["sealed_usage_status"] = "UNKNOWN"
    payload["receipt_id"] = content_hash(payload, omit={"receipt_id"})
    assert validate_run_receipt(payload) == []

    unit["lineage_resolution_status"] = "VALID"
    assert "executed_units[0] authority conflict must fail closed" in validate_run_receipt(payload)


def test_lineage_assertions_with_complementary_facts_do_not_conflict() -> None:
    payload = receipt()
    unit = payload["executed_units"][0]
    all_facts = deepcopy(unit["lineage_assertions"][0]["facts"])
    unit["lineage_assertions"] = [
        {
            "authority": "development-contract",
            "authority_hash": digest("development-contract"),
            "facts": {key: all_facts[key] for key in ("sealed_usage_status", "research_stage", "regime_scope", "episode_ids")},
        },
        {
            "authority": "dataset-manifest",
            "authority_hash": digest("dataset-manifest"),
            "facts": {key: all_facts[key] for key in ("dataset_hash", "ranking_source_hash")},
        },
    ]
    payload["artifacts"] = [
        {
            "artifact_id": assertion["authority_hash"],
            "corpus_path": f"source_corpus/sha256/{assertion['authority_hash'][7:]}",
            "provenance_path": f"artifacts/{assertion['authority']}.json",
            "validation_status": "VALID",
        }
        for assertion in unit["lineage_assertions"]
    ]
    unit["artifact_refs"] = [item["artifact_id"] for item in payload["artifacts"]]
    payload["receipt_id"] = content_hash(payload, omit={"receipt_id"})
    assert validate_run_receipt(payload) == []


def test_proven_non_sealed_requires_explicit_authority_support() -> None:
    payload = receipt()
    payload["executed_units"][0]["lineage_assertions"][0]["facts"] = {}
    payload["receipt_id"] = content_hash(payload, omit={"receipt_id"})
    assert "executed_units[0] resolved lineage claims lack authority support" in validate_run_receipt(payload)


def test_failed_attempt_is_valid_without_executed_result() -> None:
    payload = receipt()
    payload["terminal_status"] = "REJECTED_BEFORE_EXECUTION"
    payload["terminal_cause"]["status"] = "REJECTED_BEFORE_EXECUTION"
    payload["terminal_cause"]["reason_code"] = "INVALID_LINEAGE"
    payload["terminal_cause"]["runner_started"] = False
    payload["bundle_binding"]["executed_dataset_bundle_id"] = "UNKNOWN"
    payload["bundle_binding"]["executed_dataset_bundle_manifest_ref"] = "UNKNOWN"
    payload["bundle_binding"]["validation_status"] = "NOT_EXECUTED"
    payload["executed_units"] = []
    payload["identity_match_status"] = "NOT_EXECUTED"
    payload["execution_observation_status"] = "NOT_STARTED"
    payload["failure"] = {"reason_code": "INVALID_LINEAGE"}
    payload["receipt_id"] = content_hash(payload, omit={"receipt_id"})
    assert validate_run_receipt(payload) == []


def test_migration_manifest_requires_content_addressed_corpus() -> None:
    artifact_hash = digest("legacy")
    migration = {
        "schema_version": "research-ledger-migration-manifest.v1", "migration_id": "migration:1",
        "parser_version": "legacy-research-parser.v1",
        "semantic_identity_policy_version": "research-observation-identity.v1",
        "duplicate_policy": "MERGE_PROVENANCE_WITHOUT_EVIDENCE_WEIGHT",
        "conflict_policy": "QUARANTINE_FAIL_CLOSED", "generated_at": "2026-08-14T00:00:00+00:00",
        "sources": [{
            "source_artifact_hash": artifact_hash, "source_artifact_path": "artifacts/legacy.json",
            "corpus_artifact_path": f"artifacts/autonomous_research/source_corpus/sha256/{artifact_hash[7:]}",
            "corpus_artifact_hash": artifact_hash, "record_mapping_hash": digest("mapping"),
            "classification": "LEGACY_DIAGNOSTIC_ONLY", "reason_codes": ["MISSING_LINEAGE"],
        }],
    }
    assert validate_migration_manifest(migration) == []
    migration["sources"][0]["corpus_artifact_path"] = "../source_corpus/sha256/wrong"
    assert any("must reference immutable CAS" in error for error in validate_migration_manifest(migration))


def test_observation_identity_is_semantic_and_recomputed() -> None:
    payload: dict[str, object] = {
        "schema_version": "research-observation-identity.v1", "observation_id": digest("placeholder"),
        "identity_policy_version": "research-observation-identity.v1", "origin_execution_id": digest("unit"),
        "executed_trial_identity": digest("executed-trial"), "executed_lineage_id": digest("lineage"),
        "evidence_unit_id": digest("evidence-unit"), "result_unit_id": "episode-cluster:development-a",
        "metric_policy_version": "strategy-matrix-metrics.v1",
        "attempt_inclusion_policy_version": "completed-terminal-attempts.v1",
    }
    payload["observation_id"] = content_hash(payload, omit={"observation_id"})
    assert validate_observation_identity(payload) == []
    payload["source_artifact_path"] = "archive/copy.json"
    assert "source_artifact_path is not allowed" in validate_observation_identity(payload)


def test_observation_identity_rejects_junk_semantic_ids_and_empty_policies() -> None:
    payload = {
        "schema_version": "research-observation-identity.v1",
        "observation_id": digest("placeholder"), "identity_policy_version": "",
        "origin_execution_id": "junk", "executed_trial_identity": "junk",
        "executed_lineage_id": "junk", "evidence_unit_id": "junk", "result_unit_id": "",
        "metric_policy_version": "", "attempt_inclusion_policy_version": "",
    }
    payload["observation_id"] = content_hash(payload, omit={"observation_id"})
    errors = validate_observation_identity(payload)
    assert "origin_execution_id must be sha256:<64 lowercase hex>" in errors
    assert "identity_policy_version must be non-empty" in errors


def test_projection_identity_and_path_are_immutable() -> None:
    payload: dict[str, object] = {
        "schema_version": "research-projection-provenance.v1", "projection_id": digest("placeholder"),
        "projection_type": "PARAMETER_LEARNING",
        "projection_schema_version": "parameter-learning-projection.v1",
        "input_corpus_hash": digest("corpus"),
        "parameter_catalog_version": "research-parameter-catalog.v1", "parameter_catalog_hash": digest("catalog"),
        "canonicalization_version": CANONICALIZATION_VERSION,
        "eligibility_policy_version": "research-eligibility.v1",
        "failure_classifier_version": "research-failure-classifier.v1",
        "learning_policy_version": "matched-parameter-learning.v1",
        "metric_policy_version": "strategy-matrix-metrics.v1",
        "attempt_inclusion_policy_version": "terminal-receipts.v1",
        "migration_semantic_policy_version": "legacy-migration.v1",
        "generated_at": "2026-08-14T00:00:00+00:00", "output_artifact_path": "placeholder",
        "output_artifact_hash": digest("output"),
    }
    payload["projection_id"] = projection_identity(payload)
    payload["output_artifact_path"] = (
        f"artifacts/autonomous_research/projections/parameter_learning/{str(payload['projection_id'])[7:]}.json"
    )
    assert validate_projection_provenance(payload) == []
    payload["output_artifact_path"] = "artifacts/autonomous_research/search_knowledge_latest.json"
    assert "output_artifact_path must be content-addressed by projection_id" in validate_projection_provenance(payload)
