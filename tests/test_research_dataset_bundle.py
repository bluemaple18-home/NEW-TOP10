from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from app.research.receipt_store import ImmutableCollisionError
from app.research.dataset_bundle import (
    ABSENT_BY_CONTRACT,
    ABSENT_USE_ALL_FEATURE_STOCKS,
    EMPTY_USE_ALL_FEATURE_STOCKS,
    FEATURES_ARTIFACT_V1,
    LEGACY_DIAGNOSTIC_ONLY,
    RESOLVED,
    build_dataset_bundle,
    component_diff_paths,
    legacy_dataset_hash_identity,
    publish_dataset_bundle_manifest,
    recompute_dataset_bundle_id,
    validate_dataset_bundle,
    validate_fundamentals_snapshot,
    validate_requested_executed_bundle_refs,
)


SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64
SHA_C = "sha256:" + "c" * 64
SHA_D = "sha256:" + "d" * 64
SHA_E = "sha256:" + "e" * 64
SHA_F = "sha256:" + "f" * 64
SHA_1 = "sha256:" + "1" * 64
SHA_2 = "sha256:" + "2" * 64
SHA_3 = "sha256:" + "3" * 64
GIT_A = "git-sha1:" + "a" * 40
GIT_B = "git-sha1:" + "b" * 40


def coverage(status: str = "COMPLETE", *, expected: int = 2, observed: int = 2) -> dict[str, object]:
    return {
        "schema_version": "dataset-component-coverage.v1",
        "status": status,
        "expected_member_count": expected,
        "observed_member_count": observed,
        "date_start": "2026-08-01",
        "date_end": "2026-08-30",
    }


def absent_coverage() -> dict[str, object]:
    return {
        "schema_version": "dataset-component-coverage.v1",
        "status": "NOT_APPLICABLE",
        "expected_member_count": None,
        "observed_member_count": 0,
        "date_start": None,
        "date_end": None,
    }


def empty_coverage() -> dict[str, object]:
    return {
        "schema_version": "dataset-component-coverage.v1",
        "status": "EMPTY",
        "expected_member_count": 0,
        "observed_member_count": 0,
        "date_start": None,
        "date_end": None,
    }


def fundamentals_snapshot(content_id: str = SHA_D) -> dict[str, object]:
    payload = {
        "snapshot_content_id": content_id,
        "schema_version": "research-fundamentals-snapshot.v1",
        "canonicalization_version": "research-canonical-json.v1",
        "identity_kind": "FUNDAMENTALS_SNAPSHOT_V1",
        "as_of": "2026-08-30",
        "coverage": {
            "universe_content_id": SHA_1,
            "expected_member_count": 2,
            "observed_member_count": 2,
            "date_start": "2026-06-30",
            "date_end": "2026-08-30",
            "status": "COMPLETE",
        },
        "missing_value_semantics": {
            "policy": "PRESERVE_NULL",
            "version": "fundamentals-missing.v1",
        },
        "records_contract": {
            "schema_version": "fundamentals-records.v1",
            "normalization_version": "fundamentals-normalization.v1",
        },
        "records_content_id": SHA_2,
    }
    payload["snapshot_content_id"] = validate_fundamentals_snapshot(payload).content_id
    return payload


def resolved(role: str, content_id: str, *, component_coverage: dict[str, object] | None = None) -> dict[str, object]:
    identity_kind = {
        "FEATURES_ARTIFACT": "FEATURES_ARTIFACT_V1",
        "EVENTS_ARTIFACT": "EVENTS_ARTIFACT_V1",
        "SIGNALS_CONFIG": "SIGNALS_CONFIG_V1",
        "FUNDAMENTALS_SNAPSHOT": "FUNDAMENTALS_SNAPSHOT_V1",
        "UNIVERSE_ARTIFACT": "UNIVERSE_ARTIFACT_V1",
    }[role]
    return {
        "role": role,
        "member_key": "primary",
        "identity_kind": identity_kind,
        "content_id": content_id,
        "resolution_status": RESOLVED,
        "format_contract": f"{role.lower()}.v1",
        "coverage": component_coverage or coverage(),
    }


