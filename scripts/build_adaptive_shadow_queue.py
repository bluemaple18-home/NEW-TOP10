#!/usr/bin/env python3
"""Build Card B adaptive shadow queue from committed replay evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.research.adaptive_shadow_queue import (
    DEFAULT_BUNDLE_RELATIVE,
    DEFAULT_CANONICAL_QUEUE_RELATIVE,
    DEFAULT_MANIFEST_RELATIVE,
    DEFAULT_OUTPUT_ROOT_RELATIVE,
    DEFAULT_POLICY_RELATIVE,
    PROJECT_ROOT,
    ShadowQueueBoundaryError,
    authorize_canonical_queue_path,
    authorize_committed_input,
    authorize_output_root,
    build_and_write,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE_RELATIVE)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_RELATIVE)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY_RELATIVE)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT_RELATIVE)
    parser.add_argument("--canonical-queue", type=Path, default=DEFAULT_CANONICAL_QUEUE_RELATIVE)
    args = parser.parse_args()
    try:
        output_root = authorize_output_root(
            args.output_root,
            project_root=PROJECT_ROOT,
            require_repo_relative=True,
        )
        bundle_path = authorize_committed_input(
            args.bundle,
            kind="bundle",
            project_root=PROJECT_ROOT,
            require_repo_relative=True,
        )
        manifest_path = authorize_committed_input(
            args.manifest,
            kind="manifest",
            project_root=PROJECT_ROOT,
            require_repo_relative=True,
        )
        policy_path = authorize_committed_input(
            args.policy,
            kind="policy",
            project_root=PROJECT_ROOT,
            require_repo_relative=True,
        )
        canonical_queue_path = authorize_canonical_queue_path(
            args.canonical_queue,
            project_root=PROJECT_ROOT,
            require_repo_relative=True,
        )
        result = build_and_write(
            bundle_path=bundle_path,
            manifest_path=manifest_path,
            policy_path=policy_path,
            output_root=output_root,
            canonical_queue_path=canonical_queue_path,
            project_root=PROJECT_ROOT,
        )
    except ShadowQueueBoundaryError as exc:
        print(
            json.dumps(
                {"status": "FAIL", "reason_code": str(exc)},
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    projection = result["projection"]
    print(
        json.dumps(
            {
                "status": projection["status"],
                "projection_id": projection["projection_id"],
                "semantic_hash": projection["semantic_hash"],
                "counts": projection["counts"],
                "canonical_parity": projection["canonical_parity"],
                "capacity_receipt": projection["capacity_receipt"],
                "paths": result["paths"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if projection["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
