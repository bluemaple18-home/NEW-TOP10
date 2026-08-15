"""將已核准的 HIGH shadow action 轉成不可執行的研究提案。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from app.research.contracts import canonical_json_bytes, content_hash


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "shadow-research-plan-proposal.v1"
VERIFICATION_SCHEMA_VERSION = "shadow-research-plan-proposal-verification.v1"
SOURCE_COMMIT = "031d1a51f0bad634a4b400bec088847729ab07bd"
DEFAULT_PROJECTION_RELATIVE = Path(
    "docs/evidence/CARD-NEW-TOP10-ADAPTIVE-SHADOW-QUEUE-V1-RETRY-1/"
    "adaptive_shadow_queue_projection.json"
)
DEFAULT_POLICY_RELATIVE = Path("config/research_shadow_queue_policy_v1.json")
DEFAULT_CATALOG_RELATIVE = Path("config/research_parameter_catalog.json")
DEFAULT_OUTPUT_ROOT_RELATIVE = Path(
    "docs/evidence/CARD-NEW-TOP10-SHADOW-RESEARCH-PLAN-PROPOSAL-V1"
)
DEFAULT_OUTPUT_RELATIVE = DEFAULT_OUTPUT_ROOT_RELATIVE / "shadow_research_plan_proposal.json"
DEFAULT_VERIFICATION_RELATIVE = DEFAULT_OUTPUT_ROOT_RELATIVE / "verification.json"
DEFAULT_PROJECTION = PROJECT_ROOT / DEFAULT_PROJECTION_RELATIVE
DEFAULT_POLICY = PROJECT_ROOT / DEFAULT_POLICY_RELATIVE
DEFAULT_CATALOG = PROJECT_ROOT / DEFAULT_CATALOG_RELATIVE
DEFAULT_OUTPUT = PROJECT_ROOT / DEFAULT_OUTPUT_RELATIVE
DEFAULT_VERIFICATION = PROJECT_ROOT / DEFAULT_VERIFICATION_RELATIVE
AUTHORITATIVE_SOURCES = {
    DEFAULT_PROJECTION_RELATIVE: DEFAULT_PROJECTION,
    DEFAULT_POLICY_RELATIVE: DEFAULT_POLICY,
    DEFAULT_CATALOG_RELATIVE: DEFAULT_CATALOG,
}
EXPECTED_FILE_SHA256 = {
    "projection": "sha256:fa7f6f823279841e87560d4e06be4d7a06ea3d8b0eabe09045bdef381d672ea1",
    "policy": "sha256:5d39a8c771f93d42e20ea573098a5567a0aff361a4981c13724489eb360f4537",
    "catalog": "sha256:e88079414dfae381b96bd4a46326e38b8288447710008ecfe9c1d73b6ec66500",
}
EXPECTED_CONTENT_HASH = {
    "projection": "sha256:4b2ff1d0c7e0d7f95dd4104f23adda4f12eb6dd3bad46c00a268f2d092b36df0",
    "policy": "sha256:cd9737434aa65ad64f57424d39286b63f1abdad528f8bc6bf47ed2d344dd25f1",
    "catalog": "sha256:49be0593c9f2be2025761e1e14a086dde2a8a8ac55bd0006e4c9b42aed1f0f4c",
}
EXPECTED_PROJECTION_ID = "sha256:78d6f694a2db7ba8a26cc75da5ff263b145614343269a2a9a52cc016d518fbfd"
EXPECTED_PROJECTION_SEMANTIC_HASH = (
    "sha256:b188e17bc30487c897a67e2723b1f6f63433f3c4ad3ed2d3c295475a56846051"
)
EXPECTED_POLICY_VERSION = "adaptive-shadow-queue-policy.v1"
EXPECTED_CATALOG_VERSION = "research-parameter-catalog.v1"
EXPECTED_ACTION = "RESEARCH_PARAMETER_EXTENSION_UPWARD"
EXPECTED_DIRECTION = "HIGHER_LOOKS_BETTER"
EXPECTED_REGIME = "NARROW_LEADER|BIG_BULL"
PROTECTED_SURFACES = {
    "canonical_queue": ["artifacts/autonomous_research/next_action_queue.json"],
    "scheduler": [
        "scripts/com.new-top10.pm-research-harness.plist",
        "scripts/com.new-top10.fog-research-worker.plist",
    ],
    "production": [
        "models/baseline_stats.json",
        "models/latest_lgbm.pkl",
        "app/modeling/model_runtime_promotion.py",
        "app/agent_b_ranking.py",
        "config/signals.yaml",
    ],
}
PROPOSAL_BOUNDARY = {
    "canonical_queue_write_allowed": False,
    "execution_allowed": False,
    "production_change_allowed": False,
    "scheduler_change_allowed": False,
}


class ProposalBoundaryError(ValueError):
    """表示提案來源、輸出或不可執行邊界被拒絕。"""


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ProposalBoundaryError("JSON_ROOT_NOT_OBJECT")
    return payload


def _file_sha256(path: Path) -> str:
    if not path.is_file():
        return "ABSENT"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _repo_path(path: Path, project_root: Path) -> str:
    return path.resolve().relative_to(project_root.resolve()).as_posix()


def _authorize_source(
    path: Path,
    *,
    kind: str,
    expected_relative: Path,
    project_root: Path,
) -> Path:
    raw = path.as_posix()
    if ".." in PurePosixPath(raw).parts:
        raise ProposalBoundaryError(f"{kind.upper()}_NOT_COMMITTED_PATH")
    expected = project_root / expected_relative
    lexical = path if path.is_absolute() else project_root / path
    if lexical != expected:
        raise ProposalBoundaryError(f"{kind.upper()}_NOT_COMMITTED_PATH")
    if expected.resolve() != expected.absolute():
        raise ProposalBoundaryError(f"{kind.upper()}_SYMLINK_ESCAPE")
    if _file_sha256(expected) != EXPECTED_FILE_SHA256[kind]:
        raise ProposalBoundaryError(f"{kind.upper()}_CONTENT_DRIFT")
    return expected


def authorize_output_path(
    path: Path,
    *,
    expected_relative: Path,
    project_root: Path = PROJECT_ROOT,
) -> Path:
    raw = path.as_posix()
    if path.is_absolute() or ".." in PurePosixPath(raw).parts or raw != expected_relative.as_posix():
        raise ProposalBoundaryError("OUTPUT_NOT_CARD_EVIDENCE_PATH")
    expected = project_root / expected_relative
    if expected.resolve(strict=False) != expected.absolute():
        raise ProposalBoundaryError("OUTPUT_SYMLINK_ESCAPE")
    return expected


def snapshot_protected_surfaces(*, project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    groups: dict[str, list[dict[str, str]]] = {}
    for group, paths in PROTECTED_SURFACES.items():
        groups[group] = [
            {"path": path, "sha256": _file_sha256(project_root / path)}
            for path in paths
        ]
    return groups


def validate_source_documents(
    projection: Mapping[str, Any],
    policy: Mapping[str, Any],
    catalog: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    if projection.get("schema_version") != "adaptive-shadow-queue.v1":
        errors.append("SOURCE_PROJECTION_SCHEMA_INVALID")
    if projection.get("projection_id") != EXPECTED_PROJECTION_ID:
        errors.append("SOURCE_PROJECTION_ID_STALE")
    if projection.get("semantic_hash") != EXPECTED_PROJECTION_SEMANTIC_HASH:
        errors.append("SOURCE_PROJECTION_SEMANTIC_HASH_STALE")
    recomputed_projection_hash = content_hash(
        projection,
        omit={"projection_id", "semantic_hash", "generated_at"},
    )
    if projection.get("semantic_hash") != recomputed_projection_hash:
        errors.append("SOURCE_PROJECTION_SEMANTIC_HASH_MISMATCH")
    recomputed_projection_id = content_hash(
        {
            "schema_version": projection.get("schema_version"),
            "semantic_hash": projection.get("semantic_hash"),
            "policy_hash": (projection.get("policy") or {}).get("policy_hash"),
        }
    )
    if projection.get("projection_id") != recomputed_projection_id:
        errors.append("SOURCE_PROJECTION_ID_MISMATCH")
    if content_hash(policy) != EXPECTED_CONTENT_HASH["policy"]:
        errors.append("SOURCE_POLICY_CONTENT_MISMATCH")
    if policy.get("policy_version") != EXPECTED_POLICY_VERSION:
        errors.append("SOURCE_POLICY_VERSION_MISMATCH")
    if (projection.get("policy") or {}).get("policy_hash") != EXPECTED_CONTENT_HASH["policy"]:
        errors.append("SOURCE_PROJECTION_POLICY_HASH_MISMATCH")
    if content_hash(catalog) != EXPECTED_CONTENT_HASH["catalog"]:
        errors.append("SOURCE_CATALOG_CONTENT_MISMATCH")
    if catalog.get("catalog_version") != EXPECTED_CATALOG_VERSION:
        errors.append("SOURCE_CATALOG_VERSION_MISMATCH")
    rows = projection.get("rows")
    if not isinstance(rows, list) or not rows:
        return sorted(set(errors + ["SOURCE_ROWS_MISSING"]))
    dimensions = {
        row.get("id"): row
        for row in catalog.get("dimensions", [])
        if isinstance(row, Mapping) and isinstance(row.get("id"), str)
    }
    for index, row in enumerate(rows):
        prefix = f"SOURCE_ROW_{index}:"
        if not isinstance(row, Mapping):
            errors.append(prefix + "INVALID_ROW")
            continue
        if row.get("priority_band") != "HIGH":
            errors.append(prefix + "PRIORITY_NOT_HIGH")
        if row.get("action") != EXPECTED_ACTION:
            errors.append(prefix + "ACTION_NOT_SUPPORTED")
        if row.get("direction") != EXPECTED_DIRECTION:
            errors.append(prefix + "DIRECTION_NOT_UPWARD")
        if row.get("parameter") not in dimensions:
            errors.append(prefix + "PARAMETER_NOT_IN_CATALOG")
        if (row.get("scope") or {}).get("regime_id") != EXPECTED_REGIME:
            errors.append(prefix + "SCOPE_NOT_APPROVED")
        if (row.get("provenance") or {}).get("parameter_catalog_hash") != EXPECTED_CONTENT_HASH["catalog"]:
            errors.append(prefix + "CATALOG_PROVENANCE_MISMATCH")
        if row.get("row_id") != content_hash(row, omit={"row_id"}):
            errors.append(prefix + "ROW_ID_MISMATCH")
    return sorted(set(errors))


def _numeric_values(values: object) -> list[int | float]:
    if not isinstance(values, list):
        return []
    return sorted({value for value in values if isinstance(value, (int, float)) and not isinstance(value, bool)})


def _proposal_identity(row: Mapping[str, Any], catalog_hash: str) -> dict[str, Any]:
    return {
        "catalog_hash": catalog_hash,
        "current_value": row["current_value"],
        "direction": row["direction"],
        "parameter": row["parameter"],
        "proposed_next_value": row["proposed_next_value"],
        "scope": row["scope"],
        "source_semantic_action_id": row["source"]["semantic_action_id"],
    }


def dedupe_proposals(rows: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    seen: dict[str, str] = {}
    output: list[dict[str, Any]] = []
    duplicates = 0
    for supplied in sorted(rows, key=lambda item: str(item.get("proposal_id") or "")):
        row = dict(supplied)
        proposal_id = str(row.get("proposal_id") or "")
        body_hash = content_hash(row, omit={"proposal_id"})
        previous = seen.get(proposal_id)
        if previous is None:
            seen[proposal_id] = body_hash
            output.append(row)
        elif previous == body_hash:
            duplicates += 1
        else:
            raise ProposalBoundaryError(f"SEMANTIC_PROPOSAL_COLLISION:{proposal_id}")
    return output, duplicates


def _derive_proposal(
    projection: Mapping[str, Any],
    policy: Mapping[str, Any],
    catalog: Mapping[str, Any],
    *,
    source_receipt: Mapping[str, Any],
    protected_parity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    dimensions = {row["id"]: row for row in catalog["dimensions"]}
    candidates: list[dict[str, Any]] = []
    no_adjacent = False
    for source_row in projection["rows"]:
        dimension = dimensions[source_row["parameter"]]
        coverage = _numeric_values(dimension.get("coverage_values"))
        executable = _numeric_values(dimension.get("executable_values"))
        current = max(coverage)
        higher = [value for value in executable if value > current]
        if not higher:
            no_adjacent = True
            continue
        next_value = min(higher)
        row = {
            "proposal_id": "",
            "source": {
                "projection_id": projection["projection_id"],
                "projection_semantic_hash": projection["semantic_hash"],
                "row_id": source_row["row_id"],
                "semantic_action_id": source_row["semantic_action_id"],
            },
            "scope": source_row["scope"],
            "parameter": source_row["parameter"],
            "direction": source_row["direction"],
            "current_value": current,
            "proposed_next_value": next_value,
            "catalog_bounds": {"minimum": min(executable), "maximum": max(executable)},
            "reason_codes": sorted(
                set(source_row.get("reason_codes") or [])
                | {"CATALOG_ADJACENT_UPWARD_VALUE", "SHADOW_HIGH_ACTION_APPROVED"}
            ),
            "provenance": {
                "source_commit": SOURCE_COMMIT,
                "source_projection_path": DEFAULT_PROJECTION_RELATIVE.as_posix(),
                "source_policy_path": DEFAULT_POLICY_RELATIVE.as_posix(),
                "parameter_catalog_path": DEFAULT_CATALOG_RELATIVE.as_posix(),
                "policy_version": policy["policy_version"],
                "policy_hash": EXPECTED_CONTENT_HASH["policy"],
                "catalog_version": catalog["catalog_version"],
                "catalog_hash": EXPECTED_CONTENT_HASH["catalog"],
            },
            "boundary": PROPOSAL_BOUNDARY,
        }
        row["proposal_id"] = content_hash(
            _proposal_identity(row, EXPECTED_CONTENT_HASH["catalog"])
        )
        candidates.append(row)
    proposals, duplicate_count = dedupe_proposals(candidates)
    status = "NO-GO" if no_adjacent else "PASS"
    if no_adjacent:
        proposals = []
    payload = {
        "schema_version": SCHEMA_VERSION,
        "proposal_set_id": "",
        "semantic_hash": "",
        "status": status,
        "reason_codes": ["NO-GO_NO_ADJACENT_VALUE"] if no_adjacent else ["PROPOSAL_READY_FOR_HUMAN_REVIEW"],
        "source_receipt": dict(source_receipt),
        "boundary": PROPOSAL_BOUNDARY,
        "protected_surface_parity": dict(protected_parity or {}),
        "counts": {
            "source_rows": len(projection["rows"]),
            "proposals": len(proposals),
            "deduped": duplicate_count,
        },
        "proposals": proposals,
    }
    payload["semantic_hash"] = content_hash(
        payload,
        omit={"proposal_set_id", "semantic_hash"},
    )
    payload["proposal_set_id"] = content_hash(
        {"schema_version": SCHEMA_VERSION, "semantic_hash": payload["semantic_hash"]}
    )
    return payload


def build_proposal(
    *,
    projection_path: Path = DEFAULT_PROJECTION,
    policy_path: Path = DEFAULT_POLICY,
    catalog_path: Path = DEFAULT_CATALOG,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    projection_path = _authorize_source(
        projection_path,
        kind="projection",
        expected_relative=DEFAULT_PROJECTION_RELATIVE,
        project_root=project_root,
    )
    policy_path = _authorize_source(
        policy_path,
        kind="policy",
        expected_relative=DEFAULT_POLICY_RELATIVE,
        project_root=project_root,
    )
    catalog_path = _authorize_source(
        catalog_path,
        kind="catalog",
        expected_relative=DEFAULT_CATALOG_RELATIVE,
        project_root=project_root,
    )
    before = snapshot_protected_surfaces(project_root=project_root)
    projection = load_json(projection_path)
    policy = load_json(policy_path)
    catalog = load_json(catalog_path)
    errors = validate_source_documents(projection, policy, catalog)
    if errors:
        raise ProposalBoundaryError(errors[0])
    after = snapshot_protected_surfaces(project_root=project_root)
    parity = {
        "before": before,
        "after": after,
        "unchanged": before == after,
    }
    if not parity["unchanged"]:
        raise ProposalBoundaryError("PROTECTED_SURFACE_DRIFT")
    source_receipt = {
        "source_commit": SOURCE_COMMIT,
        "projection": {
            "path": _repo_path(projection_path, project_root),
            "file_sha256": EXPECTED_FILE_SHA256["projection"],
            "content_hash": EXPECTED_CONTENT_HASH["projection"],
            "projection_id": projection["projection_id"],
            "semantic_hash": projection["semantic_hash"],
        },
        "policy": {
            "path": _repo_path(policy_path, project_root),
            "file_sha256": EXPECTED_FILE_SHA256["policy"],
            "content_hash": EXPECTED_CONTENT_HASH["policy"],
            "policy_version": policy["policy_version"],
        },
        "catalog": {
            "path": _repo_path(catalog_path, project_root),
            "file_sha256": EXPECTED_FILE_SHA256["catalog"],
            "content_hash": EXPECTED_CONTENT_HASH["catalog"],
            "catalog_version": catalog["catalog_version"],
        },
    }
    return _derive_proposal(
        projection,
        policy,
        catalog,
        source_receipt=source_receipt,
        protected_parity=parity,
    )


def encode_proposal(payload: Mapping[str, Any]) -> bytes:
    return canonical_json_bytes(payload) + b"\n"


def write_deterministic_output(path: Path, payload: Mapping[str, Any]) -> None:
    body = encode_proposal(payload)
    if path.exists():
        if path.read_bytes() != body:
            raise ProposalBoundaryError("OUTPUT_IDENTITY_COLLISION")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)


def verify_proposal(payload: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("INVALID_SCHEMA_VERSION")
    if payload.get("boundary") != PROPOSAL_BOUNDARY:
        errors.append("PROPOSAL_ONLY_BOUNDARY_MISMATCH")
    parity = payload.get("protected_surface_parity") or {}
    if parity.get("unchanged") is not True or parity.get("before") != parity.get("after"):
        errors.append("PROTECTED_SURFACE_PARITY_FAILED")
    recomputed_hash = content_hash(
        payload,
        omit={"proposal_set_id", "semantic_hash"},
    )
    if payload.get("semantic_hash") != recomputed_hash:
        errors.append("SEMANTIC_HASH_MISMATCH")
    expected_set_id = content_hash(
        {"schema_version": payload.get("schema_version"), "semantic_hash": payload.get("semantic_hash")}
    )
    if payload.get("proposal_set_id") != expected_set_id:
        errors.append("PROPOSAL_SET_ID_MISMATCH")
    catalog = load_json(DEFAULT_CATALOG)
    dimensions = {row["id"]: row for row in catalog["dimensions"]}
    for index, row in enumerate(payload.get("proposals") or []):
        prefix = f"PROPOSAL_{index}:"
        dimension = dimensions.get(row.get("parameter"))
        if dimension is None:
            errors.append(prefix + "PARAMETER_NOT_IN_CATALOG")
            continue
        coverage = _numeric_values(dimension["coverage_values"])
        executable = _numeric_values(dimension["executable_values"])
        current = max(coverage)
        higher = [value for value in executable if value > current]
        expected_next = min(higher) if higher else None
        if row.get("current_value") != current or row.get("proposed_next_value") != expected_next:
            errors.append(prefix + "NEXT_VALUE_NOT_ADJACENT")
        if row.get("scope", {}).get("regime_id") != EXPECTED_REGIME:
            errors.append(prefix + "SCOPE_EXPANDED")
        if row.get("boundary") != PROPOSAL_BOUNDARY:
            errors.append(prefix + "BOUNDARY_MISMATCH")
        expected_id = content_hash(_proposal_identity(row, EXPECTED_CONTENT_HASH["catalog"]))
        if row.get("proposal_id") != expected_id:
            errors.append(prefix + "PROPOSAL_ID_MISMATCH")
    deterministic_bytes = False
    try:
        expected = build_proposal()
        repeated = build_proposal()
        deterministic_bytes = encode_proposal(expected) == encode_proposal(repeated)
    except ProposalBoundaryError as exc:
        errors.append(f"AUTHORITATIVE_RECOMPUTE_FAILED:{exc}")
    else:
        if not deterministic_bytes:
            errors.append("TWO_RUN_BYTES_DIFFER")
        if dict(payload) != expected:
            errors.append("PROPOSAL_BODY_NOT_AUTHORITATIVE")
    return {
        "schema_version": VERIFICATION_SCHEMA_VERSION,
        "status": "PASS" if not errors else "FAIL",
        "proposal_set_id": payload.get("proposal_set_id"),
        "errors": sorted(set(errors)),
        "checks": {
            "authoritative_recompute": not any(error.startswith("AUTHORITATIVE_RECOMPUTE_FAILED") for error in errors),
            "two_run_byte_equality": deterministic_bytes,
            "deterministic_identity": "SEMANTIC_HASH_MISMATCH" not in errors and "PROPOSAL_SET_ID_MISMATCH" not in errors,
            "proposal_only_boundary": "PROPOSAL_ONLY_BOUNDARY_MISMATCH" not in errors,
            "protected_surface_parity": "PROTECTED_SURFACE_PARITY_FAILED" not in errors,
        },
    }
