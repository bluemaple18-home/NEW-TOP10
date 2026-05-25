#!/usr/bin/env python3
"""產生本週模型初選池 / 每日快照 artifact。

此腳本只讀 ranking CSV，不重新訓練、不重跑 ranking。
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
SCHEMA_VERSION = "weekly-candidate-snapshot.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="產生 weekly candidate snapshot artifact")
    parser.add_argument("--ranking", default=None, help="ranking CSV；未指定時使用最新 artifacts/ranking_*.csv")
    parser.add_argument("--date", default=None, help="snapshot date；未指定時使用 ranking 檔名日期")
    parser.add_argument("--limit", type=int, default=30, help="模型初選池保留數量")
    parser.add_argument("--output", default=None, help="輸出 JSON；未指定時使用 artifacts/weekly_candidate_snapshot_YYYY-MM-DD.json")
    return parser.parse_args()


def latest_ranking_path() -> Path:
    ranking_files = sorted(ARTIFACTS_DIR.glob("ranking_*.csv"), key=ranking_sort_key)
    if not ranking_files:
        raise FileNotFoundError("找不到 artifacts/ranking_*.csv")
    return ranking_files[-1]


def ranking_sort_key(path: Path) -> tuple[str, float]:
    match = re.match(r"ranking_(\d{4}-\d{2}-\d{2})\.csv$", path.name)
    return (match.group(1) if match else "", path.stat().st_mtime)


def date_from_ranking_path(path: Path) -> str:
    match = re.match(r"ranking_(\d{4}-\d{2}-\d{2})\.csv$", path.name)
    if not match:
        raise ValueError(f"ranking 檔名缺少日期：{path}")
    return match.group(1)


def week_version_from_date(date_text: str) -> str:
    date_value = datetime.fromisoformat(date_text).date()
    monday = date_value.fromordinal(date_value.toordinal() - date_value.weekday())
    return monday.isoformat()


def read_ranking(path: Path, limit: int) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise RuntimeError(f"ranking artifact 沒有資料：{path}")
    if "stock_id" not in rows[0]:
        raise RuntimeError(f"ranking artifact 缺少 stock_id：{path}")
    return rows[:limit]


def build_payload(ranking_path: Path, snapshot_date: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "snapshot_date": snapshot_date,
        "ranking_date": date_from_ranking_path(ranking_path),
        "week_version": week_version_from_date(snapshot_date),
        "source": "ranking_artifact",
        "source_artifact": str(ranking_path),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_pool_count": len(rows),
        "contract": {
            "cadence": "daily_close_snapshot",
            "strategy": "long_only_momentum",
            "settings_applied": False,
            "intraday_prices": False,
        },
        "model_pool": [
            {
                "priority": index + 1,
                "target_type": "stock",
                "stock_id": str(row.get("stock_id", "")).strip(),
                "stock_name": row.get("stock_name"),
                "ranking": row,
            }
            for index, row in enumerate(rows)
        ],
    }


def main() -> int:
    args = parse_args()
    ranking_path = Path(args.ranking).expanduser().resolve() if args.ranking else latest_ranking_path()
    snapshot_date = args.date or date_from_ranking_path(ranking_path)
    rows = read_ranking(ranking_path, args.limit)
    payload = build_payload(ranking_path=ranking_path, snapshot_date=snapshot_date, rows=rows)
    output_path = (
        Path(args.output).expanduser().resolve()
        if args.output
        else ARTIFACTS_DIR / f"weekly_candidate_snapshot_{snapshot_date}.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "OK", "output": str(output_path), "model_pool_count": len(rows)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
