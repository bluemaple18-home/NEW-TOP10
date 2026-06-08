#!/usr/bin/env python3
"""驗證 alpha overlay portfolio replay artifact。"""

from __future__ import annotations

import argparse
import copy
import json
import tempfile
from datetime import datetime
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.research_alpha_candidate_overlay_portfolio_replay import (  # noqa: E402
    DECISION_PROMOTE,
    DECISION_REJECTED,
    GROUP_EXPOSURE_REQUIRED,
    MAX_GROUP_EXPOSURE_DELTA,
    MAX_TURNOVER_DELTA,
    MIN_BUCKET_VALID_TRADES,
    MIN_FOLD_DATES,
    MIN_FOLDS,
    MIN_POSITIVE_FOLDS,
    MIN_RETURN_DELTA,
    gate_failures,
)

OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "model_experiments"
CONTRACT_TRUE_FLAGS = {
    "research_only",
    "portfolio_bucket_proxy",
    "does_not_train_model",
    "does_not_write_models_latest_lgbm",
    "does_not_write_production_features",
    "does_not_change_risk_adjusted_score",
    "does_not_change_production_ranking",
}
ALLOWED_DECISIONS = {DECISION_PROMOTE, DECISION_REJECTED}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify alpha overlay portfolio replay")
    parser.add_argument("--artifact", default=None)
    parser.add_argument("--output", default="artifacts/model_experiments/alpha_candidate_overlay_portfolio_replay_verification_latest.json")
    parser.add_argument("--self-test", action="store_true", help="run verifier mutation self-tests")
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
    matches = sorted(OUTPUT_DIR.glob("alpha_candidate_overlay_portfolio_replay_????-??-??.json"))
    return matches[-1] if matches else None


def missing_report(path: Path) -> dict[str, Any]:
    return {
        "schema_version": "alpha-candidate-overlay-portfolio-replay-verification.v1",
        "generated_at": datetime.now().isoformat(),
        "status": "FAILED",
        "input": repo_path(path),
        "summary": {"check_count": 1, "failed_count": 1},
        "checks": [{"name": "artifact_exists", "ok": False, "value": repo_path(path)}],
    }


