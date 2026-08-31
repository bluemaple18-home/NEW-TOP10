from __future__ import annotations

from copy import deepcopy

import pytest

from app.research.contracts import content_hash, validate_attempt_started
from app.research.receipt_store import (
    ImmutableCollisionError,
    SchemaValidationError,
    corpus_path,
    write_immutable_json,
)


def digest(label: str) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(label.encode()).hexdigest()


def attempt() -> dict:
    payload = {
        "schema_version": "research-run-attempt-started.v1",
        "attempt_event_id": digest("placeholder"),
        "run_id": "run-1",
        "intent_id": "intent-1",
        "requested_trial_spec_ids": [digest("trial")],
        "requested_dataset_bundle_id": digest("bundle"),
        "requested_dataset_bundle_manifest_ref": f"dataset_bundles/{digest('bundle')[7:]}.json",
        "started_at": "2026-08-14T00:00:00+00:00",
        "executor": {"runner_id": "autonomous", "runner_version": "v1"},
        "invocation_hash": digest("invocation"),
    }
    payload["attempt_event_id"] = content_hash(payload, omit={"attempt_event_id"})
    return payload


def test_immutable_writer_is_idempotent_and_collision_safe(tmp_path) -> None:
    payload = attempt()
    target = corpus_path(tmp_path, "attempts", payload["run_id"], suffix=".started.json")
    assert write_immutable_json(target, payload, validator=validate_attempt_started, identity_field="run_id").status == "CREATED"
    original = target.read_bytes()
    assert write_immutable_json(target, payload, validator=validate_attempt_started, identity_field="run_id").status == "EXISTS_IDENTICAL"

    changed = deepcopy(payload)
    changed["intent_id"] = "mutated"
    changed["attempt_event_id"] = content_hash(changed, omit={"attempt_event_id"})
    with pytest.raises(ImmutableCollisionError):
        write_immutable_json(target, changed, validator=validate_attempt_started, identity_field="run_id")
    assert target.read_bytes() == original


def test_invalid_payload_never_creates_target(tmp_path) -> None:
    target = corpus_path(tmp_path, "attempts", "run-1", suffix=".started.json")
    with pytest.raises(SchemaValidationError):
        write_immutable_json(target, {"bad": True}, validator=validate_attempt_started)
    assert not target.exists()


@pytest.mark.parametrize("identity", ["", ".", "..", "../escape", "a/b", "a\\b"])
def test_identity_path_rejects_traversal(tmp_path, identity: str) -> None:
    with pytest.raises(ValueError):
        corpus_path(tmp_path, "attempts", identity)


def test_entity_and_body_identity_are_bound_to_path(tmp_path) -> None:
    with pytest.raises(ValueError):
        corpus_path(tmp_path, "../escape", "run-1")
    payload = attempt()
    wrong = corpus_path(tmp_path, "attempts", "run-2", suffix=".started.json")
    with pytest.raises(ValueError, match="does not match run_id"):
        write_immutable_json(wrong, payload, validator=validate_attempt_started, identity_field="run_id")
