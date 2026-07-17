#!/usr/bin/env python3
"""重算並驗證 incremental verification plan。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.architecture import verify_incremental_verification_plan  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="驗證 TOP10new incremental verification plan")
    parser.add_argument("--plan", default=".work/ARCH-UPGRADE-02/evidence/incremental_verification_plan.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    path = Path(args.plan)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    payload = json.loads(path.read_text(encoding="utf-8"))
    verify_incremental_verification_plan(payload, PROJECT_ROOT)
    print(json.dumps({"status": "OK", "plan": str(path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
