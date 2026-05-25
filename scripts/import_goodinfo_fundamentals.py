"""離線匯入 Goodinfo 基本面 cache。

此腳本可碰外部網站；API 與排名流程不得直接呼叫 Goodinfo client。
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.data.fundamental_repository import FundamentalRepository
from app.fundamentals.goodinfo_client import GoodinfoClient


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Goodinfo fundamentals into local cache")
    parser.add_argument("stock_id")
    parser.add_argument("--delay", type=float, default=1.0)
    args = parser.parse_args()

    result = GoodinfoClient(delay_seconds=args.delay).fetch_all(args.stock_id)
    path = FundamentalRepository(PROJECT_ROOT).write_cached(args.stock_id, result.to_cache_payload())
    print(f"已寫入基本面 cache: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
