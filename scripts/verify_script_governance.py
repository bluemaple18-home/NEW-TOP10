#!/usr/bin/env python3
"""重算並驗證 script governance report。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.architecture.script_governance import verify_script_governance  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="驗證 script governance report")
    parser.add_argument("--report", type=Path, default=Path(".work/ARCH-UPGRADE-05/evidence/script_governance.json"))
    parser.add_argument("--lifecycle", type=Path, default=Path(".work/ARCH-UPGRADE-01/evidence/script_lifecycle.json"))
    parser.add_argument("--references", type=Path, default=Path(".work/ARCH-UPGRADE-05/evidence/script_references.json"))
    parser.add_argument("--architecture", type=Path, default=Path(".work/ARCH-UPGRADE-01/evidence/architecture_manifest.json"))
    return parser.parse_args()


def read_json(path: Path) -> dict:
    resolved = path.resolve() if path.is_absolute() else (PROJECT_ROOT / path).resolve()
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root 必須是 object：{path}")
    return payload


def main() -> int:
    args = parse_args()
    report = read_json(args.report)
    verify_script_governance(report, read_json(args.lifecycle), read_json(args.references), read_json(args.architecture))
    if report.get("strict", {}).get("passed") is not True:
        raise ValueError("script governance strict status 不是 PASS")
    print(json.dumps({"status": "OK", "tracked_script_count": report["summary"]["tracked_script_count"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
