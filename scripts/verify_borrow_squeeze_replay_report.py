#!/usr/bin/env python3
"""驗證 borrow-squeeze replay 報告。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "borrow-squeeze-replay.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify borrow-squeeze replay report")
    parser.add_argument("--artifact", default="artifacts/model_experiments/borrow_squeeze_replay_2026-06-22.json")
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def main() -> int:
    args = parse_args()
    artifact = resolve_path(args.artifact)
    errors: list[str] = []
    if not artifact.exists():
        errors.append(f"artifact missing: {artifact}")
        print(json.dumps({"status": "FAILED", "errors": errors}, ensure_ascii=False))
        return 1

    payload = json.loads(artifact.read_text(encoding="utf-8"))
    contract = payload.get("contract") or {}
    summary = payload.get("summary") or {}
    decision = payload.get("decision") or {}

    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version mismatch")
    if payload.get("status") != "OK":
        errors.append("status must be OK")
    for key in ("research_only", "replay_only", "does_not_send_push", "uses_existing_features_only"):
        if contract.get(key) is not True:
            errors.append(f"contract.{key} must be true")
    for key in ("changes_model", "changes_production_ranking", "changes_risk_adjusted_score"):
        if contract.get(key) is not False:
            errors.append(f"contract.{key} must be false")
    if decision.get("production_status") != "BLOCKED":
        errors.append("production must remain blocked")
    if decision.get("status") not in {"MONITOR_ONLY", "REPLAY_BLOCKED"}:
        errors.append("decision.status must be a known replay decision")
    if int(summary.get("observation_count") or 0) <= 0:
        errors.append("observation_count must be positive")
    if int(summary.get("cap_hit_count") or 0) <= 0:
        errors.append("cap_hit_count must be positive")
    if "composite_signal_count" not in summary:
        errors.append("composite_signal_count missing")
    if not payload.get("observations"):
        errors.append("observations missing")
    else:
        first = payload["observations"][0]
        for key in ("price_breakout_confirm", "industry_turning_strong", "forward_returns"):
            if key not in first:
                errors.append(f"observation missing key: {key}")

    status = "OK" if not errors else "FAILED"
    print(json.dumps({"status": status, "artifact": str(artifact), "errors": errors}, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
