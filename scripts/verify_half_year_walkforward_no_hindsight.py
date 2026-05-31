#!/usr/bin/env python3
"""驗證 half-year walk-forward artifact 沒有後照鏡升級路徑。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALLOWED_LAYERS = {"model", "ranking", "trading", "operations"}
ALLOWED_DECISIONS = {"PROMOTE_CANDIDATE", "MONITOR_ONLY", "REJECTED"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify half-year walk-forward no-hindsight contract")
    parser.add_argument(
        "--artifact",
        default="artifacts/model_experiments/half_year_walkforward_validation_2026-05-31.json",
    )
    parser.add_argument("--self-test", action="store_true", help="用合成反例驗證 verifier 會擋治理漏洞")
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def require(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def as_date(value: Any) -> datetime:
    return datetime.strptime(str(value), "%Y-%m-%d")


def verify(payload: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    policy = contract.get("no_hindsight_policy") if isinstance(contract.get("no_hindsight_policy"), dict) else {}
    variants = payload.get("variants") if isinstance(payload.get("variants"), dict) else {}

    require(payload.get("status") == "OK", "artifact status must be OK", failures)
    require(bool(str(payload.get("research_question") or "").strip()), "research_question is required", failures)
    require(payload.get("layer") in ALLOWED_LAYERS, "layer must be one of model/ranking/trading/operations", failures)
    require(payload.get("pre_registered") is True, "pre_registered must be true", failures)
    require(payload.get("decision") in ALLOWED_DECISIONS, "decision must be PROMOTE_CANDIDATE/MONITOR_ONLY/REJECTED", failures)
    require(bool(str(payload.get("decision_rationale") or "").strip()), "decision_rationale is required", failures)
    require(isinstance(payload.get("decision_policy"), dict), "decision_policy is required", failures)
    diagnostics = payload.get("diagnostics_not_for_promotion")
    require(isinstance(diagnostics, list) and bool(diagnostics), "diagnostics_not_for_promotion is required", failures)
    require(contract.get("research_only") is True, "artifact must be research_only", failures)
    require(contract.get("in_memory_models_only") is True, "artifact must only train in-memory models", failures)
    require(contract.get("production_promotion_allowed") is False, "artifact must not allow production promotion", failures)
    require(contract.get("does_not_write_models_latest_lgbm") is True, "artifact must not write models/latest_lgbm.pkl", failures)
    require(
        contract.get("does_not_change_risk_adjusted_score") is True,
        "artifact must not change risk_adjusted_score",
        failures,
    )
    require(
        contract.get("does_not_change_production_ranking") is True,
        "artifact must not change production ranking",
        failures,
    )

    require(policy.get("validation_windows_are_chronological") is True, "validation windows must be chronological", failures)
    require(policy.get("train_dates_end_before_validation_start") is True, "train dates must end before validation", failures)
    require(policy.get("promotion_gate_variant") == "current_baseline", "promotion gate must use current_baseline only", failures)
    require(
        policy.get("diagnostic_failures_cannot_define_same_run_filters") is True,
        "diagnostic failures must not define same-run filters",
        failures,
    )
    require(
        policy.get("new_filters_require_next_walkforward_run") is True,
        "new filters must require next walk-forward run",
        failures,
    )
    require(policy.get("regime_breakdown_is_post_hoc_diagnostic") is True, "regime breakdown must be diagnostic", failures)

    diagnostic_only = set(policy.get("diagnostic_only_variants") or [])
    require("drop_planned_features" in diagnostic_only, "drop_planned_features must be diagnostic only", failures)
    require("planned_features_only" in diagnostic_only, "planned_features_only must be diagnostic only", failures)
    require("current_baseline" in variants, "current_baseline variant missing", failures)

    baseline = variants.get("current_baseline") if isinstance(variants.get("current_baseline"), dict) else {}
    folds = baseline.get("folds") if isinstance(baseline.get("folds"), list) else []
    require(bool(folds), "current_baseline folds missing", failures)
    for row in folds:
        if row.get("status") != "OK":
            continue
        train_end = row.get("train_end")
        validation_start = row.get("validation_start")
        require(bool(train_end), f"fold {row.get('fold')} train_end missing", failures)
        require(bool(validation_start), f"fold {row.get('fold')} validation_start missing", failures)
        if train_end and validation_start:
            require(
                as_date(train_end) < as_date(validation_start),
                f"fold {row.get('fold')} train_end must be before validation_start",
                failures,
            )
    return failures


def valid_fixture() -> dict[str, Any]:
    return {
        "schema_version": "regime-feature-offline-ablation.v1",
        "status": "OK",
        "research_question": "近半年模型是否有訊號？",
        "layer": "model",
        "pre_registered": True,
        "decision": "MONITOR_ONLY",
        "decision_rationale": "synthetic fixture",
        "decision_policy": {"negative_folds_force_monitor_only": True},
        "diagnostics_not_for_promotion": ["regime_breakdown"],
        "contract": {
            "research_only": True,
            "in_memory_models_only": True,
            "production_promotion_allowed": False,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_risk_adjusted_score": True,
            "does_not_change_production_ranking": True,
            "no_hindsight_policy": {
                "validation_windows_are_chronological": True,
                "train_dates_end_before_validation_start": True,
                "promotion_gate_variant": "current_baseline",
                "diagnostic_only_variants": ["drop_planned_features", "planned_features_only"],
                "diagnostic_failures_cannot_define_same_run_filters": True,
                "new_filters_require_next_walkforward_run": True,
                "regime_breakdown_is_post_hoc_diagnostic": True,
            },
        },
        "variants": {
            "current_baseline": {
                "folds": [
                    {
                        "fold": 1,
                        "status": "OK",
                        "train_end": "2026-01-10",
                        "validation_start": "2026-01-25",
                    }
                ]
            },
            "drop_planned_features": {},
            "planned_features_only": {},
        },
    }


def run_self_test() -> tuple[str, list[dict[str, Any]]]:
    cases: list[tuple[str, dict[str, Any], bool]] = []
    good = valid_fixture()
    cases.append(("valid_fixture_passes", good, True))

    diagnostic_gate = json.loads(json.dumps(good))
    diagnostic_gate["contract"]["no_hindsight_policy"]["promotion_gate_variant"] = "drop_planned_features"
    cases.append(("diagnostic_variant_as_gate_fails", diagnostic_gate, False))

    same_run_filters = json.loads(json.dumps(good))
    same_run_filters["contract"]["no_hindsight_policy"]["diagnostic_failures_cannot_define_same_run_filters"] = False
    cases.append(("same_run_filters_allowed_fails", same_run_filters, False))

    leaked_fold = json.loads(json.dumps(good))
    leaked_fold["variants"]["current_baseline"]["folds"][0]["train_end"] = "2026-01-25"
    cases.append(("train_validation_overlap_fails", leaked_fold, False))

    promotion_allowed = json.loads(json.dumps(good))
    promotion_allowed["contract"]["production_promotion_allowed"] = True
    cases.append(("production_promotion_allowed_fails", promotion_allowed, False))

    risk_adjusted_score_changed = json.loads(json.dumps(good))
    risk_adjusted_score_changed["contract"]["does_not_change_risk_adjusted_score"] = False
    cases.append(("risk_adjusted_score_change_fails", risk_adjusted_score_changed, False))

    production_ranking_changed = json.loads(json.dumps(good))
    production_ranking_changed["contract"]["does_not_change_production_ranking"] = False
    cases.append(("production_ranking_change_fails", production_ranking_changed, False))

    missing_decision = json.loads(json.dumps(good))
    missing_decision.pop("decision")
    cases.append(("missing_decision_fails", missing_decision, False))

    bad_layer = json.loads(json.dumps(good))
    bad_layer["layer"] = "strategy"
    cases.append(("bad_layer_fails", bad_layer, False))

    post_hoc = json.loads(json.dumps(good))
    post_hoc["pre_registered"] = False
    cases.append(("not_pre_registered_fails", post_hoc, False))

    results = []
    for name, payload, should_pass in cases:
        failures = verify(payload)
        passed = len(failures) == 0
        results.append(
            {
                "name": name,
                "expected_pass": should_pass,
                "actual_pass": passed,
                "ok": passed is should_pass,
                "failure_count": len(failures),
                "failures": failures[:5],
            }
        )
    status = "OK" if all(row["ok"] for row in results) else "FAILED"
    return status, results


def main() -> int:
    args = parse_args()
    if args.self_test:
        status, results = run_self_test()
        print(json.dumps({"status": status, "cases": results}, ensure_ascii=False))
        return 0 if status == "OK" else 1
    path = resolve_path(args.artifact)
    payload = json.loads(path.read_text(encoding="utf-8"))
    failures = verify(payload)
    if failures:
        print(json.dumps({"status": "FAILED", "artifact": str(path), "failures": failures}, ensure_ascii=False))
        return 1
    print(json.dumps({"status": "OK", "artifact": str(path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
