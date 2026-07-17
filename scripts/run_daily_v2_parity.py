#!/usr/bin/env python3
"""由既有 evidence 建立 Daily V2 parity report；不執行 production workflow。"""

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

from app.workflows.daily_v2_parity import build_daily_v2_parity_report_from_files  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="建立 production daily 與 Daily V2 parity report")
    parser.add_argument("--production-status", type=Path, required=True)
    parser.add_argument("--workflow-manifest", type=Path, required=True)
    parser.add_argument("--real-shadow-manifest", type=Path, required=True)
    parser.add_argument("--ranking-comparison", type=Path, required=True)
    parser.add_argument("--shadow-root", type=Path, required=True)
    parser.add_argument("--workflow-profile", choices=["fixture", "production-equivalent"], default="fixture")
    parser.add_argument("--output", type=Path, default=Path(".work/ARCH-UPGRADE-03/evidence/daily_v2_parity.json"))
    return parser.parse_args()


def resolve(path: Path) -> Path:
    path = path.expanduser()
    return path.resolve() if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    args = parse_args()
    report = build_daily_v2_parity_report_from_files(
        production_status_path=resolve(args.production_status),
        workflow_manifest_path=resolve(args.workflow_manifest),
        real_shadow_manifest_path=resolve(args.real_shadow_manifest),
        ranking_comparison_path=resolve(args.ranking_comparison),
        shadow_root=resolve(args.shadow_root),
        workflow_profile=args.workflow_profile,
    )
    output = resolve(args.output)
    write_json_atomic(output, report)
    print(
        json.dumps(
            {
                "status": report["status"],
                "production_switch": report["production_switch"]["status"],
                "output": str(output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
