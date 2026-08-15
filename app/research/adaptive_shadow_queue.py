"""Adaptive research shadow queue projection；只產生可稽核影子優先序。"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from app.research.contracts import content_hash
from app.research.native_evidence_replay import verify_bundle
from app.research.parameter_learning import classify_matched_contrasts
from app.research.receipt_store import write_immutable_json


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "adaptive-shadow-queue.v1"
COMPARISON_SCHEMA_VERSION = "adaptive-shadow-queue-comparison.v1"
VERIFICATION_SCHEMA_VERSION = "adaptive-shadow-queue-verification.v1"
DEFAULT_POLICY = PROJECT_ROOT / "config/research_shadow_queue_policy_v1.json"
DEFAULT_POLICY_RELATIVE = Path("config/research_shadow_queue_policy_v1.json")
DEFAULT_BUNDLE = (
    PROJECT_ROOT
    / "docs/evidence/CARD-NEW-TOP10-NATIVE-EVIDENCE-REPLAY-BUNDLE-V1/bundle.json"
)
DEFAULT_BUNDLE_RELATIVE = Path(
    "docs/evidence/CARD-NEW-TOP10-NATIVE-EVIDENCE-REPLAY-BUNDLE-V1/bundle.json"
)
DEFAULT_MANIFEST = (
    PROJECT_ROOT
    / "docs/evidence/CARD-NEW-TOP10-NATIVE-EVIDENCE-REPLAY-BUNDLE-V1/manifest.json"
)
DEFAULT_MANIFEST_RELATIVE = Path(
    "docs/evidence/CARD-NEW-TOP10-NATIVE-EVIDENCE-REPLAY-BUNDLE-V1/manifest.json"
)
DEFAULT_OUTPUT_ROOT = (
    PROJECT_ROOT
    / "docs/evidence/CARD-NEW-TOP10-ADAPTIVE-SHADOW-QUEUE-V1-RETRY-1"
)
DEFAULT_OUTPUT_ROOT_RELATIVE = Path(
    "docs/evidence/CARD-NEW-TOP10-ADAPTIVE-SHADOW-QUEUE-V1-RETRY-1"
)
DEFAULT_CANONICAL_QUEUE = (
    PROJECT_ROOT / "artifacts/autonomous_research/next_action_queue.json"
)
DEFAULT_CANONICAL_QUEUE_RELATIVE = Path(
    "artifacts/autonomous_research/next_action_queue.json"
)
DEFAULT_PROJECTION_RELATIVE = DEFAULT_OUTPUT_ROOT_RELATIVE / "adaptive_shadow_queue_projection.json"
EXPECTED_INPUT_FILE_SHA256 = {
    "bundle": "sha256:d18d64df3d0614bd6c717e16ab175bcce61d504d8e8e72adfb1319e822c85400",
    "manifest": "sha256:eebe754cc802e10584ff341ef2c6e06272bb90b7ea943ffd6cf1ac0c52532514",
    "policy": "sha256:5d39a8c771f93d42e20ea573098a5567a0aff361a4981c13724489eb360f4537",
}
EXPECTED_POLICY_HASH = "sha256:cd9737434aa65ad64f57424d39286b63f1abdad528f8bc6bf47ed2d344dd25f1"
EXPECTED_PRIORITY_BANDS = [
    {
        "band": "HIGH",
        "directions": ["HIGHER_LOOKS_BETTER", "LOWER_LOOKS_BETTER"],
        "min_matched_contrasts": 3,
        "min_distinct_lineages": 2,
        "forbidden_flags": [
            "INSUFFICIENT_EVIDENCE",
            "UNSTABLE",
            "SHARP_PEAK",
            "OVERFIT_RISK",
            "RISK_RETURN_TRADEOFF",
        ],
    },
    {
        "band": "OBSERVE",
        "directions": [
            "FLAT",
            "NON_MONOTONIC",
            "INTERIOR_PEAK",
            "UNSTABLE",
            "INSUFFICIENT_EVIDENCE",
        ],
        "min_matched_contrasts": 0,
        "min_distinct_lineages": 0,
        "forbidden_flags": [],
    },
]
EXPECTED_ACTIONS = {
    "HIGHER_LOOKS_BETTER": "RESEARCH_PARAMETER_EXTENSION_UPWARD",
    "LOWER_LOOKS_BETTER": "RESEARCH_PARAMETER_EXTENSION_DOWNWARD",
    "FLAT": "OBSERVE_LOW_SENSITIVITY",
    "NON_MONOTONIC": "NO_GO_NON_MONOTONIC",
    "INTERIOR_PEAK": "NO_GO_INTERIOR_PEAK",
    "UNSTABLE": "NO_GO_UNSTABLE",
    "INSUFFICIENT_EVIDENCE": "NO_GO_INSUFFICIENT_EVIDENCE",
}
DISQUALIFY_HIGH = {
    "INSUFFICIENT_EVIDENCE",
    "UNSTABLE",
    "SHARP_PEAK",
    "OVERFIT_RISK",
    "RISK_RETURN_TRADEOFF",
}
FORBIDDEN_SOURCE_MARKERS = ("synthetic", "legacy", "sealed", "unknown")


class ShadowQueueBoundaryError(ValueError):
    """表示 shadow queue 的固定路徑或內容權限邊界被拒絕。"""


def _authorize_exact_repo_path(
    path: Path,
    *,
    expected_relative: Path,
    field: str,
    project_root: Path,
    require_repo_relative: bool,
) -> Path:
    raw = path.as_posix()
    if ".." in PurePosixPath(raw).parts:
        raise ShadowQueueBoundaryError(f"{field}_TRAVERSAL")
    if require_repo_relative and (
        path.is_absolute() or raw != expected_relative.as_posix()
    ):
        raise ShadowQueueBoundaryError(f"{field}_NOT_COMMITTED_PATH")

    expected = project_root / expected_relative
    lexical = path if path.is_absolute() else project_root / path
    if lexical != expected:
        raise ShadowQueueBoundaryError(f"{field}_NOT_COMMITTED_PATH")
    if expected.resolve() != expected.absolute():
        raise ShadowQueueBoundaryError(f"{field}_SYMLINK_ESCAPE")
    return expected


def authorize_committed_input(
    path: Path,
    *,
    kind: str,
    project_root: Path = PROJECT_ROOT,
    require_repo_relative: bool = False,
) -> Path:
    relative_paths = {
        "bundle": DEFAULT_BUNDLE_RELATIVE,
        "manifest": DEFAULT_MANIFEST_RELATIVE,
        "policy": DEFAULT_POLICY_RELATIVE,
    }
    if kind not in relative_paths:
        raise ShadowQueueBoundaryError("INPUT_KIND_INVALID")
    expected = _authorize_exact_repo_path(
        path,
        expected_relative=relative_paths[kind],
        field=f"INPUT_{kind.upper()}",
        project_root=project_root,
        require_repo_relative=require_repo_relative,
    )
    if file_sha256_or_absent(expected) != EXPECTED_INPUT_FILE_SHA256[kind]:
        raise ShadowQueueBoundaryError(f"INPUT_{kind.upper()}_CONTENT_DRIFT")
    return expected


def authorize_canonical_queue_path(
    path: Path,
    *,
    project_root: Path = PROJECT_ROOT,
    require_repo_relative: bool = False,
) -> Path:
    return _authorize_exact_repo_path(
        path,
        expected_relative=DEFAULT_CANONICAL_QUEUE_RELATIVE,
        field="CANONICAL_QUEUE",
        project_root=project_root,
        require_repo_relative=require_repo_relative,
    )


def authorize_projection_path(
    path: Path,
    *,
    project_root: Path = PROJECT_ROOT,
    require_repo_relative: bool = False,
) -> Path:
    return _authorize_exact_repo_path(
        path,
        expected_relative=DEFAULT_PROJECTION_RELATIVE,
        field="PROJECTION",
        project_root=project_root,
        require_repo_relative=require_repo_relative,
    )


def authorize_output_root(
    path: Path,
    *,
    project_root: Path = PROJECT_ROOT,
    require_repo_relative: bool = False,
) -> Path:
    return _authorize_exact_repo_path(
        path,
        expected_relative=DEFAULT_OUTPUT_ROOT_RELATIVE,
        field="OUTPUT_ROOT",
        project_root=project_root,
        require_repo_relative=require_repo_relative,
    )


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return payload


def file_sha256_or_absent(path: Path) -> str:
    if not path.exists():
        return "ABSENT"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def repo_path(path: Path, *, project_root: Path = PROJECT_ROOT) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def _relative_path_errors(value: object, field: str) -> list[str]:
    if not isinstance(value, str) or not value:
        return [f"{field}:INVALID_REPO_RELATIVE_PATH"]
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        return [f"{field}:INVALID_REPO_RELATIVE_PATH"]
    return []


def load_policy(path: Path = DEFAULT_POLICY) -> dict[str, Any]:
    policy = load_json(path)
    required = {"schema_version", "policy_version", "admission", "priority_bands", "actions", "boundary"}
    if set(policy) != required or policy["schema_version"] != "adaptive-shadow-queue-policy.v1":
        raise ValueError("INVALID_SHADOW_QUEUE_POLICY")
    admission = policy["admission"]
    if not isinstance(admission, dict):
        raise ValueError("INVALID_SHADOW_QUEUE_ADMISSION_POLICY")
    expected_admission = {
        "required_cycles",
        "required_receipt_gate_percent",
        "required_distinct_lineages",
        "required_matched_contrasts",
        "required_capacity_status",
        "required_parity_unchanged",
    }
    if set(admission) != expected_admission:
        raise ValueError("INVALID_SHADOW_QUEUE_ADMISSION_FIELDS")
    if admission["required_cycles"] < 2 or admission["required_receipt_gate_percent"] != 100:
        raise ValueError("SHADOW_QUEUE_ADMISSION_WEAKENS_RECEIPT_GATE")
    if admission["required_distinct_lineages"] < 2 or admission["required_matched_contrasts"] < 3:
        raise ValueError("SHADOW_QUEUE_ADMISSION_WEAKENS_EVIDENCE_GATE")
    if admission["required_capacity_status"] != "PASS" or admission["required_parity_unchanged"] is not True:
        raise ValueError("SHADOW_QUEUE_ADMISSION_MUST_REQUIRE_CAPACITY_AND_PARITY")
    boundary = policy["boundary"]
    if boundary != {
        "shadow_only": True,
        "canonical_queue_write_allowed": False,
        "manager_selection_change_allowed": False,
        "scheduler_change_allowed": False,
        "production_change_allowed": False,
        "synthetic_fallback_allowed": False,
        "legacy_fallback_allowed": False,
        "sealed_or_unknown_fallback_allowed": False,
    }:
        raise ValueError("INVALID_SHADOW_QUEUE_BOUNDARY")
    if not isinstance(policy["priority_bands"], list) or not policy["priority_bands"]:
        raise ValueError("INVALID_SHADOW_QUEUE_PRIORITY_BANDS")
    if not isinstance(policy["actions"], dict) or not policy["actions"]:
        raise ValueError("INVALID_SHADOW_QUEUE_ACTIONS")
    if policy["priority_bands"] != EXPECTED_PRIORITY_BANDS:
        raise ValueError("SHADOW_QUEUE_PRIORITY_BANDS_NOT_COMMITTED")
    if policy["actions"] != EXPECTED_ACTIONS:
        raise ValueError("SHADOW_QUEUE_ACTIONS_NOT_COMMITTED")
    return policy


def _bundle_admission_errors(
    bundle: Mapping[str, Any],
    manifest: Mapping[str, Any],
    *,
    bundle_path: Path,
    policy: Mapping[str, Any],
    project_root: Path,
) -> list[str]:
    errors: list[str] = []
    if verify_bundle(bundle, project_root=project_root)["status"] != "PASS":
        errors.append("REPLAY_BUNDLE_VERIFICATION_FAILED")
    if manifest.get("status") != "PASS":
        errors.append("REPLAY_MANIFEST_NOT_PASS")
    if manifest.get("bundle_id") != bundle.get("bundle_id"):
        errors.append("REPLAY_MANIFEST_BUNDLE_ID_MISMATCH")
    if manifest.get("bundle_sha256") != file_sha256_or_absent(bundle_path):
        errors.append("REPLAY_MANIFEST_BUNDLE_HASH_MISMATCH")
    verification = manifest.get("verification") if isinstance(manifest.get("verification"), dict) else {}
    if verification.get("status") != "PASS" or verification.get("bundle_id") != bundle.get("bundle_id"):
        errors.append("REPLAY_MANIFEST_VERIFICATION_NOT_PASS")
    capacity = manifest.get("capacity") if isinstance(manifest.get("capacity"), dict) else {}
    parity = manifest.get("parity") if isinstance(manifest.get("parity"), dict) else {}
    cleanup = manifest.get("cleanup") if isinstance(manifest.get("cleanup"), dict) else {}
    admission = policy["admission"]
    if capacity.get("status") != admission["required_capacity_status"]:
        errors.append("CAPACITY_NOT_PASS")
    if cleanup.get("status") != "PASS":
        errors.append("CLEANUP_NOT_PASS")
    if parity.get("unchanged") is not admission["required_parity_unchanged"]:
        errors.append("PARITY_DRIFT")
    if not (parity.get("before_hash") == parity.get("after_cycles_hash") == parity.get("after_cleanup_hash")):
        errors.append("PARITY_HASH_MISMATCH")
    counts = bundle.get("counts") if isinstance(bundle.get("counts"), dict) else {}
    if counts.get("cycles", 0) < admission["required_cycles"]:
        errors.append("MISSING_TWO_REAL_CYCLES")
    if counts.get("adaptive_eligible", 0) != counts.get("observations", -1):
        errors.append("RECEIPT_GATE_NOT_100_PERCENT")
    if counts.get("distinct_lineages", 0) < admission["required_distinct_lineages"]:
        errors.append("DISTINCT_LINEAGES_INSUFFICIENT")
    if counts.get("matched_contrasts", 0) < admission["required_matched_contrasts"]:
        errors.append("MATCHED_CONTRASTS_INSUFFICIENT")
    if (bundle.get("admission") or {}).get("status") != "PASS":
        errors.append("BUNDLE_ADMISSION_NOT_PASS")
    learning = bundle.get("learning_projection") if isinstance(bundle.get("learning_projection"), dict) else {}
    if learning.get("source_projection_parity") is not True:
        errors.append("LEARNING_SOURCE_PROJECTION_PARITY_FAILED")
    observations = bundle.get("observations") if isinstance(bundle.get("observations"), list) else []
    for index, row in enumerate(observations):
        if not isinstance(row, dict):
            errors.append(f"OBSERVATION_{index}:INVALID_ROW")
            continue
        if row.get("sealed_usage_status") != "PROVEN_NON_SEALED":
            errors.append(f"OBSERVATION_{index}:NON_PROVEN_NON_SEALED")
        if (row.get("eligibility") or {}).get("status") != "ADAPTIVE_ELIGIBLE":
            errors.append(f"OBSERVATION_{index}:NOT_ADAPTIVE_ELIGIBLE")
        source_text = " ".join(
            str(row.get(field) or "")
            for field in ("topic_family_id", "topic_id", "research_stage", "lineage_resolution_status")
        ).lower()
        if any(marker in source_text for marker in FORBIDDEN_SOURCE_MARKERS):
            errors.append(f"OBSERVATION_{index}:FORBIDDEN_SOURCE_MARKER")
    return sorted(set(errors))


def _contrast_support(bundle: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    policy = bundle["policies"]["learning_policy"]
    parameters = list(policy.get("numeric_parameters") or [])
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in bundle.get("observations") or []:
        values = row["parameters"]
        profile = row.get("execution_profile") or {}
        for parameter in parameters:
            value = values.get(parameter)
            if value is None:
                continue
            others = tuple((key, values.get(key)) for key in parameters if key != parameter)
            key = (
                parameter,
                row["topic_family_id"],
                row["regime_id"],
                row["dataset_hash"],
                row["ranking_source_hash"],
                row["research_stage"],
                row["lineage_id"],
                profile.get("variant_role"),
                others,
            )
            groups[key].append({**row, "parameter_value": float(value)})
    support: dict[str, dict[str, Any]] = {}
    supplied = {
        row["contrast_id"]: row
        for row in (bundle.get("learning_projection") or {}).get("matched_contrasts", [])
    }
    for key, rows in groups.items():
        by_value = {row["parameter_value"]: row for row in rows}
        values = sorted(by_value)
        for lower, upper in zip(values, values[1:]):
            low, high = by_value[lower], by_value[upper]
            contrast_id = content_hash(
                {
                    "policy": policy["policy_version"],
                    "parameter": key[0],
                    "low": low["evidence_unit_id"],
                    "high": high["evidence_unit_id"],
                }
            )
            if contrast_id not in supplied:
                continue
            support[contrast_id] = {
                "contrast_id": contrast_id,
                "low_observation_id": low["observation_id"],
                "high_observation_id": high["observation_id"],
                "low_evidence_unit_id": low["evidence_unit_id"],
                "high_evidence_unit_id": high["evidence_unit_id"],
                "lineage_id": key[6],
            }
    return support


def _band_for(
    *,
    direction: str,
    flags: list[str],
    matched_contrasts: int,
    distinct_lineages: int,
    policy: Mapping[str, Any],
) -> str:
    if direction in {"INSUFFICIENT_EVIDENCE", "UNSTABLE"} or DISQUALIFY_HIGH.intersection(flags):
        return "OBSERVE"
    for band in policy["priority_bands"]:
        if direction not in band["directions"]:
            continue
        if matched_contrasts < band["min_matched_contrasts"]:
            continue
        if distinct_lineages < band["min_distinct_lineages"]:
            continue
        if set(flags).intersection(band["forbidden_flags"]):
            continue
        return band["band"]
    return "OBSERVE"


def _row_for_scope(
    *,
    bundle: Mapping[str, Any],
    scope: Mapping[str, Any],
    scope_contrasts: list[dict[str, Any]],
    support_by_contrast: Mapping[str, Mapping[str, Any]],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    learning_policy = bundle["policies"]["learning_policy"]
    parameter = str(scope["parameter"])
    direction = classify_matched_contrasts(
        scope_contrasts,
        learning_policy,
        parameter=parameter,
    )
    flags = sorted(
        {
            "INSUFFICIENT_EVIDENCE"
            for _ in [None]
            if direction["direction"] == "INSUFFICIENT_EVIDENCE"
        }
    )
    matched_contrast_count = int(scope["matched_contrast_count"])
    distinct_lineage_count = int(scope["distinct_lineage_count"])
    band = _band_for(
        direction=direction["direction"],
        flags=flags,
        matched_contrasts=matched_contrast_count,
        distinct_lineages=distinct_lineage_count,
        policy=policy,
    )
    action = policy["actions"].get(direction["direction"], "NO_GO_UNCLASSIFIED_DIRECTION")
    support_rows = [support_by_contrast[row["contrast_id"]] for row in scope_contrasts]
    evidence_unit_ids = sorted(
        {
            evidence_id
            for row in support_rows
            for evidence_id in (row["low_evidence_unit_id"], row["high_evidence_unit_id"])
        }
    )
    observation_ids = sorted(
        {
            observation_id
            for row in support_rows
            for observation_id in (row["low_observation_id"], row["high_observation_id"])
        }
    )
    semantic_action = {
        "parameter": parameter,
        "topic_family_id": scope["topic_family_id"],
        "regime_id": scope["regime_id"],
        "direction": direction["direction"],
        "action": action,
        "matched_contrast_ids": [row["contrast_id"] for row in scope_contrasts],
    }
    row = {
        "row_id": "",
        "semantic_action_id": content_hash(semantic_action),
        "priority_band": band,
        "action": action,
        "scope": {
            "type": "TOPIC_X_REGIME",
            "topic_family_id": scope["topic_family_id"],
            "regime_id": scope["regime_id"],
        },
        "parameter": parameter,
        "direction": direction["direction"],
        "edge_behavior": direction.get("edge_behavior"),
        "next_direction": direction.get("next_direction"),
        "reason_codes": [
            f"DIRECTION_{direction['direction']}",
            f"MATCHED_CONTRASTS_{matched_contrast_count}",
            f"DISTINCT_LINEAGES_{distinct_lineage_count}",
            "OFFICIAL_REPLAY_BUNDLE_VERIFIED",
            "SOURCE_PROJECTION_PARITY_VERIFIED",
        ],
        "flags": flags,
        "evidence_counts": {
            "matched_contrasts": matched_contrast_count,
            "distinct_lineages": distinct_lineage_count,
            "supporting_evidence_units": len(evidence_unit_ids),
            "supporting_observations": len(observation_ids),
        },
        "supporting_evidence_unit_ids": evidence_unit_ids,
        "supporting_observation_ids": observation_ids,
        "supporting_contrast_ids": [row["contrast_id"] for row in scope_contrasts],
        "provenance": {
            "bundle_id": bundle["bundle_id"],
            "eligibility_projection_id": bundle["eligibility_projection"]["projection_id"],
            "eligibility_replay_semantic_hash": bundle["eligibility_projection"]["replay_semantic_hash"],
            "learning_projection_id": bundle["learning_projection"]["projection_id"],
            "learning_replay_semantic_hash": bundle["learning_projection"]["replay_semantic_hash"],
            "parameter_catalog_hash": bundle["policies"]["parameter_catalog_hash"],
            "learning_policy_hash": bundle["policies"]["learning_policy_hash"],
        },
        "scope_limits": [
            "TOPIC_X_REGIME_ONLY",
            "DEVELOPMENT_ONLY_EVIDENCE",
            "NO_PRODUCTION_CONSUMER",
        ],
        "forbidden_generalization": [
            "DO_NOT_GENERALIZE_ACROSS_REGIMES",
            "DO_NOT_USE_SEALED_UNKNOWN_LEGACY_OR_SYNTHETIC_EVIDENCE",
            "DO_NOT_CHANGE_CANONICAL_QUEUE_OR_SCHEDULER",
        ],
    }
    row["row_id"] = content_hash(row, omit={"row_id"})
    return row


def build_projection(
    *,
    bundle_path: Path = DEFAULT_BUNDLE,
    manifest_path: Path = DEFAULT_MANIFEST,
    policy_path: Path = DEFAULT_POLICY,
    canonical_queue_path: Path = DEFAULT_CANONICAL_QUEUE,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    bundle_path = authorize_committed_input(
        bundle_path,
        kind="bundle",
        project_root=project_root,
    )
    manifest_path = authorize_committed_input(
        manifest_path,
        kind="manifest",
        project_root=project_root,
    )
    policy_path = authorize_committed_input(
        policy_path,
        kind="policy",
        project_root=project_root,
    )
    canonical_queue_path = authorize_canonical_queue_path(
        canonical_queue_path,
        project_root=project_root,
    )
    policy = load_policy(policy_path)
    bundle = load_json(bundle_path)
    manifest = load_json(manifest_path)
    before_hash = file_sha256_or_absent(canonical_queue_path)
    admission_errors = _bundle_admission_errors(
        bundle,
        manifest,
        bundle_path=bundle_path,
        policy=policy,
        project_root=project_root,
    )
    support_by_contrast = _contrast_support(bundle) if not admission_errors else {}
    learning = bundle.get("learning_projection") if isinstance(bundle.get("learning_projection"), dict) else {}
    supplied_contrasts = learning.get("matched_contrasts") if isinstance(learning.get("matched_contrasts"), list) else []
    missing_support = sorted(
        row["contrast_id"] for row in supplied_contrasts if row["contrast_id"] not in support_by_contrast
    )
    if missing_support:
        admission_errors.append("MATCHED_CONTRAST_SUPPORT_NOT_REPRODUCIBLE")
    rows: list[dict[str, Any]] = []
    if not admission_errors:
        for scope in learning.get("scope_evidence") or []:
            scope_contrasts = sorted(
                [
                    row
                    for row in supplied_contrasts
                    if row["parameter"] == scope["parameter"]
                    and row["topic_family_id"] == scope["topic_family_id"]
                    and row["regime_id"] == scope["regime_id"]
                ],
                key=lambda row: row["contrast_id"],
            )
            rows.append(
                _row_for_scope(
                    bundle=bundle,
                    scope=scope,
                    scope_contrasts=scope_contrasts,
                    support_by_contrast=support_by_contrast,
                    policy=policy,
                )
            )
    semantic_seen: dict[str, str] = {}
    deduped: list[dict[str, Any]] = []
    collision_errors: list[str] = []
    for row in sorted(rows, key=lambda item: (item["priority_band"], item["row_id"])):
        semantic_id = row["semantic_action_id"]
        body_hash = content_hash(row, omit={"row_id"})
        existing = semantic_seen.get(semantic_id)
        if existing is None:
            semantic_seen[semantic_id] = body_hash
            deduped.append(row)
        elif existing != body_hash:
            collision_errors.append(f"SEMANTIC_ACTION_COLLISION:{semantic_id}")
    admission_errors.extend(collision_errors)
    if admission_errors:
        deduped = []
    after_hash = file_sha256_or_absent(canonical_queue_path)
    status = "PASS" if not admission_errors else "NO-GO"
    band_counts = dict(sorted(Counter(row["priority_band"] for row in deduped).items()))
    generated_at = str(bundle.get("generated_at") or manifest.get("generated_at") or "")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "projection_id": "",
        "semantic_hash": "",
        "generated_at": generated_at,
        "status": status,
        "reason_codes": admission_errors or ["ADMISSION_PASSED"],
        "policy": {
            "policy_version": policy["policy_version"],
            "policy_hash": content_hash(policy),
        },
        "inputs": {
            "bundle_path": repo_path(bundle_path, project_root=project_root),
            "bundle_id": bundle.get("bundle_id"),
            "manifest_path": repo_path(manifest_path, project_root=project_root),
            "manifest_bundle_sha256": manifest.get("bundle_sha256"),
            "eligibility_projection_id": (bundle.get("eligibility_projection") or {}).get("projection_id"),
            "learning_projection_id": (bundle.get("learning_projection") or {}).get("projection_id"),
            "parameter_catalog_hash": (bundle.get("policies") or {}).get("parameter_catalog_hash"),
        },
        "boundary": policy["boundary"],
        "admission_receipt": {
            "status": status,
            "bundle_verification_status": verify_bundle(bundle, project_root=project_root)["status"],
            "capacity_status": (manifest.get("capacity") or {}).get("status"),
            "parity_unchanged": (manifest.get("parity") or {}).get("unchanged"),
            "cleanup_status": (manifest.get("cleanup") or {}).get("status"),
            "counts": bundle.get("counts"),
            "errors": admission_errors,
        },
        "canonical_parity": {
            "path": repo_path(canonical_queue_path, project_root=project_root),
            "before_hash": before_hash,
            "after_hash": after_hash,
            "unchanged": before_hash == after_hash,
        },
        "capacity_receipt": {
            "status": (manifest.get("capacity") or {}).get("status"),
            "observed_cycles": (manifest.get("capacity") or {}).get("observed_cycles"),
            "max_bytes_per_cycle": (manifest.get("capacity") or {}).get("max_bytes_per_cycle"),
            "max_files_per_cycle": (manifest.get("capacity") or {}).get("max_files_per_cycle"),
        },
        "counts": {
            "rows": len(deduped),
            "priority_bands": band_counts,
            "deduped_semantic_actions": len(semantic_seen),
        },
        "rows": deduped,
    }
    semantic_hash = content_hash(payload, omit={"projection_id", "semantic_hash", "generated_at"})
    payload["semantic_hash"] = semantic_hash
    payload["projection_id"] = content_hash(
        {
            "schema_version": SCHEMA_VERSION,
            "semantic_hash": semantic_hash,
            "policy_hash": payload["policy"]["policy_hash"],
        }
    )
    return payload


def compare_with_canonical(
    projection: Mapping[str, Any],
    *,
    canonical_queue_path: Path = DEFAULT_CANONICAL_QUEUE,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    canonical_hash = file_sha256_or_absent(canonical_queue_path)
    canonical_rows: list[dict[str, Any]] = []
    canonical_status = "ABSENT"
    if canonical_queue_path.is_file():
        canonical = load_json(canonical_queue_path)
        raw_rows = canonical.get("items") or canonical.get("queue") or canonical.get("rows") or []
        canonical_rows = [row for row in raw_rows if isinstance(row, dict)]
        canonical_status = "READ"
    shadow_ids = [row["semantic_action_id"] for row in projection.get("rows", [])]
    canonical_ids = [
        str(row.get("semantic_action_id") or row.get("action_id") or row.get("id"))
        for row in canonical_rows
        if row.get("semantic_action_id") or row.get("action_id") or row.get("id")
    ]
    overlap = sorted(set(shadow_ids) & set(canonical_ids))
    payload = {
        "schema_version": COMPARISON_SCHEMA_VERSION,
        "comparison_id": "",
        "projection_id": projection.get("projection_id"),
        "projection_semantic_hash": projection.get("semantic_hash"),
        "canonical_queue": {
            "path": repo_path(canonical_queue_path, project_root=project_root),
            "status": canonical_status,
            "hash": canonical_hash,
            "row_count": len(canonical_rows),
        },
        "summary": {
            "shadow_rows": len(shadow_ids),
            "canonical_rows": len(canonical_ids),
            "new_shadow_actions": len(set(shadow_ids) - set(canonical_ids)),
            "overlap": len(overlap),
            "unmapped_shadow_actions": len(shadow_ids) - len(overlap),
            "order_differences": [],
        },
        "new_shadow_action_ids": sorted(set(shadow_ids) - set(canonical_ids)),
        "overlap_action_ids": overlap,
        "unmapped_reasons": [
            {
                "reason_code": "CANONICAL_QUEUE_ABSENT" if canonical_status == "ABSENT" else "SHADOW_ONLY_ACTION_NOT_IN_CANONICAL",
                "count": len(set(shadow_ids) - set(canonical_ids)),
            }
        ],
        "boundary": {
            "comparison_only": True,
            "publish_allowed": False,
            "transaction_allowed": False,
            "tag_allowed": False,
            "push_allowed": False,
            "live_cutover_allowed": False,
        },
    }
    payload["comparison_id"] = content_hash(payload, omit={"comparison_id"})
    return payload


def _projection_validator(payload: dict[str, Any]) -> list[str]:
    return verify_projection(payload)["errors"]


def _comparison_validator(payload: dict[str, Any]) -> list[str]:
    if payload.get("schema_version") != COMPARISON_SCHEMA_VERSION:
        return ["INVALID_COMPARISON_SCHEMA"]
    if payload.get("comparison_id") != content_hash(payload, omit={"comparison_id"}):
        return ["COMPARISON_ID_MISMATCH"]
    return []


def write_outputs(
    projection: Mapping[str, Any],
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    canonical_queue_path: Path = DEFAULT_CANONICAL_QUEUE,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, str]:
    output_root = authorize_output_root(
        output_root,
        project_root=project_root,
    )
    output_root.mkdir(parents=True, exist_ok=True)
    projection_path = output_root / "adaptive_shadow_queue_projection.json"
    comparison = compare_with_canonical(
        projection,
        canonical_queue_path=canonical_queue_path,
        project_root=project_root,
    )
    comparison_path = output_root / "adaptive_shadow_queue_comparison.json"
    receipt_path = output_root / "adaptive_shadow_queue_receipt.json"
    write_immutable_json(projection_path, projection, validator=_projection_validator)
    write_immutable_json(comparison_path, comparison, validator=_comparison_validator)
    receipt = {
        "schema_version": "adaptive-shadow-queue-receipt.v1",
        "status": projection["status"],
        "projection_id": projection["projection_id"],
        "semantic_hash": projection["semantic_hash"],
        "projection_path": repo_path(projection_path, project_root=project_root),
        "comparison_path": repo_path(comparison_path, project_root=project_root),
        "canonical_parity": projection["canonical_parity"],
        "capacity_receipt": projection["capacity_receipt"],
        "counts": projection["counts"],
    }
    receipt["receipt_id"] = content_hash(receipt)
    write_immutable_json(receipt_path, receipt, validator=lambda payload: [] if payload.get("schema_version") == "adaptive-shadow-queue-receipt.v1" else ["INVALID_RECEIPT_SCHEMA"])
    return {
        "projection": repo_path(projection_path, project_root=project_root),
        "comparison": repo_path(comparison_path, project_root=project_root),
        "receipt": repo_path(receipt_path, project_root=project_root),
    }


def build_and_write(
    *,
    bundle_path: Path = DEFAULT_BUNDLE,
    manifest_path: Path = DEFAULT_MANIFEST,
    policy_path: Path = DEFAULT_POLICY,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    canonical_queue_path: Path = DEFAULT_CANONICAL_QUEUE,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    output_root = authorize_output_root(
        output_root,
        project_root=project_root,
    )
    projection = build_projection(
        bundle_path=bundle_path,
        manifest_path=manifest_path,
        policy_path=policy_path,
        canonical_queue_path=canonical_queue_path,
        project_root=project_root,
    )
    paths = write_outputs(
        projection,
        output_root=output_root,
        canonical_queue_path=canonical_queue_path,
        project_root=project_root,
    )
    return {"projection": projection, "paths": paths}


def verify_projection(payload: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("INVALID_SCHEMA")
    if payload.get("semantic_hash") != content_hash(payload, omit={"projection_id", "semantic_hash", "generated_at"}):
        errors.append("SEMANTIC_HASH_MISMATCH")
    expected_projection_id = content_hash(
        {
            "schema_version": SCHEMA_VERSION,
            "semantic_hash": payload.get("semantic_hash"),
            "policy_hash": (payload.get("policy") or {}).get("policy_hash"),
        }
    )
    if payload.get("projection_id") != expected_projection_id:
        errors.append("PROJECTION_ID_MISMATCH")
    if (payload.get("policy") or {}).get("policy_hash") != EXPECTED_POLICY_HASH:
        errors.append("POLICY_HASH_NOT_COMMITTED")
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    if boundary.get("shadow_only") is not True:
        errors.append("BOUNDARY_NOT_SHADOW_ONLY")
    for forbidden in (
        "canonical_queue_write_allowed",
        "manager_selection_change_allowed",
        "scheduler_change_allowed",
        "production_change_allowed",
        "synthetic_fallback_allowed",
        "legacy_fallback_allowed",
        "sealed_or_unknown_fallback_allowed",
    ):
        if boundary.get(forbidden) is not False:
            errors.append(f"BOUNDARY_{forbidden.upper()}_INVALID")
    parity = payload.get("canonical_parity") if isinstance(payload.get("canonical_parity"), dict) else {}
    if parity.get("unchanged") is not True or parity.get("before_hash") != parity.get("after_hash"):
        errors.append("CANONICAL_PARITY_DRIFT")
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    semantic_ids: dict[str, str] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"ROW_{index}:INVALID_ROW")
            continue
        if row.get("row_id") != content_hash(row, omit={"row_id"}):
            errors.append(f"ROW_{index}:ROW_ID_MISMATCH")
        semantic_id = row.get("semantic_action_id")
        body_hash = content_hash(row, omit={"row_id"})
        if semantic_id in semantic_ids and semantic_ids[semantic_id] != body_hash:
            errors.append(f"ROW_{index}:SEMANTIC_ACTION_COLLISION")
        semantic_ids[str(semantic_id)] = body_hash
        if row.get("priority_band") == "HIGH" and (
            row.get("direction") in {"INSUFFICIENT_EVIDENCE", "UNSTABLE"}
            or DISQUALIFY_HIGH.intersection(set(row.get("flags") or []))
        ):
            errors.append(f"ROW_{index}:DISQUALIFIED_HIGH_PRIORITY")
        if row.get("priority_band") not in {item["band"] for item in EXPECTED_PRIORITY_BANDS}:
            errors.append(f"ROW_{index}:PRIORITY_BAND_NOT_COMMITTED")
        if row.get("action") != EXPECTED_ACTIONS.get(str(row.get("direction"))):
            errors.append(f"ROW_{index}:ACTION_NOT_COMMITTED")
        for field in ("supporting_evidence_unit_ids", "supporting_observation_ids", "supporting_contrast_ids"):
            values = row.get(field)
            if not isinstance(values, list) or not values or values != sorted(set(values)):
                errors.append(f"ROW_{index}:{field.upper()}_INVALID")
    status = "PASS" if not errors else "FAIL"
    report = {
        "schema_version": VERIFICATION_SCHEMA_VERSION,
        "status": status,
        "projection_id": payload.get("projection_id"),
        "semantic_hash": payload.get("semantic_hash"),
        "errors": sorted(set(errors)),
        "counts": payload.get("counts"),
    }
    report["verification_hash"] = content_hash(report)
    return report
