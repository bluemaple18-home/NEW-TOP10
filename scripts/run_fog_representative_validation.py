#!/usr/bin/env python3
"""只在 storage validation sandbox 執行歷史 exact-regime 代表性 topic。"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DATE = "2026-08-31"
FIXTURE_IDENTITY = {
    "base_regime": "NARROW_LEADER",
    "family_tags": ["BIG_BULL", "HIGH_CHOPPY"],
}
CANDIDATE_DIR = (
    "artifacts/backtest/"
    "historical_rankings_current_model_batch_dense_2023-11-21_2026-05-15"
)
BASELINE_DIR = (
    "artifacts/backtest/"
    "historical_rankings_current_model_fog_2025-06-03_2026-07-28_ce643797"
)
FIXTURE_ROOT = Path("artifacts/autonomous_research/validation_fixture")


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def fail(reason: str, completed: subprocess.CompletedProcess[str] | None = None) -> int:
    payload: dict[str, Any] = {"status": "FAIL", "reason_code": reason}
    if completed is not None:
        payload.update(
            {
                "returncode": completed.returncode,
                "stdout_tail": completed.stdout[-2000:],
                "stderr_tail": completed.stderr[-2000:],
            }
        )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True), file=sys.stderr)
    return 1


def main() -> int:
    if os.environ.get("TOP10_STORAGE_VALIDATION_MODE") != "1":
        return fail("VALIDATION_MODE_REQUIRED")
    if (PROJECT_ROOT / ".git").exists():
        return fail("NO_GIT_VALIDATION_ROOT_REQUIRED")

    python_bin = PROJECT_ROOT / ".venv" / "bin" / "python"
    source_history = PROJECT_ROOT / "artifacts" / "market_regime_history.json"
    fixture_root = PROJECT_ROOT / FIXTURE_ROOT
    fixture_history = fixture_root / "market_regime_history.json"
    corpus_root = fixture_root / "research_spine"
    ledger = fixture_root / "research_ledger.duckdb"
    output = fixture_root / f"fog_representative_validation_{FIXTURE_DATE}.json"
    verification = fixture_root / f"fog_representative_batch_verification_{FIXTURE_DATE}.json"
    fixture_root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_history, fixture_history)

    history = json.loads(fixture_history.read_text(encoding="utf-8"))
    rows = history.get("rows") if isinstance(history.get("rows"), list) else []
    matching = [row for row in rows if row.get("trade_date") == FIXTURE_DATE]
    if len(matching) != 1 or {
        "base_regime": matching[0].get("base_regime"),
        "family_tags": sorted(matching[0].get("family_tags") or []),
    } != FIXTURE_IDENTITY:
        return fail("FIXTURE_REGIME_IDENTITY_MISMATCH")

    batch_id = (
        f"research-{FIXTURE_DATE}-{datetime.now().strftime('%H%M%S')}-{os.getpid()}"
    )
    relative_output = output.relative_to(PROJECT_ROOT).as_posix()
    relative_corpus = corpus_root.relative_to(PROJECT_ROOT).as_posix()
    relative_ledger = ledger.relative_to(PROJECT_ROOT).as_posix()
    relative_history = fixture_history.relative_to(PROJECT_ROOT).as_posix()
    runner_args = [
        "scripts/run_autonomous_research.py",
        "--date",
        FIXTURE_DATE,
        "--research-batch-id",
        batch_id,
        "--execute",
        "--closed-regime-research",
        "--market-regime-history",
        relative_history,
        "--research-contract",
        "config/regime_research_contract.json",
        "--candidate-dir",
        CANDIDATE_DIR,
        "--baseline-dir",
        BASELINE_DIR,
        "--max-topics",
        "12",
        "--execute-topic-count",
        "1",
        "--development-screen-topic-count",
        "1",
        "--max-ranking-files",
        "8",
        "--development-screen-on-sealed-exhaustion",
        "--output",
        relative_output,
    ]
    publish = run(
        [
            str(python_bin),
            "scripts/publish_research_batch_intent.py",
            "--batch-id",
            batch_id,
            "--execution-epoch",
            FIXTURE_DATE,
            "--requested-research-stage",
            "DEVELOPMENT_SCREEN",
            "--allowed-research-stage",
            "DEVELOPMENT_SCREEN",
            "--output",
            relative_output,
            "--corpus-root",
            relative_corpus,
            "--ledger",
            relative_ledger,
            "--manager-root",
            FIXTURE_ROOT.as_posix(),
            "--",
            *runner_args,
        ]
    )
    if publish.returncode != 0:
        return fail("BATCH_INTENT_PUBLICATION_FAILED", publish)
    intent_id = publish.stdout.strip().splitlines()[-1]
    intent_path = corpus_root / "batch_intents" / f"{intent_id.removeprefix('sha256:')}.json"
    execute = run(
        [
            str(python_bin),
            *runner_args,
            "--research-batch-intent",
            str(intent_path),
        ]
    )
    if execute.returncode != 0:
        return fail("REPRESENTATIVE_TOPIC_EXECUTION_FAILED", execute)
    verify = run(
        [
            str(python_bin),
            "scripts/verify_research_spine_batch.py",
            "--batch-id",
            batch_id,
            "--corpus-root",
            relative_corpus,
            "--run-artifact",
            relative_output,
            "--output",
            verification.relative_to(PROJECT_ROOT).as_posix(),
        ]
    )
    if verify.returncode != 0:
        return fail("REPRESENTATIVE_BATCH_VERIFICATION_FAILED", verify)
    payload = json.loads(output.read_text(encoding="utf-8"))
    topic_runs = payload.get("topic_runs") if isinstance(payload.get("topic_runs"), list) else []
    if not topic_runs:
        return fail("REPRESENTATIVE_WORKLOAD_EMPTY")
    result = {
        "schema_version": "fog-representative-validation.v1",
        "status": "PASS",
        "fixture_date": FIXTURE_DATE,
        "fixture_identity": FIXTURE_IDENTITY,
        "batch_id": batch_id,
        "batch_intent_id": intent_id,
        "topic_runs": topic_runs,
        "production_promotion_allowed": False,
    }
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                "topic_run_count": len(topic_runs),
                "output": relative_output,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
