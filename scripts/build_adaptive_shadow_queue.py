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
    DEFAULT_BUNDLE,
    DEFAULT_CANONICAL_QUEUE,
    DEFAULT_MANIFEST,
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_POLICY,
    PROJECT_ROOT,
    build_and_write,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--canonical-queue", type=Path, default=DEFAULT_CANONICAL_QUEUE)
    args = parser.parse_args()
    result = build_and_write(
        bundle_path=args.bundle,
        manifest_path=args.manifest,
        policy_path=args.policy,
        output_root=args.output_root,
        canonical_queue_path=args.canonical_queue,
        project_root=PROJECT_ROOT,
    )
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
