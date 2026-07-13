#!/usr/bin/env python3
"""在 shadow 目錄建立 sklearn runtime migration candidate。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.modeling.model_runtime_migration import (  # noqa: E402
    MIN_GRID_POINTS,
    build_migration_candidate,
)


SHADOW_ROOT = PROJECT_ROOT / "artifacts" / "shadow" / "model_runtime_migration"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="建立 sklearn runtime migration shadow candidate 與等價 verdict"
    )
    parser.add_argument("--source", default="models/latest_lgbm.pkl")
    parser.add_argument(
        "--output",
        default="artifacts/shadow/model_runtime_migration/latest_lgbm.pkl",
    )
    parser.add_argument(
        "--report",
        default="artifacts/shadow/model_runtime_migration/verdict.json",
    )
    parser.add_argument("--grid-points", type=int, default=MIN_GRID_POINTS)
    return parser.parse_args()


def project_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def require_shadow_output(path: Path, label: str) -> None:
    try:
        path.resolve().relative_to(SHADOW_ROOT.resolve())
    except ValueError as exc:
        raise ValueError(f"{label} 必須位於 artifacts/shadow/model_runtime_migration") from exc


def main() -> int:
    args = parse_args()
    source = project_path(args.source)
    output = project_path(args.output)
    report = project_path(args.report)
    require_shadow_output(output, "output")
    require_shadow_output(report, "report")
    result = build_migration_candidate(
        source,
        output,
        report,
        grid_points=args.grid_points,
    )
    print(
        json.dumps(
            {
                "status": result["verdict"]["status"],
                "candidate": result["candidate"],
                "report": report.relative_to(PROJECT_ROOT).as_posix(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result["verdict"]["status"] == "GO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
