#!/usr/bin/env python3
"""驗證 shadow feature promotion gate 不會開放 production score 修改。"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_PATH = PROJECT_ROOT / "artifacts" / "feature_experiment_gate_verification_latest.json"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def build_fixture(root: Path) -> dict[str, Path]:
    artifacts = root / "artifacts"
    backtest = artifacts / "backtest"
    backtest.mkdir(parents=True)
    write_json(
        backtest / "persistence_study_2026-01-05.json",
        {
            "schema_version": "candidate-persistence-backtest.v1",
            "contract": {"model_feature": False, "uses_future_rankings": False},
            "summary": {"trade_count": 30, "by_horizon_and_streak": {"5D::2-3": {"avg_net_return": 0.03}}},
        },
    )
    write_json(
        artifacts / "candidate_persistence_backtest_verification_latest.json",
        {"schema_version": "candidate-persistence-backtest-verification.v1", "status": "OK", "checks": {"no_future": True}},
    )
    write_json(
        artifacts / "market_context_2026-01-05.json",
        {
            "schema_version": "market-context.tw.v1",
            "trade_date": "2026-01-05",
            "source_status": {"twse": {"status": "ok"}, "tpex": {"status": "warn"}},
        },
    )
    write_json(
        artifacts / "market_context_fetcher_verification_latest.json",
        {"status": "OK", "checks": {"schema": True, "partial_failure": True}},
    )
    write_json(
        backtest / "strategy_matrix_2026-01-05.json",
        {
            "schema_version": "backtest-strategy-matrix.v1",
            "summary": {"positive_return_count": 2, "scenario_count": 4},
        },
    )
    write_json(
        artifacts / "portfolio_replay_verification_latest.json",
        {"status": "OK", "checks": {"contract": True}},
    )
    write_json(
        artifacts / "decision_quality_2026-01-05.json",
        {"schema_version": "decision-quality.v1", "summary": {"portfolio_replay_risk_available": True}},
    )
    write_json(
        artifacts / "decision_quality_verification_latest.json",
        {"status": "OK", "checks": {"read_only_contract": True}},
    )
    write_json(
        artifacts / "sealed_oos_report_latest.json",
        {"schema_version": "sealed-oos-report.v1", "status": "OK", "failures": []},
    )
    write_json(
        artifacts / "model_group_acceptance_2026-01-05.json",
        {"schema_version": "model-group-acceptance.v1", "status": "OK"},
    )
    write_json(
        artifacts / "industry_rotation_replay_2026-01-05.json",
        {
            "schema_version": "industry-rotation-replay.v1",
            "contract": {"ranking_score_change": False},
            "summary": {"sample_count": 10},
        },
    )
    write_json(
        artifacts / "feature_group_ablation_by_regime_2026-01-05.json",
        {
            "schema_version": "feature-group-ablation-by-regime.v1",
            "contract": {"research_only": True, "trains_model": False, "changes_ranking": False},
            "summary": {
                "candidate_metric_rows": 5,
                "groups": ["price_volume", "industry_momentum"],
                "regimes": ["NARROW_LEADER"],
            },
        },
    )
    write_json(
        artifacts / "feature_group_ablation_by_regime_verification_latest.json",
        {"status": "OK", "checks": {"strict_gate": True}},
    )
    write_json(
        backtest / "weekend_research_decision_report_2026-01-05.json",
        {
            "schema_version": "weekend-research-decision-report.v1",
            "contract": {
                "research_only": True,
                "does_not_train_model": True,
                "does_not_change_production_ranking": True,
            },
            "summary": {
                "promote_to_shadow": ["overlay", "guard_balanced"],
                "monitor_only": ["guard_strict"],
                "blocked_data": ["monthly_revenue"],
            },
        },
    )
    return {"artifacts": artifacts, "output": root / "feature_experiment_gate.json"}


def run_gate(paths: dict[str, Path], output_name: str = "feature_experiment_gate.json") -> dict[str, Any]:
    output = paths["output"].with_name(output_name)
    completed = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "build_feature_experiment_gate.py"),
            "--artifacts-dir",
            str(paths["artifacts"]),
            "--output",
            str(output),
        ],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        print(completed.stdout)
        print(completed.stderr, file=sys.stderr)
        raise RuntimeError(f"feature experiment gate failed: {completed.returncode}")
    return json.loads(output.read_text(encoding="utf-8"))


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="top10-feature-experiment-gate-") as tmp:
        paths = build_fixture(Path(tmp))
        payload = run_gate(paths)
        by_id = {item["id"]: item for item in payload["candidates"]}
        output_text = paths["output"].read_text(encoding="utf-8")
        negative_cases = negative_verification_cases(paths)
        checks = {
            "schema_ok": payload["schema_version"] == "feature-experiment-gate.v1",
            "status_ready": payload["status"] == "READY_FOR_SHADOW_TESTS",
            "production_score_blocked": payload["contract"]["production_score_change_allowed"] is False,
            "promotion_blocked": payload["contract"]["production_promotion_allowed"] is False,
            "candidate_persistence_ready": by_id["candidate_persistence"]["shadow_status"] == "READY_FOR_SHADOW",
            "market_context_ready": by_id["market_context"]["shadow_status"] == "READY_FOR_SHADOW",
            "portfolio_overlay_ready": by_id["portfolio_risk_overlay"]["shadow_status"] == "READY_FOR_SHADOW",
            "regime_feature_group_ablation_ready": by_id["regime_feature_group_ablation"]["shadow_status"] == "READY_FOR_SHADOW",
            "weekend_research_matrix_ready": by_id["weekend_research_matrix"]["shadow_status"] == "READY_FOR_SHADOW",
            "fundamentals_blocked": by_id["fundamentals"]["shadow_status"] == "BLOCKED",
            "chip_blocked": by_id["chip_flow"]["shadow_status"] == "BLOCKED",
            "industry_rotation_blocked_even_with_thin_replay": by_id["industry_rotation"]["shadow_status"] == "BLOCKED",
            "model_team_can_start": set(payload["handoff_for_model_team"]["can_start_now"])
            == {
                "candidate_persistence",
                "market_context",
                "portfolio_risk_overlay",
                "regime_feature_group_ablation",
                "weekend_research_matrix",
            },
            "must_not_change_ranking": any(
                "RankingPolicy" in item or "risk_adjusted_score" in item for item in payload["handoff_for_model_team"]["must_not_do"]
            ),
            **negative_cases,
            "no_nan_json_literal": "NaN" not in output_text,
        }
        status = "OK" if all(checks.values()) else "FAILED"
        ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
        ARTIFACT_PATH.write_text(
            json.dumps(
                {
                    "schema_version": "feature-experiment-gate-verification.v1",
                    "status": status,
                    "checks": checks,
                    "note": "uses TemporaryDirectory synthetic evidence artifacts; no model training or ranking execution",
                },
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            ),
            encoding="utf-8",
        )
        if status == "OK":
            print(f"FEATURE_EXPERIMENT_GATE_OK output={ARTIFACT_PATH}")
            return 0
        print(f"FEATURE_EXPERIMENT_GATE_FAILED output={ARTIFACT_PATH}", file=sys.stderr)
        return 1


def negative_verification_cases(paths: dict[str, Path]) -> dict[str, bool]:
    artifacts = paths["artifacts"]
    cases: dict[str, bool] = {}
    mutations = [
        (
            "candidate_persistence_blocks_when_verification_failed",
            artifacts / "candidate_persistence_backtest_verification_latest.json",
            {"schema_version": "candidate-persistence-backtest-verification.v1", "status": "FAILED", "checks": {"no_future": False}},
            "candidate_persistence",
        ),
        (
            "market_context_blocks_when_verification_failed",
            artifacts / "market_context_fetcher_verification_latest.json",
            {"status": "FAILED", "checks": {"schema": False}},
            "market_context",
        ),
        (
            "portfolio_overlay_blocks_when_verification_failed",
            artifacts / "portfolio_replay_verification_latest.json",
            {"status": "FAILED", "checks": {"contract": False}},
            "portfolio_risk_overlay",
        ),
        (
            "regime_feature_group_ablation_blocks_when_verification_failed",
            artifacts / "feature_group_ablation_by_regime_verification_latest.json",
            {"status": "FAILED", "checks": {"strict_gate": False}},
            "regime_feature_group_ablation",
        ),
    ]
    for index, (case_name, path, failed_payload, candidate_id) in enumerate(mutations, start=1):
        original = json.loads(path.read_text(encoding="utf-8"))
        write_json(path, failed_payload)
        try:
            payload = run_gate(paths, output_name=f"feature_experiment_gate_negative_{index}.json")
            by_id = {item["id"]: item for item in payload["candidates"]}
            cases[case_name] = by_id[candidate_id]["shadow_status"] == "BLOCKED"
        finally:
            write_json(path, original)
    return cases


if __name__ == "__main__":
    raise SystemExit(main())
