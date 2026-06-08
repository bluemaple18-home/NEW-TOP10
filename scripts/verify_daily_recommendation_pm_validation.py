#!/usr/bin/env python3
"""驗證每日推薦 PM 風險驗證報告。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "model_experiments"
SCHEMA_VERSION = "daily-recommendation-pm-validation.v1"
ALLOWED_DECISIONS = {"ADVANCE_TO_DAILY_SHADOW", "RESEARCH_SHADOW_WITH_GUARDS", "MONITOR_ONLY", "MISSING"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify daily recommendation PM validation report")
    parser.add_argument("--artifact", default=None)
    parser.add_argument("--min-candidates", type=int, default=8)
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def latest_artifact() -> Path:
    matches = sorted(OUTPUT_DIR.glob("daily_recommendation_pm_validation_????-??-??.json"))
    if not matches:
        raise FileNotFoundError("找不到 daily_recommendation_pm_validation_YYYY-MM-DD.json")
    return matches[-1]


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, value: Any = None) -> None:
    checks.append({"name": name, "ok": bool(ok), "value": value})


def main() -> int:
    args = parse_args()
    path = resolve_path(args.artifact) if args.artifact else latest_artifact()
    payload = json.loads(path.read_text(encoding="utf-8"))
    checks: list[dict[str, Any]] = []
    contract = payload.get("contract") or {}
    candidates = payload.get("candidates") or []
    decisions = {row.get("decision") for row in candidates}

    add_check(checks, "schema_version", payload.get("schema_version") == SCHEMA_VERSION, payload.get("schema_version"))
    for key in (
        "research_only",
        "reads_existing_artifacts_only",
        "does_not_train_model",
        "does_not_write_models_latest_lgbm",
        "does_not_change_production_ranking",
    ):
        add_check(checks, f"contract.{key}", contract.get(key) is True, contract.get(key))
    add_check(checks, "contract.promotion_ready", contract.get("promotion_ready") is False, contract.get("promotion_ready"))
    add_check(checks, "candidate_count", len(candidates) >= args.min_candidates, len(candidates))
    add_check(checks, "allowed_decisions", decisions <= ALLOWED_DECISIONS, sorted(decisions))
    add_check(checks, "baseline_exists", payload.get("baseline", {}).get("exists") is True, payload.get("baseline", {}).get("exists"))
    add_check(checks, "summary_has_best_candidate", bool((payload.get("summary") or {}).get("best_candidate")), payload.get("summary"))

    malformed = [
        row.get("candidate_id")
        for row in candidates
        if row.get("exists") is not True
        or row.get("total_return") is None
        or row.get("max_drawdown") is None
        or not row.get("decision_reasons")
    ]
    add_check(checks, "candidate_shape", not malformed, malformed[:10])

    failed = [check for check in checks if not check["ok"]]
    status = "FAILED" if failed else "OK"
    print(json.dumps({"status": status, "artifact": str(path), "checks": checks}, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
