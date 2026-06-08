#!/usr/bin/env python3
"""執行 overnight shadow training 長窗口流程。

只產研究 artifact，不訓練模型、不覆蓋 latest_lgbm、不改 production ranking。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "overnight-shadow-training-runner.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="run overnight shadow training")
    parser.add_argument("--date", required=True)
    parser.add_argument("--label", default="extended")
    parser.add_argument("--dates-from-dir", default="artifacts/backtest/historical_rankings_current_model_extended")
    parser.add_argument("--market-regime-history", default="artifacts/market_regime_history_2026-06-01.json")
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument("--model-hash-before", required=True)
    parser.add_argument("--keeps", default="6,7,8")
    parser.add_argument("--output", default=None)
    parser.add_argument("--steps-log", default=None)
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def run_step(name: str, command: list[str]) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    ended = datetime.now(timezone.utc)
    return {
        "name": name,
        "status": "OK" if completed.returncode == 0 else "FAILED",
        "returncode": completed.returncode,
        "started_at": started.isoformat(),
        "ended_at": ended.isoformat(),
        "command": command,
        "stdout_tail": completed.stdout[-3000:],
        "stderr_tail": completed.stderr[-3000:],
    }


def append_tsv(path: Path, step: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{step['name']}\t{step['status']}\t{step['started_at']}\t{step['ended_at']}\t{step['returncode']}\n")


def replay_command(rankings_dir: str, output: str, features: str) -> list[str]:
    return [
        sys.executable,
        "scripts/run_backtest_replay.py",
        "--rankings-dir",
        rankings_dir,
        "--features",
        features,
        "--output",
        output,
    ]


def portfolio_command(rankings_dir: str, output: str, features: str, top_n: int = 10) -> list[str]:
    return [
        sys.executable,
        "scripts/run_portfolio_replay.py",
        "--rankings-dir",
        rankings_dir,
        "--features",
        features,
        "--horizon",
        "10",
        "--top-n",
        str(top_n),
        "--max-group-exposure",
        "0.35",
        "--output",
        output,
    ]


def shadow_ranking_command(args: argparse.Namespace, output_dir: str, risk_profile: str) -> list[str]:
    return [
        sys.executable,
        "scripts/research_regime_shadow_ranking.py",
        "--dates-from-dir",
        args.dates_from_dir,
        "--output-dir",
        output_dir,
        "--market-regime-history",
        args.market_regime_history,
        "--risk-profile",
        risk_profile,
        "--top-n",
        "10",
        "--max-sector-count",
        "4",
        "--sector-cap-column",
        "industry_name",
    ]


def constrained_command(production_dir: str, shadow_dir: str, output_dir: str, keep: int) -> list[str]:
    return [
        sys.executable,
        "scripts/build_constrained_shadow_rankings.py",
        "--production-dir",
        production_dir,
        "--shadow-dir",
        shadow_dir,
        "--output-dir",
        output_dir,
        "--top-n",
        "10",
        "--min-production-count",
        str(keep),
    ]


def summary_command(args: argparse.Namespace, steps_log: Path) -> list[str]:
    return [
        sys.executable,
        "scripts/build_overnight_training_summary.py",
        "--date",
        args.date,
        "--window",
        args.label,
        "--artifact-label",
        args.label,
        "--model-hash-before",
        args.model_hash_before,
        "--steps-log",
        repo_path(steps_log),
    ]


def planned_steps(args: argparse.Namespace) -> list[tuple[str, list[str]]]:
    label = args.label
    production_dir = args.dates_from_dir
    feature_shadow = f"artifacts/backtest/shadow_rankings_batch01_feature_group_sector_cap_{label}"
    sector_shadow = f"artifacts/backtest/shadow_rankings_batch01_sector_context_sector_cap_{label}"
    steps: list[tuple[str, list[str]]] = [
        (
            "baseline.replay",
            replay_command(production_dir, f"artifacts/backtest/replay_batch01_baseline_{label}_{args.date}.json", args.features),
        ),
        (
            "baseline.portfolio.top10",
            portfolio_command(
                production_dir,
                f"artifacts/backtest/portfolio_batch01_baseline_{label}_top10_h10_{args.date}.json",
                args.features,
            ),
        ),
        ("feature_group.shadow_ranking", shadow_ranking_command(args, feature_shadow, "baseline")),
        ("sector_context.shadow_ranking", shadow_ranking_command(args, sector_shadow, "shadow_regime_guard_balanced")),
    ]
    for keep in [int(item.strip()) for item in args.keeps.split(",") if item.strip()]:
        for prefix, shadow_dir in [("feature_group", feature_shadow), ("sector_context", sector_shadow)]:
            constrained_dir = f"artifacts/backtest/shadow_rankings_batch01_{prefix}_constrained_k{keep}_{label}"
            candidate = f"{prefix}_constrained_k{keep}_{label}"
            steps.append((f"{prefix}.constrained.k{keep}", constrained_command(production_dir, shadow_dir, constrained_dir, keep)))
            steps.append(
                (
                    f"{prefix}.replay.k{keep}",
                    replay_command(
                        constrained_dir,
                        f"artifacts/backtest/replay_batch01_{candidate}_{args.date}.json",
                        args.features,
                    ),
                )
            )
            steps.append(
                (
                    f"{prefix}.portfolio.k{keep}",
                    portfolio_command(
                        constrained_dir,
                        f"artifacts/backtest/portfolio_batch01_{candidate}_top10_h10_{args.date}.json",
                        args.features,
                    ),
                )
            )
    return steps


def main() -> int:
    args = parse_args()
    steps_log = resolve_path(args.steps_log or f"artifacts/model_experiments/overnight_training_steps_{args.date}_{args.label}.tsv")
    if steps_log.exists():
        steps_log.unlink()
    steps: list[dict[str, Any]] = []
    for name, command in planned_steps(args):
        step = run_step(name, command)
        steps.append(step)
        append_tsv(steps_log, step)
    summary_step = run_step("summary.build", summary_command(args, steps_log))
    steps.append(summary_step)
    append_tsv(steps_log, summary_step)
    status = "OK" if all(step["status"] == "OK" for step in steps) else "FAILED"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "label": args.label,
        "status": status,
        "contract": {
            "research_only": True,
            "does_not_train_model": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_production_ranking": True,
        },
        "steps_log": repo_path(steps_log),
        "steps": steps,
    }
    output = resolve_path(args.output or f"artifacts/model_experiments/overnight_shadow_training_runner_{args.date}_{args.label}.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"status": status, "output": repo_path(output), "steps_log": repo_path(steps_log)}, ensure_ascii=False))
    return 0 if status == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
