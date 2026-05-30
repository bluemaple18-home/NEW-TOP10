#!/usr/bin/env python3
"""建立 MODEL-EXP 用的入榜持續性特徵表。

此 materializer 只使用目標日前一個已存在 ranking artifact 的狀態，
避免把當天 ranking 結果反灌成模型特徵。
輸出只寫到 artifacts/model_experiments/，不覆蓋 production features。
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "model_experiments"
SCHEMA_VERSION = "candidate-persistence-materialized-features.v1"


@dataclass
class StockState:
    first_seen_date: str
    last_seen_date: str
    ranked_history_count: int
    consecutive_ranked_days: int
    prior_rank: int
    last_rank_delta: int | None
    ranking_gap_count: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="materialize candidate persistence features for offline model experiments")
    parser.add_argument("--rankings-dir", default="artifacts/backtest/historical_rankings_current_model")
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--max-ranking-files", type=int, default=None)
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
    match = re.match(r"ranking_(\d{4}-\d{2}-\d{2})\.csv$", path.name)
    if not match:
        raise ValueError(f"ranking 檔名無法解析日期：{path}")
    return match.group(1)


def ranking_files(rankings_dir: Path, max_files: int | None) -> list[Path]:
    files = sorted(
        [path for path in rankings_dir.glob("ranking_*.csv") if re.match(r"ranking_\d{4}-\d{2}-\d{2}\.csv$", path.name)],
        key=ranking_date,
    )
    if not files:
        raise FileNotFoundError(f"找不到 ranking_*.csv：{rankings_dir}")
    return files[-max_files:] if max_files else files


def read_ranking(path: Path, top_n: int) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))[:top_n]
    if not rows:
        raise RuntimeError(f"ranking artifact 沒有資料：{path}")
    if "stock_id" not in rows[0]:
        raise RuntimeError(f"ranking artifact 缺少 stock_id：{path}")
    return [{"stock_id": str(row.get("stock_id", "")).strip().zfill(4), "rank": index} for index, row in enumerate(rows, start=1)]


def feature_universe(features_path: Path, target_dates: set[str]) -> pd.DataFrame:
    frame = pd.read_parquet(features_path, columns=["date", "stock_id"])
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    frame["stock_id"] = frame["stock_id"].astype(str).str.strip().str.zfill(4)
    frame = frame[frame["date"].isin(target_dates)].copy()
    if frame.empty:
        raise RuntimeError("features parquet 中找不到 ranking dates 對應的 stock universe")
    return frame.sort_values(["date", "stock_id"]).reset_index(drop=True)


def streak_bucket(days: int) -> str:
    if days <= 0:
        return "0"
    if days == 1:
        return "1"
    if days <= 3:
        return "2-3"
    if days <= 5:
        return "4-5"
    return "6+"


def rank_delta_direction(value: int | None) -> str:
    if value is None:
        return "new_or_unknown"
    if value > 0:
        return "improved"
    if value < 0:
        return "worsened"
    return "unchanged"


def materialized_rows(files: list[Path], universe: pd.DataFrame, top_n: int) -> pd.DataFrame:
    state: dict[str, StockState] = {}
    records: list[dict[str, Any]] = []
    by_date = {date_text: group for date_text, group in universe.groupby("date", sort=True)}

    for index, ranking_path in enumerate(files):
        date_text = ranking_date(ranking_path)
        group = by_date.get(date_text)
        if group is not None:
            for row in group.itertuples(index=False):
                stock_id = str(row.stock_id).zfill(4)
                item = state.get(stock_id)
                days_since_last_seen = None if item is None else item.ranking_gap_count
                consecutive = 0 if item is None or item.ranking_gap_count > 0 else item.consecutive_ranked_days
                records.append(
                    {
                        "date": date_text,
                        "stock_id": stock_id,
                        "consecutive_ranked_days": consecutive,
                        "streak_bucket": streak_bucket(consecutive),
                        "ranked_history_count": 0 if item is None else item.ranked_history_count,
                        "prior_rank": None if item is None else item.prior_rank,
                        "rank_delta": None if item is None else item.last_rank_delta,
                        "rank_delta_direction": rank_delta_direction(None if item is None else item.last_rank_delta),
                        "days_since_last_seen": days_since_last_seen,
                        "seen_in_previous_ranking": bool(item is not None and item.ranking_gap_count == 0),
                    }
                )

        current_rows = read_ranking(ranking_path, top_n=top_n)
        current_ids = {row["stock_id"] for row in current_rows}
        for stock_id, item in list(state.items()):
            if stock_id not in current_ids:
                item.consecutive_ranked_days = 0
                item.ranking_gap_count += 1
                state[stock_id] = item
        for row in current_rows:
            stock_id = row["stock_id"]
            rank = int(row["rank"])
            previous = state.get(stock_id)
            if previous is None:
                state[stock_id] = StockState(
                    first_seen_date=date_text,
                    last_seen_date=date_text,
                    ranked_history_count=1,
                    consecutive_ranked_days=1,
                    prior_rank=rank,
                    last_rank_delta=None,
                    ranking_gap_count=0,
                )
                continue
            consecutive = previous.consecutive_ranked_days + 1 if previous.ranking_gap_count == 0 else 1
            state[stock_id] = StockState(
                first_seen_date=previous.first_seen_date,
                last_seen_date=date_text,
                ranked_history_count=previous.ranked_history_count + 1,
                consecutive_ranked_days=consecutive,
                prior_rank=rank,
                last_rank_delta=previous.prior_rank - rank,
                ranking_gap_count=0,
            )

    result = pd.DataFrame.from_records(records)
    if result.empty:
        raise RuntimeError("materialized feature frame is empty")
    return result


def build_payload(args: argparse.Namespace) -> tuple[pd.DataFrame, dict[str, Any]]:
    rankings_dir = resolve_path(args.rankings_dir)
    features_path = resolve_path(args.features)
    files = ranking_files(rankings_dir, max_files=args.max_ranking_files)
    dates = {ranking_date(path) for path in files}
    universe = feature_universe(features_path, dates)
    frame = materialized_rows(files, universe=universe, top_n=args.top_n)
    nonzero = int((pd.to_numeric(frame["ranked_history_count"], errors="coerce") > 0).sum())
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "contract": {
            "materializer_only": True,
            "uses_current_day_ranking_result": False,
            "uses_future_rankings": False,
            "source_scope": "ranking artifacts with date < materialized date",
            "does_not_write_production_features": True,
            "does_not_train_model": True,
            "does_not_change_production_ranking": True,
        },
        "inputs": {
            "rankings_dir": repo_path(rankings_dir),
            "features": repo_path(features_path),
            "ranking_files": [repo_path(path) for path in files],
            "top_n": args.top_n,
            "max_ranking_files": args.max_ranking_files,
        },
        "summary": {
            "rows": int(len(frame)),
            "stocks": int(frame["stock_id"].nunique()),
            "dates": int(frame["date"].nunique()),
            "start_date": str(frame["date"].min()),
            "end_date": str(frame["date"].max()),
            "nonzero_history_rows": nonzero,
            "columns": list(frame.columns),
        },
    }
    return frame, metadata


def render_markdown(metadata: dict[str, Any]) -> str:
    summary = metadata["summary"]
    lines = [
        "# Candidate Persistence Materialized Features",
        "",
        f"- rows：`{summary['rows']}`",
        f"- stocks：`{summary['stocks']}`",
        f"- dates：`{summary['dates']}`",
        f"- window：`{summary['start_date']}` to `{summary['end_date']}`",
        f"- nonzero_history_rows：`{summary['nonzero_history_rows']}`",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    frame, metadata = build_payload(args)
    output = resolve_path(args.output) if args.output else OUTPUT_DIR / f"candidate_persistence_features_{args.date}.parquet"
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(output, index=False)
    metadata["output"] = repo_path(output)
    metadata_path = output.with_suffix(".json")
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(metadata), encoding="utf-8")
    print(json.dumps({"status": "OK", "output": repo_path(output), **metadata["summary"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
