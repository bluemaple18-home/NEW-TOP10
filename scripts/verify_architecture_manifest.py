#!/usr/bin/env python3
"""驗證 canonical architecture manifest 與 repo source 一致。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.architecture import verify_architecture_manifest  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="驗證 TOP10new canonical architecture manifest")
    parser.add_argument("--manifest", default=".work/ARCH-UPGRADE-01/evidence/architecture_manifest.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    path = Path(args.manifest)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    payload = json.loads(path.read_text(encoding="utf-8"))
    verify_architecture_manifest(payload, PROJECT_ROOT)
    print(json.dumps({"status": "OK", "manifest": str(path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
