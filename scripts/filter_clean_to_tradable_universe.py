#!/usr/bin/env python3
"""用本地 tradable universe 過濾既有 clean parquet。

用途：資料已重建但混入 ETF / 權證 / 非四碼商品時，離線產出只含
`data/reference/tradable_universe.csv` 的股票版本。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.data.reference_repository import ReferenceRepository


def main() -> int:
    parser = argparse.ArgumentParser(description="Filter clean parquet outputs to local tradable universe")
    parser.add_argument("--input-data-dir", default="data")
    parser.add_argument("--output-data-dir", required=True)
    parser.add_argument("--summary", default="artifacts/tradable_clean_filter_summary.json")
    args = parser.parse_args()

    allowed = {
        item.stock_id
        for item in ReferenceRepository(PROJECT_ROOT).tradable_universe(active_only=True, include_etfs=False).items
    }
    if not allowed:
        raise RuntimeError("tradable universe is empty")

    input_clean = PROJECT_ROOT / args.input_data_dir / "clean"
    output_clean = PROJECT_ROOT / args.output_data_dir / "clean"
    output_clean.mkdir(parents=True, exist_ok=True)

    summaries = []
    for name in ["features", "events", "universe"]:
        source = input_clean / f"{name}.parquet"
        target = output_clean / f"{name}.parquet"
        df = pd.read_parquet(source)
        before_rows = len(df)
        before_stocks = int(df["stock_id"].astype(str).str.strip().nunique())
        filtered = df.copy()
        filtered["stock_id"] = filtered["stock_id"].astype(str).str.strip()
        filtered = filtered[filtered["stock_id"].isin(allowed)].copy()
        filtered.to_parquet(target, index=False)
        summaries.append(
            {
                "dataset": name,
                "source": str(source),
                "target": str(target),
                "before_rows": before_rows,
                "after_rows": len(filtered),
                "before_stocks": before_stocks,
                "after_stocks": int(filtered["stock_id"].nunique()) if not filtered.empty else 0,
            }
        )
        print(f"{name}: rows {before_rows}->{len(filtered)} stocks {before_stocks}->{summaries[-1]['after_stocks']}")

    summary_path = PROJECT_ROOT / args.summary
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps({"allowed_stocks": len(allowed), "datasets": summaries}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"tradable_clean_filter_summary={summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
