#!/usr/bin/env python3
"""建立 shadow feature promotion gate。

此 gate 只讀既有 evidence artifacts，產出模型側可開始 shadow 測試的清單。
它不訓練模型、不重跑 ranking、不修改 production score。
"""

from __future__ import annotations

import argparse
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
SCHEMA_VERSION = "feature-experiment-gate.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build shadow feature promotion gate artifact")
    parser.add_argument("--artifacts-dir", default="artifacts")
    parser.add_argument("--output", default=None)
    parser.add_argument("--min-trades", type=int, default=20)
    parser.add_argument("--min-positive-scenarios", type=int, default=1)
    return parser.parse_args()


def resolve_path(value: str | None, base: Path = PROJECT_ROOT) -> Path | None:
    if value is None:
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else base / path


def repo_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def latest_existing(base: Path, pattern: str) -> Path | None:
    files = sorted(base.glob(pattern))
    return files[-1] if files else None


def latest_dated_artifact(base: Path, prefix: str) -> Path | None:
    pattern = re.compile(rf"{re.escape(prefix)}_\d{{4}}-\d{{2}}-\d{{2}}\.json$")
    files = sorted([path for path in base.glob(f"{prefix}_*.json") if pattern.match(path.name)])
    return files[-1] if files else None


def load_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def ok_verification(payload: dict[str, Any]) -> bool:
    return payload.get("status") == "OK" and all(bool(value) for value in payload.get("checks", {}).values())


