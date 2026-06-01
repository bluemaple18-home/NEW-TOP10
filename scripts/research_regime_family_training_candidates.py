#!/usr/bin/env python3
"""針對指定盤勢族群執行訓練候選研究。

本腳本只訓練記憶體內模型並產出 research artifact，不保存模型、不覆蓋
`models/latest_lgbm.pkl`、不修改 production ranking。
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
SCHEMA_VERSION = "regime-family-training-candidates.v1"
RESEARCH_LAYER = "model"
RESEARCH_QUESTION = "在固定 base regime 之外，預註冊且可重疊的 regime family tag 是否能改善候選訓練？"
DECISION_PROMOTE = "PROMOTE_CANDIDATE"
DECISION_MONITOR = "MONITOR_ONLY"
DECISION_REJECTED = "REJECTED"
BASE_REGIME_LABELS = [
    "BROAD_RISK_ON",
    "NARROW_LEADER",
    "CHOPPY_RANGE",
    "RISK_OFF",
    "PANIC_SELLING",
    "EARLY_REVERSAL",
    "MIXED_NEUTRAL",
    "UNKNOWN",
]
REGIME_FAMILY_TAGS = ["HIGH_CHOPPY", "BIG_BULL"]

MIN_DATES_PER_FAMILY = 18
MIN_OK_FOLDS = 3
MIN_AUC = 0.58
MIN_TOPN_UPLIFT = 0.0
MIN_DELTA_TOPN_RETURN = 0.002
MIN_DELTA_AUC = 0.001


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="research regime family training candidates")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--data-dir", default="data/clean")
    parser.add_argument("--market-regime-history", default="artifacts/market_regime_history_2026-05-29.json")
    parser.add_argument("--families", default="HIGH_CHOPPY,BIG_BULL")
    parser.add_argument("--horizon", type=int, default=10)
    parser.add_argument("--threshold", type=float, default=0.05)
    parser.add_argument("--folds", type=int, default=4)
    parser.add_argument("--embargo-trade-days", type=int, default=10)
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--num-boost-round", type=int, default=120)
    parser.add_argument("--family-weight", type=float, default=2.0)
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


def regime_rows(path: Path) -> pd.DataFrame:
    payload = load_json(path)
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    frame = pd.DataFrame(rows)
    if frame.empty:
        raise ValueError(f"market regime history 無 rows：{path}")
    frame["trade_date_text"] = frame["trade_date"].astype(str)
    for col in [
        "equal_weight_return",
        "value_weight_return",
        "breadth_ma20",
        "breadth_ma60",
        "advance_ratio",
        "breakout_ratio",
        "breakdown_ratio",
        "volume_spike_ratio",
        "long_upper_shadow_ratio",
        "avg_rsi",
        "top_sector_value_share",
        "top_strong_sector_value_share",
    ]:
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce")
    frame = frame.sort_values("trade_date").copy()
    frame["rolling_value_return_20d"] = rolling_compound_return(frame["value_weight_return"], 20, 10)
    frame["rolling_value_return_60d"] = rolling_compound_return(frame["value_weight_return"], 60, 30)
    frame["rolling_equal_return_20d"] = rolling_compound_return(frame["equal_weight_return"], 20, 10)
    frame["rolling_equal_return_60d"] = rolling_compound_return(frame["equal_weight_return"], 60, 30)
    frame["rolling_top_sector_share_20d"] = frame["top_sector_value_share"].rolling(20, min_periods=10).mean()
    return frame


def rolling_compound_return(series: pd.Series, window: int, min_periods: int) -> pd.Series:
    return series.fillna(0).rolling(window, min_periods=min_periods).apply(lambda values: float((1 + values).prod() - 1), raw=False)


def is_high_choppy(row: pd.Series) -> bool:
    """高檔震盪：資金集中、廣度不夠全面、上影/拉回干擾高。"""

    label = str(row.get("regime_label") or "")
    breadth = row.get("breadth_ma20")
    breadth60 = row.get("breadth_ma60")
    top_share = row.get("top_sector_value_share")
    upper = row.get("long_upper_shadow_ratio")
    ew_return = row.get("equal_weight_return")
    value_return = row.get("value_weight_return")
    if label not in {"NARROW_LEADER", "MIXED_NEUTRAL", "CHOPPY_RANGE"}:
        return False
    return (
        pd.notna(breadth)
        and 0.38 <= float(breadth) <= 0.56
        and (pd.isna(breadth60) or float(breadth60) <= 0.45)
        and pd.notna(top_share)
        and float(top_share) >= 0.65
        and pd.notna(upper)
        and float(upper) >= 0.12
        and pd.notna(ew_return)
        and float(ew_return) <= 0.016
        and (pd.isna(value_return) or float(value_return) >= -0.015)
    )


def is_big_bull(row: pd.Series) -> bool:
    """大牛市：優先辨識權值/主流族群帶動的大盤牛市。"""

    label = str(row.get("regime_label") or "")
    breadth = row.get("breadth_ma20")
    advance = row.get("advance_ratio")
    breakout = row.get("breakout_ratio")
    avg_rsi = row.get("avg_rsi")
    value_return = row.get("value_weight_return")
    ew_return = row.get("equal_weight_return")
    rolling_value_20d = row.get("rolling_value_return_20d")
    rolling_value_60d = row.get("rolling_value_return_60d")
    top_share = row.get("top_sector_value_share")
    top_strong_share = row.get("top_strong_sector_value_share")
    breakdown = row.get("breakdown_ratio")
    if label == "BROAD_RISK_ON":
        return True
    index_led_bull = (
        ((pd.notna(rolling_value_60d) and float(rolling_value_60d) >= 0.08) or (pd.notna(rolling_value_20d) and float(rolling_value_20d) >= 0.04))
        and pd.notna(top_share)
        and float(top_share) >= 0.60
        and (pd.isna(top_strong_share) or float(top_strong_share) >= 0.62)
        and (pd.isna(avg_rsi) or float(avg_rsi) >= 48)
        and (pd.isna(breakdown) or float(breakdown) <= 0.12)
    )
    if index_led_bull:
        return True
    return (
        label == "NARROW_LEADER"
        and pd.notna(breadth)
        and float(breadth) >= 0.45
        and pd.notna(advance)
        and float(advance) >= 0.48
        and pd.notna(breakout)
        and float(breakout) >= 0.05
        and pd.notna(avg_rsi)
        and float(avg_rsi) >= 50
        and pd.notna(value_return)
        and float(value_return) >= 0.015
        and pd.notna(ew_return)
        and float(ew_return) >= 0
    )


FAMILY_DEFINITIONS = {
    "HIGH_CHOPPY": {
        "zh_name": "高檔震盪盤",
        "predicate": is_high_choppy,
        "pre_registered_definition": {
            "labels": ["NARROW_LEADER", "MIXED_NEUTRAL", "CHOPPY_RANGE"],
            "breadth_ma20": "0.38~0.56",
            "breadth_ma60": "<=0.45 or unavailable",
            "top_sector_value_share": ">=0.65",
            "long_upper_shadow_ratio": ">=0.12",
            "equal_weight_return": "<=0.016",
            "value_weight_return": ">=-0.015 or unavailable",
        },
    },
    "BIG_BULL": {
        "zh_name": "大牛市",
        "predicate": is_big_bull,
        "pre_registered_definition": {
            "primary_definition": "index/mega-cap led bull market, not necessarily broad-market bull",
            "rolling_value_return_60d": ">=0.08 or rolling_value_return_20d>=0.04",
            "top_sector_value_share": ">=0.60",
            "top_strong_sector_value_share": ">=0.62 or unavailable",
            "avg_rsi": ">=48 or unavailable",
            "breakdown_ratio": "<=0.12 or unavailable",
            "broad_market_shortcut": "BROAD_RISK_ON always qualifies",
            "narrow_leader_secondary_check": "legacy NARROW_LEADER broad/advance/breakout rules remain accepted",
        },
    },
}


def family_map(regimes: pd.DataFrame, requested: list[str]) -> pd.DataFrame:
    frame = regimes.copy()
    for family in requested:
        definition = FAMILY_DEFINITIONS.get(family)
        if definition is None:
            raise ValueError(f"未知 regime family：{family}")
        predicate = definition["predicate"]
        frame[f"family_{family}"] = frame.apply(predicate, axis=1)
    return frame


def labeled_frame(args: argparse.Namespace, requested: list[str]) -> tuple[pd.DataFrame, list[str], pd.DataFrame]:
    data_dir = resolve_path(args.data_dir)
    regime_path = resolve_path(args.market_regime_history)
    if data_dir is None or regime_path is None:
        raise RuntimeError("path resolution failed")
    frame, metadata = load_m4_feature_frame(data_dir=data_dir, project_root=PROJECT_ROOT)
    frame = frame.copy()
    frame["date"] = pd.to_datetime(frame["trade_date"], errors="coerce").dt.normalize()
    frame["stock_id"] = frame["stock_id"].astype(str).str.strip().str.zfill(4)
    generator = LabelGenerator(horizon=args.horizon, threshold=args.threshold)
    labeled = generator.generate_labels(frame)
    labeled = labeled.dropna(subset=["target", "future_return", "entry_price", "exit_price"]).copy()
    labeled["target"] = labeled["target"].astype(int)
    labeled["trade_date"] = pd.to_datetime(labeled["date"], errors="coerce").dt.normalize()
    labeled["trade_date_text"] = labeled["trade_date"].dt.date.astype(str)
    regimes = family_map(regime_rows(regime_path), requested=requested)
    join_cols = ["trade_date_text", "regime_label", *[f"family_{family}" for family in requested]]
    labeled = labeled.merge(regimes[join_cols], on="trade_date_text", how="left")
    labeled["regime_label"] = labeled["regime_label"].fillna("UNKNOWN")
    for family in requested:
        labeled[f"family_{family}"] = labeled[f"family_{family}"].fillna(False).astype(bool)
    features = candidate_feature_columns(labeled, metadata)
    return labeled.sort_values(["trade_date", "stock_id"]).copy(), features, regimes


def fold_windows(family_dates: list[pd.Timestamp], folds: int) -> list[dict[str, Any]]:
    unique_dates = sorted(pd.to_datetime(family_dates).unique())
    if not unique_dates:
        return []
    chunk_size = max(1, math.ceil(len(unique_dates) / max(folds, 1)))
    windows = []
    for index in range(folds):
        dates = unique_dates[index * chunk_size : (index + 1) * chunk_size]
        if len(dates):
            windows.append({"fold": index + 1, "validation_dates": list(dates)})
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


def sample_weights(train: pd.DataFrame, family: str, variant: str, family_weight: float) -> pd.Series | None:
    if variant != "family_weighted_training":
        return None
    mask = train[f"family_{family}"].astype(bool)
    return pd.Series(1.0, index=train.index).mask(mask, family_weight)


def training_frame(frame: pd.DataFrame, family: str, train_dates: list[pd.Timestamp], variant: str) -> pd.DataFrame:
    train = frame[frame["trade_date"].isin(train_dates)].copy()
    if variant == "family_only_training":
        train = train[train[f"family_{family}"]].copy()
    return train


def run_variant(
    frame: pd.DataFrame,
    features: list[str],
    family: str,
    windows: list[dict[str, Any]],
    embargo: int,
    variant: str,
    num_boost_round: int,
    top_n: int,
    family_weight: float,
) -> dict[str, Any]:
    if not windows:
        return {"status": "SKIPPED", "reason": "no family validation windows", "folds": []}
    all_dates = sorted(frame["trade_date"].drop_duplicates().tolist())
    folds = []
    predictions = []
    for window in windows:
        validation_dates = window["validation_dates"]
        train_dates = train_dates_for_fold(all_dates, validation_dates, embargo=embargo)
        train = training_frame(frame, family, train_dates, variant)
        valid = frame[frame["trade_date"].isin(validation_dates) & frame[f"family_{family}"]].copy()
        if train.empty or valid.empty or train["target"].nunique() < 2 or valid["target"].nunique() < 2:
            folds.append({"fold": window["fold"], "status": "SKIPPED", "reason": "insufficient classes or rows"})
            continue
        weights = sample_weights(train, family, variant, family_weight)
        model = lgb.train(
            model_params(),
            lgb.Dataset(train[features], label=train["target"], weight=weights, feature_name=features),
            num_boost_round=num_boost_round,
        )
        valid["pred_prob"] = model.predict(valid[features])
        y_valid = valid["target"].astype(int)
        folds.append(
            {
                "fold": window["fold"],
                "status": "OK",
                "train_rows": int(len(train)),
                "validation_rows": int(len(valid)),
                "train_start": str(pd.to_datetime(min(train_dates)).date()) if train_dates else None,
                "train_end": str(pd.to_datetime(max(train_dates)).date()) if train_dates else None,
                "validation_start": str(pd.to_datetime(min(validation_dates)).date()),
                "validation_end": str(pd.to_datetime(max(validation_dates)).date()),
                "auc": safe_auc(y_valid, valid["pred_prob"]),
                "logloss": safe_logloss(y_valid, valid["pred_prob"]),
                "topn_proxy": topn_proxy(valid, top_n),
            }
        )
        predictions.append(valid[["trade_date_text", "stock_id", "target", "future_return", "pred_prob"]])
    prediction_frame = pd.concat(predictions, ignore_index=True) if predictions else pd.DataFrame()
    ok_folds = [row for row in folds if row.get("status") == "OK"]
    auc_values = [row["auc"] for row in ok_folds if row.get("auc") is not None]
    logloss_values = [row["logloss"] for row in ok_folds if row.get("logloss") is not None]
    return {
        "status": "OK" if ok_folds else "SKIPPED",
        "feature_count": len(features),
        "fold_count": len(ok_folds),
        "avg_auc": round(float(pd.Series(auc_values).mean()), 6) if auc_values else None,
        "avg_logloss": round(float(pd.Series(logloss_values).mean()), 6) if logloss_values else None,
        "topn_proxy": topn_proxy(prediction_frame, top_n) if not prediction_frame.empty else {},
        "folds": folds,
    }


def delta(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return round(left - right, 6)


def decision_for_family(family_result: dict[str, Any]) -> dict[str, Any]:
    baseline = family_result["variants"].get("global_baseline", {})
    candidate_name, candidate = select_candidate_variant(family_result)
    candidate_topn = candidate.get("topn_proxy", {}) if isinstance(candidate.get("topn_proxy"), dict) else {}
    baseline_topn = baseline.get("topn_proxy", {}) if isinstance(baseline.get("topn_proxy"), dict) else {}
    candidate_uplift = candidate_topn.get("topn_minus_universe_return")
    baseline_return = baseline_topn.get("avg_topn_future_return")
    candidate_return = candidate_topn.get("avg_topn_future_return")
    auc_delta = delta(candidate.get("avg_auc"), baseline.get("avg_auc"))
    topn_delta = delta(candidate_return, baseline_return)
    failures = []
    if int(family_result.get("family_date_count") or 0) < MIN_DATES_PER_FAMILY:
        failures.append(f"family_dates<{MIN_DATES_PER_FAMILY}")
    if int(candidate.get("fold_count") or 0) < MIN_OK_FOLDS:
        failures.append(f"ok_folds<{MIN_OK_FOLDS}")
    if candidate.get("avg_auc") is None or float(candidate.get("avg_auc")) < MIN_AUC:
        failures.append(f"candidate_auc<{MIN_AUC}")
    if candidate_uplift is None or float(candidate_uplift) <= MIN_TOPN_UPLIFT:
        failures.append("candidate_topn_uplift<=0")
    if auc_delta is None or auc_delta < MIN_DELTA_AUC:
        failures.append(f"candidate_auc_delta<{MIN_DELTA_AUC}")
    if topn_delta is None or topn_delta < MIN_DELTA_TOPN_RETURN:
        failures.append(f"candidate_topn_return_delta<{MIN_DELTA_TOPN_RETURN}")

    if failures:
        decision = DECISION_MONITOR if candidate.get("status") == "OK" else DECISION_REJECTED
        rationale = "尚未達訓練候選 gate：" + ", ".join(failures)
    else:
        decision = DECISION_PROMOTE
        rationale = "regime-specific 訓練候選相對全市場基準通過預註冊 gate；可進下一階段 sealed/replay。"
    return {
        "decision": decision,
        "decision_rationale": rationale,
        "selected_candidate_variant": candidate_name,
        "diagnostics": {
            "candidate_auc_delta_vs_global": auc_delta,
            "candidate_topn_return_delta_vs_global": topn_delta,
            "candidate_topn_uplift": candidate_uplift,
        },
    }


def select_candidate_variant(family_result: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """在預註冊候選中選相對 global baseline 最好的訓練法。"""

    baseline = family_result["variants"].get("global_baseline", {})
    baseline_topn = baseline.get("topn_proxy", {}) if isinstance(baseline.get("topn_proxy"), dict) else {}
    baseline_return = baseline_topn.get("avg_topn_future_return")
    candidates = []
    for name in ["family_only_training", "family_weighted_training"]:
        item = family_result["variants"].get(name, {})
        topn = item.get("topn_proxy", {}) if isinstance(item.get("topn_proxy"), dict) else {}
        candidates.append(
            {
                "name": name,
                "item": item,
                "status_ok": item.get("status") == "OK",
                "topn_delta": delta(topn.get("avg_topn_future_return"), baseline_return),
                "auc_delta": delta(item.get("avg_auc"), baseline.get("avg_auc")),
                "uplift": topn.get("topn_minus_universe_return"),
                "fold_count": int(item.get("fold_count") or 0),
            }
        )
    ok_candidates = [row for row in candidates if row["status_ok"]]
    if not ok_candidates:
        return "family_only_training", family_result["variants"].get("family_only_training", {})
    best = max(
        ok_candidates,
        key=lambda row: (
            row["topn_delta"] if row["topn_delta"] is not None else -999,
            row["auc_delta"] if row["auc_delta"] is not None else -999,
            row["uplift"] if row["uplift"] is not None else -999,
            row["fold_count"],
        ),
    )
    return str(best["name"]), best["item"]


def build_family_result(
    frame: pd.DataFrame,
    features: list[str],
    regimes: pd.DataFrame,
    family: str,
    args: argparse.Namespace,
) -> dict[str, Any]:
    family_col = f"family_{family}"
    family_dates = sorted(frame.loc[frame[family_col], "trade_date"].drop_duplicates().tolist())
    windows = fold_windows(family_dates, args.folds)
    variants = {
        variant: run_variant(
            frame=frame,
            features=features,
            family=family,
            windows=windows,
            embargo=args.embargo_trade_days,
            variant=variant,
            num_boost_round=args.num_boost_round,
            top_n=args.top_n,
            family_weight=args.family_weight,
        )
        for variant in ["global_baseline", "family_only_training", "family_weighted_training"]
    }
    family_rows = regimes[regimes[family_col]].copy()
    result = {
        "family": family,
        "zh_name": FAMILY_DEFINITIONS[family]["zh_name"],
        "pre_registered_definition": FAMILY_DEFINITIONS[family]["pre_registered_definition"],
        "family_date_count": int(len(family_dates)),
        "family_dates": [str(pd.to_datetime(value).date()) for value in family_dates],
        "regime_label_counts": {str(k): int(v) for k, v in family_rows["regime_label"].value_counts().to_dict().items()},
        "variants": variants,
    }
    result.update(decision_for_family(result))
    return result


def family_overlap_summary(families: list[dict[str, Any]]) -> dict[str, Any]:
    """記錄 family tag 重疊狀況，避免誤把 tag 當互斥 regime。"""

    by_family = {item["family"]: set(item.get("family_dates", [])) for item in families}
    pairs = []
    family_names = sorted(by_family)
    for index, left in enumerate(family_names):
        for right in family_names[index + 1 :]:
            overlap = sorted(by_family[left] & by_family[right])
            left_count = len(by_family[left])
            right_count = len(by_family[right])
            pairs.append(
                {
                    "left": left,
                    "right": right,
                    "overlap_count": len(overlap),
                    "left_count": left_count,
                    "right_count": right_count,
                    "overlap_ratio_of_left": round(len(overlap) / left_count, 6) if left_count else None,
                    "overlap_ratio_of_right": round(len(overlap) / right_count, 6) if right_count else None,
                    "overlap_dates": overlap,
                }
            )
    return {
        "family_tags_are_not_mutually_exclusive": True,
        "pairs": pairs,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    requested = [item.strip().upper() for item in args.families.split(",") if item.strip()]
    unknown = sorted(set(requested) - set(REGIME_FAMILY_TAGS))
    if unknown:
        raise ValueError(f"未知 regime family tag：{unknown}；允許清單={REGIME_FAMILY_TAGS}")
    frame, features, regimes = labeled_frame(args, requested)
    families = [build_family_result(frame, features, regimes, family, args) for family in requested]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK",
        "research_question": RESEARCH_QUESTION,
        "layer": RESEARCH_LAYER,
        "pre_registered": True,
        "decision": DECISION_MONITOR,
        "decision_rationale": "本 artifact 只選出 regime training candidate；正式 promotion 仍需 sealed OOS/replay/no-hindsight gate。",
        "decision_policy": {
            "family_min_dates": MIN_DATES_PER_FAMILY,
            "candidate_min_ok_folds": MIN_OK_FOLDS,
            "candidate_min_auc": MIN_AUC,
            "candidate_min_topn_uplift": MIN_TOPN_UPLIFT,
            "candidate_min_auc_delta_vs_global": MIN_DELTA_AUC,
            "candidate_min_topn_return_delta_vs_global": MIN_DELTA_TOPN_RETURN,
        },
        "diagnostics_not_for_promotion": [
            "family_dates",
            "regime_label_counts",
            "family_only_training",
            "family_weighted_training",
            "fold_breakdown",
        ],
        "contract": {
            "research_only": True,
            "in_memory_models_only": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_risk_adjusted_score": True,
            "does_not_change_production_ranking": True,
            "production_promotion_allowed": False,
            "taxonomy": {
                "base_regime_labels": BASE_REGIME_LABELS,
                "base_regime_mutually_exclusive": True,
                "regime_family_tags": REGIME_FAMILY_TAGS,
                "requested_family_tags": requested,
                "family_tags_are_not_base_regimes": True,
                "family_tags_are_not_mutually_exclusive": True,
                "do_not_add_family_tag_without_contract_change": True,
            },
            "split_policy": "chronological family validation with embargo",
            "no_hindsight_policy": {
                "validation_windows_are_chronological": True,
                "train_dates_end_before_validation_start": True,
                "embargo_trade_days": args.embargo_trade_days,
                "family_definitions_pre_registered": True,
                "diagnostic_failures_cannot_define_same_run_filters": True,
                "new_filters_require_next_walkforward_run": True,
                "promotion_requires_separate_sealed_replay": True,
            },
        },
        "inputs": {
            "data_dir": repo_path(resolve_path(args.data_dir)),
            "market_regime_history": repo_path(resolve_path(args.market_regime_history)),
            "families": requested,
            "horizon": args.horizon,
            "threshold": args.threshold,
            "folds": args.folds,
            "embargo_trade_days": args.embargo_trade_days,
            "top_n": args.top_n,
            "num_boost_round": args.num_boost_round,
            "family_weight": args.family_weight,
        },
        "summary": {
            "rows": int(len(frame)),
            "stocks": int(frame["stock_id"].nunique()),
            "dates": int(frame["trade_date"].nunique()),
            "feature_count": len(features),
            "families": {
                item["family"]: {
                    "decision": item["decision"],
                    "family_date_count": item["family_date_count"],
                    "selected_candidate_variant": item["selected_candidate_variant"],
                    "candidate_auc_delta_vs_global": item["diagnostics"]["candidate_auc_delta_vs_global"],
                    "candidate_topn_return_delta_vs_global": item["diagnostics"]["candidate_topn_return_delta_vs_global"],
                    "candidate_topn_uplift": item["diagnostics"]["candidate_topn_uplift"],
                }
                for item in families
            },
            "family_overlap": family_overlap_summary(families),
        },
        "families": families,
    }


def md_cell(value: Any) -> str:
    return str(value).replace("\n", " ").replace("|", "\\|")


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Regime Family Training Candidates",
        "",
        f"- status：`{payload['status']}`",
        f"- research_question：`{payload['research_question']}`",
        f"- layer：`{payload['layer']}`",
        f"- pre_registered：`{payload['pre_registered']}`",
        f"- decision：`{payload['decision']}`",
        f"- decision_rationale：{payload['decision_rationale']}",
        "",
        "| Family | Name | Days | Decision | Selected | AUC Δ | TopN Return Δ | Candidate Uplift |",
        "|---|---|---:|---|---|---:|---:|---:|",
    ]
    for item in payload["families"]:
        diag = item["diagnostics"]
        lines.append(
            "| {family} | {name} | {days} | {decision} | {selected} | {auc_delta} | {topn_delta} | {uplift} |".format(
                family=item["family"],
                name=item["zh_name"],
                days=item["family_date_count"],
                decision=item["decision"],
                selected=item["selected_candidate_variant"],
                auc_delta=diag.get("candidate_auc_delta_vs_global"),
                topn_delta=diag.get("candidate_topn_return_delta_vs_global"),
                uplift=diag.get("candidate_topn_uplift"),
            )
        )
    for item in payload["families"]:
        lines.extend(
            [
                "",
                f"## {item['family']} {item['zh_name']}",
                "",
                f"- rationale：{item['decision_rationale']}",
                f"- regime_label_counts：`{item['regime_label_counts']}`",
                "",
                "| Variant | Folds | AUC | TopN Return | Universe Return | Uplift |",
                "|---|---:|---:|---:|---:|---:|",
            ]
        )
        for variant_name, variant in item["variants"].items():
            topn = variant.get("topn_proxy", {})
            lines.append(
                "| {variant} | {folds} | {auc} | {ret} | {universe} | {uplift} |".format(
                    variant=variant_name,
                    folds=variant.get("fold_count"),
                    auc=variant.get("avg_auc"),
                    ret=topn.get("avg_topn_future_return"),
                    universe=topn.get("avg_universe_future_return"),
                    uplift=topn.get("topn_minus_universe_return"),
                )
            )
        lines.extend(["", "| Fold | Variant | Validation | AUC | Uplift |", "|---:|---|---|---:|---:|"])
        for variant_name, variant in item["variants"].items():
            for fold in variant.get("folds", []):
                topn = fold.get("topn_proxy", {})
                lines.append(
                    "| {fold} | {variant} | {start}~{end} | {auc} | {uplift} |".format(
                        fold=fold.get("fold"),
                        variant=variant_name,
                        start=fold.get("validation_start"),
                        end=fold.get("validation_end"),
                        auc=fold.get("auc"),
                        uplift=topn.get("topn_minus_universe_return"),
                    )
                )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = resolve_path(args.output) or OUTPUT_DIR / f"regime_family_training_candidates_{args.date}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "output": repo_path(output),
                "families": payload["summary"]["families"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
