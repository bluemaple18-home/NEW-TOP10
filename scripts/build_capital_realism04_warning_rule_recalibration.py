#!/usr/bin/env python3
"""重校準近 7 日 Top10 warning rule，避免 RISK_ALERT 分級失真。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Callable

from build_capital_realism03_warning_effectiveness_report import (
    HORIZONS,
    build_items_for_date,
    build_price_index,
    forward_return,
    load_features,
    ranking_date,
    ranking_files,
    repo_path,
    resolve_path,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "capital-realism04-warning-rule-recalibration.v1"
RUN_DATE = "2026-06-05"
TARGET_HORIZON = 10


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build CAPITAL-REALISM-04 warning rule recalibration report")
    parser.add_argument(
        "--rankings-dir",
        default="artifacts/backtest/historical_rankings_current_model_half_year_dense_2025-11-17_2026-05-15",
    )
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument("--watchlist-ranking-days", type=int, default=7)
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--min-samples", type=int, default=100)
    parser.add_argument(
        "--output",
        default=f"artifacts/model_experiments/capital_realism04_warning_rule_recalibration_{RUN_DATE}.json",
    )
    return parser.parse_args()


def has_signal(row: dict[str, Any], signal: str) -> bool:
    return signal in set(row.get("signals") or [])


def all_signals(*signals: str) -> Callable[[dict[str, Any]], bool]:
    return lambda row: all(has_signal(row, signal) for signal in signals)


def any_signal(*signals: str) -> Callable[[dict[str, Any]], bool]:
    return lambda row: any(has_signal(row, signal) for signal in signals)


def and_rules(*rules: Callable[[dict[str, Any]], bool]) -> Callable[[dict[str, Any]], bool]:
    return lambda row: all(rule(row) for rule in rules)


def current_risk_alert(row: dict[str, Any]) -> bool:
    return (has_signal(row, "recently_dropped_from_top10") and has_signal(row, "close_below_ma20")) or has_signal(
        row, "risk_penalty_elevated"
    )


CANDIDATES: dict[str, Callable[[dict[str, Any]], bool]] = {
    "current_risk_alert": current_risk_alert,
    "dropped_from_top10": all_signals("recently_dropped_from_top10"),
    "dropped_and_below_ma5": all_signals("recently_dropped_from_top10", "close_below_ma5"),
    "dropped_and_below_ma10": all_signals("recently_dropped_from_top10", "close_below_ma10"),
    "dropped_and_below_ma20": all_signals("recently_dropped_from_top10", "close_below_ma20"),
    "dropped_and_long_upper_shadow": all_signals("recently_dropped_from_top10", "long_upper_shadow"),
    "dropped_and_rank_worsened": all_signals("recently_dropped_from_top10", "rank_worsened"),
    "below_ma20": all_signals("close_below_ma20"),
    "below_ma20_and_long_upper_shadow": all_signals("close_below_ma20", "long_upper_shadow"),
    "rank_worsened_and_ma_break": and_rules(
        all_signals("rank_worsened"),
        any_signal("close_below_ma5", "close_below_ma10", "close_below_ma20"),
    ),
    "risk_penalty_elevated": all_signals("risk_penalty_elevated"),
}


def mean(values: list[float]) -> float | None:
    return None if not values else round(sum(values) / len(values), 6)


def rate(values: list[float], predicate: Any) -> float | None:
    return None if not values else round(sum(1 for value in values if predicate(value)) / len(values), 6)


def summarize(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "avg_return": None, "median_return": None, "negative_rate": None, "loss_gt_5pct_rate": None}
    return {
        "count": len(values),
        "avg_return": mean(values),
        "median_return": round(float(median(values)), 6),
        "negative_rate": rate(values, lambda value: value < 0),
        "loss_gt_5pct_rate": rate(values, lambda value: value <= -0.05),
    }


def collect_observations(args: argparse.Namespace) -> list[dict[str, Any]]:
    rankings_dir = resolve_path(args.rankings_dir)
    features_path = resolve_path(args.features)
    files = ranking_files(rankings_dir)
    features = load_features(features_path)
    price_index = build_price_index(features)
    target_indices = range(args.watchlist_ranking_days - 1, len(files) - max(HORIZONS))
    observations: list[dict[str, Any]] = []
    for target_index in target_indices:
        target_date = ranking_date(files[target_index])
        items = build_items_for_date(files, target_index, features, args.watchlist_ranking_days, args.top_n)
        for item in items:
            returns: dict[str, float] = {}
            for horizon in HORIZONS:
                value = forward_return(price_index, item["stock_id"], target_date, horizon)
                if value is not None:
                    returns[str(horizon)] = value
            if str(TARGET_HORIZON) not in returns:
                continue
            observations.append(
                {
                    "date": target_date,
                    "stock_id": item["stock_id"],
                    "warning_level": item.get("warning_level"),
                    "latest_in_top10": item.get("latest_in_top10"),
                    "signals": item.get("signals") or [],
                    "forward_returns": returns,
                }
            )
    return observations


def safe_delta(value: Any, base: Any) -> float | None:
    if value is None or base is None:
        return None
    return round(float(value) - float(base), 6)


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    observations = collect_observations(args)
    all_returns = [row["forward_returns"][str(TARGET_HORIZON)] for row in observations]
    watch_returns = [
        row["forward_returns"][str(TARGET_HORIZON)]
        for row in observations
        if row.get("warning_level") == "WATCH"
    ]
    baseline_all = summarize(all_returns)
    baseline_watch = summarize(watch_returns)

    candidate_results: dict[str, dict[str, Any]] = {}
    for name, predicate in CANDIDATES.items():
        selected = [row["forward_returns"][str(TARGET_HORIZON)] for row in observations if predicate(row)]
        outcome = summarize(selected)
        candidate_results[name] = {
            "outcome": outcome,
            "delta_vs_all": {
                "avg_return": safe_delta(outcome["avg_return"], baseline_all["avg_return"]),
                "negative_rate": safe_delta(outcome["negative_rate"], baseline_all["negative_rate"]),
                "loss_gt_5pct_rate": safe_delta(outcome["loss_gt_5pct_rate"], baseline_all["loss_gt_5pct_rate"]),
            },
            "delta_vs_watch": {
                "avg_return": safe_delta(outcome["avg_return"], baseline_watch["avg_return"]),
                "negative_rate": safe_delta(outcome["negative_rate"], baseline_watch["negative_rate"]),
                "loss_gt_5pct_rate": safe_delta(outcome["loss_gt_5pct_rate"], baseline_watch["loss_gt_5pct_rate"]),
            },
        }

    approved: list[str] = []
    monitor_only: list[str] = []
    rejected: list[str] = []
    for name, row in candidate_results.items():
        outcome = row["outcome"]
        delta_watch = row["delta_vs_watch"]
        has_samples = int(outcome["count"] or 0) >= args.min_samples
        directional = (
            delta_watch["avg_return"] is not None
            and delta_watch["negative_rate"] is not None
            and delta_watch["loss_gt_5pct_rate"] is not None
            and delta_watch["avg_return"] < 0
            and delta_watch["negative_rate"] > 0
            and delta_watch["loss_gt_5pct_rate"] > 0
        )
        if has_samples and directional:
            approved.append(name)
        elif has_samples:
            monitor_only.append(name)
        else:
            rejected.append(name)

    if approved:
        status = "RISK_ALERT_RULE_CANDIDATE_FOUND"
        best = min(approved, key=lambda name: candidate_results[name]["delta_vs_watch"]["avg_return"])
    else:
        status = "NO_CLEAN_RISK_ALERT_RULE"
        best = None

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK",
        "contract": {
            "research_only": True,
            "changes_model": False,
            "changes_production_ranking": False,
            "changes_risk_adjusted_score": False,
            "does_not_send_push": True,
            "non_personal_warning_only": True,
            "uses_future_rankings_for_warning": False,
            "uses_future_prices_for_evaluation_only": True,
            "target_horizon_days": TARGET_HORIZON,
            "min_samples": args.min_samples,
        },
        "inputs": {
            "rankings_dir": repo_path(resolve_path(args.rankings_dir)),
            "features": repo_path(resolve_path(args.features)),
            "watchlist_ranking_days": args.watchlist_ranking_days,
            "top_n": args.top_n,
            "observation_count": len(observations),
        },
        "baselines": {
            "all_watchlist": baseline_all,
            "watch_level": baseline_watch,
        },
        "candidate_results": candidate_results,
        "decision": {
            "status": status,
            "approved_candidates": approved,
            "monitor_only_candidates": monitor_only,
            "rejected_candidates": rejected,
            "best_candidate": best,
            "recommendation_channel": "NO_CHANGE",
            "warning_channel": "RESEARCH_ONLY_NOT_PUSH",
            "primary_read": (
                "RISK_ALERT 不能只因為聽起來比較嚴重就上線。"
                "本卡要求候選規則相對 WATCH 同時滿足：10D 平均報酬更低、負報酬率更高、"
                "大跌率更高，且樣本數足夠。"
            ),
            "next_experiments": [
                "若有 approved candidate，先做 warning-only dry-run message，不送推播。",
                "若沒有 approved candidate，保留 WEAKENING，RISK_ALERT 暫不輸出。",
                "後續再加入族群/大盤轉弱條件，不只看個股均線。",
            ],
        },
    }


def pct(value: Any) -> str:
    if value is None:
        return "--"
    return f"{float(value):.2%}"


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# CAPITAL-REALISM-04 Warning Rule Recalibration",
        "",
        f"- status: `{payload['status']}`",
        f"- decision: `{payload['decision']['status']}`",
        f"- best_candidate: `{payload['decision']['best_candidate']}`",
        f"- recommendation_channel: `{payload['decision']['recommendation_channel']}`",
        f"- warning_channel: `{payload['decision']['warning_channel']}`",
        "",
        "## Baselines",
        "",
        "```json",
        json.dumps(payload["baselines"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Candidates",
        "",
        "| candidate | count | avg 10D | neg rate | loss >5% | avg delta vs WATCH | neg delta | loss delta |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, row in sorted(payload["candidate_results"].items()):
        outcome = row["outcome"]
        delta = row["delta_vs_watch"]
        lines.append(
            f"| {name} | {outcome['count']} | {pct(outcome['avg_return'])} | "
            f"{pct(outcome['negative_rate'])} | {pct(outcome['loss_gt_5pct_rate'])} | "
            f"{pct(delta['avg_return'])} | {pct(delta['negative_rate'])} | {pct(delta['loss_gt_5pct_rate'])} |"
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "```json",
            json.dumps(payload["decision"], ensure_ascii=False, indent=2),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = resolve_path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {"status": payload["status"], "output": repo_path(output), "decision": payload["decision"]["status"]},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
