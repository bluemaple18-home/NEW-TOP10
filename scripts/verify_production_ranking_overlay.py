#!/usr/bin/env python3
"""驗證正式 ranking K overlay 邊界。

這個 verifier 只讀 ranking artifacts，不訓練模型、不重跑 ranking。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify production ranking overlay artifacts")
    parser.add_argument("--mode", choices=["default-off", "enabled-artifact"], default="default-off")
    parser.add_argument("--date", default=None)
    parser.add_argument("--artifacts-dir", default="artifacts")
    parser.add_argument("--config", default="config/signals.yaml")
    parser.add_argument("--expected-keep", type=int, default=9)
    parser.add_argument("--expected-comparison-keep", type=int, default=8)
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, value: Any = None) -> None:
    checks.append({"name": name, "ok": bool(ok), "value": value})


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path, encoding="utf-8-sig")
    if "stock_id" in frame.columns:
        frame["stock_id"] = frame["stock_id"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(4)
    return frame


def ids(frame: pd.DataFrame) -> list[str]:
    if frame.empty or "stock_id" not in frame.columns:
        return []
    return [str(value).zfill(4) for value in frame["stock_id"].head(10).tolist()]


def verify_default_off(config_path: Path) -> int:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    overlay = config.get("production_ranking_overlay") if isinstance(config, dict) else {}
    overlay = overlay if isinstance(overlay, dict) else {}
    checks: list[dict[str, Any]] = []
    add_check(checks, "config_exists", config_path.exists(), str(config_path))
    add_check(checks, "enabled_default_false", overlay.get("enabled") is False, overlay)
    add_check(checks, "promotion_review_approved_false", overlay.get("promotion_review_approved") is False, overlay)
    failed = [check for check in checks if not check["ok"]]
    print(json.dumps({"status": "FAILED" if failed else "OK", "mode": "default-off", "checks": checks}, ensure_ascii=False, indent=2))
    return 1 if failed else 0


def main() -> int:
    args = parse_args()
    if args.mode == "default-off":
        return verify_default_off(resolve_path(args.config))

    if not args.date:
        raise SystemExit("--date is required when --mode enabled-artifact")
    artifacts_dir = resolve_path(args.artifacts_dir)
    ranking_path = artifacts_dir / f"ranking_{args.date}.csv"
    baseline_path = artifacts_dir / f"baseline_ranking_{args.date}.csv"
    comparison_path = artifacts_dir / f"ranking_comparison_{args.date}.json"
    k8_path = artifacts_dir / f"ranking_comparison_k{args.expected_comparison_keep}_{args.date}.csv"

    ranking = read_csv(ranking_path)
    baseline = read_csv(baseline_path)
    k8 = read_csv(k8_path)
    comparison = json.loads(comparison_path.read_text(encoding="utf-8")) if comparison_path.exists() else {}
    ranking_ids = ids(ranking)
    baseline_ids = ids(baseline)
    k8_ids = ids(k8)
    checks: list[dict[str, Any]] = []

    add_check(checks, "ranking_exists", ranking_path.exists(), str(ranking_path))
    add_check(checks, "baseline_exists", baseline_path.exists(), str(baseline_path))
    add_check(checks, "comparison_json_exists", comparison_path.exists(), str(comparison_path))
    add_check(checks, "k8_comparison_exists", k8_path.exists(), str(k8_path))
    add_check(checks, "ranking_top10_count", len(ranking_ids) == 10, ranking_ids)
    add_check(checks, "baseline_top10_count", len(baseline_ids) == 10, baseline_ids)
    add_check(checks, "k9_keeps_top9", ranking_ids[: args.expected_keep] == baseline_ids[: args.expected_keep], ranking_ids[: args.expected_keep])
    add_check(checks, "k9_changes_at_most_one", len(set(ranking_ids) - set(baseline_ids)) <= 1, ranking_ids)
    add_check(checks, "overlay_source_column", "production_overlay_source" in ranking.columns, list(ranking.columns))
    add_check(
        checks,
        "shadow_fill_count",
        int((ranking.get("production_overlay_source", pd.Series(dtype=str)) == "shadow_fill").sum()) <= 1,
        ranking.get("production_overlay_source", pd.Series(dtype=str)).tolist(),
    )
    add_check(checks, "k8_keeps_top8", k8_ids[: args.expected_comparison_keep] == baseline_ids[: args.expected_comparison_keep], k8_ids[: args.expected_comparison_keep])
    add_check(checks, "comparison_schema", comparison.get("schema_version") == "production-ranking-overlay.v1", comparison.get("schema_version"))
    add_check(checks, "comparison_official_variant", comparison.get("contract", {}).get("official_ranking_variant") == f"k{args.expected_keep}", comparison.get("contract"))
    add_check(checks, "comparison_model_not_changed", comparison.get("contract", {}).get("model_changed") is False, comparison.get("contract"))
    add_check(checks, "comparison_push_not_changed", comparison.get("contract", {}).get("push_changed") is False, comparison.get("contract"))

    failed = [check for check in checks if not check["ok"]]
    print(json.dumps({"status": "FAILED" if failed else "OK", "checks": checks}, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
