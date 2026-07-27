#!/usr/bin/env python3
"""Fog recovery 使用的固定 role-path authority contracts。"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any


SOURCE_CONTRACT_SCHEMA = "fog-source-role-path-contract.v1"
SOURCE_LINEAGE_SCHEMA = "fog-source-lineage.v1"
PROTECTED_CONTRACT_SCHEMA = "fog-protected-role-path-contract.v1"
PRODUCTION_BASELINE_PATH_TEMPLATE = (
    "artifacts/autonomous_research/"
    "fog_production_hash_baseline_{run_date}.json"
)
PROTECTED_ROLE_PATHS = {
    "model": "models/latest_lgbm.pkl",
    "baseline": "models/baseline_stats.json",
    "ranking": "artifacts/ranking_{run_date}.csv",
    "weights": "config/signals.yaml",
    "promotion": "app/modeling/model_runtime_promotion.py",
}
SOURCE_ROLE_PATHS = {
    "research_map": {
        "topic_registry": "artifacts/autonomous_research/topic_registry.json",
        "run_history": "artifacts/autonomous_research/run_history.jsonl",
    },
    "weekend_inventory": {
        "research_map": "artifacts/research_map/research_fog_map_latest.json",
        "topic_registry": "artifacts/autonomous_research/topic_registry.json",
        "run_history": "artifacts/autonomous_research/run_history.jsonl",
    },
}


def canonical_json_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_contract(artifact_kind: str) -> dict[str, Any]:
    roles = SOURCE_ROLE_PATHS.get(artifact_kind)
    if roles is None:
        raise ValueError(f"未知 source contract：{artifact_kind}")
    return {
        "schema_version": SOURCE_CONTRACT_SCHEMA,
        "artifact_kind": artifact_kind,
        "roles": roles,
    }


def source_contract_hash(artifact_kind: str) -> str:
    return canonical_json_hash(source_contract(artifact_kind))


def protected_contract() -> dict[str, Any]:
    return {
        "schema_version": PROTECTED_CONTRACT_SCHEMA,
        "roles": PROTECTED_ROLE_PATHS,
        "baseline_path": PRODUCTION_BASELINE_PATH_TEMPLATE,
    }


def protected_contract_hash() -> str:
    return canonical_json_hash(protected_contract())


def _render_path(template: str, run_date: str) -> str:
    date.fromisoformat(run_date)
    return template.format(run_date=run_date)


def _secure_repo_path(root: Path, relative_path: str) -> tuple[Path, bool]:
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        return root / "__invalid_authority_path__", False
    root_resolved = root.resolve()
    candidate = root / relative
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError:
        return candidate, False
    return candidate, True


def canonical_protected_paths(root: Path, run_date: str) -> dict[str, Path]:
    return {
        role: root / _render_path(path, run_date)
        for role, path in PROTECTED_ROLE_PATHS.items()
    }


def canonical_baseline_path(root: Path, run_date: str) -> Path:
    return root / _render_path(PRODUCTION_BASELINE_PATH_TEMPLATE, run_date)


def build_source_lineage(
    root: Path,
    artifact_kind: str,
    *,
    allow_missing: bool = False,
) -> dict[str, Any]:
    sources: dict[str, dict[str, str | None]] = {}
    for role, relative_path in SOURCE_ROLE_PATHS[artifact_kind].items():
        path, safe = _secure_repo_path(root, relative_path)
        if not safe or not path.is_file():
            if not allow_missing:
                raise FileNotFoundError(f"{artifact_kind} source missing：{relative_path}")
            digest = None
        else:
            digest = sha256(path)
        sources[role] = {"path": relative_path, "sha256": digest}
    return {
        "schema_version": SOURCE_LINEAGE_SCHEMA,
        "contract_sha256": source_contract_hash(artifact_kind),
        "sources": sources,
    }


def verify_source_lineage(
    payload: dict[str, Any],
    artifact_kind: str,
    root: Path,
) -> dict[str, Any]:
    lineage = (
        payload.get("source_lineage")
        if isinstance(payload.get("source_lineage"), dict)
        else {}
    )
    declared = (
        lineage.get("sources")
        if isinstance(lineage.get("sources"), dict)
        else {}
    )
    expected = SOURCE_ROLE_PATHS[artifact_kind]
    schema_ok = (
        set(lineage) == {"schema_version", "contract_sha256", "sources"}
        and lineage.get("schema_version") == SOURCE_LINEAGE_SCHEMA
    )
    contract_ok = (
        lineage.get("contract_sha256") == source_contract_hash(artifact_kind)
    )
    role_set_ok = set(declared) == set(expected)
    missing: list[str] = []
    path_drift: list[str] = []
    hash_drift: list[str] = []
    current_hashes: dict[str, str] = {}

    for role, expected_path in expected.items():
        entry = declared.get(role)
        if not isinstance(entry, dict) or set(entry) != {"path", "sha256"}:
            missing.append(role)
            continue
        declared_path = entry.get("path")
        if declared_path != expected_path:
            path_drift.append(role)
            continue
        path, safe = _secure_repo_path(root, expected_path)
        if not safe:
            path_drift.append(role)
            continue
        if not path.is_file():
            missing.append(role)
            continue
        resolved_root = root.resolve()
        try:
            path.resolve().relative_to(resolved_root)
        except ValueError:
            path_drift.append(role)
            continue
        digest = sha256(path)
        current_hashes[role] = digest
        if entry.get("sha256") != digest:
            hash_drift.append(role)

    return {
        "ok": (
            schema_ok
            and contract_ok
            and role_set_ok
            and not missing
            and not path_drift
            and not hash_drift
        ),
        "schema_ok": schema_ok,
        "contract_ok": contract_ok,
        "role_set_ok": role_set_ok,
        "missing": missing,
        "path_drift": path_drift,
        "hash_drift": hash_drift,
        "declared": declared,
        "current_hashes": current_hashes,
    }
