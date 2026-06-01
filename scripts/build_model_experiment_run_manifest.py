#!/usr/bin/env python3
"""建立 MODEL-EXP-01 執行前 run manifest。

此腳本只檢查離線實驗是否具備執行條件，並產生 run manifest。
它不訓練模型、不建立候選模型檔、不改 production ranking。
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
MODEL_EXPERIMENTS_DIR = ARTIFACTS_DIR / "model_experiments"
SCHEMA_VERSION = "model-experiment-run-manifest.v1"
KNOWN_STATUSES = {
    "READY_FOR_OVERLAY_REPLAY",
    "READY_FOR_FEATURE_ABLATION",
    "BLOCKED_MISSING_MATERIALIZER",
    "WAIT_FOR_INDIVIDUAL_PASS",
    "BLOCKED_BY_PLAN_STATUS",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build MODEL-EXP-01 execution readiness manifest")
    parser.add_argument("--plan", default=None)
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument("--output", default=None)
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


def load_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {"_missing": True, "_path": repo_path(path)}
    return json.loads(path.read_text(encoding="utf-8"))


def feature_columns(path: Path | None) -> set[str]:
    if path is None or not path.exists():
        return set()
    # 欄位數小，讀 metadata 失敗時再回退到 pandas 完整欄位讀取。
    try:
        import pyarrow.parquet as pq

        return set(pq.ParquetFile(path).schema.names)
    except Exception:
        import pandas as pd

        return set(pd.read_parquet(path).columns)


def artifact_exists(path_text: str | None) -> bool:
    path = resolve_path(path_text)
    return bool(path and path.exists())


def candidate_materializer_paths(run_date: str) -> tuple[Path, Path]:
    artifact = MODEL_EXPERIMENTS_DIR / f"candidate_persistence_features_{run_date}.parquet"
    verification = MODEL_EXPERIMENTS_DIR / "candidate_persistence_features_verification_latest.json"
    return artifact, verification


def candidate_materializer_ready(run_date: str) -> tuple[bool, dict[str, Any]]:
    artifact, verification = candidate_materializer_paths(run_date)
    details: dict[str, Any] = {
        "artifact": repo_path(artifact),
        "verification": repo_path(verification),
        "artifact_exists": artifact.exists(),
        "verification_exists": verification.exists(),
    }
    if not artifact.exists() or not verification.exists():
        return False, details
    payload = load_json(verification)
    details["verification_status"] = payload.get("status")
    details["verification_input"] = payload.get("input")
    ready = payload.get("status") == "OK" and payload.get("input") == repo_path(artifact)
    return ready, details


def candidate_persistence_run(experiment: dict[str, Any], run_date: str) -> dict[str, Any]:
    columns = experiment.get("feature_policy", {}).get("additive_columns", [])
    ready, details = candidate_materializer_ready(run_date)
    if ready:
        return {
            "experiment_id": experiment.get("experiment_id"),
            "candidate_ids": experiment.get("candidate_ids", []),
            "execution_status": "READY_FOR_FEATURE_ABLATION",
            "reason": "candidate_persistence materializer 已通過 as-of 驗證；可進離線 feature ablation，但仍不可正式 retrain。",
            "required_before_execute": [
                "只讀 materialized artifact，不覆蓋 data/clean/features.parquet",
                "離線 ablation 必須保留 baseline 對照與 replay breakdown",
                "不得把結果直接轉成 production ranking bonus",
            ],
            "planned_columns": columns,
            "materialized_features": details,
            "safe_commands": [
                "uv run --with-requirements requirements.txt python scripts/build_candidate_persistence_materialized_features.py --date YYYY-MM-DD",
                "uv run --with-requirements requirements.txt python scripts/verify_candidate_persistence_materialized_features.py --artifact artifacts/model_experiments/candidate_persistence_features_YYYY-MM-DD.parquet",
            ],
        }
    return {
        "experiment_id": experiment.get("experiment_id"),
        "candidate_ids": experiment.get("candidate_ids", []),
        "execution_status": "BLOCKED_MISSING_MATERIALIZER",
        "reason": "candidate_persistence 欄位尚未有安全 training-frame materializer；不能直接把 daily artifact 混進訓練。",
        "required_before_execute": [
            "新增 as-of materializer：只使用 D 收盤前已存在的 prior ranking artifacts",
            "materializer verification：禁止 future ranking presence / future rank_delta leakage",
            "輸出 materialized feature frame 到 artifacts/model_experiments/，不得覆蓋 data/clean/features.parquet",
        ],
        "planned_columns": columns,
        "materialized_features": details,
        "safe_commands": [],
    }


def portfolio_risk_run(experiment: dict[str, Any]) -> dict[str, Any]:
    policy = experiment.get("feature_policy", {})
    status = "READY_FOR_OVERLAY_REPLAY" if policy.get("overlay_allowed") and not policy.get("model_feature_allowed") else "BLOCKED_BY_PLAN_STATUS"
    return {
        "experiment_id": experiment.get("experiment_id"),
        "candidate_ids": experiment.get("candidate_ids", []),
        "execution_status": status,
        "reason": "portfolio_risk_overlay 是 post-ranking overlay track；可跑 replay/strategy matrix，但不可進 first-pass LightGBM feature。",
        "required_before_execute": [
            "只使用 ranking/replay artifacts",
            "輸出 overlay replay artifact 到 artifacts/model_experiments/ 或 artifacts/backtest/",
            "不得 suppress production ranking rows",
        ],
        "planned_controls": policy.get("candidate_controls", []),
        "safe_commands": [
            "uv run --with-requirements requirements.txt python scripts/run_research_shadow_runs.py --skip-ranking --skip-replay"
        ],
    }


def regime_feature_run(experiment: dict[str, Any], available_features: set[str]) -> dict[str, Any]:
    raw_features = experiment.get("feature_policy", {}).get("top_shadow_features", [])
    planned = sorted({str(feature) for feature in raw_features if feature})
    missing = [feature for feature in planned if feature not in available_features]
    status = "READY_FOR_FEATURE_ABLATION" if planned and not missing else "BLOCKED_BY_PLAN_STATUS"
    return {
        "experiment_id": experiment.get("experiment_id"),
        "candidate_ids": experiment.get("candidate_ids", []),
        "execution_status": status,
        "reason": "candidate feature columns are present in feature frame" if status == "READY_FOR_FEATURE_ABLATION" else "planned features missing from feature frame",
        "required_before_execute": [
            "離線 ablation 模型只能寫 artifacts/model_experiments/",
            "必須保留 baseline/current feature set 對照",
            "必須輸出 regime breakdown 與 Top10 replay",
        ],
        "planned_features": planned,
        "missing_features": missing,
        "safe_commands": [
            "uv run --with-requirements requirements.txt python scripts/build_model_experiment_plan.py --date YYYY-MM-DD"
        ],
    }


def combined_run(experiment: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": experiment.get("experiment_id"),
        "candidate_ids": experiment.get("candidate_ids", []),
        "execution_status": "WAIT_FOR_INDIVIDUAL_PASS",
        "reason": "combined experiment must wait until individual experiments pass replay/sealed gates",
        "required_before_execute": experiment.get("prerequisites", []),
        "safe_commands": [],
    }


def build_run_item(experiment: dict[str, Any], available_features: set[str], run_date: str) -> dict[str, Any]:
    exp_id = str(experiment.get("experiment_id"))
    if experiment.get("status") == "WAIT_FOR_INDIVIDUAL_PASS":
        return combined_run(experiment)
    if experiment.get("status") != "READY_FOR_OFFLINE_EXPERIMENT":
        return {
            "experiment_id": exp_id,
            "candidate_ids": experiment.get("candidate_ids", []),
            "execution_status": "BLOCKED_BY_PLAN_STATUS",
            "reason": f"plan status is {experiment.get('status')}",
            "required_before_execute": [],
            "safe_commands": [],
        }
    if exp_id == "model_exp_candidate_persistence_only":
        return candidate_persistence_run(experiment, run_date=run_date)
    if exp_id == "model_exp_portfolio_risk_overlay_only":
        return portfolio_risk_run(experiment)
    if exp_id == "model_exp_regime_feature_group_ablation":
        return regime_feature_run(experiment, available_features)
    if exp_id == "model_exp_combined_conservative":
        return combined_run(experiment)
    return {
        "experiment_id": exp_id,
        "candidate_ids": experiment.get("candidate_ids", []),
        "execution_status": "BLOCKED_BY_PLAN_STATUS",
        "reason": "unknown experiment id",
        "required_before_execute": [],
        "safe_commands": [],
    }


def attach_ledger_fields(run: dict[str, Any], experiment: dict[str, Any]) -> dict[str, Any]:
    ledger = experiment.get("ledger", {})
    if ledger:
        run["ledger_id"] = experiment.get("ledger_id") or ledger.get("id")
        run["ledger"] = ledger
    return run


def build_manifest(args: argparse.Namespace) -> dict[str, Any]:
    plan_path = resolve_path(args.plan) or latest_plan()
    plan = load_json(plan_path)
    features_path = resolve_path(args.features)
    available_features = feature_columns(features_path)
    runs = [
        attach_ledger_fields(build_run_item(experiment, available_features, args.date), experiment)
        for experiment in plan.get("experiments", [])
    ]
    ready = [
        run["experiment_id"]
        for run in runs
        if run.get("execution_status") in {"READY_FOR_OVERLAY_REPLAY", "READY_FOR_FEATURE_ABLATION"}
    ]
    blocked = [
        run["experiment_id"]
        for run in runs
        if str(run.get("execution_status", "")).startswith("BLOCKED")
    ]
    waiting = [
        run["experiment_id"]
        for run in runs
        if run.get("execution_status") == "WAIT_FOR_INDIVIDUAL_PASS"
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "READY_WITH_BLOCKERS" if ready and blocked else ("READY" if ready else "BLOCKED"),
        "contract": {
            "manifest_only": True,
            "does_not_train_model": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_risk_adjusted_score": True,
            "does_not_change_production_ranking": True,
            "production_promotion_allowed": False,
        },
        "inputs": {
            "model_experiment_plan": repo_path(plan_path),
            "features": repo_path(features_path),
            "feature_column_count": len(available_features),
        },
        "summary": {
            "run_count": len(runs),
            "ready_to_execute": ready,
            "blocked": blocked,
            "waiting": waiting,
            "next_missing_piece": "candidate_persistence materializer" if "model_exp_candidate_persistence_only" in blocked else None,
        },
        "runs": runs,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# MODEL-EXP-01 Run Manifest",
        "",
        f"- status：`{payload['status']}`",
        f"- date：`{payload['date']}`",
        f"- production_promotion_allowed：`{payload['contract']['production_promotion_allowed']}`",
        "",
        "| Experiment | Status | Reason |",
        "|---|---|---|",
    ]
    for run in payload["runs"]:
        lines.append(f"| {run['experiment_id']} | {run['execution_status']} | {run['reason']} |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_manifest(args)
    output = resolve_path(args.output) or MODEL_EXPERIMENTS_DIR / f"model_exp_run_manifest_{args.date}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output), **payload["summary"]}, ensure_ascii=False))
    return 0 if payload["status"] in {"READY", "READY_WITH_BLOCKERS", "BLOCKED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
