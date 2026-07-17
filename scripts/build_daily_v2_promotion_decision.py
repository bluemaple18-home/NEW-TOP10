#!/usr/bin/env python3
"""建立 Daily V2 promotion GO/NO-GO；永不執行 production switch。"""

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

from app.workflows.daily_v2_promotion import build_daily_v2_promotion_decision_from_files  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="建立 Daily V2 production promotion decision")
    parser.add_argument("--parity", type=Path, action="append", required=True)
    parser.add_argument("--script-governance", type=Path, required=True)
    parser.add_argument("--acceptance", type=Path)
    parser.add_argument("--independent-review", type=Path)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--output", type=Path, default=Path(".work/ARCH-UPGRADE-06/evidence/promotion_decision.json"))
    return parser.parse_args()


def resolve(path: Path | None) -> Path | None:
    if path is None:
        return None
    return path.resolve() if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def main() -> int:
    args = parse_args()
    decision = build_daily_v2_promotion_decision_from_files(
        parity_paths=[resolve(path) for path in args.parity],
        script_governance_path=resolve(args.script_governance),
        acceptance_path=resolve(args.acceptance),
        independent_review_path=resolve(args.independent_review),
        expected_base_sha=args.base_sha,
        expected_candidate_sha=args.candidate_sha,
    )
    output = resolve(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    print(json.dumps({"status": decision["status"], "decision": decision["decision"], "output": str(output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
