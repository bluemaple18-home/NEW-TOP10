"""既有 autonomous runner 的 native Research Spine lifecycle adapter。"""

from __future__ import annotations

import hashlib
import json
import math
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from app.research.contracts import (
    CANONICALIZATION_VERSION,
    TERMINAL_CAUSE_POLICY_VERSION,
    content_hash,
    requested_executed_differences,
    select_terminal_cause,
    validate_attempt_started,
    validate_research_intent,
    validate_orphan_reconciliation,
    validate_run_receipt,
    validate_trial_spec,
)
from app.research.dataset_bundle import (
    RESOLVED,
    build_dataset_bundle,
    component_diff_paths,
    publish_dataset_bundle_manifest,
    validate_requested_executed_bundle_refs,
)
from app.research.parameter_catalog import parameter_catalog_hash
from app.research.receipt_store import corpus_path, publish_file_to_cas, write_immutable_json


SAFETY = {
    "does_not_train_model": True,
    "does_not_change_production_ranking": True,
    "production_promotion_allowed": False,
}


@dataclass(frozen=True)
class AttemptContext:
    root: Path
    run_id: str
    intent_id: str
    attempt_event_id: str
    started_at: str
    trial_specs: dict[str, dict[str, Any]]
    requested: dict[str, Any]
    trial_ids_by_role: dict[str, list[str]]
    requested_dataset_bundle_id: str = ""
    requested_dataset_bundle_manifest_ref: str = ""
    requested_dataset_bundle_manifest: dict[str, Any] | None = None


def reconcile_orphan_attempts(
    corpus_root: Path,
    *,
    observed_at: datetime | None = None,
    minimum_age_seconds: int = 86_400,
) -> list[Path]:
    """將逾時且沒有terminal receipt的attempt標成UNKNOWN orphan；不猜執行事實。"""
    now = observed_at or datetime.now(timezone.utc)
    written: list[Path] = []
    for attempt_path in sorted((corpus_root / "attempts").glob("*.started.json")):
        try:
            attempt = json.loads(attempt_path.read_text(encoding="utf-8"))
            started = datetime.fromisoformat(str(attempt["started_at"]).replace("Z", "+00:00"))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            continue
        run_id = str(attempt.get("run_id") or "")
        if not run_id or (corpus_root / "receipts" / f"{run_id}.json").exists():
            continue
        if (now - started).total_seconds() < minimum_age_seconds:
            continue
        payload = {
            "schema_version": "research-orphan-reconciliation.v1",
            "run_id": run_id,
            "intent_id": attempt.get("intent_id"),
            "attempt_event_id": attempt.get("attempt_event_id"),
            "observed_at": now.isoformat(),
            "reconciliation_policy_version": "attempt-timeout-24h.v1",
            "status": "ORPHANED_ATTEMPT",
            "sealed_usage_status": "UNKNOWN",
            "facts_unknown": [
                "executed_parameters",
                "executed_lineage",
                "executed_dataset_bundle",
                "result",
            ],
        }
        target = corpus_path(corpus_root, "reconciliations", run_id, suffix=".orphan.json")
        write_immutable_json(
            target,
            payload,
            validator=validate_orphan_reconciliation,
            identity_field="run_id",
        )
        written.append(target)
    return written


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _source_manifest(path: Path, *, max_files: int | None = None) -> dict[str, Any]:
    if not path.exists():
        return {"resolution_status": "UNRESOLVED", "files": []}
    if path.is_file():
        return {
            "resolution_status": "RESOLVED",
            "files": [{"name": path.name, "hash": _sha256_file(path)}],
        }
    files = sorted(item for item in path.glob("ranking_*.csv") if item.is_file())
    if max_files:
        files = files[-max_files:]
    return {
        "resolution_status": "RESOLVED" if files else "UNRESOLVED",
        "files": [{"name": item.name, "hash": _sha256_file(item)} for item in files],
    }


def _bundle_coverage(file_count: int) -> dict[str, Any]:
    return {
        "schema_version": "dataset-component-coverage.v1",
        "status": "COMPLETE" if file_count > 0 else "EMPTY",
        "expected_member_count": file_count,
        "observed_member_count": file_count,
        "date_start": "1970-01-01" if file_count > 0 else None,
        "date_end": "1970-01-01" if file_count > 0 else None,
    }


