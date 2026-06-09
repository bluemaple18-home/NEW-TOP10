#!/usr/bin/env python3
"""驗證 guarded Top10 performance backtest research artifact。"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "guarded-top10-performance-backtest.v1"
REQUIRED_WINDOWS = ("recent_100", "recent_6m")
REQUIRED_HORIZONS = {"1", "3", "5", "10"}
ALLOWED_DECISIONS = {
    "GUARDED_OUTPERFORMS_RESEARCH_ONLY",
    "MIXED_MONITOR_ONLY",
    "GUARDED_UNDERPERFORMS",
    "INSUFFICIENT_DATA",
}
REPLAY_FILENAME_PATTERN = re.compile(r"^guarded_top10_replay_(\d{4}-\d{2}-\d{2})\.json$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify guarded Top10 performance artifacts")
    parser.add_argument("--artifact", action="append", default=[], help="指定 artifact；未指定時驗 latest recent_100/recent_6m")
    parser.add_argument("--artifacts-dir", default="artifacts/research")
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def latest_for_window(artifacts_dir: Path, window: str) -> Path:
    files = sorted(artifacts_dir.glob(f"guarded_top10_performance_{window}_????-??-??.json"))
    if not files:
        raise FileNotFoundError(f"找不到 {window} performance artifact")
    return files[-1]


def main() -> int:
    args = parse_args()
    artifacts = [resolve_path(path) for path in args.artifact]
    if not artifacts:
        artifacts_dir = resolve_path(args.artifacts_dir)
        artifacts = [latest_for_window(artifacts_dir, window) for window in REQUIRED_WINDOWS]
    results = [{"artifact": repo_path(path), "errors": verify(path)} for path in artifacts]
    errors = [error for result in results for error in result["errors"]]
    status = "OK" if not errors else "FAILED"
    print(json.dumps({"status": status, "results": results}, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


def verify(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        return [f"artifact missing: {path}"]
    text = path.read_text(encoding="utf-8")
    if "PROMOTION_READY" in text:
        errors.append("artifact must not contain PROMOTION_READY")
    if "total_compounded_bucket_return" in text:
        errors.append("overlapping horizon compound must use overlapping_bucket_compound_proxy naming")
    payload = json.loads(text)
    contract = payload.get("contract", {})
    outputs = payload.get("outputs", {})
    decision = payload.get("decision", {})
    summary = payload.get("summary", {})
    inputs = payload.get("inputs", {})
    production_baseline = payload.get("production_baseline", {})
    window = payload.get("window") if isinstance(payload.get("window"), dict) else {}

    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if contract.get("research_only") is not True:
        errors.append("contract.research_only must be true")
    if contract.get("performance_backtest") is not True:
        errors.append("contract.performance_backtest must be true")
    if int(contract.get("candidate_pool_size") or 0) != 80:
        errors.append("contract.candidate_pool_size must be 80")
    for key in ("does_not_train_model", "does_not_write_models_latest_lgbm", "does_not_change_production_ranking", "does_not_change_publish_source"):
        if contract.get(key) is not True:
            errors.append(f"contract.{key} must be true")
    if decision.get("promotion_ready") is not False:
        errors.append("decision.promotion_ready must be false")
    if decision.get("status") not in ALLOWED_DECISIONS:
        errors.append(f"decision.status not allowed: {decision.get('status')}")
    if inputs.get("window") not in REQUIRED_WINDOWS:
        errors.append("inputs.window must be recent_100 or recent_6m")
    json_output = str(outputs.get("json") or "")
    md_output = str(outputs.get("markdown") or "")
    if not json_output.startswith("artifacts/research/guarded_top10_performance_"):
        errors.append("json output must stay under artifacts/research")
    if not md_output.startswith("artifacts/research/guarded_top10_performance_"):
        errors.append("markdown output must stay under artifacts/research")
    if md_output and not (PROJECT_ROOT / md_output).exists():
        errors.append(f"markdown output missing: {md_output}")

    comparison = summary.get("comparison_by_horizon") or {}
    if set(comparison) != REQUIRED_HORIZONS:
        errors.append("comparison_by_horizon must include 1,3,5,10")
    production_dirs = set(inputs.get("production_dirs") or [])
    if not production_dirs:
        errors.append("inputs.production_dirs must record source allowlist")
    source_by_date = production_baseline.get("production_source_by_date") or {}
    source_counts = production_baseline.get("source_counts") or {}
    if not source_by_date:
        errors.append("production_baseline.production_source_by_date missing")
    if not source_counts:
        errors.append("production_baseline.source_counts missing")
    if production_baseline.get("overlap_policy") != "later production-dir overrides earlier production-dir for the same ranking date":
        errors.append("production_baseline.overlap_policy missing or unexpected")
    comparable_dates = window.get("comparable_dates") if isinstance(window.get("comparable_dates"), list) else []
    if not comparable_dates:
        errors.append("window.comparable_dates must be non-empty")
    selected_dates = window.get("selected_dates") if isinstance(window.get("selected_dates"), list) else []
    if selected_dates and not set(comparable_dates) <= set(selected_dates):
        errors.append("window.comparable_dates must be a subset of selected_dates")
    for date_text in comparable_dates:
        if str(date_text) not in source_by_date:
            errors.append(f"production source missing for comparable date: {date_text}")
    for date_text, source in source_by_date.items():
        if not any(str(source).startswith(f"{directory}/") for directory in production_dirs):
            errors.append(f"production source for {date_text} is outside allowlist: {source}")
    for variant in ("production", "guarded"):
        body = summary.get(variant) or {}
        by_horizon = body.get("by_horizon") or {}
        if set(by_horizon.keys()) != REQUIRED_HORIZONS:
            errors.append(f"{variant}.by_horizon must include 1,3,5,10")
        for horizon, row in by_horizon.items():
            if "overlapping_bucket_compound_proxy" not in row:
                errors.append(f"{variant}.by_horizon.{horizon}.overlapping_bucket_compound_proxy missing")
            if "total_compounded_bucket_return" in row:
                errors.append(f"{variant}.by_horizon.{horizon}.total_compounded_bucket_return must not be used")
        if "turnover" not in body:
            errors.append(f"{variant}.turnover missing")
        if "concentration" not in body:
            errors.append(f"{variant}.concentration missing")
        if "regime_slice" not in body:
            errors.append(f"{variant}.regime_slice missing")
    for horizon, row in comparison.items():
        if "guarded_minus_production_overlapping_bucket_compound_proxy" not in row:
            errors.append(f"comparison_by_horizon.{horizon}.overlapping compound proxy delta missing")
        if "guarded_minus_production_total_compounded_bucket_return" in row:
            errors.append(f"comparison_by_horizon.{horizon}.old compound delta must not be used")
    for key in ("guarded_added_vs_removed_performance", "guard_hit_quality"):
        if key not in summary:
            errors.append(f"summary.{key} missing")
    if int(window.get("comparable_date_count") or 0) <= 0:
        errors.append("comparable_date_count must be positive")
    if comparable_dates and int(window.get("comparable_date_count") or 0) != len(comparable_dates):
        errors.append("comparable_date_count must match len(comparable_dates)")
    comparable_date_texts = [str(date_text) for date_text in comparable_dates]
    comparable_date_set = set(comparable_date_texts)
    replay_dates: list[str] = []
    for replay_output in payload.get("guarded_replay_outputs") or []:
        replay_path = PROJECT_ROOT / replay_output
        replay_date = replay_date_from_path(replay_output)
        if replay_date is None:
            errors.append(f"guarded replay output filename must include date: {replay_output}")
        else:
            replay_dates.append(replay_date)
            if comparable_dates and replay_date not in comparable_date_set:
                errors.append(f"guarded replay output date is not comparable: {replay_output}")
        if not replay_path.exists():
            errors.append(f"guarded replay output missing: {replay_output}")
            continue
        replay_payload = json.loads(replay_path.read_text(encoding="utf-8"))
        if replay_date is not None and replay_payload.get("ranking_date") != replay_date:
            errors.append(f"guarded replay ranking_date mismatch for {replay_output}: {replay_payload.get('ranking_date')}")
        boundary = replay_payload.get("regime_history_boundary") or {}
        if boundary.get("future_rows_after_target") != 0:
            errors.append(f"guarded replay output has future regime history rows: {replay_output}")
        if not boundary.get("end_date"):
            errors.append(f"guarded replay output missing regime_history_boundary.end_date: {replay_output}")
        elif replay_date is not None and boundary.get("end_date") != replay_date:
            errors.append(f"guarded replay output end_date mismatch for {replay_output}: {boundary.get('end_date')}")
    if comparable_dates and sorted(replay_dates) != sorted(comparable_date_texts):
        errors.append("guarded replay output dates must match window.comparable_dates")
    return errors


def replay_date_from_path(value: str) -> str | None:
    match = REPLAY_FILENAME_PATTERN.fullmatch(Path(value).name)
    return match.group(1) if match else None


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
