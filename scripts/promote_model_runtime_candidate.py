#!/usr/bin/env python3
"""將已通過 gate 的 runtime migration candidate 原子 promotion。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.modeling.model_runtime_promotion import (  # noqa: E402
    PromotionError,
    promote_model_runtime_candidate,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="原子 promotion sklearn runtime migration candidate"
    )
    parser.add_argument(
        "--candidate",
        default="artifacts/shadow/model_runtime_migration/latest_lgbm.pkl",
    )
    parser.add_argument(
        "--verdict",
        default="artifacts/shadow/model_runtime_migration/verdict.json",
    )
    parser.add_argument(
        "--backup",
        default="models/backup/latest_lgbm.pre-runtime-migration.pkl",
    )
    parser.add_argument(
        "--report",
        default="artifacts/model_runtime_promotion/promotion.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = promote_model_runtime_candidate(
            PROJECT_ROOT,
            Path(args.candidate),
            Path(args.verdict),
            Path(args.backup),
            Path(args.report),
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": exc.status if isinstance(exc, PromotionError) else "ERROR",
                    "error": str(exc),
                    "report": (
                        exc.report_path.relative_to(PROJECT_ROOT).as_posix()
                        if isinstance(exc, PromotionError)
                        else None
                    ),
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1

    print(
        json.dumps(
            {
                "status": result["status"],
                "backup": result["backup"],
                "report": Path(args.report).as_posix(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
