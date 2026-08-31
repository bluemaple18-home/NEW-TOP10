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


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _nonempty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _trial_ids(payload: dict[str, Any]) -> list[Any]:
    value = payload.get("requested_trial_spec_ids")
    if isinstance(value, list):
        return value
    requested = _mapping(payload.get("requested"))
    value = requested.get("trial_spec_ids")
    return value if isinstance(value, list) else []


def _bundle_ref(payload: dict[str, Any]) -> tuple[Any, Any]:
    requested = _mapping(payload.get("requested"))
    binding = _mapping(payload.get("bundle_binding"))
    return (
        payload.get("requested_dataset_bundle_id")
        or requested.get("dataset_bundle_id")
        or binding.get("requested_dataset_bundle_id"),
        payload.get("requested_dataset_bundle_manifest_ref")
        or requested.get("dataset_bundle_manifest_ref")
        or binding.get("requested_dataset_bundle_manifest_ref"),
    )


def _add_error(errors: list[dict[str, str]], entity: object, reason: str) -> None:
    errors.append({"entity": str(entity), "reason": reason})


def verify_batch(
    *, corpus_root: Path, batch_id: str, run_artifact: Path | None = None,
) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    intents: dict[str, dict[str, Any]] = {}
    if not _nonempty_text(batch_id):
        _add_error(errors, "batch", "BATCH_ID_EMPTY")
    for path in sorted((corpus_root / "intents").glob("*.json")):
        payload = _load(path)
        if (payload.get("selection_reason") or {}).get("research_batch_id") != batch_id:
            continue
        schema_errors = validate_research_intent(payload)
        if schema_errors:
            _add_error(errors, path.name, "; ".join(schema_errors))
        intent_id = payload.get("intent_id")
        if not _nonempty_text(intent_id):
            _add_error(errors, path.name, "INTENT_ID_EMPTY")
            continue
        if path.stem != intent_id:
            _add_error(errors, path.name, "INTENT_PATH_ID_MISMATCH")
        if intent_id in intents:
            _add_error(errors, intent_id, "BATCH_INTENT_ID_DUPLICATE")
        intents[str(intent_id)] = payload

    attempts: dict[str, dict[str, Any]] = {}
    for path in sorted((corpus_root / "attempts").glob("*.started.json")):
        payload = _load(path)
        if (payload.get("executor") or {}).get("research_batch_id") != batch_id:
            continue
        schema_errors = validate_attempt_started(payload)
        if schema_errors:
            _add_error(errors, path.name, "; ".join(schema_errors))
        run_id = payload.get("run_id")
        intent_id = payload.get("intent_id")
        if not _nonempty_text(run_id):
            _add_error(errors, path.name, "ATTEMPT_RUN_ID_EMPTY")
            continue
        if not _nonempty_text(intent_id):
            _add_error(errors, path.name, "ATTEMPT_INTENT_ID_EMPTY")
        if path.name != f"{run_id}.started.json":
            _add_error(errors, path.name, "ATTEMPT_PATH_RUN_ID_MISMATCH")
        intent = intents.get(str(payload.get("intent_id")))
        if intent is None:
            _add_error(errors, path.name, "BATCH_INTENT_MISSING")
        else:
            if _trial_ids(payload) != _trial_ids(intent):
                _add_error(errors, path.name, "BATCH_TRIAL_SET_MISMATCH")
            if _bundle_ref(payload) != _bundle_ref(intent):
                _add_error(errors, path.name, "BATCH_BUNDLE_BINDING_MISMATCH")
        if str(run_id) in attempts:
            _add_error(errors, run_id, "BATCH_RUN_ID_DUPLICATE")
        attempts[str(run_id)] = payload
    attempted_intents = {str(payload.get("intent_id")) for payload in attempts.values()}
    for intent_id in sorted(set(intents) - attempted_intents):
        _add_error(errors, intent_id, "BATCH_ATTEMPT_MISSING")

    receipt_ids: list[str] = []
    receipts_by_run: dict[str, dict[str, Any]] = {}
    for run_id, attempt in attempts.items():
        path = corpus_root / "receipts" / f"{run_id}.json"
        if not path.is_file():
            _add_error(errors, run_id, "TERMINAL_RECEIPT_MISSING")
            continue
        receipt = _load(path)
        schema_errors = validate_run_receipt(receipt)
        if schema_errors:
            _add_error(errors, path.name, "; ".join(schema_errors))
        if receipt.get("run_id") != run_id:
            _add_error(errors, path.name, "RECEIPT_RUN_MISMATCH")
        if receipt.get("intent_id") != attempt.get("intent_id"):
            _add_error(errors, path.name, "RECEIPT_INTENT_MISMATCH")
        if receipt.get("attempt_event_id") != attempt.get("attempt_event_id"):
            _add_error(errors, path.name, "RECEIPT_ATTEMPT_EVENT_MISMATCH")
        if _trial_ids(receipt) != _trial_ids(attempt):
            _add_error(errors, path.name, "RECEIPT_TRIAL_SET_MISMATCH")
        if _bundle_ref(receipt) != _bundle_ref(attempt):
            _add_error(errors, path.name, "RECEIPT_BUNDLE_BINDING_MISMATCH")
        receipt_id = receipt.get("receipt_id")
        if not _nonempty_text(receipt_id):
            _add_error(errors, path.name, "RECEIPT_ID_EMPTY")
        else:
            receipt_ids.append(str(receipt_id))
        receipts_by_run[run_id] = receipt

    empty_outcome = False
    if run_artifact is not None and run_artifact.is_file():
        run = _load(run_artifact)
        if (run.get("inputs") or {}).get("research_batch_id") != batch_id:
            _add_error(errors, run_artifact.name, "RUN_ARTIFACT_BATCH_MISMATCH")
        topic_runs = run.get("topic_runs") or []
        empty_outcome = not topic_runs and (
            (run.get("outcome") or {}).get("decision")
            in {"NO_EXECUTABLE_TOPIC", "TOPIC_SUPPLY_EXHAUSTED", "TOPIC_SUPPLY_ATTEMPT_BUDGET_EXCEEDED"}
        )
        for index, topic_run in enumerate(topic_runs):
            entity = f"{run_artifact.name}:topic_runs[{index}]"
            spine = _mapping(_mapping(topic_run).get("research_spine"))
            run_id = spine.get("run_id")
            intent_id = spine.get("intent_id")
            receipt_id = spine.get("receipt_id")
            receipt_path = spine.get("receipt_path")
            if not _nonempty_text(run_id):
                _add_error(errors, entity, "RUN_ARTIFACT_RUN_EMPTY")
                continue
            attempt = attempts.get(str(run_id))
            receipt = receipts_by_run.get(str(run_id))
            if attempt is None or receipt is None:
                _add_error(errors, entity, "RUN_ARTIFACT_RUN_MISMATCH")
                continue
            if intent_id != attempt.get("intent_id"):
                _add_error(errors, entity, "RUN_ARTIFACT_INTENT_MISMATCH")
            if receipt_id != receipt.get("receipt_id"):
                _add_error(errors, entity, "RUN_ARTIFACT_RECEIPT_MISMATCH")
            if not _nonempty_text(receipt_path) or Path(str(receipt_path)).name != f"{run_id}.json":
                _add_error(errors, entity, "RUN_ARTIFACT_RECEIPT_PATH_MISMATCH")
    if not attempts and not empty_outcome:
        _add_error(errors, batch_id, "NO_ATTEMPT_OR_PROVEN_EMPTY_OUTCOME")

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
