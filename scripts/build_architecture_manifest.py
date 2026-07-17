#!/usr/bin/env python3
"""建立 TOP10new canonical architecture manifest。"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.architecture import build_architecture_manifest  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="建立 TOP10new canonical architecture manifest")
    parser.add_argument("--output", default=".work/ARCH-UPGRADE-01/evidence/architecture_manifest.json")
    return parser.parse_args()


def write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def main() -> int:
    args = parse_args()
    output = Path(args.output)
    if not output.is_absolute():
        output = PROJECT_ROOT / output
    manifest = build_architecture_manifest(PROJECT_ROOT)
    write_json_atomic(output, manifest)
    print(json.dumps({"status": "OK", "output": str(output), "git_sha": manifest["source"]["git_sha"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