def number_value(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def candidate_status(ready: bool, blocked_reason: str | None = None) -> str:
    return "READY_FOR_SHADOW" if ready else "BLOCKED"


def promotion_status() -> str:
    return "BLOCKED_PROMOTION_PENDING"


def allowed_if_ready(ready: bool, uses: list[str]) -> list[str]:
    return uses if ready else []


def evidence_item(path: Path | None, payload: dict[str, Any], status: str | None = None) -> dict[str, Any]:
    return {
        "path": repo_path(path) if path and path.exists() else None,
        "schema_version": payload.get("schema_version"),
        "status": status if status is not None else payload.get("status"),
        "exists": bool(path and path.exists()),
    }


def build_candidate_persistence_candidate(artifacts_dir: Path, min_trades: int) -> dict[str, Any]:
    study_path = latest_existing(artifacts_dir / "backtest", "persistence_study_*.json")
    verify_path = artifacts_dir / "candidate_persistence_backtest_verification_latest.json"
    study = load_json(study_path)
    verification = load_json(verify_path)
    summary = study.get("summary", {})
    trade_count = int(summary.get("trade_count") or 0)
    contract = study.get("contract", {})
    ready = (
        study.get("schema_version") == "candidate-persistence-backtest.v1"
        and contract.get("model_feature") is False
        and contract.get("uses_future_rankings") is False
        and trade_count >= min_trades
        and ok_verification(verification)
    )
    blockers = []
    if trade_count < min_trades:
        blockers.append(f"trade_count={trade_count} < min_trades={min_trades}")
    if not ok_verification(verification):
        blockers.append("candidate persistence backtest verification is not OK")
    if contract.get("uses_future_rankings") is not False:
        blockers.append("future ranking guard missing")
    return {
        "id": "candidate_persistence",
        "label": "入榜天數 / 連續入榜 / rank_delta",
        "shadow_status": candidate_status(ready),
        "production_promotion_status": promotion_status(),
        "allowed_shadow_uses": allowed_if_ready(
            ready,
            [
                "shadow feature columns: consecutive_ranked_days, streak_bucket, rank_delta_direction",
                "decision overlay analysis by horizon and streak bucket",
            ],
        ),
        "blocked_production_uses": [
            "do not add direct ranking score bonus",
            "do not train production model with streak columns until promotion criteria pass",
        ],
        "evidence": {
            "study": evidence_item(study_path, study),
            "verification": evidence_item(verify_path, verification),
            "trade_count": trade_count,
        },
        "blockers": blockers,
        "promotion_requirements": promotion_requirements("candidate_persistence"),
    }


def build_market_context_candidate(artifacts_dir: Path) -> dict[str, Any]:
    context_path = latest_dated_artifact(artifacts_dir, "market_context")
    verify_path = artifacts_dir / "market_context_fetcher_verification_latest.json"
    decision_path = latest_dated_artifact(artifacts_dir, "decision_quality")
    context = load_json(context_path)
    verification = load_json(verify_path)
    decision_quality = load_json(decision_path)
    source_status = context.get("source_status", {})
    ready = (
        context.get("schema_version") == "market-context.tw.v1"
        and ok_verification(verification)
        and any(status.get("status") in {"ok", "warn"} for status in source_status.values() if isinstance(status, dict))
    )
    blockers = []
    if not ok_verification(verification):
        blockers.append("market context fetcher verification is not OK")
    if context.get("schema_version") != "market-context.tw.v1":
        blockers.append("missing market_context artifact")
    return {
        "id": "market_context",
        "label": "台灣市場背景 / breadth / 三大法人 / 期權 context",
        "shadow_status": candidate_status(ready),
        "production_promotion_status": promotion_status(),
        "allowed_shadow_uses": allowed_if_ready(
            ready,
            [
                "regime filter shadow test",
                "risk overlay comparison against daily Top10 outcomes",
                "feature ablation as model candidate only after as-of checks",
            ],
        ),
        "blocked_production_uses": [
            "do not change RankingPolicy risk_adjusted_score",
            "do not treat failed external source as bullish or bearish signal",
        ],
        "evidence": {
            "latest_market_context": evidence_item(context_path, context),
            "verification": evidence_item(verify_path, verification),
            "decision_quality": evidence_item(decision_path, decision_quality),
            "source_status": source_status,
        },
        "blockers": blockers,
        "promotion_requirements": promotion_requirements("market_context"),
    }


def build_portfolio_risk_candidate(artifacts_dir: Path, min_positive_scenarios: int) -> dict[str, Any]:
    matrix_path = latest_existing(artifacts_dir / "backtest", "strategy_matrix_*.json")
    decision_path = latest_dated_artifact(artifacts_dir, "decision_quality")
    portfolio_verify_path = artifacts_dir / "portfolio_replay_verification_latest.json"
    matrix = load_json(matrix_path)
    decision_quality = load_json(decision_path)
    portfolio_verify = load_json(portfolio_verify_path)
    matrix_summary = matrix.get("summary", {})
    positive_count = int(matrix_summary.get("positive_return_count") or 0)
    risk_available = bool((decision_quality.get("summary") or {}).get("portfolio_replay_risk_available"))
    ready = (
        matrix.get("schema_version") == "backtest-strategy-matrix.v1"
        and positive_count >= min_positive_scenarios
        and ok_verification(portfolio_verify)
    )
    blockers = []
    if positive_count < min_positive_scenarios:
        blockers.append(f"positive_return_count={positive_count} < min_positive_scenarios={min_positive_scenarios}")
    if not ok_verification(portfolio_verify):
        blockers.append("portfolio replay verification is not OK")
    return {
        "id": "portfolio_risk_overlay",
        "label": "portfolio replay 風險 / exposure / event exit overlay",
        "shadow_status": candidate_status(ready),
        "production_promotion_status": promotion_status(),
        "allowed_shadow_uses": allowed_if_ready(
            ready,
            [
                "risk gate simulation outside production ranking",
                "portfolio overlay comparison across horizon / stop / take-profit scenarios",
            ],
        ),
        "blocked_production_uses": [
            "do not suppress production ranking rows directly",
            "do not convert replay risk flags into model labels without a sealed experiment",
        ],
        "evidence": {
            "strategy_matrix": evidence_item(matrix_path, matrix),
            "portfolio_verification": evidence_item(portfolio_verify_path, portfolio_verify),
            "decision_quality": evidence_item(decision_path, decision_quality),
            "decision_quality_portfolio_risk_available": risk_available,
            "positive_return_count": positive_count,
        },
        "blockers": blockers,
        "promotion_requirements": promotion_requirements("portfolio_risk_overlay"),
    }


def blocked_data_candidate(candidate_id: str, label: str, required_artifact: str) -> dict[str, Any]:
    return {
        "id": candidate_id,
        "label": label,
        "shadow_status": "BLOCKED",
        "production_promotion_status": promotion_status(),
        "allowed_shadow_uses": [],
        "blocked_production_uses": ["do not add to production model before data contract and as-of validation"],
        "evidence": {"required_artifact": required_artifact},
        "blockers": [f"missing required data contract artifact: {required_artifact}"],
        "promotion_requirements": promotion_requirements(candidate_id),
    }


def build_chip_flow_candidate(artifacts_dir: Path) -> dict[str, Any]:
    handoff_path = PROJECT_ROOT / "docs" / "tasks" / "2026-06-08_CHIP-FLOW_warning_research_handoff.md"
    contract_path = latest_dated_artifact(artifacts_dir, "chip_data_contract")
    contract = load_json(contract_path)
    coverage_path = latest_dated_artifact(artifacts_dir, "chip_flow_runtime_coverage")
    coverage = load_json(coverage_path)
    warning_path = latest_dated_artifact(artifacts_dir / "model_experiments", "chip_warning_shadow_report")
    warning = load_json(warning_path)
    aggregate_path = latest_dated_artifact(artifacts_dir / "model_experiments", "chip_warning_replay_aggregate")
    aggregate = load_json(aggregate_path)
    composite_path = latest_dated_artifact(artifacts_dir / "model_experiments", "chip_composite_warning_report")
    composite = load_json(composite_path)
    blockers: list[str] = []
    if contract.get("schema_version") != "chip-data-contract.v1" or contract.get("status") != "OK":
        blockers.append("missing required data contract artifact: artifacts/chip_data_contract_YYYY-MM-DD.json")
    if coverage_path is None:
        blockers.append("missing chip-flow runtime coverage audit")
    elif coverage.get("status") != "OK":
        blockers.append(f"chip-flow runtime coverage audit status={coverage.get('status') or 'missing'}")
    if warning_path is None:
        blockers.append("missing chip warning-only shadow replay")
    elif warning.get("status") != "OK":
        blockers.append(f"chip warning-only shadow replay status={warning.get('status') or 'missing'}")
    elif warning.get("decision", {}).get("status") == "NOT_STABLE_ENOUGH_FOR_WARNING_CHANNEL":
        blockers.append("chip warning-only replay is not stable enough for warning channel")
    if aggregate_path is not None and aggregate.get("decision", {}).get("status") == "NOT_STABLE_ENOUGH_FOR_WARNING_CHANNEL":
        blockers.append("chip aggregate replay is not stable enough for warning channel")
    if composite_path is not None and composite.get("decision", {}).get("status") == "NOT_STABLE_ENOUGH_FOR_WARNING_CHANNEL":
        blockers.append("chip composite warning replay is not stable enough for warning channel")
    if handoff_path.exists():
        blockers.append("chip-flow handoff decision blocks production warning/ranking promotion")
    return {
        "id": "chip_flow",
        "label": "籌碼 / 三大法人 / 融資融券 feature candidates",
        "shadow_status": "BLOCKED",
        "production_promotion_status": promotion_status(),
        "allowed_shadow_uses": [],
        "blocked_production_uses": [
            "do not add to production model before data contract, coverage audit, replay, and as-of validation",
            "do not promote as production warning channel from current chip-flow evidence",
            "do not use foreign/trust/margin flow as standalone market or exit signal",
        ],
        "evidence": {
            "handoff": {
                "path": repo_path(handoff_path),
                "status": "OK" if handoff_path.exists() else "MISSING",
            },
            "data_contract": evidence_item(contract_path, contract),
            "runtime_coverage": evidence_item(coverage_path, coverage),
            "warning_shadow_replay": evidence_item(warning_path, warning),
            "warning_replay_aggregate": evidence_item(aggregate_path, aggregate),
            "composite_warning_replay": evidence_item(composite_path, composite),
        },
        "blockers": blockers,
        "promotion_requirements": promotion_requirements("chip_flow"),
    }


def build_industry_candidate(artifacts_dir: Path) -> dict[str, Any]:
    industry_path = latest_existing(artifacts_dir, "industry_rotation_replay_*.json")
    payload = load_json(industry_path)
    blockers = ["industry rotation remains monitor_only; production promotion criteria not defined"]
    if not industry_path:
        blockers.append("missing industry rotation replay artifact")
    return {
        "id": "industry_rotation",
        "label": "產業輪動 / group momentum overlay",
        "shadow_status": "BLOCKED",
        "production_promotion_status": promotion_status(),
        "allowed_shadow_uses": [],
        "blocked_production_uses": ["do not change production score before replay and concentration checks"],
        "evidence": {"industry_rotation_replay": evidence_item(industry_path, payload)},
        "blockers": blockers,
        "promotion_requirements": promotion_requirements("industry_rotation"),
    }


def build_regime_feature_group_candidate(artifacts_dir: Path) -> dict[str, Any]:
    ablation_path = latest_dated_artifact(artifacts_dir, "feature_group_ablation_by_regime")
    verify_path = artifacts_dir / "feature_group_ablation_by_regime_verification_latest.json"
    payload = load_json(ablation_path)
    verification = load_json(verify_path)
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    candidate_rows = int(summary.get("candidate_metric_rows") or 0)
    ready = (
        payload.get("schema_version") == "feature-group-ablation-by-regime.v1"
        and contract.get("research_only") is True
        and contract.get("trains_model") is False
        and contract.get("changes_ranking") is False
        and candidate_rows > 0
        and ok_verification(verification)
    )
    blockers = []
    if payload.get("schema_version") != "feature-group-ablation-by-regime.v1":
        blockers.append("missing feature_group_ablation_by_regime artifact")
    if not ok_verification(verification):
        blockers.append("feature group ablation verification is not OK")
    if candidate_rows <= 0:
        blockers.append("candidate_metric_rows is empty")
    return {
        "id": "regime_feature_group_ablation",
        "label": "依市場盤勢切分的 feature group 消融",
        "shadow_status": candidate_status(ready),
        "production_promotion_status": promotion_status(),
        "allowed_shadow_uses": allowed_if_ready(
            ready,
            [
                "prioritize feature groups by market regime before model training",
                "select shadow-only candidate columns for replay experiments",
                "identify noisy feature groups that need exclusion or regime-specific handling",
            ],
        ),
        "blocked_production_uses": [
            "do not directly convert IC results into RankingPolicy weights",
            "do not promote any feature group without replay and sealed OOS confirmation",
        ],
        "evidence": {
            "ablation": evidence_item(ablation_path, payload),
            "verification": evidence_item(verify_path, verification),
            "candidate_metric_rows": candidate_rows,
            "groups": summary.get("groups"),
            "regimes": summary.get("regimes"),
        },
        "blockers": blockers,
        "promotion_requirements": promotion_requirements("regime_feature_group_ablation"),
    }


def build_weekend_research_matrix_candidate(artifacts_dir: Path) -> dict[str, Any]:
    report_path = latest_existing(artifacts_dir / "backtest", "weekend_research_decision_report_*.json")
    payload = load_json(report_path)
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    promote = list(summary.get("promote_to_shadow") or [])
    blocked_data = list(summary.get("blocked_data") or [])
    ready = (
        payload.get("schema_version") == "weekend-research-decision-report.v1"
        and payload.get("status") == "OK"
        and contract.get("research_only") is True
        and contract.get("does_not_fetch_data") is True
        and contract.get("does_not_train_model") is True
        and contract.get("does_not_change_production_ranking") is True
        and bool(promote)
    )
    blockers = []
    if payload.get("schema_version") != "weekend-research-decision-report.v1":
        blockers.append("missing weekend research decision report")
    if payload.get("status") != "OK":
        blockers.append("weekend research decision report is not OK")
    if not promote:
        blockers.append("no promote_to_shadow variants")
    if contract.get("does_not_fetch_data") is not True:
        blockers.append("does_not_fetch_data contract missing")
    if contract.get("does_not_change_production_ranking") is not True:
        blockers.append("production ranking immutability contract missing")
    return {
        "id": "weekend_research_matrix",
        "label": "週末大量測試矩陣 / replay stability decision",
        "shadow_status": candidate_status(ready),
        "production_promotion_status": promotion_status(),
        "allowed_shadow_uses": allowed_if_ready(
            ready,
            [
                "shadow-run promoted variants only: " + ",".join(promote),
                "separate 5d candidate track from 10d risk track",
                "use blocked_data list as data backlog, not as model features",
            ],
        ),
        "blocked_production_uses": [
            "do not promote matrix result directly to production ranking",
            "do not use blocked data dimensions before coverage/as-of gates pass",
        ],
        "evidence": {
            "decision_report": evidence_item(report_path, payload),
            "promote_to_shadow": promote,
            "blocked_data": blocked_data,
        },
        "blockers": blockers,
        "promotion_requirements": promotion_requirements("weekend_research_matrix"),
    }


def promotion_requirements(candidate_id: str) -> list[str]:
    return [
        f"{candidate_id} shadow experiment artifact with explicit as-of policy",
        "production replay improvement versus baseline on matured ranking dates",
        "sealed OOS report status OK for any trained model candidate",
        "walk-forward or time-split result showing non-degradation",
        "portfolio replay does not increase max drawdown or concentration beyond configured caps",
        "code review confirms no production ranking score path is changed before approval",
    ]


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    artifacts_dir = resolve_path(args.artifacts_dir) or ARTIFACTS_DIR
    model_group_path = latest_existing(artifacts_dir, "model_group_acceptance_*.json")
    sealed_path = artifacts_dir / "sealed_oos_report_latest.json"
    decision_verify_path = artifacts_dir / "decision_quality_verification_latest.json"
    model_group = load_json(model_group_path)
    sealed = load_json(sealed_path)
    decision_verify = load_json(decision_verify_path)
    candidates = [
        build_candidate_persistence_candidate(artifacts_dir, args.min_trades),
        build_market_context_candidate(artifacts_dir),
        build_portfolio_risk_candidate(artifacts_dir, args.min_positive_scenarios),
        blocked_data_candidate("fundamentals", "基本面 coverage / as-of feature candidates", "artifacts/fundamental_contract_YYYY-MM-DD.json"),
        build_chip_flow_candidate(artifacts_dir),
        build_industry_candidate(artifacts_dir),
        build_regime_feature_group_candidate(artifacts_dir),
        build_weekend_research_matrix_candidate(artifacts_dir),
    ]
    ready = [item for item in candidates if item["shadow_status"] == "READY_FOR_SHADOW"]
    blocked = [item for item in candidates if item["shadow_status"] != "READY_FOR_SHADOW"]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "READY_FOR_SHADOW_TESTS" if ready else "BLOCKED",
        "contract": {
            "purpose": "authorize shadow feature experiments without changing production ranking score",
            "production_score_change_allowed": False,
            "model_training_allowed": "shadow_only",
            "production_promotion_allowed": False,
            "source_policy": "read_existing_evidence_artifacts_only",
        },
        "global_evidence": {
            "model_group_acceptance": evidence_item(model_group_path, model_group),
            "sealed_oos_latest": evidence_item(sealed_path, sealed),
            "decision_quality_verification": evidence_item(decision_verify_path, decision_verify),
        },
        "summary": {
            "candidate_count": len(candidates),
            "ready_for_shadow_count": len(ready),
            "blocked_count": len(blocked),
            "ready_for_shadow": [item["id"] for item in ready],
            "blocked": [item["id"] for item in blocked],
            "production_promotion_allowed": False,
        },
        "handoff_for_model_team": {
            "can_start_now": [item["id"] for item in ready],
            "must_not_do": [
                "do not edit RankingPolicy weights or risk_adjusted_score",
                "do not add candidate columns to production LightGBM training without a promotion artifact",
                "do not use future ranking, future price, or external-source failure as signal",
                "do not promote a shadow experiment without sealed OOS, replay, and review evidence",
            ],
            "next_expected_artifacts": [
                "artifacts/shadow_feature_experiment_<candidate>_YYYY-MM-DD.json",
                "artifacts/shadow_feature_experiment_<candidate>_YYYY-MM-DD.md",
            ],
        },
        "candidates": candidates,
    }


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    run_date = datetime.now().strftime("%Y-%m-%d")
    output_path = resolve_path(args.output) if args.output else ARTIFACTS_DIR / f"feature_experiment_gate_{run_date}.json"
    if output_path is None:
        raise RuntimeError("output path resolution failed")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output_path), **payload["summary"]}, ensure_ascii=False))
    return 0 if payload["status"] in {"READY_FOR_SHADOW_TESTS", "BLOCKED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
