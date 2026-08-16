from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path

import pytest

from app.research.contracts import content_hash
from app.research import ranking_provenance_admission as admission


def _rehash(payload: dict) -> dict:
    payload["audit_id"] = content_hash(payload, omit={"audit_id"})
    return payload


def _sources() -> tuple[dict, dict]:
    root = admission.PROJECT_ROOT
    availability = json.loads((root / admission.AVAILABILITY_RELATIVE).read_text(encoding="utf-8"))
    feasibility = json.loads((root / admission.FEASIBILITY_RELATIVE).read_text(encoding="utf-8"))
    return availability, feasibility


def _valid_receipt(scenario: str, ranking_date: str, artifact: dict[str, str]) -> dict:
    return {
        "scenario": scenario,
        "ranking_date": ranking_date,
        "contemporaneous_at_generation": True,
        "immutable_committed_receipt": True,
        "receipt_identity": "receipt-001",
        "receipt_commit": "a" * 40,
        "ranking_artifact": artifact,
        "producer": {
            "entrypoint": "scripts/build_rankings.py",
            "source_commit": "b" * 40,
            "source_sha256": "sha256:" + "1" * 64,
        },
        "model": {
            "artifact_path": "models/model.bin",
            "version": "v1",
            "sha256": "sha256:" + "2" * 64,
        },
        "config": {"sha256": "sha256:" + "3" * 64},
        "universe": {
            "snapshot_path": "artifacts/universe.json",
            "sha256": "sha256:" + "4" * 64,
        },
        "top_n_policy": {"top_n": 10, "sort_policy": "score_desc", "tie_break_policy": "stock_id_asc"},
    }


def test_actual_evidence_is_deterministic_no_go_matrix() -> None:
    payload = admission.build_audit()
    assert payload["status"] == "NO_GO_RANKING_PROVENANCE_INCOMPLETE"
    assert payload["record_count"] == 50
    assert payload["missing_lineage_field_count"] == 300
    assert {record["admission"] for record in payload["records"]} == {"REJECT"}
    assert {
        field["status"]
        for record in payload["records"]
        for field in record["lineage"].values()
    } == {"MISSING"}
    assert {source["commit_status"] for source in payload["sources"].values()} == {"MATCHED"}
    assert admission.RECEIPT_AUTHORITY_CONFIGURED is False
    assert {
        field["reason_code"]
        for record in payload["records"]
        for name, field in record["lineage"].items()
        if name == "ranking_artifact"
    } == {"CURRENT_AVAILABILITY_HASH_NOT_CONTEMPORANEOUS_PROVENANCE"}
    assert admission.validate_audit(payload) == []
    assert payload == admission.build_audit()


def test_unregistered_synthetic_receipt_is_record_level_conflict() -> None:
    availability, feasibility = _sources()
    artifacts, _ = admission._availability_artifacts(availability)
    key = sorted(artifacts)[0]
    receipt = _valid_receipt(*key, artifacts[key])
    availability["contemporaneous_ranking_provenance_receipts"] = [receipt]
    payload = admission.evaluate_admission(availability, feasibility)
    assert payload["status"] == "BLOCKED_EVIDENCE_CONFLICT"
    assert "UNSUPPORTED_OR_UNREGISTERED_RECEIPT_AUTHORITY" in payload["reason_codes"]
    conflicted = [row for row in payload["records"] if row["scenario"] == key[0] and row["ranking_date"] == key[1]]
    assert {field["status"] for field in conflicted[0]["lineage"].values()} == {"CONFLICT"}
    audit = {
        "schema_version": admission.SCHEMA_VERSION,
        "audit_id": "",
        **payload,
        "contract": {
            "research_only": True, "network_requests": 0, "raw_data_writes": 0,
            "outcome_access_allowed": False, "replay_allowed": False, "runtime_change_allowed": False,
            "current_hash_backfill_allowed": False, "latest_or_default_fallback_allowed": False,
            "receipt_authority_configured": False,
        },
        "sources": {
            "availability": {"path": "a.json", "sha256": "sha256:" + "a" * 64, "commit_status": "MATCHED"},
            "feasibility": {"path": "b.json", "sha256": "sha256:" + "b" * 64, "commit_status": "MATCHED"},
        },
    }
    _rehash(audit)
    assert admission.validate_audit(audit) == []


