#!/usr/bin/env python3
"""從歷史 ranking artifacts 建立候選入榜天數摘要。

此腳本只讀 `artifacts/ranking_*.csv`，不重跑 ranking、模型或 ETL。
所有 streak 都只使用目標 ranking 日期以前的 artifact，避免未來資料污染。
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
SCHEMA_VERSION = "candidate-persistence.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build candidate persistence artifact from ranking history")
    parser.add_argument("--ranking", default=None, help="目標 ranking CSV；未指定時使用最新 artifacts/ranking_*.csv")
    parser.add_argument("--rankings-dir", default="artifacts", help="ranking history 目錄")
    parser.add_argument("--limit", type=int, default=30, help="目標 ranking 讀取筆數")
    parser.add_argument("--output", default=None, help="輸出 JSON；未指定時寫 artifacts/candidate_persistence_YYYY-MM-DD.json")
    return parser.parse_args()


def ranking_date(path: Path) -> str:
    match = re.match(r"ranking_(\d{4}-\d{2}-\d{2})\.csv$", path.name)
    if not match:
        raise ValueError(f"ranking 檔名無法解析日期：{path}")
    return match.group(1)


def sorted_ranking_files(rankings_dir: Path) -> list[Path]:
    files = [path for path in rankings_dir.glob("ranking_*.csv") if re.match(r"ranking_\d{4}-\d{2}-\d{2}\.csv$", path.name)]
    return sorted(files, key=lambda path: ranking_date(path))


def latest_ranking(rankings_dir: Path) -> Path:
    files = sorted_ranking_files(rankings_dir)
    if not files:
        raise FileNotFoundError(f"找不到 ranking_*.csv：{rankings_dir}")
    return files[-1]


def read_ranking(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise RuntimeError(f"ranking artifact 沒有資料：{path}")
    if "stock_id" not in rows[0]:
        raise RuntimeError(f"ranking artifact 缺少 stock_id：{path}")
    rows = rows[:limit] if limit is not None else rows
    normalized = []
    for index, row in enumerate(rows, start=1):
        normalized.append(
            {
                **row,
                "rank": index,
                "stock_id": str(row.get("stock_id", "")).strip().zfill(4),
            }
        )
    return normalized


def history_until(rankings_dir: Path, target_date: str) -> list[tuple[str, Path]]:
    return [(ranking_date(path), path) for path in sorted_ranking_files(rankings_dir) if ranking_date(path) <= target_date]


def history_until_with_target(rankings_dir: Path, target_ranking: Path, target_date: str) -> list[tuple[str, Path]]:
    history = [(date_text, path) for date_text, path in history_until(rankings_dir, target_date) if date_text != target_date]
    history.append((target_date, target_ranking))
    return sorted(history, key=lambda item: item[0])


def build_payload(target_ranking: Path, rankings_dir: Path, limit: int) -> dict[str, Any]:
    target_date = ranking_date(target_ranking)
    target_rows = read_ranking(target_ranking, limit=limit)
    history_files = history_until_with_target(rankings_dir, target_ranking, target_date)
    history_by_stock: dict[str, list[dict[str, Any]]] = {}

    for date_text, path in history_files:
        for row in read_ranking(path, limit=limit):
            history_by_stock.setdefault(row["stock_id"], []).append({"date": date_text, "rank": row["rank"]})

    items = []
    for row in target_rows:
        stock_id = row["stock_id"]
        stock_history = history_by_stock.get(stock_id, [])
        current_rank = row["rank"]
        previous = stock_history[-2] if len(stock_history) >= 2 else None
        first_seen = stock_history[0]["date"] if stock_history else target_date
        consecutive = consecutive_seen_count(stock_history, history_files)
        previous_rank = previous["rank"] if previous else None
        rank_delta = previous_rank - current_rank if previous_rank is not None else None
        items.append(
            {
                "stock_id": stock_id,
                "stock_name": row.get("stock_name"),
                "rank": current_rank,
                "first_seen_date": first_seen,
                "consecutive_ranked_days": consecutive,
                "ranked_history_count": len(stock_history),
                "previous_rank": previous_rank,
                "rank_delta": rank_delta,
                "rank_delta_meaning": "positive means rank improved" if rank_delta is not None else "new_or_no_previous_artifact",
                "history_dates": [item["date"] for item in stock_history],
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ranking_date": target_date,
        "source_artifact": str(target_ranking),
        "history_artifact_count": len(history_files),
        "limit": limit,
        "contract": {
            "uses_future_rankings": False,
            "rank_history_scope": "ranking artifacts with date <= ranking_date",
            "consecutive_unit": "available ranking artifact days",
            "model_feature": False,
        },
        "items": items,
    }


def consecutive_seen_count(stock_history: list[dict[str, Any]], history_files: list[tuple[str, Path]]) -> int:
    if not stock_history:
        return 0
    seen_dates = {item["date"] for item in stock_history}
    count = 0
    for date_text, _ in reversed(history_files):
        if date_text not in seen_dates:
            break
        count += 1
    return count


def main() -> int:
    args = parse_args()
    rankings_dir = (PROJECT_ROOT / args.rankings_dir).resolve()
    target_ranking = Path(args.ranking).expanduser().resolve() if args.ranking else latest_ranking(rankings_dir)
    payload = build_payload(target_ranking=target_ranking, rankings_dir=rankings_dir, limit=args.limit)
    target_date = payload["ranking_date"]
    output_path = (
        Path(args.output).expanduser().resolve()
        if args.output
        else ARTIFACTS_DIR / f"candidate_persistence_{target_date}.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "OK", "output": str(output_path), "items": len(payload["items"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
