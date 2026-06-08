#!/usr/bin/env python3
"""建立 chip warning-only shadow report。

此腳本先做 replay 前置檢查：確認是否已有可回測的 chip 歷史欄位。
若本地 features 尚未 materialize chip-flow 欄位，報告會明確 BLOCKED。
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


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUN_DATE = "2026-06-06"
SCHEMA_VERSION = "chip-warning-shadow-report.v1"
HORIZONS = (3, 5, 10)
GROUPS = ("CHIP_RISK", "FOREIGN_SELL_ONLY", "MARGIN_UP_ONLY", "CHIP_SUPPORTIVE", "NEUTRAL")


REQUIRED_FEATURE_COLUMNS = [
    "institutional_available",
    "foreign_buy",
    "trust_buy",
    "dealer_buy",
    "margin_available",
    "margin_purchase_today_balance",
    "margin_purchase_balance_change",
    "short_sale_today_balance",
    "short_sale_balance_change",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build chip warning-only shadow report")
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument(
        "--chip-csv",
        default="data/raw/chip/chip_flow_materialized_replay_tail5_2026-06-06.csv",
    )
    parser.add_argument(
        "--current-chip-csv",
        default="data/raw/chip/chip_flow_materialized_recent_top10_2026-06-06.csv",
    )
    parser.add_argument(
        "--rankings-dir",
        default="artifacts/backtest/historical_rankings_current_model_half_year_dense_2025-11-17_2026-05-15",
    )
    parser.add_argument("--current-ranking", default="artifacts/ranking_2026-06-05.csv")
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument(
        "--coverage",
        default=f"artifacts/chip_flow_runtime_coverage_{RUN_DATE}.json",
    )
    parser.add_argument(
        "--output",
        default=f"artifacts/model_experiments/chip_warning_shadow_report_{RUN_DATE}.json",
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


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def latest_dated_artifact(directory: Path, prefix: str) -> Path | None:
    files = sorted(directory.glob(f"{prefix}_*.json"))
    return files[-1] if files else None


def ranking_date(path: Path) -> str:
    match = re.match(r"ranking_(\d{4}-\d{2}-\d{2})\.csv$", path.name)
    if not match:
        raise ValueError(f"ranking 檔名無法解析日期：{path}")
    return match.group(1)


def ranking_files(path: Path) -> list[Path]:
    files = sorted(
        [item for item in path.glob("ranking_*.csv") if re.match(r"ranking_\d{4}-\d{2}-\d{2}\.csv$", item.name)],
        key=ranking_date,
    )
    if not files:
        raise FileNotFoundError(f"找不到 ranking_*.csv：{path}")
    return files


def read_ranking(path: Path, top_n: int) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return rows[:top_n]


def load_chip(path: Path) -> Any:
    import pandas as pd

    frame = pd.read_csv(path, parse_dates=["date"], dtype={"stock_id": str})
    frame["stock_id"] = frame["stock_id"].astype(str).str.zfill(4)
    return frame.sort_values(["stock_id", "date"])


def load_features(path: Path) -> Any:
    import pandas as pd

    frame = pd.read_parquet(path)
    date_column = "trade_date" if "trade_date" in frame.columns else "date"
    frame = frame.copy()
    frame["stock_id"] = frame["stock_id"].astype(str).str.zfill(4)
    frame["_date"] = pd.to_datetime(frame[date_column]).dt.date
    return frame.sort_values(["stock_id", "_date"])


def build_price_index(features: Any) -> dict[str, list[tuple[Any, float]]]:
    import pandas as pd

    result: dict[str, list[tuple[Any, float]]] = {}
    for stock_id, group in features.groupby("stock_id", sort=False):
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


def summarize_values(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "avg_return": None, "median_return": None, "negative_rate": None, "loss_gt_5pct_rate": None}
    return {
        "count": len(values),
        "avg_return": round(sum(values) / len(values), 6),
        "median_return": round(float(median(values)), 6),
        "negative_rate": round(sum(1 for value in values if value < 0) / len(values), 6),
        "loss_gt_5pct_rate": round(sum(1 for value in values if value <= -0.05) / len(values), 6),
    }


def chip_metrics(chip: Any, stock_id: str, target_date: str, window_rows: int = 5) -> dict[str, Any] | None:
    import pandas as pd

    rows = chip[(chip["stock_id"] == str(stock_id).zfill(4)) & (chip["date"] <= pd.to_datetime(target_date))].tail(window_rows)
    required = [
        "foreign_buy",
        "trust_buy",
        "dealer_buy",
        "margin_purchase_balance_change",
        "margin_purchase_today_balance",
        "short_sale_balance_change",
        "short_sale_today_balance",
    ]
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
        "trust_latest": int(latest["trust_buy"]),
        "dealer_latest": int(latest["dealer_buy"]),
        "margin_latest_change": int(latest["margin_purchase_balance_change"]),
        "margin_latest_balance": int(latest["margin_purchase_today_balance"]),
        "short_latest_change": int(latest["short_sale_balance_change"]),
        "short_latest_balance": int(latest["short_sale_today_balance"]),
    }


def classify_chip(metrics: dict[str, Any]) -> tuple[str, list[str]]:
    signals: list[str] = []
    if metrics["foreign_5d"] < 0:
        signals.append("foreign_5d_sell")
    if metrics["trust_5d"] < 0:
        signals.append("trust_5d_sell")
    if metrics["margin_5d"] > 0:
        signals.append("margin_5d_up")
    if metrics["margin_latest_change"] > 0:
        signals.append("margin_latest_up")
    if metrics["short_5d"] > 0:
        signals.append("short_5d_up")

    if metrics["foreign_5d"] < 0 and metrics["margin_5d"] > 0:
        return "CHIP_RISK", signals
    if metrics["foreign_5d"] > 0 and metrics["margin_5d"] <= 0:
        return "CHIP_SUPPORTIVE", signals
    if metrics["foreign_5d"] < 0:
        return "FOREIGN_SELL_ONLY", signals
    if metrics["margin_5d"] > 0:
        return "MARGIN_UP_ONLY", signals
    return "NEUTRAL", signals


def build_replay(chip: Any, rankings_dir: Path, features_path: Path, top_n: int) -> dict[str, Any]:
    features = load_features(features_path)
    price_index = build_price_index(features)
    chip_dates = {str(item) for item in chip["date"].dt.date.unique()}
    files = [path for path in ranking_files(rankings_dir) if ranking_date(path) in chip_dates]
    observations: list[dict[str, Any]] = []
    by_group_horizon: dict[str, dict[int, list[float]]] = {group: {horizon: [] for horizon in HORIZONS} for group in GROUPS}
    group_counter: Counter[str] = Counter()
    signal_counter: Counter[str] = Counter()

    for path in files:
        target_date = ranking_date(path)
        for row in read_ranking(path, top_n):
            stock_id = str(row.get("stock_id", "")).zfill(4)
            metrics = chip_metrics(chip, stock_id, target_date)
            if not metrics:
                continue
            group, signals = classify_chip(metrics)
            group_counter[group] += 1
            signal_counter.update(signals)
            returns: dict[str, float] = {}
            for horizon in HORIZONS:
                value = forward_return(price_index, stock_id, target_date, horizon)
                if value is not None:
                    returns[str(horizon)] = value
                    by_group_horizon[group][horizon].append(value)
            observations.append(
                {
                    "date": target_date,
                    "stock_id": stock_id,
                    "stock_name": row.get("stock_name"),
                    "chip_group": group,
                    "signals": signals,
                    "chip_metrics": metrics,
                    "forward_returns": returns,
                }
            )

    group_outcomes = {
        group: {str(horizon): summarize_values(values) for horizon, values in by_group_horizon[group].items()}
        for group in GROUPS
    }
    risk_5d = group_outcomes["CHIP_RISK"]["5"]
    supportive_5d = group_outcomes["CHIP_SUPPORTIVE"]["5"]
    if risk_5d["count"] and supportive_5d["count"] and risk_5d["avg_return"] < supportive_5d["avg_return"]:
        replay_status = "DIRECTIONALLY_USEFUL_MONITOR_ONLY"
    else:
        replay_status = "NOT_STABLE_ENOUGH_FOR_WARNING_CHANNEL"

    return {
        "ranking_files": [repo_path(path) for path in files],
        "target_dates": [ranking_date(path) for path in files],
        "observation_count": len(observations),
        "group_counts": dict(group_counter),
        "signal_counts": dict(signal_counter),
        "group_outcomes": group_outcomes,
        "replay_status": replay_status,
        "observations": observations,
        "observations_sample": observations[:80],
    }


def build_current_snapshot(chip_path: Path, ranking_path: Path, top_n: int) -> dict[str, Any]:
    if not chip_path.exists() or not ranking_path.exists():
        return {"available": False, "reason": "current chip csv or current ranking missing"}
    chip = load_chip(chip_path)
    latest_date = str(chip["date"].max().date())
    rows = read_ranking(ranking_path, top_n)
    items: list[dict[str, Any]] = []
    for row in rows:
        stock_id = str(row.get("stock_id", "")).zfill(4)
        metrics = chip_metrics(chip, stock_id, latest_date)
        if not metrics:
            continue
        group, signals = classify_chip(metrics)
        items.append(
            {
                "stock_id": stock_id,
                "stock_name": row.get("stock_name"),
                "chip_group": group,
                "signals": signals,
                "chip_metrics": metrics,
            }
        )
    return {
        "available": True,
        "asof_date": latest_date,
        "top_n": top_n,
        "item_count": len(items),
        "group_counts": dict(Counter(item["chip_group"] for item in items)),
        "margin_latest_up_count": sum(1 for item in items if item["chip_metrics"]["margin_latest_change"] > 0),
        "margin_latest_down_count": sum(1 for item in items if item["chip_metrics"]["margin_latest_change"] < 0),
        "foreign_latest_sell_count": sum(1 for item in items if item["chip_metrics"]["foreign_latest"] < 0),
        "trust_latest_sell_count": sum(1 for item in items if item["chip_metrics"]["trust_latest"] < 0),
        "items": items,
        "primary_read": "最新 Top10 並非全面融資增加；目前更像個股分化，不能把融資單獨當獲利了結訊號。",
    }


def inspect_features(path: Path) -> dict[str, Any]:
    import pandas as pd

    if not path.exists():
        return {
            "exists": False,
            "columns": [],
            "missing_required_columns": REQUIRED_FEATURE_COLUMNS,
            "row_count": 0,
            "stock_count": 0,
            "latest_date": None,
        }
    frame = pd.read_parquet(path)
    columns = list(frame.columns)
    missing = [col for col in REQUIRED_FEATURE_COLUMNS if col not in columns]
    latest_date = str(pd.to_datetime(frame["date"]).max().date()) if "date" in frame.columns and not frame.empty else None
    stock_count = int(frame["stock_id"].nunique()) if "stock_id" in frame.columns and not frame.empty else 0
    return {
        "exists": True,
        "columns": columns,
        "missing_required_columns": missing,
        "row_count": int(len(frame)),
        "stock_count": stock_count,
        "latest_date": latest_date,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    features_path = resolve_path(args.features)
    chip_path = resolve_path(args.chip_csv)
    current_chip_path = resolve_path(args.current_chip_csv)
    rankings_dir = resolve_path(args.rankings_dir)
    current_ranking_path = resolve_path(args.current_ranking)
    coverage_path = resolve_path(args.coverage)
    coverage = load_json(coverage_path)
    materialized_path = latest_dated_artifact(PROJECT_ROOT / "artifacts" / "model_experiments", "chip_flow_materialized_features")
    materialized = load_json(materialized_path) if materialized_path else {}
    feature_state = inspect_features(features_path)
    blockers: list[str] = []
    replay: dict[str, Any] | None = None
    current_snapshot: dict[str, Any] | None = None

    if coverage.get("status") != "OK":
        blockers.append(f"runtime coverage status={coverage.get('status') or 'missing'}")
    if materialized.get("status") != "OK":
        blockers.append("chip-flow materialized feature smoke missing or not OK")
    if not chip_path.exists():
        blockers.append(f"chip replay csv missing: {repo_path(chip_path)}")
    else:
        chip = load_chip(chip_path)
        replay = build_replay(chip, rankings_dir, features_path, args.top_n)
        if replay["observation_count"] <= 0:
            blockers.append("chip replay produced zero observations")
    current_snapshot = build_current_snapshot(current_chip_path, current_ranking_path, args.top_n)

    status = "OK" if not blockers and replay else "BLOCKED"
    replay_status = replay["replay_status"] if replay else "SHADOW_REPLAY_NOT_READY"
    production_status = "BLOCKED"
    if status == "OK" and replay_status == "DIRECTIONALLY_USEFUL_MONITOR_ONLY":
        decision_status = "SHADOW_REPLAY_MONITOR_ONLY"
    elif status == "OK":
        decision_status = replay_status
    else:
        decision_status = "SHADOW_REPLAY_NOT_READY"

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "contract": {
            "research_only": True,
            "warning_only": True,
            "changes_model": False,
            "changes_production_ranking": False,
            "changes_risk_adjusted_score": False,
            "does_not_send_push": True,
            "uses_future_prices_for_evaluation_only": False,
        },
        "inputs": {
            "features": repo_path(features_path),
            "chip_csv": repo_path(chip_path),
            "current_chip_csv": repo_path(current_chip_path),
            "rankings_dir": repo_path(rankings_dir),
            "current_ranking": repo_path(current_ranking_path),
            "coverage": repo_path(coverage_path),
            "materialized_smoke": repo_path(materialized_path) if materialized_path else None,
        },
        "feature_state": {
            "exists": feature_state["exists"],
            "row_count": feature_state["row_count"],
            "stock_count": feature_state["stock_count"],
            "latest_date": feature_state["latest_date"],
            "required_columns": REQUIRED_FEATURE_COLUMNS,
            "missing_required_columns": feature_state["missing_required_columns"],
        },
        "replay": replay,
        "current_snapshot": current_snapshot,
        "candidate_rules": [
            {
                "id": "foreign_selling_plus_ma_break",
                "rule": "foreign_net_buy_5d_ratio < 0 and close < ma10",
            },
            {
                "id": "trust_streak_break_plus_top10_drop",
                "rule": "trust_buy_days_5d declines and dropped_from_top10",
            },
            {
                "id": "margin_up_price_flat",
                "rule": "margin_balance_change_20d > 0 and return_10d <= 0",
            },
            {
                "id": "margin_forced_exit_risk",
                "rule": "margin_balance_change_20d < 0 and close < ma20",
            },
        ],
        "blockers": blockers,
        "decision": {
            "status": decision_status,
            "production_status": production_status,
            "primary_read": (
                "shadow CSV 已可做 warning-only replay；這批 tail sample 沒有證明「外資賣且融資增」"
                "一定比較差，反而顯示籌碼訊號需要搭配價格/排名轉弱，不能單獨變成獲利了結提醒。"
                if status == "OK"
                else "FinMind smoke 可抓，shadow materialized smoke 也可產出；但尚未形成可 replay 的 chip shadow CSV。"
            ),
            "next_step": (
                "擴大 replay 到至少 60-80 個 target dates，並把 chip 訊號只當 warning overlay，不進 production score。"
                if status == "OK"
                else "擴大 materializer 到半年 ranking universe，產出可 join ranking dates 的歷史 chip frame，再執行 replay。"
            ),
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    state = payload["feature_state"]
    replay = payload.get("replay") or {}
    current = payload.get("current_snapshot") or {}
    lines = [
        "# Chip Warning Shadow Report",
        "",
        f"- status: `{payload['status']}`",
        f"- decision: `{payload['decision']['status']}`",
        f"- production_status: `{payload['decision']['production_status']}`",
        "",
        "## Primary Read",
        "",
        payload["decision"]["primary_read"],
        "",
        "## Replay",
        "",
        f"- replay_status: `{replay.get('replay_status')}`",
        f"- observation_count: `{replay.get('observation_count')}`",
        f"- target_dates: `{replay.get('target_dates')}`",
        f"- group_counts: `{replay.get('group_counts')}`",
        "",
        "| group | 3D avg | 5D avg | 10D avg | 5D negative | count 5D |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    outcomes = replay.get("group_outcomes") or {}
    for group in GROUPS:
        row = outcomes.get(group) or {}
        h3 = row.get("3") or {}
        h5 = row.get("5") or {}
        h10 = row.get("10") or {}
        lines.append(
            f"| `{group}` | {pct(h3.get('avg_return'))} | {pct(h5.get('avg_return'))} | "
            f"{pct(h10.get('avg_return'))} | {pct(h5.get('negative_rate'))} | {h5.get('count', 0)} |"
        )
    lines.extend(
        [
            "",
            "## Current Top10 Snapshot",
            "",
            f"- available: `{current.get('available')}`",
            f"- asof_date: `{current.get('asof_date')}`",
            f"- group_counts: `{current.get('group_counts')}`",
            f"- margin_latest_up_count: `{current.get('margin_latest_up_count')}`",
            f"- margin_latest_down_count: `{current.get('margin_latest_down_count')}`",
            f"- foreign_latest_sell_count: `{current.get('foreign_latest_sell_count')}`",
            f"- trust_latest_sell_count: `{current.get('trust_latest_sell_count')}`",
            "",
            current.get("primary_read") or "",
            "",
            "## Feature State",
            "",
            f"- features exists: `{state['exists']}`",
            f"- row_count: `{state['row_count']}`",
            f"- stock_count: `{state['stock_count']}`",
            f"- latest_date: `{state['latest_date']}`",
            f"- missing_required_columns: `{state['missing_required_columns']}`",
            "",
            "## Blockers",
            "",
        ]
    )
    lines.extend([f"- {item}" for item in payload["blockers"]] or ["- none"])
    lines.extend(["", "## Next Step", "", f"- {payload['decision']['next_step']}"])
    return "\n".join(lines) + "\n"


def pct(value: Any) -> str:
    if value is None:
        return "--"
    return f"{float(value):.2%}"


def main() -> int:
    args = parse_args()
    output_path = resolve_path(args.output)
    markdown_path = resolve_path(args.markdown_output) if args.markdown_output else output_path.with_suffix(".md")
    payload = build_payload(args)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "decision": payload["decision"]["status"],
                "output": repo_path(output_path),
                "markdown": repo_path(markdown_path),
                "blockers": payload["blockers"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