def build_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    contract = payload.get("contract", {})
    summary = payload.get("summary", {})
    decision_policy = payload.get("decision_policy", {})
    daily = payload.get("daily", [])
    recomputed_failures = gate_failures(summary) if isinstance(summary, dict) else ["summary_missing"]
    expected_decision = DECISION_REJECTED if recomputed_failures else DECISION_PROMOTE
    checks: list[dict[str, Any]] = [
        {
            "name": "schema",
            "ok": payload.get("schema_version") == "alpha-candidate-overlay-portfolio-replay.v1",
            "value": payload.get("schema_version"),
        },
        {"name": "status", "ok": payload.get("status") == "OK", "value": payload.get("status")},
        {"name": "pre_registered", "ok": payload.get("pre_registered") is True, "value": payload.get("pre_registered")},
        {"name": "decision_known", "ok": payload.get("decision") in ALLOWED_DECISIONS, "value": payload.get("decision")},
        {
            "name": "decision_matches_recomputed_gate",
            "ok": payload.get("decision") == expected_decision,
            "value": {
                "decision": payload.get("decision"),
                "expected": expected_decision,
                "failures": recomputed_failures,
            },
        },
        {"name": "has_decision_rationale", "ok": bool(str(payload.get("decision_rationale") or "").strip()), "value": payload.get("decision_rationale")},
        {"name": "has_daily_rows", "ok": isinstance(daily, list) and len(daily) > 0, "value": len(daily) if isinstance(daily, list) else None},
        {"name": "has_baseline_summary", "ok": isinstance(summary.get("baseline"), dict), "value": summary.get("baseline")},
        {"name": "has_overlay_summary", "ok": isinstance(summary.get("overlay"), dict), "value": summary.get("overlay")},
        {"name": "fold_count", "ok": int(summary.get("fold_count") or 0) >= MIN_FOLDS, "value": summary.get("fold_count")},
        {
            "name": "baseline_min_valid_trade_count",
            "ok": int((summary.get("baseline") or {}).get("min_valid_trade_count") or 0) >= MIN_BUCKET_VALID_TRADES,
            "value": (summary.get("baseline") or {}).get("min_valid_trade_count"),
        },
        {
            "name": "overlay_min_valid_trade_count",
            "ok": int((summary.get("overlay") or {}).get("min_valid_trade_count") or 0) >= MIN_BUCKET_VALID_TRADES,
            "value": (summary.get("overlay") or {}).get("min_valid_trade_count"),
        },
        {"name": "return_delta_present", "ok": summary.get("return_delta") is not None, "value": summary.get("return_delta")},
        {"name": "max_drawdown_delta_present", "ok": summary.get("max_drawdown_delta") is not None, "value": summary.get("max_drawdown_delta")},
        {"name": "turnover_delta_present", "ok": summary.get("turnover_delta") is not None, "value": summary.get("turnover_delta")},
        {
            "name": "group_exposure_delta_present",
            "ok": summary.get("avg_max_group_exposure_delta") is not None,
            "value": summary.get("avg_max_group_exposure_delta"),
        },
        {"name": "policy.min_return_delta", "ok": decision_policy.get("min_return_delta") == MIN_RETURN_DELTA, "value": decision_policy.get("min_return_delta")},
        {"name": "policy.min_positive_folds", "ok": decision_policy.get("min_positive_folds") == MIN_POSITIVE_FOLDS, "value": decision_policy.get("min_positive_folds")},
        {"name": "policy.min_folds", "ok": decision_policy.get("min_folds") == MIN_FOLDS, "value": decision_policy.get("min_folds")},
        {"name": "policy.min_fold_dates", "ok": decision_policy.get("min_fold_dates") == MIN_FOLD_DATES, "value": decision_policy.get("min_fold_dates")},
        {
            "name": "policy.min_bucket_valid_trades",
            "ok": decision_policy.get("min_bucket_valid_trades") == MIN_BUCKET_VALID_TRADES,
            "value": decision_policy.get("min_bucket_valid_trades"),
        },
        {"name": "policy.max_turnover_delta", "ok": decision_policy.get("max_turnover_delta") == MAX_TURNOVER_DELTA, "value": decision_policy.get("max_turnover_delta")},
        {
            "name": "policy.max_group_exposure_delta",
            "ok": decision_policy.get("max_group_exposure_delta") == MAX_GROUP_EXPOSURE_DELTA,
            "value": decision_policy.get("max_group_exposure_delta"),
        },
        {
            "name": "policy.group_exposure_required",
            "ok": decision_policy.get("group_exposure_required") is GROUP_EXPOSURE_REQUIRED,
            "value": decision_policy.get("group_exposure_required"),
        },
        {
            "name": "promotion_blocked",
            "ok": contract.get("production_promotion_allowed") is False,
            "value": contract.get("production_promotion_allowed"),
        },
    ]
    for flag in CONTRACT_TRUE_FLAGS:
        checks.append({"name": f"contract.{flag}", "ok": contract.get(flag) is True, "value": contract.get(flag)})
    failed = [item for item in checks if not item["ok"]]
    return {
        "schema_version": "alpha-candidate-overlay-portfolio-replay-verification.v1",
        "generated_at": datetime.now().isoformat(),
        "status": "OK" if not failed else "FAILED",
        "input": repo_path(path),
        "summary": {
            "check_count": len(checks),
            "failed_count": len(failed),
        },
        "checks": checks,
    }


