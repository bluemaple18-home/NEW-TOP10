#!/usr/bin/env python3
"""建立 deterministic、不可執行的 shadow research plan proposal。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.research.shadow_plan_proposal import (
    DEFAULT_CATALOG_RELATIVE,
    DEFAULT_OUTPUT_RELATIVE,
    DEFAULT_POLICY_RELATIVE,
    DEFAULT_PROJECTION_RELATIVE,
    PROJECT_ROOT,
    ProposalBoundaryError,
    authorize_output_path,
    build_proposal,
    write_deterministic_output,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--projection", type=Path, default=DEFAULT_PROJECTION_RELATIVE)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY_RELATIVE)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG_RELATIVE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_RELATIVE)
    args = parser.parse_args()
    try:
        output = authorize_output_path(
            args.output,
            expected_relative=DEFAULT_OUTPUT_RELATIVE,
            project_root=PROJECT_ROOT,
        )
        payload = build_proposal(
            projection_path=args.projection,
            policy_path=args.policy,
            catalog_path=args.catalog,
            project_root=PROJECT_ROOT,
        )
        write_deterministic_output(output, payload)
    except ProposalBoundaryError as exc:
        print(
            json.dumps({"status": "FAIL", "reason_code": str(exc)}, sort_keys=True),
            file=sys.stderr,
        )
        return 2
    print(
        json.dumps(
            {
                "status": payload["status"],
                "proposal_set_id": payload["proposal_set_id"],
                "output": DEFAULT_OUTPUT_RELATIVE.as_posix(),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
