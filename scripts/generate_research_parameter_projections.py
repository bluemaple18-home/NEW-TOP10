#!/usr/bin/env python3
"""驗證或重建 legacy formal parameter projection。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.research.parameter_catalog import executable_parameter_dimensions  # noqa: E402


CONTRACT_PATH = PROJECT_ROOT / "config" / "regime_research_contract.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="generate catalog-backed research projections")
    parser.add_argument("--check", action="store_true", help="只驗證，不寫檔")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    expected = executable_parameter_dimensions()
    observed = contract["parameter_universe"].get("dimensions")
    if args.check:
        if observed != expected:
            raise SystemExit("regime research parameter projection drift")
        print(json.dumps({"status": "OK", "dimensions": len(expected)}))
        return 0
    contract["parameter_universe"]["dimensions"] = expected
    CONTRACT_PATH.write_text(
        json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": "UPDATED", "dimensions": len(expected)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
