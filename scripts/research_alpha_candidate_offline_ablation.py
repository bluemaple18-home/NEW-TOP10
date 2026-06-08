#!/usr/bin/env python3
"""執行 shadow alpha 候選因子的離線模型消融。

只訓練記憶體內暫時模型，比較 baseline 與 baseline+alpha；不保存模型、不改排名。
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import date, datetime, timezone
from pathlib import Path
import sys
from typing import Any

import lightgbm as lgb
import pandas as pd
from sklearn.metrics import log_loss, roc_auc_score


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.labels import LabelGenerator
from app.modeling.feature_contract import candidate_feature_columns, load_m4_feature_frame


OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "model_experiments"
SCHEMA_VERSION = "alpha-candidate-offline-ablation.v1"
DECISION_PROMOTE = "PROMOTE_TO_NEXT_REPLAY"
DECISION_MONITOR = "MONITOR_ONLY"
DECISION_REJECTED = "REJECTED"
MIN_AUC_DELTA = 0.001
MIN_TOPN_DELTA = 0.0
MIN_POSITIVE_FOLDS = 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="research alpha candidate offline ablation")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--data-dir", default="data/clean")
    parser.add_argument("--alpha-artifact", default=None)
    parser.add_argument("--signal-check", default=None)
    parser.add_argument("--horizon", type=int, default=10)
    parser.add_argument("--threshold", type=float, default=0.05)
    parser.add_argument("--folds", type=int, default=4)
    parser.add_argument("--embargo-trade-days", type=int, default=10)
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--num-boost-round", type=int, default=80)
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


def latest_artifact(pattern: str) -> Path | None:
    matches = sorted(OUTPUT_DIR.glob(pattern))
    return matches[-1] if matches else None


def load_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def selected_alpha_features(signal_check: dict[str, Any], alpha_frame: pd.DataFrame) -> list[str]:
    candidates = [
        str(feature)
        for feature in signal_check.get("summary", {}).get("shadow_candidates", [])
        if str(feature) in alpha_frame.columns
    ]
    if candidates:
        return candidates
    return [
        column
        for column in alpha_frame.columns
        if column not in {"date", "stock_id"} and pd.api.types.is_numeric_dtype(alpha_frame[column])
    ]


def load_alpha_frame(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    missing = [column for column in ("date", "stock_id") if column not in frame.columns]
    if missing:
        raise ValueError(f"alpha artifact 缺少必要欄位：{missing}")
    frame = frame.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    if frame["date"].isna().any():
        raise ValueError("alpha artifact date 欄位含不可解析日期")
    frame["stock_id"] = frame["stock_id"].astype(str).str.strip()
    if frame.duplicated(["date", "stock_id"]).any():
        raise ValueError("alpha artifact 含同股同交易日多筆資料")
    return frame.sort_values(["date", "stock_id"]).copy()


def labeled_frame(args: argparse.Namespace) -> tuple[pd.DataFrame, list[str], list[str], Path, Path | None]:
    data_dir = resolve_path(args.data_dir)
    if data_dir is None:
        raise RuntimeError("data_dir path resolution failed")
    alpha_path = resolve_path(args.alpha_artifact) or latest_artifact("alpha_candidate_features_????-??-??.parquet")
    if alpha_path is None:
        raise FileNotFoundError("找不到 alpha_candidate_features_YYYY-MM-DD.parquet")
    signal_path = resolve_path(args.signal_check) or latest_artifact("alpha_candidate_signal_check_????-??-??.json")
    signal_check = load_json(signal_path)

    frame, metadata = load_m4_feature_frame(data_dir=data_dir, project_root=PROJECT_ROOT)
    frame = frame.copy()
    frame["date"] = pd.to_datetime(frame["trade_date"], errors="coerce").dt.normalize()
    frame["stock_id"] = frame["stock_id"].astype(str).str.strip()
    labeled = LabelGenerator(horizon=args.horizon, threshold=args.threshold).generate_labels(frame)
    labeled = labeled.dropna(subset=["target", "future_return", "entry_price", "exit_price"]).copy()
    labeled["target"] = labeled["target"].astype(int)
    baseline_features = candidate_feature_columns(labeled, metadata)

    alpha = load_alpha_frame(alpha_path)
    alpha_features = selected_alpha_features(signal_check, alpha)
    if not alpha_features:
        raise ValueError("沒有可用 alpha candidate features")
    merged = labeled.merge(alpha[["date", "stock_id", *alpha_features]], on=["date", "stock_id"], how="inner", validate="one_to_one")
    if merged.empty:
        raise RuntimeError("M4 feature frame 與 alpha artifact 沒有可重疊資料")
    merged["trade_date"] = pd.to_datetime(merged["date"], errors="coerce").dt.normalize()
    merged["trade_date_text"] = merged["trade_date"].dt.date.astype(str)
    return merged.sort_values(["trade_date", "stock_id"]).copy(), baseline_features, alpha_features, alpha_path, signal_path


def fold_windows(dates: list[pd.Timestamp], folds: int) -> list[dict[str, Any]]:
    if folds < 1:
        raise ValueError("--folds must be >= 1")
    unique_dates = sorted(pd.to_datetime(dates).unique())
    if len(unique_dates) < folds + 2:
        raise ValueError("交易日數不足，無法建立 folds")
    validation_dates = unique_dates[-max(folds * 20, folds):]
    chunk_size = max(1, math.ceil(len(validation_dates) / folds))
    return [
        {"fold": index + 1, "validation_dates": list(validation_dates[index * chunk_size : (index + 1) * chunk_size])}
        for index in range(folds)
        if len(validation_dates[index * chunk_size : (index + 1) * chunk_size]) > 0
    ]


def train_dates_for_fold(all_dates: list[pd.Timestamp], validation_dates: list[pd.Timestamp], embargo: int) -> list[pd.Timestamp]:
    first_val = min(validation_dates)
    ordered = sorted(pd.to_datetime(all_dates).unique())
    try:
        first_index = ordered.index(first_val)
    except ValueError:
        return []
    cutoff = max(0, first_index - embargo)
    return ordered[:cutoff]


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
    return round(float(log_loss(y_true, prob.clip(1e-6, 1 - 1e-6))), 6)


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
        predictions.append(valid[["trade_date_text", "stock_id", "target", "future_return", "pred_prob"]])
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
        "folds": fold_rows,
    }


def delta(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return round(left - right, 6)


def decision_for(plus: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    auc_delta = delta(plus.get("avg_auc"), baseline.get("avg_auc"))
    plus_topn = plus.get("topn_proxy", {}) if isinstance(plus.get("topn_proxy"), dict) else {}
    base_topn = baseline.get("topn_proxy", {}) if isinstance(baseline.get("topn_proxy"), dict) else {}
    topn_delta = delta(plus_topn.get("avg_topn_future_return"), base_topn.get("avg_topn_future_return"))
    plus_folds = plus.get("folds", []) if isinstance(plus.get("folds"), list) else []
    base_folds = baseline.get("folds", []) if isinstance(baseline.get("folds"), list) else []
    positive_folds = 0
    for plus_fold, base_fold in zip(plus_folds, base_folds, strict=False):
        plus_return = (plus_fold.get("topn_proxy") or {}).get("avg_topn_future_return")
        base_return = (base_fold.get("topn_proxy") or {}).get("avg_topn_future_return")
        if delta(plus_return, base_return) is not None and float(delta(plus_return, base_return) or 0) > MIN_TOPN_DELTA:
            positive_folds += 1
    failed = []
    if auc_delta is None or auc_delta < MIN_AUC_DELTA:
        failed.append(f"auc_delta<{MIN_AUC_DELTA}")
    if topn_delta is None or topn_delta <= MIN_TOPN_DELTA:
        failed.append("topn_delta<=0")
    if positive_folds < MIN_POSITIVE_FOLDS:
        failed.append(f"positive_folds<{MIN_POSITIVE_FOLDS}")
    if failed:
        decision = DECISION_REJECTED
        rationale = "alpha ablation 未通過：" + ", ".join(failed)
    else:
        decision = DECISION_PROMOTE
        rationale = "alpha 相對 baseline 在 AUC、TopN proxy 與 fold 一致性都有正向改善；可進下一輪 replay。"
    if decision == DECISION_PROMOTE and any((row.get("topn_proxy") or {}).get("topn_minus_universe_return", 0) <= 0 for row in plus_folds):
        decision = DECISION_MONITOR
        rationale = "alpha 有改善但仍存在 TopN 不打贏 universe 的 fold；先監控。"
    return {
        "decision": decision,
        "decision_rationale": rationale,
        "policy": {
            "min_auc_delta": MIN_AUC_DELTA,
            "min_topn_delta": MIN_TOPN_DELTA,
            "min_positive_folds": MIN_POSITIVE_FOLDS,
            "production_promotion_allowed": False,
        },
        "diagnostics": {
            "auc_delta": auc_delta,
            "topn_return_delta": topn_delta,
            "positive_fold_count": positive_folds,
            "failed": failed,
        },
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    frame, baseline_features, alpha_features, alpha_path, signal_path = labeled_frame(args)
    windows = fold_windows(frame["trade_date"].drop_duplicates().tolist(), folds=args.folds)
    variants = {
        "baseline_only": run_variant(frame, baseline_features, windows, args.embargo_trade_days, args.num_boost_round, args.top_n),
        "baseline_plus_alpha": run_variant(
            frame,
            [*baseline_features, *alpha_features],
            windows,
            args.embargo_trade_days,
            args.num_boost_round,
            args.top_n,
        ),
        "alpha_only_diagnostic": run_variant(frame, alpha_features, windows, args.embargo_trade_days, args.num_boost_round, args.top_n),
    }
    decision = decision_for(variants["baseline_plus_alpha"], variants["baseline_only"])
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK",
        "research_question": "shadow alpha candidates 是否能在 walk-forward 中改善 baseline 模型？",
        "layer": "model",
        "pre_registered": True,
        "decision": decision["decision"],
        "decision_rationale": decision["decision_rationale"],
        "decision_policy": decision["policy"],
        "decision_diagnostics": decision["diagnostics"],
        "diagnostics_not_for_promotion": ["alpha_only_diagnostic"],
        "contract": {
            "research_only": True,
            "in_memory_models_only": True,
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
                "promotion_gate_variant": "baseline_plus_alpha_vs_baseline_only",
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
        },
        "summary": {
            "rows": int(len(frame)),
            "stocks": int(frame["stock_id"].nunique()),
            "dates": int(frame["trade_date"].nunique()),
            "baseline_feature_count": len(baseline_features),
            "alpha_features": alpha_features,
            "alpha_feature_count": len(alpha_features),
            "baseline_auc": variants["baseline_only"].get("avg_auc"),
            "baseline_plus_alpha_auc": variants["baseline_plus_alpha"].get("avg_auc"),
            "auc_delta": decision["diagnostics"]["auc_delta"],
            "baseline_topn_return": variants["baseline_only"].get("topn_proxy", {}).get("avg_topn_future_return"),
            "baseline_plus_alpha_topn_return": variants["baseline_plus_alpha"].get("topn_proxy", {}).get("avg_topn_future_return"),
            "topn_return_delta": decision["diagnostics"]["topn_return_delta"],
        },
        "variants": variants,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Alpha Candidate Offline Ablation",
        "",
        f"- status：`{payload['status']}`",
        f"- decision：`{payload['decision']}`",
        f"- decision_rationale：{payload['decision_rationale']}",
        f"- alpha_features：`{summary['alpha_features']}`",
        f"- auc_delta：`{summary['auc_delta']}`",
        f"- topn_return_delta：`{summary['topn_return_delta']}`",
        f"- production_promotion_allowed：`{payload['contract']['production_promotion_allowed']}`",
        "",
        "| Variant | Features | Folds | AUC | Logloss | TopN Return | Universe Return | Uplift |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, item in payload["variants"].items():
        topn = item.get("topn_proxy", {})
        lines.append(
            f"| {name} | {item.get('feature_count')} | {item.get('fold_count')} | {item.get('avg_auc')} | "
            f"{item.get('avg_logloss')} | {topn.get('avg_topn_future_return')} | "
            f"{topn.get('avg_universe_future_return')} | {topn.get('topn_minus_universe_return')} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = resolve_path(args.output) or OUTPUT_DIR / f"alpha_candidate_offline_ablation_{args.date}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output), **payload["summary"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