def self_test_payload() -> dict[str, Any]:
    baseline = {
        "date_count": 60,
        "avg_net_return": 0.05,
        "hit_rate": 0.6,
        "compounded_return": 0.4,
        "max_drawdown": -0.25,
        "turnover": 0.35,
        "avg_max_group_exposure": 0.3,
        "min_valid_trade_count": MIN_BUCKET_VALID_TRADES,
        "incomplete_bucket_count": 0,
    }
    overlay = {
        "date_count": 60,
        "avg_net_return": 0.06,
        "hit_rate": 0.62,
        "compounded_return": 0.5,
        "max_drawdown": -0.2,
        "turnover": 0.4,
        "avg_max_group_exposure": 0.28,
        "min_valid_trade_count": MIN_BUCKET_VALID_TRADES,
        "incomplete_bucket_count": 0,
    }
    folds = [
        {
            "fold": 1,
            "baseline": {**baseline, "date_count": MIN_FOLD_DATES},
            "overlay": {**overlay, "date_count": MIN_FOLD_DATES},
            "return_delta": -0.001,
        },
        {
            "fold": 2,
            "baseline": {**baseline, "date_count": MIN_FOLD_DATES},
            "overlay": {**overlay, "date_count": MIN_FOLD_DATES},
            "return_delta": 0.015,
        },
        {
            "fold": 3,
            "baseline": {**baseline, "date_count": MIN_FOLD_DATES},
            "overlay": {**overlay, "date_count": MIN_FOLD_DATES},
            "return_delta": 0.02,
        },
    ]
    return {
        "schema_version": "alpha-candidate-overlay-portfolio-replay.v1",
        "generated_at": datetime.now().isoformat(),
        "date": "2026-06-06",
        "status": "OK",
        "pre_registered": True,
        "decision": DECISION_PROMOTE,
        "decision_rationale": "portfolio replay 通過 gate；可進 promotion review candidate。",
        "decision_policy": {
            "min_return_delta": MIN_RETURN_DELTA,
            "min_positive_folds": MIN_POSITIVE_FOLDS,
            "min_folds": MIN_FOLDS,
            "min_fold_dates": MIN_FOLD_DATES,
            "min_bucket_valid_trades": MIN_BUCKET_VALID_TRADES,
            "max_turnover_delta": MAX_TURNOVER_DELTA,
            "max_group_exposure_delta": MAX_GROUP_EXPOSURE_DELTA,
            "group_exposure_required": GROUP_EXPOSURE_REQUIRED,
            "max_drawdown_must_not_worsen": True,
            "production_promotion_allowed": False,
        },
        "contract": {
            "research_only": True,
            "portfolio_bucket_proxy": True,
            "does_not_train_model": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_write_production_features": True,
            "does_not_change_risk_adjusted_score": True,
            "does_not_change_production_ranking": True,
            "production_promotion_allowed": False,
        },
        "summary": {
            "baseline": baseline,
            "overlay": overlay,
            "fold_count": MIN_FOLDS,
            "return_delta": 0.01,
            "positive_day_count": 40,
            "negative_day_count": 20,
            "positive_fold_count": MIN_POSITIVE_FOLDS,
            "max_drawdown_delta": 0.05,
            "turnover_delta": 0.05,
            "avg_max_group_exposure_delta": -0.02,
            "folds": folds,
        },
        "daily": [{"ranking_date": "2026-01-02"}],
    }


def write_self_test_payload(directory: Path, name: str, payload: dict[str, Any]) -> Path:
    path = directory / f"{name}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return path


def run_self_test() -> int:
    cases: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as raw_directory:
        directory = Path(raw_directory)
        valid_payload = self_test_payload()

        bad_metrics = copy.deepcopy(valid_payload)
        bad_metrics["summary"]["return_delta"] = -0.5
        bad_metrics["summary"]["positive_fold_count"] = 0
        bad_metrics["summary"]["max_drawdown_delta"] = -0.5

        missing_fold = copy.deepcopy(valid_payload)
        missing_fold["summary"]["fold_count"] = MIN_FOLDS - 1
        missing_fold["summary"]["folds"] = missing_fold["summary"]["folds"][: MIN_FOLDS - 1]

        missing_group_delta = copy.deepcopy(valid_payload)
        missing_group_delta["summary"]["avg_max_group_exposure_delta"] = None

        rejected_consistent = copy.deepcopy(valid_payload)
        rejected_consistent["decision"] = DECISION_REJECTED
        rejected_consistent["decision_rationale"] = "portfolio replay 未通過：return_delta<=0"
        rejected_consistent["summary"]["return_delta"] = -0.01

        fixtures = [
            ("valid_promote", valid_payload, "OK"),
            ("bad_metrics_promote", bad_metrics, "FAILED"),
            ("missing_fold_promote", missing_fold, "FAILED"),
            ("missing_group_delta_promote", missing_group_delta, "FAILED"),
            ("rejected_consistent", rejected_consistent, "OK"),
        ]
        for name, payload, expected in fixtures:
            report = build_report(write_self_test_payload(directory, name, payload))
            cases.append(
                {
                    "name": name,
                    "expected": expected,
                    "actual": report["status"],
                    "ok": report["status"] == expected,
                    "failed_count": report["summary"]["failed_count"],
                }
            )

    failed = [case for case in cases if not case["ok"]]
    report = {
        "status": "OK" if not failed else "FAILED",
        "case_count": len(cases),
        "failed_count": len(failed),
        "cases": cases,
    }
    print(json.dumps(report, ensure_ascii=False))
    return 0 if not failed else 1


def main() -> int:
    args = parse_args()
    if args.self_test:
        return run_self_test()
    artifact = resolve_path(args.artifact) or latest_artifact()
    if artifact is None:
        raise FileNotFoundError("找不到 alpha_candidate_overlay_portfolio_replay_YYYY-MM-DD.json")
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
