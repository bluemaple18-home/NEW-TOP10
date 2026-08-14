"""Daily research batch owner authority contract。"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from app.research.contracts import (
    CANONICALIZATION_VERSION,
    canonical_json_bytes,
    content_hash,
)
from app.research.receipt_store import corpus_path, write_immutable_json


BATCH_INTENT_SCHEMA_VERSION = "research-batch-intent.v1"
BATCH_INTENT_ENTITY = "batch_intents"
BATCH_INTENT_FLAG = "--research-batch-intent"
CANONICAL_SCHEDULER_OWNER = "daily_research_quota"
CANONICAL_SCHEDULER_ENTRYPOINT = "scripts/run_daily_research_quota.sh"
BATCH_ID_PATTERN = re.compile(r"research-\d{4}-\d{2}-\d{2}-\d{6}-\d+")
HASH_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")
ALLOWED_STAGES = {"DEVELOPMENT_SCREEN", "COARSE_SCREEN"}
SAFETY = {
    "does_not_train_model": True,
    "does_not_change_production_ranking": True,
    "production_promotion_allowed": False,
}


@dataclass(frozen=True)
class BatchAuthorityResult:
    status: str
    batch_intent_id: str | None
    reason_code: str


class BatchOwnerAuthorityError(RuntimeError):
    pass


def _hash_bytes(encoded: bytes) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _file_hash(path: Path) -> str:
    return _hash_bytes(path.read_bytes())


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_runner_argv(argv: Sequence[str]) -> list[str]:
    """移除 authority transport flag；剩餘 argv 必須與 Intent 綁定內容完全一致。"""

    normalized: list[str] = []
    iterator = iter(enumerate(argv))
    seen = False
    for _, value in iterator:
        if value != BATCH_INTENT_FLAG:
            normalized.append(value)
            continue
        if seen:
            raise BatchOwnerAuthorityError("DUPLICATE_BATCH_INTENT_REFERENCE")
        seen = True
        try:
            next(iterator)
        except StopIteration as exc:
            raise BatchOwnerAuthorityError("MISSING_BATCH_INTENT_REFERENCE_VALUE") from exc
    return normalized


def runner_argv_hash(argv: Sequence[str]) -> str:
    return content_hash({"argv": list(argv)})


def _relative_path(value: Path, project_root: Path) -> str:
    resolved = value.resolve(strict=False)
    try:
        return resolved.relative_to(project_root.resolve(strict=True)).as_posix()
    except ValueError:
        return str(resolved)


def _resolve_under(root: Path, value: str | Path) -> Path:
    base = root.resolve(strict=True)
    raw = Path(value).expanduser()
    candidate = raw if raw.is_absolute() else root / raw
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise BatchOwnerAuthorityError("PATH_ESCAPE") from exc
    return resolved


def _is_path_inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve(strict=False).relative_to(parent.resolve(strict=True))
        return True
    except (OSError, RuntimeError, ValueError):
        return False


def _path_record(path: Path, project_root: Path) -> dict[str, str]:
    return {
        "repo_path": _relative_path(path, project_root),
        "resolved_path": str(path.resolve(strict=False)),
    }


def _git_head(project_root: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=project_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise BatchOwnerAuthorityError("GIT_HEAD_UNAVAILABLE")
    return completed.stdout.strip()


def _json_file_digest(path: Path) -> tuple[str, str]:
    payload = _load_json(path)
    return str(payload.get("catalog_version") or payload.get("policy_version") or path.name), content_hash(payload)


def _canonical_scheduler_entrypoint(project_root: Path) -> Path:
    return project_root.resolve(strict=True) / CANONICAL_SCHEDULER_ENTRYPOINT


def _canonical_scheduler_errors(project_root: Path, scheduler: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    canonical = _canonical_scheduler_entrypoint(project_root)
    if scheduler.get("owner") != CANONICAL_SCHEDULER_OWNER:
        errors.append("SCHEDULER_OWNER_MISMATCH")
    if scheduler.get("entrypoint") != CANONICAL_SCHEDULER_ENTRYPOINT:
        errors.append("SCHEDULER_ENTRYPOINT_MISMATCH")
    cursor = project_root.resolve(strict=True)
    for part in Path(CANONICAL_SCHEDULER_ENTRYPOINT).parts:
        cursor = cursor / part
        if cursor.is_symlink():
            errors.append("SCHEDULER_ENTRYPOINT_SYMLINK")
            break
    if not canonical.is_file():
        errors.append("SCHEDULER_ENTRYPOINT_MISSING")
    elif scheduler.get("entrypoint_hash") != _file_hash(canonical):
        errors.append("SCHEDULER_ENTRYPOINT_HASH_MISMATCH")
    return errors


def build_batch_intent(
    *,
    project_root: Path,
    corpus_root: Path,
    batch_id: str,
    scheduler_entrypoint: Path,
    runner_argv: Sequence[str],
    output_path: Path,
    ledger_path: Path,
    requested_research_stage: str,
    allowed_research_stages: Sequence[str],
    policy_path: Path,
    catalog_path: Path,
    execution_epoch: str,
    created_at: str | None = None,
) -> dict[str, Any]:
    project_root = project_root.resolve(strict=True)
    canonical_scheduler = _canonical_scheduler_entrypoint(project_root)
    if scheduler_entrypoint.resolve(strict=False) != canonical_scheduler.resolve(strict=False):
        raise BatchOwnerAuthorityError("SCHEDULER_ENTRYPOINT_MISMATCH")
    authorized_argv = normalize_runner_argv(runner_argv)
    policy_version, policy_hash = _json_file_digest(policy_path)
    catalog_version, catalog_hash = _json_file_digest(catalog_path)
    payload: dict[str, Any] = {
        "schema_version": BATCH_INTENT_SCHEMA_VERSION,
        "canonicalization_version": CANONICALIZATION_VERSION,
        "batch_intent_id": "sha256:" + "0" * 64,
        "batch_id": batch_id,
        "scheduler": {
            "owner": CANONICAL_SCHEDULER_OWNER,
            "entrypoint": CANONICAL_SCHEDULER_ENTRYPOINT,
            "entrypoint_hash": _file_hash(canonical_scheduler),
        },
        "runner": {
            "argv": authorized_argv,
            "argv_hash": runner_argv_hash(authorized_argv),
        },
        "project": {
            "repo_identity": content_hash({"repo_root": project_root.name, "head": _git_head(project_root)}),
            "repo_root": str(project_root),
            "head": _git_head(project_root),
        },
        "research": {
            "requested_stage": requested_research_stage,
            "allowed_stage_set": sorted(allowed_research_stages),
        },
        "paths": {
            "output_root": _path_record(output_path.parent, project_root),
            "spine_root": _path_record(corpus_root, project_root),
            "ledger_path": _path_record(ledger_path, project_root),
            "manager_paths": {
                "topic_bank": _path_record(output_path.parent / "topic_bank.json", project_root),
                "registry": _path_record(output_path.parent / "topic_registry.json", project_root),
                "history": _path_record(output_path.parent / "run_history.json", project_root),
                "queue": _path_record(output_path.parent / "next_action_queue.json", project_root),
                "summary": _path_record(output_path.parent / "manager_summary.json", project_root),
                "runner_registry": _path_record(output_path.parent / "runner_registry.json", project_root),
            },
        },
        "catalog": {
            "version": catalog_version,
            "hash": catalog_hash,
        },
        "policy": {
            "version": policy_version,
            "hash": policy_hash,
        },
        "created_at": created_at or _utc_now(),
        "execution_epoch": execution_epoch,
        "safety": SAFETY,
    }
    payload["batch_intent_id"] = content_hash(payload, omit={"batch_intent_id"})
    return payload


def validate_batch_intent(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    fields = {
        "schema_version",
        "canonicalization_version",
        "batch_intent_id",
        "batch_id",
        "scheduler",
        "runner",
        "project",
        "research",
        "paths",
        "catalog",
        "policy",
        "created_at",
        "execution_epoch",
        "safety",
    }
    extras = sorted(set(payload) - fields)
    missing = sorted(fields - set(payload))
    errors.extend(f"{field} is required" for field in missing)
    errors.extend(f"{field} is not allowed" for field in extras)
    if payload.get("schema_version") != BATCH_INTENT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {BATCH_INTENT_SCHEMA_VERSION}")
    if payload.get("canonicalization_version") != CANONICALIZATION_VERSION:
        errors.append("canonicalization_version is invalid")
    if not isinstance(payload.get("batch_intent_id"), str) or not HASH_PATTERN.fullmatch(str(payload.get("batch_intent_id"))):
        errors.append("batch_intent_id must be sha256:<64 lowercase hex>")
    if not isinstance(payload.get("batch_id"), str) or not BATCH_ID_PATTERN.fullmatch(str(payload.get("batch_id"))):
        errors.append("batch_id must use research-YYYY-MM-DD-HHMMSS-PID format")
    for key in ("scheduler", "runner", "project", "research", "paths", "catalog", "policy", "safety"):
        if not isinstance(payload.get(key), Mapping):
            errors.append(f"{key} must be an object")
    runner = payload.get("runner") if isinstance(payload.get("runner"), Mapping) else {}
    if not isinstance(runner.get("argv"), list) or not all(isinstance(item, str) and item for item in runner.get("argv", [])):
        errors.append("runner.argv must be a non-empty string list")
    elif runner.get("argv_hash") != runner_argv_hash(runner["argv"]):
        errors.append("runner.argv_hash does not match argv")
    if not isinstance(runner.get("argv_hash"), str) or not HASH_PATTERN.fullmatch(str(runner.get("argv_hash"))):
        errors.append("runner.argv_hash must be sha256:<64 lowercase hex>")
    research = payload.get("research") if isinstance(payload.get("research"), Mapping) else {}
    allowed = research.get("allowed_stage_set")
    if research.get("requested_stage") not in ALLOWED_STAGES:
        errors.append("research.requested_stage is invalid")
    if not isinstance(allowed, list) or not allowed or set(allowed) - ALLOWED_STAGES:
        errors.append("research.allowed_stage_set is invalid")
    elif research.get("requested_stage") not in allowed:
        errors.append("research.requested_stage must be allowed")
    safety = payload.get("safety") if isinstance(payload.get("safety"), Mapping) else {}
    for field, expected in SAFETY.items():
        if safety.get(field) is not expected:
            errors.append(f"safety.{field} must be {str(expected).lower()}")
    for section in ("catalog", "policy"):
        record = payload.get(section) if isinstance(payload.get(section), Mapping) else {}
        if not isinstance(record.get("version"), str) or not record.get("version"):
            errors.append(f"{section}.version must be non-empty")
        if not isinstance(record.get("hash"), str) or not HASH_PATTERN.fullmatch(str(record.get("hash"))):
            errors.append(f"{section}.hash must be sha256:<64 lowercase hex>")
    if not errors and payload.get("batch_intent_id") != content_hash(payload, omit={"batch_intent_id"}):
        errors.append("batch_intent_id does not match canonical content")
    return errors


def publish_batch_intent(*, corpus_root: Path, payload: Mapping[str, Any]):
    batch_intent_id = str(payload.get("batch_intent_id") or "")
    return write_immutable_json(
        corpus_path(corpus_root, BATCH_INTENT_ENTITY, batch_intent_id),
        payload,
        validator=validate_batch_intent,
        identity_field="batch_intent_id",
    )


def load_batch_intent_reference(corpus_root: Path, reference: str) -> tuple[Path, dict[str, Any]]:
    if not reference:
        raise BatchOwnerAuthorityError("MISSING_BATCH_INTENT_REFERENCE")
    candidate = Path(reference)
    if candidate.is_absolute() or "/" in reference or "\\" in reference:
        path = candidate.expanduser().resolve(strict=False)
        root = corpus_root.resolve(strict=False)
        try:
            path.relative_to(root / BATCH_INTENT_ENTITY)
        except ValueError as exc:
            raise BatchOwnerAuthorityError("BATCH_INTENT_PATH_ESCAPE") from exc
    else:
        identity = reference.removeprefix("sha256:")
        path = corpus_path(corpus_root, BATCH_INTENT_ENTITY, identity)
    if not path.is_file():
        raise BatchOwnerAuthorityError("BATCH_INTENT_MISSING")
    payload = _load_json(path)
    stem = path.name.removesuffix(".json")
    if stem != str(payload.get("batch_intent_id", "")).removeprefix("sha256:"):
        raise BatchOwnerAuthorityError("BATCH_INTENT_PATH_BODY_MISMATCH")
    return path, payload


def _all_paths_isolated(project_root: Path, paths: Sequence[Path]) -> bool:
    if not paths:
        return False
    roots: list[Path] = []
    isolation_root = paths[0].resolve(strict=False).parent
    for path in paths:
        resolved = path.resolve(strict=False)
        if _is_path_inside(resolved, project_root):
            return False
        try:
            resolved.relative_to(isolation_root)
        except ValueError:
            return False
        if path.is_symlink():
            return False
        roots.append(resolved)
    common = Path(os.path.commonpath([str(path) for path in roots]))
    return not _is_path_inside(common, project_root)


def write_set_paths(
    *,
    output_path: Path,
    corpus_root: Path,
    ledger_path: Path,
    manager_root: Path,
) -> list[Path]:
    return [
        output_path,
        output_path.with_suffix(".md"),
        output_path.parent,
        output_path.parent / "run_placeholder",
        corpus_root,
        ledger_path,
        manager_root / "topic_bank.json",
        manager_root / "topic_registry.json",
        manager_root / "run_history.json",
        manager_root / "next_action_queue.json",
        manager_root / "manager_summary.json",
        manager_root / "runner_registry.json",
    ]


def isolated_write_set_allowed(*, project_root: Path, paths: Sequence[Path]) -> bool:
    return _all_paths_isolated(project_root.resolve(strict=True), paths)


def verify_batch_owner_authority(
    *,
    project_root: Path,
    corpus_root: Path,
    batch_id: str,
    batch_intent_reference: str | None,
    runtime_argv: Sequence[str],
    output_path: Path,
    ledger_path: Path,
    manager_root: Path,
    requested_research_stage: str,
    execution_epoch: str,
) -> BatchAuthorityResult:
    write_paths = write_set_paths(
        output_path=output_path,
        corpus_root=corpus_root,
        ledger_path=ledger_path,
        manager_root=manager_root,
    )
    if not batch_intent_reference:
        if isolated_write_set_allowed(project_root=project_root, paths=write_paths):
            return BatchAuthorityResult("PASS", None, "ISOLATED_WRITE_SET")
        raise BatchOwnerAuthorityError("MISSING_BATCH_INTENT")
    if not BATCH_ID_PATTERN.fullmatch(batch_id):
        raise BatchOwnerAuthorityError("MALFORMED_BATCH_ID")
    path, payload = load_batch_intent_reference(corpus_root, batch_intent_reference)
    errors = validate_batch_intent(payload)
    if errors:
        raise BatchOwnerAuthorityError("INVALID_BATCH_INTENT: " + "; ".join(errors))
    encoded_hash = _hash_bytes(canonical_json_bytes({key: value for key, value in payload.items() if key != "batch_intent_id"}))
    if encoded_hash != payload.get("batch_intent_id"):
        raise BatchOwnerAuthorityError("BATCH_INTENT_CONTENT_HASH_MISMATCH")
    _resolve_under(corpus_root, path.relative_to(corpus_root))
    scheduler_errors = _canonical_scheduler_errors(project_root, payload.get("scheduler") or {})
    if scheduler_errors:
        raise BatchOwnerAuthorityError(scheduler_errors[0])
    if payload.get("batch_id") != batch_id:
        raise BatchOwnerAuthorityError("BATCH_ID_MISMATCH")
    if payload.get("execution_epoch") != execution_epoch:
        raise BatchOwnerAuthorityError("EXECUTION_EPOCH_MISMATCH")
    if payload.get("project", {}).get("head") != _git_head(project_root):
        raise BatchOwnerAuthorityError("REPO_IDENTITY_MISMATCH")
    runner = payload.get("runner") or {}
    authorized_argv = normalize_runner_argv(runtime_argv)
    if list(runner.get("argv") or []) != authorized_argv:
        raise BatchOwnerAuthorityError("RUNNER_ARGV_MISMATCH")
    if runner.get("argv_hash") != runner_argv_hash(authorized_argv):
        raise BatchOwnerAuthorityError("RUNNER_ARGV_HASH_MISMATCH")
    research = payload.get("research") or {}
    if research.get("requested_stage") != requested_research_stage:
        raise BatchOwnerAuthorityError("REQUESTED_STAGE_MISMATCH")
    if requested_research_stage not in set(research.get("allowed_stage_set") or []):
        raise BatchOwnerAuthorityError("REQUESTED_STAGE_NOT_ALLOWED")
    expected_paths = payload.get("paths") or {}
    if expected_paths.get("spine_root", {}).get("resolved_path") != str(corpus_root.resolve(strict=False)):
        raise BatchOwnerAuthorityError("SPINE_ROOT_MISMATCH")
    if expected_paths.get("output_root", {}).get("resolved_path") != str(output_path.parent.resolve(strict=False)):
        raise BatchOwnerAuthorityError("OUTPUT_ROOT_MISMATCH")
    if expected_paths.get("ledger_path", {}).get("resolved_path") != str(ledger_path.resolve(strict=False)):
        raise BatchOwnerAuthorityError("LEDGER_PATH_MISMATCH")
    manager_paths = expected_paths.get("manager_paths") or {}
    for name, manager_path in {
        "topic_bank": manager_root / "topic_bank.json",
        "registry": manager_root / "topic_registry.json",
        "history": manager_root / "run_history.json",
        "queue": manager_root / "next_action_queue.json",
        "summary": manager_root / "manager_summary.json",
        "runner_registry": manager_root / "runner_registry.json",
    }.items():
        if manager_paths.get(name, {}).get("resolved_path") != str(manager_path.resolve(strict=False)):
            raise BatchOwnerAuthorityError("MANAGER_PATH_MISMATCH")
    return BatchAuthorityResult("PASS", str(payload["batch_intent_id"]), "CANONICAL_BATCH_INTENT")
