#!/usr/bin/env python3
"""執行 regime feature group 的離線模型消融。

此腳本只訓練暫存記憶體內模型來比較特徵組合，不保存 model 檔、
不覆蓋 models/latest_lgbm.pkl、不修改 production ranking。
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import lightgbm as lgb
import pandas as pd
from sklearn.metrics import log_loss, roc_auc_score


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.labels import LabelGenerator  # noqa: E402
from app.modeling.feature_contract import candidate_feature_columns, load_m4_feature_frame  # noqa: E402


OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "model_experiments"
SCHEMA_VERSION = "regime-feature-offline-ablation.v1"
PRE_REGISTERED_GATE_VARIANT = "current_baseline"
DIAGNOSTIC_ONLY_VARIANTS = ("drop_planned_features", "planned_features_only")
RESEARCH_QUESTION = "近半年 walk-forward 下，模型 Top10 是否穩定打贏同日市場平均？"
RESEARCH_LAYER = "model"
DECISION_PROMOTE = "PROMOTE_CANDIDATE"
DECISION_MONITOR = "MONITOR_ONLY"
DECISION_REJECTED = "REJECTED"
MIN_BASELINE_AUC = 0.60
MIN_TOPN_UPLIFT = 0.0
MIN_POSITIVE_FOLDS = 4


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="research regime feature offline ablation")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--data-dir", default="data/clean")
    parser.add_argument("--run-manifest", default=None)
    parser.add_argument("--market-regime-history", default="artifacts/market_regime_history_2026-05-29.json")
    parser.add_argument("--horizon", type=int, default=10)
    parser.add_argument("--threshold", type=float, default=0.05)
    parser.add_argument("--folds", type=int, default=4)
    parser.add_argument("--embargo-trade-days", type=int, default=10)
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--num-boost-round", type=int, default=120)
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


def load_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def latest_manifest() -> Path | None:
    matches = sorted(OUTPUT_DIR.glob("model_exp_run_manifest_????-??-??.json"))
    return matches[-1] if matches else None


def planned_features(manifest: dict[str, Any]) -> list[str]:
    for run in manifest.get("runs", []):
        if run.get("experiment_id") == "model_exp_regime_feature_group_ablation":
            return sorted({str(feature) for feature in run.get("planned_features", []) if feature})
    return []


def regime_map(path: Path) -> dict[str, str]:
    payload = load_json(path)
    return {
        str(row.get("trade_date")): str(row.get("regime_label"))
        for row in payload.get("rows", [])
        if row.get("trade_date") and row.get("regime_label")
    }


def labeled_frame(args: argparse.Namespace) -> tuple[pd.DataFrame, list[str], list[str], Path | None]:
    data_dir = resolve_path(args.data_dir)
    if data_dir is None:
        raise RuntimeError("data_dir path resolution failed")
    frame, metadata = load_m4_feature_frame(data_dir=data_dir, project_root=PROJECT_ROOT)
    frame = frame.copy()
    frame["date"] = pd.to_datetime(frame["trade_date"], errors="coerce").dt.normalize()
    frame["stock_id"] = frame["stock_id"].astype(str).str.strip().str.zfill(4)
    generator = LabelGenerator(horizon=args.horizon, threshold=args.threshold)
    labeled = generator.generate_labels(frame)
    labeled = labeled.dropna(subset=["target", "future_return", "entry_price", "exit_price"]).copy()
    labeled["target"] = labeled["target"].astype(int)
    labeled["trade_date"] = pd.to_datetime(labeled["date"], errors="coerce").dt.normalize()
    mapping = regime_map(resolve_path(args.market_regime_history) or Path())
    labeled["trade_date_text"] = labeled["trade_date"].dt.date.astype(str)
    labeled["regime_label"] = labeled["trade_date_text"].map(mapping).fillna("UNKNOWN")
    all_features = candidate_feature_columns(labeled, metadata)
    manifest_path = resolve_path(args.run_manifest) or latest_manifest()
    planned = [feature for feature in planned_features(load_json(manifest_path)) if feature in all_features]
    return labeled.sort_values(["trade_date", "stock_id"]).copy(), all_features, planned, manifest_path


def fold_windows(dates: list[pd.Timestamp], folds: int) -> list[dict[str, Any]]:
    if folds < 1:
        raise ValueError("--folds must be >= 1")
    unique_dates = sorted(pd.to_datetime(dates).unique())
    if len(unique_dates) < folds + 2:
        raise ValueError("交易日數不足，無法建立 folds")
    validation_dates = unique_dates[-max(folds * 20, folds):]
    chunk_size = max(1, math.ceil(len(validation_dates) / folds))
    windows = []
    for index in range(folds):
        val = validation_dates[index * chunk_size : (index + 1) * chunk_size]
        if len(val) == 0:
            continue
        windows.append({"fold": index + 1, "validation_dates": list(val)})
    return windows


def train_dates_for_fold(all_dates: list[pd.Timestamp], validation_dates: list[pd.Timestamp], embargo: int) -> list[pd.Timestamp]:
    first_val = min(validation_dates)
    ordered = sorted(pd.to_datetime(all_dates).unique())
    try:
        first_index = ordered.index(first_val)
    except ValueError:
        return []
    cutoff = max(0, first_index - embargo)
    return ordered[:cutoff]


def feature_sets(all_features: list[str], planned: list[str]) -> dict[str, list[str]]:
    planned_set = set(planned)
    return {
        "current_baseline": all_features,
        "drop_planned_features": [feature for feature in all_features if feature not in planned_set],
        "planned_features_only": planned,
    }


def model_params() -> dict[str, Any]:
    return {
        "objective": "binary",
        "metric": "auc",
        "verbosity": -1,
        "boosting_type": "gbdt",
        "learning_rate": 0.05,
        "num_leaves": 31,
        "feature_fraction": 0.85,
        "bagging_fraction": 0.85,
        "bagging_freq": 1,
        "min_child_samples": 80,
        "lambda_l1": 0.1,
        "lambda_l2": 1.0,
        "is_unbalance": True,
        "seed": 42,
        "num_threads": 4,
    }


def safe_auc(y_true: pd.Series, prob: pd.Series) -> float | None:
    if y_true.nunique(dropna=True) < 2:
        return None
    return round(float(roc_auc_score(y_true, prob)), 6)


def safe_logloss(y_true: pd.Series, prob: pd.Series) -> float | None:
    if y_true.nunique(dropna=True) < 2:
        return None
    clipped = prob.clip(1e-6, 1 - 1e-6)
    return round(float(log_loss(y_true, clipped)), 6)


def topn_proxy(frame: pd.DataFrame, top_n: int) -> dict[str, Any]:
    if frame.empty:
        return {"date_count": 0, "trade_count": 0}
    rows = []
    for date_text, group in frame.groupby("trade_date_text", sort=True):
        top = group.sort_values("pred_prob", ascending=False).head(top_n)
        top_return = pd.to_numeric(top["future_return"], errors="coerce")
        universe_return = pd.to_numeric(group["future_return"], errors="coerce")
        rows.append(
            {
                "trade_date": date_text,
                "avg_future_return": float(top_return.mean()),
                "universe_avg_future_return": float(universe_return.mean()),
                "hit_rate": float((top_return > 0).mean()),
                "universe_hit_rate": float((universe_return > 0).mean()),
                "count": int(len(top)),
            }
        )
    result = pd.DataFrame(rows)
    topn_return = float(result["avg_future_return"].mean())
    universe_return = float(result["universe_avg_future_return"].mean())
    topn_hit = float(result["hit_rate"].mean())
    universe_hit = float(result["universe_hit_rate"].mean())
    return {
        "date_count": int(len(result)),
        "trade_count": int(result["count"].sum()),
        "avg_topn_future_return": round(topn_return, 6),
        "avg_universe_future_return": round(universe_return, 6),
        "topn_minus_universe_return": round(topn_return - universe_return, 6),
        "avg_topn_hit_rate": round(topn_hit, 6),
        "avg_universe_hit_rate": round(universe_hit, 6),
        "topn_minus_universe_hit_rate": round(topn_hit - universe_hit, 6),
    }


def evaluate_regimes(frame: pd.DataFrame, top_n: int) -> dict[str, Any]:
    result = {}
    for regime, group in frame.groupby("regime_label", dropna=False):
        y = group["target"].astype(int)
        prob = group["pred_prob"]
        result[str(regime)] = {
            "rows": int(len(group)),
            "auc": safe_auc(y, prob),
            "logloss": safe_logloss(y, prob),
            "topn_proxy": topn_proxy(group, top_n=top_n),
        }
    return result


def run_variant(
    frame: pd.DataFrame,
    features: list[str],
    windows: list[dict[str, Any]],
    embargo: int,
    num_boost_round: int,
    top_n: int,
) -> dict[str, Any]:
    if not features:
        return {"status": "SKIPPED", "reason": "no features", "folds": []}
    all_dates = sorted(frame["trade_date"].drop_duplicates().tolist())
    fold_rows = []
    predictions = []
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
            lgb.Dataset(train[features], label=train["target"], feature_name=features),
            num_boost_round=num_boost_round,
        )
        valid = valid.copy()
        valid["pred_prob"] = model.predict(valid[features])
        y_valid = valid["target"].astype(int)
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
                "auc": safe_auc(y_valid, valid["pred_prob"]),
                "logloss": safe_logloss(y_valid, valid["pred_prob"]),
                "topn_proxy": topn_proxy(valid, top_n=top_n),
            }
        )
        predictions.append(valid[["trade_date_text", "stock_id", "regime_label", "target", "future_return", "pred_prob"]])
    prediction_frame = pd.concat(predictions, ignore_index=True) if predictions else pd.DataFrame()
    ok_folds = [row for row in fold_rows if row.get("status") == "OK"]
    auc_values = [row["auc"] for row in ok_folds if row.get("auc") is not None]
    logloss_values = [row["logloss"] for row in ok_folds if row.get("logloss") is not None]
    return {
        "status": "OK" if ok_folds else "SKIPPED",
        "feature_count": len(features),
        "fold_count": len(ok_folds),
        "avg_auc": round(float(pd.Series(auc_values).mean()), 6) if auc_values else None,
        "avg_logloss": round(float(pd.Series(logloss_values).mean()), 6) if logloss_values else None,
        "topn_proxy": topn_proxy(prediction_frame, top_n=top_n) if not prediction_frame.empty else {},
        "regime_breakdown": evaluate_regimes(prediction_frame, top_n=top_n) if not prediction_frame.empty else {},
        "folds": fold_rows,
    }


def delta(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return round(left - right, 6)


def decision_for_baseline(baseline: dict[str, Any]) -> dict[str, Any]:
    topn = baseline.get("topn_proxy", {}) if isinstance(baseline.get("topn_proxy"), dict) else {}
    folds = baseline.get("folds", []) if isinstance(baseline.get("folds"), list) else []
    baseline_auc = baseline.get("avg_auc")
    uplift = topn.get("topn_minus_universe_return")
    positive_folds = [
        row
        for row in folds
        if float((row.get("topn_proxy") or {}).get("topn_minus_universe_return") or 0) > MIN_TOPN_UPLIFT
    ]
    negative_folds = [
        f"{row.get('validation_start')}~{row.get('validation_end')}"
        for row in folds
        if float((row.get("topn_proxy") or {}).get("topn_minus_universe_return") or 0) <= MIN_TOPN_UPLIFT
    ]
    failed = []
    if baseline_auc is None or float(baseline_auc) < MIN_BASELINE_AUC:
        failed.append(f"baseline_auc<{MIN_BASELINE_AUC}")
    if uplift is None or float(uplift) <= MIN_TOPN_UPLIFT:
        failed.append("topn_uplift<=0")
    if len(positive_folds) < MIN_POSITIVE_FOLDS:
        failed.append(f"positive_folds<{MIN_POSITIVE_FOLDS}")

    if failed:
        decision = DECISION_REJECTED
        rationale = "主要 gate 未通過：" + ", ".join(failed)
    elif negative_folds:
        decision = DECISION_MONITOR
        rationale = "整體有訊號，但仍有負 uplift folds；先監控，不進 promotion。"
    else:
        decision = DECISION_PROMOTE
        rationale = "預註冊 gate 通過且未出現負 uplift folds；可進人工 promotion review。"
    return {
        "decision": decision,
        "decision_rationale": rationale,
        "policy": {
            "promote_requires_baseline_auc_at_least": MIN_BASELINE_AUC,
            "promote_requires_topn_uplift_above": MIN_TOPN_UPLIFT,
            "promote_requires_positive_folds_at_least": MIN_POSITIVE_FOLDS,
            "negative_folds_force_monitor_only": True,
        },
        "diagnostics": {
            "positive_fold_count": len(positive_folds),
            "negative_or_flat_folds": negative_folds,
        },
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    frame, all_features, planned, manifest_path = labeled_frame(args)
    windows = fold_windows(frame["trade_date"].drop_duplicates().tolist(), folds=args.folds)
    variants = {}
    for name, features in feature_sets(all_features, planned).items():
        variants[name] = run_variant(
            frame=frame,
            features=features,
            windows=windows,
            embargo=args.embargo_trade_days,
            num_boost_round=args.num_boost_round,
            top_n=args.top_n,
        )
    baseline = variants.get("current_baseline", {})
    dropped = variants.get("drop_planned_features", {})
    planned_only = variants.get("planned_features_only", {})
    decision = decision_for_baseline(baseline)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK",
        "research_question": RESEARCH_QUESTION,
        "layer": RESEARCH_LAYER,
        "pre_registered": True,
        "decision": decision["decision"],
        "decision_rationale": decision["decision_rationale"],
        "decision_policy": decision["policy"],
        "diagnostics_not_for_promotion": [
            "drop_planned_features",
            "planned_features_only",
            "regime_breakdown",
            "negative_or_flat_folds",
        ],
        "decision_diagnostics": decision["diagnostics"],
        "contract": {
            "research_only": True,
            "in_memory_models_only": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_risk_adjusted_score": True,
            "does_not_change_production_ranking": True,
            "production_promotion_allowed": False,
            "split_policy": "chronological validation tail with embargo",
            "no_hindsight_policy": {
                "validation_windows_are_chronological": True,
                "train_dates_end_before_validation_start": True,
                "embargo_trade_days": args.embargo_trade_days,
                "promotion_gate_variant": PRE_REGISTERED_GATE_VARIANT,
                "diagnostic_only_variants": list(DIAGNOSTIC_ONLY_VARIANTS),
                "diagnostic_failures_cannot_define_same_run_filters": True,
                "new_filters_require_next_walkforward_run": True,
                "regime_breakdown_is_post_hoc_diagnostic": True,
            },
        },
        "inputs": {
            "data_dir": repo_path(resolve_path(args.data_dir)),
            "run_manifest": repo_path(manifest_path),
            "market_regime_history": repo_path(resolve_path(args.market_regime_history)),
            "horizon": args.horizon,
            "threshold": args.threshold,
            "folds": args.folds,
            "embargo_trade_days": args.embargo_trade_days,
            "top_n": args.top_n,
            "num_boost_round": args.num_boost_round,
        },
        "summary": {
            "rows": int(len(frame)),
            "stocks": int(frame["stock_id"].nunique()),
            "dates": int(frame["trade_date"].nunique()),
            "all_feature_count": len(all_features),
            "planned_features": planned,
            "planned_feature_count": len(planned),
            "baseline_auc": baseline.get("avg_auc"),
            "drop_planned_auc": dropped.get("avg_auc"),
            "planned_only_auc": planned_only.get("avg_auc"),
            "baseline_minus_drop_auc": delta(baseline.get("avg_auc"), dropped.get("avg_auc")),
            "baseline_topn_return": baseline.get("topn_proxy", {}).get("avg_topn_future_return"),
            "baseline_universe_return": baseline.get("topn_proxy", {}).get("avg_universe_future_return"),
            "baseline_topn_minus_universe_return": baseline.get("topn_proxy", {}).get("topn_minus_universe_return"),
            "drop_planned_topn_return": dropped.get("topn_proxy", {}).get("avg_topn_future_return"),
            "drop_planned_universe_return": dropped.get("topn_proxy", {}).get("avg_universe_future_return"),
            "drop_planned_topn_minus_universe_return": dropped.get("topn_proxy", {}).get("topn_minus_universe_return"),
            "baseline_minus_drop_topn_return": delta(
                baseline.get("topn_proxy", {}).get("avg_topn_future_return"),
                dropped.get("topn_proxy", {}).get("avg_topn_future_return"),
            ),
        },
        "variants": variants,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    baseline = payload["variants"].get("current_baseline", {})
    lines = [
        "# Regime Feature Offline Ablation / Walk-forward Validation",
        "",
        f"- status：`{payload['status']}`",
        f"- research_question：`{payload.get('research_question')}`",
        f"- layer：`{payload.get('layer')}`",
        f"- pre_registered：`{payload.get('pre_registered')}`",
        f"- decision：`{payload.get('decision')}`",
        f"- decision_rationale：{payload.get('decision_rationale')}",
        f"- rows：`{summary['rows']}`",
        f"- promotion_gate_variant：`{payload['contract']['no_hindsight_policy']['promotion_gate_variant']}`",
        f"- diagnostic_only_variants：`{payload['contract']['no_hindsight_policy']['diagnostic_only_variants']}`",
        f"- diagnostic_failures_cannot_define_same_run_filters：`{payload['contract']['no_hindsight_policy']['diagnostic_failures_cannot_define_same_run_filters']}`",
        f"- planned_features：`{summary['planned_features']}`",
        f"- baseline_auc：`{summary['baseline_auc']}`",
        f"- drop_planned_auc：`{summary['drop_planned_auc']}`",
        f"- baseline_minus_drop_auc：`{summary['baseline_minus_drop_auc']}`",
        f"- baseline_minus_drop_topn_return：`{summary['baseline_minus_drop_topn_return']}`",
        f"- baseline_topn_minus_universe_return：`{summary['baseline_topn_minus_universe_return']}`",
        "",
        "| Variant | Features | Folds | AUC | Logloss | TopN Return | Universe Return | Uplift | TopN Hit | Universe Hit |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, item in payload["variants"].items():
        topn = item.get("topn_proxy", {})
        lines.append(
            "| {name} | {features} | {folds} | {auc} | {logloss} | {ret} | {universe} | {uplift} | {hit} | {universe_hit} |".format(
                name=name,
                features=item.get("feature_count"),
                folds=item.get("fold_count"),
                auc=item.get("avg_auc"),
                logloss=item.get("avg_logloss"),
                ret=topn.get("avg_topn_future_return"),
                universe=topn.get("avg_universe_future_return"),
                uplift=topn.get("topn_minus_universe_return"),
                hit=topn.get("avg_topn_hit_rate"),
                universe_hit=topn.get("avg_universe_hit_rate"),
            )
        )
    lines.append("")
    if baseline.get("folds"):
        lines.extend(
            [
                "## Baseline Fold Breakdown",
                "",
                "| Fold | Validation Window | AUC | TopN Return | Universe Return | Uplift | TopN Hit | Universe Hit |",
                "|---:|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in baseline["folds"]:
            topn = row.get("topn_proxy", {})
            lines.append(
                "| {fold} | {start} ~ {end} | {auc} | {ret} | {universe} | {uplift} | {hit} | {universe_hit} |".format(
                    fold=row.get("fold"),
                    start=row.get("validation_start"),
                    end=row.get("validation_end"),
                    auc=row.get("auc"),
                    ret=topn.get("avg_topn_future_return"),
                    universe=topn.get("avg_universe_future_return"),
                    uplift=topn.get("topn_minus_universe_return"),
                    hit=topn.get("avg_topn_hit_rate"),
                    universe_hit=topn.get("avg_universe_hit_rate"),
                )
            )
        lines.append("")
    regimes = baseline.get("regime_breakdown", {})
    if regimes:
        lines.extend(
            [
                "## Baseline Regime Breakdown",
                "",
                "| Regime | Dates | Trades | AUC | TopN Return | Universe Return | Uplift | TopN Hit | Universe Hit |",
                "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for regime, row in sorted(regimes.items()):
            topn = row.get("topn_proxy", {})
            lines.append(
                "| {regime} | {dates} | {trades} | {auc} | {ret} | {universe} | {uplift} | {hit} | {universe_hit} |".format(
                    regime=regime,
                    dates=topn.get("date_count"),
                    trades=topn.get("trade_count"),
                    auc=row.get("auc"),
                    ret=topn.get("avg_topn_future_return"),
                    universe=topn.get("avg_universe_future_return"),
                    uplift=topn.get("topn_minus_universe_return"),
                    hit=topn.get("avg_topn_hit_rate"),
                    universe_hit=topn.get("avg_universe_hit_rate"),
                )
            )
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = resolve_path(args.output) or OUTPUT_DIR / f"regime_feature_offline_ablation_{args.date}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output), **payload["summary"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
