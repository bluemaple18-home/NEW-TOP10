#!/usr/bin/env python3
"""由 SHADOW-01 產物產生 MODEL-EXP-01 離線實驗計畫。

此腳本只整理候選特徵實驗矩陣，不訓練模型、不改 production ranking。
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
OUTPUT_DIR = ARTIFACTS_DIR / "model_experiments"
SCHEMA_VERSION = "model-experiment-plan.v1"
SUPPORTED_CANDIDATES = {
    "candidate_persistence",
    "portfolio_risk_overlay",
    "regime_feature_group_ablation",
}
FORBIDDEN_CANDIDATES = {
    "market_context",
    "fundamentals",
    "chip_flow",
    "industry_rotation",
    "weekend_research_matrix",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build MODEL-EXP-01 plan from SHADOW-01 artifacts")
    parser.add_argument("--shadow-index", default=None)
    parser.add_argument("--date", default=date.today().isoformat())
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


def latest_shadow_index() -> Path | None:
    matches = sorted(ARTIFACTS_DIR.glob("shadow_feature_experiment_????-??-??.json"))
    return matches[-1] if matches else None


def load_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {"_missing": True, "_path": repo_path(path)}
    return json.loads(path.read_text(encoding="utf-8"))


def safe_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def shadow_artifact_rows(index: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in index.get("candidates", []):
        path = resolve_path(row.get("artifact"))
        payload = load_json(path)
        rows.append(
            {
                "candidate_id": row.get("candidate_id"),
                "status": row.get("status"),
                "decision": row.get("decision"),
                "artifact": repo_path(path),
                "payload": payload,
            }
        )
    return rows


def candidate_persistence_plan(row: dict[str, Any]) -> dict[str, Any]:
    payload = row["payload"]
    metrics = payload.get("metrics", {})
    buckets = metrics.get("top_positive_buckets", {})
    return {
        "experiment_id": "model_exp_candidate_persistence_only",
        "candidate_ids": ["candidate_persistence"],
        "experiment_type": "offline_feature_ablation",
        "priority": 1,
        "status": "READY_FOR_OFFLINE_EXPERIMENT",
        "feature_policy": {
            "additive_columns": [
                "consecutive_ranked_days",
                "streak_bucket",
                "rank_delta_direction",
            ],
            "as_of_policy": "derive only from prior ranking artifacts available at D close; never use future ranking presence",
            "missing_policy": "new_or_unknown explicit category; missing must not imply bullish signal",
            "production_score_policy": "do not add direct ranking bonus",
        },
        "evidence": {
            "artifact": row["artifact"],
            "trade_count": metrics.get("trade_count"),
            "positive_bucket_count": metrics.get("positive_bucket_count"),
            "top_positive_buckets": buckets,
        },
        "required_gates": common_required_gates(),
        "kill_conditions": [
            "sealed OOS AUC/top10 uplift fails versus baseline",
            "5D or 10D replay worsens max drawdown versus baseline",
            "positive effect exists only in tiny buckets with no walk-forward repeatability",
            "as-of join requires current or future ranking date",
        ],
    }


def portfolio_risk_plan(row: dict[str, Any]) -> dict[str, Any]:
    payload = row["payload"]
    metrics = payload.get("metrics", {})
    best = metrics.get("best_scenarios", [])
    return {
        "experiment_id": "model_exp_portfolio_risk_overlay_only",
        "candidate_ids": ["portfolio_risk_overlay"],
        "experiment_type": "post_ranking_overlay_ablation",
        "priority": 2,
        "status": "READY_FOR_OFFLINE_EXPERIMENT",
        "feature_policy": {
            "model_feature_allowed": False,
            "overlay_allowed": True,
            "scope": "evaluate risk gates after ranking; do not suppress production rows before promotion",
            "candidate_controls": [
                "max_group_exposure",
                "event_exit_overlay",
                "drawdown_guard",
            ],
        },
        "evidence": {
            "artifact": row["artifact"],
            "scenario_count": metrics.get("scenario_count"),
            "positive_return_count": metrics.get("positive_return_count"),
            "best_scenarios": best,
        },
        "required_gates": common_required_gates()
        + [
            "portfolio concentration gate: group exposure must not increase",
            "risk overlay must be evaluated separately from LightGBM feature ablation",
        ],
        "kill_conditions": [
            "return improves only by reducing trades to an impractical sample size",
            "max group exposure or concentration increases versus baseline",
            "overlay changes Top10 selection without a matching replay improvement",
        ],
    }


def regime_feature_group_plan(row: dict[str, Any]) -> dict[str, Any]:
    payload = row["payload"]
    metrics = payload.get("metrics", {})
    top = metrics.get("top_shadow_features", [])
    selected_groups = sorted({item.get("group") for item in top if item.get("group")})
    selected_regimes = sorted({item.get("regime_label") for item in top if item.get("regime_label")})
    return {
        "experiment_id": "model_exp_regime_feature_group_ablation",
        "candidate_ids": ["regime_feature_group_ablation"],
        "experiment_type": "offline_feature_group_ablation",
        "priority": 3,
        "status": "READY_FOR_OFFLINE_EXPERIMENT",
        "feature_policy": {
            "candidate_groups": selected_groups,
            "candidate_regimes": selected_regimes,
            "top_shadow_features": [item.get("feature") for item in top[:12]],
            "as_of_policy": "use only columns already present in features frame or pre-validated as-of joins",
            "weight_policy": "do not convert IC directly into RankingPolicy weights",
        },
        "evidence": {
            "artifact": row["artifact"],
            "feature_count": metrics.get("feature_count"),
            "metric_rows": metrics.get("metric_rows"),
            "candidate_metric_rows": metrics.get("candidate_metric_rows"),
            "top_shadow_features": top,
        },
        "required_gates": common_required_gates()
        + [
            "regime split report: each market regime must be reported separately",
            "feature group ablation must include baseline/current feature set comparison",
        ],
        "kill_conditions": [
            "uplift appears only in one short regime window",
            "feature group increases weak-market drawdown",
            "candidate group depends on blocked fundamental/chip data coverage",
        ],
    }


def combined_plan(enabled: set[str]) -> dict[str, Any]:
    prerequisites = [
        "model_exp_candidate_persistence_only",
        "model_exp_regime_feature_group_ablation",
    ]
    status = "WAIT_FOR_INDIVIDUAL_PASS"
    candidate_ids = ["candidate_persistence", "regime_feature_group_ablation"]
    if not set(candidate_ids) <= enabled:
        status = "BLOCKED_BY_MISSING_INDIVIDUAL"
    return {
        "experiment_id": "model_exp_combined_conservative",
        "candidate_ids": candidate_ids,
        "experiment_type": "offline_combined_ablation",
        "priority": 4,
        "status": status,
        "prerequisites": prerequisites,
        "feature_policy": {
            "combine_only_after_individual_pass": True,
            "exclude_by_default": ["portfolio_risk_overlay"],
            "reason": "portfolio_risk_overlay is a post-ranking overlay track, not a first-pass LightGBM feature.",
        },
        "required_gates": common_required_gates()
        + [
            "combined experiment must beat each individual candidate on replay risk-adjusted metrics",
        ],
        "kill_conditions": [
            "combined feature set improves AUC but worsens Top10 replay",
            "combined feature set overfits one regime and degrades others",
        ],
    }


def common_required_gates() -> list[str]:
    return [
        "no formal retrain and no overwrite of models/latest_lgbm.pkl during MODEL-EXP-01",
        "sealed OOS split with embargo before any model promotion",
        "Top10 replay by 1D/3D/5D/10D versus current baseline",
        "market regime breakdown with at least EARLY_REVERSAL/MIXED_NEUTRAL/NARROW_LEADER/PANIC_SELLING/RISK_OFF",
        "industry concentration and max drawdown non-degradation",
        "manual review before production promotion",
    ]


def build_experiments(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enabled = {
        str(row["candidate_id"])
        for row in rows
        if row.get("status") == "OK" and row.get("decision") == "MODEL_EXP_CANDIDATE"
    }
    experiments = []
    by_id = {str(row["candidate_id"]): row for row in rows}
    if "candidate_persistence" in enabled:
        experiments.append(candidate_persistence_plan(by_id["candidate_persistence"]))
    if "portfolio_risk_overlay" in enabled:
        experiments.append(portfolio_risk_plan(by_id["portfolio_risk_overlay"]))
    if "regime_feature_group_ablation" in enabled:
        experiments.append(regime_feature_group_plan(by_id["regime_feature_group_ablation"]))
    experiments.append(combined_plan(enabled))
    return experiments


def build_plan(args: argparse.Namespace) -> dict[str, Any]:
    shadow_index_path = resolve_path(args.shadow_index) or latest_shadow_index()
    shadow_index = load_json(shadow_index_path)
    rows = shadow_artifact_rows(shadow_index)
    candidate_ids = {str(row.get("candidate_id")) for row in rows}
    forbidden_present = sorted(candidate_ids & FORBIDDEN_CANDIDATES)
    unsupported_present = sorted(candidate_ids - SUPPORTED_CANDIDATES)
    experiments = build_experiments(rows)
    ready = [item["experiment_id"] for item in experiments if item.get("status") == "READY_FOR_OFFLINE_EXPERIMENT"]
    blocked = [
        item["experiment_id"]
        for item in experiments
        if item.get("status") not in {"READY_FOR_OFFLINE_EXPERIMENT", "WAIT_FOR_INDIVIDUAL_PASS"}
    ]
    status = "READY_FOR_MODEL_EXPERIMENTS" if ready and not forbidden_present else "BLOCKED"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": status,
        "contract": {
            "plan_only": True,
            "shadow_inputs_only": True,
            "does_not_train_model": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_risk_adjusted_score": True,
            "does_not_change_production_ranking": True,
            "production_promotion_allowed": False,
        },
        "inputs": {
            "shadow_feature_experiment_index": repo_path(shadow_index_path),
            "shadow_candidates": sorted(candidate_ids),
        },
        "summary": {
            "experiment_count": len(experiments),
            "ready_experiments": ready,
            "blocked_experiments": blocked,
            "wait_for_individual_pass": [
                item["experiment_id"]
                for item in experiments
                if item.get("status") == "WAIT_FOR_INDIVIDUAL_PASS"
            ],
            "forbidden_candidates_present": forbidden_present,
            "unsupported_candidates_present": unsupported_present,
            "next_stage": "MODEL-EXP-01 offline runs; no production model replacement",
        },
        "experiments": experiments,
        "promotion_path": [
            "MODEL-EXP-01 offline candidate ablation",
            "MODEL-EXP-02 sealed OOS + replay + regime breakdown",
            "MODEL-PROMOTE-01 manual review and rollback-ready model replacement",
        ],
    }


def pct(value: Any) -> str:
    parsed = safe_float(value)
    if parsed is None:
        return "--"
    return f"{parsed:.2%}"


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# MODEL-EXP-01 Plan",
        "",
        f"- status：`{payload['status']}`",
        f"- date：`{payload['date']}`",
        f"- production_promotion_allowed：`{payload['contract']['production_promotion_allowed']}`",
        "",
        "## Experiment Matrix",
        "",
        "| Experiment | Type | Status | Candidates |",
        "|---|---|---|---|",
    ]
    for item in payload["experiments"]:
        lines.append(
            "| {experiment} | {etype} | {status} | {candidates} |".format(
                experiment=item["experiment_id"],
                etype=item["experiment_type"],
                status=item["status"],
                candidates=", ".join(item.get("candidate_ids", [])),
            )
        )
    lines.extend(["", "## Gates", ""])
    for gate in common_required_gates():
        lines.append(f"- {gate}")
    lines.extend(["", "## Promotion Path", ""])
    for step in payload["promotion_path"]:
        lines.append(f"- {step}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_plan(args)
    output = resolve_path(args.output) or OUTPUT_DIR / f"model_exp_plan_{args.date}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "output": repo_path(output),
                **payload["summary"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if payload["status"] in {"READY_FOR_MODEL_EXPERIMENTS", "BLOCKED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