def test_latest_fallback_outcome_and_performance_keys_are_rejected() -> None:
    payload = copy.deepcopy(admission.build_audit())
    payload["records"][0]["lineage"]["model"] = {
        "status": "PROVEN",
        "evidence": {"version": "latest"},
    }
    _rehash(payload)
    assert "LATEST_OR_DEFAULT_FALLBACK_FORBIDDEN" in admission.validate_audit(payload)

    payload = copy.deepcopy(admission.build_audit())
    payload["outcome_value"] = 1
    _rehash(payload)
    assert "OUTCOME_KEY_FORBIDDEN" in admission.validate_audit(payload)

    for forbidden_key in ("profit", "roi", "performance"):
        payload = copy.deepcopy(admission.build_audit())
        payload[forbidden_key] = 1
        _rehash(payload)
        assert "OUTCOME_KEY_FORBIDDEN" in admission.validate_audit(payload)


def test_scenario_date_alias_and_false_admission_are_rejected() -> None:
    payload = copy.deepcopy(admission.build_audit())
    payload["records"].append(copy.deepcopy(payload["records"][0]))
    payload["record_count"] += 1
    _rehash(payload)
    assert "SCENARIO_DATE_ALIAS" in admission.validate_audit(payload)

    payload = copy.deepcopy(admission.build_audit())
    payload["status"] = "ADMITTED_RANKING_PROVENANCE_COMPLETE"
    _rehash(payload)
    assert "FALSE_ADMISSION" in admission.validate_audit(payload)
    assert "ADMISSION_AUTHORITY_NOT_CONFIGURED" in admission.validate_audit(payload)


def test_unregistered_receipt_schema_and_alias_are_conflicts() -> None:
    availability, feasibility = _sources()
    artifacts, _ = admission._availability_artifacts(availability)
    key = sorted(artifacts)[0]
    receipt = _valid_receipt(*key, artifacts[key])
    receipt["profit"] = 1
    availability["contemporaneous_ranking_provenance_receipts"] = [receipt]
    payload = admission.evaluate_admission(availability, feasibility)
    assert payload["status"] == "BLOCKED_EVIDENCE_CONFLICT"
    assert "RECEIPT_SCHEMA_INVALID" in payload["reason_codes"]

    availability, feasibility = _sources()
    receipt = _valid_receipt(*key, artifacts[key])
    availability["contemporaneous_ranking_provenance_receipts"] = [receipt, receipt]
    payload = admission.evaluate_admission(availability, feasibility)
    assert "RECEIPT_SCENARIO_DATE_ALIAS_OR_UNKNOWN" in payload["reason_codes"]
    assert {field["status"] for row in payload["records"] for field in row["lineage"].values()} == {"CONFLICT"}


def test_proven_requires_exact_cross_bound_evidence_and_is_not_admissible() -> None:
    payload = copy.deepcopy(admission.build_audit())
    row = payload["records"][0]
    row["lineage"]["model"] = {"status": "PROVEN", "evidence": {}}
    payload["missing_lineage_field_count"] -= 1
    _rehash(payload)
    errors = admission.validate_audit(payload)
    assert "LINEAGE_PROVEN_EVIDENCE_INVALID" in errors
    assert "ADMISSION_AUTHORITY_NOT_CONFIGURED" in errors

    payload = copy.deepcopy(admission.build_audit())
    row = payload["records"][0]
    artifact = row["artifact_identity"]
    row["lineage"]["model"] = {
        "status": "PROVEN",
        "evidence": {
            "scenario": "wrong-scenario", "ranking_date": row["ranking_date"],
            "receipt_identity": "receipt-1", "artifact_path": artifact["path"],
            "artifact_sha256": artifact["sha256"],
            "value": {"artifact_path": "models/model.bin", "version": "v1", "sha256": "sha256:" + "1" * 64},
        },
    }
    payload["missing_lineage_field_count"] -= 1
    _rehash(payload)
    assert "LINEAGE_PROVEN_EVIDENCE_INVALID" in admission.validate_audit(payload)


def test_committed_source_drift_is_fail_closed(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test"], check=True)
    source = tmp_path / "source.json"
    source.write_text("{}\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "source.json"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "fixture"], check=True)
    admission._committed_json(tmp_path, Path("source.json"))
    source.write_text('{"changed":true}\n', encoding="utf-8")
    with pytest.raises(admission.RankingProvenanceAdmissionError, match="SOURCE_WORKTREE_DRIFT"):
        admission._committed_json(tmp_path, Path("source.json"))


def test_encoding_is_canonical_and_portable() -> None:
    payload = admission.build_audit()
    assert admission.encode_audit(payload) == admission.encode_audit(admission.build_audit())
    serialized = admission.encode_audit(payload).decode("utf-8")
    assert "/Users/" not in serialized
    assert "generated_at" not in serialized
    assert "timestamp" not in serialized