def absent_events() -> dict[str, object]:
    return {
        "role": "EVENTS_ARTIFACT",
        "member_key": "primary",
        "identity_kind": "EVENTS_ARTIFACT_V1",
        "resolution_status": ABSENT_BY_CONTRACT,
        "semantic_absence_code": "OPTIONAL_COMPONENT_NOT_PRESENT",
        "coverage": absent_coverage(),
    }


def ranking_universe_absent() -> dict[str, object]:
    return {
        "role": "UNIVERSE_ARTIFACT",
        "member_key": "primary",
        "identity_kind": "UNIVERSE_ARTIFACT_V1",
        "resolution_status": ABSENT_USE_ALL_FEATURE_STOCKS,
        "semantic_absence_code": "UNIVERSE_NOT_PRESENT_USE_ALL_FEATURE_STOCKS",
        "coverage": absent_coverage(),
    }


def ranking_universe_empty() -> dict[str, object]:
    return {
        "role": "UNIVERSE_ARTIFACT",
        "member_key": "primary",
        "identity_kind": "UNIVERSE_ARTIFACT_V1",
        "content_id": SHA_E,
        "resolution_status": EMPTY_USE_ALL_FEATURE_STOCKS,
        "format_contract": "universe.v1",
        "coverage": empty_coverage(),
        "member_count": 0,
    }


def m4_training_manifest(*, features: str = SHA_A, events: dict[str, object] | None = None, signals: str = SHA_C, snapshot: dict[str, object] | None = None) -> dict[str, object]:
    snapshot = snapshot or fundamentals_snapshot()
    return build_dataset_bundle(
        consumer_id="M4_TRAINING_V1",
        contract_version="m4-training-dataset.v1",
        components=[
            resolved("SIGNALS_CONFIG", signals),
            {
                **resolved(
                    "FUNDAMENTALS_SNAPSHOT",
                    snapshot["snapshot_content_id"],
                    component_coverage=snapshot["coverage"],
                ),
                "format_contract": "research-fundamentals-snapshot.v1",
            },
            events or absent_events(),
            resolved("FEATURES_ARTIFACT", features),
        ],
        transformation_identity={
            "contract_version": "m4-transform.v1",
            "git_blob_ids": [GIT_B, GIT_A],
        },
        resolution_semantics={
            "fallback_policy_version": "dataset-resolution-policy.v1",
            "identity_bearing_absence_is_explicit": True,
        },
        fundamentals_snapshots={"primary": snapshot},
    )


def m4_ranking_manifest(universe: dict[str, object]) -> dict[str, object]:
    snapshot = fundamentals_snapshot()
    return build_dataset_bundle(
        consumer_id="M4_RANKING_V1",
        contract_version="m4-ranking-dataset.v1",
        components=[
            resolved("FEATURES_ARTIFACT", SHA_A),
            absent_events(),
            resolved("SIGNALS_CONFIG", SHA_C),
            {
                **resolved(
                    "FUNDAMENTALS_SNAPSHOT",
                    snapshot["snapshot_content_id"],
                    component_coverage=snapshot["coverage"],
                ),
                "format_contract": "research-fundamentals-snapshot.v1",
            },
            universe,
        ],
        transformation_identity={
            "contract_version": "m4-transform.v1",
            "git_blob_ids": [GIT_A],
        },
        resolution_semantics={
            "fallback_policy_version": "dataset-resolution-policy.v1",
            "identity_bearing_absence_is_explicit": True,
        },
        fundamentals_snapshots={"primary": snapshot},
    )


def component_by_role(manifest: dict[str, object], role: str) -> dict[str, object]:
    components = manifest["identity_payload"]["components"]
    return next(component for component in components if component["role"] == role)


def snapshot_map() -> dict[str, dict[str, object]]:
    return {"primary": fundamentals_snapshot()}


def test_a1_sc_001_identity_is_path_and_order_independent() -> None:
    first = m4_training_manifest()
    reordered = build_dataset_bundle(
        consumer_id="M4_TRAINING_V1",
        contract_version="m4-training-dataset.v1",
        components=list(reversed(first["identity_payload"]["components"])),
        transformation_identity={
            "git_blob_ids": list(reversed(first["identity_payload"]["transformation_identity"]["git_blob_ids"])),
            "contract_version": "m4-transform.v1",
        },
        resolution_semantics=first["identity_payload"]["resolution_semantics"],
        fundamentals_snapshots={"primary": fundamentals_snapshot()},
        metadata={"path": "/tmp/not-identity-bearing/features.parquet"},
    )

    assert reordered["dataset_bundle_id"] == first["dataset_bundle_id"]
    assert validate_dataset_bundle(reordered, fundamentals_snapshots=snapshot_map()).status == "EXECUTABLE"


