#!/usr/bin/env python3
"""回測 overlap-first 每日推薦影子排序。

此腳本只讀既有 production / candidate ranking CSV，產出 overlap-first shadow
ranking，再用既有零股 portfolio replay 比較 production / candidate / overlap-first。
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import run_odd_lot_portfolio_replay  # noqa: E402


SCHEMA_VERSION = "overlap-first-recommendation-performance.v1"
DEFAULT_PRODUCTION_DIR = "artifacts/backtest/historical_rankings_current_model_batch_dense_2023-11-21_2026-05-15"
DEFAULT_CANDIDATE_DIR = (
    "artifacts/model_experiments/training_candidates/current_baseline_candidate_2026-06-08/"
    "candidate_rankings_2023-11-21_2026-05-15"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="backtest overlap-first recommendation performance")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--window", choices=["recent_100", "recent_6m", "long"], default="recent_100")
    parser.add_argument("--production-rankings-dir", default=DEFAULT_PRODUCTION_DIR)
    parser.add_argument("--candidate-rankings-dir", default=DEFAULT_CANDIDATE_DIR)
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument("--initial-cash", type=float, default=300_000)
    parser.add_argument("--top-n", type=int, default=7)
    parser.add_argument("--ranking-top-n", type=int, default=10)
    parser.add_argument("--actionable-top-n", type=int, default=7)
    parser.add_argument("--horizon", type=int, default=40)
    parser.add_argument("--max-gross-exposure", type=float, default=0.75)
    parser.add_argument("--max-position-weight", type=float, default=0.12)
    parser.add_argument("--stop-loss-pct", type=float, default=0.12)
    parser.add_argument("--trailing-stop-pct", type=float, default=0.10)
    parser.add_argument("--min-event-holding-days", type=int, default=5)
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


def ranking_date(path: Path) -> str:
    return path.stem.removeprefix("ranking_")


def ranking_files(path: Path) -> dict[str, Path]:
    return {
        ranking_date(item): item
        for item in sorted(path.glob("ranking_*.csv"))
        if item.name.startswith("ranking_") and item.suffix == ".csv"
    }


def select_dates(common_dates: list[str], window: str) -> list[str]:
    if window == "recent_100":
        return common_dates[-100:]
    if window == "recent_6m":
        # 近半年約 120 個交易日；用交易日數切，避免日曆假日造成漂移。
        return common_dates[-120:]
    return common_dates


def normalize_stock_id(value: Any) -> str:
    return str(value or "").strip().replace(".0", "").zfill(4)


def read_rows(path: Path, top_n: int) -> tuple[list[str], list[dict[str, Any]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = []
        for rank, row in enumerate(reader, start=1):
            if rank > top_n:
                break
            normalized = dict(row)
            normalized["stock_id"] = normalize_stock_id(normalized.get("stock_id"))
            rows.append(normalized)
    return fieldnames, rows


def merge_fieldnames(*fieldname_groups: list[str]) -> list[str]:
    result: list[str] = []
    for group in fieldname_groups:
        for name in group:
            if name and name not in result:
                result.append(name)
    for required in ["stock_id", "stock_name"]:
        if required not in result:
            result.insert(0, required)
    return result


def ordered_overlap_first(
    production_rows: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
    actionable_top_n: int,
    top_n: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    prod_by_id = {row["stock_id"]: row for row in production_rows}
    cand_by_id = {row["stock_id"]: row for row in candidate_rows}
    prod_ids = [row["stock_id"] for row in production_rows]
    cand_ids = [row["stock_id"] for row in candidate_rows]
    cand_rank = {stock_id: index + 1 for index, stock_id in enumerate(cand_ids)}
    prod_rank = {stock_id: index + 1 for index, stock_id in enumerate(prod_ids)}

    overlap_ids = [stock_id for stock_id in cand_ids if stock_id in prod_by_id]
    overlap_ids.sort(key=lambda stock_id: (cand_rank[stock_id] + prod_rank[stock_id], cand_rank[stock_id]))
    candidate_trail_ids = [
        stock_id
        for stock_id in cand_ids
        if stock_id not in prod_by_id and cand_rank[stock_id] <= actionable_top_n
    ]
    production_only_ids = [stock_id for stock_id in prod_ids if stock_id not in cand_by_id]
    candidate_no_trail_ids = [
        stock_id
        for stock_id in cand_ids
        if stock_id not in prod_by_id and cand_rank[stock_id] > actionable_top_n
    ]
    selected_ids = [*overlap_ids, *candidate_trail_ids, *production_only_ids, *candidate_no_trail_ids][:top_n]
    rows: list[dict[str, Any]] = []
    buckets: dict[str, int] = {
        "overlap_high_confidence": 0,
        "candidate_trail10_only": 0,
        "production_baseline_only": 0,
        "candidate_no_trail10_only": 0,
    }
    for stock_id in selected_ids:
        if stock_id in prod_by_id and stock_id in cand_by_id:
            source = dict(cand_by_id[stock_id])
            bucket = "overlap_high_confidence"
        elif stock_id in cand_by_id and cand_rank[stock_id] <= actionable_top_n:
            source = dict(cand_by_id[stock_id])
            bucket = "candidate_trail10_only"
        elif stock_id in prod_by_id:
            source = dict(prod_by_id[stock_id])
            bucket = "production_baseline_only"
        else:
            source = dict(cand_by_id[stock_id])
            bucket = "candidate_no_trail10_only"
        source["selection_bucket"] = bucket
        source["production_rank"] = str(prod_rank.get(stock_id, ""))
        source["candidate_rank"] = str(cand_rank.get(stock_id, ""))
        rows.append(source)
        buckets[bucket] += 1
    return rows, buckets


def write_ranking(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    for extra in ["selection_bucket", "production_rank", "candidate_rank"]:
        if extra not in fieldnames:
            fieldnames.append(extra)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def build_overlap_rankings(args: argparse.Namespace, selected_dates: list[str], production_files: dict[str, Path], candidate_files: dict[str, Path]) -> dict[str, Any]:
    output_dir = (
        PROJECT_ROOT
        / "artifacts"
        / "backtest"
        / f"overlap_first_rankings_{args.window}_{selected_dates[0]}_{selected_dates[-1]}"
    )
    if output_dir.exists():
        shutil.rmtree(output_dir)
    bucket_totals: dict[str, int] = {}
    overlap_counts: list[int] = []
    for date_text in selected_dates:
        prod_fields, prod_rows = read_rows(production_files[date_text], args.ranking_top_n)
        cand_fields, cand_rows = read_rows(candidate_files[date_text], args.ranking_top_n)
        rows, buckets = ordered_overlap_first(prod_rows, cand_rows, args.actionable_top_n, args.ranking_top_n)
        overlap_counts.append(buckets.get("overlap_high_confidence", 0))
        for key, value in buckets.items():
            bucket_totals[key] = bucket_totals.get(key, 0) + value
        write_ranking(output_dir / f"ranking_{date_text}.csv", merge_fieldnames(cand_fields, prod_fields), rows)
    return {
        "dir": output_dir,
        "ranking_count": len(selected_dates),
        "bucket_totals": bucket_totals,
        "avg_overlap_count": round(sum(overlap_counts) / len(overlap_counts), 6) if overlap_counts else None,
        "min_overlap_count": min(overlap_counts) if overlap_counts else None,
        "max_overlap_count": max(overlap_counts) if overlap_counts else None,
    }


def build_subset_rankings(label: str, selected_dates: list[str], files: dict[str, Path], args: argparse.Namespace) -> Path:
    output_dir = (
        PROJECT_ROOT
        / "artifacts"
        / "backtest"
        / f"{label}_rankings_{args.window}_{selected_dates[0]}_{selected_dates[-1]}"
    )
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for date_text in selected_dates:
        shutil.copy2(files[date_text], output_dir / f"ranking_{date_text}.csv")
    return output_dir


def replay_args(rankings_dir: Path, args: argparse.Namespace, output: Path) -> argparse.Namespace:
    return argparse.Namespace(
        rankings_dir=str(rankings_dir),
        features=args.features,
        horizon=args.horizon,
        top_n=args.top_n,
        entry_delay_trade_days=1,
        max_ranking_files=None,
        initial_cash=args.initial_cash,
        max_gross_exposure=args.max_gross_exposure,
        market_regime_history=None,
        big_bull_gross_exposure=None,
        high_choppy_gross_exposure=None,
        other_family_gross_exposure=None,
        max_position_weight=args.max_position_weight,
        min_shares=1,
        lot_size=1,
        fee_rate=0.001425,
        tax_rate=0.003,
        slippage_rate=0.001,
        stop_loss_pct=args.stop_loss_pct,
        take_profit_pct=None,
        partial_take_profit_pct=None,
        partial_take_profit_fraction=0.5,
        trailing_stop_pct=args.trailing_stop_pct,
        min_event_holding_days=args.min_event_holding_days,
        same_day_hit_priority="stop_loss",
        output=str(output),
    )


def run_replay(label: str, rankings_dir: Path, args: argparse.Namespace, selected_dates: list[str]) -> tuple[Path, dict[str, Any]]:
    output = (
        PROJECT_ROOT
        / "artifacts"
        / "model_experiments"
        / f"odd_lot_portfolio_{label}_overlap_perf_{args.window}_{selected_dates[0]}_{selected_dates[-1]}_{args.date}.json"
    )
    payload = run_odd_lot_portfolio_replay.build_payload(replay_args(rankings_dir, args, output))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    output.with_suffix(".md").write_text(run_odd_lot_portfolio_replay.render_markdown(payload), encoding="utf-8")
    return output, payload


def compact_replay(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary") or {}
    return {
        "path": repo_path(path),
        "total_return": summary.get("total_return"),
        "max_drawdown": summary.get("max_drawdown"),
        "win_rate": summary.get("win_rate"),
        "avg_trade_return": summary.get("avg_trade_return"),
        "trade_count": summary.get("trade_count"),
        "daily_count": summary.get("daily_count"),
        "final_equity": summary.get("final_equity"),
        "avg_cash_weight": summary.get("avg_cash_weight"),
    }


def n(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def compare(overlap: dict[str, Any], production: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "overlap_vs_production": {
            "return_delta": round(n(overlap.get("total_return")) - n(production.get("total_return")), 6),
            "drawdown_delta": round(n(overlap.get("max_drawdown")) - n(production.get("max_drawdown")), 6),
            "win_rate_delta": round(n(overlap.get("win_rate")) - n(production.get("win_rate")), 6),
        },
        "overlap_vs_candidate": {
            "return_delta": round(n(overlap.get("total_return")) - n(candidate.get("total_return")), 6),
            "drawdown_delta": round(n(overlap.get("max_drawdown")) - n(candidate.get("max_drawdown")), 6),
            "win_rate_delta": round(n(overlap.get("win_rate")) - n(candidate.get("win_rate")), 6),
        },
    }


def decision(comparison: dict[str, Any]) -> dict[str, Any]:
    vs_prod = comparison["overlap_vs_production"]
    vs_cand = comparison["overlap_vs_candidate"]
    blockers: list[str] = []
    warnings: list[str] = []
    if vs_prod["return_delta"] <= 0:
        blockers.append("overlap-first does not beat production total return")
    if vs_prod["drawdown_delta"] < 0:
        blockers.append("overlap-first worsens max drawdown versus production")
    if vs_prod["win_rate_delta"] <= 0:
        warnings.append("overlap-first does not improve trade win rate versus production")
    if vs_cand["return_delta"] < 0:
        warnings.append("overlap-first underperforms pure candidate return")
    status = "PROMOTION_REVIEW_CANDIDATE" if not blockers else "MONITOR_ONLY"
    return {
        "status": status,
        "production_switch_ready": False,
        "promotion_ready": False,
        "blockers": blockers,
        "warnings": warnings,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    production_dir = resolve_path(args.production_rankings_dir)
    candidate_dir = resolve_path(args.candidate_rankings_dir)
    production_files = ranking_files(production_dir)
    candidate_files = ranking_files(candidate_dir)
    common_dates = sorted(set(production_files) & set(candidate_files))
    selected_dates = select_dates(common_dates, args.window)
    if not selected_dates:
        raise RuntimeError("沒有可比較 ranking 日期")
    overlap_info = build_overlap_rankings(args, selected_dates, production_files, candidate_files)
    production_subset_dir = build_subset_rankings("production_subset", selected_dates, production_files, args)
    candidate_subset_dir = build_subset_rankings("candidate_subset", selected_dates, candidate_files, args)
    overlap_path, overlap_payload = run_replay("overlap_first", overlap_info["dir"], args, selected_dates)
    production_path, production_payload = run_replay("production", production_subset_dir, args, selected_dates)
    candidate_path, candidate_payload = run_replay("candidate", candidate_subset_dir, args, selected_dates)
    replays = {
        "production": compact_replay(production_path, production_payload),
        "candidate": compact_replay(candidate_path, candidate_payload),
        "overlap_first": compact_replay(overlap_path, overlap_payload),
    }
    comparison = compare(replays["overlap_first"], replays["production"], replays["candidate"])
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK",
        "window": args.window,
        "contract": {
            "research_only": True,
            "uses_existing_rankings_only": True,
            "changes_production_ranking": False,
            "changes_clawd_message": False,
            "changes_model": False,
            "production_switch_ready": False,
            "promotion_ready": False,
        },
        "inputs": {
            "production_rankings_dir": repo_path(production_dir),
            "candidate_rankings_dir": repo_path(candidate_dir),
            "production_subset_rankings_dir": repo_path(production_subset_dir),
            "candidate_subset_rankings_dir": repo_path(candidate_subset_dir),
            "features": repo_path(resolve_path(args.features)),
            "selected_start_date": selected_dates[0],
            "selected_end_date": selected_dates[-1],
            "selected_ranking_days": len(selected_dates),
            "initial_cash": args.initial_cash,
            "top_n": args.top_n,
            "ranking_top_n": args.ranking_top_n,
            "actionable_top_n": args.actionable_top_n,
            "horizon": args.horizon,
            "max_gross_exposure": args.max_gross_exposure,
            "max_position_weight": args.max_position_weight,
            "stop_loss_pct": args.stop_loss_pct,
            "trailing_stop_pct": args.trailing_stop_pct,
            "min_event_holding_days": args.min_event_holding_days,
        },
        "overlap_rankings": {
            "dir": repo_path(overlap_info["dir"]),
            "ranking_count": overlap_info["ranking_count"],
            "bucket_totals": overlap_info["bucket_totals"],
            "avg_overlap_count": overlap_info["avg_overlap_count"],
            "min_overlap_count": overlap_info["min_overlap_count"],
            "max_overlap_count": overlap_info["max_overlap_count"],
        },
        "replays": replays,
        "comparison": comparison,
        "decision": decision(comparison),
    }


def pct(value: Any) -> str:
    if value is None:
        return "--"
    return f"{float(value):.2%}"


def render_markdown(payload: dict[str, Any]) -> str:
    rows = payload["replays"]
    comp = payload["comparison"]["overlap_vs_production"]
    decision_row = payload["decision"]
    lines = [
        "# Overlap-First Recommendation Performance",
        "",
        f"- window: `{payload['window']}`",
        f"- ranking days: `{payload['inputs']['selected_ranking_days']}`",
        f"- date range: `{payload['inputs']['selected_start_date']} ~ {payload['inputs']['selected_end_date']}`",
        f"- decision: `{decision_row['status']}`",
        "",
        "| Variant | Total Return | Max DD | Win Rate | Trades |",
        "|---|---:|---:|---:|---:|",
    ]
    for label in ["production", "candidate", "overlap_first"]:
        row = rows[label]
        lines.append(
            f"| {label} | {pct(row.get('total_return'))} | {pct(row.get('max_drawdown'))} | {pct(row.get('win_rate'))} | {row.get('trade_count')} |"
        )
    lines.extend(
        [
            "",
            "## Delta vs Production",
            "",
            f"- return_delta: `{pct(comp['return_delta'])}`",
            f"- drawdown_delta: `{pct(comp['drawdown_delta'])}`",
            f"- win_rate_delta: `{pct(comp['win_rate_delta'])}`",
            "",
            "## Boundary",
            "",
            "- 不改正式 ranking。",
            "- 不改推播。",
            "- 不改模型。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = (
        resolve_path(args.output)
        if args.output
        else PROJECT_ROOT / "artifacts" / "model_experiments" / f"overlap_first_recommendation_performance_{args.window}_{args.date}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "decision": payload["decision"]["status"],
                "output": repo_path(output),
                "ranking_days": payload["inputs"]["selected_ranking_days"],
                "overlap_vs_production": payload["comparison"]["overlap_vs_production"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
