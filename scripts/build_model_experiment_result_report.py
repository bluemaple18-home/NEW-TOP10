#!/usr/bin/env python3
"""彙整 MODEL-EXP-01 已執行測試結果。

此腳本只讀 model_experiments artifacts，產生研究結論報告。
不訓練模型、不改 ranking、不做 production promotion。
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import model_experiment_ledger as ledger_lib  # noqa: E402

MODEL_EXPERIMENTS_DIR = PROJECT_ROOT / "artifacts" / "model_experiments"
SCHEMA_VERSION = "model-experiment-result-report.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build MODEL-EXP-01 result report")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--run-manifest", default=None)
    parser.add_argument("--portfolio-comparison", default=None)
    parser.add_argument("--portfolio-comparison-extended", default=None)
    parser.add_argument("--regime-ablation", default=None)
    parser.add_argument("--regime-offline-ablation", default=None)
    parser.add_argument("--candidate-persistence-ablation", default=None)
    parser.add_argument("--candidate-persistence-ablation-extended", default=None)
    parser.add_argument("--output", default=None)
    parser.add_argument("--ledger", default=str(ledger_lib.DEFAULT_LEDGER))
    parser.add_argument("--no-ledger-update", action="store_true")
    parser.add_argument("--self-test", action="store_true")
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
        return {"_missing": True, "_path": repo_path(path)}
    return json.loads(path.read_text(encoding="utf-8"))


def safe_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def default_path(args: argparse.Namespace, name: str) -> Path:
    mapping = {
        "run_manifest": MODEL_EXPERIMENTS_DIR / f"model_exp_run_manifest_{args.date}.json",
        "portfolio_comparison": MODEL_EXPERIMENTS_DIR / f"model_exp_strategy_matrix_comparison_portfolio_risk_overlay_{args.date}.json",
        "portfolio_comparison_extended": MODEL_EXPERIMENTS_DIR / f"model_exp_strategy_matrix_comparison_portfolio_risk_overlay_extended_tail_{args.date}.json",
        "regime_ablation": MODEL_EXPERIMENTS_DIR / f"model_exp_regime_feature_group_ablation_{args.date}.json",
        "regime_offline_ablation": MODEL_EXPERIMENTS_DIR / f"regime_feature_offline_ablation_{args.date}.json",
        "candidate_persistence_ablation": MODEL_EXPERIMENTS_DIR / f"candidate_persistence_materialized_ablation_{args.date}.json",
        "candidate_persistence_ablation_extended": MODEL_EXPERIMENTS_DIR / f"candidate_persistence_materialized_ablation_extended_{args.date}.json",
    }
    return mapping[name]


def portfolio_decision(payload: dict[str, Any], extended: dict[str, Any] | None = None) -> dict[str, Any]:
    rows = {row.get("variant"): row for row in payload.get("summary", [])}
    current = rows.get("current", {})
    overlay = rows.get("portfolio_risk_overlay", {})
    current_return = safe_float(current.get("best_total_return"))
    overlay_return = safe_float(overlay.get("best_total_return"))
    current_dd = safe_float(current.get("best_max_drawdown"))
    overlay_dd = safe_float(overlay.get("best_max_drawdown"))
    current_score = safe_float(current.get("best_score"))
    overlay_score = safe_float(overlay.get("best_score"))
    return_delta = None if current_return is None or overlay_return is None else round(overlay_return - current_return, 6)
    dd_delta = None if current_dd is None or overlay_dd is None else round(overlay_dd - current_dd, 6)
    score_delta = None if current_score is None or overlay_score is None else round(overlay_score - current_score, 6)
    recent_passed = (
        return_delta is not None
        and return_delta > 0
        and dd_delta is not None
        and dd_delta > 0
        and score_delta is not None
        and score_delta > 0
    )
    extended_metrics = portfolio_delta_metrics(extended or {})
    extended_passed = bool(extended_metrics.get("passed"))
    passed = recent_passed and (extended_passed if extended and not extended.get("_missing") else True)
    return {
        "experiment_id": "model_exp_portfolio_risk_overlay_only",
        "status": "PASS_TO_PROMOTION_REVIEW_QUEUE" if passed and extended_passed else ("PASS_TO_LONGER_REPLAY" if passed else "MONITOR_ONLY"),
        "metrics": {
            "current_best": current,
            "overlay_best": overlay,
            "delta_total_return": return_delta,
            "delta_max_drawdown": dd_delta,
            "delta_score": score_delta,
            "extended": extended_metrics,
        },
        "notes": [
            "這是 post-ranking overlay/replay track，不是 LightGBM feature。",
            "extended tail 若同時通過，下一步也只能進人工 promotion review，不可直接改 production ranking。",
        ],
    }


def portfolio_delta_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload or payload.get("_missing"):
        return {"available": False, "passed": False}
    rows = {row.get("variant"): row for row in payload.get("summary", [])}
    current = rows.get("current_tail") or rows.get("current") or {}
    overlay = rows.get("portfolio_risk_overlay_tail") or rows.get("portfolio_risk_overlay") or {}
    current_return = safe_float(current.get("best_total_return"))
    overlay_return = safe_float(overlay.get("best_total_return"))
    current_dd = safe_float(current.get("best_max_drawdown"))
    overlay_dd = safe_float(overlay.get("best_max_drawdown"))
    current_score = safe_float(current.get("best_score"))
    overlay_score = safe_float(overlay.get("best_score"))
    return_delta = None if current_return is None or overlay_return is None else round(overlay_return - current_return, 6)
    dd_delta = None if current_dd is None or overlay_dd is None else round(overlay_dd - current_dd, 6)
    score_delta = None if current_score is None or overlay_score is None else round(overlay_score - current_score, 6)
    return {
        "available": True,
        "passed": return_delta is not None and return_delta > 0 and dd_delta is not None and dd_delta > 0 and score_delta is not None and score_delta > 0,
        "current_best": current,
        "overlay_best": overlay,
        "delta_total_return": return_delta,
        "delta_max_drawdown": dd_delta,
        "delta_score": score_delta,
    }


def top_shadow_features(payload: dict[str, Any], limit: int = 20) -> list[dict[str, Any]]:
    rows = []
    for row in payload.get("metrics", []):
        if row.get("status") != "SHADOW_CANDIDATE":
            continue
        rows.append(
            {
                "group": row.get("group"),
                "feature": row.get("feature"),
                "regime_label": row.get("regime_label"),
                "horizon": row.get("horizon"),
                "days": row.get("days"),
                "ic_mean": safe_float(row.get("ic_mean")),
                "abs_ic_mean": safe_float(row.get("abs_ic_mean")),
                "t_stat": safe_float(row.get("ic_t_stat")),
                "direction_consistency": safe_float(row.get("ic_direction_consistency")),
                "spread_mean": safe_float(row.get("top_bottom_spread_mean")),
            }
        )
    return sorted(rows, key=lambda item: item.get("abs_ic_mean") or 0, reverse=True)[:limit]


def regime_decision(payload: dict[str, Any], offline: dict[str, Any] | None = None) -> dict[str, Any]:
    payload_missing = payload.get("_missing") is True
    summary = payload.get("summary", {})
    top = top_shadow_features(payload)
    thin_regime_rows = [row for row in top if int(row.get("days") or 0) < 20]
    stable_rows = [row for row in top if int(row.get("days") or 0) >= 20]
    offline_summary = (offline or {}).get("summary", {})
    auc_delta = safe_float(offline_summary.get("baseline_minus_drop_auc"))
    topn_delta = safe_float(offline_summary.get("baseline_minus_drop_topn_return"))
    offline_available = bool(offline) and not (offline or {}).get("_missing")
    offline_evidence_available = offline_available and (auc_delta is not None or topn_delta is not None or bool(offline_summary))
    regime_evidence_available = (not payload_missing) and (
        bool(top)
        or summary.get("feature_count") is not None
        or summary.get("metric_rows") is not None
        or summary.get("candidate_metric_rows") is not None
    )
    evidence_available = regime_evidence_available or offline_evidence_available
    offline_passed = (
        offline_evidence_available
        and auc_delta is not None
        and auc_delta >= 0.002
        and topn_delta is not None
        and topn_delta >= 0
    )
    if offline_evidence_available:
        status = "PASS_TO_MODEL_EXP_02" if offline_passed else "MONITOR_ONLY_WEAK_MODEL_UPLIFT"
    elif regime_evidence_available:
        status = "PASS_TO_OFFLINE_ABLATION_WITH_CAUTION" if top else "MONITOR_ONLY"
    else:
        status = "MONITOR_ONLY"
    return {
        "experiment_id": "model_exp_regime_feature_group_ablation",
        "status": status,
        "evidence_available": evidence_available,
        "metrics": {
            "evidence_available": evidence_available,
            "missing_evidence_reason": None if evidence_available else "regime and offline ablation artifacts are missing required primary evidence",
            "feature_count": summary.get("feature_count"),
            "metric_rows": summary.get("metric_rows"),
            "candidate_metric_rows": summary.get("candidate_metric_rows"),
            "top_shadow_features": top,
            "thin_regime_top_count": len(thin_regime_rows),
            "stable_window_top_count": len(stable_rows),
            "offline_ablation": offline_summary,
        },
        "notes": [
            "PANIC_SELLING top signals 樣本天數偏少，不能直接視為穩定訊號。",
            "offline ablation 若模型層 uplift 太弱或 Top10 proxy 變差，應降級觀察。",
        ],
    }


def candidate_persistence_decision(current: dict[str, Any], extended: dict[str, Any]) -> dict[str, Any] | None:
    if current.get("_missing") and extended.get("_missing"):
        return None
    current_buckets = current.get("summary", {}).get("candidate_buckets", [])
    extended_buckets = extended.get("summary", {}).get("candidate_buckets", [])
    current_evidence_available = not current.get("_missing") and (
        current.get("summary", {}).get("trade_count") is not None or current.get("summary", {}).get("candidate_buckets") is not None
    )
    extended_evidence_available = not extended.get("_missing") and (
        extended.get("summary", {}).get("trade_count") is not None or extended.get("summary", {}).get("candidate_buckets") is not None
    )
    evidence_available = current_evidence_available and extended_evidence_available
    meaningful_extended = [
        row
        for row in extended_buckets
        if str(row.get("group", "")).endswith("::1")
        and safe_float(row.get("return_delta")) is not None
        and (safe_float(row.get("return_delta")) or 0) >= 0.005
        and int(row.get("trade_count") or 0) >= 20
    ]
    status = "PASS_TO_OFFLINE_ABLATION_WITH_CAUTION" if meaningful_extended else "MONITOR_ONLY_NOT_STABLE"
    return {
        "experiment_id": "model_exp_candidate_persistence_only",
        "status": status,
        "evidence_available": evidence_available,
        "metrics": {
            "evidence_available": evidence_available,
            "current_evidence_available": current_evidence_available,
            "extended_evidence_available": extended_evidence_available,
            "missing_evidence_reason": None if evidence_available else "candidate persistence current and extended ablation evidence are both required before resolving verdict",
            "current_trade_count": current.get("summary", {}).get("trade_count"),
            "current_candidate_buckets": current_buckets[:8],
            "extended_trade_count": extended.get("summary", {}).get("trade_count"),
            "extended_candidate_buckets": extended_buckets[:8],
            "meaningful_extended_bucket_count": len(meaningful_extended),
        },
        "notes": [
            "近期 window prior streak=1 看起來有正向，但 extended window 沒有穩定延續。",
            "暫不進模型訓練候選；保留為訊息/UI 脈絡或之後分盤勢再測。",
        ],
    }


def ready_manifest_decisions(run_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for run in run_manifest.get("runs", []):
        if run.get("experiment_id") != "model_exp_candidate_persistence_only":
            continue
        if run.get("execution_status") != "READY_FOR_FEATURE_ABLATION":
            continue
        rows.append(
            {
                "experiment_id": run.get("experiment_id"),
                "status": "READY_TO_OFFLINE_ABLATION",
                "metrics": {
                    "materialized_features": run.get("materialized_features", {}),
                    "planned_columns": run.get("planned_columns", []),
                },
                "notes": [
                    "materializer 已補上，但這只代表可以測，不代表可以 promote。",
                    "下一步是離線 ablation + replay，不能直接進正式模型。",
                ],
            }
        )
    return rows


def blocked_decisions(run_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for run in run_manifest.get("runs", []):
        status = str(run.get("execution_status") or "")
        if status.startswith("BLOCKED") or status == "WAIT_FOR_INDIVIDUAL_PASS":
            rows.append(
                {
                    "experiment_id": run.get("experiment_id"),
                    "status": status,
                    "reason": run.get("reason"),
                    "required_before_execute": run.get("required_before_execute", []),
                }
            )
    return rows


def verdict_from_status(status: str) -> str:
    if status == "PASS_TO_PROMOTION_REVIEW_QUEUE":
        return "passed"
    if status in {"MONITOR_ONLY_WEAK_MODEL_UPLIFT", "MONITOR_ONLY_NOT_STABLE", "MONITOR_ONLY"}:
        return "failed"
    if status in {"PASS_TO_LONGER_REPLAY", "PASS_TO_OFFLINE_ABLATION_WITH_CAUTION", "PASS_TO_MODEL_EXP_02"}:
        return "partial"
    return "pending"


def next_action_from_status(status: str) -> str:
    mapping = {
        "PASS_TO_PROMOTION_REVIEW_QUEUE": "human_promotion_review_with_existing_gates",
        "PASS_TO_LONGER_REPLAY": "collect_longer_replay_evidence",
        "PASS_TO_OFFLINE_ABLATION_WITH_CAUTION": "run_offline_ablation_and_replay",
        "PASS_TO_MODEL_EXP_02": "run_sealed_oos_and_replay",
        "READY_TO_OFFLINE_ABLATION": "run_offline_ablation_before_verdict",
        "WAIT_FOR_INDIVIDUAL_PASS": "wait_for_individual_experiments",
    }
    if status.startswith("BLOCKED"):
        return "resolve_blocker_before_verdict"
    if status.startswith("MONITOR_ONLY"):
        return "record_failed_or_monitor_only_result"
    return mapping.get(status, "manual_review")


def has_actual_evidence(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return any(has_actual_evidence(item) for item in value)
    if isinstance(value, dict):
        return any(has_actual_evidence(child) for child in value.values())
    return False


def enrich_ledger_fields(decisions: list[dict[str, Any]], run_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    runs = {item.get("experiment_id"): item for item in run_manifest.get("runs", [])}
    enriched = []
    for decision in decisions:
        run = runs.get(decision.get("experiment_id"), {})
        ledger = run.get("ledger", {})
        status = str(decision.get("status") or "")
        actual_metrics = decision.get("metrics") or {"status": status, "reason": decision.get("reason")}
        verdict = verdict_from_status(status)
        next_action = next_action_from_status(status)
        explicit_evidence = decision.get("evidence_available")
        if explicit_evidence is None and isinstance(actual_metrics, dict):
            explicit_evidence = actual_metrics.get("evidence_available")
        evidence_available = bool(explicit_evidence) if explicit_evidence is not None else has_actual_evidence(actual_metrics)
        if verdict in {"passed", "failed", "partial"} and not evidence_available:
            verdict = "pending"
            next_action = "collect_required_evidence_before_verdict"
        enriched.append(
            {
                **decision,
                "ledger_id": run.get("ledger_id") or ledger.get("id"),
                "hypothesis": ledger.get("hypothesis"),
                "baseline": ledger.get("baseline"),
                "decision_policy": ledger.get("decision_policy"),
                "actual_metrics": actual_metrics,
                "evidence_available": evidence_available,
                "verdict": verdict,
                "next_action": next_action,
                "promotion_allowed": False,
            }
        )
    return enriched


def sync_ledger_from_report(payload: dict[str, Any], ledger_path: Path, report_path: Path) -> dict[str, Any]:
    ledger = ledger_lib.load_ledger(ledger_path)
    updates: list[dict[str, Any]] = []
    for decision in payload.get("decisions", []):
        ledger_id = decision.get("ledger_id")
        if not ledger_id:
            updates.append({"experiment_id": decision.get("experiment_id"), "status": "missing_ledger_id"})
            continue
        verdict = decision.get("verdict")
        if verdict == "pending":
            trigger_date = payload.get("date")
            ok, status = ledger_lib.reschedule_entry(
                ledger,
                str(ledger_id),
                trigger_date=str(trigger_date),
                reason=str(decision.get("next_action")),
            )
        else:
            ok, status = ledger_lib.resolve_entry(
                ledger,
                str(ledger_id),
                str(verdict),
                result_report=repo_path(report_path),
                actual_metrics=decision.get("actual_metrics") or {"status": decision.get("status")},
                reason=str(decision.get("next_action")),
            )
        updates.append({"ledger_id": ledger_id, "status": status, "ok": ok, "verdict": verdict})
    checks = ledger_lib.validate_ledger_payload(ledger)
    failed = [item for item in checks if not item["ok"]]
    failed_updates = [item for item in updates if item.get("ok") is False or item.get("status") in {"missing_ledger_id", "missing_id"}]
    if not failed and not failed_updates:
        ledger_lib.atomic_write_json(ledger_path, ledger)
    return {
        "status": "OK" if not failed and not failed_updates else "FAILED",
        "ledger": repo_path(ledger_path),
        "updates": updates,
        "failed_updates": failed_updates,
        "failed_checks": [item["name"] for item in failed[:10]],
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    run_path = resolve_path(args.run_manifest) or default_path(args, "run_manifest")
    portfolio_path = resolve_path(args.portfolio_comparison) or default_path(args, "portfolio_comparison")
    portfolio_extended_path = resolve_path(args.portfolio_comparison_extended) or default_path(args, "portfolio_comparison_extended")
    regime_path = resolve_path(args.regime_ablation) or default_path(args, "regime_ablation")
    regime_offline_path = resolve_path(args.regime_offline_ablation) or default_path(args, "regime_offline_ablation")
    candidate_path = resolve_path(args.candidate_persistence_ablation) or default_path(args, "candidate_persistence_ablation")
    candidate_extended_path = resolve_path(args.candidate_persistence_ablation_extended) or default_path(args, "candidate_persistence_ablation_extended")
    run_manifest = load_json(run_path)
    portfolio = load_json(portfolio_path)
    portfolio_extended = load_json(portfolio_extended_path)
    regime = load_json(regime_path)
    regime_offline = load_json(regime_offline_path)
    candidate = load_json(candidate_path)
    candidate_extended = load_json(candidate_extended_path)
    candidate_decision = candidate_persistence_decision(candidate, candidate_extended)
    decisions = [
        portfolio_decision(portfolio, portfolio_extended),
        regime_decision(regime, regime_offline),
        *([candidate_decision] if candidate_decision else ready_manifest_decisions(run_manifest)),
        *blocked_decisions(run_manifest),
    ]
    decisions = enrich_ledger_fields(decisions, run_manifest)
    promote = [
        item["experiment_id"]
        for item in decisions
        if item.get("status") in {"PASS_TO_LONGER_REPLAY", "PASS_TO_PROMOTION_REVIEW_QUEUE", "PASS_TO_OFFLINE_ABLATION_WITH_CAUTION", "PASS_TO_MODEL_EXP_02", "READY_TO_OFFLINE_ABLATION"}
    ]
    blocked = [item["experiment_id"] for item in decisions if str(item.get("status", "")).startswith("BLOCKED")]
    waiting = [item["experiment_id"] for item in decisions if item.get("status") == "WAIT_FOR_INDIVIDUAL_PASS"]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK" if not any(item.get("_missing") for item in [run_manifest, portfolio, regime]) else "WARN",
        "contract": {
            "research_only": True,
            "reads_model_experiment_artifacts_only": True,
            "does_not_train_model": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_risk_adjusted_score": True,
            "does_not_change_production_ranking": True,
            "production_promotion_allowed": False,
        },
        "inputs": {
            "run_manifest": repo_path(run_path),
            "portfolio_comparison": repo_path(portfolio_path),
            "portfolio_comparison_extended": repo_path(portfolio_extended_path),
            "regime_ablation": repo_path(regime_path),
            "regime_offline_ablation": repo_path(regime_offline_path),
            "candidate_persistence_ablation": repo_path(candidate_path),
            "candidate_persistence_ablation_extended": repo_path(candidate_extended_path),
        },
        "summary": {
            "pass_to_next": promote,
            "blocked": blocked,
            "waiting": waiting,
            "next_missing_piece": "candidate_persistence materializer" if "model_exp_candidate_persistence_only" in blocked else None,
            "ledger_resolver_status": "PENDING_WRITE",
        },
        "decisions": decisions,
    }


def pct(value: Any) -> str:
    parsed = safe_float(value)
    if parsed is None:
        return "--"
    return f"{parsed:.2%}"


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# MODEL-EXP-01 Result Report",
        "",
        f"- status：`{payload['status']}`",
        f"- date：`{payload['date']}`",
        f"- pass_to_next：`{payload['summary']['pass_to_next']}`",
        f"- blocked：`{payload['summary']['blocked']}`",
        "",
        "| Experiment | Status | Note |",
        "|---|---|---|",
    ]
    for item in payload["decisions"]:
        note = item.get("reason") or "；".join(item.get("notes", [])[:1])
        lines.append(f"| {item['experiment_id']} | {item['status']} | {note} |")
    lines.append("")
    return "\n".join(lines)


def self_test_cases() -> dict[str, bool]:
    with tempfile.TemporaryDirectory(prefix="top10-result-resolver-") as tmp:
        ledger_path = Path(tmp) / "ledger.json"
        report_path = Path(tmp) / "model_exp_result_report_2026-01-05.json"
        payload = {
            "date": "2026-01-05",
            "decisions": [
                {
                    "experiment_id": "model_exp_missing_ledger",
                    "ledger_id": None,
                    "status": "PASS_TO_LONGER_REPLAY",
                    "verdict": "passed",
                    "next_action": "sync evidence",
                    "actual_metrics": {"sealed_top10_return_uplift": 0.003},
                }
            ],
        }
        result = sync_ledger_from_report(payload, ledger_path, report_path)
    missing_regime_decision = regime_decision({"_missing": True}, {"_missing": True})
    enriched_missing_regime = enrich_ledger_fields([missing_regime_decision], {"runs": []})[0]
    missing_extended_candidate = candidate_persistence_decision(
        {"summary": {"trade_count": 10, "candidate_buckets": [{"group": "5D::1", "return_delta": 0.01, "trade_count": 20}]}},
        {"_missing": True},
    )
    enriched_missing_extended = enrich_ledger_fields([missing_extended_candidate], {"runs": []})[0] if missing_extended_candidate else {}
    return {
        "missing_ledger_id_marks_resolver_failed": result["status"] == "FAILED",
        "missing_ledger_id_recorded_as_failed_update": any(item.get("status") == "missing_ledger_id" for item in result["failed_updates"]),
        "missing_regime_evidence_stays_pending": enriched_missing_regime["verdict"] == "pending"
        and enriched_missing_regime["next_action"] == "collect_required_evidence_before_verdict",
        "missing_candidate_extended_evidence_stays_pending": enriched_missing_extended.get("verdict") == "pending"
        and enriched_missing_extended.get("next_action") == "collect_required_evidence_before_verdict",
    }


def run_self_test() -> int:
    checks = self_test_cases()
    status = "OK" if all(checks.values()) else "FAILED"
    print(json.dumps({"schema_version": f"{SCHEMA_VERSION}-self-test", "status": status, "checks": checks}, ensure_ascii=False, sort_keys=True))
    return 0 if status == "OK" else 1


def main() -> int:
    args = parse_args()
    if args.self_test:
        return run_self_test()
    payload = build_report(args)
    output = resolve_path(args.output) or MODEL_EXPERIMENTS_DIR / f"model_exp_result_report_{args.date}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    ledger_sync = {"status": "SKIPPED", "updates": [], "failed_checks": []}
    ledger_path = resolve_path(args.ledger)
    if ledger_path is None:
        raise RuntimeError("ledger path resolution failed")
    if not args.no_ledger_update:
        ledger_sync = sync_ledger_from_report(payload, ledger_path, output)
    payload["summary"]["ledger_resolver_status"] = ledger_sync["status"]
    payload["ledger_resolver"] = ledger_sync
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output), **payload["summary"]}, ensure_ascii=False))
    return 0 if payload["status"] in {"OK", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
