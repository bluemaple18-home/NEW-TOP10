#!/usr/bin/env python3
"""用 prior-only materialized persistence features 做離線消融研究。

此腳本只讀 replay 輸入與 candidate_persistence_features parquet。
它不訓練模型、不覆蓋正式模型、不修改 production ranking。
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

from scripts import run_backtest_replay  # noqa: E402


OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "model_experiments"
SCHEMA_VERSION = "candidate-persistence-materialized-ablation.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="research candidate persistence materialized feature ablation")
    parser.add_argument("--rankings-dir", default="artifacts/backtest/historical_rankings_current_model")
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument("--materialized", default=None)
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--horizons", default="1,3,5,10")
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--max-ranking-files", type=int, default=None)
    parser.add_argument("--min-trades", type=int, default=20)
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


def repo_paths(values: list[Any]) -> list[str]:
    rows: list[str] = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            continue
        rows.append(repo_path(resolve_path(value)) or value)
    return rows


def default_materialized(run_date: str) -> Path:
    return OUTPUT_DIR / f"candidate_persistence_features_{run_date}.parquet"


def replay_args(args: argparse.Namespace) -> argparse.Namespace:
    return argparse.Namespace(
        rankings_dir=args.rankings_dir,
        features=args.features,
        horizons=args.horizons,
        top_n=args.top_n,
        max_ranking_files=args.max_ranking_files,
        fee_rate=0.001425,
        tax_rate=0.003,
        slippage_rate=0.001,
        max_position_weight=0.2,
        default_gross_exposure=0.65,
        output=None,
    )


def load_materialized(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"materialized persistence artifact 不存在：{path}")
    frame = pd.read_parquet(path)
    required = {"date", "stock_id", "consecutive_ranked_days", "streak_bucket", "rank_delta_direction"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"materialized persistence artifact 缺欄位：{missing}")
    frame = frame.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    frame["stock_id"] = frame["stock_id"].astype(str).str.strip().str.zfill(4)
    return frame


def merge_trades(trades: list[dict[str, Any]], materialized: pd.DataFrame) -> pd.DataFrame:
    frame = pd.DataFrame(trades)
    if frame.empty:
        return frame
    frame["ranking_date"] = pd.to_datetime(frame["ranking_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    frame["stock_id"] = frame["stock_id"].astype(str).str.strip().str.zfill(4)
    joined = frame.merge(
        materialized,
        left_on=["ranking_date", "stock_id"],
        right_on=["date", "stock_id"],
        how="left",
        suffixes=("", "_persistence"),
    )
    joined["consecutive_ranked_days"] = pd.to_numeric(joined["consecutive_ranked_days"], errors="coerce").fillna(0).astype(int)
    joined["ranked_history_count"] = pd.to_numeric(joined.get("ranked_history_count"), errors="coerce").fillna(0).astype(int)
    joined["streak_bucket"] = joined["streak_bucket"].fillna("0")
    joined["rank_delta_direction"] = joined["rank_delta_direction"].fillna("new_or_unknown")
    if "seen_in_previous_ranking" in joined.columns:
        joined["seen_in_previous_ranking"] = joined["seen_in_previous_ranking"].map(lambda value: bool(value) if pd.notna(value) else False)
    else:
        joined["seen_in_previous_ranking"] = False
    joined["net_return"] = pd.to_numeric(joined["net_return"], errors="coerce")
    joined["mae"] = pd.to_numeric(joined["mae"], errors="coerce")
    joined["mfe"] = pd.to_numeric(joined["mfe"], errors="coerce")
    return joined


def metric_summary(group: pd.DataFrame) -> dict[str, Any]:
    returns = pd.to_numeric(group["net_return"], errors="coerce")
    return {
        "trade_count": int(len(group)),
        "avg_net_return": round(float(returns.mean()), 6),
        "median_net_return": round(float(returns.median()), 6),
        "hit_rate": round(float((returns > 0).mean()), 6),
        "avg_mae": round(float(pd.to_numeric(group["mae"], errors="coerce").mean()), 6),
        "avg_mfe": round(float(pd.to_numeric(group["mfe"], errors="coerce").mean()), 6),
    }


def grouped_summary(frame: pd.DataFrame, group_col: str) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for (horizon, bucket), group in frame.groupby(["horizon", group_col], dropna=False):
        rows[f"{int(horizon)}D::{bucket}"] = metric_summary(group)
    return rows


def baselines(frame: pd.DataFrame) -> dict[str, dict[str, Any]]:
    return {f"{int(horizon)}D": metric_summary(group) for horizon, group in frame.groupby("horizon")}


def candidate_buckets(frame: pd.DataFrame, baseline: dict[str, dict[str, Any]], min_trades: int) -> list[dict[str, Any]]:
    rows = []
    for key, item in grouped_summary(frame, "streak_bucket").items():
        horizon = key.split("::", 1)[0]
        base = baseline.get(horizon, {})
        if item["trade_count"] < min_trades:
            continue
        return_delta = round(item["avg_net_return"] - float(base.get("avg_net_return", 0)), 6)
        hit_delta = round(item["hit_rate"] - float(base.get("hit_rate", 0)), 6)
        if return_delta > 0 and hit_delta >= 0:
            rows.append(
                {
                    "group": key,
                    "trade_count": item["trade_count"],
                    "avg_net_return": item["avg_net_return"],
                    "baseline_avg_net_return": base.get("avg_net_return"),
                    "return_delta": return_delta,
                    "hit_rate": item["hit_rate"],
                    "baseline_hit_rate": base.get("hit_rate"),
                    "hit_delta": hit_delta,
                }
            )
    return sorted(rows, key=lambda row: (row["return_delta"], row["trade_count"]), reverse=True)


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    materialized_path = resolve_path(args.materialized) or default_materialized(args.date)
    materialized = load_materialized(materialized_path)
    replay = run_backtest_replay.run_replay(replay_args(args))
    trades = merge_trades(replay.get("trades", []), materialized)
    baseline = baselines(trades)
    candidates = candidate_buckets(trades, baseline=baseline, min_trades=args.min_trades)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK" if len(trades) else "WARN",
        "contract": {
            "research_only": True,
            "uses_prior_only_materialized_features": True,
            "does_not_train_model": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_risk_adjusted_score": True,
            "does_not_change_production_ranking": True,
            "production_promotion_allowed": False,
        },
        "inputs": {
            "rankings_dir": repo_path(resolve_path(args.rankings_dir)),
            "features": repo_path(resolve_path(args.features)),
            "materialized": repo_path(materialized_path),
            "ranking_files": repo_paths(replay.get("inputs", {}).get("ranking_files", [])),
            "horizons": replay.get("inputs", {}).get("horizons", []),
            "top_n": args.top_n,
            "min_trades": args.min_trades,
        },
        "summary": {
            "trade_count": int(len(trades)),
            "baseline_by_horizon": baseline,
            "candidate_bucket_count": len(candidates),
            "candidate_buckets": candidates[:20],
        },
        "by_horizon_and_streak": grouped_summary(trades, "streak_bucket"),
        "by_horizon_and_rank_delta_direction": grouped_summary(trades, "rank_delta_direction"),
        "by_horizon_and_seen_previous": grouped_summary(trades, "seen_in_previous_ranking"),
    }


def pct(value: Any) -> str:
    try:
        return f"{float(value):.2%}"
    except (TypeError, ValueError):
        return "--"


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Candidate Persistence Materialized Ablation",
        "",
        f"- status：`{payload['status']}`",
        f"- trade_count：`{payload['summary']['trade_count']}`",
        f"- candidate_bucket_count：`{payload['summary']['candidate_bucket_count']}`",
        "",
        "## Candidate Buckets",
        "",
        "| Bucket | Trades | Avg Return | Baseline | Delta | Hit | Hit Delta |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for item in payload["summary"]["candidate_buckets"][:12]:
        lines.append(
            "| {group} | {trades} | {avg} | {base} | {delta} | {hit} | {hit_delta} |".format(
                group=item["group"],
                trades=item["trade_count"],
                avg=pct(item["avg_net_return"]),
                base=pct(item["baseline_avg_net_return"]),
                delta=pct(item["return_delta"]),
                hit=pct(item["hit_rate"]),
                hit_delta=pct(item["hit_delta"]),
            )
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = resolve_path(args.output) or OUTPUT_DIR / f"candidate_persistence_materialized_ablation_{args.date}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output), **payload["summary"]}, ensure_ascii=False))
    return 0 if payload["status"] in {"OK", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
