"""Native Evidence Activation 的唯讀啟動契約與基線盤點。"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from app.research.contracts import content_hash


POLICY_SCHEMA = "native-evidence-activation-policy.v1"
PLAN_SCHEMA = "native-evidence-execution-plan.v1"
BASELINE_SCHEMA = "native-evidence-activation-baseline.v1"
MINIMUM_HOST_FREE_PERCENT = 10
MINIMUM_HOST_RESERVE_BYTES = 20 * 1024**3

_REQUIRED_SURFACES = {
    "queue_paths": {
        "AUTONOMOUS_NEXT_ACTION_QUEUE": "artifacts/autonomous_research/next_action_queue.json",
    },
    "runner_argv_sources": {
        "DAILY_RESEARCH_QUOTA_ENTRYPOINT": "scripts/run_daily_research_quota.sh",
        "AUTONOMOUS_RESEARCH_RUNNER": "scripts/run_autonomous_research.py",
    },
    "scheduler_paths": {
        "PM_RESEARCH_HARNESS_SCHEDULER": "scripts/com.new-top10.pm-research-harness.plist",
        "FOG_RESEARCH_WORKER_SCHEDULER": "scripts/com.new-top10.fog-research-worker.plist",
    },
    "production_paths": {
        "PRODUCTION_BASELINE": "models/baseline_stats.json",
        "PRODUCTION_MODEL": "models/latest_lgbm.pkl",
        "PRODUCTION_PROMOTION_CODE": "app/modeling/model_runtime_promotion.py",
        "PRODUCTION_RANKING_CODE": "app/agent_b_ranking.py",
        "PRODUCTION_SIGNAL_WEIGHTS": "config/signals.yaml",
    },
}
_REQUIRED_STORAGE = {
    "RESEARCH_SPINE_CORPUS": "artifacts/autonomous_research/research_spine",
    "RESEARCH_LEDGER": "data/research/research_ledger.duckdb",
    "RUN_OUTPUT_ARCHIVE": "artifacts/autonomous_research/run_outputs",
    "DAILY_RESEARCH_LOGS": "logs/daily_research",
}

_CAPACITY_QUANTITIES = {
    "max_bytes",
    "max_file_count",
    "max_bytes_per_cycle",
    "max_files_per_cycle",
    "normal_growth_bytes_per_hour",
    "burst_window_minutes",
    "stabilization_minutes",
    "retention_days",
    "sampling_interval_seconds",
    "rss_growth_limit_bytes",
    "swap_growth_limit_bytes",
}
_SAFETY = {
    "does_not_train_model": True,
    "does_not_change_production_ranking": True,
    "production_promotion_allowed": False,
    "does_not_change_queue_selection": True,
    "does_not_change_scheduler": True,
}


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _exact_fields(value: object, fields: set[str], prefix: str) -> list[str]:
    mapping = _mapping(value)
    errors = [f"{prefix}{field} is required" for field in sorted(fields) if field not in mapping]
    errors.extend(f"{prefix}{field} is not allowed" for field in sorted(set(mapping) - fields))
    return errors


def _hash_errors(value: object, field: str) -> list[str]:
    if not isinstance(value, str) or len(value) != 71 or not value.startswith("sha256:"):
        return [f"{field} must be sha256:<64 lowercase hex>"]
    if any(character not in "0123456789abcdef" for character in value[7:]):
        return [f"{field} must be sha256:<64 lowercase hex>"]
    return []


def _relative_path_errors(value: object, field: str) -> list[str]:
    if not isinstance(value, str) or not value:
        return [f"{field} must be a non-empty repo-relative path"]
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or value != path.as_posix():
        return [f"{field} must be a normalized repo-relative path"]
    return []


def _positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _string_list_errors(value: object, field: str, *, paths: bool = False) -> list[str]:
    if not isinstance(value, list) or not value:
        return [f"{field} must be a non-empty list"]
    errors: list[str] = []
    if len(value) != len(set(item for item in value if isinstance(item, str))):
        errors.append(f"{field} must not contain duplicates")
    for index, item in enumerate(value):
        if paths:
            errors.extend(_relative_path_errors(item, f"{field}[{index}]"))
        elif not isinstance(item, str) or not item:
            errors.append(f"{field}[{index}] must be non-empty")
    return errors


def load_activation_policy(path: Path | str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("activation policy root must be an object")
    return payload


def validate_activation_policy(payload: Mapping[str, Any]) -> list[str]:
    fields = {
        "schema_version",
        "policy_version",
        "enabled",
        "activation_mode",
        "capacity_budget",
        "baseline_inventory",
        "safety",
    }
    errors = _exact_fields(payload, fields, "")
    if payload.get("schema_version") != POLICY_SCHEMA:
        errors.append(f"schema_version must be {POLICY_SCHEMA}")
    if not isinstance(payload.get("policy_version"), str) or not payload.get("policy_version"):
        errors.append("policy_version must be non-empty")
    if not isinstance(payload.get("enabled"), bool):
        errors.append("enabled must be boolean")
    if payload.get("activation_mode") not in {"DISABLED", "DRY_RUN", "CANARY"}:
        errors.append("activation_mode must be DISABLED, DRY_RUN, or CANARY")
    enabled = payload.get("enabled")
    mode = payload.get("activation_mode")
    if enabled is False and mode != "DISABLED":
        errors.append("disabled policy must use DISABLED activation_mode")
    if enabled is True and mode == "DISABLED":
        errors.append("enabled policy must use DRY_RUN or CANARY activation_mode")

    capacity_fields = _CAPACITY_QUANTITIES | {
        "status",
        "minimum_host_free_percent",
        "minimum_host_reserve_bytes",
    }
    capacity = _mapping(payload.get("capacity_budget"))
    errors.extend(_exact_fields(capacity, capacity_fields, "capacity_budget."))
    if capacity.get("status") not in {"UNKNOWN", "KNOWN"}:
        errors.append("capacity_budget.status must be UNKNOWN or KNOWN")
    for field in sorted(_CAPACITY_QUANTITIES):
        value = capacity.get(field)
        if capacity.get("status") == "UNKNOWN" and value is not None:
            errors.append(f"capacity_budget.{field} must be null while status is UNKNOWN")
        if capacity.get("status") == "KNOWN" and not _positive_int(value):
            errors.append(f"capacity_budget.{field} must be a positive integer when KNOWN")
    free_percent = capacity.get("minimum_host_free_percent")
    if (
        not isinstance(free_percent, (int, float))
        or isinstance(free_percent, bool)
        or not math.isfinite(free_percent)
        or not MINIMUM_HOST_FREE_PERCENT <= free_percent <= 100
    ):
        errors.append("capacity_budget.minimum_host_free_percent must be finite and at least 10")
    reserve = capacity.get("minimum_host_reserve_bytes")
    if not _positive_int(reserve) or reserve < MINIMUM_HOST_RESERVE_BYTES:
        errors.append("capacity_budget.minimum_host_reserve_bytes must be at least 20 GiB")
    if capacity.get("status") == "KNOWN" and all(
        _positive_int(capacity.get(field)) for field in _CAPACITY_QUANTITIES
    ):
        if capacity.get("max_bytes_per_cycle", 0) > capacity.get("max_bytes", 0):
            errors.append("capacity_budget.max_bytes_per_cycle must not exceed max_bytes")
        if capacity.get("max_files_per_cycle", 0) > capacity.get("max_file_count", 0):
            errors.append("capacity_budget.max_files_per_cycle must not exceed max_file_count")
        if capacity.get("burst_window_minutes", 0) > capacity.get("stabilization_minutes", 0):
            errors.append("capacity_budget.burst_window_minutes must not exceed stabilization_minutes")

    inventory_fields = {
        "queue_paths",
        "runner_argv_sources",
        "scheduler_paths",
        "production_paths",
        "storage_write_paths",
    }
    inventory = _mapping(payload.get("baseline_inventory"))
    errors.extend(_exact_fields(inventory, inventory_fields, "baseline_inventory."))
    surface_fields = {"role", "path"}
    for field, required in _REQUIRED_SURFACES.items():
        rows = inventory.get(field)
        if not isinstance(rows, list):
            errors.append(f"baseline_inventory.{field} must be a list")
            continue
        observed: dict[str, str] = {}
        for index, row_value in enumerate(rows):
            row = _mapping(row_value)
            prefix = f"baseline_inventory.{field}[{index}]."
            errors.extend(_exact_fields(row, surface_fields, prefix))
            errors.extend(_relative_path_errors(row.get("path"), prefix + "path"))
            role = row.get("role")
            if not isinstance(role, str) or not role:
                errors.append(prefix + "role must be non-empty")
            elif role in observed:
                errors.append(f"baseline_inventory.{field} contains duplicate role {role}")
            elif isinstance(row.get("path"), str):
                observed[role] = row["path"]
        if observed != required:
            errors.append(f"baseline_inventory.{field} must equal canonical required role/path set")
    storage_rows = inventory.get("storage_write_paths")
    if not isinstance(storage_rows, list) or not storage_rows:
        errors.append("baseline_inventory.storage_write_paths must be a non-empty list")
    else:
        seen: set[str] = set()
        row_fields = {"role", "path", "category", "retention_class", "rebuildable"}
        observed_storage: dict[str, str] = {}
        for index, row_value in enumerate(storage_rows):
            row = _mapping(row_value)
            prefix = f"baseline_inventory.storage_write_paths[{index}]."
            errors.extend(_exact_fields(row, row_fields, prefix))
            errors.extend(_relative_path_errors(row.get("path"), prefix + "path"))
            role = row.get("role")
            if not isinstance(role, str) or not role:
                errors.append(prefix + "role must be non-empty")
            elif role in observed_storage:
                errors.append("baseline_inventory.storage_write_paths contains duplicate role")
            elif isinstance(row.get("path"), str):
                observed_storage[role] = row["path"]
            if isinstance(row.get("path"), str):
                if row["path"] in seen:
                    errors.append("baseline_inventory.storage_write_paths must not contain duplicates")
                seen.add(row["path"])
            if not isinstance(row.get("category"), str) or not row.get("category"):
                errors.append(prefix + "category must be non-empty")
            if not isinstance(row.get("retention_class"), str) or not row.get("retention_class"):
                errors.append(prefix + "retention_class must be non-empty")
            if not isinstance(row.get("rebuildable"), bool):
                errors.append(prefix + "rebuildable must be boolean")
        if observed_storage != _REQUIRED_STORAGE:
            errors.append("baseline_inventory.storage_write_paths must equal canonical required role/path set")

    safety = _mapping(payload.get("safety"))
    errors.extend(_exact_fields(safety, set(_SAFETY), "safety."))
    for field, expected in _SAFETY.items():
        if safety.get(field) is not expected:
            errors.append(f"safety.{field} must be {str(expected).lower()}")
    return errors


def assess_activation_readiness(policy: Mapping[str, Any]) -> dict[str, Any]:
    errors = validate_activation_policy(policy)
    reasons: list[str] = []
    if errors:
        reasons.append("POLICY_INVALID")
    if policy.get("enabled") is not True:
        reasons.append("ACTIVATION_DISABLED")
    capacity = _mapping(policy.get("capacity_budget"))
    if capacity.get("status") != "KNOWN":
        reasons.append("CAPACITY_BUDGET_UNKNOWN")
    return {
        "status": "GO" if not reasons else "NO-GO",
        "reason_codes": sorted(set(reasons)),
        "validation_errors": errors,
    }


def _rfc3339_utc_errors(value: object, field: str) -> list[str]:
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", value
    ):
        return [f"{field} must be an RFC3339 UTC timestamp"]
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return [f"{field} must be an RFC3339 UTC timestamp"]
    return []


def _baseline_errors(
    baseline: Mapping[str, Any], policy: Mapping[str, Any], project_root: Path
) -> list[str]:
    errors: list[str] = []
    if baseline.get("schema_version") != BASELINE_SCHEMA:
        errors.append(f"baseline.schema_version must be {BASELINE_SCHEMA}")
    if baseline.get("policy_version") != policy.get("policy_version"):
        errors.append("baseline.policy_version does not match trusted policy")
    trusted_policy_hash = content_hash(policy)
    if baseline.get("policy_hash") != trusted_policy_hash:
        errors.append("baseline.policy_hash does not match trusted policy")
    if baseline.get("baseline_id") != content_hash(
        baseline, omit={"baseline_id", "generated_at"}
    ):
        errors.append("baseline.baseline_id does not match normalized content")
    anchor = _mapping(baseline.get("anchor"))
    if anchor.get("anchor_type") != "PRE_ACTIVATION":
        errors.append("baseline.anchor.anchor_type must be PRE_ACTIVATION")
    if anchor.get("policy_hash") != trusted_policy_hash:
        errors.append("baseline.anchor.policy_hash does not match trusted policy")
    provenance = _mapping(baseline.get("provenance"))
    if provenance != {
        "builder": "app.research.native_evidence_activation",
        "builder_schema_version": BASELINE_SCHEMA,
        "inventory_mode": "READ_ONLY_FILESYSTEM_INVENTORY",
    }:
        errors.append("baseline.provenance is not trusted")
    locks = _mapping(baseline.get("locks"))
    if anchor.get("runner_argv_contract_hash") != locks.get("runner_argv_contract_hash"):
        errors.append("baseline anchor does not bind runner argv contract")
    expected_categories = {
        "queue": _REQUIRED_SURFACES["queue_paths"],
        "runner_argv_sources": _REQUIRED_SURFACES["runner_argv_sources"],
        "scheduler": _REQUIRED_SURFACES["scheduler_paths"],
        "production": _REQUIRED_SURFACES["production_paths"],
    }
    for category, required in expected_categories.items():
        rows = locks.get(category)
        if not isinstance(rows, list):
            errors.append(f"baseline.locks.{category} must be a list")
            continue
        observed = {row.get("role"): row for row in rows if isinstance(row, Mapping)}
        if set(observed) != set(required):
            errors.append(f"baseline.locks.{category} roles are incomplete")
            continue
        for role, relative in required.items():
            row = observed[role]
            if row.get("path") != relative or row.get("exists") is not True:
                errors.append(f"baseline lock {role} is missing or has wrong path")
                continue
            errors.extend(_hash_errors(row.get("content_hash"), f"baseline lock {role}"))
            try:
                current = _resolve_within_root(project_root, relative)
            except ValueError as exc:
                errors.append(str(exc))
                continue
            if not current.is_file() or _raw_file_hash(current) != row.get("content_hash"):
                errors.append(f"baseline lock {role} drifted from project root")
    return errors


def validate_execution_plan(
    payload: Mapping[str, Any], *, policy: Mapping[str, Any], baseline: Mapping[str, Any], project_root: Path | str
) -> list[str]:
    fields = {
        "schema_version",
        "plan_id",
        "baseline_id",
        "policy_version",
        "policy_hash",
        "research_batch_id",
        "intent_id",
        "run_id",
        "trial_spec_ids",
        "research_stage",
        "lineage",
        "runner",
        "safety",
        "created_at",
    }
    errors = _exact_fields(payload, fields, "")
    root = Path(project_root).resolve()
    policy_errors = validate_activation_policy(policy)
    errors.extend(f"trusted policy: {error}" for error in policy_errors)
    errors.extend(_baseline_errors(baseline, policy, root))
    if payload.get("schema_version") != PLAN_SCHEMA:
        errors.append(f"schema_version must be {PLAN_SCHEMA}")
    for field in ("policy_version", "research_batch_id", "run_id", "research_stage"):
        if not isinstance(payload.get(field), str) or not payload.get(field):
            errors.append(f"{field} must be non-empty")
    for field in ("plan_id", "baseline_id", "policy_hash"):
        errors.extend(_hash_errors(payload.get(field), field))
    if payload.get("policy_version") != policy.get("policy_version"):
        errors.append("policy_version does not match trusted policy")
    if payload.get("policy_hash") != content_hash(policy):
        errors.append("policy_hash does not match trusted policy")
    if payload.get("baseline_id") != baseline.get("baseline_id"):
        errors.append("baseline_id does not match trusted baseline")
    if not isinstance(payload.get("intent_id"), str) or not re.fullmatch(
        r"intent-[0-9a-f]{32}", payload["intent_id"]
    ):
        errors.append("intent_id must use intent-<32 lowercase hex> format")
    if not isinstance(payload.get("run_id"), str) or not re.fullmatch(
        r"run-[0-9a-f]{32}", payload["run_id"]
    ):
        errors.append("run_id must use run-<32 lowercase hex> format")
    if not isinstance(payload.get("research_batch_id"), str) or not re.fullmatch(
        r"research-\d{4}-\d{2}-\d{2}-\d{6}-\d+", payload["research_batch_id"]
    ):
        errors.append("research_batch_id must use research-YYYY-MM-DD-HHMMSS-PID format")
    if payload.get("research_stage") not in {"DEVELOPMENT_SCREEN", "COARSE_SCREEN"}:
        errors.append("research_stage must be DEVELOPMENT_SCREEN or COARSE_SCREEN")
    errors.extend(_rfc3339_utc_errors(payload.get("created_at"), "created_at"))
    errors.extend(_string_list_errors(payload.get("trial_spec_ids"), "trial_spec_ids"))
    if isinstance(payload.get("trial_spec_ids"), list):
        for index, value in enumerate(payload["trial_spec_ids"]):
            errors.extend(_hash_errors(value, f"trial_spec_ids[{index}]"))

    lineage_fields = {
        "dataset_hash",
        "ranking_source_hash",
        "regime_id",
        "regime_authority_hash",
        "episode_ids",
        "sealed_usage_status",
    }
    lineage = _mapping(payload.get("lineage"))
    errors.extend(_exact_fields(lineage, lineage_fields, "lineage."))
    for field in ("dataset_hash", "ranking_source_hash", "regime_authority_hash"):
        errors.extend(_hash_errors(lineage.get(field), f"lineage.{field}"))
    if not isinstance(lineage.get("regime_id"), str) or not lineage.get("regime_id"):
        errors.append("lineage.regime_id must be non-empty")
    errors.extend(_string_list_errors(lineage.get("episode_ids"), "lineage.episode_ids"))
    if lineage.get("sealed_usage_status") != "PROVEN_NON_SEALED":
        errors.append("lineage.sealed_usage_status must be PROVEN_NON_SEALED")
    if lineage.get("regime_id") in {"UNKNOWN", "UNSCOPED", "SEALED"}:
        errors.append("lineage.regime_id must be an explicit non-sealed regime")

    runner_fields = {"script_path", "script_hash", "argv", "argv_hash"}
    runner = _mapping(payload.get("runner"))
    errors.extend(_exact_fields(runner, runner_fields, "runner."))
    errors.extend(_relative_path_errors(runner.get("script_path"), "runner.script_path"))
    errors.extend(_hash_errors(runner.get("script_hash"), "runner.script_hash"))
    errors.extend(_hash_errors(runner.get("argv_hash"), "runner.argv_hash"))
    errors.extend(_string_list_errors(runner.get("argv"), "runner.argv"))
    if isinstance(runner.get("argv"), list) and runner.get("argv_hash") != content_hash({"argv": runner["argv"]}):
        errors.append("runner.argv_hash does not match argv")
    runner_lock_rows = _mapping(baseline.get("locks")).get("runner_argv_sources")
    runner_locks = {
        row.get("role"): row for row in runner_lock_rows or [] if isinstance(row, Mapping)
    }
    trusted_runner = runner_locks.get("AUTONOMOUS_RESEARCH_RUNNER", {})
    if runner.get("script_path") != trusted_runner.get("path"):
        errors.append("runner.script_path does not match trusted baseline")
    if runner.get("script_hash") != trusted_runner.get("content_hash"):
        errors.append("runner.script_hash does not match trusted baseline")
    argv = runner.get("argv")
    if isinstance(argv, list):
        if not argv or argv[0] != runner.get("script_path"):
            errors.append("runner.argv[0] must equal runner.script_path")
        for required_flag in ("--execute", "--closed-regime-research", "--research-batch-id"):
            if required_flag not in argv:
                errors.append(f"runner.argv must contain {required_flag}")

    safety = _mapping(payload.get("safety"))
    errors.extend(_exact_fields(safety, set(_SAFETY), "safety."))
    for field, expected in _SAFETY.items():
        if safety.get(field) is not expected:
            errors.append(f"safety.{field} must be {str(expected).lower()}")
    if payload.get("plan_id") != content_hash(payload, omit={"plan_id"}):
        errors.append("plan_id does not match normalized content")
    return errors


def _resolve_within_root(root: Path, relative: str) -> Path:
    candidate = root / relative
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path escapes project root: {relative}") from exc
    return resolved


def _raw_file_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _file_lock(root: Path, surface: Mapping[str, Any]) -> dict[str, Any]:
    relative = str(surface["path"])
    path = _resolve_within_root(root, relative)
    exists = path.is_file() and not path.is_symlink()
    digest = None
    size = 0
    if exists:
        data = path.read_bytes()
        digest = "sha256:" + hashlib.sha256(data).hexdigest()
        size = len(data)
    return {
        "role": surface["role"],
        "path": relative,
        "exists": exists,
        "content_hash": digest,
        "bytes": size,
    }


def _storage_inventory(root: Path, row: Mapping[str, Any]) -> dict[str, Any]:
    target = _resolve_within_root(root, str(row["path"]))
    files: Sequence[Path]
    if target.is_file() and not target.is_symlink():
        files = [target]
    elif target.is_dir() and not target.is_symlink():
        files = sorted(path for path in target.rglob("*") if path.is_file() and not path.is_symlink())
    else:
        files = []
    return {
        **dict(row),
        "exists": target.exists(),
        "bytes": sum(path.stat().st_size for path in files),
        "file_count": len(files),
    }


def build_baseline_inventory(*, project_root: Path | str, policy_path: Path | str) -> dict[str, Any]:
    """只讀取既有 surface，回傳可序列化基線；本函式不寫 artifact。"""
    root = Path(project_root).resolve()
    policy = load_activation_policy(policy_path)
    errors = validate_activation_policy(policy)
    if errors:
        raise ValueError("invalid activation policy: " + "; ".join(errors))
    inventory = _mapping(policy["baseline_inventory"])
    queue = [_file_lock(root, row) for row in inventory["queue_paths"]]
    runner = [_file_lock(root, row) for row in inventory["runner_argv_sources"]]
    scheduler = [_file_lock(root, row) for row in inventory["scheduler_paths"]]
    production = [_file_lock(root, row) for row in inventory["production_paths"]]
    runner_argv_contract_hash = content_hash({"sources": runner})
    storage = [_storage_inventory(root, row) for row in inventory["storage_write_paths"]]
    usage = shutil.disk_usage(root)
    capacity = _mapping(policy["capacity_budget"])
    free_percent = (usage.free / usage.total * 100) if usage.total else 0.0
    host_gate = (
        free_percent >= float(capacity["minimum_host_free_percent"])
        and usage.free >= int(capacity["minimum_host_reserve_bytes"])
    )
    readiness = assess_activation_readiness(policy)
    required_locks = queue + runner + scheduler + production
    if any(not lock["exists"] or lock["content_hash"] is None for lock in required_locks):
        readiness["reason_codes"] = sorted(set(readiness["reason_codes"] + ["MISSING_REQUIRED_LOCK"]))
        readiness["status"] = "NO-GO"
    if not host_gate:
        readiness["reason_codes"] = sorted(set(readiness["reason_codes"] + ["HOST_CAPACITY_BELOW_RESERVE"]))
        readiness["status"] = "NO-GO"
    payload: dict[str, Any] = {
        "schema_version": BASELINE_SCHEMA,
        "baseline_id": "",
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "policy_version": policy["policy_version"],
        "policy_hash": content_hash(policy),
        "anchor": {
            "anchor_type": "PRE_ACTIVATION",
            "policy_hash": content_hash(policy),
            "runner_argv_contract_hash": runner_argv_contract_hash,
        },
        "provenance": {
            "builder": "app.research.native_evidence_activation",
            "builder_schema_version": BASELINE_SCHEMA,
            "inventory_mode": "READ_ONLY_FILESYSTEM_INVENTORY",
        },
        "status": readiness["status"],
        "reason_codes": readiness["reason_codes"],
        "host_capacity": {
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
            "free_percent": round(free_percent, 6),
            "startup_reserve_gate_pass": host_gate,
        },
        "locks": {
            "queue": queue,
            "runner_argv_sources": runner,
            "runner_argv_contract_hash": runner_argv_contract_hash,
            "scheduler": scheduler,
            "production": production,
        },
        "storage_write_inventory": storage,
    }
    payload["baseline_id"] = content_hash(payload, omit={"baseline_id", "generated_at"})
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="建立 Native Evidence Activation 唯讀基線盤點")
    parser.add_argument("--policy", default="config/native_evidence_activation_policy_v1.json")
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args()
    payload = build_baseline_inventory(project_root=args.project_root, policy_path=args.policy)
    print(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False))
    return 0 if payload["status"] == "GO" else 2


if __name__ == "__main__":
    raise SystemExit(main())
