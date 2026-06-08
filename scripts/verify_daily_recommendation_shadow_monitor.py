#!/usr/bin/env python3
"""驗證每日推薦 shadow monitor artifact。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "model_experiments"
SCHEMA_VERSION = "daily-recommendation-shadow-monitor.v1"
ALLOWED_DECISIONS = {"DAILY_SHADOW_READY", "DAILY_SHADOW_READY_WITH_REGIME_GAP"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify daily recommendation shadow monitor")
    parser.add_argument("--artifact", default=None)
    parser.add_argument("--expected-days", type=int, default=7)
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def latest_artifact() -> Path:
    matches = sorted(OUTPUT_DIR.glob("daily_recommendation_shadow_monitor_????-??-??.json"))
    if not matches:
        raise FileNotFoundError("找不到 daily_recommendation_shadow_monitor_YYYY-MM-DD.json")
    return matches[-1]


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, value: Any = None) -> None:
    checks.append({"name": name, "ok": bool(ok), "value": value})


def main() -> int:
    args = parse_args()
    path = resolve_path(args.artifact) if args.artifact else latest_artifact()
    payload = json.loads(path.read_text(encoding="utf-8"))
    checks: list[dict[str, Any]] = []
    contract = payload.get("contract") or {}
    summary = payload.get("summary") or {}
    latest = payload.get("latest") or {}

    add_check(checks, "schema_version", payload.get("schema_version") == SCHEMA_VERSION, payload.get("schema_version"))
    for key in (
        "research_only",
        "shadow_monitor_only",
        "does_not_train_model",
        "does_not_write_models_latest_lgbm",
        "does_not_change_production_ranking",
        "does_not_send_push",
    ):
        add_check(checks, f"contract.{key}", contract.get(key) is True, contract.get(key))
    add_check(checks, "contract.promotion_ready", contract.get("promotion_ready") is False, contract.get("promotion_ready"))
    add_check(checks, "date_count", summary.get("date_count") == args.expected_days, summary.get("date_count"))
    add_check(checks, "decision_allowed", summary.get("decision") in ALLOWED_DECISIONS, summary.get("decision"))
    add_check(checks, "avg_overlap_at_least_9", float(summary.get("avg_overlap_count") or 0) >= 9.0, summary.get("avg_overlap_count"))
    add_check(checks, "latest_has_top10", len(latest.get("shadow_top10") or []) == 10, len(latest.get("shadow_top10") or []))
    add_check(checks, "latest_added_one", len(latest.get("added_vs_production") or []) <= 1, latest.get("added_vs_production"))
    add_check(checks, "errors_empty", not payload.get("errors"), payload.get("errors"))

    failed = [check for check in checks if not check["ok"]]
    print(json.dumps({"status": "FAILED" if failed else "OK", "artifact": str(path), "checks": checks}, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
