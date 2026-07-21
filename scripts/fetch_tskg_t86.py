#!/usr/bin/env python3
"""下載單一交易日 TWSE T86，輸出本機 normalized snapshot。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.tskg.twse_t86 import fetch_t86_snapshot, write_t86_snapshot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="fetch one TWSE T86 business-date snapshot")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def output_path(trade_date: str, explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit).expanduser()
        return path if path.is_absolute() else PROJECT_ROOT / path
    return PROJECT_ROOT / "artifacts" / "tskg" / "t86" / f"twse_t86_{trade_date}.json"


def main() -> int:
    args = parse_args()
    target = output_path(args.date, args.output)
    try:
        snapshot = fetch_t86_snapshot(args.date)
        written = write_t86_snapshot(snapshot, target)
    except Exception as error:
        print(
            json.dumps(
                {
                    "status": "FAILED",
                    "trade_date": args.date,
                    "error_type": type(error).__name__,
                    "error": str(error),
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1
    print(
        json.dumps(
            {
                "status": "OK",
                "trade_date": snapshot["trade_date"],
                "row_count": snapshot["integrity"]["row_count"],
                "canonical_sha256": snapshot["integrity"]["canonical_sha256"],
                "output": str(written),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
