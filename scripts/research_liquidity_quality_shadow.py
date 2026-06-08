#!/usr/bin/env python3
"""流動性品質 shadow ranking 研究。

把 3000 萬保留為最低可交易 gate，並測試 percentile / log liquidity score
會如何改變既有 ranking artifact 內的候選排序。此腳本只輸出 shadow artifact，
不覆蓋正式 ranking、不改 risk_adjusted_score、不改模型。
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


SCHEMA_VERSION = "liquidity-quality-shadow.v1"
VARIANTS = ["production", "percentile_gate", "log_gate"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="research liquidity quality shadow ranking")
    parser.add_argument("--rankings-dir", default="artifacts")
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument("--date-from", default="2026-05-26")
    parser.add_argument("--date-to", default="2026-06-02")
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--tradability-threshold", type=float, default=30_000_000.0)
    parser.add_argument("--log-full-score-value", type=float, default=500_000_000.0)
    parser.add_argument("--output", default="artifacts/liquidity_quality_shadow_2026-06-03.json")
    parser.add_argument("--shadow-ranking-dir", default="artifacts/backtest/liquidity_quality_shadow_rankings_2026-06-03")
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
    match = re.match(r"ranking_(\d{4}-\d{2}-\d{2})\.csv$", path.name)
    if not match:
        raise ValueError(f"ranking 檔名無法解析日期：{path}")
    return match.group(1)


def ranking_files(rankings_dir: Path, date_from: str, date_to: str) -> list[Path]:
    files = []
    for path in rankings_dir.glob("ranking_*.csv"):
        if not re.match(r"ranking_\d{4}-\d{2}-\d{2}\.csv$", path.name):
            continue
        date_text = ranking_date(path)
        if date_from <= date_text <= date_to:
            files.append(path)
    return sorted(files, key=ranking_date)


def read_ranking(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    result = []
    for index, row in enumerate(rows, start=1):
        normalized = dict(row)
        normalized["production_rank"] = index
        normalized["stock_id"] = str(row.get("stock_id", "")).strip().zfill(4)
        result.append(normalized)
    return result


def numeric(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return default if math.isnan(parsed) else parsed


def load_feature_frame(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"features 不存在：{path}")
    frame = pd.read_parquet(path, columns=["date", "stock_id", "avg_value_20d", "close", "open", "high", "low"])
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    frame["date_text"] = frame["date"].astype(str)
    frame["stock_id"] = frame["stock_id"].astype(str).str.zfill(4)
    frame["avg_value_20d"] = pd.to_numeric(frame["avg_value_20d"], errors="coerce")
    return frame


def feature_lookup(frame: pd.DataFrame) -> dict[tuple[str, str], dict[str, Any]]:
    lookup: dict[tuple[str, str], dict[str, Any]] = {}
    for row in frame.itertuples(index=False):
        lookup[(str(row.date_text), str(row.stock_id))] = {
            "avg_value_20d": None if pd.isna(row.avg_value_20d) else float(row.avg_value_20d),
            "open": none_if_nan(row.open),
            "high": none_if_nan(row.high),
            "low": none_if_nan(row.low),
            "close": none_if_nan(row.close),
        }
    return lookup


def none_if_nan(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(parsed) else parsed


def daily_liquidity_percentiles(frame: pd.DataFrame, threshold: float) -> dict[tuple[str, str], float]:
    result: dict[tuple[str, str], float] = {}
    for date_text, group in frame.groupby("date_text", sort=False):
        tradable = group[group["avg_value_20d"].fillna(0) >= threshold].copy()
        if tradable.empty:
            continue
        ranks = tradable["avg_value_20d"].rank(method="average", pct=True)
        for stock_id, pct in zip(tradable["stock_id"], ranks, strict=False):
            result[(str(date_text), str(stock_id).zfill(4))] = float(pct)
    return result


def log_liquidity_score(value: float, threshold: float, full_score_value: float) -> float:
    if value < threshold:
        return 0.0
    lower = math.log1p(threshold)
    upper = math.log1p(max(full_score_value, threshold + 1))
    raw = (math.log1p(value) - lower) / (upper - lower)
    return max(0.5, min(1.0, 0.5 + 0.5 * raw))


def enrich_rows(
    rows: list[dict[str, Any]],
    date_text: str,
    lookup: dict[tuple[str, str], dict[str, Any]],
    percentiles: dict[tuple[str, str], float],
    threshold: float,
    log_full_score_value: float,
) -> list[dict[str, Any]]:
    enriched = []
    for row in rows:
        stock_id = str(row["stock_id"]).zfill(4)
        feature = lookup.get((date_text, stock_id), {})
        avg_value = feature.get("avg_value_20d")
        avg_value_num = numeric(avg_value, 0.0)
        percentile = percentiles.get((date_text, stock_id))
        production_quality = numeric(row.get("quality_score"), 0.5)
        percentile_quality = 0.0 if avg_value_num < threshold else 0.5 + 0.5 * numeric(percentile, 0.0)
        log_quality = log_liquidity_score(avg_value_num, threshold, log_full_score_value)
        base = numeric(row.get("prediction_score")) + numeric(row.get("setup_score")) - numeric(row.get("risk_penalty"))
        enriched.append(
            {
                **row,
                "avg_value_20d": avg_value_num,
                "liquidity_gate_pass": avg_value_num >= threshold,
                "production_quality_score": production_quality,
                "percentile_liquidity_score": round(percentile_quality, 6),
                "log_liquidity_score": round(log_quality, 6),
                "production_shadow_score": numeric(row.get("risk_adjusted_score")),
                "percentile_gate_shadow_score": max(0.0, base + percentile_quality) if avg_value_num >= threshold else -1.0,
                "log_gate_shadow_score": max(0.0, base + log_quality) if avg_value_num >= threshold else -1.0,
            }
        )
    return enriched


def sort_variant(rows: list[dict[str, Any]], variant: str) -> list[dict[str, Any]]:
    if variant == "production":
        key = "production_shadow_score"
    elif variant == "percentile_gate":
        key = "percentile_gate_shadow_score"
    elif variant == "log_gate":
        key = "log_gate_shadow_score"
    else:
        raise ValueError(f"未知 variant：{variant}")
    sorted_rows = sorted(rows, key=lambda item: (numeric(item.get(key), -1.0), -int(item.get("production_rank") or 9999)), reverse=True)
    return sorted_rows


def top_items(rows: list[dict[str, Any]], variant: str, top_n: int) -> list[dict[str, Any]]:
    key_map = {
        "production": "production_shadow_score",
        "percentile_gate": "percentile_gate_shadow_score",
        "log_gate": "log_gate_shadow_score",
    }
    key = key_map[variant]
    quality_key = {
        "production": "production_quality_score",
        "percentile_gate": "percentile_liquidity_score",
        "log_gate": "log_liquidity_score",
    }[variant]
    result = []
    for rank, row in enumerate(sort_variant(rows, variant)[:top_n], start=1):
        result.append(
            {
                "rank": rank,
                "production_rank": row.get("production_rank"),
                "stock_id": row.get("stock_id"),
                "stock_name": row.get("stock_name"),
                "score": round(numeric(row.get(key)), 6),
                "production_score": round(numeric(row.get("production_shadow_score")), 6),
                "rank_delta_vs_production": int(row.get("production_rank") or rank) - rank,
                "avg_value_20d": round(numeric(row.get("avg_value_20d")), 2),
                "production_quality_score": round(numeric(row.get("production_quality_score")), 6),
                "percentile_liquidity_score": row.get("percentile_liquidity_score"),
                "log_liquidity_score": row.get("log_liquidity_score"),
                "liquidity_gate_pass": row.get("liquidity_gate_pass"),
                "model_prob": numeric(row.get("model_prob")),
                "final_score": numeric(row.get("final_score")),
                "setup_score": numeric(row.get("setup_score")),
                "quality_score": round(numeric(row.get(quality_key)), 6),
                "risk_penalty": numeric(row.get("risk_penalty")),
                "risk_adjusted_score": round(numeric(row.get(key)), 6),
                "suggested_weight": row.get("suggested_weight"),
                "max_position_weight": row.get("max_position_weight"),
                "gross_exposure": row.get("gross_exposure"),
            }
        )
    return result


def write_shadow_csv(path: Path, rows: list[dict[str, Any]], variant: str, top_n: int) -> None:
    items = top_items(rows, variant, top_n)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "rank",
        "production_rank",
        "rank_delta_vs_production",
        "stock_id",
        "stock_name",
        "score",
        "production_score",
        "avg_value_20d",
        "production_quality_score",
        "percentile_liquidity_score",
        "log_liquidity_score",
        "liquidity_gate_pass",
        "model_prob",
        "final_score",
        "setup_score",
        "quality_score",
        "risk_penalty",
        "risk_adjusted_score",
        "suggested_weight",
        "max_position_weight",
        "gross_exposure",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(items)


def compact_stats(items: list[dict[str, Any]]) -> dict[str, Any]:
    values = [numeric(item.get("avg_value_20d")) for item in items]
    return {
        "avg_avg_value_20d": round(sum(values) / len(values), 2) if values else None,
        "median_avg_value_20d": round(float(median(values)), 2) if values else None,
        "min_avg_value_20d": round(min(values), 2) if values else None,
        "gate_fail_count": sum(1 for item in items if not item.get("liquidity_gate_pass")),
    }


def next_trade_dates(trade_dates: list[date], source: date, horizon: int) -> list[date] | None:
    future = [item for item in trade_dates if item > source]
    if len(future) < horizon:
        return None
    return future[:horizon]


def forward_return(
    date_text: str,
    items: list[dict[str, Any]],
    lookup: dict[tuple[str, str], dict[str, Any]],
    trade_dates: list[date],
    horizon: int,
) -> dict[str, Any]:
    source = datetime.fromisoformat(date_text).date()
    dates = next_trade_dates(trade_dates, source, horizon)
    if dates is None:
        return {"available": False, "horizon": horizon, "reason": "insufficient_future_bars"}
    entry_date = dates[0].isoformat()
    exit_date = dates[-1].isoformat()
    returns = []
    for item in items:
        stock_id = str(item["stock_id"]).zfill(4)
        entry = lookup.get((entry_date, stock_id), {}).get("open")
        exit_close = lookup.get((exit_date, stock_id), {}).get("close")
        if entry is None or exit_close is None or entry <= 0:
            continue
        returns.append(float(exit_close) / float(entry) - 1)
    if not returns:
        return {"available": False, "horizon": horizon, "reason": "no_complete_bars"}
    return {
        "available": True,
        "horizon": horizon,
        "entry_date": entry_date,
        "exit_date": exit_date,
        "trade_count": len(returns),
        "avg_return": round(sum(returns) / len(returns), 6),
        "hit_rate": round(sum(value > 0 for value in returns) / len(returns), 6),
    }


def date_analysis(
    path: Path,
    args: argparse.Namespace,
    lookup: dict[tuple[str, str], dict[str, Any]],
    percentiles: dict[tuple[str, str], float],
    trade_dates: list[date],
    shadow_dir: Path,
) -> dict[str, Any]:
    date_text = ranking_date(path)
    rows = enrich_rows(
        read_ranking(path),
        date_text=date_text,
        lookup=lookup,
        percentiles=percentiles,
        threshold=args.tradability_threshold,
        log_full_score_value=args.log_full_score_value,
    )
    variant_items = {variant: top_items(rows, variant, args.top_n) for variant in VARIANTS}
    for variant in VARIANTS:
        write_shadow_csv(shadow_dir / variant / f"ranking_{date_text}.csv", rows, variant, args.top_n)
    production_ids = {item["stock_id"] for item in variant_items["production"]}
    variants = {}
    for variant, items in variant_items.items():
        ids = {item["stock_id"] for item in items}
        variants[variant] = {
            "items": items,
            "stats": compact_stats(items),
            "overlap_with_production": len(ids & production_ids),
            "overlap_rate_with_production": round(len(ids & production_ids) / args.top_n, 6),
            "top1_changed": items[0]["stock_id"] != variant_items["production"][0]["stock_id"] if items and variant_items["production"] else False,
            "forward_returns": {
                str(horizon): forward_return(date_text, items, lookup, trade_dates, horizon)
                for horizon in [1, 3, 5]
            },
        }
    return {
        "date": date_text,
        "source_ranking": repo_path(path),
        "source_candidate_rows": len(rows),
        "variants": variants,
    }


def summarize_dates(dates: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {"date_count": len(dates), "variants": {}}
    for variant in VARIANTS:
        variant_rows = [item["variants"][variant] for item in dates]
        overlap_rates = [numeric(row.get("overlap_rate_with_production")) for row in variant_rows]
        top1_changes = [bool(row.get("top1_changed")) for row in variant_rows]
        avg_values = [numeric(row.get("stats", {}).get("avg_avg_value_20d")) for row in variant_rows]
        fwd = []
        for row in variant_rows:
            ret = row.get("forward_returns", {}).get("1", {})
            if ret.get("available"):
                fwd.append(numeric(ret.get("avg_return")))
        summary["variants"][variant] = {
            "avg_overlap_rate_with_production": round(sum(overlap_rates) / len(overlap_rates), 6) if overlap_rates else None,
            "top1_change_count": sum(top1_changes),
            "avg_top10_avg_value_20d": round(sum(avg_values) / len(avg_values), 2) if avg_values else None,
            "available_1d_forward_days": len(fwd),
            "avg_1d_forward_return_if_available": round(sum(fwd) / len(fwd), 6) if fwd else None,
        }
    return summary


def decision(summary: dict[str, Any]) -> dict[str, Any]:
    percentile = summary["variants"].get("percentile_gate", {})
    log_gate = summary["variants"].get("log_gate", {})
    production = summary["variants"].get("production", {})
    candidates = []
    for name, row in [("percentile_gate", percentile), ("log_gate", log_gate)]:
        overlap = numeric(row.get("avg_overlap_rate_with_production"))
        top1_change_count = int(row.get("top1_change_count") or 0)
        fwd_delta = numeric(row.get("avg_1d_forward_return_if_available")) - numeric(
            production.get("avg_1d_forward_return_if_available")
        )
        if overlap >= 0.6 and top1_change_count <= max(2, int(summary["date_count"] * 0.5)) and fwd_delta >= -0.01:
            candidates.append(name)
    return {
        "status": "READY_FOR_REPLAY_EXTENSION" if candidates else "MONITOR_ONLY",
        "shadow_candidates": candidates,
        "production_ready": False,
        "reason": "只完成 ranking 差異與可用 forward return 初檢；尚未接正式 risk_adjusted_score。",
        "next_step": "run portfolio replay on selected shadow ranking directories" if candidates else "keep as diagnostics",
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    rankings_dir = resolve_path(args.rankings_dir)
    features_path = resolve_path(args.features)
    shadow_dir = resolve_path(args.shadow_ranking_dir)
    features = load_feature_frame(features_path)
    lookup = feature_lookup(features)
    percentiles = daily_liquidity_percentiles(features, args.tradability_threshold)
    trade_dates = sorted(features["date"].dropna().unique())
    files = ranking_files(rankings_dir, args.date_from, args.date_to)
    dates = [
        date_analysis(path, args, lookup=lookup, percentiles=percentiles, trade_dates=trade_dates, shadow_dir=shadow_dir)
        for path in files
    ]
    summary = summarize_dates(dates)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK" if dates else "FAILED",
        "contract": {
            "research_only": True,
            "changes_production_ranking": False,
            "changes_risk_adjusted_score": False,
            "changes_model": False,
            "source_ranking_scope": "existing ranking artifact rows only; cannot introduce candidates absent from source ranking CSV",
            "tradability_gate_preserved": True,
        },
        "inputs": {
            "rankings_dir": repo_path(rankings_dir),
            "features": repo_path(features_path),
            "date_from": args.date_from,
            "date_to": args.date_to,
            "top_n": args.top_n,
            "tradability_threshold": args.tradability_threshold,
            "log_full_score_value": args.log_full_score_value,
            "shadow_ranking_dir": repo_path(shadow_dir),
        },
        "summary": summary,
        "decision": decision(summary),
        "dates": dates,
    }


def pct(value: Any) -> str:
    try:
        return f"{float(value):.2%}"
    except (TypeError, ValueError):
        return "--"


def money(value: Any) -> str:
    try:
        return f"{float(value):,.0f}"
    except (TypeError, ValueError):
        return "--"


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Liquidity Quality Shadow",
        "",
        f"- status: `{payload['status']}`",
        f"- decision: `{payload['decision']['status']}`",
        f"- production_ready: `{payload['decision']['production_ready']}`",
        f"- source_scope: `{payload['contract']['source_ranking_scope']}`",
        "",
        "## Summary",
        "",
        "| variant | avg overlap | top1 changes | avg top10 value | 1D days | avg 1D return |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for variant, row in payload["summary"].get("variants", {}).items():
        lines.append(
            f"| {variant} | {pct(row.get('avg_overlap_rate_with_production'))} | {row.get('top1_change_count')} | {money(row.get('avg_top10_avg_value_20d'))} | {row.get('available_1d_forward_days')} | {pct(row.get('avg_1d_forward_return_if_available'))} |"
        )
    lines.extend(["", "## Daily Top1 Changes", ""])
    for item in payload.get("dates", []):
        prod = item["variants"]["production"]["items"][0]
        percentile = item["variants"]["percentile_gate"]["items"][0]
        log_gate = item["variants"]["log_gate"]["items"][0]
        lines.append(
            f"- {item['date']}: production `{prod['stock_id']}`; percentile `{percentile['stock_id']}`; log `{log_gate['stock_id']}`"
        )
    lines.extend(["", "## Decision", "", json.dumps(payload["decision"], ensure_ascii=False, indent=2), ""])
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
            {
                "status": payload["status"],
                "output": repo_path(output),
                "decision": payload["decision"]["status"],
                "shadow_candidates": payload["decision"]["shadow_candidates"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