def test_a1_sc_002_identity_changes_on_identity_bearing_drift() -> None:
    base = m4_training_manifest()
    assert m4_training_manifest(features=SHA_B)["dataset_bundle_id"] != base["dataset_bundle_id"]
    changed = deepcopy(base)
    changed["identity_payload"]["components"][0]["coverage"] = coverage("PARTIAL", expected=2, observed=1)
    changed["dataset_bundle_id"] = recompute_dataset_bundle_id(changed)
    assert changed["dataset_bundle_id"] != base["dataset_bundle_id"]
    blob_changed = deepcopy(base)
    blob_changed["identity_payload"]["transformation_identity"]["git_blob_ids"] = [GIT_A]
    blob_changed["dataset_bundle_id"] = recompute_dataset_bundle_id(blob_changed)
    assert blob_changed["dataset_bundle_id"] != base["dataset_bundle_id"]


@pytest.mark.parametrize(
    "mutate, expected",
    [
        (lambda m: m["identity_payload"].update({"extra": True}), "identity_payload.extra is not allowed"),
        (lambda m: m["identity_payload"]["components"].append(deepcopy(m["identity_payload"]["components"][0])), "component keys must be unique"),
        (lambda m: m["identity_payload"]["components"][0].update({"role": "UNKNOWN"}), "components[0].role is unsupported"),
        (lambda m: component_by_role(m, "FEATURES_ARTIFACT").update({"content_id": "features.parquet"}), "content_id must be sha256"),
        (lambda m: component_by_role(m, "EVENTS_ARTIFACT").update({"content_id": SHA_B}), "content_id is not allowed"),
        (lambda m: m["identity_payload"].update({"components": [c for c in m["identity_payload"]["components"] if c["role"] != "FEATURES_ARTIFACT"]}), "consumer role FEATURES_ARTIFACT must have exactly one record"),
    ],
)
def test_a1_sc_003_schema_and_matrix_fail_closed(mutate, expected: str) -> None:
    manifest = m4_training_manifest()
    mutate(manifest)
    result = validate_dataset_bundle(manifest, fundamentals_snapshots=snapshot_map())
    assert result.status == "NOT_EXECUTABLE"
    assert any(expected in error for error in result.errors)


@pytest.mark.parametrize(
    ("manifest", "role", "bad_coverage"),
    [
        (m4_training_manifest(), "FEATURES_ARTIFACT", absent_coverage()),
        (m4_training_manifest(), "EVENTS_ARTIFACT", coverage()),
        (m4_ranking_manifest(ranking_universe_absent()), "UNIVERSE_ARTIFACT", coverage()),
        (m4_ranking_manifest(ranking_universe_empty()), "UNIVERSE_ARTIFACT", coverage()),
    ],
    ids=[
        "resolved-rejects-not-applicable",
        "absent-by-contract-requires-not-applicable",
        "absent-use-all-requires-not-applicable",
        "empty-use-all-requires-empty",
    ],
)
def test_a1_sc_003_coverage_is_bound_to_resolution_variant(
    manifest: dict[str, object],
    role: str,
    bad_coverage: dict[str, object],
) -> None:
    component_by_role(manifest, role)["coverage"] = bad_coverage
    result = validate_dataset_bundle(manifest, fundamentals_snapshots=snapshot_map())
    assert result.status == "NOT_EXECUTABLE"
    assert any("coverage.status is not allowed for resolution variant" in error for error in result.errors)


def test_a1_sc_003_malformed_git_blob_ids_fail_closed_without_crashing() -> None:
    manifest = m4_training_manifest()
    manifest["identity_payload"]["transformation_identity"]["git_blob_ids"] = [{}]
    result = validate_dataset_bundle(manifest, fundamentals_snapshots=snapshot_map())
    assert result.status == "NOT_EXECUTABLE"
    assert "transformation_identity.git_blob_ids entries must be strings" in result.errors


