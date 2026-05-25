"""批次匯入目前 universe 的 Goodinfo 基本面 cache。

此腳本只供離線任務使用；API/UI 不應同步呼叫。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.data.fundamental_repository import FundamentalRepository
from app.fundamentals.goodinfo_client import GoodinfoClient


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Goodinfo fundamentals for the local stock universe")
    parser.add_argument("--limit", type=int, default=0, help="最多匯入幾檔；0 表示不限制")
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--force", action="store_true", help="重新抓取已存在的 cache")
    parser.add_argument("--features-path", default="data/clean/features.parquet")
    args = parser.parse_args()

    stock_ids = _stock_universe(features_path=PROJECT_ROOT / args.features_path, limit=args.limit)
    repository = FundamentalRepository(PROJECT_ROOT)
    client = GoodinfoClient(delay_seconds=args.delay)
    results = []

    for index, stock_id in enumerate(stock_ids, start=1):
        path = repository.cache_path(stock_id)
        if path.exists() and not args.force:
            results.append({"stock_id": stock_id, "status": "skipped", "path": str(path)})
            continue
        try:
            fetched = client.fetch_all(stock_id)
            written = repository.write_cached(stock_id, fetched.to_cache_payload())
            results.append({"stock_id": stock_id, "status": "ok", "path": str(written)})
            print(f"[{index}/{len(stock_ids)}] ok {stock_id}")
        except Exception as exc:
            results.append({"stock_id": stock_id, "status": "error", "error": str(exc)})
            print(f"[{index}/{len(stock_ids)}] error {stock_id}: {exc}")
        time.sleep(args.delay)

    summary = {
        "total": len(results),
        "ok": sum(item["status"] == "ok" for item in results),
        "skipped": sum(item["status"] == "skipped" for item in results),
        "error": sum(item["status"] == "error" for item in results),
        "results": results,
    }
    out_path = PROJECT_ROOT / "artifacts" / "goodinfo_universe_import_summary.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"GOODINFO_UNIVERSE_IMPORT total={summary['total']} ok={summary['ok']} skipped={summary['skipped']} error={summary['error']} path={out_path}")
    return 0 if summary["error"] == 0 else 2


def _stock_universe(features_path: Path, limit: int) -> list[str]:
    if not features_path.exists():
        raise FileNotFoundError(f"找不到 features：{features_path}")
    features = pd.read_parquet(features_path, columns=["stock_id"])
    stock_ids = sorted(features["stock_id"].astype(str).str.strip().unique().tolist())
    if limit > 0:
        return stock_ids[:limit]
    return stock_ids


if __name__ == "__main__":
    raise SystemExit(main())
