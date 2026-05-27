#!/usr/bin/env python3
"""驗證每日通知用的產業主題對照是否覆蓋所有股票。"""

from __future__ import annotations

import csv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDUSTRY_MAP_PATH = PROJECT_ROOT / "data" / "reference" / "stock_industry_map.csv"
BUCKET_MAP_PATH = PROJECT_ROOT / "config" / "notification_industry_buckets.csv"


def main() -> int:
    stock_industries = load_stock_industries()
    bucket_map = load_bucket_map()

    missing = sorted(set(stock_industries.values()) - set(bucket_map))
    unused = sorted(set(bucket_map) - set(stock_industries.values()))
    blank_stocks = sorted(stock_id for stock_id, industry in stock_industries.items() if not industry)

    if blank_stocks or missing:
        if blank_stocks:
            print("NOTIFICATION_BUCKETS_FAIL blank_industry_stock_ids=" + ",".join(blank_stocks[:20]))
        if missing:
            print("NOTIFICATION_BUCKETS_FAIL missing_industries=" + ",".join(missing))
        return 1

    print(
        "NOTIFICATION_BUCKETS_OK "
        f"stocks={len(stock_industries)} "
        f"industries={len(set(stock_industries.values()))} "
        f"buckets={len(set(bucket_map.values()))}"
    )
    if unused:
        print("NOTIFICATION_BUCKETS_WARN unused_industries=" + ",".join(unused))
    return 0


def load_stock_industries() -> dict[str, str]:
    with INDUSTRY_MAP_PATH.open(encoding="utf-8-sig", newline="") as file:
        return {
            str(row.get("stock_id") or "").zfill(4): str(row.get("industry_name") or "").strip()
            for row in csv.DictReader(file)
            if row.get("stock_id")
        }


def load_bucket_map() -> dict[str, str]:
    seen = {}
    duplicates = []
    with BUCKET_MAP_PATH.open(encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            industry = str(row.get("industry_name") or "").strip()
            bucket = str(row.get("notification_bucket") or "").strip()
            if not industry or not bucket:
                print(f"NOTIFICATION_BUCKETS_FAIL blank_mapping row={row}")
                raise SystemExit(1)
            if industry in seen:
                duplicates.append(industry)
            seen[industry] = bucket
    if duplicates:
        print("NOTIFICATION_BUCKETS_FAIL duplicate_industries=" + ",".join(sorted(set(duplicates))))
        raise SystemExit(1)
    return seen


if __name__ == "__main__":
    raise SystemExit(main())
