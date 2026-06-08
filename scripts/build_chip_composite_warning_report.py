#!/usr/bin/env python3
"""測試 chip + price/ranking composite warning。

這份報告只做 research-only replay，不改 ranking、不改模型、不送提醒。
核心問題：外資賣 + 融資增 是否必須搭配價格/排名轉弱才有 warning 價值。
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUN_DATE = datetime.now().strftime("%Y-%m-%d")
SCHEMA_VERSION = "chip-composite-warning-report.v1"
HORIZONS = (3, 5, 10)
GROUPS = ("COMPOSITE_RISK", "CHIP_RISK_ONLY", "TECH_WEAK_ONLY", "NO_COMPOSITE_RISK")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build chip composite warning replay")
    parser.add_argument("--chip-csv", default="data/raw/chip/chip_flow_materialized_top3_60d_2026-06-07.csv")
    parser.add_argument(
        "--rankings-dir",
        default="artifacts/backtest/historical_rankings_current_model_half_year_dense_2025-11-17_2026-05-15",
    )
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument("--top-n", type=int, default=3)
    parser.add_argument(
        "--output",
        default=f"artifacts/model_experiments/chip_composite_warning_report_{RUN_DATE}.json",
    )
    parser.add_argument("--markdown-output", default=None)
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


def ranking_files(rankings_dir: Path) -> list[Path]:
    return sorted(
        [path for path in rankings_dir.glob("ranking_*.csv") if re.match(r"ranking_\d{4}-\d{2}-\d{2}\.csv$", path.name)],
        key=ranking_date,
    )


def read_ranking(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_chip(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, parse_dates=["date"], dtype={"stock_id": str})
    frame["stock_id"] = frame["stock_id"].astype(str).str.zfill(4)
    return frame.sort_values(["stock_id", "date"])


def load_features(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    frame = frame.copy()
    frame["stock_id"] = frame["stock_id"].astype(str).str.zfill(4)
    frame["_date"] = pd.to_datetime(frame["date"]).dt.date
    return frame.sort_values(["stock_id", "_date"])


def latest_feature_rows(features: pd.DataFrame, target_date: str) -> dict[str, dict[str, Any]]:
    target = datetime.fromisoformat(target_date).date()
    latest = features[features["_date"] <= target].groupby("stock_id", sort=False).tail(1)
    return {str(row["stock_id"]).zfill(4): row.to_dict() for _, row in latest.iterrows()}


def build_price_index(features: pd.DataFrame) -> dict[str, list[tuple[Any, float]]]:
    result: dict[str, list[tuple[Any, float]]] = {}
    for stock_id, group in features.groupby("stock_id", sort=False):
        rows = []
        for _, row in group.iterrows():
            close = row.get("close")
            if pd.notna(close):
                rows.append((row["_date"], float(close)))
        result[str(stock_id).zfill(4)] = rows
    return result


def close_on_or_before(price_index: dict[str, list[tuple[Any, float]]], stock_id: str, target_date: str, offset: int = 0) -> float | None:
    rows = price_index.get(str(stock_id).zfill(4)) or []
    target = datetime.fromisoformat(target_date).date()
    valid = [(date_value, close) for date_value, close in rows if date_value <= target]
    if not valid or len(valid) <= offset:
        return None
    return valid[-1 - offset][1]


def trailing_return(price_index: dict[str, list[tuple[Any, float]]], stock_id: str, target_date: str, lookback: int) -> float | None:
    latest = close_on_or_before(price_index, stock_id, target_date, 0)
    earlier = close_on_or_before(price_index, stock_id, target_date, lookback)
    if latest is None or earlier is None or earlier <= 0:
        return None
    return round((latest / earlier) - 1, 6)


def forward_return(price_index: dict[str, list[tuple[Any, float]]], stock_id: str, target_date: str, horizon: int) -> float | None:
    rows = price_index.get(str(stock_id).zfill(4)) or []
    target = datetime.fromisoformat(target_date).date()
    start_index = next((index for index, (date_value, _) in enumerate(rows) if date_value >= target), None)
    if start_index is None or start_index + horizon >= len(rows):
        return None
    start_close = rows[start_index][1]
    end_close = rows[start_index + horizon][1]
    if start_close <= 0:
        return None
    return round((end_close / start_close) - 1, 6)


def chip_metrics(chip: pd.DataFrame, stock_id: str, target_date: str, window_rows: int = 5) -> dict[str, Any] | None:
    required = [
        "foreign_buy",
        "trust_buy",
        "dealer_buy",
        "margin_purchase_balance_change",
        "margin_purchase_today_balance",
        "short_sale_balance_change",
        "short_sale_today_balance",
    ]
    rows = chip[
        (chip["stock_id"] == str(stock_id).zfill(4))
        & (chip["date"] <= pd.to_datetime(target_date))
    ].tail(window_rows)
    rows = rows.dropna(subset=required)
    if rows.empty:
        return None
    latest = rows.iloc[-1]
    return {
        "foreign_5d": int(rows["foreign_buy"].sum()),
        "trust_5d": int(rows["trust_buy"].sum()),
        "dealer_5d": int(rows["dealer_buy"].sum()),
        "margin_5d": int(rows["margin_purchase_balance_change"].sum()),
        "short_5d": int(rows["short_sale_balance_change"].sum()),
        "foreign_latest": int(latest["foreign_buy"]),
        "margin_latest_change": int(latest["margin_purchase_balance_change"]),
    }


def parse_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(parsed) else parsed


def build_rank_index(files: list[Path]) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for path in files:
        date_text = ranking_date(path)
        result[date_text] = {}
        for rank, row in enumerate(read_ranking(path), start=1):
            result[date_text][str(row.get("stock_id", "")).zfill(4)] = rank
    return result


def previous_date(dates: list[str], date_text: str) -> str | None:
    index = dates.index(date_text)
    return dates[index - 1] if index > 0 else None


def classify(metrics: dict[str, Any], feature_row: dict[str, Any] | None, rank_delta: int | None, trail_5d: float | None) -> tuple[str, list[str]]:
    signals: list[str] = []
    chip_risk = metrics["foreign_5d"] < 0 and metrics["margin_5d"] > 0
    if metrics["foreign_5d"] < 0:
        signals.append("foreign_5d_sell")
    if metrics["margin_5d"] > 0:
        signals.append("margin_5d_up")

    close = parse_float(feature_row.get("close")) if feature_row else None
    ma10 = parse_float(feature_row.get("ma10")) if feature_row else None
    ma20 = parse_float(feature_row.get("ma20")) if feature_row else None
    long_upper_shadow = bool(feature_row.get("long_upper_shadow")) if feature_row else False
    price_weak = False
    if close is not None and ma10 is not None and close < ma10:
        signals.append("close_below_ma10")
        price_weak = True
    if close is not None and ma20 is not None and close < ma20:
        signals.append("close_below_ma20")
        price_weak = True
    if trail_5d is not None and trail_5d <= 0:
        signals.append("trailing_5d_nonpositive")
        price_weak = True
    if long_upper_shadow:
        signals.append("long_upper_shadow")
        price_weak = True

    rank_weak = rank_delta is not None and rank_delta <= -2
    if rank_weak:
        signals.append("rank_worsened_2plus")

    tech_weak = price_weak or rank_weak
    if chip_risk and tech_weak:
        return "COMPOSITE_RISK", signals
    if chip_risk:
        return "CHIP_RISK_ONLY", signals
    if tech_weak:
        return "TECH_WEAK_ONLY", signals
    return "NO_COMPOSITE_RISK", signals


def summarize(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "avg_return": None, "median_return": None, "negative_rate": None, "loss_gt_5pct_rate": None}
    return {
        "count": len(values),
        "avg_return": round(sum(values) / len(values), 6),
        "median_return": round(float(median(values)), 6),
        "negative_rate": round(sum(1 for value in values if value < 0) / len(values), 6),
        "loss_gt_5pct_rate": round(sum(1 for value in values if value <= -0.05) / len(values), 6),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    chip_path = resolve_path(args.chip_csv)
    rankings_dir = resolve_path(args.rankings_dir)
    features_path = resolve_path(args.features)
    chip = load_chip(chip_path)
    features = load_features(features_path)
    price_index = build_price_index(features)
    files = ranking_files(rankings_dir)
    rank_index = build_rank_index(files)
    dates = [ranking_date(path) for path in files]
    chip_dates = {str(item) for item in chip["date"].dt.date.unique()}
    target_files = [path for path in files if ranking_date(path) in chip_dates]

    by_group_horizon: dict[str, dict[int, list[float]]] = {group: {horizon: [] for horizon in HORIZONS} for group in GROUPS}
    group_counts: Counter[str] = Counter()
    signal_counts: Counter[str] = Counter()
    observations: list[dict[str, Any]] = []

    for path in target_files:
        date_text = ranking_date(path)
        prev_date = previous_date(dates, date_text)
        latest_features = latest_feature_rows(features, date_text)
        for rank, row in enumerate(read_ranking(path)[: args.top_n], start=1):
            stock_id = str(row.get("stock_id", "")).zfill(4)
            metrics = chip_metrics(chip, stock_id, date_text)
            if not metrics:
                continue
            prev_rank = rank_index.get(prev_date or "", {}).get(stock_id)
            rank_delta = prev_rank - rank if prev_rank is not None else None
            trail_5d = trailing_return(price_index, stock_id, date_text, lookback=5)
            group, signals = classify(metrics, latest_features.get(stock_id), rank_delta, trail_5d)
            group_counts[group] += 1
            signal_counts.update(signals)
            returns: dict[str, float] = {}
            for horizon in HORIZONS:
                value = forward_return(price_index, stock_id, date_text, horizon)
                if value is not None:
                    returns[str(horizon)] = value
                    by_group_horizon[group][horizon].append(value)
            observations.append(
                {
                    "date": date_text,
                    "stock_id": stock_id,
                    "stock_name": row.get("stock_name"),
                    "rank": rank,
                    "previous_rank": prev_rank,
                    "rank_delta": rank_delta,
                    "trailing_return_5d": trail_5d,
                    "group": group,
                    "signals": signals,
                    "chip_metrics": metrics,
                    "forward_returns": returns,
                }
            )

    group_outcomes = {
        group: {str(horizon): summarize(values) for horizon, values in horizons.items()}
        for group, horizons in by_group_horizon.items()
    }
    composite = group_outcomes["COMPOSITE_RISK"]["5"]
    no_risk = group_outcomes["NO_COMPOSITE_RISK"]["5"]
    tech_weak = group_outcomes["TECH_WEAK_ONLY"]["5"]
    composite_useful = (
        composite["count"] >= 10
        and no_risk["count"] >= 10
        and composite["avg_return"] is not None
        and no_risk["avg_return"] is not None
        and composite["avg_return"] < no_risk["avg_return"]
        and composite["negative_rate"] is not None
        and no_risk["negative_rate"] is not None
        and composite["negative_rate"] > no_risk["negative_rate"]
    )
    tech_dominates = (
        tech_weak["count"] >= 10
        and no_risk["count"] >= 10
        and tech_weak["avg_return"] is not None
        and no_risk["avg_return"] is not None
        and tech_weak["avg_return"] < no_risk["avg_return"]
        and tech_weak["negative_rate"] is not None
        and no_risk["negative_rate"] is not None
        and tech_weak["negative_rate"] > no_risk["negative_rate"]
    )
    if composite_useful:
        decision_status = "COMPOSITE_MONITOR_ONLY"
        primary_read = "chip + 價格/排名轉弱 composite 對 5D 有方向性，但仍只可研究監控。"
    elif tech_dominates:
        decision_status = "TECH_WEAKNESS_DOMINATES"
        primary_read = "目前技術/排名轉弱比單純 chip composite 更像主要訊號；chip 只能當輔助。"
    else:
        decision_status = "NOT_STABLE_ENOUGH_FOR_WARNING_CHANNEL"
        primary_read = "composite warning 尚未穩定；本次樣本沒有證明 chip + 價格/排名轉弱可作正式提醒。"

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK",
        "contract": {
            "research_only": True,
            "warning_only": True,
            "changes_model": False,
            "changes_production_ranking": False,
            "changes_risk_adjusted_score": False,
            "does_not_send_push": True,
        },
        "inputs": {
            "chip_csv": repo_path(chip_path),
            "rankings_dir": repo_path(rankings_dir),
            "features": repo_path(features_path),
            "top_n": args.top_n,
        },
        "summary": {
            "observation_count": len(observations),
            "target_date_count": len({item["date"] for item in observations}),
            "group_counts": dict(group_counts),
            "signal_counts": dict(signal_counts),
            "group_outcomes": group_outcomes,
        },
        "decision": {
            "status": decision_status,
            "production_status": "BLOCKED",
            "primary_read": primary_read,
            "next_step": "若要繼續，應擴到 Top10/Top20 並測更嚴格的 price/rank weakening 門檻。",
        },
        "observations_sample": observations[:120],
    }


def pct(value: Any) -> str:
    if value is None:
        return "--"
    return f"{float(value):.2%}"


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Chip Composite Warning Report",
        "",
        f"- status: `{payload['status']}`",
        f"- decision: `{payload['decision']['status']}`",
        f"- production_status: `{payload['decision']['production_status']}`",
        "",
        "## Primary Read",
        "",
        payload["decision"]["primary_read"],
        "",
        "## Summary",
        "",
        f"- observation_count: `{summary['observation_count']}`",
        f"- target_date_count: `{summary['target_date_count']}`",
        f"- group_counts: `{summary['group_counts']}`",
        "",
        "| group | 3D avg | 5D avg | 10D avg | 5D negative | count 5D |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for group in GROUPS:
        row = summary["group_outcomes"][group]
        h3 = row["3"]
        h5 = row["5"]
        h10 = row["10"]
        lines.append(
            f"| `{group}` | {pct(h3['avg_return'])} | {pct(h5['avg_return'])} | {pct(h10['avg_return'])} | "
            f"{pct(h5['negative_rate'])} | {h5['count']} |"
        )
    lines.extend(["", "## Next Step", "", f"- {payload['decision']['next_step']}"])
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    output_path = resolve_path(args.output)
    markdown_path = resolve_path(args.markdown_output) if args.markdown_output else output_path.with_suffix(".md")
    payload = build_payload(args)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    markdown_path.write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "decision": payload["decision"]["status"],
                "output": repo_path(output_path),
                "markdown": repo_path(markdown_path),
                "observation_count": payload["summary"]["observation_count"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
