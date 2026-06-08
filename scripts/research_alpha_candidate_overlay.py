#!/usr/bin/env python3
"""研究 shadow alpha 作為 post-model rerank overlay 的效果。

只訓練記憶體內 baseline 模型，然後在驗證窗用 alpha rank 做 shadow rerank；不保存模型、不改排名。
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
import sys
from typing import Any

import lightgbm as lgb
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.research_alpha_candidate_offline_ablation import (  # noqa: E402
    delta,
    fold_windows,
    labeled_frame,
    model_params,
    repo_path,
    resolve_path,
    safe_auc,
    safe_logloss,
    topn_proxy,
    train_dates_for_fold,
)


OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "model_experiments"
SCHEMA_VERSION = "alpha-candidate-overlay.v1"
BLEND_WEIGHTS = (0.1, 0.2, 0.3)
DECISION_PROMOTE = "PROMOTE_TO_REPLAY_CANDIDATE"
DECISION_MONITOR = "MONITOR_ONLY"
DECISION_REJECTED = "REJECTED"
MIN_TOPN_DELTA = 0.0
MIN_POSITIVE_FOLDS = 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="research alpha candidate post-model overlay")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--data-dir", default="data/clean")
    parser.add_argument("--alpha-artifact", default=None)
    parser.add_argument("--signal-check", default=None)
    parser.add_argument("--horizon", type=int, default=10)
    parser.add_argument("--threshold", type=float, default=0.05)
    parser.add_argument("--folds", type=int, default=3)
    parser.add_argument("--embargo-trade-days", type=int, default=10)
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--num-boost-round", type=int, default=30)
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def rank_pct_by_date(frame: pd.DataFrame, column: str) -> pd.Series:
    return frame.groupby("trade_date")[column].rank(method="average", pct=True)


def with_alpha_score(frame: pd.DataFrame, alpha_features: list[str]) -> pd.DataFrame:
    result = frame.copy()
    ranked = pd.DataFrame(
        {
            feature: rank_pct_by_date(result, feature)
            for feature in alpha_features
        },
        index=result.index,
    )
    result["alpha_rank_score"] = ranked.mean(axis=1)
    return result


def evaluate_score_variant(frame: pd.DataFrame, score_col: str, top_n: int) -> dict[str, Any]:
    scored = frame.copy()
    scored["pred_prob"] = scored[score_col]
    return {
        "auc": safe_auc(scored["target"].astype(int), scored["pred_prob"]),
        "logloss": safe_logloss(scored["target"].astype(int), scored["pred_prob"]),
        "topn_proxy": topn_proxy(scored, top_n=top_n),
    }


def run_overlay(
    frame: pd.DataFrame,
    baseline_features: list[str],
    alpha_features: list[str],
    windows: list[dict[str, Any]],
    embargo: int,
    num_boost_round: int,
    top_n: int,
) -> dict[str, Any]:
    all_dates = sorted(frame["trade_date"].drop_duplicates().tolist())
    fold_rows: list[dict[str, Any]] = []
    predictions: list[pd.DataFrame] = []
    for window in windows:
        validation_dates = window["validation_dates"]
        train_dates = train_dates_for_fold(all_dates, validation_dates, embargo=embargo)
        train = frame[frame["trade_date"].isin(train_dates)].copy()
        valid = frame[frame["trade_date"].isin(validation_dates)].copy()
        if train.empty or valid.empty or train["target"].nunique() < 2 or valid["target"].nunique() < 2:
            fold_rows.append({"fold": window["fold"], "status": "SKIPPED", "reason": "insufficient classes or rows"})
            continue
        model = lgb.train(
            model_params(),
            lgb.Dataset(train[baseline_features], label=train["target"], feature_name=baseline_features),
            num_boost_round=num_boost_round,
        )
        valid = with_alpha_score(valid.copy(), alpha_features)
        valid["baseline_score"] = model.predict(valid[baseline_features])
        valid["baseline_rank_score"] = rank_pct_by_date(valid, "baseline_score")
        valid["alpha_only_score"] = valid["alpha_rank_score"]
        for weight in BLEND_WEIGHTS:
            valid[f"blend_{weight:.2f}_score"] = (
                (1 - weight) * valid["baseline_rank_score"] + weight * valid["alpha_rank_score"]
            )
        variant_metrics = {
            "baseline": evaluate_score_variant(valid, "baseline_score", top_n=top_n),
            "alpha_only_diagnostic": evaluate_score_variant(valid, "alpha_only_score", top_n=top_n),
        }
        for weight in BLEND_WEIGHTS:
            variant_metrics[f"blend_{weight:.2f}"] = evaluate_score_variant(valid, f"blend_{weight:.2f}_score", top_n=top_n)
        fold_rows.append(
            {
                "fold": window["fold"],
                "status": "OK",
                "train_rows": int(len(train)),
                "validation_rows": int(len(valid)),
                "train_start": str(pd.to_datetime(min(train_dates)).date()),
                "train_end": str(pd.to_datetime(max(train_dates)).date()),
                "validation_start": str(pd.to_datetime(min(validation_dates)).date()),
                "validation_end": str(pd.to_datetime(max(validation_dates)).date()),
                "variants": variant_metrics,
            }
        )
        keep_cols = ["trade_date_text", "stock_id", "target", "future_return", "baseline_score", "alpha_only_score"]
        keep_cols.extend(f"blend_{weight:.2f}_score" for weight in BLEND_WEIGHTS)
        predictions.append(valid[keep_cols])
    prediction_frame = pd.concat(predictions, ignore_index=True) if predictions else pd.DataFrame()
    variants = aggregate_variants(prediction_frame, fold_rows, top_n=top_n)
    return {"status": "OK" if predictions else "SKIPPED", "folds": fold_rows, "variants": variants}


def aggregate_variants(predictions: pd.DataFrame, folds: list[dict[str, Any]], top_n: int) -> dict[str, Any]:
    if predictions.empty:
        return {}
    score_columns = {
        "baseline": "baseline_score",
        "alpha_only_diagnostic": "alpha_only_score",
        **{f"blend_{weight:.2f}": f"blend_{weight:.2f}_score" for weight in BLEND_WEIGHTS},
    }
    result: dict[str, Any] = {}
    for name, score_col in score_columns.items():
        scored = predictions.copy()
        scored["pred_prob"] = scored[score_col]
        auc_values = []
        logloss_values = []
        for row in folds:
            variant = (row.get("variants") or {}).get(name) or {}
            if variant.get("auc") is not None:
                auc_values.append(variant["auc"])
            if variant.get("logloss") is not None:
                logloss_values.append(variant["logloss"])
        result[name] = {
            "fold_count": sum(1 for row in folds if row.get("status") == "OK"),
            "avg_auc": round(float(pd.Series(auc_values).mean()), 6) if auc_values else None,
            "avg_logloss": round(float(pd.Series(logloss_values).mean()), 6) if logloss_values else None,
            "topn_proxy": topn_proxy(scored, top_n=top_n),
        }
    return result


def fold_topn_delta(fold: dict[str, Any], variant: str) -> float | None:
    variants = fold.get("variants") or {}
    base = ((variants.get("baseline") or {}).get("topn_proxy") or {}).get("avg_topn_future_return")
    candidate = ((variants.get(variant) or {}).get("topn_proxy") or {}).get("avg_topn_future_return")
    return delta(candidate, base)


def decision_for(overlay: dict[str, Any]) -> dict[str, Any]:
    variants = overlay.get("variants", {})
    baseline = variants.get("baseline", {})
    blend_names = [f"blend_{weight:.2f}" for weight in BLEND_WEIGHTS]
    ranked: list[dict[str, Any]] = []
    for name in blend_names:
        item = variants.get(name, {})
        topn_delta = delta(
            (item.get("topn_proxy") or {}).get("avg_topn_future_return"),
            (baseline.get("topn_proxy") or {}).get("avg_topn_future_return"),
        )
        positive_folds = sum(
            1
            for fold in overlay.get("folds", [])
            if fold.get("status") == "OK" and (fold_topn_delta(fold, name) or 0) > MIN_TOPN_DELTA
        )
        ranked.append({"variant": name, "topn_delta": topn_delta, "positive_folds": positive_folds})
    ranked = sorted(ranked, key=lambda row: (row["topn_delta"] if row["topn_delta"] is not None else -999, row["positive_folds"]), reverse=True)
    best = ranked[0] if ranked else {"variant": None, "topn_delta": None, "positive_folds": 0}
    failed = []
    if best["topn_delta"] is None or best["topn_delta"] <= MIN_TOPN_DELTA:
        failed.append("topn_delta<=0")
    if int(best["positive_folds"] or 0) < MIN_POSITIVE_FOLDS:
        failed.append(f"positive_folds<{MIN_POSITIVE_FOLDS}")
    if failed:
        return {
            "decision": DECISION_REJECTED,
            "decision_rationale": "alpha overlay 未通過：" + ", ".join(failed),
            "best_variant": best,
            "ranked_variants": ranked,
        }
    return {
        "decision": DECISION_PROMOTE,
        "decision_rationale": "alpha overlay 在 TopN proxy 與 fold 一致性上優於 baseline；可進下一輪 shadow replay。",
        "best_variant": best,
        "ranked_variants": ranked,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    frame, baseline_features, alpha_features, alpha_path, signal_path = labeled_frame(args)
    windows = fold_windows(frame["trade_date"].drop_duplicates().tolist(), folds=args.folds)
    overlay = run_overlay(
        frame=frame,
        baseline_features=baseline_features,
        alpha_features=alpha_features,
        windows=windows,
        embargo=args.embargo_trade_days,
        num_boost_round=args.num_boost_round,
        top_n=args.top_n,
    )
    decision = decision_for(overlay)
    variants = overlay.get("variants", {})
    baseline = variants.get("baseline", {})
    best_variant = decision["best_variant"].get("variant")
    best = variants.get(best_variant, {}) if best_variant else {}
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK",
        "research_question": "shadow alpha 是否適合作為 post-model rerank overlay？",
        "layer": "ranking",
        "pre_registered": True,
        "decision": decision["decision"],
        "decision_rationale": decision["decision_rationale"],
        "decision_policy": {
            "min_topn_delta": MIN_TOPN_DELTA,
            "min_positive_folds": MIN_POSITIVE_FOLDS,
            "production_promotion_allowed": False,
        },
        "decision_diagnostics": {
            "best_variant": decision["best_variant"],
            "ranked_variants": decision["ranked_variants"],
        },
        "diagnostics_not_for_promotion": ["alpha_only_diagnostic"],
        "contract": {
            "research_only": True,
            "in_memory_models_only": True,
            "post_model_overlay_only": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_write_production_features": True,
            "does_not_change_risk_adjusted_score": True,
            "does_not_change_production_ranking": True,
            "production_promotion_allowed": False,
            "split_policy": "chronological validation tail with embargo",
            "no_hindsight_policy": {
                "validation_windows_are_chronological": True,
                "train_dates_end_before_validation_start": True,
                "embargo_trade_days": args.embargo_trade_days,
                "promotion_gate_variant": "best_pre_registered_blend_vs_baseline",
                "diagnostic_only_variants": ["alpha_only_diagnostic"],
                "diagnostic_failures_cannot_define_same_run_filters": True,
                "new_filters_require_next_walkforward_run": True,
            },
        },
        "inputs": {
            "data_dir": repo_path(resolve_path(args.data_dir)),
            "alpha_artifact": repo_path(alpha_path),
            "signal_check": repo_path(signal_path),
            "horizon": args.horizon,
            "threshold": args.threshold,
            "folds": args.folds,
            "embargo_trade_days": args.embargo_trade_days,
            "top_n": args.top_n,
            "num_boost_round": args.num_boost_round,
            "blend_weights": list(BLEND_WEIGHTS),
        },
        "summary": {
            "rows": int(len(frame)),
            "stocks": int(frame["stock_id"].nunique()),
            "dates": int(frame["trade_date"].nunique()),
            "baseline_feature_count": len(baseline_features),
            "alpha_features": alpha_features,
            "alpha_feature_count": len(alpha_features),
            "best_variant": best_variant,
            "baseline_topn_return": (baseline.get("topn_proxy") or {}).get("avg_topn_future_return"),
            "best_topn_return": (best.get("topn_proxy") or {}).get("avg_topn_future_return"),
            "best_topn_delta": decision["best_variant"].get("topn_delta"),
            "best_positive_folds": decision["best_variant"].get("positive_folds"),
        },
        "overlay": overlay,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Alpha Candidate Overlay Research",
        "",
        f"- decision：`{payload['decision']}`",
        f"- decision_rationale：{payload['decision_rationale']}",
        f"- alpha_features：`{summary['alpha_features']}`",
        f"- best_variant：`{summary['best_variant']}`",
        f"- best_topn_delta：`{summary['best_topn_delta']}`",
        f"- production_promotion_allowed：`{payload['contract']['production_promotion_allowed']}`",
        "",
        "| Variant | Folds | AUC | TopN Return | Universe Return | Uplift |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, item in payload["overlay"].get("variants", {}).items():
        topn = item.get("topn_proxy", {})
        lines.append(
            f"| {name} | {item.get('fold_count')} | {item.get('avg_auc')} | "
            f"{topn.get('avg_topn_future_return')} | {topn.get('avg_universe_future_return')} | "
            f"{topn.get('topn_minus_universe_return')} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = resolve_path(args.output) or OUTPUT_DIR / f"alpha_candidate_overlay_{args.date}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output), **payload["summary"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
