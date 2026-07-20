from __future__ import annotations

from copy import deepcopy

from app.research.tskg_evidence_contract import (
    build_evidence_envelope,
    verify_evidence_envelope,
)


def _complete_assessments() -> dict[str, dict[str, object]]:
    return {
        "identity_assessment": {
            "status": "RESOLVED",
            "entity_refs": ["entity:fixture-company"],
            "resolver_version": "fixture-v1",
        },
        "source_assessment": {
            "status": "SYNTHETIC_ONLY",
            "source_refs": ["source:synthetic-fixture"],
            "policy_receipt_refs": ["docs/evidence/policy.json"],
        },
        "temporal_scope": {
            "status": "BOUNDED",
            "as_of": "2026-07-20T00:00:00Z",
            "valid_from": "2026-01-01T00:00:00Z",
            "valid_to": "2026-07-20T00:00:00Z",
        },
        "conflict_assessment": {
            "status": "NONE",
            "conflict_refs": [],
        },
    }


def test_grandfathered_archive_does_not_require_research_rerun() -> None:
    envelope = build_evidence_envelope(
        research_id="research:archived-study",
        usage_intent="ARCHIVE_ONLY",
        adoption_mode="GRANDFATHERED",
    )

    assert envelope["decision"] == "GRANDFATHERED"
    assert envelope["hard_block"] is False
    assert verify_evidence_envelope(envelope)["status"] == "OK"


def test_new_research_records_missing_evidence_without_blocking_execution() -> None:
    envelope = build_evidence_envelope(
        research_id="research:new-study",
        usage_intent="RESEARCH_ONLY",
        adoption_mode="REQUIRED_NOW",
    )

    assert envelope["decision"] == "NEEDS_EVIDENCE"
    assert envelope["hard_block"] is False
    assert set(envelope["blocking_reasons"]) == {
        "conflict_not_evaluated",
        "evidence_refs_missing",
        "identity_not_evaluated",
        "source_not_evaluated",
        "temporal_scope_not_evaluated",
    }


def test_reuse_is_blocked_until_all_assessments_are_complete() -> None:
    blocked = build_evidence_envelope(
        research_id="research:reused-study",
        usage_intent="MODEL_INPUT",
        adoption_mode="CHECK_ON_REUSE",
    )
    ready = build_evidence_envelope(
        research_id="research:reused-study",
        usage_intent="MODEL_INPUT",
        adoption_mode="CHECK_ON_REUSE",
        evidence_refs=["docs/evidence/reused-study.json"],
        **_complete_assessments(),
    )

    assert blocked["decision"] == "BLOCKED"
    assert blocked["hard_block"] is True
    assert ready["decision"] == "READY"
    assert ready["hard_block"] is False


def test_open_conflict_blocks_promotion() -> None:
    assessments = _complete_assessments()
    assessments["conflict_assessment"] = {
        "status": "OPEN",
        "conflict_refs": ["docs/evidence/conflict.json"],
    }
    envelope = build_evidence_envelope(
        research_id="research:conflicted-study",
        usage_intent="PROMOTION",
        adoption_mode="REQUIRED_NOW",
        evidence_refs=["docs/evidence/conflicted-study.json"],
        **assessments,
    )

    assert envelope["decision"] == "BLOCKED"
    assert envelope["blocking_reasons"] == ["conflict_open"]


def test_verifier_rejects_tampered_decision_and_unknown_fields() -> None:
    envelope = build_evidence_envelope(
        research_id="research:tampered-study",
        usage_intent="RESEARCH_ONLY",
        adoption_mode="REQUIRED_NOW",
    )
    tampered = deepcopy(envelope)
    tampered["decision"] = "READY"
    tampered["unexpected"] = True

    report = verify_evidence_envelope(tampered)

    assert report["status"] == "FAILED"
    assert "top_level_shape" in report["failed_checks"]
    assert "decision_matches_recomputed" in report["failed_checks"]


def test_verifier_rejects_nonportable_evidence_and_invalid_time() -> None:
    assessments = _complete_assessments()
    assessments["temporal_scope"]["as_of"] = "2026-07-20"
    envelope = build_evidence_envelope(
        research_id="research:portable-study",
        usage_intent="MODEL_INPUT",
        adoption_mode="CHECK_ON_REUSE",
        evidence_refs=["docs/evidence/portable-study.json"],
        **_complete_assessments(),
    )
    envelope["evidence_refs"] = ["/tmp/private-evidence.json"]
    envelope["temporal_scope"] = assessments["temporal_scope"]

    report = verify_evidence_envelope(envelope)

    assert report["status"] == "FAILED"
    assert "evidence_refs_repo_relative" in report["failed_checks"]
    assert "temporal_scope_timestamp" in report["failed_checks"]
