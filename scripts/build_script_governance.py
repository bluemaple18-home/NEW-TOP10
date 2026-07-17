#!/usr/bin/env python3
"""由三份可重算 evidence 建立全量 script governance。"""

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

from app.architecture.script_governance import build_script_governance  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="建立 script governance report")
    parser.add_argument("--lifecycle", type=Path, default=Path(".work/ARCH-UPGRADE-01/evidence/script_lifecycle.json"))
    parser.add_argument("--references", type=Path, default=Path(".work/ARCH-UPGRADE-05/evidence/script_references.json"))
    parser.add_argument("--architecture", type=Path, default=Path(".work/ARCH-UPGRADE-01/evidence/architecture_manifest.json"))
    parser.add_argument("--output", type=Path, default=Path(".work/ARCH-UPGRADE-05/evidence/script_governance.json"))
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def read_json(path: Path) -> dict:
    payload = json.loads(resolve(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root 必須是 object：{path}")
    return payload


def main() -> int:
    args = parse_args()
    report = build_script_governance(read_json(args.lifecycle), read_json(args.references), read_json(args.architecture))
    output = resolve(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    print(json.dumps({"status": "OK" if report["strict"]["passed"] else "NO-GO", **report["summary"]}, ensure_ascii=False))
    return 0 if report["strict"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
