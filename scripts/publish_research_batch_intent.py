#!/usr/bin/env python3
"""發布 daily research runner 的 immutable Batch Intent。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.research.batch_owner import build_batch_intent, publish_batch_intent  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="publish immutable research Batch Intent")
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--execution-epoch", required=True)
    parser.add_argument("--requested-research-stage", required=True)
    parser.add_argument("--allowed-research-stage", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--corpus-root",
        type=Path,
        default=PROJECT_ROOT / "artifacts/autonomous_research/research_spine",
    )
    parser.add_argument(
        "--ledger",
        type=Path,
        default=PROJECT_ROOT / "data/research/research_ledger.duckdb",
    )
    parser.add_argument(
        "--policy",
        type=Path,
        default=PROJECT_ROOT / "config/native_evidence_activation_policy_v1.json",
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=PROJECT_ROOT / "config/research_parameter_catalog.json",
    )
    parser.add_argument("runner_argv", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    runner_argv = list(args.runner_argv)
    if runner_argv and runner_argv[0] == "--":
        runner_argv = runner_argv[1:]
    payload = build_batch_intent(
        project_root=PROJECT_ROOT,
        corpus_root=args.corpus_root,
        batch_id=args.batch_id,
        scheduler_entrypoint=PROJECT_ROOT / "scripts/run_daily_research_quota.sh",
        runner_argv=runner_argv,
        output_path=args.output,
        ledger_path=args.ledger,
        requested_research_stage=args.requested_research_stage,
        allowed_research_stages=args.allowed_research_stage,
        policy_path=args.policy,
        catalog_path=args.catalog,
        execution_epoch=args.execution_epoch,
    )
    publish_batch_intent(corpus_root=args.corpus_root, payload=payload)
    print(str(payload["batch_intent_id"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