@pytest.mark.parametrize("field", ["changed_identity_paths", "changed_roles", "evidence_refs"])
def test_a1_sc_008_malformed_delta_lists_fail_closed_without_crashing(field: str) -> None:
    requested = m4_training_manifest(features=SHA_A)
    executed = m4_training_manifest(features=SHA_B)
    delta = valid_delta("SOURCE_FALLBACK", requested, executed, extra={field: [{}]})
    result = validate_requested_executed_bundle_refs(
        refs_envelope(requested, executed, delta),
        requested,
        executed,
        requested_fundamentals_snapshots=snapshot_map(),
        executed_fundamentals_snapshots=snapshot_map(),
    )
    assert result.status == "INVALID"
    assert f"resolution_delta.{field} entries must be strings" in result.errors


def test_a1_sc_004_fundamentals_snapshot_golden_and_bundle_binding() -> None:
    golden = {
        "snapshot_content_id": "sha256:82f3aedc1b54e2df0064c6accc7f767231c8c98e4c7e1000a955535741fb02b5",
        "schema_version": "research-fundamentals-snapshot.v1",
        "canonicalization_version": "research-canonical-json.v1",
        "identity_kind": "FUNDAMENTALS_SNAPSHOT_V1",
        "as_of": "2026-08-30",
        "coverage": {
            "universe_content_id": "sha256:" + "1" * 64,
            "expected_member_count": 2,
            "observed_member_count": 2,
            "date_start": "2026-06-30",
            "date_end": "2026-08-30",
            "status": "COMPLETE",
        },
        "missing_value_semantics": {
            "policy": "PRESERVE_NULL",
            "version": "fundamentals-missing.v1",
        },
        "records_contract": {
            "schema_version": "fundamentals-records.v1",
            "normalization_version": "fundamentals-normalization.v1",
        },
        "records_content_id": "sha256:" + "2" * 64,
    }
    assert validate_fundamentals_snapshot(golden).content_id == golden["snapshot_content_id"]

    manifest = m4_training_manifest(snapshot=golden)
    assert validate_dataset_bundle(manifest).status == "NOT_EXECUTABLE"
    manifest["identity_payload"]["components"][2]["content_id"] = SHA_F
    result = validate_dataset_bundle(manifest, fundamentals_snapshots={"primary": golden})
    assert result.status == "NOT_EXECUTABLE"
    assert "fundamentals content_id must match snapshot_content_id" in result.errors


def test_a1_sc_004_impossible_calendar_dates_fail_closed() -> None:
    component_bad = m4_training_manifest()
    component_by_role(component_bad, "FEATURES_ARTIFACT")["coverage"]["date_start"] = "2026-02-31"
    assert validate_dataset_bundle(component_bad, fundamentals_snapshots=snapshot_map()).status == "NOT_EXECUTABLE"

    snapshot_bad = fundamentals_snapshot()
    snapshot_bad["as_of"] = "2026-00-01"
    assert validate_fundamentals_snapshot(snapshot_bad).status == "INVALID"

    snapshot_bad = fundamentals_snapshot()
    snapshot_bad["coverage"]["date_end"] = "2026-02-31"
    assert validate_fundamentals_snapshot(snapshot_bad).status == "INVALID"


def test_a1_sc_005_ranking_universe_absent_empty_and_resolved_are_distinct() -> None:
    absent = m4_ranking_manifest(ranking_universe_absent())
    empty = m4_ranking_manifest(ranking_universe_empty())
    resolved_universe = m4_ranking_manifest(resolved("UNIVERSE_ARTIFACT", SHA_F))

    assert len({absent["dataset_bundle_id"], empty["dataset_bundle_id"], resolved_universe["dataset_bundle_id"]}) == 3
    assert "content_id" not in absent["identity_payload"]["components"][-1]
    assert empty["identity_payload"]["components"][-1]["member_count"] == 0


