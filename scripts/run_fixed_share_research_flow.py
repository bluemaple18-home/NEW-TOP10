#!/usr/bin/env python3
"""固定股數研究工廠一鍵流程。

只重跑研究 artifacts，不訓練模型、不修改 production ranking。這是 automation
可呼叫的入口，將四套矩陣與彙整報告串起來。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "fixed-share-research-flow.v1"


MATRIX_RUNS = [
    {
        "id": "production_half_year",
        "rankings_dir": "artifacts/backtest/historical_rankings_current_model_half_year_dense_2025-11-17_2026-05-15",
        "variant_label": "production",
        "output": "artifacts/backtest/fixed_share_hypothesis_matrix_production_half_year_{date}.json",
    },
    {
        "id": "a1_half_year",
        "rankings_dir": "artifacts/backtest/shadow_rankings_batch01_sector_context_constrained_k7_half_year_dense",
        "variant_label": "sector_context_production_top7_shadow_fill3",
        "output": "artifacts/backtest/fixed_share_hypothesis_matrix_sector_context_top7_fill3_half_year_{date}.json",
    },
    {
        "id": "production_extended",
        "rankings_dir": "artifacts/backtest/historical_rankings_current_model_extended",
        "variant_label": "production_extended",
        "output": "artifacts/backtest/fixed_share_hypothesis_matrix_production_extended_{date}.json",
    },
    {
        "id": "a1_extended",
        "rankings_dir": "artifacts/backtest/shadow_rankings_batch01_sector_context_constrained_k7_extended",
        "variant_label": "sector_context_top7_fill3_extended",
        "output": "artifacts/backtest/fixed_share_hypothesis_matrix_sector_context_top7_fill3_extended_{date}.json",
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="run fixed-share research flow")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--skip-matrices", action="store_true")
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def run_command(command: list[str]) -> dict[str, Any]:
    result = subprocess.run(command, cwd=PROJECT_ROOT, text=True, capture_output=True, check=False)
    return {
        "command": command,
        "returncode": result.returncode,
        "stdout_tail": result.stdout[-1000:],
        "stderr_tail": result.stderr[-1000:],
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    if not args.skip_matrices:
        for run in MATRIX_RUNS:
            output = run["output"].format(date=args.date)
            command = [
                sys.executable,
                "scripts/run_fixed_share_hypothesis_matrix.py",
                "--rankings-dir",
                run["rankings_dir"],
                "--variant-label",
                run["variant_label"],
                "--output",
                output,
            ]
            result = run_command(command)
            steps.append({"id": run["id"], "kind": "matrix", "output": output, **result})
            if result["returncode"] != 0:
                break

    if all(step["returncode"] == 0 for step in steps):
        report_output = f"artifacts/model_experiments/fixed_share_research_factory_report_{args.date}.json"
        command = [
            sys.executable,
            "scripts/build_fixed_share_research_factory_report.py",
            "--date",
            args.date,
            "--output",
            report_output,
        ]
        result = run_command(command)
        steps.append({"id": "research_factory_report", "kind": "report", "output": report_output, **result})

    if steps and all(step["returncode"] == 0 for step in steps):
        verification_output = "artifacts/model_experiments/fixed_share_research_factory_verification_latest.json"
        command = [
            sys.executable,
            "scripts/verify_fixed_share_research_factory.py",
            "--date",
            args.date,
            "--output",
            verification_output,
        ]
        result = run_command(command)
        steps.append({"id": "research_factory_verification", "kind": "verification", "output": verification_output, **result})

    status = "OK" if steps and all(step["returncode"] == 0 for step in steps) else "FAILED"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": status,
        "contract": {
            "research_only": True,
            "model_changes": False,
            "production_changes": False,
            "promotion_ready": False,
        },
        "steps": steps,
    }


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output_path = (
        Path(args.output).expanduser()
        if args.output
        else PROJECT_ROOT / "artifacts" / "model_experiments" / f"fixed_share_research_flow_{args.date}.json"
    )
    output_path = output_path if output_path.is_absolute() else PROJECT_ROOT / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output_path)}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
