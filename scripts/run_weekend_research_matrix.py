#!/usr/bin/env python3
"""週末大量研究矩陣 runner。

這個 runner 只串接研究/回測腳本，不抓資料、不訓練模型、不改 production ranking。
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
SCHEMA_VERSION = "weekend-research-matrix-run.v1"
RECENT_WINDOW = "2026-04-08_2026-05-13"
VARIANTS = {
    "current": "artifacts/backtest/historical_rankings_current_model",
    "overlay": "artifacts/backtest/shadow_rankings_regime_overlay_recent",
    "guard_balanced": "artifacts/backtest/shadow_rankings_regime_guard_balanced_recent",
    "guard_strict": "artifacts/backtest/shadow_rankings_regime_guard_recent",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="run weekend research matrix")
    parser.add_argument("--max-ranking-files", type=int, default=25)
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument("--output", default=f"artifacts/backtest/weekend_research_matrix_{RECENT_WINDOW}.json")
    parser.add_argument("--skip-heavy", action="store_true", help="只跑 audit/factor/compare，不重跑 strategy matrix")
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


def strategy_output(label: str) -> str:
    return f"artifacts/backtest/strategy_matrix_{label}_recent_{RECENT_WINDOW}.json"


def replay_variant_args() -> list[str]:
    return [
        "--variant",
        f"current=artifacts/backtest/replay_current_model_{RECENT_WINDOW}.json",
        "--variant",
        f"overlay=artifacts/backtest/replay_shadow_regime_overlay_{RECENT_WINDOW}.json",
        "--variant",
        f"guard_balanced=artifacts/backtest/replay_shadow_regime_guard_balanced_{RECENT_WINDOW}.json",
        "--variant",
        f"guard_strict=artifacts/backtest/replay_shadow_regime_guard_{RECENT_WINDOW}.json",
        "--output",
        f"artifacts/backtest/replay_variant_comparison_{RECENT_WINDOW}.json",
    ]


def strategy_variant_args() -> list[str]:
    args: list[str] = []
    for label in VARIANTS:
        args.extend(["--variant", f"{label}={strategy_output(label)}"])
    return args


def matrix_commands(args: argparse.Namespace) -> list[tuple[str, list[str]]]:
    python = sys.executable
    commands: list[tuple[str, list[str]]] = [
        ("dataset_coverage", [python, "scripts/audit_research_dataset_coverage.py"]),
        ("factor_monitor", [python, "scripts/monitor_factors.py"]),
        ("industry_momentum_walkforward", [python, "scripts/research_industry_momentum_walkforward.py"]),
    ]
    if not args.skip_heavy:
        for label, rankings_dir in VARIANTS.items():
            commands.append(
                (
                    f"strategy_matrix.{label}",
                    [
                        python,
                        "scripts/run_backtest_strategy_matrix.py",
                        "--rankings-dir",
                        rankings_dir,
                        "--features",
                        args.features,
                        "--max-ranking-files",
                        str(args.max_ranking_files),
                        "--horizons",
                        "3,5,10",
                        "--stop-loss-pcts",
                        "none,0.06,0.08",
                        "--take-profit-pcts",
                        "none,0.12,0.15",
                        "--max-group-exposures",
                        "none,0.35,0.5",
                        "--output",
                        strategy_output(label),
                    ],
                )
            )
    commands.append(
        (
            "compare_replay_variants",
            [python, "scripts/compare_replay_variants.py", *replay_variant_args()],
        )
    )
    commands.append(
        (
            "compare_strategy_matrices",
            [
                python,
                "scripts/compare_strategy_matrices.py",
                *strategy_variant_args(),
                "--output",
                f"artifacts/backtest/strategy_matrix_comparison_recent_{RECENT_WINDOW}.json",
            ],
        )
    )
    return commands


def summarize_outputs() -> dict[str, Any]:
    comparison_path = PROJECT_ROOT / f"artifacts/backtest/strategy_matrix_comparison_recent_{RECENT_WINDOW}.json"
    replay_path = PROJECT_ROOT / f"artifacts/backtest/replay_variant_comparison_{RECENT_WINDOW}.json"
    coverage_path = PROJECT_ROOT / "artifacts" / "research_dataset_coverage_2026-05-29.json"
    industry_path = PROJECT_ROOT / "artifacts" / "industry_momentum_walkforward_shadow.json"
    summary: dict[str, Any] = {
        "strategy_matrix_comparison": repo_path(comparison_path),
        "replay_variant_comparison": repo_path(replay_path),
        "dataset_coverage": repo_path(coverage_path),
        "industry_momentum_walkforward": repo_path(industry_path),
    }
    if comparison_path.exists():
        data = json.loads(comparison_path.read_text(encoding="utf-8"))
        summary["strategy_best"] = data.get("summary", [])
        summary["strategy_best_by_horizon"] = data.get("best_by_horizon", [])
    if replay_path.exists():
        data = json.loads(replay_path.read_text(encoding="utf-8"))
        summary["replay_rows"] = data.get("rows", [])
    if coverage_path.exists():
        data = json.loads(coverage_path.read_text(encoding="utf-8"))
        summary["coverage_status_counts"] = data.get("summary", {}).get("status_counts")
        summary["blocked_dimensions"] = data.get("summary", {}).get("blocked_dimensions")
    if industry_path.exists():
        data = json.loads(industry_path.read_text(encoding="utf-8"))
        summary["industry_recommendation"] = data.get("recommendation")
        summary["industry_walkforward"] = data.get("walkforward")
    return summary


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Weekend Research Matrix",
        "",
        f"- status：`{payload['status']}`",
        f"- generated_at：`{payload['generated_at']}`",
        f"- max_ranking_files：`{payload['inputs']['max_ranking_files']}`",
        "",
        "## Steps",
        "",
        "| Step | Status |",
        "|---|---|",
    ]
    for step in payload["steps"]:
        lines.append(f"| `{step['name']}` | `{step['status']}` |")
    lines.extend(["", "## Outputs", ""])
    for key, value in payload["outputs"].items():
        if isinstance(value, str):
            lines.append(f"- `{key}`：`{value}`")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    steps = [run_step(name, command) for name, command in matrix_commands(args)]
    status = "OK" if all(step["status"] == "OK" for step in steps) else "FAILED"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "contract": {
            "research_only": True,
            "does_not_fetch_data": True,
            "does_not_train_model": True,
            "does_not_change_production_ranking": True,
        },
        "inputs": {
            "max_ranking_files": args.max_ranking_files,
            "features": args.features,
            "skip_heavy": args.skip_heavy,
            "variants": VARIANTS,
        },
        "steps": steps,
        "outputs": summarize_outputs(),
    }
    output_path = resolve_path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output_path.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": status, "output": repo_path(output_path), "steps": len(steps)}, ensure_ascii=False))
    return 0 if status == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