def test_a1_sc_006_training_fallback_uses_content_not_path_identity() -> None:
    production = m4_training_manifest(features=SHA_A)
    fallback = m4_training_manifest(features=SHA_B)
    same_fallback_different_path = build_dataset_bundle(
        consumer_id="M4_TRAINING_V1",
        contract_version="m4-training-dataset.v1",
        components=fallback["identity_payload"]["components"],
        transformation_identity=fallback["identity_payload"]["transformation_identity"],
        resolution_semantics=fallback["identity_payload"]["resolution_semantics"],
        fundamentals_snapshots={"primary": fundamentals_snapshot()},
        metadata={"path": "/another/path/features.parquet"},
    )
    assert production["dataset_bundle_id"] != fallback["dataset_bundle_id"]
    assert same_fallback_different_path["dataset_bundle_id"] == fallback["dataset_bundle_id"]


def test_a1_sc_007_legacy_hash_bridge_never_synthesizes_bundle_id() -> None:
    bridged = legacy_dataset_hash_identity(SHA_A)
    assert bridged == {
        "identity_kind": FEATURES_ARTIFACT_V1,
        "content_id": SHA_A,
        "eligibility": LEGACY_DIAGNOSTIC_ONLY,
        "dataset_bundle_id": None,
    }


def test_a1_sc_008_requested_executed_atomic_training_fallback() -> None:
    requested = m4_training_manifest(features=SHA_A)
    target_snapshot = fundamentals_snapshot()
    target_snapshot["records_content_id"] = SHA_E
    target_snapshot["snapshot_content_id"] = validate_fundamentals_snapshot(target_snapshot).content_id
    executed = m4_training_manifest(features=SHA_B, events=absent_events(), snapshot=target_snapshot)
    expected_paths = component_diff_paths(requested, executed)
    envelope = {
        "requested_dataset_bundle_id": requested["dataset_bundle_id"],
        "executed_dataset_bundle_id": executed["dataset_bundle_id"],
        "resolution_delta": {
            "reason_code": "SOURCE_FALLBACK",
            "transition_profile_version": "m4-training-source-fallback.v1",
            "changed_identity_paths": expected_paths,
            "changed_roles": ["FEATURES_ARTIFACT", "FUNDAMENTALS_SNAPSHOT"],
            "resolution_authority": "dataset-resolution-policy.v1",
            "requested_manifest_id": requested["dataset_bundle_id"],
            "executed_manifest_id": executed["dataset_bundle_id"],
            "evidence_refs": [SHA_C],
        },
    }
    assert validate_requested_executed_bundle_refs(
        envelope,
        requested,
        executed,
        requested_fundamentals_snapshots=snapshot_map(),
        executed_fundamentals_snapshots={"primary": target_snapshot},
    ).status == "VALID"

    envelope["resolution_delta"]["changed_identity_paths"] = expected_paths[:-1]
    assert validate_requested_executed_bundle_refs(
        envelope,
        requested,
        executed,
        requested_fundamentals_snapshots=snapshot_map(),
        executed_fundamentals_snapshots={"primary": target_snapshot},
    ).status == "INVALID"


def test_a1_sc_008_rejects_invalid_or_stale_manifests_before_delta() -> None:
    requested = m4_training_manifest(features=SHA_A)
    executed = m4_training_manifest(features=SHA_B)
    paths = component_diff_paths(requested, executed)
    envelope = {
        "requested_dataset_bundle_id": requested["dataset_bundle_id"],
        "executed_dataset_bundle_id": executed["dataset_bundle_id"],
        "resolution_delta": {
            "reason_code": "SOURCE_FALLBACK",
            "transition_profile_version": "m4-training-source-fallback.v1",
            "changed_identity_paths": paths,
            "changed_roles": ["FEATURES_ARTIFACT"],
            "resolution_authority": "dataset-resolution-policy.v1",
            "requested_manifest_id": requested["dataset_bundle_id"],
            "executed_manifest_id": executed["dataset_bundle_id"],
            "evidence_refs": [SHA_C],
        },
    }

    stale = deepcopy(executed)
    stale["dataset_bundle_id"] = SHA_F
    assert validate_requested_executed_bundle_refs(
        envelope,
        requested,
        stale,
        requested_fundamentals_snapshots=snapshot_map(),
        executed_fundamentals_snapshots=snapshot_map(),
    ).status == "INVALID"

    envelope["resolution_delta"]["changed_identity_paths"] = [{}]
    result = validate_requested_executed_bundle_refs(
        envelope,
        requested,
        executed,
        requested_fundamentals_snapshots=snapshot_map(),
        executed_fundamentals_snapshots=snapshot_map(),
    )
    assert result.status == "INVALID"


