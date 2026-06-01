#!/usr/bin/env python3
"""建立 revenue 缺口下的 technical-only training lane artifact。

此 artifact 只把資料降級變成機器可讀契約；不改 feature frame、不重訓模型、
不降低 sealed/replay/promotion 門檻。
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
MODEL_EXPERIMENTS_DIR = ARTIFACTS_DIR / "model_experiments"
SCHEMA_VERSION = "technical-only-training-lane.v1"
REVENUE_FEATURES = ("revenue_yoy", "revenue_mom")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build technical-only training lane artifact")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument("--model-health", default="artifacts/model_health_report_latest.json")
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
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def feature_coverage(features_path: Path) -> dict[str, dict[str, Any]]:
    if not features_path.exists():
        raise FileNotFoundError(f"features parquet 不存在：{features_path}")
    columns = ["date", "stock_id", *REVENUE_FEATURES]
    frame = pd.read_parquet(features_path, columns=columns)
    rows = int(len(frame))
    coverage: dict[str, dict[str, Any]] = {}
    for feature in REVENUE_FEATURES:
        non_null = int(pd.to_numeric(frame[feature], errors="coerce").notna().sum()) if feature in frame.columns else 0
        coverage[feature] = {
            "exists": feature in frame.columns,
            "non_null_rows": non_null,
            "total_rows": rows,
            "coverage_ratio": round(non_null / rows, 6) if rows else None,
        }
    return coverage


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    features_path = resolve_path(args.features)
    health_path = resolve_path(args.model_health)
    if features_path is None or health_path is None:
        raise RuntimeError("path resolution failed")
    health = load_json(health_path)
    baseline = health.get("baseline") if isinstance(health.get("baseline"), dict) else {}
    skipped = [str(item) for item in baseline.get("skipped_empty_model_features") or []]
    missing_revenue = [feature for feature in REVENUE_FEATURES if feature in skipped]
    coverage = feature_coverage(features_path)
    all_revenue_empty = all((coverage[feature]["non_null_rows"] or 0) == 0 for feature in REVENUE_FEATURES)
    status = "RESEARCH_ONLY_ALLOWED" if set(missing_revenue) == set(REVENUE_FEATURES) and all_revenue_empty else "BLOCKED"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": status,
        "chosen_path": "technical_only_lane",
        "contract": {
            "research_only_allowed": status == "RESEARCH_ONLY_ALLOWED",
            "production_promotion_allowed": False,
            "does_not_drop_model_features_silently": True,
            "does_not_modify_feature_frame": True,
            "does_not_train_model": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_risk_adjusted_score": True,
            "does_not_change_production_ranking": True,
            "sealed_replay_acceptance_still_required": True,
            "promotion_requires_explicit_degradation_acceptance": True,
        },
        "inputs": {
            "features": repo_path(features_path),
            "model_health": repo_path(health_path),
        },
        "evidence": {
            "revenue_feature_coverage": coverage,
            "model_health_status": health.get("status"),
            "model_feature_count": baseline.get("model_feature_count"),
            "monitored_model_feature_count": baseline.get("monitored_model_feature_count"),
            "coverage_ratio": baseline.get("coverage_ratio"),
            "skipped_empty_model_features": skipped,
        },
        "lane_policy": {
            "excluded_from_monitorable_baseline": missing_revenue,
            "allowed_scope": "research/readiness only",
            "forbidden_scope": [
                "production promotion",
                "auto retrain enablement",
                "silent model feature drop",
                "lowering sealed/replay/acceptance gates",
            ],
            "required_before_promotion": [
                "補齊 revenue_yoy/revenue_mom 可監控 baseline，或",
                "在下一輪 sealed/replay/acceptance 中明確接受 technical-only degradation，且仍需人工 promotion review",
            ],
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    coverage = payload["evidence"]["revenue_feature_coverage"]
    lines = [
        "# Technical-only Training Lane",
        "",
        f"- status：`{payload['status']}`",
        f"- chosen_path：`{payload['chosen_path']}`",
        f"- production_promotion_allowed：`{payload['contract']['production_promotion_allowed']}`",
        "",
        "| Feature | Non-null Rows | Total Rows | Coverage |",
        "|---|---:|---:|---:|",
    ]
    for feature, row in coverage.items():
        ratio = row.get("coverage_ratio")
        lines.append(f"| {feature} | {row.get('non_null_rows')} | {row.get('total_rows')} | {ratio} |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    output = resolve_path(args.output) or MODEL_EXPERIMENTS_DIR / f"technical_only_training_lane_{args.date}.json"
    payload = build_payload(args)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "output": repo_path(output),
                "chosen_path": payload["chosen_path"],
                "production_promotion_allowed": payload["contract"]["production_promotion_allowed"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if payload["status"] == "RESEARCH_ONLY_ALLOWED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
