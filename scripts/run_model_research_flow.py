#!/usr/bin/env python3
"""串接安全模型研究流程。

流程只包含 feature gate、SHADOW-01、MODEL-EXP-01 plan 與驗證。
不訓練模型、不覆蓋 models/latest_lgbm.pkl、不改 production ranking。
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
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
MODEL_EXPERIMENTS_DIR = ARTIFACTS_DIR / "model_experiments"
SCHEMA_VERSION = "model-research-flow.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="run safe model research flow")
    parser.add_argument("--date", default=date.today().isoformat())
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


def skipped_step(name: str, command: list[str], reason: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "name": name,
        "status": "SKIPPED",
        "returncode": None,
        "started_at": now,
        "ended_at": now,
        "command": command,
        "stdout_tail": "",
        "stderr_tail": "",
        "skip_reason": reason,
    }


def flow_steps(run_date: str) -> list[tuple[str, list[str]]]:
    shadow_index = f"artifacts/shadow_feature_experiment_{run_date}.json"
    model_plan = f"artifacts/model_experiments/model_exp_plan_{run_date}.json"
    run_manifest = f"artifacts/model_experiments/model_exp_run_manifest_{run_date}.json"
    return [
        ("feature_gate.build", [sys.executable, "scripts/build_feature_experiment_gate.py"]),
        ("feature_gate.verify", [sys.executable, "scripts/verify_feature_experiment_gate.py"]),
        ("shadow_feature.build", [sys.executable, "scripts/build_shadow_feature_experiment.py", "--date", run_date]),
        (
            "shadow_feature.verify",
            [
                sys.executable,
                "scripts/verify_shadow_feature_experiment.py",
                "--artifact",
                shadow_index,
            ],
        ),
        ("model_exp_plan.build", [sys.executable, "scripts/build_model_experiment_plan.py", "--date", run_date]),
        (
            "model_exp_plan.verify",
            [
                sys.executable,
                "scripts/verify_model_experiment_plan.py",
                "--artifact",
                model_plan,
            ],
        ),
        ("model_exp_run_manifest.build", [sys.executable, "scripts/build_model_experiment_run_manifest.py", "--date", run_date]),
        (
            "model_exp_run_manifest.verify",
            [
                sys.executable,
                "scripts/verify_model_experiment_run_manifest.py",
                "--artifact",
                run_manifest,
            ],
        ),
    ]


def run_flow(steps_to_run: list[tuple[str, list[str]]]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    failed_step: str | None = None
    for name, command in steps_to_run:
        if failed_step is not None:
            steps.append(skipped_step(name, command, f"previous step failed: {failed_step}"))
            continue
        step = run_step(name, command)
        steps.append(step)
        if step["status"] != "OK":
            failed_step = name
    return steps


def build_manifest(run_date: str, steps: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": run_date,
        "status": "OK" if all(step["status"] == "OK" for step in steps) else "FAILED",
        "contract": {
            "research_only": True,
            "safe_flow_only": True,
            "does_not_fetch_data": True,
            "does_not_train_model": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_risk_adjusted_score": True,
            "does_not_change_production_ranking": True,
            "production_promotion_allowed": False,
        },
        "outputs": {
            "feature_gate": f"artifacts/feature_experiment_gate_{run_date}.json",
            "shadow_feature_experiment": f"artifacts/shadow_feature_experiment_{run_date}.json",
            "shadow_feature_verification": "artifacts/shadow_feature_experiment_verification_latest.json",
            "model_experiment_plan": f"artifacts/model_experiments/model_exp_plan_{run_date}.json",
            "model_experiment_plan_verification": "artifacts/model_experiments/model_exp_plan_verification_latest.json",
            "model_experiment_run_manifest": f"artifacts/model_experiments/model_exp_run_manifest_{run_date}.json",
            "model_experiment_run_manifest_verification": "artifacts/model_experiments/model_exp_run_manifest_verification_latest.json",
        },
        "steps": steps,
    }


def main() -> int:
    args = parse_args()
    steps = run_flow(flow_steps(args.date))
    manifest = build_manifest(args.date, steps)
    output = resolve_path(args.output) or MODEL_EXPERIMENTS_DIR / f"model_research_flow_{args.date}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "output": repo_path(output),
                "steps": len(steps),
                "failed_steps": [step["name"] for step in steps if step["status"] != "OK"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if manifest["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
