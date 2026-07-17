#!/usr/bin/env python3
"""依 changed files 或 Git revisions 建立 required verification plan。"""

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

from app.architecture import build_incremental_verification_plan, changed_files_from_git  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="建立 TOP10new incremental verification plan")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--changed-file", action="append", dest="changed_files")
    source.add_argument("--base")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--output", default=".work/ARCH-UPGRADE-02/evidence/incremental_verification_plan.json")
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
    if args.base:
        changed = changed_files_from_git(PROJECT_ROOT, args.base, args.head)
        request = {"mode": "git_diff", "base": args.base, "head": args.head}
    else:
        changed = args.changed_files
        request = {"mode": "files", "changed_files": sorted(set(changed))}
    plan = build_incremental_verification_plan(PROJECT_ROOT, changed_files=changed, request=request)
    output = Path(args.output)
    if not output.is_absolute():
        output = PROJECT_ROOT / output
    write_json_atomic(output, plan)
    print(json.dumps({"status": "OK", "risk": plan["risk"]["level"], "output": str(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