def valid_delta(
    reason_code: str,
    requested: dict[str, object],
    executed: dict[str, object],
    *,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    payload = {
        "reason_code": reason_code,
        "changed_identity_paths": component_diff_paths(requested, executed),
        "changed_roles": [
            path.split("/", 3)[2].split(":", 1)[0]
            for path in component_diff_paths(requested, executed)
            if path.startswith("/components/")
        ],
        "resolution_authority": "dataset-resolution-policy.v1",
        "requested_manifest_id": requested["dataset_bundle_id"],
        "executed_manifest_id": executed["dataset_bundle_id"],
        "evidence_refs": [SHA_C],
    }
    payload["changed_roles"] = sorted(set(payload["changed_roles"]))
    if extra:
        payload.update(extra)
    return payload


def refs_envelope(
    requested: dict[str, object],
    executed: dict[str, object],
    delta: dict[str, object] | None,
) -> dict[str, object]:
    envelope = {
        "requested_dataset_bundle_id": requested["dataset_bundle_id"],
        "executed_dataset_bundle_id": executed["dataset_bundle_id"],
    }
    if delta is not None:
        envelope["resolution_delta"] = delta
    return envelope


def test_a1_sc_008_exact_match_requires_no_delta_and_mismatch_requires_delta() -> None:
    requested = m4_training_manifest()
    assert validate_requested_executed_bundle_refs(
        refs_envelope(requested, requested, None),
        requested,
        requested,
        requested_fundamentals_snapshots=snapshot_map(),
        executed_fundamentals_snapshots=snapshot_map(),
    ).status == "VALID"

    with_delta = refs_envelope(requested, requested, valid_delta("TRANSFORMATION_CHANGE", requested, requested))
    assert validate_requested_executed_bundle_refs(
        with_delta,
        requested,
        requested,
        requested_fundamentals_snapshots=snapshot_map(),
        executed_fundamentals_snapshots=snapshot_map(),
    ).status == "INVALID"

    executed = m4_training_manifest(features=SHA_B)
    assert validate_requested_executed_bundle_refs(
        refs_envelope(requested, executed, None),
        requested,
        executed,
        requested_fundamentals_snapshots=snapshot_map(),
        executed_fundamentals_snapshots=snapshot_map(),
    ).status == "INVALID"


def test_a1_sc_008_source_unavailable_coverage_transform_and_policy_reasons() -> None:
    requested = m4_training_manifest(events=resolved("EVENTS_ARTIFACT", SHA_E))
    unavailable = m4_training_manifest(events=absent_events())
    unavailable_delta = valid_delta("SOURCE_UNAVAILABLE", requested, unavailable)
    assert validate_requested_executed_bundle_refs(
        refs_envelope(requested, unavailable, unavailable_delta),
        requested,
        unavailable,
        requested_fundamentals_snapshots=snapshot_map(),
        executed_fundamentals_snapshots=snapshot_map(),
    ).status == "VALID"

    coverage_changed = deepcopy(requested)
    component_by_role(coverage_changed, "FEATURES_ARTIFACT")["coverage"] = coverage("PARTIAL", expected=2, observed=1)
    coverage_changed["dataset_bundle_id"] = recompute_dataset_bundle_id(coverage_changed)
    coverage_delta = valid_delta("COVERAGE_RECONCILIATION", requested, coverage_changed)
    assert validate_requested_executed_bundle_refs(
        refs_envelope(requested, coverage_changed, coverage_delta),
        requested,
        coverage_changed,
        requested_fundamentals_snapshots=snapshot_map(),
        executed_fundamentals_snapshots=snapshot_map(),
    ).status == "VALID"

    transform_changed = deepcopy(requested)
    transform_changed["identity_payload"]["transformation_identity"]["git_blob_ids"] = [GIT_A]
    transform_changed["dataset_bundle_id"] = recompute_dataset_bundle_id(transform_changed)
    transform_delta = valid_delta("TRANSFORMATION_CHANGE", requested, transform_changed)
    assert validate_requested_executed_bundle_refs(
        refs_envelope(requested, transform_changed, transform_delta),
        requested,
        transform_changed,
        requested_fundamentals_snapshots=snapshot_map(),
        executed_fundamentals_snapshots=snapshot_map(),
    ).status == "VALID"

    policy_changed = deepcopy(requested)
    policy_changed["identity_payload"]["resolution_semantics"]["fallback_policy_version"] = "dataset-resolution-policy.v2"
    policy_changed["dataset_bundle_id"] = recompute_dataset_bundle_id(policy_changed)
    policy_delta = valid_delta("RESOLUTION_POLICY_CHANGE", requested, policy_changed)
    assert validate_requested_executed_bundle_refs(
        refs_envelope(requested, policy_changed, policy_delta),
        requested,
        policy_changed,
        requested_fundamentals_snapshots=snapshot_map(),
        executed_fundamentals_snapshots=snapshot_map(),
    ).status == "VALID"


def test_a1_sc_008_rejects_unsupported_fallback_and_signal_change() -> None:
    requested = m4_training_manifest(features=SHA_A)
    executed = m4_training_manifest(features=SHA_B, signals=SHA_F)
    paths = component_diff_paths(requested, executed)
    envelope = {
        "requested_dataset_bundle_id": requested["dataset_bundle_id"],
        "executed_dataset_bundle_id": executed["dataset_bundle_id"],
        "resolution_delta": {
            "reason_code": "SOURCE_FALLBACK",
            "transition_profile_version": "m4-training-source-fallback.v1",
            "changed_identity_paths": paths,
            "changed_roles": ["FEATURES_ARTIFACT", "SIGNALS_CONFIG"],
            "resolution_authority": "dataset-resolution-policy.v1",
            "requested_manifest_id": requested["dataset_bundle_id"],
            "executed_manifest_id": executed["dataset_bundle_id"],
            "evidence_refs": [SHA_C],
        },
    }
    assert validate_requested_executed_bundle_refs(envelope, requested, executed).status == "INVALID"

    ranking_requested = m4_ranking_manifest(ranking_universe_absent())
    ranking_executed = m4_ranking_manifest(ranking_universe_empty())
    ranking_envelope = deepcopy(envelope)
    ranking_envelope["requested_dataset_bundle_id"] = ranking_requested["dataset_bundle_id"]
    ranking_envelope["executed_dataset_bundle_id"] = ranking_executed["dataset_bundle_id"]
    ranking_envelope["resolution_delta"]["requested_manifest_id"] = ranking_requested["dataset_bundle_id"]
    ranking_envelope["resolution_delta"]["executed_manifest_id"] = ranking_executed["dataset_bundle_id"]
    ranking_envelope["resolution_delta"]["changed_identity_paths"] = component_diff_paths(ranking_requested, ranking_executed)
    ranking_envelope["resolution_delta"]["changed_roles"] = ["UNIVERSE_ARTIFACT"]
    assert validate_requested_executed_bundle_refs(ranking_envelope, ranking_requested, ranking_executed).status == "INVALID"


def test_a1_sc_009_immutable_manifest_round_trip_rebuilds_without_projection(tmp_path: Path) -> None:
    manifest = m4_training_manifest()
    result = publish_dataset_bundle_manifest(tmp_path, manifest, fundamentals_snapshots=snapshot_map())
    loaded = result.path.read_text(encoding="utf-8")
    assert result.status == "CREATED"
    assert publish_dataset_bundle_manifest(tmp_path, manifest, fundamentals_snapshots=snapshot_map()).status == "EXISTS_IDENTICAL"
    assert manifest["dataset_bundle_id"][7:] in result.path.name
    assert validate_dataset_bundle(manifest, fundamentals_snapshots=snapshot_map()).status == "EXECUTABLE"
    assert recompute_dataset_bundle_id(__import__("json").loads(loaded)) == manifest["dataset_bundle_id"]

    result.path.write_text('{"corrupt":true}\n', encoding="utf-8")
    with pytest.raises(ImmutableCollisionError):
        publish_dataset_bundle_manifest(tmp_path, manifest, fundamentals_snapshots=snapshot_map())


def test_a1_sc_010_runtime_writer_contracts_are_not_mutated() -> None:
    import app.research.run_receipts as run_receipts

    assert not hasattr(run_receipts, "dataset_bundle_id")