def _strategy_matrix_dataset_bundle(source_manifest: dict[str, Any]) -> dict[str, Any]:
    files = source_manifest.get("files")
    if (
        source_manifest.get("resolution_status") != "RESOLVED"
        or not isinstance(files, list)
        or len(files) != 1
        or not _valid_hash((files[0] if files else {}).get("hash"))
    ):
        raise ValueError("REQUESTED_DATASET_BUNDLE_INVALID")
    return build_dataset_bundle(
        consumer_id="STRATEGY_MATRIX_FEATURES_V1",
        contract_version="strategy-matrix-features.v1",
        components=[
            {
                "role": "FEATURES_ARTIFACT",
                "member_key": "primary",
                "identity_kind": "FEATURES_ARTIFACT_V1",
                "content_id": files[0]["hash"],
                "resolution_status": RESOLVED,
                "format_contract": "features-artifact.v1",
                "coverage": _bundle_coverage(1),
            }
        ],
        transformation_identity={
            "contract_version": "strategy-matrix-source-adapter.v1",
            "git_blob_ids": ["git-sha1:" + "0" * 40],
        },
        resolution_semantics={
            "fallback_policy_version": "dataset-resolution-policy.v1",
            "identity_bearing_absence_is_explicit": True,
        },
    )


def _manifest_ref(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _dataset_binding_envelope(
    requested_manifest: dict[str, Any],
    executed_manifest: dict[str, Any],
    *,
    requested_ref: str,
    executed_ref: str,
    evidence_refs: list[str],
) -> dict[str, Any]:
    requested_id = str(requested_manifest["dataset_bundle_id"])
    executed_id = str(executed_manifest["dataset_bundle_id"])
    binding = {
        "requested_dataset_bundle_id": requested_id,
        "requested_dataset_bundle_manifest_ref": requested_ref,
        "executed_dataset_bundle_id": executed_id,
        "executed_dataset_bundle_manifest_ref": executed_ref,
        "validation_status": "VALID",
    }
    envelope: dict[str, Any] = {
        "requested_dataset_bundle_id": requested_id,
        "executed_dataset_bundle_id": executed_id,
    }
    if requested_id != executed_id:
        paths = component_diff_paths(requested_manifest, executed_manifest)
        if all(path.startswith("/transformation_identity/") for path in paths):
            reason_code = "TRANSFORMATION_CHANGE"
        elif all("/coverage/" in path for path in paths):
            reason_code = "COVERAGE_RECONCILIATION"
        else:
            reason_code = "SOURCE_FALLBACK"
        delta = {
            "reason_code": reason_code,
            "changed_identity_paths": paths,
            "changed_roles": sorted({
                path.split("/", 3)[2].split(":", 1)[0]
                for path in paths
                if path.startswith("/components/") and ":" in path.split("/", 3)[2]
            }),
            "resolution_authority": "dataset-resolution-policy.v1",
            "requested_manifest_id": requested_id,
            "executed_manifest_id": executed_id,
            "evidence_refs": sorted(set(evidence_refs)),
        }
        if reason_code == "SOURCE_FALLBACK":
            delta["transition_profile_version"] = "m4-training-source-fallback.v1"
        binding["resolution_delta"] = delta
        envelope["resolution_delta"] = delta
    result = validate_requested_executed_bundle_refs(envelope, requested_manifest, executed_manifest)
    if result.status != "VALID":
        raise ValueError("DATASET_BUNDLE_BINDING_INVALID:" + "; ".join(result.errors))
    return binding


def _not_executed_bundle_binding(context: AttemptContext) -> dict[str, Any]:
    return {
        "requested_dataset_bundle_id": context.requested_dataset_bundle_id,
        "requested_dataset_bundle_manifest_ref": context.requested_dataset_bundle_manifest_ref,
        "executed_dataset_bundle_id": "UNKNOWN",
        "executed_dataset_bundle_manifest_ref": "UNKNOWN",
        "validation_status": "NOT_EXECUTED",
    }


def _status_evidence(
    candidate: Mapping[str, Any],
    *,
    status: str,
    reason_code: str,
    observed_at: str,
    observer: str,
) -> dict[str, Any] | None:
    """補齊受控 terminal status 必備的一手 cause evidence。"""
    supplied = candidate.get("status_evidence")
    if isinstance(supplied, Mapping):
        return dict(supplied)
    if status == "CANCELLED":
        return {
            "cancellation_request_id": str(
                candidate.get("cancellation_request_id")
                or content_hash({
                    "run_id": candidate.get("run_id"),
                    "status": status,
                    "reason_code": reason_code,
                    "observed_at": observed_at,
                })
            ),
            "accepted_at": str(candidate.get("accepted_at") or observed_at),
            "typed_reason": reason_code,
        }
    if status == "TIMED_OUT":
        return {
            "deadline_at": str(candidate.get("deadline_at") or observed_at),
            "timeout_policy_version": str(
                candidate.get("timeout_policy_version") or "attempt-deadline.v1"
            ),
            "observer_id": str(candidate.get("observer_id") or observer),
        }
    if status == "ABORTED":
        return {
            "abort_initiator": str(candidate.get("abort_initiator") or observer),
            "invariant": reason_code,
            "supervisor_id": str(candidate.get("supervisor_id") or observer),
        }
    return None


def _terminal_cause_candidate(
    candidate: Mapping[str, Any],
    *,
    default_status: str,
    default_reason_code: str,
    default_observed_at: str,
    default_observer: str,
) -> dict[str, Any]:
    status = str(candidate.get("status") or default_status)
    reason_code = str(candidate.get("reason_code") or default_reason_code)
    observed_at = str(candidate.get("observed_at") or default_observed_at)
    observer = str(candidate.get("observer") or default_observer)
    runner_started = candidate.get("runner_started")
    normalized: dict[str, Any] = {
        "status": status,
        "reason_code": reason_code,
        "observed_at": observed_at,
        "observer": observer,
        "runner_started": runner_started if isinstance(runner_started, bool) else status != "REJECTED_BEFORE_EXECUTION",
        "evidence_refs": list(candidate.get("evidence_refs") or []),
    }
    status_evidence = _status_evidence(
        candidate,
        status=status,
        reason_code=reason_code,
        observed_at=observed_at,
        observer=observer,
    )
    if status_evidence is not None:
        normalized["status_evidence"] = status_evidence
    return normalized


def begin_topic_attempt(
    *,
    corpus_root: Path,
    project_root: Path,
    topic: Any,
    scenarios: list[dict[str, Any]],
    research_stage: str,
    regime_scope: dict[str, Any],
    features_path: str,
    execution_settings: dict[str, Any],
    selection_reason_codes: list[str] | None = None,
    research_batch_id: str = "UNSCOPED",
) -> AttemptContext:
    dataset_manifest = _source_manifest((project_root / features_path).resolve())
    dataset_hash = str(
        (dataset_manifest.get("files") or [{}])[0].get("hash")
        or content_hash(dataset_manifest)
    )
    requested_bundle_manifest = _strategy_matrix_dataset_bundle(dataset_manifest)
    requested_bundle_write = publish_dataset_bundle_manifest(corpus_root, requested_bundle_manifest)
    requested_bundle_id = str(requested_bundle_manifest["dataset_bundle_id"])
    requested_bundle_ref = _manifest_ref(requested_bundle_write.path, corpus_root)
    specs: dict[str, dict[str, Any]] = {}
    parameters_by_trial: dict[str, dict[str, Any]] = {}
    trial_ids_by_role: dict[str, list[str]] = {"baseline": [], "candidate": []}
    for role, ranking_dir in (("baseline", topic.baseline_dir), ("candidate", topic.candidate_dir)):
        ranking_manifest = _source_manifest(
            (project_root / ranking_dir).resolve(),
            max_files=int(execution_settings.get("max_ranking_files") or 0) or None,
        )
        ranking_hash = content_hash(ranking_manifest)
        for scenario in scenarios:
            parameters = {
                **scenario,
                "regime_gate": None,
                "risk_guard": None,
                "entry_filter": None,
            }
            spec: dict[str, Any] = {
                "schema_version": "research-trial-spec.v1",
                "canonicalization_version": CANONICALIZATION_VERSION,
                "trial_spec_id": "sha256:" + "0" * 64,
                "topic_id": topic.topic_id,
                "topic_family_id": topic.topic_id.split(":", 1)[0],
                "parameter_catalog_version": "research-parameter-catalog.v1",
                "parameter_catalog_hash": parameter_catalog_hash(),
                "parameters": parameters,
                "research_stage": research_stage,
                "regime_scope": regime_scope,
                "dataset_authority": {"dataset_hash": dataset_hash},
                "ranking_source_authority": {"ranking_source_hash": ranking_hash},
                "execution_profile": {
                    "runner": "strategy_matrix_comparison",
                    "profile": topic.validation_profile,
                    "variant_role": role,
                    "execution_settings": execution_settings,
                    "dataset_manifest": dataset_manifest,
                    "ranking_manifest": ranking_manifest,
                },
                "safety": SAFETY,
            }
            spec["trial_spec_id"] = content_hash(spec, omit={"trial_spec_id"})
            trial_id = str(spec["trial_spec_id"])
            specs[trial_id] = spec
            parameters_by_trial[trial_id] = parameters
            trial_ids_by_role[role].append(trial_id)
            write_immutable_json(
                corpus_path(corpus_root, "trial_specs", trial_id),
                spec,
                validator=validate_trial_spec,
                identity_field="trial_spec_id",
            )

    intent_id = "intent-" + uuid.uuid4().hex
    run_id = "run-" + uuid.uuid4().hex
    started_at = datetime.now(timezone.utc).isoformat()
    trial_ids = sorted(specs)
    intent = {
        "schema_version": "research-intent.v1",
        "intent_id": intent_id,
        "requested_trial_spec_ids": trial_ids,
        "requested_dataset_bundle_id": requested_bundle_id,
        "requested_dataset_bundle_manifest_ref": requested_bundle_ref,
        "requested_at": started_at,
        "request_source": "existing_autonomous_manager",
        "selection_reason": {
            "reason_codes": selection_reason_codes or ["EXISTING_MANAGER_SELECTION"],
            "research_batch_id": research_batch_id,
        },
    }
    write_immutable_json(
        corpus_path(corpus_root, "intents", intent_id),
        intent,
        validator=validate_research_intent,
        identity_field="intent_id",
    )
    attempt: dict[str, Any] = {
        "schema_version": "research-run-attempt-started.v1",
        "attempt_event_id": "sha256:" + "0" * 64,
        "run_id": run_id,
        "intent_id": intent_id,
        "requested_trial_spec_ids": trial_ids,
        "requested_dataset_bundle_id": requested_bundle_id,
        "requested_dataset_bundle_manifest_ref": requested_bundle_ref,
        "started_at": started_at,
        "executor": {
            "runner_id": "autonomous-research",
            "runner_version": "v1",
            "research_batch_id": research_batch_id,
        },
        "invocation_hash": content_hash({"topic_id": topic.topic_id, "trial_spec_ids": trial_ids}),
    }
    attempt["attempt_event_id"] = content_hash(attempt, omit={"attempt_event_id"})
    write_immutable_json(
        corpus_path(corpus_root, "attempts", run_id, suffix=".started.json"),
        attempt,
        validator=validate_attempt_started,
        identity_field="run_id",
    )
    requested = {
        "trial_spec_ids": trial_ids,
        "dataset_bundle_id": requested_bundle_id,
        "dataset_bundle_manifest_ref": requested_bundle_ref,
        "parameters_by_trial": parameters_by_trial,
        "research_stage": research_stage,
        "regime_scope": regime_scope,
        "dataset_authority": {"dataset_hash": dataset_hash},
        "ranking_source_authority_by_trial": {
            trial_id: spec["ranking_source_authority"] for trial_id, spec in specs.items()
        },
        "execution_profile_by_trial": {
            trial_id: spec["execution_profile"] for trial_id, spec in specs.items()
        },
    }
    return AttemptContext(
        corpus_root,
        run_id,
        intent_id,
        str(attempt["attempt_event_id"]),
        started_at,
        specs,
        requested,
        trial_ids_by_role,
        requested_bundle_id,
        requested_bundle_ref,
        requested_bundle_manifest,
    )


def _artifact_error(artifact: dict[str, str], reason_code: str) -> dict[str, str]:
    return {**artifact, "validation_status": "INVALID", "reason_code": reason_code}


def _valid_manifest(value: object) -> bool:
    if not isinstance(value, dict) or value.get("resolution_status") != "RESOLVED":
        return False
    files = value.get("files")
    return bool(files) and all(
        isinstance(item, dict)
        and isinstance(item.get("name"), str)
        and bool(item["name"])
        and _valid_hash(item.get("hash"))
        for item in files
    )


def _valid_hash(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", value) is not None


def _canonical_value(value: Any) -> bool:
    try:
        content_hash({"value": value})
    except (TypeError, ValueError):
        return False
    return not isinstance(value, float) or math.isfinite(value)


def _regime_id(value: object) -> str | None:
    if not isinstance(value, dict):
        return None
    if isinstance(value.get("regime_id"), str):
        return value["regime_id"]
    base = value.get("base_regime")
    tags = value.get("family_tags")
    if not isinstance(base, str) or not isinstance(tags, list):
        return None
    return f"{base}|{'+'.join(sorted(str(tag) for tag in tags))}"


def _resolution_values(receipt: dict[str, Any], field: str) -> tuple[Any, Any]:
    requested = receipt["requested"]
    if field == "artifact_set":
        return "NO_INVALID_ARTIFACTS", [item["reason_code"] for item in receipt["artifact_errors"]]
    if field == "dataset_bundle":
        binding = receipt["bundle_binding"]
        return (
            {
                "dataset_bundle_id": binding["requested_dataset_bundle_id"],
                "dataset_bundle_manifest_ref": binding["requested_dataset_bundle_manifest_ref"],
            },
            {
                "dataset_bundle_id": binding["executed_dataset_bundle_id"],
                "dataset_bundle_manifest_ref": binding["executed_dataset_bundle_manifest_ref"],
            },
        )
    if field == "trial_spec_ids":
        return requested["trial_spec_ids"], [
            unit["requested_trial_spec_id"] for unit in receipt["executed_units"]
        ]
    if "." in field:
        root, trial_id = field.split(".", 1)
        unit = next(
            item for item in receipt["executed_units"]
            if item["requested_trial_spec_id"] == trial_id
        )
        mapping = {
            "executed_trial_spec_id": (trial_id, unit["executed_trial_spec_id"]),
            "parameters_by_trial": (
                requested["parameters_by_trial"][trial_id], unit["executed_parameters"]
            ),
            "ranking_source_authority_by_trial": (
                requested["ranking_source_authority_by_trial"][trial_id],
                {"ranking_source_hash": unit["executed_ranking_source_hash"]},
            ),
            "execution_profile_by_trial": (
                requested["execution_profile_by_trial"][trial_id],
                unit["executed_execution_profile"],
            ),
        }
        return mapping[root]
    unit = receipt["executed_units"][0]
    mapping = {
        "research_stage": (requested["research_stage"], unit["executed_research_stage"]),
        "regime_scope": (requested["regime_scope"], unit["executed_regime_scope"]),
        "dataset_authority": (
            requested["dataset_authority"], {"dataset_hash": unit["executed_dataset_hash"]}
        ),
    }
    return mapping[field]


def finish_topic_attempt(
    context: AttemptContext,
    *,
    terminal_status: str,
    matrix_paths: list[Path],
    lineage_authority_paths: list[Path] | None = None,
    failure_reason: str | None = None,
    completed_at: datetime | None = None,
    terminal_cause_candidates: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    units: list[dict[str, Any]] = []
    artifacts: list[dict[str, str]] = []
    artifact_errors: list[dict[str, str]] = []
    seen_roles: set[str] = set()
    trusted_development: dict[str, Any] | None = None
    trusted_artifact_id: str | None = None
    for authority_path in lineage_authority_paths or []:
        if not authority_path.is_file():
            continue
        try:
            authority_id, authority_cas = publish_file_to_cas(context.root, authority_path)
            authority_payload = json.loads(authority_cas.read_text(encoding="utf-8"))
        except Exception:
            continue
        if (
            authority_payload.get("research_stage") == "DEVELOPMENT_SCREEN"
            and authority_payload.get("boundary", {}).get("sealed_data_read_allowed") is False
            and authority_payload.get("boundary", {}).get("exact_match_required") is True
            and isinstance(authority_payload.get("development_episode_ids"), list)
            and authority_payload.get("development_episode_ids")
            and _valid_hash(authority_payload.get("dataset_hash"))
            and _valid_hash(authority_payload.get("execution_dataset_hash"))
            and _valid_hash(authority_payload.get("split_artifact_hash"))
            and _valid_hash(authority_payload.get("research_contract_hash"))
            and _valid_hash(authority_payload.get("regime_history_hash"))
        ):
            trusted_development = authority_payload
            trusted_artifact_id = authority_id
            trusted_record = {
                "artifact_id": authority_id,
                "corpus_path": authority_cas.relative_to(context.root).as_posix(),
                "provenance_path": authority_path.as_posix(),
                "validation_status": "VALID",
            }
            if not any(item["artifact_id"] == authority_id for item in artifacts):
                artifacts.append(trusted_record)
    lookup = {
        (spec["execution_profile"]["variant_role"], json.dumps(spec["parameters"], sort_keys=True)):
        (trial_id, spec)
        for trial_id, spec in context.trial_specs.items()
    }
    for source in matrix_paths:
        if not source.is_file():
            continue
        try:
            artifact_id, cas_path = publish_file_to_cas(context.root, source)
        except Exception:
            continue
        artifact = {
            "artifact_id": artifact_id,
            "corpus_path": cas_path.relative_to(context.root).as_posix(),
            "provenance_path": source.as_posix(),
            "validation_status": "INVALID",
        }
        if not any(item["artifact_id"] == artifact_id for item in artifacts):
            artifacts.append(artifact)
        try:
            matrix = json.loads(cas_path.read_text(encoding="utf-8"))
        except Exception as error:
            artifact_errors.append(_artifact_error(artifact, type(error).__name__.upper()))
            continue
        spine = matrix.get("research_spine") or {}
        role = str(spine.get("variant_role") or "")
        expected_ids = sorted(context.trial_ids_by_role.get(role) or [])
        if (
            role not in context.trial_ids_by_role
            or role in seen_roles
            or spine.get("run_id") != context.run_id
            or spine.get("intent_id") != context.intent_id
            or sorted(spine.get("requested_trial_spec_ids") or []) != expected_ids
        ):
            artifact_errors.append(_artifact_error(artifact, "ATTEMPT_CORRELATION_MISMATCH"))
            continue
        seen_roles.add(role)
        prepared: list[tuple[
            str,
            dict[str, Any],
            dict[str, Any],
            dict[str, Any],
            dict[str, Any],
            str,
        ]] = []
        observed: set[str] = set()
        reasons: set[str] = set()
        for row in matrix.get("scenarios") or []:
            parameters = {
                key: row.get(key)
                for key in ("horizon", "stop_loss_pct", "take_profit_pct", "max_group_exposure")
            }
            parameters.update({"regime_gate": None, "risk_guard": None, "entry_filter": None})
            matched = lookup.get((role, json.dumps(parameters, sort_keys=True)))
            if matched is None:
                reasons.add("UNEXPECTED_SCENARIO")
                continue
            trial_id, spec = matched
            if trial_id in observed:
                reasons.add("DUPLICATE_SCENARIO")
                continue
            observed.add(trial_id)
            authority = row.get("execution_authority") or {}
            required = {
                "research_stage", "regime_scope", "episode_ids", "episode_authority_hash",
                "episode_authority", "dataset_hash", "dataset_manifest", "ranking_manifest",
                "execution_settings",
            }
            if (
                set(authority) != required
                or not isinstance(authority.get("research_stage"), str)
                or not authority["research_stage"].strip()
                or not _valid_hash(authority.get("dataset_hash"))
                or not _valid_hash(authority.get("episode_authority_hash"))
                or not isinstance(authority.get("episode_authority"), dict)
                or not isinstance(authority.get("execution_settings"), dict)
                or not isinstance(authority.get("regime_scope"), dict)
                or _regime_id(authority.get("regime_scope")) is None
                or not isinstance(authority.get("episode_ids"), list)
                or not authority["episode_ids"]
                or any(
                    not isinstance(episode_id, str) or not episode_id.strip()
                    for episode_id in authority["episode_ids"]
                )
                or len(authority["episode_ids"]) != len(set(authority["episode_ids"]))
                or not _canonical_value(authority.get("execution_settings"))
            ):
                reasons.add("INCOMPLETE_EXECUTION_AUTHORITY")
                continue
            if not _valid_manifest(authority.get("ranking_manifest")):
                reasons.add("UNRESOLVED_RANKING_MANIFEST")
                continue
            if not _valid_manifest(authority.get("dataset_manifest")):
                reasons.add("UNRESOLVED_DATASET_MANIFEST")
                continue
            dataset_files = authority["dataset_manifest"]["files"]
            if len(dataset_files) != 1 or dataset_files[0]["hash"] != authority["dataset_hash"]:
                reasons.add("DATASET_AUTHORITY_MISMATCH")
                continue
            if content_hash(authority["episode_authority"]) != authority["episode_authority_hash"]:
                reasons.add("EPISODE_AUTHORITY_HASH_MISMATCH")
                continue
            try:
                executed_bundle_manifest = _strategy_matrix_dataset_bundle(authority["dataset_manifest"])
                executed_bundle_write = publish_dataset_bundle_manifest(
                    context.root,
                    executed_bundle_manifest,
                )
                _dataset_binding_envelope(
                    context.requested_dataset_bundle_manifest or {},
                    executed_bundle_manifest,
                    requested_ref=context.requested_dataset_bundle_manifest_ref,
                    executed_ref=_manifest_ref(executed_bundle_write.path, context.root),
                    evidence_refs=[artifact_id],
                )
            except ValueError:
                reasons.add("DATASET_BUNDLE_BINDING_INVALID")
                continue
            prepared.append((
                trial_id,
                spec,
                parameters,
                authority,
                executed_bundle_manifest,
                _manifest_ref(executed_bundle_write.path, context.root),
            ))
        if observed != set(expected_ids):
            reasons.add("MISSING_SCENARIO")
        if reasons or len(prepared) != len(expected_ids):
            artifact_errors.append(_artifact_error(artifact, sorted(reasons)[0]))
            continue
        artifact["validation_status"] = "VALID"
        candidate_units: list[dict[str, Any]] = []
        try:
            for trial_id, requested_spec, parameters, authority, executed_bundle_manifest, executed_bundle_ref in prepared:
                actual_profile = {
                    "runner": "strategy_matrix_comparison",
                    "profile": requested_spec["execution_profile"]["profile"],
                    "variant_role": role,
                    "execution_settings": authority["execution_settings"],
                    "dataset_manifest": authority["dataset_manifest"],
                    "ranking_manifest": authority["ranking_manifest"],
                }
                executed_spec = {
                    **requested_spec,
                    "trial_spec_id": "sha256:" + "0" * 64,
                    "research_stage": authority["research_stage"],
                    "regime_scope": authority["regime_scope"],
                    "dataset_authority": {"dataset_hash": authority["dataset_hash"]},
                    "ranking_source_authority": {
                        "ranking_source_hash": content_hash(authority["ranking_manifest"])
                    },
                    "execution_profile": actual_profile,
                }
                executed_spec["trial_spec_id"] = content_hash(
                    executed_spec, omit={"trial_spec_id"}
                )
                executed_id = str(executed_spec["trial_spec_id"])
                write_immutable_json(
                    corpus_path(context.root, "trial_specs", executed_id),
                    executed_spec,
                    validator=validate_trial_spec,
                    identity_field="trial_spec_id",
                )
                matrix_contract = matrix.get("contract") or {}
                episode_authority = authority["episode_authority"]
                proven_development = (
                    authority["research_stage"] == "DEVELOPMENT_SCREEN"
                    and matrix_contract.get("development_only") is True
                    and matrix_contract.get("sealed_data_read_allowed") is False
                    and episode_authority.get("ok") is True
                    and episode_authority.get("reason_code") == "DEVELOPMENT_EPISODES_ONLY"
                    and set(authority["episode_ids"]).issubset(
                        set(episode_authority.get("development_episode_ids") or [])
                    )
                    and trusted_development is not None
                    and trusted_artifact_id is not None
                    and trusted_development.get("topic_id") == requested_spec["topic_id"]
                    and trusted_development.get("regime_id")
                    == _regime_id(authority["regime_scope"])
                    and trusted_development.get("execution_dataset_hash")
                    == authority["dataset_hash"]
                    and set(authority["episode_ids"]).issubset(
                        set(trusted_development.get("development_episode_ids") or [])
                    )
                )
                sealed = "PROVEN_NON_SEALED" if proven_development else "UNKNOWN"
                resolution = "VALID" if proven_development else "INVALID_LINEAGE"
                facts = {
                    "sealed_usage_status": sealed,
                    "research_stage": authority["research_stage"],
                    "dataset_hash": authority["dataset_hash"],
                    "ranking_source_hash": executed_spec["ranking_source_authority"]["ranking_source_hash"],
                    "regime_scope": authority["regime_scope"],
                    "episode_ids": authority["episode_ids"],
                }
                candidate_units.append({
                    "execution_unit_id": content_hash({"run_id": context.run_id, "trial_id": executed_id}),
                    "requested_trial_spec_id": trial_id,
                    "executed_trial_spec_id": executed_id,
                    "executed_parameters": parameters,
                    "executed_research_stage": authority["research_stage"],
                    "executed_regime_scope": authority["regime_scope"],
                    "executed_dataset_hash": authority["dataset_hash"],
                    "executed_dataset_bundle_id": executed_bundle_manifest["dataset_bundle_id"],
                    "executed_dataset_bundle_manifest_ref": executed_bundle_ref,
                    "executed_ranking_source_hash": executed_spec["ranking_source_authority"]["ranking_source_hash"],
                    "executed_execution_profile": actual_profile,
                    "lineage": {
                        "lineage_id": content_hash(facts),
                        "sealed_usage_status": sealed,
                        "episode_ids": authority["episode_ids"],
                        "episode_authority_hash": authority["episode_authority_hash"],
                    },
                    "lineage_assertions": [
                        {
                            "authority": "strategy-matrix-execution-authority",
                            "authority_hash": artifact_id,
                            "facts": facts,
                        },
                        *(
                            [{
                                "authority": "development-split-authority",
                                "authority_hash": trusted_artifact_id,
                                "facts": {
                                    "sealed_usage_status": sealed,
                                    "research_stage": authority["research_stage"],
                                    "dataset_hash": authority["dataset_hash"],
                                    "regime_scope": authority["regime_scope"],
                                    "episode_ids": authority["episode_ids"],
                                },
                            }]
                            if proven_development and trusted_artifact_id
                            else []
                        ),
                    ],
                    "lineage_resolution_status": resolution,
                    "artifact_refs": [
                        artifact_id,
                        *([trusted_artifact_id] if proven_development and trusted_artifact_id else []),
                    ],
                })
        except Exception as error:
            artifact["validation_status"] = "INVALID"
            artifact_errors.append(_artifact_error(artifact, type(error).__name__.upper()))
            continue
        units.extend(candidate_units)

    complete = len(units) == len(context.trial_specs) and not artifact_errors
    completed = completed_at or datetime.now(timezone.utc)
    if completed.tzinfo is None:
        completed = completed.replace(tzinfo=timezone.utc)
    completed_iso = completed.isoformat()
    derived_status = terminal_status
    derived_reason = (
        "RUNNER_COMPLETED" if terminal_status == "SUCCEEDED"
        else failure_reason or "RUNTIME_FAILURE"
    )
    if terminal_status == "SUCCEEDED" and not complete:
        derived_status = "FAILED"
        derived_reason = "INCOMPLETE_EXECUTION_FACTS"
    candidates = [
        _terminal_cause_candidate(
            candidate,
            default_status=derived_status,
            default_reason_code=derived_reason,
            default_observed_at=completed_iso,
            default_observer="controlled-executor",
        )
        for candidate in (terminal_cause_candidates or [])
    ]
    derived_candidate = _terminal_cause_candidate(
        {"run_id": context.run_id},
        default_status=derived_status,
        default_reason_code=derived_reason,
        default_observed_at=completed_iso,
        default_observer="controlled-executor",
    )
    candidates.append(derived_candidate)
    selected_cause = select_terminal_cause(candidates)
    if selected_cause["status"] == "SUCCEEDED" and not complete:
        selected_cause = derived_candidate
    terminal_status = str(selected_cause["status"])
    cause_reason = str(selected_cause["reason_code"])
    observation = (
        "OBSERVED" if complete else "PARTIALLY_OBSERVED" if units else
        "NOT_STARTED" if terminal_status == "REJECTED_BEFORE_EXECUTION" else "UNKNOWN"
    )
    if units:
        bundle_binding = {
            "requested_dataset_bundle_id": context.requested_dataset_bundle_id,
            "requested_dataset_bundle_manifest_ref": context.requested_dataset_bundle_manifest_ref,
            "executed_dataset_bundle_id": units[0]["executed_dataset_bundle_id"],
            "executed_dataset_bundle_manifest_ref": units[0]["executed_dataset_bundle_manifest_ref"],
            "validation_status": "VALID",
        }
        if bundle_binding["requested_dataset_bundle_id"] != bundle_binding["executed_dataset_bundle_id"]:
            executed_manifest_path = context.root / bundle_binding["executed_dataset_bundle_manifest_ref"]
            executed_manifest = json.loads(executed_manifest_path.read_text(encoding="utf-8"))
            bundle_binding = _dataset_binding_envelope(
                context.requested_dataset_bundle_manifest or {},
                executed_manifest,
                requested_ref=context.requested_dataset_bundle_manifest_ref,
                executed_ref=bundle_binding["executed_dataset_bundle_manifest_ref"],
                evidence_refs=[
                    str(ref)
                    for unit in units
                    for ref in unit.get("artifact_refs", [])
                    if _valid_hash(ref)
                ],
            )
    else:
        bundle_binding = _not_executed_bundle_binding(context)
    cause_evidence_refs = sorted({
        *(
            str(item.get("artifact_id"))
            for item in [*artifacts, *artifact_errors]
            if _valid_hash(item.get("artifact_id"))
        ),
        *(
            str(ref)
            for ref in selected_cause.get("evidence_refs", [])
            if _valid_hash(ref)
        ),
        content_hash(
            {
                "run_id": context.run_id,
                "terminal_status": terminal_status,
                "reason_code": cause_reason,
            }
        ),
    })
    terminal_cause: dict[str, Any] = {
        "policy_version": TERMINAL_CAUSE_POLICY_VERSION,
        "status": terminal_status,
        "reason_code": cause_reason,
        "observed_at": selected_cause["observed_at"],
        "observer": selected_cause["observer"],
        "runner_started": selected_cause["runner_started"],
        "evidence_refs": cause_evidence_refs,
    }
    if "status_evidence" in selected_cause:
        terminal_cause["status_evidence"] = selected_cause["status_evidence"]
    receipt: dict[str, Any] = {
        "schema_version": "research-run-receipt.v1",
        "run_id": context.run_id,
        "intent_id": context.intent_id,
        "receipt_id": "sha256:" + "0" * 64,
        "attempt_event_id": context.attempt_event_id,
        "writer_version": "research-receipt-writer.v1",
        "terminal_status": terminal_status,
        "started_at": context.started_at,
        "completed_at": completed_iso,
        "terminal_cause": terminal_cause,
        "bundle_binding": bundle_binding,
        "requested": context.requested,
        "executed_units": units,
        "resolution_events": [],
        "identity_match_status": "NOT_EXECUTED",
        "execution_observation_status": observation,
        "artifacts": artifacts,
        "artifact_errors": artifact_errors,
        "safety": SAFETY,
    }
    differences = requested_executed_differences(receipt) if units else set()
    receipt["resolution_events"] = [
        {
            "reason_code": "REQUESTED_EXECUTED_DIFFERENCE",
            "field": field,
            "requested": _resolution_values(receipt, field)[0],
            "executed": _resolution_values(receipt, field)[1],
        }
        for field in sorted(differences)
    ]
    receipt["identity_match_status"] = (
        "EXACT" if units and not differences else "EXPLAINED_MISMATCH" if units else "NOT_EXECUTED"
    )
    if terminal_status != "SUCCEEDED":
        receipt["failure"] = {"reason_code": cause_reason}
    receipt["receipt_id"] = content_hash(receipt, omit={"receipt_id"})
    write_immutable_json(
        corpus_path(context.root, "receipts", context.run_id),
        receipt,
        validator=validate_run_receipt,
        identity_field="run_id",
    )
    return receipt
