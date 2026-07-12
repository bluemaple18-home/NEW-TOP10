#!/usr/bin/env python3
"""VWAP entry-quality overlay replay。

讀既有 ranking CSV 與正式 features.parquet，比較 baseline TopN 與 VWAP 追價風險
overlay 的 D+1 open 進、D+H close 出結果。不訓練模型、不改 production ranking。
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import run_backtest_replay


SCHEMA_VERSION = "vwap-entry-quality-replay.v1"
VWAP_FEATURES = ["close_vs_vwap_5d", "close_vs_vwap_20d", "vwap_reclaim_20d", "vwap_loss_20d"]
POLICIES = {
    "baseline": {"description": "原始 TopN，不套 VWAP overlay。"},
    "avoid_extended_vwap_5d": {"max_close_vs_vwap_5d": 0.08, "hard_filter": True},
    "avoid_extended_vwap_20d": {"max_close_vs_vwap_20d": 0.12, "hard_filter": True},
    "strict_avoid_extended_vwap": {"max_close_vs_vwap_5d": 0.03, "max_close_vs_vwap_20d": 0.06, "hard_filter": True},
    "lowest_vwap_distance_5d": {"rank_by_low_distance": "close_vs_vwap_5d"},
    "lowest_vwap_distance_20d": {"rank_by_low_distance": "close_vs_vwap_20d"},
    "lowest_combined_vwap_distance": {"rank_by_low_distance": "combined"},
    "prefer_reclaim_avoid_loss": {"bonus_reclaim": 0.08, "penalty_loss": 0.12},
    "balanced_cost_basis": {"max_close_vs_vwap_5d": 0.10, "max_close_vs_vwap_20d": 0.15, "penalty_loss": 0.08, "hard_filter": True},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="research VWAP entry quality overlay replay")
    parser.add_argument("--rankings-dir", default="artifacts/backtest/historical_rankings_current_model_half_year_dense_2025-11-17_2026-05-15")
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--horizons", default="3,5,10")
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--candidate-pool", type=int, default=20)
    parser.add_argument("--entry-delay-trade-days", type=int, default=1)
    parser.add_argument("--fee-rate", type=float, default=0.001425)
    parser.add_argument("--tax-rate", type=float, default=0.003)
    parser.add_argument("--slippage-rate", type=float, default=0.001)
    parser.add_argument("--market-regime-history", default="artifacts/market_regime_history_2026-06-01.json")
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


def parse_horizons(value: str) -> list[int]:
    horizons = sorted({int(item.strip()) for item in value.split(",") if item.strip()})
    if not horizons:
        raise ValueError("--horizons 不可為空")
    return horizons


def ranking_files(rankings_dir: Path) -> list[Path]:
    files = run_backtest_replay.ranking_files(rankings_dir, None)
    if not files:
        raise FileNotFoundError(f"找不到 ranking_*.csv：{rankings_dir}")
    return files


def read_ranking(path: Path, pool_size: int) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    result = []
    for rank, row in enumerate(rows[:pool_size], start=1):
        result.append(
            {
                "rank": rank,
                "stock_id": str(row.get("stock_id", "")).strip().zfill(4),
                "stock_name": row.get("stock_name"),
                "risk_adjusted_score": parse_float(row.get("risk_adjusted_score")),
                "model_prob": parse_float(row.get("model_prob")),
            }
        )
    return result


def parse_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(parsed) else parsed


def load_feature_lookup(path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    columns = ["date", "stock_id", "close", *VWAP_FEATURES]
    frame = pd.read_parquet(path, columns=columns)
    frame["date_text"] = pd.to_datetime(frame["date"], errors="coerce").dt.date.astype(str)
    frame["stock_id"] = frame["stock_id"].astype(str).str.zfill(4)
    return {
        (row.date_text, row.stock_id): {
            "close": row.close,
            "close_vs_vwap_5d": row.close_vs_vwap_5d,
            "close_vs_vwap_20d": row.close_vs_vwap_20d,
            "vwap_reclaim_20d": row.vwap_reclaim_20d,
            "vwap_loss_20d": row.vwap_loss_20d,
        }
        for row in frame.itertuples(index=False)
    }


def load_regime_map(path: Path | None) -> dict[str, str]:
    if path is None or not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    result = {}
    for row in payload.get("rows", []):
        trade_date = str(row.get("trade_date") or "").strip()
        label = str(row.get("regime_label") or "").strip()
        if trade_date and label:
            result[trade_date] = label
    return result


def score_item(item: dict[str, Any], features: dict[str, Any] | None, policy: dict[str, Any]) -> tuple[float, str]:
    base = float(item.get("risk_adjusted_score") or item.get("model_prob") or 0.0)
    if not features:
        return base - 999.0, "missing_features"
    score = base
    reasons = []
    close_vs_5d = parse_float(features.get("close_vs_vwap_5d"))
    close_vs_20d = parse_float(features.get("close_vs_vwap_20d"))
    reclaim = parse_float(features.get("vwap_reclaim_20d")) or 0.0
    loss = parse_float(features.get("vwap_loss_20d")) or 0.0
    rank_by = policy.get("rank_by_low_distance")
    if rank_by == "close_vs_vwap_5d":
        return -(close_vs_5d if close_vs_5d is not None else 999.0), "low_distance_5d"
    if rank_by == "close_vs_vwap_20d":
        return -(close_vs_20d if close_vs_20d is not None else 999.0), "low_distance_20d"
    if rank_by == "combined":
        distance_5d = close_vs_5d if close_vs_5d is not None else 999.0
        distance_20d = close_vs_20d if close_vs_20d is not None else 999.0
        return -((distance_5d + distance_20d) / 2), "low_distance_combined"
    max_5d = policy.get("max_close_vs_vwap_5d")
    max_20d = policy.get("max_close_vs_vwap_20d")
    if max_5d is not None and close_vs_5d is not None and close_vs_5d > float(max_5d):
        if policy.get("hard_filter"):
            score = -999.0
        else:
            score -= 1.0 + (close_vs_5d - float(max_5d))
        reasons.append("extended_5d")
    if max_20d is not None and close_vs_20d is not None and close_vs_20d > float(max_20d):
        if policy.get("hard_filter"):
            score = -999.0
        else:
            score -= 1.0 + (close_vs_20d - float(max_20d))
        reasons.append("extended_20d")
    score += float(policy.get("bonus_reclaim") or 0.0) * reclaim
    score -= float(policy.get("penalty_loss") or 0.0) * loss
    if reclaim:
        reasons.append("reclaim")
    if loss:
        reasons.append("loss")
    return score, ",".join(reasons)


def select_policy_items(
    ranking: list[dict[str, Any]],
    feature_lookup: dict[tuple[str, str], dict[str, Any]],
    date_text: str,
    policy_name: str,
    top_n: int,
) -> list[dict[str, Any]]:
    if policy_name == "baseline":
        return ranking[:top_n]
    policy = POLICIES[policy_name]
    scored = []
    for item in ranking:
        features = feature_lookup.get((date_text, item["stock_id"]))
        overlay_score, reason = score_item(item, features, policy)
        scored.append({**item, "overlay_score": overlay_score, "overlay_reason": reason})
    return sorted(scored, key=lambda row: row["overlay_score"], reverse=True)[:top_n]


def simulate_stock(
    price_index: dict[str, pd.DataFrame],
    trade_dates: list[Any],
    ranking_date_text: str,
    stock_id: str,
    horizon: int,
    args: argparse.Namespace,
) -> dict[str, Any] | None:
    stock_prices = price_index.get(str(stock_id).zfill(4))
    if stock_prices is None:
        return None
    entry_date = run_backtest_replay.next_market_trade_date(trade_dates, ranking_date_text, args.entry_delay_trade_days)
    if entry_date is None:
        return None
    holding_dates = run_backtest_replay.market_holding_dates(trade_dates, entry_date, horizon)
    if holding_dates is None:
        return None
    holding = run_backtest_replay.stock_holding_bars(stock_prices, holding_dates)
    if holding is None or run_backtest_replay.has_missing_ohlc(holding):
        return None
    return run_backtest_replay.simulate_trade(
        holding=holding,
        fee_rate=args.fee_rate,
        tax_rate=args.tax_rate,
        slippage_rate=args.slippage_rate,
    )


def simulate_bucket(
    items: list[dict[str, Any]],
    price_index: dict[str, pd.DataFrame],
    trade_dates: list[Any],
    date_text: str,
    horizon: int,
    args: argparse.Namespace,
) -> dict[str, Any]:
    trades = []
    for item in items:
        trade = simulate_stock(price_index, trade_dates, date_text, item["stock_id"], horizon, args)
        if trade is not None:
            trades.append({"stock_id": item["stock_id"], **trade})
    returns = pd.Series([trade["net_return"] for trade in trades], dtype=float)
    return {
        "stock_ids": [item["stock_id"] for item in items],
        "valid_trade_count": int(len(trades)),
        "avg_net_return": round(float(returns.mean()), 6) if not returns.empty else None,
        "hit_rate": round(float((returns > 0).mean()), 6) if not returns.empty else None,
        "avg_mae": round(float(pd.Series([trade["mae"] for trade in trades], dtype=float).mean()), 6) if trades else None,
        "avg_mfe": round(float(pd.Series([trade["mfe"] for trade in trades], dtype=float).mean()), 6) if trades else None,
    }


def max_drawdown(returns: list[float]) -> float | None:
    if not returns:
        return None
    equity = 1.0
    peak = 1.0
    worst = 0.0
    for value in returns:
        equity *= 1 + value
        peak = max(peak, equity)
        worst = min(worst, equity / peak - 1)
    return round(worst, 6)


def turnover(rows: list[dict[str, Any]], policy: str) -> float | None:
    previous: set[str] | None = None
    values = []
    for row in rows:
        current = set(row["policies"][policy]["stock_ids"])
        if previous is not None:
            values.append(1 - len(previous & current) / max(len(current), 1))
        previous = current
    return round(float(pd.Series(values).mean()), 6) if values else None


def summarize_policy(rows: list[dict[str, Any]], policy: str, horizon: int) -> dict[str, Any]:
    buckets = [row["policies"][policy] for row in rows if row["horizon"] == horizon]
    returns = [bucket["avg_net_return"] for bucket in buckets if bucket.get("avg_net_return") is not None]
    hit_rates = [bucket["hit_rate"] for bucket in buckets if bucket.get("hit_rate") is not None]
    maes = [bucket["avg_mae"] for bucket in buckets if bucket.get("avg_mae") is not None]
    mfes = [bucket["avg_mfe"] for bucket in buckets if bucket.get("avg_mfe") is not None]
    valid_counts = [int(bucket.get("valid_trade_count") or 0) for bucket in buckets]
    return {
        "date_count": len(returns),
        "avg_net_return": round(float(pd.Series(returns).mean()), 6) if returns else None,
        "hit_rate": round(float(pd.Series(hit_rates).mean()), 6) if hit_rates else None,
        "avg_mae": round(float(pd.Series(maes).mean()), 6) if maes else None,
        "avg_mfe": round(float(pd.Series(mfes).mean()), 6) if mfes else None,
        "max_drawdown": max_drawdown(returns),
        "turnover": turnover([row for row in rows if row["horizon"] == horizon], policy),
        "min_valid_trade_count": min(valid_counts) if valid_counts else 0,
    }


def summarize(rows: list[dict[str, Any]], horizons: list[int]) -> dict[str, Any]:
    result = {}
    for horizon in horizons:
        baseline = summarize_policy(rows, "baseline", horizon)
        variants = {}
        for policy in POLICIES:
            summary = summarize_policy(rows, policy, horizon)
            delta = None
            if summary.get("avg_net_return") is not None and baseline.get("avg_net_return") is not None:
                delta = round(float(summary["avg_net_return"]) - float(baseline["avg_net_return"]), 6)
            variants[policy] = {**summary, "return_delta_vs_baseline": delta}
        result[str(horizon)] = variants
    return result


def summarize_by_regime(rows: list[dict[str, Any]], horizons: list[int]) -> dict[str, Any]:
    regimes = sorted({str(row.get("market_regime") or "UNKNOWN") for row in rows})
    result: dict[str, Any] = {}
    for regime in regimes:
        subset = [row for row in rows if str(row.get("market_regime") or "UNKNOWN") == regime]
        if not subset:
            continue
        result[regime] = {
            "row_count": len(subset),
            "summary": summarize(subset, horizons),
        }
    return result


def decision(summary: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for horizon, variants in summary.items():
        for policy, metrics in variants.items():
            if policy == "baseline":
                continue
            rows.append(
                {
                    "horizon": int(horizon),
                    "policy": policy,
                    "return_delta": metrics.get("return_delta_vs_baseline"),
                    "hit_rate": metrics.get("hit_rate"),
                    "max_drawdown": metrics.get("max_drawdown"),
                    "turnover": metrics.get("turnover"),
                }
            )
    rows = sorted(rows, key=lambda row: row["return_delta"] if row["return_delta"] is not None else -999, reverse=True)
    best = rows[0] if rows else {}
    positive = [row for row in rows if (row.get("return_delta") or 0) > 0]
    return {
        "status": "ENTRY_QUALITY_CANDIDATE" if positive else "NO_ENTRY_QUALITY_UPLIFT",
        "best_policy": best,
        "positive_policy_count": len(positive),
        "next_step": "run stricter replay with regime split and drawdown/turnover gates" if positive else "monitor only; do not promote",
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    rankings_dir = resolve_path(args.rankings_dir)
    features_path = resolve_path(args.features)
    regime_path = resolve_path(args.market_regime_history)
    assert rankings_dir is not None and features_path is not None
    horizons = parse_horizons(args.horizons)
    feature_lookup = load_feature_lookup(features_path)
    regime_map = load_regime_map(regime_path)
    price_frame = run_backtest_replay.load_price_frame(features_path)
    trade_dates = run_backtest_replay.market_trade_dates(price_frame)
    price_index = run_backtest_replay.build_price_index(price_frame)
    files = ranking_files(rankings_dir)
    rows = []
    for path in files:
        date_text = run_backtest_replay.ranking_date(path)
        market_regime = regime_map.get(date_text, "UNKNOWN")
        ranking = read_ranking(path, args.candidate_pool)
        for horizon in horizons:
            policies = {}
            for policy_name in POLICIES:
                items = select_policy_items(ranking, feature_lookup, date_text, policy_name, args.top_n)
                policies[policy_name] = simulate_bucket(items, price_index, trade_dates, date_text, horizon, args)
            rows.append({"ranking_date": date_text, "horizon": horizon, "market_regime": market_regime, "policies": policies})
    summary = summarize(rows, horizons)
    regime_summary = summarize_by_regime(rows, horizons)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "contract": {
            "research_only": True,
            "reads_formal_features_parquet": True,
            "does_not_train_model": True,
            "does_not_change_production_ranking": True,
            "production_ready": False,
        },
        "inputs": {
            "rankings_dir": repo_path(rankings_dir),
            "features": repo_path(features_path),
            "market_regime_history": repo_path(regime_path),
            "regime_coverage": {
                "mapped_dates": len(regime_map),
                "unknown_ranking_dates": sum(1 for path in files if regime_map.get(run_backtest_replay.ranking_date(path)) is None),
            },
            "ranking_file_count": len(files),
            "horizons": horizons,
            "top_n": args.top_n,
            "candidate_pool": args.candidate_pool,
            "policies": POLICIES,
        },
        "decision": decision(summary),
        "summary": summary,
        "regime_summary": regime_summary,
        "daily": rows,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# VWAP Entry Quality Replay",
        "",
        f"- decision：`{payload['decision']['status']}`",
        f"- best_policy：`{payload['decision']['best_policy']}`",
        f"- next_step：`{payload['decision']['next_step']}`",
        "",
        "| Horizon | Policy | Return | Delta | Hit | MDD | Turnover |",
        "|---:|---|---:|---:|---:|---:|---:|",
    ]
    for horizon, variants in payload["summary"].items():
        for policy, metrics in variants.items():
            lines.append(
                f"| {horizon} | {policy} | {fmt(metrics.get('avg_net_return'))} | "
                f"{fmt(metrics.get('return_delta_vs_baseline'))} | {fmt(metrics.get('hit_rate'))} | "
                f"{fmt(metrics.get('max_drawdown'))} | {fmt(metrics.get('turnover'))} |"
            )
    lines.extend(["", "## Regime Summary", "", "| Regime | Horizon | Best Policy | Best Delta | Baseline Return |", "|---|---:|---|---:|---:|"])
    for regime, regime_payload in payload.get("regime_summary", {}).items():
        for horizon, variants in regime_payload.get("summary", {}).items():
            baseline_return = variants.get("baseline", {}).get("avg_net_return")
            candidates = [
                (policy, metrics.get("return_delta_vs_baseline"))
                for policy, metrics in variants.items()
                if policy != "baseline"
            ]
            best_policy, best_delta = max(candidates, key=lambda item: item[1] if item[1] is not None else -999)
            lines.append(f"| {regime} | {horizon} | {best_policy} | {fmt(best_delta)} | {fmt(baseline_return)} |")
    return "\n".join(lines) + "\n"


def fmt(value: Any) -> str:
    if value is None:
        return "--"
    return f"{float(value):.4f}"


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = resolve_path(args.output) or PROJECT_ROOT / "artifacts" / "model_experiments" / f"vwap_entry_quality_replay_{args.date}.json"
    assert output is not None
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": "OK", "output": repo_path(output), "decision": payload["decision"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
