#!/usr/bin/env python3
"""產生 SHADOW-01 候選特徵驗證 artifact。

此腳本只讀 feature gate 與既有研究 artifacts，整理哪些候選特徵可進下一階段
離線模型實驗。它不訓練模型、不改 ranking、不寫 production artifacts。
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
SCHEMA_VERSION = "shadow-feature-experiment.v1"
DEFAULT_CANDIDATES = [
    "candidate_persistence",
    "portfolio_risk_overlay",
    "regime_feature_group_ablation",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build SHADOW-01 feature experiment artifacts")
    parser.add_argument("--gate", default=None, help="feature experiment gate JSON；未指定時讀最新 artifacts/feature_experiment_gate_*.json")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--artifacts-dir", default="artifacts")
    parser.add_argument("--candidate", action="append", help="只產指定 candidate；可重複指定")
    parser.add_argument("--output-dir", default="artifacts")
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


def latest_existing(directory: Path, pattern: str) -> Path | None:
    matches = sorted(directory.glob(pattern))
    return matches[-1] if matches else None


def gate_path(args: argparse.Namespace, artifacts_dir: Path) -> Path | None:
    return resolve_path(args.gate) if args.gate else latest_existing(artifacts_dir, "feature_experiment_gate_????-??-??.json")


def artifact_ref_path(path_text: str | None, artifacts_dir: Path) -> Path | None:
    if not path_text:
        return None
    path = Path(path_text).expanduser()
    if path.is_absolute():
        return path
    if path.parts and path.parts[0] == "artifacts":
        return artifacts_dir.joinpath(*path.parts[1:])
    return PROJECT_ROOT / path


def safe_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def pct(value: Any) -> str:
    parsed = safe_float(value)
    if parsed is None:
        return "--"
    return f"{parsed:.2%}"


def evidence_payload(candidate: dict[str, Any], key: str, artifacts_dir: Path) -> tuple[Path | None, dict[str, Any]]:
    ref = candidate.get("evidence", {}).get(key)
    path = artifact_ref_path(ref.get("path"), artifacts_dir) if isinstance(ref, dict) else None
    return path, load_json(path)


def top_positive_buckets(summary: dict[str, Any], section: str, limit: int = 5) -> list[dict[str, Any]]:
    rows = []
    for bucket, metrics in summary.get(section, {}).items():
        avg_return = safe_float(metrics.get("avg_net_return"))
        trade_count = int(metrics.get("trade_count") or 0)
        if avg_return is None or avg_return <= 0:
            continue
        horizon, _, label = bucket.partition("::")
        rows.append(
            {
                "bucket": bucket,
                "horizon": horizon,
                "label": label,
                "trade_count": trade_count,
                "avg_net_return": avg_return,
                "hit_rate": safe_float(metrics.get("hit_rate")),
                "avg_mae": safe_float(metrics.get("avg_mae")),
                "avg_mfe": safe_float(metrics.get("avg_mfe")),
            }
        )
    return sorted(rows, key=lambda row: (row["avg_net_return"], row["trade_count"]), reverse=True)[:limit]


def candidate_persistence_summary(candidate: dict[str, Any], artifacts_dir: Path) -> dict[str, Any]:
    study_path, study = evidence_payload(candidate, "study", artifacts_dir)
    verify_path, verify = evidence_payload(candidate, "verification", artifacts_dir)
    summary = study.get("summary", {})
    positives = {
        "by_horizon_and_streak": top_positive_buckets(summary, "by_horizon_and_streak"),
        "by_rank_delta_direction": top_positive_buckets(summary, "by_rank_delta_direction"),
    }
    positive_count = sum(len(rows) for rows in positives.values())
    decision = "MODEL_EXP_CANDIDATE" if verify.get("status") == "OK" and positive_count > 0 else "MONITOR_ONLY"
    return {
        "decision": decision,
        "source_artifacts": {
            "study": repo_path(study_path),
            "verification": repo_path(verify_path),
        },
        "verification_status": verify.get("status"),
        "metrics": {
            "trade_count": summary.get("trade_count"),
            "positive_bucket_count": positive_count,
            "top_positive_buckets": positives,
        },
        "model_prep_notes": [
            "只可作離線模型實驗候選，不可直接加 ranking bonus。",
            "優先測 consecutive_ranked_days、streak_bucket、rank_delta_direction 的 as-of join。",
            "正報酬 bucket 樣本數偏小者需在 sealed OOS 另行降權或淘汰。",
        ],
    }


def best_scenarios(payload: dict[str, Any], limit: int = 5) -> list[dict[str, Any]]:
    rows = []
    for row in payload.get("scenarios", []):
        rows.append(
            {
                "scenario_id": row.get("scenario_id"),
                "horizon": row.get("horizon"),
                "total_return": safe_float(row.get("total_return")),
                "max_drawdown": safe_float(row.get("max_drawdown")),
                "win_rate": safe_float(row.get("win_rate")),
                "score": safe_float(row.get("score")),
                "max_group_exposure": row.get("max_group_exposure"),
                "trade_count": row.get("trade_count"),
            }
        )
    return sorted(rows, key=lambda row: row.get("score") if row.get("score") is not None else -999, reverse=True)[:limit]


def portfolio_risk_summary(candidate: dict[str, Any], artifacts_dir: Path) -> dict[str, Any]:
    matrix_path, matrix = evidence_payload(candidate, "strategy_matrix", artifacts_dir)
    verify_path, verify = evidence_payload(candidate, "portfolio_verification", artifacts_dir)
    top = best_scenarios(matrix)
    summary = matrix.get("summary", {})
    best = top[0] if top else {}
    decision = (
        "MODEL_EXP_CANDIDATE"
        if verify.get("status") == "OK" and safe_float(best.get("total_return")) and safe_float(best.get("total_return")) > 0
        else "MONITOR_ONLY"
    )
    return {
        "decision": decision,
        "source_artifacts": {
            "strategy_matrix": repo_path(matrix_path),
            "verification": repo_path(verify_path),
        },
        "verification_status": verify.get("status"),
        "metrics": {
            "scenario_count": summary.get("scenario_count"),
            "positive_return_count": summary.get("positive_return_count"),
            "negative_return_count": summary.get("negative_return_count"),
            "best_scenarios": top,
        },
        "model_prep_notes": [
            "只可作離線風控 overlay/feature 實驗，不可直接 suppress production ranking rows。",
            "優先測 group exposure、event exit、drawdown guard 對 5D/10D replay 的影響。",
            "需確認不提高集中度與 max drawdown 後，才可進 sealed OOS。",
        ],
    }


def top_feature_groups(payload: dict[str, Any], limit: int = 12) -> list[dict[str, Any]]:
    rows = []
    for row in payload.get("metrics", []):
        if row.get("status") != "SHADOW_CANDIDATE":
            continue
        rows.append(
            {
                "regime_label": row.get("regime_label"),
                "horizon": row.get("horizon"),
                "group": row.get("group"),
                "feature": row.get("feature"),
                "days": row.get("days"),
                "coverage": safe_float(row.get("coverage")),
                "ic_mean": safe_float(row.get("ic_mean")),
                "abs_ic_mean": safe_float(row.get("abs_ic_mean")),
                "direction_consistency": safe_float(row.get("ic_direction_consistency")),
                "t_stat": safe_float(row.get("ic_t_stat")),
                "spread_mean": safe_float(row.get("top_bottom_spread_mean")),
            }
        )
    return sorted(rows, key=lambda row: row.get("abs_ic_mean") or 0, reverse=True)[:limit]


def regime_feature_group_summary(candidate: dict[str, Any], artifacts_dir: Path) -> dict[str, Any]:
    ablation_path, ablation = evidence_payload(candidate, "ablation", artifacts_dir)
    verify_path, verify = evidence_payload(candidate, "verification", artifacts_dir)
    summary = ablation.get("summary", {})
    top = top_feature_groups(ablation)
    decision = "MODEL_EXP_CANDIDATE" if verify.get("status") == "OK" and top else "MONITOR_ONLY"
    return {
        "decision": decision,
        "source_artifacts": {
            "ablation": repo_path(ablation_path),
            "verification": repo_path(verify_path),
        },
        "verification_status": verify.get("status"),
        "metrics": {
            "feature_count": summary.get("feature_count"),
            "metric_rows": summary.get("metric_rows"),
            "candidate_metric_rows": summary.get("candidate_metric_rows"),
            "groups": summary.get("groups", []),
            "regimes": summary.get("regimes", []),
            "top_shadow_features": top,
        },
        "model_prep_notes": [
            "只可作 feature group selection，不可把 IC 結果直接轉成 production 權重。",
            "下一階段應依 regime 做離線模型 ablation，並比較含/不含候選欄位的 replay。",
            "fundamental group 目前多為資料不足，需和 blocked data backlog 分開處理。",
        ],
    }


def summarize_candidate(candidate: dict[str, Any], artifacts_dir: Path) -> dict[str, Any]:
    candidate_id = str(candidate.get("id"))
    if candidate_id == "candidate_persistence":
        result = candidate_persistence_summary(candidate, artifacts_dir)
    elif candidate_id == "portfolio_risk_overlay":
        result = portfolio_risk_summary(candidate, artifacts_dir)
    elif candidate_id == "regime_feature_group_ablation":
        result = regime_feature_group_summary(candidate, artifacts_dir)
    else:
        result = {
            "decision": "UNSUPPORTED",
            "source_artifacts": {},
            "verification_status": None,
            "metrics": {},
            "model_prep_notes": ["此 candidate 尚未定義 SHADOW-01 summarizer。"],
        }

    if candidate.get("shadow_status") != "READY_FOR_SHADOW":
        result["decision"] = "BLOCKED_BY_FEATURE_GATE"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidate_id": candidate_id,
        "candidate_label": candidate.get("label"),
        "status": "OK" if result["decision"] in {"MODEL_EXP_CANDIDATE", "MONITOR_ONLY"} else "BLOCKED",
        "decision": result["decision"],
        "contract": {
            "shadow_only": True,
            "reads_existing_artifacts_only": True,
            "does_not_train_model": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_risk_adjusted_score": True,
            "does_not_change_production_ranking": True,
        },
        "feature_gate": {
            "shadow_status": candidate.get("shadow_status"),
            "production_promotion_status": candidate.get("production_promotion_status"),
            "allowed_shadow_uses": candidate.get("allowed_shadow_uses", []),
            "blocked_production_uses": candidate.get("blocked_production_uses", []),
            "blockers": candidate.get("blockers", []),
            "promotion_requirements": candidate.get("promotion_requirements", []),
        },
        **result,
    }


def render_candidate(payload: dict[str, Any]) -> str:
    lines = [
        f"# Shadow Feature Experiment: {payload['candidate_id']}",
        "",
        f"- status：`{payload['status']}`",
        f"- decision：`{payload['decision']}`",
        f"- gate：`{payload['feature_gate']['shadow_status']}`",
        "",
        "## Contract",
        "",
    ]
    for key, value in payload["contract"].items():
        lines.append(f"- {key}：`{value}`")
    lines.extend(["", "## Evidence", ""])
    for key, value in payload.get("source_artifacts", {}).items():
        lines.append(f"- {key}：`{value}`")
    lines.extend(["", "## Model Prep Notes", ""])
    for item in payload.get("model_prep_notes", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def render_index(payload: dict[str, Any]) -> str:
    lines = [
        "# SHADOW-01 Feature Experiment Index",
        "",
        f"- status：`{payload['status']}`",
        f"- date：`{payload['date']}`",
        f"- production_promotion_allowed：`{payload['contract']['production_promotion_allowed']}`",
        "",
        "| Candidate | Status | Decision | Artifact |",
        "|---|---|---|---|",
    ]
    for row in payload["candidates"]:
        lines.append(f"| {row['candidate_id']} | {row['status']} | {row['decision']} | `{row['artifact']}` |")
    lines.append("")
    return "\n".join(lines)


def write_candidate(payload: dict[str, Any], output_dir: Path, run_date: str) -> dict[str, Any]:
    output = output_dir / f"shadow_feature_experiment_{payload['candidate_id']}_{run_date}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_candidate(payload), encoding="utf-8")
    return {
        "candidate_id": payload["candidate_id"],
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_path(output),
        "markdown": repo_path(output.with_suffix(".md")),
    }


def build_index(args: argparse.Namespace) -> dict[str, Any]:
    artifacts_dir = resolve_path(args.artifacts_dir) or ARTIFACTS_DIR
    output_dir = resolve_path(args.output_dir) or ARTIFACTS_DIR
    gate_file = gate_path(args, artifacts_dir)
    gate = load_json(gate_file)
    requested = set(args.candidate or DEFAULT_CANDIDATES)
    candidates = [
        candidate for candidate in gate.get("candidates", [])
        if candidate.get("id") in requested
    ]
    found = {candidate.get("id") for candidate in candidates}
    missing = sorted(requested - found)

    rows = []
    for candidate in candidates:
        payload = summarize_candidate(candidate, artifacts_dir)
        rows.append(write_candidate(payload, output_dir, args.date))

    status = "OK" if rows and not missing and all(row["status"] == "OK" for row in rows) else "WARN"
    index = {
        "schema_version": "shadow-feature-experiment-index.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": status,
        "contract": {
            "shadow_only": True,
            "reads_existing_artifacts_only": True,
            "does_not_train_model": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_risk_adjusted_score": True,
            "does_not_change_production_ranking": True,
            "production_promotion_allowed": False,
        },
        "inputs": {
            "feature_experiment_gate": repo_path(gate_file),
            "requested_candidates": sorted(requested),
        },
        "summary": {
            "candidate_count": len(rows),
            "model_exp_candidate": [row["candidate_id"] for row in rows if row["decision"] == "MODEL_EXP_CANDIDATE"],
            "monitor_only": [row["candidate_id"] for row in rows if row["decision"] == "MONITOR_ONLY"],
            "blocked": [row["candidate_id"] for row in rows if row["status"] != "OK"],
            "missing_requested": missing,
        },
        "candidates": rows,
    }
    output = output_dir / f"shadow_feature_experiment_{args.date}.json"
    output.write_text(json.dumps(index, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_index(index), encoding="utf-8")
    return index | {"_output": repo_path(output)}


def main() -> int:
    args = parse_args()
    payload = build_index(args)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "output": payload["_output"],
                **payload["summary"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if payload["status"] in {"OK", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
