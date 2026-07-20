#!/usr/bin/env python3
"""驗證單一 TSKG research evidence envelope。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.research.tskg_evidence_contract import verify_evidence_envelope  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify TSKG research evidence")
    parser.add_argument("--artifact", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = json.loads(Path(args.artifact).read_text(encoding="utf-8"))
    report = verify_evidence_envelope(payload)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
