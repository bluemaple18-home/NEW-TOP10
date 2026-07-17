#!/usr/bin/env python3
"""驗證 Daily V2 promotion decision 與來源 digest。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.workflows.daily_v2_promotion import verify_daily_v2_promotion_decision_from_files  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="驗證 Daily V2 promotion decision")
    parser.add_argument("--decision", type=Path, default=Path(".work/ARCH-UPGRADE-06/evidence/promotion_decision.json"))
    args = parser.parse_args()
    path = args.decision.resolve() if args.decision.is_absolute() else (PROJECT_ROOT / args.decision).resolve()
    payload = json.loads(path.read_text(encoding="utf-8"))
    verify_daily_v2_promotion_decision_from_files(payload)
    print(json.dumps({"status": "OK", "decision": payload["status"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
