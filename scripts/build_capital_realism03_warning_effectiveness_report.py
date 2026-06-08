#!/usr/bin/env python3
"""用半年歷史 replay 驗證近 7 日 Top10 warning-only 訊號。"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

import pandas as pd

from build_recent_top10_watchlist_warning import build_stock_item, ranking_date, read_ranking, select_window


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "capital-realism03-warning-effectiveness.v1"
RUN_DATE = "2026-06-05"
HORIZONS = (1, 3, 5, 10)
LEVELS = ("WATCH", "WEAKENING", "RISK_ALERT")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build CAPITAL-REALISM-03 warning effectiveness report")
    parser.add_argument(
        "--rankings-dir",
        default="artifacts/backtest/historical_rankings_current_model_half_year_dense_2025-11-17_2026-05-15",
    )
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument("--watchlist-ranking-days", type=int, default=7)
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--min-target-dates", type=int, default=80)
    parser.add_argument(
        "--output",
        default=f"artifacts/model_experiments/capital_realism03_warning_effectiveness_report_{RUN_DATE}.json",
    )
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def ranking_files(rankings_dir: Path) -> list[Path]:
    files = sorted(
        [path for path in rankings_dir.glob("ranking_*.csv") if re.match(r"ranking_\d{4}-\d{2}-\d{2}\.csv$", path.name)],
        key=lambda path: ranking_date(path),
    )
    if not files:
        raise FileNotFoundError(f"找不到 ranking_*.csv：{rankings_dir}")
    return files


def load_features(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"features parquet 不存在：{path}")
    frame = pd.read_parquet(path)
    date_column = "trade_date" if "trade_date" in frame.columns else "date"
    if date_column not in frame.columns:
        raise RuntimeError("features parquet 缺少 date/trade_date 欄位")
    frame = frame.copy()
    frame["stock_id"] = frame["stock_id"].astype(str).str.zfill(4)
    frame["_date"] = pd.to_datetime(frame[date_column]).dt.date
    frame = frame.sort_values(["stock_id", "_date"])
    return frame


def latest_rows_by_stock(frame: pd.DataFrame, target_date: str) -> dict[str, dict[str, Any]]:
    target = datetime.fromisoformat(target_date).date()
    latest = frame[frame["_date"] <= target].groupby("stock_id", sort=False).tail(1)
    return {str(row["stock_id"]).zfill(4): row.to_dict() for _, row in latest.iterrows()}


def build_price_index(frame: pd.DataFrame) -> dict[str, list[tuple[Any, float]]]:
    result: dict[str, list[tuple[Any, float]]] = {}
    for stock_id, group in frame.groupby("stock_id", sort=False):
        rows = []
        for _, row in group.iterrows():
            close = row.get("close")
            if pd.notna(close):
                rows.append((row["_date"], float(close)))
        result[str(stock_id).zfill(4)] = rows
    return result


def forward_return(price_index: dict[str, list[tuple[Any, float]]], stock_id: str, target_date: str, horizon: int) -> float | None:
    rows = price_index.get(str(stock_id).zfill(4)) or []
    target = datetime.fromisoformat(target_date).date()
    start_index = next((index for index, (date_value, _) in enumerate(rows) if date_value >= target), None)
    if start_index is None:
        return None
    end_index = start_index + horizon
    if end_index >= len(rows):
        return None
    start_close = rows[start_index][1]
    end_close = rows[end_index][1]
    if start_close <= 0:
        return None
    return round((end_close / start_close) - 1, 6)


def build_items_for_date(files: list[Path], target_index: int, features: pd.DataFrame, watchlist_days: int, top_n: int) -> list[dict[str, Any]]:
    window = select_window(files[: target_index + 1], target_date=ranking_date(files[target_index]), days=watchlist_days)
    target_date = ranking_date(window[-1])
    latest_by_stock = latest_rows_by_stock(features, target_date)
    history_by_stock: dict[str, list[dict[str, Any]]] = {}
    for path in window:
        for row in read_ranking(path, top_n=top_n):
            history_by_stock.setdefault(row["stock_id"], []).append(row)
    return [
        build_stock_item(stock_id, history=history, latest_by_stock=latest_by_stock, target_date=target_date)
        for stock_id, history in sorted(history_by_stock.items(), key=lambda item: (-len(item[1]), item[1][-1]["rank"], item[0]))
    ]


def mean(values: list[float]) -> float | None:
    return None if not values else round(sum(values) / len(values), 6)


def rate(values: list[float], predicate: Any) -> float | None:
    return None if not values else round(sum(1 for value in values if predicate(value)) / len(values), 6)


def summarize_values(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "avg_return": None, "median_return": None, "negative_rate": None, "loss_gt_5pct_rate": None}
    return {
        "count": len(values),
        "avg_return": mean(values),
        "median_return": round(float(median(values)), 6),
        "negative_rate": rate(values, lambda value: value < 0),
        "loss_gt_5pct_rate": rate(values, lambda value: value <= -0.05),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    rankings_dir = resolve_path(args.rankings_dir)
    features_path = resolve_path(args.features)
    files = ranking_files(rankings_dir)
    features = load_features(features_path)
    price_index = build_price_index(features)
    target_indices = range(args.watchlist_ranking_days - 1, len(files) - max(HORIZONS))

    observations: list[dict[str, Any]] = []
    by_level_horizon: dict[str, dict[int, list[float]]] = {
        level: {horizon: [] for horizon in HORIZONS} for level in LEVELS
    }
    signal_counter: Counter[str] = Counter()
    level_counter: Counter[str] = Counter()

    for target_index in target_indices:
        target_date = ranking_date(files[target_index])
        items = build_items_for_date(files, target_index, features, args.watchlist_ranking_days, args.top_n)
        for item in items:
            level = str(item.get("warning_level"))
            level_counter[level] += 1
            signal_counter.update(item.get("signals") or [])
            returns: dict[str, float] = {}
            for horizon in HORIZONS:
                value = forward_return(price_index, item["stock_id"], target_date, horizon)
                if value is not None:
                    returns[str(horizon)] = value
                    if level in by_level_horizon:
                        by_level_horizon[level][horizon].append(value)
            observations.append(
                {
                    "date": target_date,
                    "stock_id": item["stock_id"],
                    "warning_level": level,
                    "latest_in_top10": item.get("latest_in_top10"),
                    "signals": item.get("signals") or [],
                    "forward_returns": returns,
                }
            )

    level_outcomes = {
        level: {str(horizon): summarize_values(values) for horizon, values in by_level_horizon[level].items()}
        for level in LEVELS
    }
    comparisons: dict[str, dict[str, Any]] = {}
    for horizon in HORIZONS:
        watch = level_outcomes["WATCH"][str(horizon)]
        for level in ("WEAKENING", "RISK_ALERT"):
            row = level_outcomes[level][str(horizon)]
            if watch["avg_return"] is None or row["avg_return"] is None:
                avg_delta = None
            else:
                avg_delta = round(float(row["avg_return"]) - float(watch["avg_return"]), 6)
            if watch["negative_rate"] is None or row["negative_rate"] is None:
                neg_delta = None
            else:
                neg_delta = round(float(row["negative_rate"]) - float(watch["negative_rate"]), 6)
            comparisons[f"{level}_vs_WATCH_{horizon}d"] = {
                "avg_return_delta": avg_delta,
                "negative_rate_delta": neg_delta,
                "sample_count": row["count"],
            }

    ten_day_weakening = comparisons["WEAKENING_vs_WATCH_10d"]
    ten_day_alert = comparisons["RISK_ALERT_vs_WATCH_10d"]
    weakening_directional = (
        ten_day_weakening["avg_return_delta"] is not None
        and ten_day_weakening["negative_rate_delta"] is not None
        and ten_day_weakening["avg_return_delta"] < 0
        and ten_day_weakening["negative_rate_delta"] > 0
    )
    alert_directional = (
        ten_day_alert["avg_return_delta"] is not None
        and ten_day_alert["negative_rate_delta"] is not None
        and ten_day_alert["avg_return_delta"] < 0
        and ten_day_alert["negative_rate_delta"] > 0
    )
    if weakening_directional and alert_directional:
        effectiveness = "DIRECTIONALLY_USEFUL_MONITOR_ONLY"
    elif weakening_directional:
        effectiveness = "PARTIAL_WEAKENING_SIGNAL_MONITOR_ONLY"
    else:
        effectiveness = "NOT_STABLE_ENOUGH_FOR_WARNING_CHANNEL"

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
            "watchlist_ranking_days": args.watchlist_ranking_days,
            "top_n": args.top_n,
        },
        "inputs": {
            "rankings_dir": repo_path(rankings_dir),
            "features": repo_path(features_path),
            "ranking_start": ranking_date(files[0]),
            "ranking_end": ranking_date(files[-1]),
            "evaluated_target_dates": len(set(row["date"] for row in observations)),
            "horizons": list(HORIZONS),
        },
        "summary": {
            "observation_count": len(observations),
            "level_counts": dict(level_counter),
            "signal_counts": dict(signal_counter),
            "level_outcomes": level_outcomes,
            "comparisons": comparisons,
        },
        "decision": {
            "status": effectiveness,
            "recommendation_channel": "NO_CHANGE",
            "warning_channel": "RESEARCH_ONLY_NOT_PUSH",
            "primary_read": (
                "近 7 日 Top10 warning 可以作為研究中的非個人化風險層，"
                "但目前只看到 WEAKENING 有方向性；RISK_ALERT 分級還沒有穩定比 WATCH 更差。"
                "所以不能直接變成賣出推播或第二頻道正式訊息。"
            ),
            "next_experiments": [
                "把 warning 規則改成只對近 7 天入榜池輸出，不混入每日推薦訊息。",
                "新增 warning-only dry-run message artifact；不 live send、不分頻，先看文字與名單是否合理。",
                "若要接推播，需另外接第二 target channel，並保證不影響每日 Top10 主流程。",
            ],
        },
        "observations_sample": observations[:100],
    }


def pct(value: Any) -> str:
    if value is None:
        return "--"
    return f"{float(value):.2%}"


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# CAPITAL-REALISM-03 Warning Effectiveness Report",
        "",
        f"- status: `{payload['status']}`",
        f"- decision: `{payload['decision']['status']}`",
        f"- recommendation_channel: `{payload['decision']['recommendation_channel']}`",
        f"- warning_channel: `{payload['decision']['warning_channel']}`",
        "",
        "## 白話結論",
        "",
        payload["decision"]["primary_read"],
        "",
        "## Level Outcomes",
        "",
        "| level | 1D avg | 3D avg | 5D avg | 10D avg | 10D negative | count 10D |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for level in LEVELS:
        outcomes = summary["level_outcomes"][level]
        ten = outcomes["10"]
        lines.append(
            f"| {level} | {pct(outcomes['1']['avg_return'])} | {pct(outcomes['3']['avg_return'])} | "
            f"{pct(outcomes['5']['avg_return'])} | {pct(ten['avg_return'])} | "
            f"{pct(ten['negative_rate'])} | {ten['count']} |"
        )
    lines.extend(
        [
            "",
            "## Comparisons",
            "",
            "```json",
            json.dumps(summary["comparisons"], ensure_ascii=False, indent=2),
            "```",
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
    if payload["inputs"]["evaluated_target_dates"] < args.min_target_dates:
        raise RuntimeError(
            f"evaluated target dates too few: {payload['inputs']['evaluated_target_dates']} < {args.min_target_dates}"
        )
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
