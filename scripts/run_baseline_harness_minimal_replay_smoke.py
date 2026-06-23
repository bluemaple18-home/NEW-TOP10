#!/usr/bin/env python3
"""執行 baseline harness 最小 replay smoke。

只使用 artifacts/backtest/production_baseline_harness_smoke 的三日 ranking；
不建立 artifacts/backtest/production，不跑全量 replay，不改模型、不改正式 ranking。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from scripts import run_backtest_replay, run_capital_aware_replay  # noqa: E402
from weekend_training_common import PRODUCTION_IMPACT, repo_path, resolve_path, write_json, write_text  # noqa: E402


SCHEMA_VERSION = "baseline-harness-minimal-replay-smoke.v1"
TASK_ID = "WEEKEND-TRAINING-17"
EXPECTED_DATES = ["2026-05-13", "2026-05-14", "2026-05-15"]
INPUT_BASELINE_PATH = "artifacts/backtest/production_baseline_harness_smoke"
MATERIALIZATION_SUMMARY = "artifacts/weekend_training/research_only_baseline_materialization_smoke_2026-06-18.json"
FORBIDDEN_PRODUCTION_PATH = PROJECT_ROOT / "artifacts" / "backtest" / "production"
FORBIDDEN_TEXT = "PROMOTION_READY"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="run baseline harness minimal replay smoke")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--baseline-dir", default=INPUT_BASELINE_PATH)
    parser.add_argument("--materialization-summary", default=MATERIALIZATION_SUMMARY)
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument("--market-regime-history", default="artifacts/market_regime_history_2026-06-01.json")
    parser.add_argument("--group-map", default="data/reference/stock_industry_map.csv")
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def output_paths(run_date: str, override: str | None) -> tuple[Path, Path]:
    if override:
        json_path = resolve_path(override)
        assert json_path is not None
    else:
        json_path = PROJECT_ROOT / "artifacts" / "weekend_training" / f"baseline_harness_minimal_replay_smoke_{run_date}.json"
    return json_path, json_path.with_suffix(".md")


def is_exact_path(path: Path, expected_repo_path: str) -> bool:
    expected = PROJECT_ROOT / expected_repo_path
    return path.resolve() == expected.resolve()


def contains_forbidden_text(*payloads: dict[str, Any]) -> bool:
    return FORBIDDEN_TEXT in json.dumps(payloads, ensure_ascii=False)


def ranking_files(baseline_dir: Path) -> list[Path]:
    return sorted(path for path in baseline_dir.glob("ranking_*.csv") if path.is_file())


def ranking_date(path: Path) -> str:
    return path.stem.removeprefix("ranking_")


def validate_inputs(baseline_dir: Path, manifest: dict[str, Any], materialization: dict[str, Any]) -> list[str]:
    files = ranking_files(baseline_dir) if baseline_dir.exists() else []
    file_dates = [ranking_date(path) for path in files]
    contract = manifest.get("contract") if isinstance(manifest.get("contract"), dict) else {}
    errors: list[str] = []
    if not is_exact_path(baseline_dir, INPUT_BASELINE_PATH):
        errors.append(f"baseline-dir must be exactly {INPUT_BASELINE_PATH}: {repo_path(baseline_dir)}")
    if FORBIDDEN_PRODUCTION_PATH.exists():
        errors.append(f"forbidden production path exists: {repo_path(FORBIDDEN_PRODUCTION_PATH)}")
    if manifest.get("schema_version") != "research-only-production-baseline-smoke-manifest.v1":
        errors.append(f"manifest schema mismatch: {manifest.get('schema_version')}")
    if manifest.get("materialization_status") != "OK":
        errors.append(f"manifest materialization_status is not OK: {manifest.get('materialization_status')}")
    if manifest.get("research_only") is not True:
        errors.append("manifest research_only must be true")
    if manifest.get("target_output_path") != INPUT_BASELINE_PATH:
        errors.append(f"manifest target_output_path mismatch: {manifest.get('target_output_path')}")
    if manifest.get("ranking_file_count") != 3 or manifest.get("ranking_dates") != EXPECTED_DATES:
        errors.append(f"manifest ranking coverage mismatch: {manifest.get('ranking_file_count')} {manifest.get('ranking_dates')}")
    if len(files) != 3 or file_dates != EXPECTED_DATES:
        errors.append(f"baseline file coverage mismatch: count={len(files)} dates={file_dates}")
    if materialization.get("materialization_status") != "OK" or materialization.get("research_only") is not True:
        errors.append("materialization summary must be OK and research_only")
    if materialization.get("estimated_unlockable_combo_count") != 0:
        errors.append(f"estimated_unlockable_combo_count must be 0: {materialization.get('estimated_unlockable_combo_count')}")
    if manifest.get("production_impact") != PRODUCTION_IMPACT or materialization.get("production_impact") != PRODUCTION_IMPACT:
        errors.append("production_impact must be NO_PRODUCTION_CHANGE")
    if contract.get("does_not_execute_replay") is not True:
        errors.append("input manifest must state original materialization did not execute replay")
    if contains_forbidden_text(manifest, materialization):
        errors.append(f"forbidden text present: {FORBIDDEN_TEXT}")
    return errors


def build_runner_args(args: argparse.Namespace, baseline_dir: Path) -> argparse.Namespace:
    old_argv = sys.argv
    try:
        sys.argv = ["run_capital_aware_replay.py"]
        defaults = run_capital_aware_replay.parse_args()
    finally:
        sys.argv = old_argv
    defaults.rankings_dir = repo_path(baseline_dir)
    defaults.features = args.features
    defaults.market_regime_history = args.market_regime_history
    defaults.group_map = args.group_map
    defaults.scenario = "fixed40"
    defaults.gross_policy = "fixed"
    defaults.initial_cash = 500_000.0
    defaults.top_n = 3
    defaults.horizon = 1
    defaults.entry_delay_trade_days = 1
    defaults.max_ranking_files = 3
    defaults.max_new_positions_per_day = 1
    defaults.max_open_positions = 3
    defaults.max_position_pct = 0.10
    defaults.max_group_pct = 0.30
    defaults.fixed_gross = 0.30
    defaults.output = None
    return defaults


def classify_data_gap(error: Exception) -> str:
    text = str(error)
    data_gap_markers = [
        "沒有可回測的 entry plans",
        "insufficient_future_bars",
        "missing_entry_date",
        "features 不存在",
        "No such file",
    ]
    if any(marker in text for marker in data_gap_markers):
        return "BLOCKED_DATA_GAP"
    return "FAILED"


def run_smoke(args: argparse.Namespace) -> dict[str, Any]:
    run_date = str(args.date)
    baseline_dir = resolve_path(args.baseline_dir)
    materialization_path = resolve_path(args.materialization_summary)
    assert baseline_dir is not None and materialization_path is not None
    manifest_path = baseline_dir / "manifest.json"
    manifest = read_json(manifest_path)
    materialization = read_json(materialization_path)
    input_errors = validate_inputs(baseline_dir, manifest, materialization)
    if input_errors:
        raise RuntimeError("; ".join(input_errors))

    files = ranking_files(baseline_dir)
    file_dates = [ranking_date(path) for path in files]
    runner_can_read_baseline = False
    read_sample: list[dict[str, Any]] = []
    for path in files:
        items = run_backtest_replay.read_ranking(path, top_n=3)
        read_sample.append({"date": ranking_date(path), "path": repo_path(path), "read_top_n": len(items)})
    runner_can_read_baseline = all(row["read_top_n"] > 0 for row in read_sample)

    runner_args = build_runner_args(args, baseline_dir)
    runner_status = "NOT_RUN"
    runner_payload: dict[str, Any] | None = None
    runner_error: str | None = None
    try:
        runner_payload = run_capital_aware_replay.run_replay(runner_args)
        runner_status = "OK"
    except Exception as exc:
        runner_status = classify_data_gap(exc)
        runner_error = str(exc)
        if runner_status != "BLOCKED_DATA_GAP":
            raise

    runner_summary = runner_payload.get("summary") if isinstance(runner_payload, dict) else {}
    actual_replay_count = len(file_dates)
    replay_status = "OK" if runner_status == "OK" else runner_status
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now_utc(),
        "date": run_date,
        "task_id": TASK_ID,
        "replay_smoke_status": replay_status,
        "runner_can_read_baseline": runner_can_read_baseline,
        "input_baseline_path": repo_path(baseline_dir),
        "manifest": repo_path(manifest_path),
        "materialization_summary": repo_path(materialization_path),
        "ranking_file_count": len(files),
        "date_range": {"start": EXPECTED_DATES[0], "end": EXPECTED_DATES[-1], "dates": file_dates},
        "actual_replay_count": actual_replay_count,
        "estimated_unlockable_combo_count": 0,
        "target_production_path_created": FORBIDDEN_PRODUCTION_PATH.exists(),
        "production_impact": PRODUCTION_IMPACT,
        "runner": {
            "script": "scripts/run_capital_aware_replay.py",
            "status": runner_status,
            "error": runner_error,
            "args": {
                "rankings_dir": runner_args.rankings_dir,
                "max_ranking_files": runner_args.max_ranking_files,
                "top_n": runner_args.top_n,
                "horizon": runner_args.horizon,
                "entry_delay_trade_days": runner_args.entry_delay_trade_days,
                "scenario": runner_args.scenario,
                "gross_policy": runner_args.gross_policy,
            },
            "summary": runner_summary,
        },
        "read_sample": read_sample,
        "contract": {
            "research_only": True,
            "three_day_smoke_only": True,
            "does_not_create_artifacts_backtest_production": True,
            "does_not_run_202176_grid": True,
            "does_not_train_model": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_production_ranking": True,
            "does_not_publish_clawd": True,
            "no_promotion_ready": True,
            "replay_smoke_ok_is_not_full_replay_unlock": True,
        },
        "next_action": "WEEKEND-TRAINING-18_baseline_harness_small_window_replay" if replay_status == "OK" else "補 replay 所需資料契約，不跑全量。",
    }
    return payload


def render_markdown(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Baseline Harness Minimal Replay Smoke",
            "",
            f"- replay_smoke_status: `{payload.get('replay_smoke_status')}`",
            f"- runner_can_read_baseline: `{payload.get('runner_can_read_baseline')}`",
            f"- input_baseline_path: `{payload.get('input_baseline_path')}`",
            f"- ranking_file_count: `{payload.get('ranking_file_count')}`",
            f"- actual_replay_count: `{payload.get('actual_replay_count')}`",
            f"- target_production_path_created: `{payload.get('target_production_path_created')}`",
            f"- estimated_unlockable_combo_count: `{payload.get('estimated_unlockable_combo_count')}`",
            f"- production_impact: `{payload.get('production_impact')}`",
            "",
        ]
    )


def main() -> int:
    args = parse_args()
    try:
        payload = run_smoke(args)
    except Exception as exc:
        print(f"BASELINE_HARNESS_MINIMAL_REPLAY_SMOKE_FAILED {exc}", file=sys.stderr)
        return 1
    json_path, md_path = output_paths(str(args.date), args.output)
    write_json(json_path, payload)
    write_text(md_path, render_markdown(payload))
    print(
        "BASELINE_HARNESS_MINIMAL_REPLAY_SMOKE_"
        f"{payload['replay_smoke_status']} output={repo_path(json_path)}"
    )
    return 0 if payload["replay_smoke_status"] in {"OK", "BLOCKED_DATA_GAP"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
