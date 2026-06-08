#!/usr/bin/env python3
"""驗證 alpha candidate overlay replay artifact。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "model_experiments"
CONTRACT_TRUE_FLAGS = {
    "research_only",
    "in_memory_models_only",
    "post_model_overlay_only",
    "does_not_write_models_latest_lgbm",
    "does_not_write_production_features",
    "does_not_change_risk_adjusted_score",
    "does_not_change_production_ranking",
}
ALLOWED_DECISIONS = {"PROMOTE_TO_PORTFOLIO_REPLAY_CANDIDATE", "MONITOR_ONLY", "REJECTED"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify alpha candidate overlay replay")
    parser.add_argument("--artifact", default=None)
    parser.add_argument("--output", default="artifacts/model_experiments/alpha_candidate_overlay_replay_verification_latest.json")
    return parser.parse_args()


def resolve_path(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def latest_artifact() -> Path | None:
    matches = sorted(OUTPUT_DIR.glob("alpha_candidate_overlay_replay_????-??-??.json"))
    return matches[-1] if matches else None


def as_date(value: Any) -> datetime:
    return datetime.strptime(str(value), "%Y-%m-%d")


def missing_report(path: Path) -> dict[str, Any]:
    return {
        "schema_version": "alpha-candidate-overlay-replay-verification.v1",
        "generated_at": datetime.now().isoformat(),
        "status": "FAILED",
        "input": repo_path(path),
        "summary": {"check_count": 1, "failed_count": 1},
        "checks": [{"name": "artifact_exists", "ok": False, "value": repo_path(path)}],
    }


def build_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    contract = payload.get("contract", {})
    policy = contract.get("no_hindsight_policy", {}) if isinstance(contract.get("no_hindsight_policy"), dict) else {}
    summary = payload.get("summary", {})
    inputs = payload.get("inputs", {})
    daily = payload.get("daily", [])
    folds = payload.get("folds", [])
    min_retain = int(summary.get("min_retain_baseline") or inputs.get("min_retain_baseline") or 0)
    top_n = int(inputs.get("top_n") or 10)
    expected_min_overlap = min_retain / top_n if min_retain > 0 and top_n > 0 else 0
    checks: list[dict[str, Any]] = [
        {"name": "schema", "ok": payload.get("schema_version") == "alpha-candidate-overlay-replay.v1", "value": payload.get("schema_version")},
        {"name": "status", "ok": payload.get("status") == "OK", "value": payload.get("status")},
        {"name": "pre_registered", "ok": payload.get("pre_registered") is True, "value": payload.get("pre_registered")},
        {"name": "decision_known", "ok": payload.get("decision") in ALLOWED_DECISIONS, "value": payload.get("decision")},
        {"name": "has_decision_rationale", "ok": bool(str(payload.get("decision_rationale") or "").strip()), "value": payload.get("decision_rationale")},
        {"name": "has_alpha_features", "ok": int(summary.get("alpha_feature_count") or 0) > 0, "value": summary.get("alpha_features")},
        {"name": "has_daily_rows", "ok": isinstance(daily, list) and len(daily) > 0, "value": len(daily) if isinstance(daily, list) else None},
        {"name": "has_folds", "ok": isinstance(folds, list) and len(folds) > 0, "value": len(folds) if isinstance(folds, list) else None},
        {
            "name": "daily_required_fields",
            "ok": all(
                {"trade_date", "baseline_avg_future_return", "overlay_avg_future_return", "return_delta", "overlap_ratio"} <= set(row)
                for row in daily
            ),
            "value": len(daily),
        },
        {
            "name": "promotion_blocked",
            "ok": contract.get("production_promotion_allowed") is False,
            "value": contract.get("production_promotion_allowed"),
        },
        {
            "name": "promotion_gate_variant_present",
            "ok": bool(policy.get("promotion_gate_variant")),
            "value": policy.get("promotion_gate_variant"),
        },
        {
            "name": "new_filters_require_next_run",
            "ok": policy.get("new_filters_require_next_walkforward_run") is True,
            "value": policy.get("new_filters_require_next_walkforward_run"),
        },
        {
            "name": "declared_retain_overlap_met",
            "ok": float(summary.get("avg_overlap_ratio") or 0) + 1e-9 >= expected_min_overlap,
            "value": {
                "avg_overlap_ratio": summary.get("avg_overlap_ratio"),
                "expected_min_overlap": expected_min_overlap,
            },
        },
    ]
    for flag in CONTRACT_TRUE_FLAGS:
        checks.append({"name": f"contract.{flag}", "ok": contract.get(flag) is True, "value": contract.get(flag)})
    for row in folds:
        if row.get("status") != "OK":
            continue
        train_end = row.get("train_end")
        validation_start = row.get("validation_start")
        checks.append(
            {
                "name": f"fold_{row.get('fold')}.train_before_validation",
                "ok": bool(train_end and validation_start and as_date(train_end) < as_date(validation_start)),
                "value": {"train_end": train_end, "validation_start": validation_start},
            }
        )
    failed = [item for item in checks if not item["ok"]]
    return {
        "schema_version": "alpha-candidate-overlay-replay-verification.v1",
        "generated_at": datetime.now().isoformat(),
        "status": "OK" if not failed else "FAILED",
        "input": repo_path(path),
        "summary": {
            "check_count": len(checks),
            "failed_count": len(failed),
        },
        "checks": checks,
    }


def main() -> int:
    args = parse_args()
    artifact = resolve_path(args.artifact) or latest_artifact()
    if artifact is None:
        raise FileNotFoundError("找不到 alpha_candidate_overlay_replay_YYYY-MM-DD.json")
    output = resolve_path(args.output)
    if output is None:
        raise RuntimeError("output path resolution failed")
    report = missing_report(artifact) if not artifact.exists() else build_report(artifact)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"status": report["status"], "output": repo_path(output), **report["summary"]}, ensure_ascii=False))
    return 0 if report["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
