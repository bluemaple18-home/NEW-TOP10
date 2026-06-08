#!/usr/bin/env python3
"""彙整 AUTO-TRAINING-10 BIG_BULL ranking/replay extension 結果。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import research_regime_family_training_candidates as candidates  # noqa: E402

SCHEMA_VERSION = "big-bull-ranking-replay-extension-report.v1"
VARIANTS = {
    "baseline": "portfolio_auto10_baseline",
    "family_only": "portfolio_auto10_family_only",
    "blended_rerank": "portfolio_auto10_blended_rerank",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build AUTO-TRAINING-10 summary report")
    parser.add_argument("--date", required=True)
    parser.add_argument("--data-dir", default="data/clean")
    parser.add_argument("--market-regime-history", default="artifacts/market_regime_history_2026-06-01.json")
    parser.add_argument("--artifacts-dir", default="artifacts/backtest")
    parser.add_argument("--high-choppy-context", default="artifacts/model_experiments/high_choppy_context_overlay_2026-06-01.json")
    parser.add_argument("--high-choppy-verification", default="artifacts/model_experiments/high_choppy_context_overlay_verification_latest.json")
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def portfolio_path(artifacts_dir: Path, variant: str, top_n: int, delay: int, date_text: str, suffix: str = "") -> Path:
    stem = f"{VARIANTS[variant]}_top{top_n}_d{delay}{suffix}_{date_text}.json"
    return artifacts_dir / stem


def turnover(daily: list[dict[str, Any]]) -> dict[str, Any]:
    if not daily:
        return {"total_entries": 0, "total_exits": 0, "avg_daily_turnover_events": 0.0}
    entries = sum(int(row.get("entries") or 0) for row in daily)
    exits = sum(int(row.get("exits") or 0) for row in daily)
    return {
        "total_entries": entries,
        "total_exits": exits,
        "avg_daily_turnover_events": round((entries + exits) / len(daily), 6),
    }


def compact_summary(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    summary = payload.get("summary", {})
    return {
        "path": repo_path(path),
        "total_return": summary.get("total_return"),
        "avg_trade_return": summary.get("avg_trade_return"),
        "max_drawdown": summary.get("max_drawdown"),
        "hit_rate": summary.get("win_rate"),
        "trade_count": summary.get("trade_count"),
        "skipped_count": summary.get("skipped_count"),
        "sector_concentration": summary.get("max_group_exposure"),
        **turnover(payload.get("daily", [])),
    }


def topn_matrix(artifacts_dir: Path, date_text: str) -> dict[str, Any]:
    rows = {}
    for variant in VARIANTS:
        rows[variant] = {
            f"top{top_n}": compact_summary(portfolio_path(artifacts_dir, variant, top_n, 1, date_text))
            for top_n in (5, 10, 15)
        }
    return rows


def entry_matrix(artifacts_dir: Path, date_text: str) -> dict[str, Any]:
    rows = {}
    for variant in VARIANTS:
        rows[variant] = {
            f"d{delay}": compact_summary(portfolio_path(artifacts_dir, variant, 10, delay, date_text))
            for delay in (1, 2, 3)
        }
    return rows


def window_matrix(artifacts_dir: Path, date_text: str) -> dict[str, Any]:
    return {
        variant: {
            "full": compact_summary(portfolio_path(artifacts_dir, variant, 10, 1, date_text)),
            "last12": compact_summary(portfolio_path(artifacts_dir, variant, 10, 1, date_text, "_last12")),
        }
        for variant in VARIANTS
    }


def stratified_by_dates(payload: dict[str, Any], dates: set[str]) -> dict[str, Any]:
    trades = [trade for trade in payload.get("trades", []) if str(trade.get("ranking_date")) in dates]
    if not trades:
        return {"trade_count": 0, "avg_net_return": None, "hit_rate": None, "ranking_dates": []}
    returns = [float(trade.get("net_return") or 0.0) for trade in trades]
    return {
        "trade_count": len(trades),
        "avg_net_return": round(sum(returns) / len(returns), 6),
        "hit_rate": round(sum(1 for value in returns if value > 0) / len(returns), 6),
        "ranking_dates": sorted({str(trade.get("ranking_date")) for trade in trades}),
    }


def high_choppy_stratified(artifacts_dir: Path, date_text: str, context_path: Path) -> dict[str, Any]:
    context = read_json(context_path)
    strict_dates = set(context.get("dates", {}).get("strict", []))
    rolling_dates = set(context.get("dates", {}).get("rolling_context", []))
    rows = {}
    for variant in ("family_only", "blended_rerank"):
        payload = read_json(portfolio_path(artifacts_dir, variant, 10, 1, date_text))
        rows[variant] = {
            "strict_high_choppy": stratified_by_dates(payload, strict_dates),
            "rolling_high_choppy": stratified_by_dates(payload, rolling_dates),
        }
    return rows


def required_high_choppy_inputs(context_path: Path, verification_path: Path) -> dict[str, Any]:
    checks = {
        "context_artifact_exists": context_path.exists(),
        "verification_artifact_exists": verification_path.exists(),
        "context_status_ok": False,
        "verification_status_ok": False,
        "soft_feature_allowed": False,
        "stratified_evaluation_allowed": False,
    }
    context: dict[str, Any] = {}
    verification: dict[str, Any] = {}
    if context_path.exists():
        context = read_json(context_path)
        summary = context.get("summary", {})
        allowed = summary.get("usage_allowed", {})
        checks["context_status_ok"] = context.get("status") == "OK"
        checks["soft_feature_allowed"] = (allowed.get("soft_feature") or {}).get("status") == "ALLOWED"
        checks["stratified_evaluation_allowed"] = (allowed.get("stratified_evaluation") or {}).get("status") == "ALLOWED"
    if verification_path.exists():
        verification = read_json(verification_path)
        checks["verification_status_ok"] = verification.get("status") == "OK"
    return {
        "status": "OK" if all(checks.values()) else "FAILED",
        "context_artifact": repo_path(context_path),
        "verification_artifact": repo_path(verification_path),
        "checks": checks,
        "context_decision": context.get("decision"),
        "verification_status": verification.get("status"),
    }


def metric_delta(with_feature: dict[str, Any], without_feature: dict[str, Any]) -> dict[str, Any]:
    with_topn = with_feature.get("topn_proxy", {})
    without_topn = without_feature.get("topn_proxy", {})
    return {
        "avg_auc_delta": round(float(with_feature.get("avg_auc") or 0) - float(without_feature.get("avg_auc") or 0), 6)
        if with_feature.get("avg_auc") is not None and without_feature.get("avg_auc") is not None
        else None,
        "topn_return_delta": round(
            float(with_topn.get("avg_topn_future_return") or 0) - float(without_topn.get("avg_topn_future_return") or 0),
            6,
        )
        if with_topn.get("avg_topn_future_return") is not None
        and without_topn.get("avg_topn_future_return") is not None
        else None,
        "topn_uplift_delta": round(
            float(with_topn.get("topn_minus_universe_return") or 0)
            - float(without_topn.get("topn_minus_universe_return") or 0),
            6,
        )
        if with_topn.get("topn_minus_universe_return") is not None
        and without_topn.get("topn_minus_universe_return") is not None
        else None,
    }


def high_choppy_soft_feature_comparison(args: argparse.Namespace, context_path: Path) -> dict[str, Any]:
    context = read_json(context_path)
    rolling_dates = set(context.get("dates", {}).get("rolling_context", []))
    if not rolling_dates:
        return {"status": "FAILED", "reason": "missing rolling_context dates"}
    frame_args = argparse.Namespace(
        data_dir=args.data_dir,
        market_regime_history=args.market_regime_history,
        horizon=10,
        threshold=0.05,
    )
    frame, features, _regimes = candidates.labeled_frame(frame_args, ["BIG_BULL"])
    frame = frame.copy()
    frame["high_choppy_rolling_context"] = (
        pd.to_datetime(frame["trade_date"], errors="coerce").dt.date.astype(str).isin(rolling_dates).astype(int)
    )
    family_dates = sorted(frame.loc[frame["family_BIG_BULL"], "trade_date"].drop_duplicates().tolist())
    windows = candidates.fold_windows(family_dates, 4)
    common_kwargs = {
        "frame": frame,
        "family": "BIG_BULL",
        "windows": windows,
        "embargo": 10,
        "variant": "family_only_training",
        "num_boost_round": 120,
        "top_n": 10,
        "family_weight": 2.0,
    }
    without_feature = candidates.run_variant(features=features, **common_kwargs)
    with_feature = candidates.run_variant(features=[*features, "high_choppy_rolling_context"], **common_kwargs)
    deltas = metric_delta(with_feature, without_feature)
    helped = any((deltas.get(key) or 0) > 0 for key in ("avg_auc_delta", "topn_return_delta", "topn_uplift_delta"))
    return {
        "status": "OK",
        "feature_name": "high_choppy_rolling_context",
        "context_identity": "soft feature + stratified diagnostic; not family-specific model; not promotion evidence",
        "without_feature": {
            "fold_count": without_feature.get("fold_count"),
            "avg_auc": without_feature.get("avg_auc"),
            "topn_proxy": without_feature.get("topn_proxy"),
        },
        "with_feature": {
            "fold_count": with_feature.get("fold_count"),
            "avg_auc": with_feature.get("avg_auc"),
            "topn_proxy": with_feature.get("topn_proxy"),
        },
        "delta": deltas,
        "soft_feature_decision": "SOFT_FEATURE_RETAIN_FOR_FOLLOWUP" if helped else "MONITOR_ONLY",
        "affects_next_stage_qualification": False,
        "reason": "soft feature comparison is diagnostic; next-stage ranking qualification still comes from replay robustness",
    }


def choose_candidate(topn: dict[str, Any], entry: dict[str, Any], soft_feature: dict[str, Any]) -> dict[str, Any]:
    candidates = ["family_only", "blended_rerank"]
    scores = {}
    for variant in candidates:
        top10 = topn[variant]["top10"]
        d1 = entry[variant]["d1"]
        scores[variant] = {
            "total_return": top10["total_return"],
            "max_drawdown": top10["max_drawdown"],
            "hit_rate": top10["hit_rate"],
            "d1_total_return": d1["total_return"],
        }
    best = max(candidates, key=lambda name: (scores[name]["total_return"] or -999, scores[name]["hit_rate"] or -999))
    return {
        "best_candidate": best,
        "decision": "RANKING_FOLLOWUP_CANDIDATE",
        "promotion_ready": False,
        "high_choppy_included_in_main_training": soft_feature.get("status") == "OK",
        "reason": "已納入 HIGH_CHOPPY rolling context soft feature comparison 與 stratified evaluation；production promotion 仍由 sealed OOS / rollback gate 判定。",
        "scores": scores,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    artifacts_dir = resolve_path(args.artifacts_dir)
    high_choppy_context = resolve_path(args.high_choppy_context)
    high_choppy_verification = resolve_path(args.high_choppy_verification)
    required_inputs = required_high_choppy_inputs(high_choppy_context, high_choppy_verification)
    topn = topn_matrix(artifacts_dir, args.date)
    entry = entry_matrix(artifacts_dir, args.date)
    window = window_matrix(artifacts_dir, args.date)
    soft_feature = (
        high_choppy_soft_feature_comparison(args, high_choppy_context)
        if required_inputs["status"] == "OK"
        else {"status": "FAILED", "reason": "required HIGH_CHOPPY inputs missing or invalid"}
    )
    stratified = high_choppy_stratified(artifacts_dir, args.date, high_choppy_context) if required_inputs["status"] == "OK" else {}
    status = "OK" if required_inputs["status"] == "OK" and soft_feature.get("status") == "OK" and stratified else "FAILED"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": status,
        "contract": {
            "research_only": True,
            "variants": ["BIG_BULL family_only", "BIG_BULL blended_rerank"],
            "baseline": "current production ranking",
            "requires_high_choppy_soft_feature_comparison": True,
            "requires_high_choppy_stratified_evaluation": True,
            "missing_high_choppy_evaluation_is_failed": True,
            "does_not_write_models_latest_lgbm": True,
            "production_promotion_allowed": False,
        },
        "required_high_choppy_inputs": required_inputs,
        "topn_sensitivity": topn,
        "entry_day_sensitivity": entry,
        "replay_window_sensitivity": window,
        "high_choppy_soft_feature_comparison": soft_feature,
        "big_bull_high_choppy_stratified": stratified,
        "high_choppy_included_in_main_training": status == "OK",
        "decision": choose_candidate(topn, entry, soft_feature),
    }


def pct(value: Any) -> str:
    return "--" if value is None else f"{float(value):.2%}"


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# AUTO-TRAINING-10 BIG_BULL Ranking Replay Extension",
        "",
        f"- status: {payload['status']}",
        f"- best_candidate: {payload['decision']['best_candidate']}",
        f"- decision: {payload['decision']['decision']}",
        f"- promotion_ready: {payload['decision']['promotion_ready']}",
        f"- high_choppy_included_in_main_training: {payload['high_choppy_included_in_main_training']}",
        "",
        "## HIGH_CHOPPY Soft Feature Comparison",
        "",
        f"- status: {payload['high_choppy_soft_feature_comparison']['status']}",
        f"- decision: {payload['high_choppy_soft_feature_comparison'].get('soft_feature_decision')}",
        f"- auc_delta: {payload['high_choppy_soft_feature_comparison'].get('delta', {}).get('avg_auc_delta')}",
        f"- topn_return_delta: {payload['high_choppy_soft_feature_comparison'].get('delta', {}).get('topn_return_delta')}",
        f"- topn_uplift_delta: {payload['high_choppy_soft_feature_comparison'].get('delta', {}).get('topn_uplift_delta')}",
        "",
        "## TopN Sensitivity",
        "",
        "| Variant | TopN | Total | Max DD | Hit | Avg Trade | Trades | Sector Conc. | Turnover Events/Day |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for variant, by_topn in payload["topn_sensitivity"].items():
        for topn, row in by_topn.items():
            lines.append(
                f"| {variant} | {topn} | {pct(row['total_return'])} | {pct(row['max_drawdown'])} | "
                f"{pct(row['hit_rate'])} | {pct(row['avg_trade_return'])} | {row['trade_count']} | "
                f"{pct(row['sector_concentration'])} | {row['avg_daily_turnover_events']:.2f} |"
            )
    lines.extend(["", "## Entry Day Sensitivity", "", "| Variant | Entry | Total | Max DD | Hit | Trades |", "|---|---:|---:|---:|---:|---:|"])
    for variant, by_delay in payload["entry_day_sensitivity"].items():
        for delay, row in by_delay.items():
            lines.append(f"| {variant} | {delay} | {pct(row['total_return'])} | {pct(row['max_drawdown'])} | {pct(row['hit_rate'])} | {row['trade_count']} |")
    lines.extend(["", "## Replay Window Sensitivity", "", "| Variant | Window | Total | Max DD | Hit | Trades |", "|---|---|---:|---:|---:|---:|"])
    for variant, by_window in payload["replay_window_sensitivity"].items():
        for window, row in by_window.items():
            lines.append(f"| {variant} | {window} | {pct(row['total_return'])} | {pct(row['max_drawdown'])} | {pct(row['hit_rate'])} | {row['trade_count']} |")
    lines.extend(["", "## HIGH_CHOPPY Stratified", "", "| Variant | Slice | Avg Return | Hit | Trades | Dates |", "|---|---|---:|---:|---:|---|"])
    for variant, slices in payload["big_bull_high_choppy_stratified"].items():
        for name, row in slices.items():
            dates = ", ".join(row.get("ranking_dates", []))
            lines.append(
                f"| {variant} | {name} | {pct(row['avg_net_return'])} | {pct(row['hit_rate'])} | "
                f"{row['trade_count']} | {dates} |"
            )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    output = resolve_path(args.output) if args.output else PROJECT_ROOT / "artifacts" / "model_experiments" / f"big_bull_ranking_replay_extension_{args.date}.json"
    payload = build_payload(args)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output), "best_candidate": payload["decision"]["best_candidate"]}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
