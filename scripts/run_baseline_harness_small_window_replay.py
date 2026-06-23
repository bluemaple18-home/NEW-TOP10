#!/usr/bin/env python3
"""執行 baseline harness 小窗口 replay smoke。

透過 production baseline harness 產生小窗口 staging ranking，materialize 到 research-only
small-window baseline，再用 capital-aware replay 做 bounded smoke；不建立
artifacts/backtest/production，不跑 202,176 格，不改模型與正式 ranking。
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from scripts import build_production_baseline_harness, run_backtest_replay, run_capital_aware_replay  # noqa: E402
from weekend_training_common import PRODUCTION_IMPACT, repo_path, resolve_path, write_json, write_text  # noqa: E402


SCHEMA_VERSION = "baseline-harness-small-window-replay.v1"
TASK_ID = "WEEKEND-TRAINING-18"
DEFAULT_START_DATE = "2026-04-16"
DEFAULT_END_DATE = "2026-05-15"
TARGET_BASELINE_PATH = "artifacts/backtest/production_baseline_harness_small_window"
STAGING_OUTPUT_TEMPLATE = "artifacts/weekend_training/staging/production_baseline_harness_small_window_{date}"
MIN_RANKING_COUNT = 10
MAX_RANKING_COUNT = 25
FORBIDDEN_PRODUCTION_PATH = PROJECT_ROOT / "artifacts" / "backtest" / "production"
FORBIDDEN_TEXT = "PROMOTION_READY"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="run baseline harness small-window replay")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--start-date", default=DEFAULT_START_DATE)
    parser.add_argument("--end-date", default=DEFAULT_END_DATE)
    parser.add_argument("--target-dir", default=TARGET_BASELINE_PATH)
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
        json_path = PROJECT_ROOT / "artifacts" / "weekend_training" / f"baseline_harness_small_window_replay_{run_date}.json"
    return json_path, json_path.with_suffix(".md")


def is_exact_path(path: Path, expected_repo_path: str) -> bool:
    expected = PROJECT_ROOT / expected_repo_path
    return path.resolve() == expected.resolve()


def contains_forbidden_text(*payloads: dict[str, Any]) -> bool:
    return FORBIDDEN_TEXT in json.dumps(payloads, ensure_ascii=False)


def ranking_files(directory: Path) -> list[Path]:
    return sorted(path for path in directory.glob("ranking_*.csv") if path.is_file())


def ranking_date(path: Path) -> str:
    return path.stem.removeprefix("ranking_")


def clean_target_dir(target_dir: Path) -> None:
    if not is_exact_path(target_dir, TARGET_BASELINE_PATH):
        raise RuntimeError(f"target-dir must be exactly {TARGET_BASELINE_PATH}: {repo_path(target_dir)}")
    if FORBIDDEN_PRODUCTION_PATH.exists():
        raise RuntimeError(f"forbidden production path exists: {repo_path(FORBIDDEN_PRODUCTION_PATH)}")
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)


def build_harness_args(args: argparse.Namespace, staging_dir: Path) -> argparse.Namespace:
    return argparse.Namespace(
        date=f"{args.date}-small-window",
        start_date=args.start_date,
        end_date=args.end_date,
        data_dir="data/clean",
        model_dir="models",
        config="config/signals.yaml",
        output_dir=repo_path(staging_dir),
        stride=1,
        max_dates=None,
        legacy_per_date_load=False,
    )


def copy_small_window_baseline(staging_manifest: dict[str, Any], staging_manifest_path: Path, target_dir: Path) -> list[dict[str, Any]]:
    output_dir = resolve_path(staging_manifest.get("output_dir")) or staging_manifest_path.parent
    copied: list[dict[str, Any]] = []
    for date_text in staging_manifest.get("ranking_dates") or []:
        source = output_dir / f"ranking_{date_text}.csv"
        target = target_dir / source.name
        if not source.exists():
            raise RuntimeError(f"missing staging ranking: {repo_path(source)}")
        shutil.copy2(source, target)
        copied.append({"date": str(date_text), "source_path": repo_path(source), "target_path": repo_path(target), "bytes": target.stat().st_size})
    return copied


def materialize_manifest(
    run_date: str,
    target_dir: Path,
    staging_manifest_path: Path,
    staging_manifest: dict[str, Any],
    copied_files: list[dict[str, Any]],
) -> dict[str, Any]:
    manifest = {
        "schema_version": "research-only-production-baseline-small-window-manifest.v1",
        "generated_at": now_utc(),
        "date": run_date,
        "task_id": TASK_ID,
        "research_only": True,
        "materialization_status": "OK",
        "target_output_path": repo_path(target_dir),
        "forbidden_production_path": repo_path(FORBIDDEN_PRODUCTION_PATH),
        "target_production_path_created": FORBIDDEN_PRODUCTION_PATH.exists(),
        "source_staging_manifest": repo_path(staging_manifest_path),
        "source_staging_output_dir": staging_manifest.get("output_dir"),
        "source_schema_version": staging_manifest.get("schema_version"),
        "window": {
            "start": staging_manifest.get("start_date"),
            "end": staging_manifest.get("end_date"),
            "suggested_window": f"{DEFAULT_START_DATE} ~ {DEFAULT_END_DATE}",
        },
        "ranking_dates": [row["date"] for row in copied_files],
        "ranking_file_count": len(copied_files),
        "estimated_unlockable_combo_count": 0,
        "production_impact": PRODUCTION_IMPACT,
        "copied_files": copied_files,
        "lineage": {
            "traces_source_staging_harness": True,
            "copied_from_staging_harness": True,
            "source_pipeline": staging_manifest.get("source_pipeline"),
            "source_generator_manifest": (staging_manifest.get("lineage") or {}).get("generator_manifest"),
            "source_model_artifact": staging_manifest.get("model_artifact"),
            "source_model_hash": staging_manifest.get("model_hash"),
            "source_config": staging_manifest.get("config"),
            "source_config_hash": staging_manifest.get("config_hash"),
        },
        "contract": {
            "research_only": True,
            "small_window_only": True,
            "does_not_create_artifacts_backtest_production": True,
            "does_not_run_202176_grid": True,
            "does_not_train_model": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_production_ranking": True,
            "does_not_publish_clawd": True,
            "no_promotion_ready": True,
            "small_window_ok_is_not_full_replay_unlock": True,
        },
    }
    write_json(target_dir / "manifest.json", manifest)
    return manifest


def build_runner_args(args: argparse.Namespace, target_dir: Path, ranking_count: int) -> argparse.Namespace:
    old_argv = sys.argv
    try:
        sys.argv = ["run_capital_aware_replay.py"]
        defaults = run_capital_aware_replay.parse_args()
    finally:
        sys.argv = old_argv
    defaults.rankings_dir = repo_path(target_dir)
    defaults.features = args.features
    defaults.market_regime_history = args.market_regime_history
    defaults.group_map = args.group_map
    defaults.scenario = "fixed40"
    defaults.gross_policy = "fixed"
    defaults.initial_cash = 500_000.0
    defaults.top_n = 3
    defaults.horizon = 1
    defaults.entry_delay_trade_days = 1
    defaults.max_ranking_files = ranking_count
    defaults.max_new_positions_per_day = 1
    defaults.max_open_positions = 3
    defaults.max_position_pct = 0.10
    defaults.max_group_pct = 0.30
    defaults.fixed_gross = 0.30
    defaults.output = None
    return defaults


def read_baseline_sample(target_dir: Path) -> list[dict[str, Any]]:
    sample: list[dict[str, Any]] = []
    for path in ranking_files(target_dir):
        items = run_backtest_replay.read_ranking(path, top_n=3)
        sample.append({"date": ranking_date(path), "path": repo_path(path), "read_top_n": len(items)})
    return sample


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    if FORBIDDEN_PRODUCTION_PATH.exists():
        raise RuntimeError(f"forbidden production path exists before run: {repo_path(FORBIDDEN_PRODUCTION_PATH)}")

    run_date = str(args.date)
    staging_dir = resolve_path(STAGING_OUTPUT_TEMPLATE.format(date=run_date))
    target_dir = resolve_path(args.target_dir)
    assert staging_dir is not None and target_dir is not None
    harness_args = build_harness_args(args, staging_dir)
    harness_smoke = build_production_baseline_harness.build_payload(harness_args)
    staging_manifest_path = staging_dir / "manifest.json"
    staging_manifest = read_json(staging_manifest_path)
    harness_status = harness_smoke.get("harness_status") or (staging_manifest.get("summary") or {}).get("harness_status")
    if harness_status != "OK":
        raise RuntimeError(f"harness small-window staging blocked: {harness_smoke.get('blocker_reasons')}")
    if FORBIDDEN_PRODUCTION_PATH.exists():
        raise RuntimeError(f"forbidden production path exists after harness: {repo_path(FORBIDDEN_PRODUCTION_PATH)}")

    clean_target_dir(target_dir)
    copied_files = copy_small_window_baseline(staging_manifest, staging_manifest_path, target_dir)
    materialized_manifest = materialize_manifest(run_date, target_dir, staging_manifest_path, staging_manifest, copied_files)
    if contains_forbidden_text(harness_smoke, staging_manifest, materialized_manifest):
        raise RuntimeError(f"forbidden text present: {FORBIDDEN_TEXT}")

    ranking_count = len(copied_files)
    read_sample = read_baseline_sample(target_dir)
    runner_can_read_baseline = all(row["read_top_n"] > 0 for row in read_sample)
    runner_args = build_runner_args(args, target_dir, ranking_count)
    runner_payload = run_capital_aware_replay.run_replay(runner_args)
    runner_summary = runner_payload.get("summary") if isinstance(runner_payload, dict) else {}
    file_dates = [row["date"] for row in copied_files]
    status = "OK" if ranking_count >= MIN_RANKING_COUNT and runner_can_read_baseline else "BLOCKED"
    if runner_summary.get("daily_count", 0) < MIN_RANKING_COUNT:
        status = "BLOCKED"

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now_utc(),
        "date": run_date,
        "task_id": TASK_ID,
        "small_window_status": status,
        "runner_can_read_baseline": runner_can_read_baseline,
        "input_baseline_path": repo_path(target_dir),
        "manifest": repo_path(target_dir / "manifest.json"),
        "staging_manifest": repo_path(staging_manifest_path),
        "window": {"start": args.start_date, "end": args.end_date, "dates": file_dates},
        "ranking_file_count": ranking_count,
        "actual_replay_count": int(runner_summary.get("daily_count") or 0),
        "estimated_unlockable_combo_count": 0,
        "target_production_path_created": FORBIDDEN_PRODUCTION_PATH.exists(),
        "production_impact": PRODUCTION_IMPACT,
        "runner": {
            "script": "scripts/run_capital_aware_replay.py",
            "status": "OK",
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
        "harness": {
            "script": "scripts/build_production_baseline_harness.py",
            "status": harness_status,
            "staging_output_dir": repo_path(staging_dir),
            "ranking_file_count": ranking_count,
        },
        "read_sample": read_sample[:5],
        "window_note": "實際交易日數以 harness 產出的 ranking file count 為準。",
        "contract": {
            "research_only": True,
            "small_window_only": True,
            "does_not_create_artifacts_backtest_production": True,
            "does_not_run_202176_grid": True,
            "does_not_train_model": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_production_ranking": True,
            "does_not_publish_clawd": True,
            "no_promotion_ready": True,
            "small_window_ok_is_not_full_replay_unlock": True,
        },
        "next_action": "WEEKEND-TRAINING-19_baseline_harness_medium_window_review" if status == "OK" else "修小窗口 harness/replay blocker，不跑全量。",
    }


def render_markdown(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Baseline Harness Small-Window Replay",
            "",
            f"- small_window_status: `{payload.get('small_window_status')}`",
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


def output_paths(run_date: str, override: str | None) -> tuple[Path, Path]:
    if override:
        json_path = resolve_path(override)
        assert json_path is not None
    else:
        json_path = PROJECT_ROOT / "artifacts" / "weekend_training" / f"baseline_harness_small_window_replay_{run_date}.json"
    return json_path, json_path.with_suffix(".md")


def main() -> int:
    args = parse_args()
    try:
        payload = build_payload(args)
    except Exception as exc:
        print(f"BASELINE_HARNESS_SMALL_WINDOW_REPLAY_FAILED {exc}", file=sys.stderr)
        return 1
    json_path, md_path = output_paths(str(args.date), args.output)
    write_json(json_path, payload)
    write_text(md_path, render_markdown(payload))
    print(f"BASELINE_HARNESS_SMALL_WINDOW_REPLAY_{payload['small_window_status']} output={repo_path(json_path)}")
    return 0 if payload["small_window_status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
