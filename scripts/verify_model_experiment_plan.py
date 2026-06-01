#!/usr/bin/env python3
"""驗證 MODEL-EXP-01 plan artifact。

此驗證確保模型實驗計畫沒有跳過 shadow gate、沒有包含 blocked candidate，
也沒有允許 production promotion。
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
MODEL_EXPERIMENTS_DIR = ARTIFACTS_DIR / "model_experiments"
REQUIRED_EXPERIMENTS = {
    "model_exp_candidate_persistence_only",
    "model_exp_portfolio_risk_overlay_only",
    "model_exp_regime_feature_group_ablation",
    "model_exp_combined_conservative",
}
FORBIDDEN_CANDIDATES = {
    "market_context",
    "fundamentals",
    "chip_flow",
    "industry_rotation",
    "weekend_research_matrix",
}
CONTRACT_TRUE_FLAGS = {
    "plan_only",
    "shadow_inputs_only",
    "does_not_train_model",
    "does_not_write_models_latest_lgbm",
    "does_not_change_risk_adjusted_score",
    "does_not_change_production_ranking",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify MODEL-EXP-01 plan")
    parser.add_argument("--artifact", default=None)
    parser.add_argument("--output", default="artifacts/model_experiments/model_exp_plan_verification_latest.json")
    return parser.parse_args()


def resolve_path(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def latest_plan() -> Path | None:
    matches = sorted(MODEL_EXPERIMENTS_DIR.glob("model_exp_plan_????-??-??.json"))
    return matches[-1] if matches else None


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_report(plan_path: Path) -> dict[str, Any]:
    payload = load_json(plan_path)
    checks: list[dict[str, Any]] = []
    experiments = payload.get("experiments", [])
    experiment_ids = {item.get("experiment_id") for item in experiments}
    candidate_ids = {
        candidate
        for item in experiments
        for candidate in item.get("candidate_ids", [])
    }
    contract = payload.get("contract", {})

    checks.extend(
        [
            {"name": "schema", "ok": payload.get("schema_version") == "model-experiment-plan.v1", "value": payload.get("schema_version")},
            {"name": "status", "ok": payload.get("status") == "READY_FOR_MODEL_EXPERIMENTS", "value": payload.get("status")},
            {"name": "required_experiments", "ok": REQUIRED_EXPERIMENTS <= experiment_ids, "value": sorted(experiment_ids)},
            {"name": "forbidden_candidates_absent", "ok": not (candidate_ids & FORBIDDEN_CANDIDATES), "value": sorted(candidate_ids & FORBIDDEN_CANDIDATES)},
            {
                "name": "production_promotion_blocked",
                "ok": contract.get("production_promotion_allowed") is False,
                "value": contract.get("production_promotion_allowed"),
            },
            {
                "name": "has_promotion_path",
                "ok": len(payload.get("promotion_path", [])) >= 3,
                "value": payload.get("promotion_path", []),
            },
        ]
    )
    for flag in CONTRACT_TRUE_FLAGS:
        checks.append({"name": f"contract.{flag}", "ok": contract.get(flag) is True, "value": contract.get(flag)})

    for item in experiments:
        exp_id = item.get("experiment_id")
        gates = item.get("required_gates", [])
        kill_conditions = item.get("kill_conditions", [])
        checks.extend(
            [
                {"name": f"{exp_id}.has_required_gates", "ok": bool(gates), "value": len(gates)},
                {"name": f"{exp_id}.has_kill_conditions", "ok": bool(kill_conditions), "value": len(kill_conditions)},
                {"name": f"{exp_id}.has_ledger_id", "ok": bool(item.get("ledger_id")), "value": item.get("ledger_id")},
                {
                    "name": f"{exp_id}.ledger_contract_safe",
                    "ok": item.get("ledger", {}).get("production_promotion_allowed") is False,
                    "value": item.get("ledger", {}),
                },
                {
                    "name": f"{exp_id}.no_direct_production_score",
                    "ok": "risk_adjusted_score" not in json.dumps(item.get("feature_policy", {}), ensure_ascii=False),
                    "value": item.get("feature_policy", {}),
                },
            ]
        )
    failed = [item for item in checks if not item["ok"]]
    return {
        "schema_version": "model-experiment-plan-verification.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK" if not failed else "FAILED",
        "input": repo_path(plan_path),
        "summary": {
            "check_count": len(checks),
            "failed_count": len(failed),
            "experiment_count": len(experiments),
            "experiments": sorted(experiment_ids),
        },
        "checks": checks,
    }


def main() -> int:
    args = parse_args()
    plan_path = resolve_path(args.artifact) or latest_plan()
    if plan_path is None:
        raise FileNotFoundError("找不到 artifacts/model_experiments/model_exp_plan_YYYY-MM-DD.json")
    report = build_report(plan_path)
    output = resolve_path(args.output)
    if output is None:
        raise RuntimeError("output path resolution failed")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"status": report["status"], "output": repo_path(output), **report["summary"]}, ensure_ascii=False))
    return 0 if report["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
