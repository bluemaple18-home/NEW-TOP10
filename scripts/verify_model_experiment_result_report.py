#!/usr/bin/env python3
"""驗證 MODEL-EXP-01 result report。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_EXPERIMENTS_DIR = PROJECT_ROOT / "artifacts" / "model_experiments"
CONTRACT_TRUE_FLAGS = {
    "research_only",
    "reads_model_experiment_artifacts_only",
    "does_not_train_model",
    "does_not_write_models_latest_lgbm",
    "does_not_change_risk_adjusted_score",
    "does_not_change_production_ranking",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify MODEL-EXP-01 result report")
    parser.add_argument("--artifact", default=None)
    parser.add_argument("--output", default="artifacts/model_experiments/model_exp_result_report_verification_latest.json")
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


def latest_report() -> Path | None:
    matches = sorted(MODEL_EXPERIMENTS_DIR.glob("model_exp_result_report_????-??-??.json"))
    return matches[-1] if matches else None


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_report(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    checks: list[dict[str, Any]] = []
    contract = payload.get("contract", {})
    summary = payload.get("summary", {})
    decisions = {item.get("experiment_id"): item for item in payload.get("decisions", [])}
    checks.extend(
        [
            {"name": "schema", "ok": payload.get("schema_version") == "model-experiment-result-report.v1", "value": payload.get("schema_version")},
            {
                "name": "status",
                "ok": payload.get("status") in {"OK", "WARN"},
                "value": payload.get("status"),
            },
            {
                "name": "production_promotion_blocked",
                "ok": contract.get("production_promotion_allowed") is False,
                "value": contract.get("production_promotion_allowed"),
            },
            {
                "name": "portfolio_has_decision",
                "ok": "model_exp_portfolio_risk_overlay_only" in decisions,
                "value": sorted(decisions),
            },
            {
                "name": "regime_has_decision",
                "ok": "model_exp_regime_feature_group_ablation" in decisions,
                "value": sorted(decisions),
            },
            {
                "name": "portfolio_status_safe",
                "ok": decisions.get("model_exp_portfolio_risk_overlay_only", {}).get("status")
                in {"PASS_TO_LONGER_REPLAY", "PASS_TO_PROMOTION_REVIEW_QUEUE", "MONITOR_ONLY"},
                "value": decisions.get("model_exp_portfolio_risk_overlay_only", {}).get("status"),
            },
            {
                "name": "regime_status_safe",
                "ok": decisions.get("model_exp_regime_feature_group_ablation", {}).get("status")
                in {"PASS_TO_OFFLINE_ABLATION_WITH_CAUTION", "PASS_TO_MODEL_EXP_02", "MONITOR_ONLY_WEAK_MODEL_UPLIFT", "MONITOR_ONLY"},
                "value": decisions.get("model_exp_regime_feature_group_ablation", {}).get("status"),
            },
            {
                "name": "candidate_persistence_has_safe_status",
                "ok": decisions.get("model_exp_candidate_persistence_only", {}).get("status")
                in {"BLOCKED_MISSING_MATERIALIZER", "READY_TO_OFFLINE_ABLATION", "MONITOR_ONLY_NOT_STABLE", "PASS_TO_OFFLINE_ABLATION_WITH_CAUTION"},
                "value": decisions.get("model_exp_candidate_persistence_only", {}).get("status"),
            },
            {
                "name": "combined_waits",
                "ok": decisions.get("model_exp_combined_conservative", {}).get("status") == "WAIT_FOR_INDIVIDUAL_PASS",
                "value": decisions.get("model_exp_combined_conservative", {}).get("status"),
            },
            {
                "name": "summary_has_next_step",
                "ok": bool(summary.get("pass_to_next") or summary.get("blocked") or summary.get("waiting")),
                "value": summary,
            },
        ]
    )
    for flag in CONTRACT_TRUE_FLAGS:
        checks.append({"name": f"contract.{flag}", "ok": contract.get(flag) is True, "value": contract.get(flag)})

    for exp_id, item in decisions.items():
        checks.extend(
            [
                {"name": f"{exp_id}.has_ledger_id", "ok": bool(item.get("ledger_id")), "value": item.get("ledger_id")},
                {"name": f"{exp_id}.has_hypothesis", "ok": bool(item.get("hypothesis")), "value": item.get("hypothesis")},
                {"name": f"{exp_id}.has_baseline", "ok": bool(item.get("baseline")), "value": item.get("baseline")},
                {"name": f"{exp_id}.has_decision_policy", "ok": bool(item.get("decision_policy")), "value": item.get("decision_policy")},
                {"name": f"{exp_id}.has_actual_metrics", "ok": isinstance(item.get("actual_metrics"), dict), "value": item.get("actual_metrics")},
                {
                    "name": f"{exp_id}.verdict_known",
                    "ok": item.get("verdict") in {"passed", "failed", "partial", "pending", "expired", "stale"},
                    "value": item.get("verdict"),
                },
                {"name": f"{exp_id}.has_next_action", "ok": bool(item.get("next_action")), "value": item.get("next_action")},
                {"name": f"{exp_id}.promotion_allowed_false", "ok": item.get("promotion_allowed") is False, "value": item.get("promotion_allowed")},
            ]
        )
    failed = [item for item in checks if not item["ok"]]
    return {
        "schema_version": "model-experiment-result-report-verification.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
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
    artifact = resolve_path(args.artifact) or latest_report()
    if artifact is None:
        raise FileNotFoundError("找不到 artifacts/model_experiments/model_exp_result_report_YYYY-MM-DD.json")
    report = build_report(artifact)
    output = resolve_path(args.output)
    if output is None:
        raise RuntimeError("output path resolution failed")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"status": report["status"], "output": repo_path(output), **report["summary"]}, ensure_ascii=False))
    return 0 if report["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
