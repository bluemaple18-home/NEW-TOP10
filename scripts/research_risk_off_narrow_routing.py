#!/usr/bin/env python3
"""研究 RISK_OFF 窄盤下的 feature routing。

本腳本只訓練記憶體內模型並產生診斷 artifact，不保存模型、不覆蓋正式 ranking。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import lightgbm as lgb
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.research_regime_feature_offline_ablation import (  # noqa: E402
    evaluate_regimes,
    feature_sets,
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


SCHEMA_VERSION = "risk-off-narrow-routing.v1"
OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "model_experiments"
MODEL_HASH = "76f530f6491f996f4838500acacbde40a10c90f43116cec0dcc69fb6b4935675"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="research risk-off narrow index-led routing")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--data-dir", default="data/clean")
    parser.add_argument("--run-manifest", default=None)
    parser.add_argument("--market-regime-history", default="artifacts/market_regime_history_2026-06-01.json")
    parser.add_argument("--horizon", type=int, default=10)
    parser.add_argument("--threshold", type=float, default=0.05)
    parser.add_argument("--folds", type=int, default=8)
    parser.add_argument("--embargo-trade-days", type=int, default=10)
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--num-boost-round", type=int, default=120)
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def attach_market_context(frame: pd.DataFrame, market_path: Path) -> pd.DataFrame:
    payload = load_json(market_path)
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    market = pd.DataFrame(rows)
    if market.empty:
        raise ValueError(f"market regime history 無 rows：{market_path}")
    market["trade_date_text"] = market["trade_date"].astype(str)
    cols = [
        "trade_date_text",
        "value_weight_return",
        "breadth_ma20",
        "top_sector_value_share",
        "long_upper_shadow_ratio",
    ]
    market = market[[col for col in cols if col in market.columns]].copy()
    for col in [item for item in cols if item != "trade_date_text"]:
        if col in market.columns:
            market[col] = pd.to_numeric(market[col], errors="coerce")
    return frame.merge(market, on="trade_date_text", how="left")


def is_risk_off_narrow_index_led(frame: pd.DataFrame) -> pd.Series:
    """窄盤撐指數：RISK_OFF、廣度弱、資金集中，且指數不算崩跌。"""

    return (
        (frame["regime_label"].astype(str) == "RISK_OFF")
        & (pd.to_numeric(frame.get("breadth_ma20"), errors="coerce") <= 0.25)
        & (pd.to_numeric(frame.get("top_sector_value_share"), errors="coerce") >= 0.62)
        & (pd.to_numeric(frame.get("value_weight_return"), errors="coerce") >= -0.005)
    )


def train_model(frame: pd.DataFrame, features: list[str], num_boost_round: int) -> lgb.Booster:
    return lgb.train(
        model_params(),
        lgb.Dataset(frame[features], label=frame["target"], feature_name=features),
        num_boost_round=num_boost_round,
    )


def fold_prediction_frame(
    frame: pd.DataFrame,
    feature_map: dict[str, list[str]],
    validation_dates: list[pd.Timestamp],
    train_dates: list[pd.Timestamp],
    num_boost_round: int,
) -> pd.DataFrame | None:
    train = frame[frame["trade_date"].isin(train_dates)].copy()
    valid = frame[frame["trade_date"].isin(validation_dates)].copy()
    if train.empty or valid.empty or train["target"].nunique() < 2 or valid["target"].nunique() < 2:
        return None

    models: dict[str, lgb.Booster] = {}
    for name, features in feature_map.items():
        if not features:
            continue
        models[name] = train_model(train, features, num_boost_round)
        valid[f"pred_{name}"] = models[name].predict(valid[features])

    routed_mask = is_risk_off_narrow_index_led(valid)
    valid["pred_current_baseline"] = valid["pred_current_baseline"]
    valid["pred_planned_on_narrow_else_baseline"] = valid["pred_current_baseline"]
    valid.loc[routed_mask, "pred_planned_on_narrow_else_baseline"] = valid.loc[routed_mask, "pred_planned_features_only"]
    valid["pred_planned_on_narrow_else_drop"] = valid["pred_drop_planned_features"]
    valid.loc[routed_mask, "pred_planned_on_narrow_else_drop"] = valid.loc[routed_mask, "pred_planned_features_only"]
    valid["risk_off_narrow_index_led"] = routed_mask
    return valid


def evaluate_prediction(frame: pd.DataFrame, pred_col: str, top_n: int) -> dict[str, Any]:
    work = frame.copy()
    work["pred_prob"] = pd.to_numeric(work[pred_col], errors="coerce")
    topn = topn_proxy(work, top_n)
    return {
        "auc": safe_auc(work["target"].astype(int), work["pred_prob"]),
        "logloss": safe_logloss(work["target"].astype(int), work["pred_prob"]),
        "topn_proxy": topn,
        "regime_breakdown": evaluate_regimes(work, top_n=top_n),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    frame, all_features, planned, manifest_path = labeled_frame(args)
    frame = attach_market_context(frame, resolve_path(args.market_regime_history))
    windows = fold_windows(frame["trade_date"].drop_duplicates().tolist(), folds=args.folds)
    base_feature_sets = feature_sets(all_features, planned)
    feature_map = {
        "current_baseline": base_feature_sets["current_baseline"],
        "drop_planned_features": base_feature_sets["drop_planned_features"],
        "planned_features_only": base_feature_sets["planned_features_only"],
    }
    all_dates = sorted(frame["trade_date"].drop_duplicates().tolist())
    prediction_frames: list[pd.DataFrame] = []
    fold_rows = []
    for window in windows:
        validation_dates = window["validation_dates"]
        train_dates = train_dates_for_fold(all_dates, validation_dates, embargo=args.embargo_trade_days)
        pred = fold_prediction_frame(frame, feature_map, validation_dates, train_dates, args.num_boost_round)
        if pred is None:
            fold_rows.append({"fold": window["fold"], "status": "SKIPPED"})
            continue
        prediction_frames.append(pred)
        fold = {
            "fold": window["fold"],
            "status": "OK",
            "validation_start": str(pd.to_datetime(min(validation_dates)).date()),
            "validation_end": str(pd.to_datetime(max(validation_dates)).date()),
            "train_start": str(pd.to_datetime(min(train_dates)).date()) if train_dates else None,
            "train_end": str(pd.to_datetime(max(train_dates)).date()) if train_dates else None,
            "risk_off_narrow_dates": int(pred.loc[pred["risk_off_narrow_index_led"], "trade_date_text"].nunique()),
        }
        for pred_col in [
            "pred_current_baseline",
            "pred_drop_planned_features",
            "pred_planned_features_only",
            "pred_planned_on_narrow_else_baseline",
            "pred_planned_on_narrow_else_drop",
        ]:
            fold[pred_col.removeprefix("pred_")] = evaluate_prediction(pred, pred_col, args.top_n)["topn_proxy"]
        fold_rows.append(fold)

    combined = pd.concat(prediction_frames, ignore_index=True) if prediction_frames else pd.DataFrame()
    variants = {}
    for pred_col in [
        "pred_current_baseline",
        "pred_drop_planned_features",
        "pred_planned_features_only",
        "pred_planned_on_narrow_else_baseline",
        "pred_planned_on_narrow_else_drop",
    ]:
        variants[pred_col.removeprefix("pred_")] = evaluate_prediction(combined, pred_col, args.top_n) if not combined.empty else {}

    baseline_uplift = (variants.get("current_baseline", {}).get("topn_proxy") or {}).get("topn_minus_universe_return")
    decisions = {}
    for name, row in variants.items():
        uplift = (row.get("topn_proxy") or {}).get("topn_minus_universe_return")
        decisions[name] = {
            "delta_vs_baseline_uplift": round(float(uplift) - float(baseline_uplift), 6)
            if uplift is not None and baseline_uplift is not None
            else None,
            "decision": "DIAGNOSTIC_ONLY",
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK",
        "contract": {
            "research_only": True,
            "in_memory_models_only": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_production_ranking": True,
            "does_not_change_risk_adjusted_score": True,
            "production_promotion_allowed": False,
            "same_run_filters_allowed": False,
            "model_hash_before": MODEL_HASH,
        },
        "inputs": {
            "data_dir": repo_path(resolve_path(args.data_dir)),
            "market_regime_history": repo_path(resolve_path(args.market_regime_history)),
            "run_manifest": repo_path(manifest_path) if manifest_path else None,
            "folds": args.folds,
            "embargo_trade_days": args.embargo_trade_days,
            "top_n": args.top_n,
            "routing_definition": {
                "regime_label": "RISK_OFF",
                "breadth_ma20": "<=0.25",
                "top_sector_value_share": ">=0.62",
                "value_weight_return": ">=-0.005",
            },
        },
        "summary": {
            "rows": int(len(frame)),
            "fold_count": len([row for row in fold_rows if row.get("status") == "OK"]),
            "risk_off_narrow_dates": int(combined.loc[combined["risk_off_narrow_index_led"], "trade_date_text"].nunique()) if not combined.empty else 0,
            "baseline_uplift": baseline_uplift,
            "best_variant": max(
                variants,
                key=lambda name: float((variants[name].get("topn_proxy") or {}).get("topn_minus_universe_return") or -999),
            )
            if variants
            else None,
        },
        "decisions": decisions,
        "variants": variants,
        "folds": fold_rows,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Risk-Off Narrow Routing Research",
        "",
        f"- status：`{payload['status']}`",
        f"- production_promotion_allowed：`{payload['contract']['production_promotion_allowed']}`",
        f"- same_run_filters_allowed：`{payload['contract']['same_run_filters_allowed']}`",
        f"- risk_off_narrow_dates：`{payload['summary']['risk_off_narrow_dates']}`",
        f"- best_variant：`{payload['summary']['best_variant']}`",
        "",
        "| Variant | AUC | TopN Return | Universe Return | Uplift | Delta vs Baseline Uplift |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, row in payload.get("variants", {}).items():
        topn = row.get("topn_proxy") or {}
        decision = payload.get("decisions", {}).get(name, {})
        lines.append(
            "| {name} | {auc} | {ret} | {universe} | {uplift} | {delta} |".format(
                name=name,
                auc=row.get("auc"),
                ret=topn.get("avg_topn_future_return"),
                universe=topn.get("avg_universe_future_return"),
                uplift=topn.get("topn_minus_universe_return"),
                delta=decision.get("delta_vs_baseline_uplift"),
            )
        )
    lines.extend(["", "## Fold Routing Coverage", "", "| Fold | Window | Routed Dates |", "|---:|---|---:|"])
    for row in payload.get("folds", []):
        lines.append(
            f"| {row.get('fold')} | {row.get('validation_start')} ~ {row.get('validation_end')} | {row.get('risk_off_narrow_dates')} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = resolve_path(args.output) if args.output else OUTPUT_DIR / f"risk_off_narrow_routing_{args.date}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": "OK", "output": repo_path(output), **payload["summary"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
