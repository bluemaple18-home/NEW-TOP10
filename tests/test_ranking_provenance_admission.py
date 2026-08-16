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
    assert admission.validate_audit(payload) == []
    assert payload == admission.build_audit()


def test_current_hash_backfill_cannot_admit() -> None:
    availability, feasibility = _sources()
    artifacts, _ = admission._availability_artifacts(availability)
    key = sorted(artifacts)[0]
    receipt = _valid_receipt(*key, artifacts[key])
    receipt["contemporaneous_at_generation"] = False
    availability["contemporaneous_ranking_provenance_receipts"] = [receipt]
    payload = admission.evaluate_admission(availability, feasibility)
    assert payload["status"] == "BLOCKED_EVIDENCE_CONFLICT"
    assert "RECEIPT_NOT_CONTEMPORANEOUS" in payload["reason_codes"]


def test_latest_fallback_and_outcome_key_are_rejected() -> None:
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


def test_receipt_requires_same_artifact_identity() -> None:
    availability, feasibility = _sources()
    artifacts, _ = admission._availability_artifacts(availability)
    key = sorted(artifacts)[0]
    receipt = _valid_receipt(*key, artifacts[key])
    receipt["ranking_artifact"]["sha256"] = "sha256:" + "f" * 64
    availability["contemporaneous_ranking_provenance_receipts"] = [receipt]
    payload = admission.evaluate_admission(availability, feasibility)
    assert payload["status"] == "BLOCKED_EVIDENCE_CONFLICT"
    assert "RECEIPT_ARTIFACT_IDENTITY_CONFLICT" in payload["reason_codes"]


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
