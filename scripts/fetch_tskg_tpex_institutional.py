#!/usr/bin/env python3
"""抓取 TPEx 官方 OGL OpenAPI 的最新三大法人逐證券 snapshot。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.tskg.tpex_institutional import (
    fetch_tpex_institutional_snapshot,
    write_tpex_institutional_snapshot,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="fetch latest TPEx institutional snapshot")
    parser.add_argument("--expect-date", help="optional YYYY-MM-DD fail-closed date assertion")
    parser.add_argument("--output", help="output path; default derives from response date")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    snapshot = fetch_tpex_institutional_snapshot(expected_trade_date=args.expect_date)
    target = Path(args.output) if args.output else (
        PROJECT_ROOT / "artifacts" / "tskg" / "tpex" / f"tpex_3insti_{snapshot['trade_date']}.json"
    )
    if not target.is_absolute():
        target = PROJECT_ROOT / target
    write_tpex_institutional_snapshot(snapshot, target)
    print(f"TSKG_TPEX_INSTITUTIONAL_OK rows={snapshot['integrity']['row_count']} output={target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
