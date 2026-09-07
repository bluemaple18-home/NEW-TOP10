#!/usr/bin/env python3
"""發布由 Storage Guard metadata 綁定的 Fog terminal evidence。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.fog_natural_acceptance import write_terminal_evidence  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", required=True)
    parser.add_argument("--scheduled-at", required=True)
    parser.add_argument("--invocation-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--artifact-run-date", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    path = write_terminal_evidence(
        PROJECT_ROOT,
        job=args.job,
        scheduled_at=args.scheduled_at,
        invocation_id=args.invocation_id,
        run_id=args.run_id,
        artifact_run_date=args.artifact_run_date,
    )
    print(json.dumps({"status": "OK", "path": path.relative_to(PROJECT_ROOT).as_posix()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
