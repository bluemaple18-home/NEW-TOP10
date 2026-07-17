"""建立並驗證 TOP10new 的 canonical architecture manifest。"""

from __future__ import annotations

import hashlib
import json
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

import yaml


CONTROL_PLANE_SCHEMA_VERSION = "top10.architecture-control-plane.v1"
MANIFEST_SCHEMA_VERSION = "top10.architecture-manifest.v1"
LIFECYCLE_SCHEMA_VERSION = "script-lifecycle-policy.v1"


class ArchitectureControlPlaneError(ValueError):
    """控制面或 manifest 不符合可驗證契約。"""


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ArchitectureControlPlaneError(f"無法讀取 YAML：{path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ArchitectureControlPlaneError(f"YAML root 必須是 mapping：{path}")
    return payload


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_sha(repo_root: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise ArchitectureControlPlaneError(f"無法取得 Git SHA：{completed.stderr.strip()}")
    return completed.stdout.strip()


def _require_mapping(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict) or not value:
        raise ArchitectureControlPlaneError(f"{key} 必須是非空 mapping")
    return value


def _require_list(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list) or not value:
        raise ArchitectureControlPlaneError(f"{key} 必須是非空 list")
    return value


def _require_refs(values: Iterable[str], known: set[str], label: str) -> None:
    unknown = sorted(set(values) - known)
    if unknown:
        raise ArchitectureControlPlaneError(f"{label} 引用未知項目：{unknown}")


def _require_paths(repo_root: Path, paths: Iterable[str], label: str) -> None:
    missing = sorted(path for path in set(paths) if not (repo_root / path).exists())
    if missing:
        raise ArchitectureControlPlaneError(f"{label} 引用不存在路徑：{missing}")


def _lifecycle_entrypoints(lifecycle: dict[str, Any]) -> set[str]:
    if lifecycle.get("schema_version") != LIFECYCLE_SCHEMA_VERSION:
        raise ArchitectureControlPlaneError("不支援的 script lifecycle schema")
    entrypoints = lifecycle.get("production_entrypoints")
    if not isinstance(entrypoints, list) or not entrypoints:
        raise ArchitectureControlPlaneError("script lifecycle 缺少 production_entrypoints")
    if len(entrypoints) != len(set(entrypoints)):
        raise ArchitectureControlPlaneError("script lifecycle production_entrypoints 不得重複")
    return set(entrypoints)


def validate_control_plane_config(
    config: dict[str, Any],
    lifecycle: dict[str, Any],
    repo_root: Path,
) -> None:
    """驗證人工維護的控制面設定與 repo 現況一致。"""

    if config.get("schema_version") != CONTROL_PLANE_SCHEMA_VERSION:
        raise ArchitectureControlPlaneError("不支援的 architecture control plane schema")

    domains = _require_mapping(config, "domains")
    entrypoints = _require_mapping(config, "entrypoints")
    workflows = _require_mapping(config, "workflows")
    artifacts = _require_mapping(config, "artifacts")
    verification = _require_mapping(config, "verification")

    lifecycle_entrypoints = _lifecycle_entrypoints(lifecycle)
    configured_entrypoints = set(entrypoints)
    if lifecycle_entrypoints != configured_entrypoints:
        missing = sorted(lifecycle_entrypoints - configured_entrypoints)
        extra = sorted(configured_entrypoints - lifecycle_entrypoints)
        raise ArchitectureControlPlaneError(
            f"production entrypoint 與 lifecycle 不一致：missing={missing}, extra={extra}"
        )
    _require_paths(repo_root, configured_entrypoints, "production entrypoint")

    domain_paths: list[str] = []
    for domain_id, domain in domains.items():
        if not isinstance(domain, dict) or not str(domain.get("owner", "")).strip():
            raise ArchitectureControlPlaneError(f"domain {domain_id} 缺少 owner")
        paths = domain.get("paths")
        if not isinstance(paths, list) or not paths:
            raise ArchitectureControlPlaneError(f"domain {domain_id} 缺少 paths")
        domain_paths.extend(str(path) for path in paths)
    if len(domain_paths) != len(set(domain_paths)):
        raise ArchitectureControlPlaneError("domain paths 不得重複宣告")
    _require_paths(repo_root, domain_paths, "domain")

    workflow_ids = set(workflows)
    artifact_ids = set(artifacts)
    verification_ids = set(verification)
    domain_ids = set(domains)

    verification_paths: list[str] = []
    for verification_id, spec in verification.items():
        if not isinstance(spec, dict) or spec.get("kind") not in {"test", "gate"}:
            raise ArchitectureControlPlaneError(f"verification {verification_id} kind 無效")
        command = spec.get("command")
        if not isinstance(command, list) or not command or not all(isinstance(item, str) for item in command):
            raise ArchitectureControlPlaneError(f"verification {verification_id} command 無效")
        paths = spec.get("paths", [])
        if not isinstance(paths, list):
            raise ArchitectureControlPlaneError(f"verification {verification_id} paths 無效")
        verification_paths.extend(str(path) for path in paths)
    _require_paths(repo_root, verification_paths, "verification")

    for path, spec in entrypoints.items():
        if not isinstance(spec, dict):
            raise ArchitectureControlPlaneError(f"entrypoint {path} spec 無效")
        _require_refs([str(spec.get("domain"))], domain_ids, f"entrypoint {path} domain")
        _require_refs(spec.get("workflows", []), workflow_ids, f"entrypoint {path} workflows")
        required = spec.get("required_verification")
        if not isinstance(required, list) or not required:
            raise ArchitectureControlPlaneError(f"entrypoint {path} 缺少 required_verification")
        _require_refs(required, verification_ids, f"entrypoint {path} verification")

    declared_step_ids: set[str] = set()
    for workflow_id, workflow in workflows.items():
        if not isinstance(workflow, dict):
            raise ArchitectureControlPlaneError(f"workflow {workflow_id} spec 無效")
        _require_refs([str(workflow.get("owner_domain"))], domain_ids, f"workflow {workflow_id} owner")
        workflow_entrypoints = workflow.get("entrypoints")
        if not isinstance(workflow_entrypoints, list) or not workflow_entrypoints:
            raise ArchitectureControlPlaneError(f"workflow {workflow_id} 缺少 entrypoints")
        _require_refs(workflow_entrypoints, configured_entrypoints, f"workflow {workflow_id} entrypoints")
        required = workflow.get("required_verification")
        if not isinstance(required, list) or not required:
            raise ArchitectureControlPlaneError(f"workflow {workflow_id} 缺少 required_verification")
        _require_refs(required, verification_ids, f"workflow {workflow_id} verification")
        steps = _require_list(workflow, "steps")
        step_names: set[str] = set()
        for step in steps:
            if not isinstance(step, dict) or not str(step.get("id", "")).strip():
                raise ArchitectureControlPlaneError(f"workflow {workflow_id} step 無效")
            step_id = str(step["id"])
            if step_id in step_names:
                raise ArchitectureControlPlaneError(f"workflow {workflow_id} step 重複：{step_id}")
            step_names.add(step_id)
            declared_step_ids.add(f"{workflow_id}.{step_id}")
            _require_refs(step.get("inputs", []), artifact_ids, f"step {workflow_id}.{step_id} inputs")
            _require_refs(step.get("outputs", []), artifact_ids, f"step {workflow_id}.{step_id} outputs")

    for artifact_id, artifact in artifacts.items():
        if not isinstance(artifact, dict) or not str(artifact.get("path", "")).strip():
            raise ArchitectureControlPlaneError(f"artifact {artifact_id} 缺少 path")
        producers = artifact.get("producers")
        consumers = artifact.get("consumers")
        if not isinstance(producers, list) or not producers:
            raise ArchitectureControlPlaneError(f"artifact {artifact_id} 缺少 producers")
        if not isinstance(consumers, list) or not consumers:
            raise ArchitectureControlPlaneError(f"artifact {artifact_id} 缺少 consumers")
        _require_refs(producers, declared_step_ids, f"artifact {artifact_id} producers")
        _require_refs(consumers, workflow_ids, f"artifact {artifact_id} consumers")


def build_architecture_manifest(
    repo_root: Path,
    *,
    config_path: Path | None = None,
    lifecycle_path: Path | None = None,
) -> dict[str, Any]:
    """從控制面設定與 lifecycle policy 產生 deterministic manifest。"""

    repo_root = repo_root.resolve()
    config_path = (config_path or repo_root / "config/architecture_control_plane.yaml").resolve()
    lifecycle_path = (lifecycle_path or repo_root / "config/script_lifecycle.yaml").resolve()
    config = _load_yaml(config_path)
    lifecycle = _load_yaml(lifecycle_path)
    validate_control_plane_config(config, lifecycle, repo_root)

    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "source": {
            "git_sha": _git_sha(repo_root),
            "inputs": {
                str(config_path.relative_to(repo_root)): _sha256(config_path),
                str(lifecycle_path.relative_to(repo_root)): _sha256(lifecycle_path),
            },
        },
        "lifecycle_contract": {
            "step_statuses": ["pending", "running", "succeeded", "failed", "skipped"],
            "automatic_full_fallback_allowed": False,
            "resume_requires_persistent_manifest": True,
        },
        "control_plane": deepcopy(config),
    }


def verify_architecture_manifest(
    manifest: dict[str, Any],
    repo_root: Path,
    *,
    config_path: Path | None = None,
    lifecycle_path: Path | None = None,
) -> None:
    """重算 manifest；任何 drift 或手動竄改都 fail loud。"""

    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise ArchitectureControlPlaneError("不支援的 architecture manifest schema")
    expected = build_architecture_manifest(
        repo_root,
        config_path=config_path,
        lifecycle_path=lifecycle_path,
    )
    if manifest != expected:
        actual_digest = hashlib.sha256(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        expected_digest = hashlib.sha256(
            json.dumps(expected, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        raise ArchitectureControlPlaneError(
            f"architecture manifest 與 repo source 不一致：actual={actual_digest}, expected={expected_digest}"
        )
