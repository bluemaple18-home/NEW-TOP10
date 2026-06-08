#!/usr/bin/env python3
"""驗證正式自動化訓練前的準備狀態。

這支腳本是「開自動訓練前」的總閘門：只跑/讀既有安全檢查與研究
artifact，可訓練暫存研究模型，但不訓練/保存正式模型、不覆蓋
`models/latest_lgbm.pkl`、不改 production ranking。它的輸出可用來判斷
目前是已可準備自動化，還是仍有 blocker。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
MODEL_EXPERIMENTS_DIR = ARTIFACTS_DIR / "model_experiments"
SCHEMA_VERSION = "training-automation-readiness.v1"

CORE_CHECKS: tuple[tuple[str, list[str]], ...] = (
    ("data.pipeline.validate", ["-m", "app.pipeline_cli", "validate", "--json"]),
    ("resource.guard", ["scripts/verify_resource_guard.py"]),
    ("production.write_guard", ["scripts/verify_production_write_guard.py"]),
    ("sealed_oos.capacity_preflight", ["scripts/verify_retrain_sealed_oos_capacity_preflight.py"]),
    ("retrain.rollback", ["scripts/verify_retrain_rollback.py"]),
    ("model.research_governance.self_test", ["scripts/verify_half_year_walkforward_no_hindsight.py", "--self-test"]),
    ("model.research_flow.verify", ["scripts/verify_model_research_flow.py"]),
    ("model.group_acceptance", ["scripts/verify_model_group_acceptance.py"]),
)

HALF_YEAR_WALKFORWARD_MIN_AUC = 0.60
HALF_YEAR_WALKFORWARD_MIN_UPLIFT = 0.0
HALF_YEAR_WALKFORWARD_MIN_POSITIVE_FOLDS = 4
TRAINING_READY_MODEL_GROUP_STATES = {"READY", "READY_WITH_MONITORING_WARNINGS"}
BLOCKER_CATEGORIES = {
    "must_fix_before_training",
    "acceptable_monitoring_warning",
    "data_unavailable_with_explicit_degradation",
    "waiting_for_approved_experiment",
}
REVENUE_FEATURES = {"revenue_yoy", "revenue_mom"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify training automation readiness")
    parser.add_argument("--date", default=datetime.now().astimezone().date().isoformat())
    parser.add_argument("--output", default=None)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument(
        "--skip-model-research-flow",
        action="store_true",
        help="只讀既有 model research artifacts；預設會重跑 flow 產生當日 artifact",
    )
    parser.add_argument(
        "--skip-half-year-walkforward",
        action="store_true",
        help="只讀既有 half-year walk-forward artifact；預設會重跑近半年驗證",
    )
    parser.add_argument(
        "--skip-fixed-share-research-flow",
        action="store_true",
        help="只讀既有 fixed-share research artifacts；預設會重跑固定股數研究工廠",
    )
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


def load_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_config() -> dict[str, Any]:
    path = PROJECT_ROOT / "config" / "automation.yaml"
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def run_step(name: str, args: list[str], timeout_seconds: int) -> dict[str, Any]:
    command = [sys.executable, *args]
    env = os.environ.copy()
    env.setdefault("PYTHONPYCACHEPREFIX", "/private/tmp/top10_pycache")
    started_at = datetime.now(timezone.utc)
    try:
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        return {
            "name": name,
            "command": command,
            "status": "OK" if completed.returncode == 0 else "FAILED",
            "exit_code": completed.returncode,
            "started_at": started_at.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "stdout_tail": completed.stdout[-4000:],
            "stderr_tail": completed.stderr[-4000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "command": command,
            "status": "FAILED",
            "exit_code": None,
            "started_at": started_at.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "stdout_tail": (exc.stdout or "")[-4000:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-4000:] if isinstance(exc.stderr, str) else "",
            "error": f"timeout after {timeout_seconds}s",
        }


def research_flow_step(args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.skip_model_research_flow:
        return [
            {
                "name": "model.research_flow.run",
                "status": "SKIPPED",
                "exit_code": 0,
                "message": "skip-model-research-flow",
            }
        ]
    return [
        run_step(
            "model.research_flow.run",
            ["scripts/run_model_research_flow.py", "--date", args.date],
            args.timeout_seconds,
        )
    ]


def fixed_share_research_flow_step(args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.skip_fixed_share_research_flow:
        return [
            {
                "name": "trade_plan.fixed_share_research_flow",
                "status": "SKIPPED",
                "exit_code": 0,
                "message": "skip-fixed-share-research-flow",
            }
        ]
    output_path = MODEL_EXPERIMENTS_DIR / f"fixed_share_research_flow_{args.date}.json"
    return [
        run_step(
            "trade_plan.fixed_share_research_flow",
            [
                "scripts/run_fixed_share_research_flow.py",
                "--date",
                args.date,
                "--output",
                repo_path(output_path) or str(output_path),
            ],
            args.timeout_seconds,
        )
    ]


def build_result_report_steps(args: argparse.Namespace) -> list[dict[str, Any]]:
    report_path = MODEL_EXPERIMENTS_DIR / f"model_exp_result_report_{args.date}.json"
    return [
        run_step(
            "model.result_report.build",
            ["scripts/build_model_experiment_result_report.py", "--date", args.date],
            args.timeout_seconds,
        ),
        run_step(
            "model.result_report.verify",
            ["scripts/verify_model_experiment_result_report.py", "--artifact", repo_path(report_path) or str(report_path)],
            args.timeout_seconds,
        ),
    ]


def half_year_walkforward_path(date_text: str) -> Path:
    return MODEL_EXPERIMENTS_DIR / f"half_year_walkforward_validation_{date_text}.json"


def half_year_walkforward_step(args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.skip_half_year_walkforward:
        return [
            {
                "name": "model.half_year_walkforward",
                "status": "SKIPPED",
                "exit_code": 0,
                "message": "skip-half-year-walkforward",
            }
        ]
    output_path = half_year_walkforward_path(args.date)
    return [
        run_step(
            "model.half_year_walkforward",
            [
                "scripts/research_regime_feature_offline_ablation.py",
                "--date",
                args.date,
                "--folds",
                "6",
                "--embargo-trade-days",
                "10",
                "--top-n",
                "10",
                "--num-boost-round",
                "120",
                "--output",
                repo_path(output_path) or str(output_path),
            ],
            args.timeout_seconds,
        )
    ]


def half_year_no_hindsight_verify_step(args: argparse.Namespace) -> list[dict[str, Any]]:
    artifact_path = half_year_walkforward_path(args.date)
    return [
        run_step(
            "model.half_year_no_hindsight.verify",
            [
                "scripts/verify_half_year_walkforward_no_hindsight.py",
                "--artifact",
                repo_path(artifact_path) or str(artifact_path),
            ],
            args.timeout_seconds,
        )
    ]


def step_status_ok(step: dict[str, Any]) -> bool:
    return step.get("status") in {"OK", "SKIPPED"}


def classify_item(
    *,
    category: str,
    code: str,
    message: str,
    source: str,
    action: str,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if category not in BLOCKER_CATEGORIES:
        raise ValueError(f"unknown readiness category: {category}")
    return {
        "category": category,
        "code": code,
        "message": message,
        "source": source,
        "action": action,
        "evidence": evidence or {},
    }


def category_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {category: sum(1 for row in rows if row.get("category") == category) for category in sorted(BLOCKER_CATEGORIES)}


def health_checks_by_name(health: dict[str, Any]) -> dict[str, dict[str, Any]]:
    checks = health.get("checks") if isinstance(health.get("checks"), list) else []
    return {str(row.get("name")): row for row in checks if isinstance(row, dict)}


def health_warn_checks(health: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in health.get("checks", [])
        if isinstance(row, dict) and str(row.get("status", "")).upper() in {"WARN", "CRITICAL", "FAILED"}
    ]


def check_not_ok(row: dict[str, Any] | None) -> bool:
    return bool(row) and str(row.get("status", "")).upper() != "OK"


def technical_only_lane_path(run_date: str) -> Path:
    return MODEL_EXPERIMENTS_DIR / f"technical_only_training_lane_{run_date}.json"


def high_choppy_context_overlay_path(run_date: str) -> Path:
    return MODEL_EXPERIMENTS_DIR / f"high_choppy_context_overlay_{run_date}.json"


def fixed_share_research_flow_path(run_date: str) -> Path:
    return MODEL_EXPERIMENTS_DIR / f"fixed_share_research_flow_{run_date}.json"


def fixed_share_research_factory_verification_path() -> Path:
    return MODEL_EXPERIMENTS_DIR / "fixed_share_research_factory_verification_latest.json"


def fixed_share_research_status(run_date: str) -> dict[str, Any]:
    flow_path = fixed_share_research_flow_path(run_date)
    verification_path = fixed_share_research_factory_verification_path()
    report_path = MODEL_EXPERIMENTS_DIR / f"fixed_share_research_factory_report_{run_date}.json"
    flow = load_json(flow_path)
    verification = load_json(verification_path)
    return {
        "flow_artifact": repo_path(flow_path),
        "verification_artifact": repo_path(verification_path),
        "report_artifact": repo_path(report_path),
        "flow_exists": flow_path.exists(),
        "verification_exists": verification_path.exists(),
        "report_exists": report_path.exists(),
        "flow_status": flow.get("status", "NOT_RUN"),
        "verification_status": verification.get("status", "NOT_RUN"),
        "verification_errors": len(verification.get("errors") or []),
        "contract": verification.get("contract", {}),
    }


def high_choppy_context_status(run_date: str) -> dict[str, Any]:
    """讀取 HIGH_CHOPPY 研究狀態；缺檔也不得阻塞主訓練 readiness。"""

    path = high_choppy_context_overlay_path(run_date)
    payload = load_json(path)
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    allowed = summary.get("usage_allowed") if isinstance(summary.get("usage_allowed"), dict) else {}
    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    return {
        "artifact": repo_path(path),
        "exists": path.exists(),
        "status": payload.get("status", "NOT_RUN"),
        "decision": payload.get("decision", "NOT_RUN"),
        "strict_dates": summary.get("strict_dates"),
        "rolling_context_dates": summary.get("rolling_context_dates"),
        "new_dates_quality": summary.get("new_dates_quality"),
        "soft_feature_allowed": (allowed.get("soft_feature") or {}).get("status", "BLOCKED"),
        "stratified_evaluation_allowed": (allowed.get("stratified_evaluation") or {}).get("status", "BLOCKED"),
        "ranking_overlay_allowed": (allowed.get("ranking_overlay") or {}).get("status", "BLOCKED"),
        "promotion_evidence_allowed": (allowed.get("promotion_evidence") or {}).get("status", "BLOCKED"),
        "blocks_main_training": bool(contract.get("blocks_main_training", False)),
    }


def technical_only_lane_ready(run_date: str) -> tuple[bool, dict[str, Any]]:
    path = technical_only_lane_path(run_date)
    payload = load_json(path)
    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    ready = (
        payload.get("schema_version") == "technical-only-training-lane.v1"
        and payload.get("status") == "RESEARCH_ONLY_ALLOWED"
        and payload.get("chosen_path") == "technical_only_lane"
        and contract.get("research_only_allowed") is True
        and contract.get("production_promotion_allowed") is False
        and contract.get("does_not_drop_model_features_silently") is True
        and contract.get("sealed_replay_acceptance_still_required") is True
    )
    return ready, {
        "artifact": repo_path(path),
        "exists": path.exists(),
        "status": payload.get("status"),
        "chosen_path": payload.get("chosen_path"),
        "production_promotion_allowed": contract.get("production_promotion_allowed"),
    }


def data_degradations(health: dict[str, Any], run_date: str) -> list[dict[str, Any]]:
    baseline = health.get("baseline") if isinstance(health.get("baseline"), dict) else {}
    skipped = [str(item) for item in baseline.get("skipped_empty_model_features") or []]
    revenue_skipped = [feature for feature in skipped if feature in REVENUE_FEATURES]
    if not revenue_skipped:
        return []
    lane_ready, lane_details = technical_only_lane_ready(run_date)
    if not lane_ready:
        return []
    return [
        {
            "id": "monthly_revenue_features_unavailable",
            "category": "data_unavailable_with_explicit_degradation",
            "features": revenue_skipped,
            "reason": "月營收欄位在 baseline_stats 中為空，PSI baseline 只能覆蓋 technical/event/pattern/fundamental 以外的可用欄位。",
            "degradation": "允許 research/readiness 使用 technical-only 可監控 baseline；禁止據此 production promotion 或啟用正式 auto retrain。",
            "required_before_training": "已產出 technical-only research artifact；正式 promotion 前仍需補齊 revenue_yoy/revenue_mom 來源，或在下一輪 sealed/replay/acceptance 明確接受此降級。",
            "evidence": {
                "model_feature_count": baseline.get("model_feature_count"),
                "monitored_model_feature_count": baseline.get("monitored_model_feature_count"),
                "coverage_ratio": baseline.get("coverage_ratio"),
                "technical_only_lane": lane_details,
            },
        }
    ]


def next_stage_experiment_entry_conditions(
    result_report: dict[str, Any],
    half_year_walkforward: dict[str, Any],
) -> list[dict[str, Any]]:
    decisions = result_report.get("decisions") if isinstance(result_report.get("decisions"), list) else []
    waiting = [row for row in decisions if isinstance(row, dict) and row.get("status") == "WAIT_FOR_INDIVIDUAL_PASS"]
    if not waiting:
        waiting = [
            {
                "experiment_id": "next_model_experiment",
                "required_before_execute": [],
                "reason": "no result_report waiting experiment recorded",
            }
        ]
    return [
        {
            "experiment_id": row.get("experiment_id"),
            "current_status": row.get("status"),
            "approval_status": "NOT_APPROVED",
            "required_before_execute": row.get("required_before_execute", []),
            "entry_conditions": [
                "training launch may use the pre-registered current_baseline lane when no-hindsight and core gates pass",
                "result_report.summary.pass_to_next must contain at least one upstream experiment before production promotion review",
                "half_year_walkforward decision must be PROMOTE_CANDIDATE before production promotion review",
                "sealed OOS, replay, and no-hindsight verifier must all pass on the same candidate",
                "data degradations affecting selected features must be resolved or explicitly scoped to research-only technical lane",
                "manual promotion review is still required; readiness never writes models/latest_lgbm.pkl",
            ],
            "current_half_year_decision": half_year_walkforward.get("decision", "MISSING"),
            "reason": row.get("reason"),
        }
        for row in waiting
    ]


def readiness_assessment(
    steps: list[dict[str, Any]],
    config: dict[str, Any],
    health: dict[str, Any],
    result_report: dict[str, Any],
    model_group: dict[str, Any],
    half_year_walkforward: dict[str, Any],
    run_date: str,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    blocker_details: list[dict[str, Any]] = []
    warning_details: list[dict[str, Any]] = []
    promotion_blockers: list[str] = []
    promotion_blocker_details: list[dict[str, Any]] = []
    degradations = data_degradations(health, run_date=run_date)

    def add_blocker(detail: dict[str, Any]) -> None:
        blockers.append(str(detail["message"]))
        blocker_details.append(detail)

    def add_warning(detail: dict[str, Any]) -> None:
        warnings.append(str(detail["message"]))
        warning_details.append(detail)

    def add_promotion_blocker(detail: dict[str, Any]) -> None:
        promotion_blockers.append(str(detail["message"]))
        promotion_blocker_details.append(detail)

    failed_steps = [step["name"] for step in steps if not step_status_ok(step)]
    if failed_steps:
        add_blocker(
            classify_item(
                category="must_fix_before_training",
                code="failed_readiness_steps",
                message="failed readiness steps: " + ", ".join(failed_steps),
                source="steps",
                action="修正失敗 gate；正式自動訓練前不能有 FAILED readiness step。",
                evidence={"failed_steps": failed_steps},
            )
        )

    monitor_config = config.get("monitor") if isinstance(config.get("monitor"), dict) else {}
    auto_retrain_enabled = bool(monitor_config.get("auto_retrain", False))
    if auto_retrain_enabled:
        add_blocker(
            classify_item(
                category="must_fix_before_training",
                code="auto_retrain_enabled_before_approval",
                message="monitor.auto_retrain is enabled before readiness is fully approved",
                source="config/automation.yaml",
                action="關閉 auto_retrain，直到 readiness 為 READY_FOR_AUTOMATED_TRAINING_REVIEW 並完成人工 review。",
            )
        )

    if str(config.get("retrain", {}).get("schedule", "")).lower() not in {"manual", ""}:
        add_warning(
            classify_item(
                category="acceptable_monitoring_warning",
                code="retrain_schedule_not_manual",
                message=f"retrain.schedule={config.get('retrain', {}).get('schedule')} is not manual",
                source="config/automation.yaml",
                action="正式啟用前確認排程仍符合人工 review 決策。",
            )
        )

    health_status = str(health.get("status", "MISSING")).upper()
    group_auto = str(model_group.get("auto_retrain_readiness", "MISSING")).upper()
    group_auto_ready_for_training = group_auto in TRAINING_READY_MODEL_GROUP_STATES
    if health_status != "OK":
        warn_checks = health_warn_checks(health)
        health_detail = classify_item(
            category="must_fix_before_training" if not group_auto_ready_for_training else "acceptable_monitoring_warning",
            code="model_health_not_ok",
            message=f"model health is {health_status}",
            source="artifacts/model_health_report_latest.json",
            action=(
                "處理 health CRITICAL/未分類 WARN 來源；正式自動訓練前不能有未分類 health 風險。"
                if not group_auto_ready_for_training
                else "health WARN 已被 model group 分類為可接受監控或明確資料降級；可進訓練啟動 review，但不可直接 promotion。"
            ),
            evidence={
                "checks": warn_checks,
                "auto_retrain_readiness": group_auto,
                "auto_retrain_readiness_reason": model_group.get("auto_retrain_readiness_reason"),
                "auto_retrain_readiness_warnings": model_group.get("auto_retrain_readiness_warnings", []),
            },
        )
        if group_auto_ready_for_training:
            add_warning(health_detail)
        else:
            add_blocker(health_detail)
        if group_auto_ready_for_training:
            add_promotion_blocker(
                classify_item(
                    category="must_fix_before_training",
                    code="model_health_warn_blocks_promotion",
                    message=f"model health is {health_status}; production promotion remains blocked",
                    source="artifacts/model_health_report_latest.json",
                    action="先補齊資料降級或讓 promotion gate 明確接受該降級，才可升正式模型。",
                    evidence={"checks": warn_checks},
                )
            )
        checks = health_checks_by_name(health)
        if check_not_ok(checks.get("monitor.psi_baseline")):
            baseline_check = checks["monitor.psi_baseline"]
            baseline_category = (
                "data_unavailable_with_explicit_degradation"
                if degradations
                else "must_fix_before_training"
            )
            baseline_detail = classify_item(
                category=baseline_category,
                code="psi_baseline_incomplete",
                message=f"monitor.psi_baseline is {baseline_check.get('status')}: {baseline_check.get('message')}",
                source="artifacts/model_health_report_latest.json",
                action="補齊缺失監控特徵，或保留 research-only 降級並禁止 promotion。",
                evidence={"degradations": degradations},
            )
            if degradations:
                add_warning(baseline_detail)
                add_promotion_blocker(baseline_detail)
            else:
                add_blocker(baseline_detail)
        if check_not_ok(checks.get("monitor.factor")):
            factor_check = checks["monitor.factor"]
            add_warning(
                classify_item(
                    category="acceptable_monitoring_warning",
                    code="factor_monitor_warn",
                    message=f"monitor.factor is {factor_check.get('status')}: {factor_check.get('message')}",
                    source="artifacts/factor_monitor_report.json",
                    action="保留為監控 warning；正式訓練前若要使用 factor-derived rule，需另開實驗 gate。",
                )
            )
        if check_not_ok(checks.get("ranking.realized_outcome")):
            outcome_check = checks["ranking.realized_outcome"]
            add_warning(
                classify_item(
                    category="acceptable_monitoring_warning",
                    code="ranking_outcome_not_mature",
                    message=f"ranking.realized_outcome is {outcome_check.get('status')}: {outcome_check.get('message')}",
                    source="artifacts/model_health_report_latest.json",
                    action="標示為時間未成熟；等待 10d horizon 後再評估，不當作模型失敗。",
                )
            )

    if group_auto not in TRAINING_READY_MODEL_GROUP_STATES:
        add_blocker(
            classify_item(
                category="must_fix_before_training",
                code="model_group_auto_retrain_not_ready",
                message=f"model_group auto_retrain_readiness is {group_auto}",
                source="artifacts/model_group_acceptance_<date>.json",
                action="先處理 model health 未分類風險；不得啟動自動訓練。",
                evidence={
                    "model_health_status": model_group.get("model_health_status"),
                    "auto_retrain_readiness_reason": model_group.get("auto_retrain_readiness_reason"),
                },
            )
        )
    elif group_auto != "READY":
        add_warning(
            classify_item(
                category="acceptable_monitoring_warning",
                code="model_group_ready_with_monitoring_warnings",
                message=f"model_group auto_retrain_readiness is {group_auto}",
                source="artifacts/model_group_acceptance_<date>.json",
                action="可進訓練啟動 review；promotion 仍需處理 warning 或通過 promotion gate。",
                evidence={
                    "model_health_status": model_group.get("model_health_status"),
                    "auto_retrain_readiness_reason": model_group.get("auto_retrain_readiness_reason"),
                    "auto_retrain_readiness_warnings": model_group.get("auto_retrain_readiness_warnings", []),
                },
            )
        )

    result_status = str(result_report.get("status", "MISSING")).upper()
    if result_status not in {"OK", "WARN"}:
        add_blocker(
            classify_item(
                category="must_fix_before_training",
                code="model_experiment_result_report_bad_status",
                message=f"model experiment result report status is {result_status}",
                source="artifacts/model_experiments/model_exp_result_report_<date>.json",
                action="修正 result report 產出或 verifier；正式訓練前 result report 必須為 OK/WARN。",
            )
        )

    summary = result_report.get("summary") if isinstance(result_report.get("summary"), dict) else {}
    pass_to_next = summary.get("pass_to_next") or []
    if not pass_to_next:
        add_promotion_blocker(
            classify_item(
                category="waiting_for_approved_experiment",
                code="no_approved_next_stage_experiment",
                message="no model experiment is approved for production promotion review yet",
                source="artifacts/model_experiments/model_exp_result_report_<date>.json",
                action="可先啟動預註冊自動訓練候選；但不能用 MONITOR_ONLY 或 waiting experiment 直接 promotion。",
                evidence={"waiting": summary.get("waiting", []), "pass_to_next": pass_to_next},
            )
        )
    if summary.get("blocked"):
        add_warning(
            classify_item(
                category="waiting_for_approved_experiment",
                code="blocked_experiments",
                message="blocked experiments: " + ", ".join(str(item) for item in summary.get("blocked", [])),
                source="artifacts/model_experiments/model_exp_result_report_<date>.json",
                action="補齊該 experiment 的 required artifact 後再重跑 result report。",
            )
        )
    if summary.get("waiting"):
        add_warning(
            classify_item(
                category="waiting_for_approved_experiment",
                code="waiting_experiments",
                message="waiting experiments: " + ", ".join(str(item) for item in summary.get("waiting", [])),
                source="artifacts/model_experiments/model_exp_result_report_<date>.json",
                action="等待 individual experiments 通過後，才能執行 combined experiment。",
                evidence={"waiting": summary.get("waiting", [])},
            )
        )

    half_year_summary = half_year_walkforward.get("summary") if isinstance(half_year_walkforward.get("summary"), dict) else {}
    half_year_baseline = half_year_walkforward.get("variants", {}).get("current_baseline", {})
    half_year_topn = half_year_baseline.get("topn_proxy") if isinstance(half_year_baseline.get("topn_proxy"), dict) else {}
    no_hindsight_policy = (
        half_year_walkforward.get("contract", {})
        .get("no_hindsight_policy", {})
        if isinstance(half_year_walkforward.get("contract"), dict)
        else {}
    )
    half_year_status = str(half_year_walkforward.get("status", "MISSING")).upper()
    if half_year_status != "OK":
        add_blocker(
            classify_item(
                category="must_fix_before_training",
                code="half_year_walkforward_not_ok",
                message=f"half-year walk-forward status is {half_year_status}",
                source="artifacts/model_experiments/half_year_walkforward_validation_<date>.json",
                action="修正 half-year artifact；正式訓練前 governance gate 必須 OK。",
            )
        )
    half_year_decision = str(half_year_walkforward.get("decision", "MISSING")).upper()
    if half_year_decision == "REJECTED":
        add_blocker(
            classify_item(
                category="waiting_for_approved_experiment",
                code="half_year_decision_rejected",
                message="half-year research decision is REJECTED",
                source="artifacts/model_experiments/half_year_walkforward_validation_<date>.json",
                action="重新定義下一輪預註冊實驗；不得 promotion。",
            )
        )
    elif half_year_decision == "MONITOR_ONLY":
        add_promotion_blocker(
            classify_item(
                category="waiting_for_approved_experiment",
                code="half_year_decision_monitor_only",
                message="half-year research decision is MONITOR_ONLY",
                source="artifacts/model_experiments/half_year_walkforward_validation_<date>.json",
                action="MONITOR_ONLY 可啟動預註冊訓練候選，但正式 promotion 前必須有 PROMOTE_CANDIDATE 或新的 approved experiment。",
                evidence={"decision_rationale": half_year_walkforward.get("decision_rationale")},
            )
        )
    elif half_year_decision != "PROMOTE_CANDIDATE":
        add_blocker(
            classify_item(
                category="waiting_for_approved_experiment",
                code="half_year_decision_unknown",
                message=f"half-year research decision is {half_year_decision}",
                source="artifacts/model_experiments/half_year_walkforward_validation_<date>.json",
                action="修正 decision 標準化；只能是 PROMOTE_CANDIDATE/MONITOR_ONLY/REJECTED。",
            )
        )
    if no_hindsight_policy.get("promotion_gate_variant") != "current_baseline":
        add_blocker(
            classify_item(
                category="must_fix_before_training",
                code="promotion_gate_not_current_baseline",
                message="half-year no-hindsight policy missing current_baseline promotion gate",
                source="artifacts/model_experiments/half_year_walkforward_validation_<date>.json",
                action="promotion gate 必須固定為 current_baseline，diagnostic variants 不可同輪升級。",
            )
        )
    if no_hindsight_policy.get("diagnostic_failures_cannot_define_same_run_filters") is not True:
        add_blocker(
            classify_item(
                category="must_fix_before_training",
                code="same_run_diagnostic_filters_allowed",
                message="half-year no-hindsight policy does not block same-run diagnostic filters",
                source="artifacts/model_experiments/half_year_walkforward_validation_<date>.json",
                action="禁止同輪用 diagnostic failure 回補 filter。",
            )
        )
    if no_hindsight_policy.get("new_filters_require_next_walkforward_run") is not True:
        add_blocker(
            classify_item(
                category="must_fix_before_training",
                code="new_filters_do_not_require_next_walkforward",
                message="half-year no-hindsight policy does not require next walk-forward run for new filters",
                source="artifacts/model_experiments/half_year_walkforward_validation_<date>.json",
                action="新 filter 必須進下一輪 walk-forward。",
            )
        )
    baseline_auc = half_year_summary.get("baseline_auc")
    if baseline_auc is None or float(baseline_auc) < HALF_YEAR_WALKFORWARD_MIN_AUC:
        add_blocker(
            classify_item(
                category="waiting_for_approved_experiment",
                code="half_year_baseline_auc_below_gate",
                message=f"half-year baseline_auc below gate: {baseline_auc}",
                source="artifacts/model_experiments/half_year_walkforward_validation_<date>.json",
                action="下一輪實驗需達到預註冊 AUC gate。",
            )
        )
    uplift = half_year_topn.get("topn_minus_universe_return")
    if uplift is None or float(uplift) <= HALF_YEAR_WALKFORWARD_MIN_UPLIFT:
        add_blocker(
            classify_item(
                category="waiting_for_approved_experiment",
                code="half_year_topn_uplift_below_gate",
                message=f"half-year Top10 uplift below gate: {uplift}",
                source="artifacts/model_experiments/half_year_walkforward_validation_<date>.json",
                action="下一輪實驗需達到 Top10 vs universe uplift gate。",
            )
        )
    folds = half_year_baseline.get("folds") if isinstance(half_year_baseline.get("folds"), list) else []
    positive_folds = [
        row
        for row in folds
        if float((row.get("topn_proxy") or {}).get("topn_minus_universe_return") or 0) > HALF_YEAR_WALKFORWARD_MIN_UPLIFT
    ]
    if len(positive_folds) < HALF_YEAR_WALKFORWARD_MIN_POSITIVE_FOLDS:
        add_blocker(
            classify_item(
                category="waiting_for_approved_experiment",
                code="half_year_positive_folds_below_gate",
                message=f"half-year positive folds below gate: {len(positive_folds)}/{HALF_YEAR_WALKFORWARD_MIN_POSITIVE_FOLDS}",
                source="artifacts/model_experiments/half_year_walkforward_validation_<date>.json",
                action="下一輪實驗需達到 positive folds gate。",
            )
        )
    negative_folds = [
        f"{row.get('validation_start')}~{row.get('validation_end')}"
        for row in folds
        if float((row.get("topn_proxy") or {}).get("topn_minus_universe_return") or 0) <= HALF_YEAR_WALKFORWARD_MIN_UPLIFT
    ]
    if negative_folds:
        add_warning(
            classify_item(
                category="acceptable_monitoring_warning",
                code="half_year_negative_folds_diagnostic_only",
                message="half-year post-hoc negative or flat fold windows (diagnostic only): " + ", ".join(negative_folds),
                source="artifacts/model_experiments/half_year_walkforward_validation_<date>.json",
                action="只可作下一輪假設，不可同輪 promotion filter。",
                evidence={"negative_or_flat_folds": negative_folds},
            )
        )
    core_ok = not failed_steps and not auto_retrain_enabled
    if not core_ok:
        status = "FAILED"
    elif blockers:
        status = "PREPARED_WITH_BLOCKERS"
    else:
        status = "READY_FOR_AUTOMATED_TRAINING_REVIEW"
    training_launch_ready = status == "READY_FOR_AUTOMATED_TRAINING_REVIEW"
    return {
        "status": status,
        "training_launch_ready": training_launch_ready,
        "training_launch_mode": "pre_registered_candidate_with_promotion_gate" if training_launch_ready else "blocked",
        "promotion_ready": not promotion_blockers and not blockers,
        "promotion_blockers": promotion_blockers,
        "blockers": blockers,
        "warnings": warnings,
        "blocker_details": blocker_details,
        "warning_details": warning_details,
        "promotion_blocker_details": promotion_blocker_details,
        "blocker_summary_by_category": category_counts(blocker_details),
        "warning_summary_by_category": category_counts(warning_details),
        "promotion_blocker_summary_by_category": category_counts(promotion_blocker_details),
        "data_degradations": degradations,
        "policy_decisions": {
            "monitor_only_blocks_formal_automated_training": False,
            "monitor_only_blocks_production_promotion": True,
            "automated_training_can_start_without_promotion_candidate": True,
            "technical_only_research_allowed_when_revenue_unavailable": bool(degradations),
            "technical_only_research_allows_promotion": False,
            "readiness_artifact_can_prepare_review_but_never_promotes": True,
        },
        "next_stage_experiment_entry_conditions": next_stage_experiment_entry_conditions(
            result_report,
            half_year_walkforward,
        ),
    }


def build_payload(args: argparse.Namespace, steps: list[dict[str, Any]]) -> dict[str, Any]:
    config = load_config()
    health_path = ARTIFACTS_DIR / "model_health_report_latest.json"
    model_group_path = ARTIFACTS_DIR / f"model_group_acceptance_{args.date}.json"
    result_report_path = MODEL_EXPERIMENTS_DIR / f"model_exp_result_report_{args.date}.json"
    half_year_path = half_year_walkforward_path(args.date)
    health = load_json(health_path)
    model_group = load_json(model_group_path)
    result_report = load_json(result_report_path)
    half_year_walkforward = load_json(half_year_path)
    assessment = readiness_assessment(steps, config, health, result_report, model_group, half_year_walkforward, args.date)
    status = assessment["status"]
    high_choppy_status = high_choppy_context_status(args.date)
    fixed_share_status = fixed_share_research_status(args.date)
    half_year_baseline = half_year_walkforward.get("variants", {}).get("current_baseline", {})
    half_year_topn = half_year_baseline.get("topn_proxy") if isinstance(half_year_baseline.get("topn_proxy"), dict) else {}
    no_hindsight_policy = (
        half_year_walkforward.get("contract", {})
        .get("no_hindsight_policy", {})
        if isinstance(half_year_walkforward.get("contract"), dict)
        else {}
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": status,
        "contract": {
            "pre_automation_gate": True,
            "research_only": True,
            "does_not_fetch_data": True,
            "does_not_train_production_model": True,
            "may_train_in_memory_research_models": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_risk_adjusted_score": True,
            "does_not_change_production_ranking": True,
            "does_not_enable_auto_retrain": True,
            "no_hindsight_required": True,
            "diagnostic_failures_cannot_define_same_run_filters": True,
        },
        "readiness": {
            "core_steps_ok": all(step_status_ok(step) for step in steps),
            "auto_retrain_enabled": bool((config.get("monitor") or {}).get("auto_retrain", False)),
            "retrain_schedule": (config.get("retrain") or {}).get("schedule"),
            "model_health_status": health.get("status", "MISSING"),
            "model_group_acceptance_status": model_group.get("status", "MISSING"),
            "auto_retrain_readiness": model_group.get("auto_retrain_readiness", "MISSING"),
            "model_experiment_result_status": result_report.get("status", "MISSING"),
            "half_year_walkforward_status": half_year_walkforward.get("status", "MISSING"),
            "half_year_research_question": half_year_walkforward.get("research_question"),
            "half_year_layer": half_year_walkforward.get("layer"),
            "half_year_decision": half_year_walkforward.get("decision", "MISSING"),
            "half_year_decision_rationale": half_year_walkforward.get("decision_rationale"),
            "half_year_baseline_auc": (half_year_walkforward.get("summary") or {}).get("baseline_auc"),
            "half_year_topn_return": half_year_topn.get("avg_topn_future_return"),
            "half_year_universe_return": half_year_topn.get("avg_universe_future_return"),
            "half_year_topn_minus_universe_return": half_year_topn.get("topn_minus_universe_return"),
            "half_year_no_hindsight_policy": no_hindsight_policy,
            "pass_to_next": (result_report.get("summary") or {}).get("pass_to_next", []),
            "training_launch_ready": assessment["training_launch_ready"],
            "training_launch_mode": assessment["training_launch_mode"],
            "promotion_ready": assessment["promotion_ready"],
            "promotion_blocked": bool(assessment["promotion_blockers"]),
            "promotion_blockers": assessment["promotion_blockers"],
            "blocked": assessment["blockers"],
            "warnings": assessment["warnings"],
            "blocker_details": assessment["blocker_details"],
            "warning_details": assessment["warning_details"],
            "promotion_blocker_details": assessment["promotion_blocker_details"],
            "blocker_summary_by_category": assessment["blocker_summary_by_category"],
            "warning_summary_by_category": assessment["warning_summary_by_category"],
            "promotion_blocker_summary_by_category": assessment["promotion_blocker_summary_by_category"],
            "data_degradations": assessment["data_degradations"],
            "policy_decisions": assessment["policy_decisions"],
            "high_choppy_context_status": high_choppy_status,
            "fixed_share_research_status": fixed_share_status,
            "next_stage_experiment_entry_conditions": assessment["next_stage_experiment_entry_conditions"],
        },
        "artifacts": {
            "model_health_report": repo_path(health_path),
            "model_group_acceptance": repo_path(model_group_path),
            "model_experiment_result_report": repo_path(result_report_path),
            "half_year_walkforward_validation": repo_path(half_year_path),
            "technical_only_training_lane": repo_path(technical_only_lane_path(args.date)),
            "high_choppy_context_overlay": repo_path(high_choppy_context_overlay_path(args.date)),
            "fixed_share_research_flow": repo_path(fixed_share_research_flow_path(args.date)),
            "fixed_share_research_factory_verification": repo_path(fixed_share_research_factory_verification_path()),
            "feature_experiment_gate": repo_path(ARTIFACTS_DIR / f"feature_experiment_gate_{args.date}.json"),
            "model_research_flow": repo_path(MODEL_EXPERIMENTS_DIR / f"model_research_flow_{args.date}.json"),
        },
        "steps": steps,
    }


def md_cell(value: Any) -> str:
    text = str(value).replace("\n", " ").replace("|", "\\|")
    return text


def render_markdown(payload: dict[str, Any]) -> str:
    readiness = payload["readiness"]
    high_choppy = readiness.get("high_choppy_context_status") or {}
    fixed_share = readiness.get("fixed_share_research_status") or {}
    lines = [
        "# Training Automation Readiness",
        "",
        f"- status：`{payload['status']}`",
        f"- date：`{payload['date']}`",
        f"- auto_retrain_enabled：`{readiness['auto_retrain_enabled']}`",
        f"- auto_retrain_readiness：`{readiness['auto_retrain_readiness']}`",
        f"- model_health_status：`{readiness['model_health_status']}`",
        f"- training_launch_ready：`{readiness['training_launch_ready']}`",
        f"- training_launch_mode：`{readiness['training_launch_mode']}`",
        f"- promotion_ready：`{readiness['promotion_ready']}`",
        f"- promotion_blocked：`{readiness['promotion_blocked']}`",
        f"- result_report_status：`{readiness['model_experiment_result_status']}`",
        f"- half_year_walkforward_status：`{readiness['half_year_walkforward_status']}`",
        f"- half_year_layer：`{readiness['half_year_layer']}`",
        f"- half_year_decision：`{readiness['half_year_decision']}`",
        f"- half_year_decision_rationale：{readiness['half_year_decision_rationale']}",
        f"- half_year_topn_minus_universe_return：`{readiness['half_year_topn_minus_universe_return']}`",
        f"- half_year_promotion_gate_variant：`{readiness['half_year_no_hindsight_policy'].get('promotion_gate_variant')}`",
        f"- same_run_diagnostic_filters_allowed：`{not readiness['half_year_no_hindsight_policy'].get('diagnostic_failures_cannot_define_same_run_filters', False)}`",
        f"- high_choppy_context：`{high_choppy.get('status')}` / `{high_choppy.get('decision')}`",
        f"- high_choppy_blocks_main_training：`{high_choppy.get('blocks_main_training')}`",
        f"- fixed_share_research_flow：`{fixed_share.get('flow_status')}`",
        f"- fixed_share_research_verification：`{fixed_share.get('verification_status')}` errors=`{fixed_share.get('verification_errors')}`",
        "",
        "## Blockers",
        "",
    ]
    blockers = readiness.get("blocked") or []
    lines.extend([f"- {item}" for item in blockers] if blockers else ["- none"])
    lines.extend(["", "## Blocker Classification", ""])
    summary = readiness.get("blocker_summary_by_category") or {}
    lines.extend([f"- {category}：`{count}`" for category, count in sorted(summary.items())])
    details = readiness.get("blocker_details") or []
    if details:
        lines.extend(["", "| Category | Code | Message | Action |", "|---|---|---|---|"])
        for row in details:
            lines.append(
                "| {category} | `{code}` | {message} | {action} |".format(
                    category=md_cell(row.get("category")),
                    code=md_cell(row.get("code")),
                    message=md_cell(row.get("message")),
                    action=md_cell(row.get("action")),
                )
            )
    else:
        lines.append("- none")
    lines.extend(["", "## Warnings", ""])
    warnings = readiness.get("warnings") or []
    lines.extend([f"- {item}" for item in warnings] if warnings else ["- none"])
    warning_details = readiness.get("warning_details") or []
    if warning_details:
        lines.extend(["", "| Category | Code | Message | Action |", "|---|---|---|---|"])
        for row in warning_details:
            lines.append(
                "| {category} | `{code}` | {message} | {action} |".format(
                    category=md_cell(row.get("category")),
                    code=md_cell(row.get("code")),
                    message=md_cell(row.get("message")),
                    action=md_cell(row.get("action")),
                )
            )
    lines.extend(["", "## Promotion Blockers", ""])
    promotion_blockers = readiness.get("promotion_blockers") or []
    lines.extend([f"- {item}" for item in promotion_blockers] if promotion_blockers else ["- none"])
    promotion_summary = readiness.get("promotion_blocker_summary_by_category") or {}
    if promotion_summary:
        lines.extend(["", "## Promotion Blocker Classification", ""])
        lines.extend([f"- {category}：`{count}`" for category, count in sorted(promotion_summary.items())])
    promotion_details = readiness.get("promotion_blocker_details") or []
    if promotion_details:
        lines.extend(["", "| Category | Code | Message | Action |", "|---|---|---|---|"])
        for row in promotion_details:
            lines.append(
                "| {category} | `{code}` | {message} | {action} |".format(
                    category=md_cell(row.get("category")),
                    code=md_cell(row.get("code")),
                    message=md_cell(row.get("message")),
                    action=md_cell(row.get("action")),
                )
            )
    lines.extend(["", "## Data Degradations", ""])
    degradations = readiness.get("data_degradations") or []
    if degradations:
        for row in degradations:
            lines.extend(
                [
                    f"- id：`{row.get('id')}`",
                    f"  reason：{row.get('reason')}",
                    f"  degradation：{row.get('degradation')}",
                    f"  required_before_training：{row.get('required_before_training')}",
                ]
            )
    else:
        lines.append("- none")
    lines.extend(["", "## Policy Decisions", ""])
    for key, value in sorted((readiness.get("policy_decisions") or {}).items()):
        lines.append(f"- {key}：`{value}`")
    lines.extend(["", "## Next Stage Entry Conditions", ""])
    next_conditions = readiness.get("next_stage_experiment_entry_conditions") or []
    if next_conditions:
        for row in next_conditions:
            lines.append(f"- experiment_id：`{row.get('experiment_id')}` approval_status：`{row.get('approval_status')}`")
            for condition in row.get("entry_conditions", []):
                lines.append(f"  - {condition}")
    else:
        lines.append("- none")
    lines.extend(["", "## Steps", "", "| Step | Status |", "|---|---|"])
    for step in payload["steps"]:
        lines.append(f"| `{step['name']}` | `{step['status']}` |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    steps: list[dict[str, Any]] = []
    steps.extend(research_flow_step(args))
    steps.extend(fixed_share_research_flow_step(args))
    steps.extend(half_year_walkforward_step(args))
    steps.extend(half_year_no_hindsight_verify_step(args))
    steps.extend(run_step(name, command, args.timeout_seconds) for name, command in CORE_CHECKS)
    steps.extend(build_result_report_steps(args))
    payload = build_payload(args, steps)
    output_path = resolve_path(args.output) or ARTIFACTS_DIR / f"training_automation_readiness_{args.date}.json"
    if output_path is None:
        raise RuntimeError("output path resolution failed")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output_path.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "output": repo_path(output_path),
                "training_launch_ready": payload["readiness"]["training_launch_ready"],
                "promotion_ready": payload["readiness"]["promotion_ready"],
                "blocked": payload["readiness"]["blocked"],
                "promotion_blockers": payload["readiness"]["promotion_blockers"],
                "warnings": payload["readiness"]["warnings"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if payload["status"] != "FAILED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
