#!/usr/bin/env python3
"""驗證單次 daily invocation 的 native Research Spine terminal facts。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.research.contracts import (
    validate_attempt_started,
    validate_research_intent,
    validate_run_receipt,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_batch(
    *, corpus_root: Path, batch_id: str, run_artifact: Path | None = None,
) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    intents: dict[str, dict[str, Any]] = {}
    for path in sorted((corpus_root / "intents").glob("*.json")):
        payload = _load(path)
        if (payload.get("selection_reason") or {}).get("research_batch_id") != batch_id:
            continue
        schema_errors = validate_research_intent(payload)
        if schema_errors:
            errors.append({"entity": path.name, "reason": "; ".join(schema_errors)})
        intents[str(payload.get("intent_id"))] = payload

    attempts: dict[str, dict[str, Any]] = {}
    for path in sorted((corpus_root / "attempts").glob("*.started.json")):
        payload = _load(path)
        if (payload.get("executor") or {}).get("research_batch_id") != batch_id:
            continue
        schema_errors = validate_attempt_started(payload)
        if schema_errors:
            errors.append({"entity": path.name, "reason": "; ".join(schema_errors)})
        intent = intents.get(str(payload.get("intent_id")))
        if intent is None:
            errors.append({"entity": path.name, "reason": "BATCH_INTENT_MISSING"})
        elif set(payload.get("requested_trial_spec_ids") or []) != set(
            intent.get("requested_trial_spec_ids") or []
        ):
            errors.append({"entity": path.name, "reason": "BATCH_TRIAL_SET_MISMATCH"})
        attempts[str(payload.get("run_id"))] = payload
    attempted_intents = {str(payload.get("intent_id")) for payload in attempts.values()}
    for intent_id in sorted(set(intents) - attempted_intents):
        errors.append({"entity": intent_id, "reason": "BATCH_ATTEMPT_MISSING"})

    receipt_ids: list[str] = []
    for run_id, attempt in attempts.items():
        path = corpus_root / "receipts" / f"{run_id}.json"
        if not path.is_file():
            errors.append({"entity": run_id, "reason": "TERMINAL_RECEIPT_MISSING"})
            continue
        receipt = _load(path)
        schema_errors = validate_run_receipt(receipt)
        if schema_errors:
            errors.append({"entity": path.name, "reason": "; ".join(schema_errors)})
        if receipt.get("intent_id") != attempt.get("intent_id"):
            errors.append({"entity": path.name, "reason": "RECEIPT_INTENT_MISMATCH"})
        receipt_ids.append(str(receipt.get("receipt_id")))

    empty_outcome = False
    if run_artifact is not None and run_artifact.is_file():
        run = _load(run_artifact)
        if (run.get("inputs") or {}).get("research_batch_id") != batch_id:
            errors.append({"entity": run_artifact.name, "reason": "RUN_ARTIFACT_BATCH_MISMATCH"})
        empty_outcome = not (run.get("topic_runs") or []) and (
            (run.get("outcome") or {}).get("decision")
            in {"NO_EXECUTABLE_TOPIC", "TOPIC_SUPPLY_EXHAUSTED", "TOPIC_SUPPLY_ATTEMPT_BUDGET_EXCEEDED"}
        )
    if not attempts and not empty_outcome:
        errors.append({"entity": batch_id, "reason": "NO_ATTEMPT_OR_PROVEN_EMPTY_OUTCOME"})

    return {
        "schema_version": "research-spine-batch-verification.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if not errors else "FAIL",
        "research_batch_id": batch_id,
        "intent_ids": sorted(intents),
        "run_ids": sorted(attempts),
        "receipt_ids": sorted(receipt_ids),
        "intent_count": len(intents),
        "attempt_count": len(attempts),
        "receipt_count": len(receipt_ids),
        "empty_outcome": empty_outcome,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-id", required=True)
    parser.add_argument(
        "--corpus-root", type=Path,
        default=PROJECT_ROOT / "artifacts/autonomous_research/research_spine",
    )
    parser.add_argument("--run-artifact", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify_batch(
        corpus_root=args.corpus_root,
        batch_id=args.batch_id,
        run_artifact=args.run_artifact,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
