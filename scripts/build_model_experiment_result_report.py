#!/usr/bin/env python3
"""彙整 MODEL-EXP-01 已執行測試結果。

此腳本只讀 model_experiments artifacts，產生研究結論報告。
不訓練模型、不改 ranking、不做 production promotion。
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_EXPERIMENTS_DIR = PROJECT_ROOT / "artifacts" / "model_experiments"
SCHEMA_VERSION = "model-experiment-result-report.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build MODEL-EXP-01 result report")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--run-manifest", default=None)
    parser.add_argument("--portfolio-comparison", default=None)
    parser.add_argument("--regime-ablation", default=None)
    parser.add_argument("--candidate-persistence-ablation", default=None)
    parser.add_argument("--candidate-persistence-ablation-extended", default=None)
    parser.add_argument("--output", default=None)
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
        "regime_ablation": MODEL_EXPERIMENTS_DIR / f"model_exp_regime_feature_group_ablation_{args.date}.json",
        "candidate_persistence_ablation": MODEL_EXPERIMENTS_DIR / f"candidate_persistence_materialized_ablation_{args.date}.json",
        "candidate_persistence_ablation_extended": MODEL_EXPERIMENTS_DIR / f"candidate_persistence_materialized_ablation_extended_{args.date}.json",
    }
    return mapping[name]


def portfolio_decision(payload: dict[str, Any]) -> dict[str, Any]:
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
    passed = (
        return_delta is not None
        and return_delta > 0
        and dd_delta is not None
        and dd_delta > 0
        and score_delta is not None
        and score_delta > 0
    )
    return {
        "experiment_id": "model_exp_portfolio_risk_overlay_only",
        "status": "PASS_TO_LONGER_REPLAY" if passed else "MONITOR_ONLY",
        "metrics": {
            "current_best": current,
            "overlay_best": overlay,
            "delta_total_return": return_delta,
            "delta_max_drawdown": dd_delta,
            "delta_score": score_delta,
        },
        "notes": [
            "這是 post-ranking overlay/replay track，不是 LightGBM feature。",
            "下一步應擴大 rolling window，確認不是近期盤勢特化。",
        ],
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


def regime_decision(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary", {})
    top = top_shadow_features(payload)
    thin_regime_rows = [row for row in top if int(row.get("days") or 0) < 20]
    stable_rows = [row for row in top if int(row.get("days") or 0) >= 20]
    status = "PASS_TO_OFFLINE_ABLATION_WITH_CAUTION" if top else "MONITOR_ONLY"
    return {
        "experiment_id": "model_exp_regime_feature_group_ablation",
        "status": status,
        "metrics": {
            "feature_count": summary.get("feature_count"),
            "metric_rows": summary.get("metric_rows"),
            "candidate_metric_rows": summary.get("candidate_metric_rows"),
            "top_shadow_features": top,
            "thin_regime_top_count": len(thin_regime_rows),
            "stable_window_top_count": len(stable_rows),
        },
        "notes": [
            "PANIC_SELLING top signals 樣本天數偏少，不能直接視為穩定訊號。",
            "優先用 stable-window rows 做第一輪 feature ablation；薄樣本 regime 只當觀察。",
        ],
    }


def candidate_persistence_decision(current: dict[str, Any], extended: dict[str, Any]) -> dict[str, Any] | None:
    if current.get("_missing") and extended.get("_missing"):
        return None
    current_buckets = current.get("summary", {}).get("candidate_buckets", [])
    extended_buckets = extended.get("summary", {}).get("candidate_buckets", [])
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
        "metrics": {
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


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    run_path = resolve_path(args.run_manifest) or default_path(args, "run_manifest")
    portfolio_path = resolve_path(args.portfolio_comparison) or default_path(args, "portfolio_comparison")
    regime_path = resolve_path(args.regime_ablation) or default_path(args, "regime_ablation")
    candidate_path = resolve_path(args.candidate_persistence_ablation) or default_path(args, "candidate_persistence_ablation")
    candidate_extended_path = resolve_path(args.candidate_persistence_ablation_extended) or default_path(args, "candidate_persistence_ablation_extended")
    run_manifest = load_json(run_path)
    portfolio = load_json(portfolio_path)
    regime = load_json(regime_path)
    candidate = load_json(candidate_path)
    candidate_extended = load_json(candidate_extended_path)
    candidate_decision = candidate_persistence_decision(candidate, candidate_extended)
    decisions = [
        portfolio_decision(portfolio),
        regime_decision(regime),
        *([candidate_decision] if candidate_decision else ready_manifest_decisions(run_manifest)),
        *blocked_decisions(run_manifest),
    ]
    promote = [
        item["experiment_id"]
        for item in decisions
        if item.get("status") in {"PASS_TO_LONGER_REPLAY", "PASS_TO_OFFLINE_ABLATION_WITH_CAUTION", "READY_TO_OFFLINE_ABLATION"}
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
            "regime_ablation": repo_path(regime_path),
            "candidate_persistence_ablation": repo_path(candidate_path),
            "candidate_persistence_ablation_extended": repo_path(candidate_extended_path),
        },
        "summary": {
            "pass_to_next": promote,
            "blocked": blocked,
            "waiting": waiting,
            "next_missing_piece": "candidate_persistence materializer" if "model_exp_candidate_persistence_only" in blocked else None,
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


def main() -> int:
    args = parse_args()
    payload = build_report(args)
    output = resolve_path(args.output) or MODEL_EXPERIMENTS_DIR / f"model_exp_result_report_{args.date}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output), **payload["summary"]}, ensure_ascii=False))
    return 0 if payload["status"] in {"OK", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
