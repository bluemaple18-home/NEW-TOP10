#!/usr/bin/env python3
"""執行 TOP10 只讀研究稽核。"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.research_auditor import AuditInputs, build_audit, write_audit


def main() -> int:
    parser = argparse.ArgumentParser(description="build a research-only TOP10 audit report")
    parser.add_argument("--ranking", required=True, type=Path)
    parser.add_argument("--features", type=Path)
    parser.add_argument("--fundamentals", type=Path)
    parser.add_argument("--backtest", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    payload = build_audit(
        AuditInputs(
            ranking=args.ranking,
            features=args.features,
            fundamentals=args.fundamentals,
            backtest=args.backtest,
        )
    )
    write_audit(payload, args.output)
    print(f"status={payload['status']} output={args.output}")
    return 0 if payload["status"] == "GO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
