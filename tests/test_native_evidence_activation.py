from __future__ import annotations

import copy
import json
from pathlib import Path

from app.research.contracts import content_hash
from app.research.native_evidence_activation import (
    assess_activation_readiness,
    build_baseline_inventory,
    load_activation_policy,
    validate_activation_policy,
    validate_execution_plan,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = PROJECT_ROOT / "config" / "native_evidence_activation_policy_v1.json"


def test_repository_policy_is_strict_and_bounded_canary_is_go() -> None:
    policy = load_activation_policy(POLICY_PATH)

    assert validate_activation_policy(policy) == []
    readiness = assess_activation_readiness(policy)
    assert readiness == {"status": "GO", "reason_codes": [], "validation_errors": []}
    assert policy["enabled"] is True
    assert policy["activation_mode"] == "CANARY"
    assert policy["capacity_budget"]["status"] == "KNOWN"
    storage = {row["role"]: row for row in policy["baseline_inventory"]["storage_write_paths"]}
    assert storage["RESEARCH_SPINE_CORPUS"]["retention_class"] == "PERMANENT"
    assert storage["RESEARCH_SPINE_CORPUS"]["rebuildable"] is False
    assert storage["RUN_OUTPUT_ARCHIVE"]["retention_class"] == "30_DAYS_ROTATING"
    assert storage["RUN_OUTPUT_ARCHIVE"]["rebuildable"] is True
    assert storage["DAILY_RESEARCH_LOGS"]["retention_class"] == "30_DAYS_ROTATING"
    assert storage["DAILY_RESEARCH_LOGS"]["rebuildable"] is True


def test_policy_rejects_unknown_fields_and_partial_capacity_budget() -> None:
    policy = load_activation_policy(POLICY_PATH)
    policy["unexpected"] = True
    del policy["capacity_budget"]["max_bytes_per_cycle"]

    errors = validate_activation_policy(policy)

    assert "unexpected is not allowed" in errors
    assert "capacity_budget.max_bytes_per_cycle is required" in errors


def test_policy_rejects_lowered_reserve_bool_nonfinite_and_semantic_inversion() -> None:
    policy = load_activation_policy(POLICY_PATH)
    budget = policy["capacity_budget"]
    budget.update(
        {
            "status": "KNOWN",
            "max_bytes": 10,
            "max_file_count": 10,
            "max_bytes_per_cycle": 11,
            "max_files_per_cycle": True,
            "normal_growth_bytes_per_hour": 1,
            "burst_window_minutes": 10,
            "stabilization_minutes": 5,
            "retention_days": 1,
            "sampling_interval_seconds": 1,
            "rss_growth_limit_bytes": 1,
            "swap_growth_limit_bytes": 1,
            "minimum_host_free_percent": float("nan"),
            "minimum_host_reserve_bytes": 1,
        }
    )

    errors = validate_activation_policy(policy)

    assert "capacity_budget.max_files_per_cycle must be a positive integer when KNOWN" in errors
    assert "capacity_budget.minimum_host_free_percent must be finite and at least 10" in errors
    assert "capacity_budget.minimum_host_reserve_bytes must be at least 20 GiB" in errors

    policy = load_activation_policy(POLICY_PATH)
    budget = policy["capacity_budget"]
    budget.update({field: 1 for field in budget if field not in {"status", "minimum_host_free_percent", "minimum_host_reserve_bytes"}})
    budget.update({
        "status": "KNOWN",
        "max_bytes": 10,
        "max_bytes_per_cycle": 11,
        "max_file_count": 10,
        "max_files_per_cycle": 11,
        "burst_window_minutes": 10,
        "stabilization_minutes": 5,
    })
    semantic_errors = validate_activation_policy(policy)
    assert "capacity_budget.max_bytes_per_cycle must not exceed max_bytes" in semantic_errors
    assert "capacity_budget.max_files_per_cycle must not exceed max_file_count" in semantic_errors
    assert "capacity_budget.burst_window_minutes must not exceed stabilization_minutes" in semantic_errors

    policy = load_activation_policy(POLICY_PATH)
    policy["activation_mode"] = "DISABLED"
    assert "enabled policy must use DRY_RUN or CANARY activation_mode" in validate_activation_policy(policy)


def test_policy_requires_canonical_inventory_roles_and_paths() -> None:
    policy = load_activation_policy(POLICY_PATH)
    policy["baseline_inventory"]["production_paths"].pop()
    errors = validate_activation_policy(policy)
    assert "baseline_inventory.production_paths must equal canonical required role/path set" in errors


def _execution_plan(policy: dict[str, object], baseline: dict[str, object]) -> dict[str, object]:
    hash_value = "sha256:" + "1" * 64
    runner_lock = next(
        row
        for row in baseline["locks"]["runner_argv_sources"]  # type: ignore[index]
        if row["role"] == "AUTONOMOUS_RESEARCH_RUNNER"
    )
    argv = [
        "scripts/run_autonomous_research.py",
        "--execute",
        "--closed-regime-research",
        "--research-batch-id",
        "research-2026-08-14-010203-123",
    ]
    plan: dict[str, object] = {
        "schema_version": "native-evidence-execution-plan.v1",
        "plan_id": "",
        "baseline_id": baseline["baseline_id"],
        "policy_version": policy["policy_version"],
        "policy_hash": content_hash(policy),
        "research_batch_id": "research-2026-08-14-010203-123",
        "intent_id": "intent-" + "a" * 32,
        "run_id": "run-" + "b" * 32,
        "trial_spec_ids": [hash_value],
        "research_stage": "DEVELOPMENT_SCREEN",
        "lineage": {
            "dataset_hash": hash_value,
            "ranking_source_hash": hash_value,
            "regime_id": "RISK_OFF",
            "regime_authority_hash": hash_value,
            "episode_ids": ["episode-001"],
            "sealed_usage_status": "PROVEN_NON_SEALED",
        },
        "runner": {
            "script_path": "scripts/run_autonomous_research.py",
            "script_hash": runner_lock["content_hash"],
            "argv": argv,
            "argv_hash": content_hash({"argv": argv}),
        },
        "safety": {
            "does_not_train_model": True,
            "does_not_change_production_ranking": True,
            "production_promotion_allowed": False,
            "does_not_change_queue_selection": True,
            "does_not_change_scheduler": True,
        },
        "created_at": "2026-08-14T00:00:00Z",
    }
    plan["plan_id"] = content_hash(plan, omit={"plan_id"})
    return plan


def test_execution_plan_is_strict_identity_and_safety_contract() -> None:
    policy = load_activation_policy(POLICY_PATH)
    baseline = build_baseline_inventory(project_root=PROJECT_ROOT, policy_path=POLICY_PATH)
    plan = _execution_plan(policy, baseline)
    kwargs = {"policy": policy, "baseline": baseline, "project_root": PROJECT_ROOT}
    assert validate_execution_plan(plan, **kwargs) == []

    unsafe = copy.deepcopy(plan)
    unsafe["safety"]["does_not_train_model"] = False  # type: ignore[index]
    assert "safety.does_not_train_model must be true" in validate_execution_plan(unsafe, **kwargs)

    mismatched = copy.deepcopy(plan)
    mismatched["runner"]["argv"].append("--rerun")  # type: ignore[index,union-attr]
    errors = validate_execution_plan(mismatched, **kwargs)
    assert "runner.argv_hash does not match argv" in errors
    assert "plan_id does not match normalized content" in errors


def test_execution_plan_rejects_untrusted_ids_stage_lineage_and_bindings() -> None:
    policy = load_activation_policy(POLICY_PATH)
    baseline = build_baseline_inventory(project_root=PROJECT_ROOT, policy_path=POLICY_PATH)
    kwargs = {"policy": policy, "baseline": baseline, "project_root": PROJECT_ROOT}
    plan = _execution_plan(policy, baseline)
    plan.update(
        {
            "intent_id": "intent-not-a-uuid",
            "run_id": "run-1",
            "research_batch_id": "UNSCOPED",
            "research_stage": "SEALED",
            "created_at": "yesterday",
            "policy_hash": "sha256:" + "0" * 64,
        }
    )
    plan["lineage"]["regime_id"] = "UNKNOWN"  # type: ignore[index]
    plan["runner"]["script_hash"] = "sha256:" + "0" * 64  # type: ignore[index]

    errors = validate_execution_plan(plan, **kwargs)

    assert "intent_id must use intent-<32 lowercase hex> format" in errors
    assert "run_id must use run-<32 lowercase hex> format" in errors
    assert "research_batch_id must use research-YYYY-MM-DD-HHMMSS-PID format" in errors
    assert "research_stage must be DEVELOPMENT_SCREEN or COARSE_SCREEN" in errors
    assert "created_at must be an RFC3339 UTC timestamp" in errors
    assert "lineage.regime_id must be an explicit non-sealed regime" in errors
    assert "policy_hash does not match trusted policy" in errors
    assert "runner.script_hash does not match trusted baseline" in errors


def test_baseline_builder_hashes_surfaces_and_only_reads(tmp_path: Path) -> None:
    policy = load_activation_policy(POLICY_PATH)
    policy["baseline_inventory"] = {
        **policy["baseline_inventory"],
    }
    surface_rows = []
    for key in ("queue_paths", "runner_argv_sources", "scheduler_paths", "production_paths"):
        surface_rows.extend(policy["baseline_inventory"][key])  # type: ignore[index]
    for row in surface_rows:
        relative = row["path"]
        data = relative.encode()
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    spine_file = tmp_path / "artifacts/autonomous_research/research_spine/one.json"
    spine_file.parent.mkdir(parents=True, exist_ok=True)
    spine_file.write_bytes(b"1234")
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*") if path.is_file())

    baseline = build_baseline_inventory(project_root=tmp_path, policy_path=policy_path)

    after = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*") if path.is_file())
    assert after == before
    assert baseline["status"] == "GO"
    assert baseline["locks"]["queue"][0]["content_hash"].startswith("sha256:")
    assert all(row["exists"] for row in baseline["locks"]["production"])
    assert baseline["locks"]["runner_argv_contract_hash"].startswith("sha256:")
    assert baseline["storage_write_inventory"][0]["bytes"] == 4
    assert baseline["storage_write_inventory"][0]["file_count"] == 1


def test_baseline_fails_closed_for_missing_lock_and_symlink_escape(tmp_path: Path) -> None:
    policy = load_activation_policy(POLICY_PATH)
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(json.dumps(policy), encoding="utf-8")

    missing = build_baseline_inventory(project_root=tmp_path, policy_path=policy_path)
    assert missing["status"] == "NO-GO"
    assert "MISSING_REQUIRED_LOCK" in missing["reason_codes"]

    outside = tmp_path.parent / "outside-runner.py"
    outside.write_text("pass\n", encoding="utf-8")
    escaped = tmp_path / "scripts/run_autonomous_research.py"
    escaped.parent.mkdir(parents=True, exist_ok=True)
    escaped.symlink_to(outside)
    try:
        build_baseline_inventory(project_root=tmp_path, policy_path=policy_path)
    except ValueError as exc:
        assert "path escapes project root" in str(exc)
    else:
        raise AssertionError("symlink escape must fail closed")


def test_baseline_fails_closed_when_storage_budget_is_exceeded(tmp_path: Path) -> None:
    policy = load_activation_policy(POLICY_PATH)
    surface_rows = []
    for key in ("queue_paths", "runner_argv_sources", "scheduler_paths", "production_paths"):
        surface_rows.extend(policy["baseline_inventory"][key])
    for row in surface_rows:
        path = tmp_path / row["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(row["role"], encoding="utf-8")
    spine = tmp_path / "artifacts/autonomous_research/research_spine/oversized.json"
    spine.parent.mkdir(parents=True, exist_ok=True)
    spine.write_bytes(b"1234")
    policy["capacity_budget"]["max_bytes"] = 1
    policy["capacity_budget"]["max_bytes_per_cycle"] = 1
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(json.dumps(policy), encoding="utf-8")

    baseline = build_baseline_inventory(project_root=tmp_path, policy_path=policy_path)

    assert baseline["status"] == "NO-GO"
    assert "STORAGE_BYTES_BUDGET_EXCEEDED" in baseline["reason_codes"]
