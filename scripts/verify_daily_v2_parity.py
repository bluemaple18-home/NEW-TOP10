#!/usr/bin/env python3
"""重算 Daily V2 parity report 綁定的四份 evidence。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.workflows.daily_v2_parity import verify_daily_v2_parity_report_from_files  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="驗證 Daily V2 parity report")
    parser.add_argument("--report", type=Path, default=Path(".work/ARCH-UPGRADE-03/evidence/daily_v2_parity.json"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    path = args.report.expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    payload = json.loads(path.read_text(encoding="utf-8"))
    verify_daily_v2_parity_report_from_files(payload)
    print(json.dumps({"status": "OK", "parity": payload["status"], "report": str(path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
