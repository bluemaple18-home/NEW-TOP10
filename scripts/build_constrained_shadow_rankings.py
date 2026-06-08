#!/usr/bin/env python3
"""產出 constrained shadow ranking。

用途：研究用 overlay，不訓練模型、不改 production ranking。
規則：每個日期先保留 production TopK，再用 shadow ranking 補滿 TopN。
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "constrained-shadow-ranking.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build constrained shadow ranking")
    parser.add_argument("--production-dir", default="artifacts/backtest/historical_rankings_current_model")
    parser.add_argument("--shadow-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--min-production-count", type=int, default=5)
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def ranking_dates(path: Path) -> list[str]:
    return sorted(item.stem.removeprefix("ranking_") for item in path.glob("ranking_*.csv"))


def read_ranking(path: Path, top_n: int) -> pd.DataFrame:
    frame = pd.read_csv(path, encoding="utf-8-sig").head(top_n).copy()
    frame["stock_id"] = frame["stock_id"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(4)
    return frame


def combine(production: pd.DataFrame, shadow: pd.DataFrame, top_n: int, min_production_count: int) -> pd.DataFrame:
    rows: list[pd.Series] = []
    selected: set[str] = set()
    production_keep = max(0, min(top_n, min_production_count))
    for _, row in production.head(production_keep).iterrows():
        stock_id = str(row.get("stock_id")).zfill(4)
        rows.append(row)
        selected.add(stock_id)
    for _, row in shadow.iterrows():
        stock_id = str(row.get("stock_id")).zfill(4)
        if stock_id in selected:
            continue
        rows.append(row)
        selected.add(stock_id)
        if len(rows) >= top_n:
            break
    if len(rows) < top_n:
        for _, row in production.iterrows():
            stock_id = str(row.get("stock_id")).zfill(4)
            if stock_id in selected:
                continue
            rows.append(row)
            selected.add(stock_id)
            if len(rows) >= top_n:
                break
    result = pd.DataFrame(rows).head(top_n).reset_index(drop=True)
    result["rank"] = range(1, len(result) + 1)
    result["constrained_shadow_source"] = [
        "production_keep" if idx < production_keep else "shadow_fill" for idx in range(len(result))
    ]
    return result


def write_ranking(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_MINIMAL)


def build(args: argparse.Namespace) -> dict[str, Any]:
    production_dir = resolve_path(args.production_dir)
    shadow_dir = resolve_path(args.shadow_dir)
    output_dir = resolve_path(args.output_dir)
    dates = sorted(set(ranking_dates(production_dir)) & set(ranking_dates(shadow_dir)))
    outputs = []
    overlap_counts = []
    for date_text in dates:
        production = read_ranking(production_dir / f"ranking_{date_text}.csv", args.top_n)
        shadow = read_ranking(shadow_dir / f"ranking_{date_text}.csv", args.top_n)
        combined = combine(production, shadow, args.top_n, args.min_production_count)
        output_path = output_dir / f"ranking_{date_text}.csv"
        write_ranking(output_path, combined)
        outputs.append(repo_path(output_path))
        overlap_counts.append(len(set(production["stock_id"]) & set(combined["stock_id"])))
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "contract": {
            "research_only": True,
            "trains_model": False,
            "modifies_production_ranking": False,
            "top_n": args.top_n,
            "min_production_count": args.min_production_count,
        },
        "inputs": {
            "production_dir": repo_path(production_dir),
            "shadow_dir": repo_path(shadow_dir),
            "output_dir": repo_path(output_dir),
        },
        "summary": {
            "date_count": len(dates),
            "avg_overlap_count": round(sum(overlap_counts) / len(overlap_counts), 6) if overlap_counts else None,
            "min_overlap_count": min(overlap_counts) if overlap_counts else None,
        },
        "outputs": outputs,
    }


def main() -> int:
    args = parse_args()
    payload = build(args)
    output_dir = resolve_path(args.output_dir)
    summary_path = output_dir / "constrained_shadow_ranking.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"status": "OK", "summary": repo_path(summary_path), **payload["summary"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
