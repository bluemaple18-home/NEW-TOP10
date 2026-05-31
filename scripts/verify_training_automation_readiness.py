#!/usr/bin/env python3
"""驗證正式自動化訓練前的準備狀態。

這支腳本是「開自動訓練前」的總閘門：只跑/讀既有安全檢查與研究
artifact，不訓練模型、不覆蓋 `models/latest_lgbm.pkl`、不改 production
ranking。它的輸出可用來判斷目前是已可準備自動化，還是仍有 blocker。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
MODEL_EXPERIMENTS_DIR = ARTIFACTS_DIR / "model_experiments"
SCHEMA_VERSION = "training-automation-readiness.v1"

CORE_CHECKS: tuple[tuple[str, list[str]], ...] = (
    ("data.pipeline.validate", ["-m", "app.pipeline_cli", "validate", "--json"]),
    ("resource.guard", ["scripts/verify_resource_guard.py"]),
    ("production.write_guard", ["scripts/verify_production_write_guard.py"]),
    ("sealed_oos.capacity_preflight", ["scripts/verify_retrain_sealed_oos_capacity_preflight.py"]),
    ("retrain.rollback", ["scripts/verify_retrain_rollback.py"]),
    ("model.research_flow.verify", ["scripts/verify_model_research_flow.py"]),
    ("model.group_acceptance", ["scripts/verify_model_group_acceptance.py"]),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify training automation readiness")
    parser.add_argument("--date", default=datetime.now().astimezone().date().isoformat())
    parser.add_argument("--output", default=None)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument(
        "--skip-model-research-flow",
        action="store_true",
        help="只讀既有 model research artifacts；預設會重跑 flow 產生當日 artifact",
    )
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


def load_config() -> dict[str, Any]:
    path = PROJECT_ROOT / "config" / "automation.yaml"
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def run_step(name: str, args: list[str], timeout_seconds: int) -> dict[str, Any]:
    command = [sys.executable, *args]
    env = os.environ.copy()
    env.setdefault("PYTHONPYCACHEPREFIX", "/private/tmp/top10_pycache")
    started_at = datetime.now(timezone.utc)
    try:
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        return {
            "name": name,
            "command": command,
            "status": "OK" if completed.returncode == 0 else "FAILED",
            "exit_code": completed.returncode,
            "started_at": started_at.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "stdout_tail": completed.stdout[-4000:],
            "stderr_tail": completed.stderr[-4000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "command": command,
            "status": "FAILED",
            "exit_code": None,
            "started_at": started_at.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "stdout_tail": (exc.stdout or "")[-4000:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-4000:] if isinstance(exc.stderr, str) else "",
            "error": f"timeout after {timeout_seconds}s",
        }


def research_flow_step(args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.skip_model_research_flow:
        return [
            {
                "name": "model.research_flow.run",
                "status": "SKIPPED",
                "exit_code": 0,
                "message": "skip-model-research-flow",
            }
        ]
    return [
        run_step(
            "model.research_flow.run",
            ["scripts/run_model_research_flow.py", "--date", args.date],
            args.timeout_seconds,
        )
    ]


def build_result_report_steps(args: argparse.Namespace) -> list[dict[str, Any]]:
    report_path = MODEL_EXPERIMENTS_DIR / f"model_exp_result_report_{args.date}.json"
    return [
        run_step(
            "model.result_report.build",
            ["scripts/build_model_experiment_result_report.py", "--date", args.date],
            args.timeout_seconds,
        ),
        run_step(
            "model.result_report.verify",
            ["scripts/verify_model_experiment_result_report.py", "--artifact", repo_path(report_path) or str(report_path)],
            args.timeout_seconds,
        ),
    ]


def step_status_ok(step: dict[str, Any]) -> bool:
    return step.get("status") in {"OK", "SKIPPED"}


def readiness_status(
    steps: list[dict[str, Any]],
    config: dict[str, Any],
    health: dict[str, Any],
    result_report: dict[str, Any],
    model_group: dict[str, Any],
) -> tuple[str, list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    failed_steps = [step["name"] for step in steps if not step_status_ok(step)]
    if failed_steps:
        blockers.append("failed readiness steps: " + ", ".join(failed_steps))

    monitor_config = config.get("monitor") if isinstance(config.get("monitor"), dict) else {}
    auto_retrain_enabled = bool(monitor_config.get("auto_retrain", False))
    if auto_retrain_enabled:
        blockers.append("monitor.auto_retrain is enabled before readiness is fully approved")

    if str(config.get("retrain", {}).get("schedule", "")).lower() not in {"manual", ""}:
        warnings.append(f"retrain.schedule={config.get('retrain', {}).get('schedule')} is not manual")

    health_status = str(health.get("status", "MISSING")).upper()
    if health_status != "OK":
        blockers.append(f"model health is {health_status}")

    group_auto = str(model_group.get("auto_retrain_readiness", "MISSING")).upper()
    if group_auto != "READY":
        blockers.append(f"model_group auto_retrain_readiness is {group_auto}")

    result_status = str(result_report.get("status", "MISSING")).upper()
    if result_status not in {"OK", "WARN"}:
        blockers.append(f"model experiment result report status is {result_status}")

    summary = result_report.get("summary") if isinstance(result_report.get("summary"), dict) else {}
    pass_to_next = summary.get("pass_to_next") or []
    if not pass_to_next:
        blockers.append("no model experiment is approved for next-stage training yet")
    if summary.get("blocked"):
        warnings.append("blocked experiments: " + ", ".join(str(item) for item in summary.get("blocked", [])))
    if summary.get("waiting"):
        warnings.append("waiting experiments: " + ", ".join(str(item) for item in summary.get("waiting", [])))

    core_ok = not failed_steps and not auto_retrain_enabled
    if not core_ok:
        return "FAILED", blockers, warnings
    if blockers:
        return "PREPARED_WITH_BLOCKERS", blockers, warnings
    if warnings:
        return "PREPARED_WITH_WARNINGS", blockers, warnings
    return "READY_FOR_AUTOMATED_TRAINING_REVIEW", blockers, warnings


def build_payload(args: argparse.Namespace, steps: list[dict[str, Any]]) -> dict[str, Any]:
    config = load_config()
    health_path = ARTIFACTS_DIR / "model_health_report_latest.json"
    model_group_path = ARTIFACTS_DIR / f"model_group_acceptance_{args.date}.json"
    result_report_path = MODEL_EXPERIMENTS_DIR / f"model_exp_result_report_{args.date}.json"
    health = load_json(health_path)
    model_group = load_json(model_group_path)
    result_report = load_json(result_report_path)
    status, blockers, warnings = readiness_status(steps, config, health, result_report, model_group)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": status,
        "contract": {
            "pre_automation_gate": True,
            "research_only": True,
            "does_not_fetch_data": True,
            "does_not_train_model": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_risk_adjusted_score": True,
            "does_not_change_production_ranking": True,
            "does_not_enable_auto_retrain": True,
        },
        "readiness": {
            "core_steps_ok": all(step_status_ok(step) for step in steps),
            "auto_retrain_enabled": bool((config.get("monitor") or {}).get("auto_retrain", False)),
            "retrain_schedule": (config.get("retrain") or {}).get("schedule"),
            "model_health_status": health.get("status", "MISSING"),
            "model_group_acceptance_status": model_group.get("status", "MISSING"),
            "auto_retrain_readiness": model_group.get("auto_retrain_readiness", "MISSING"),
            "model_experiment_result_status": result_report.get("status", "MISSING"),
            "pass_to_next": (result_report.get("summary") or {}).get("pass_to_next", []),
            "blocked": blockers,
            "warnings": warnings,
        },
        "artifacts": {
            "model_health_report": repo_path(health_path),
            "model_group_acceptance": repo_path(model_group_path),
            "model_experiment_result_report": repo_path(result_report_path),
            "feature_experiment_gate": repo_path(ARTIFACTS_DIR / f"feature_experiment_gate_{args.date}.json"),
            "model_research_flow": repo_path(MODEL_EXPERIMENTS_DIR / f"model_research_flow_{args.date}.json"),
        },
        "steps": steps,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    readiness = payload["readiness"]
    lines = [
        "# Training Automation Readiness",
        "",
        f"- status：`{payload['status']}`",
        f"- date：`{payload['date']}`",
        f"- auto_retrain_enabled：`{readiness['auto_retrain_enabled']}`",
        f"- auto_retrain_readiness：`{readiness['auto_retrain_readiness']}`",
        f"- model_health_status：`{readiness['model_health_status']}`",
        f"- result_report_status：`{readiness['model_experiment_result_status']}`",
        "",
        "## Blockers",
        "",
    ]
    blockers = readiness.get("blocked") or []
    lines.extend([f"- {item}" for item in blockers] if blockers else ["- none"])
    lines.extend(["", "## Warnings", ""])
    warnings = readiness.get("warnings") or []
    lines.extend([f"- {item}" for item in warnings] if warnings else ["- none"])
    lines.extend(["", "## Steps", "", "| Step | Status |", "|---|---|"])
    for step in payload["steps"]:
        lines.append(f"| `{step['name']}` | `{step['status']}` |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    steps: list[dict[str, Any]] = []
    steps.extend(research_flow_step(args))
    steps.extend(run_step(name, command, args.timeout_seconds) for name, command in CORE_CHECKS)
    steps.extend(build_result_report_steps(args))
    payload = build_payload(args, steps)
    output_path = resolve_path(args.output) or ARTIFACTS_DIR / f"training_automation_readiness_{args.date}.json"
    if output_path is None:
        raise RuntimeError("output path resolution failed")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output_path.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "output": repo_path(output_path),
                "blocked": payload["readiness"]["blocked"],
                "warnings": payload["readiness"]["warnings"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if payload["status"] != "FAILED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
