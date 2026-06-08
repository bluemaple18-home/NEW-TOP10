#!/usr/bin/env python3
"""建立 HIGH_CHOPPY rolling-window context / overlay 研究 artifact。

本腳本只產出 research artifact，不訓練模型、不改 production ranking，也不把
HIGH_CHOPPY 升成正式 base regime。rolling 定義會先寫入 artifact，再附上分層
label / replay 診斷，避免用結果倒推條件。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.labels import LabelGenerator  # noqa: E402


SCHEMA_VERSION = "high-choppy-context-overlay.v1"
OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "model_experiments"
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build HIGH_CHOPPY rolling context overlay artifact")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument("--market-regime-history", default="artifacts/market_regime_history_2026-06-01.json")
    parser.add_argument("--ranking-dir", default="artifacts/backtest/shadow_rankings_conservative_setup_extended")
    parser.add_argument("--horizon", type=int, default=10)
    parser.add_argument("--threshold", type=float, default=0.05)
    parser.add_argument("--top-n", type=int, default=10)
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


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def num(value: Any, digits: int = 6) -> float | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(parsed):
        return None
    return round(float(parsed), digits)


def rolling_compound_return(series: pd.Series, window: int, min_periods: int) -> pd.Series:
    return series.fillna(0).rolling(window, min_periods=min_periods).apply(lambda values: float((1 + values).prod() - 1), raw=False)


def load_regime_frame(path: Path) -> pd.DataFrame:
    payload = load_json(path)
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    frame = pd.DataFrame(rows)
    if frame.empty:
        raise ValueError(f"market regime history 無 rows：{path}")
    frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce").dt.normalize()
    frame["trade_date_text"] = frame["trade_date"].dt.date.astype(str)
    numeric_cols = [
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
    ]
    for col in numeric_cols:
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame = frame.sort_values("trade_date").copy()
    frame["rolling_value_return_20d"] = rolling_compound_return(frame["value_weight_return"], 20, 10)
    frame["rolling_value_return_60d"] = rolling_compound_return(frame["value_weight_return"], 60, 30)
    frame["rolling_equal_return_20d"] = rolling_compound_return(frame["equal_weight_return"], 20, 10)
    frame["rolling_equal_return_60d"] = rolling_compound_return(frame["equal_weight_return"], 60, 30)
    frame["rolling_value_volatility_10d"] = frame["value_weight_return"].rolling(10, min_periods=5).std()
    frame["rolling_upper_shadow_10d"] = frame["long_upper_shadow_ratio"].rolling(10, min_periods=5).mean()
    frame["rolling_breakout_10d"] = frame["breakout_ratio"].rolling(10, min_periods=5).mean()
    frame["rolling_breakdown_10d"] = frame["breakdown_ratio"].rolling(10, min_periods=5).mean()
    frame["rolling_top_sector_share_20d"] = frame["top_sector_value_share"].rolling(20, min_periods=10).mean()
    frame["rolling_breadth_ma20_10d"] = frame["breadth_ma20"].rolling(10, min_periods=5).mean()
    frame["rolling_advance_10d"] = frame["advance_ratio"].rolling(10, min_periods=5).mean()
    return frame


def strict_high_choppy(row: pd.Series) -> bool:
    """沿用既有單日 strict HIGH_CHOPPY 定義作為 overlap baseline。"""

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


def rolling_high_choppy(row: pd.Series) -> bool:
    if str(row.get("regime_label") or "") in {"PANIC_SELLING", "UNKNOWN"}:
        return False
    high_condition = any(
        [
            pd.notna(row.get("rolling_value_return_20d")) and float(row["rolling_value_return_20d"]) >= 0.04,
            pd.notna(row.get("rolling_value_return_60d")) and float(row["rolling_value_return_60d"]) >= 0.10,
            pd.notna(row.get("rolling_equal_return_20d")) and float(row["rolling_equal_return_20d"]) >= 0.03,
        ]
    ) and (pd.isna(row.get("value_weight_return")) or float(row["value_weight_return"]) >= -0.025)
    choppy_signals = [
        pd.notna(row.get("rolling_upper_shadow_10d")) and float(row["rolling_upper_shadow_10d"]) >= 0.12,
        pd.notna(row.get("rolling_value_volatility_10d")) and float(row["rolling_value_volatility_10d"]) >= 0.016,
        pd.notna(row.get("rolling_breakdown_10d")) and float(row["rolling_breakdown_10d"]) >= 0.06,
        pd.notna(row.get("rolling_breakout_10d")) and float(row["rolling_breakout_10d"]) <= 0.035,
    ]
    choppy_condition = sum(bool(item) for item in choppy_signals) >= 2
    concentrated = pd.notna(row.get("rolling_top_sector_share_20d")) and float(row["rolling_top_sector_share_20d"]) >= 0.66
    not_broad = (
        pd.notna(row.get("rolling_breadth_ma20_10d"))
        and 0.24 <= float(row["rolling_breadth_ma20_10d"]) <= 0.56
        and (pd.isna(row.get("rolling_advance_10d")) or float(row["rolling_advance_10d"]) <= 0.62)
    )
    return bool(high_condition and choppy_condition and concentrated and not_broad)


def context_definition() -> dict[str, Any]:
    return {
        "pre_registered_before_evaluation": True,
        "context_type": "rolling_window_regime_family_context",
        "high_condition": "rolling_value_return_20d>=4% OR rolling_value_return_60d>=10% OR rolling_equal_return_20d>=3%; current value return must not be below -2.5%",
        "choppy_condition": "at least two of: rolling_upper_shadow_10d>=12%, rolling_value_volatility_10d>=1.6%, rolling_breakdown_10d>=6%, rolling_breakout_10d<=3.5%",
        "concentration_condition": "rolling_top_sector_value_share_20d>=66%",
        "breadth_condition": "24%<=rolling_breadth_ma20_10d<=56% and rolling_advance_10d<=62% when available",
        "excluded_base_regimes": ["PANIC_SELLING", "UNKNOWN"],
        "formal_base_regime_created": False,
        "family_tag_created": False,
    }


def date_list(frame: pd.DataFrame, mask_col: str) -> list[str]:
    return frame.loc[frame[mask_col], "trade_date_text"].dropna().astype(str).tolist()


def count_by_regime(frame: pd.DataFrame, dates: set[str]) -> dict[str, int]:
    if not dates:
        return {}
    counts = frame.loc[frame["trade_date_text"].isin(dates), "regime_label"].value_counts().to_dict()
    return {str(key): int(value) for key, value in counts.items()}


def load_labeled_features(path: Path, horizon: int, threshold: float) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    frame = frame.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["stock_id"] = frame["stock_id"].astype(str).str.strip().str.zfill(4)
    labeled = LabelGenerator(horizon=horizon, threshold=threshold).generate_labels(frame)
    labeled["trade_date_text"] = pd.to_datetime(labeled["date"], errors="coerce").dt.date.astype(str)
    return labeled.dropna(subset=["target", "future_return"])[["trade_date_text", "stock_id", "target", "future_return"]].copy()


def label_summary(labeled: pd.DataFrame, dates: set[str]) -> dict[str, Any]:
    subset = labeled[labeled["trade_date_text"].isin(dates)].copy()
    if subset.empty:
        return {"date_count": 0, "row_count": 0}
    by_date = subset.groupby("trade_date_text").agg(
        avg_future_return=("future_return", "mean"),
        positive_label_rate=("target", "mean"),
        rows=("stock_id", "count"),
    )
    return {
        "date_count": int(by_date.shape[0]),
        "row_count": int(subset.shape[0]),
        "avg_future_return": num(by_date["avg_future_return"].mean()),
        "positive_label_rate": num(by_date["positive_label_rate"].mean()),
        "median_daily_rows": num(by_date["rows"].median(), digits=2),
    }


def top10_replay_summary(ranking_dir: Path, labeled: pd.DataFrame, dates: set[str], top_n: int) -> dict[str, Any]:
    if not ranking_dir.exists() or not dates:
        return {"date_count": 0, "trade_count": 0, "ranking_dir_exists": ranking_dir.exists()}
    rows = []
    label_key = labeled.set_index(["trade_date_text", "stock_id"])
    for date_text in sorted(dates):
        ranking_path = ranking_dir / f"ranking_{date_text}.csv"
        if not ranking_path.exists():
            continue
        ranking = pd.read_csv(ranking_path, dtype={"stock_id": str}).head(top_n).copy()
        ranking["stock_id"] = ranking["stock_id"].astype(str).str.strip().str.zfill(4)
        keys = [(date_text, stock_id) for stock_id in ranking["stock_id"]]
        matched = label_key.reindex(pd.MultiIndex.from_tuples(keys, names=["trade_date_text", "stock_id"])).dropna()
        if matched.empty:
            continue
        future_return = pd.to_numeric(matched["future_return"], errors="coerce")
        target = pd.to_numeric(matched["target"], errors="coerce")
        universe = labeled[labeled["trade_date_text"] == date_text]
        rows.append(
            {
                "trade_date": date_text,
                "top10_avg_future_return": float(future_return.mean()),
                "top10_hit_rate": float(target.mean()),
                "universe_avg_future_return": float(pd.to_numeric(universe["future_return"], errors="coerce").mean()),
                "trade_count": int(len(matched)),
            }
        )
    result = pd.DataFrame(rows)
    if result.empty:
        return {"date_count": 0, "trade_count": 0, "ranking_dir_exists": True}
    return {
        "date_count": int(len(result)),
        "trade_count": int(result["trade_count"].sum()),
        "avg_top10_future_return": num(result["top10_avg_future_return"].mean()),
        "avg_universe_future_return": num(result["universe_avg_future_return"].mean()),
        "top10_minus_universe_return": num((result["top10_avg_future_return"] - result["universe_avg_future_return"]).mean()),
        "avg_top10_hit_rate": num(result["top10_hit_rate"].mean()),
        "covered_dates": result["trade_date"].tolist(),
    }


def usage_status(rolling_count: int, replay: dict[str, Any]) -> dict[str, dict[str, str]]:
    soft_allowed = rolling_count >= 18
    replay_delta = replay.get("top10_minus_universe_return")
    overlay_allowed = (
        rolling_count >= 18
        and int(replay.get("date_count") or 0) >= 3
        and replay_delta is not None
        and float(replay_delta) > 0
    )
    strat_allowed = rolling_count > 0
    return {
        "soft_feature": {
            "status": "ALLOWED" if soft_allowed else "BLOCKED",
            "reason": "rolling context has enough dates for a soft candidate" if soft_allowed else "sample size remains monitor-only",
        },
        "stratified_evaluation": {
            "status": "ALLOWED" if strat_allowed else "BLOCKED",
            "reason": "diagnostic slicing only; not promotion evidence" if strat_allowed else "no rolling context dates",
        },
        "ranking_overlay": {
            "status": "ALLOWED" if overlay_allowed else "BLOCKED",
            "reason": "enough rolling dates and positive Top10 replay spread for ranking/risk overlay candidate"
            if overlay_allowed
            else "requires enough replay coverage and positive Top10-vs-universe spread before overlay candidate",
        },
        "promotion_evidence": {
            "status": "BLOCKED",
            "reason": "HIGH_CHOPPY context artifact is research-only and cannot promote production models/ranking",
        },
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    regime_path = resolve_path(args.market_regime_history)
    features_path = resolve_path(args.features)
    ranking_dir = resolve_path(args.ranking_dir)
    if regime_path is None or features_path is None or ranking_dir is None:
        raise RuntimeError("path resolution failed")
    regimes = load_regime_frame(regime_path)
    regimes["strict_high_choppy"] = regimes.apply(strict_high_choppy, axis=1)
    regimes["rolling_high_choppy"] = regimes.apply(rolling_high_choppy, axis=1)
    strict_dates = set(date_list(regimes, "strict_high_choppy"))
    rolling_dates = set(date_list(regimes, "rolling_high_choppy"))
    new_dates = rolling_dates - strict_dates
    overlap_dates = strict_dates & rolling_dates
    labeled = load_labeled_features(features_path, args.horizon, args.threshold)
    new_top10 = top10_replay_summary(ranking_dir, labeled, new_dates, args.top_n)
    allowed = usage_status(len(rolling_dates), new_top10)
    decision = "MONITOR_ONLY"
    if allowed["ranking_overlay"]["status"] == "ALLOWED":
        decision = "RANKING_OVERLAY_CANDIDATE"
    elif allowed["soft_feature"]["status"] == "ALLOWED":
        decision = "SOFT_FEATURE_CANDIDATE"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK",
        "decision": decision,
        "decision_rationale": "HIGH_CHOPPY 以 rolling-window context 進入研究；不得訓練專屬正式模型，也不阻塞主訓練。",
        "context_definition": context_definition(),
        "contract": {
            "research_only": True,
            "trains_model": False,
            "does_not_train_family_specific_model": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_risk_adjusted_score": True,
            "does_not_change_production_ranking": True,
            "does_not_add_formal_base_regime": True,
            "blocks_main_training": False,
            "production_promotion_allowed": False,
            "taxonomy": {
                "base_regime_labels": BASE_REGIME_LABELS,
                "base_regime_mutually_exclusive": True,
                "context_family": "HIGH_CHOPPY",
                "family_tags_are_not_base_regimes": True,
            },
        },
        "inputs": {
            "features": repo_path(features_path),
            "market_regime_history": repo_path(regime_path),
            "ranking_dir": repo_path(ranking_dir),
            "horizon": args.horizon,
            "threshold": args.threshold,
            "top_n": args.top_n,
        },
        "summary": {
            "strict_dates": len(strict_dates),
            "rolling_context_dates": len(rolling_dates),
            "new_dates": len(new_dates),
            "overlap_count": len(overlap_dates),
            "overlap_ratio_of_strict": num(len(overlap_dates) / len(strict_dates)) if strict_dates else None,
            "overlap_ratio_of_rolling": num(len(overlap_dates) / len(rolling_dates)) if rolling_dates else None,
            "new_dates_base_regime_distribution": count_by_regime(regimes, new_dates),
            "rolling_context_base_regime_distribution": count_by_regime(regimes, rolling_dates),
            "strict_label_quality": label_summary(labeled, strict_dates),
            "rolling_label_quality": label_summary(labeled, rolling_dates),
            "new_dates_quality": label_summary(labeled, new_dates),
            "new_dates_top10_replay": new_top10,
            "usage_allowed": allowed,
            "blocks_main_training": False,
        },
        "dates": {
            "strict": sorted(strict_dates),
            "rolling_context": sorted(rolling_dates),
            "new": sorted(new_dates),
            "overlap": sorted(overlap_dates),
        },
    }


def md_status(row: dict[str, str]) -> str:
    return f"`{row.get('status')}` - {row.get('reason')}"


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    allowed = summary["usage_allowed"]
    replay = summary["new_dates_top10_replay"]
    return "\n".join(
        [
            "# HIGH_CHOPPY Context Overlay",
            "",
            f"- status：`{payload['status']}`",
            f"- decision：`{payload['decision']}`",
            f"- strict_dates：`{summary['strict_dates']}`",
            f"- rolling_context_dates：`{summary['rolling_context_dates']}`",
            f"- new_dates：`{summary['new_dates']}`",
            f"- blocks_main_training：`{summary['blocks_main_training']}`",
            f"- soft_feature：{md_status(allowed['soft_feature'])}",
            f"- stratified_evaluation：{md_status(allowed['stratified_evaluation'])}",
            f"- ranking_overlay：{md_status(allowed['ranking_overlay'])}",
            f"- promotion_evidence：{md_status(allowed['promotion_evidence'])}",
            "",
            "## New Dates Quality",
            "",
            f"- base_regime_distribution：`{summary['new_dates_base_regime_distribution']}`",
            f"- label_quality：`{summary['new_dates_quality']}`",
            f"- top10_replay：`{replay}`",
            "",
        ]
    )


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = resolve_path(args.output) or OUTPUT_DIR / f"high_choppy_context_overlay_{args.date}.json"
    if output is None:
        raise RuntimeError("output path resolution failed")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "output": repo_path(output),
                "decision": payload["decision"],
                "strict_dates": payload["summary"]["strict_dates"],
                "rolling_context_dates": payload["summary"]["rolling_context_dates"],
                "blocks_main_training": False,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
