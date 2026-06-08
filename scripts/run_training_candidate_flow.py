#!/usr/bin/env python3
"""安全執行自動訓練候選流程。

這支腳本只產生 candidate model artifact，不覆蓋 `models/latest_lgbm.pkl`，
不刷新正式 baseline，不跑 production ranking。候選是否能升版仍必須另走
sealed OOS / replay / rollback / promotion review。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
MODEL_EXPERIMENTS_DIR = ARTIFACTS_DIR / "model_experiments"
SCHEMA_VERSION = "training-candidate-flow.v1"
LATEST_MODEL = PROJECT_ROOT / "models" / "latest_lgbm.pkl"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="run safe training candidate flow")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--candidate-id", default=None)
    parser.add_argument("--readiness", default=None)
    parser.add_argument("--data-dir", default="data/clean")
    parser.add_argument("--horizon", type=int, default=10)
    parser.add_argument("--threshold", type=float, default=0.05)
    parser.add_argument("--optuna-trials", type=int, default=None)
    parser.add_argument("--sealed-trade-days", type=int, default=None)
    parser.add_argument("--min-train-trade-days", type=int, default=None)
    parser.add_argument("--min-sealed-trade-days", type=int, default=None)
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


def read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_candidate_config(args: argparse.Namespace, root: Path) -> Path:
    """建立候選訓練專用 config，不修改 production config/automation.yaml。"""

    source = PROJECT_ROOT / "config" / "automation.yaml"
    config = yaml.safe_load(source.read_text(encoding="utf-8")) if source.exists() else {}
    if not isinstance(config, dict):
        config = {}
    retrain = config.get("retrain") if isinstance(config.get("retrain"), dict) else {}
    sealed = retrain.get("sealed_oos") if isinstance(retrain.get("sealed_oos"), dict) else {}
    sealed = dict(sealed)
    if args.sealed_trade_days is not None:
        sealed["sealed_trade_days"] = args.sealed_trade_days
    if args.min_train_trade_days is not None:
        sealed["min_train_trade_days"] = args.min_train_trade_days
    if args.min_sealed_trade_days is not None:
        sealed["min_sealed_trade_days"] = args.min_sealed_trade_days
    retrain = {**retrain, "sealed_oos": sealed}
    config["retrain"] = retrain
    output = root / "candidate_automation.yaml"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return output


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_step(name: str, command: list[str], env_overrides: dict[str, str] | None = None) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return {
        "name": name,
        "status": "OK" if completed.returncode == 0 else "FAILED",
        "returncode": completed.returncode,
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "command": command,
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
    }


def readiness_ok(path: Path) -> tuple[bool, dict[str, Any]]:
    payload = read_json(path)
    readiness = payload.get("readiness") if isinstance(payload.get("readiness"), dict) else {}
    ok = (
        payload.get("status") == "READY_FOR_AUTOMATED_TRAINING_REVIEW"
        and readiness.get("training_launch_ready") is True
        and readiness.get("promotion_ready") is False
        and not readiness.get("blocked")
    )
    return ok, {
        "path": repo_path(path),
        "exists": path.exists(),
        "status": payload.get("status", "MISSING"),
        "training_launch_ready": readiness.get("training_launch_ready"),
        "promotion_ready": readiness.get("promotion_ready"),
        "blocked": readiness.get("blocked", []),
    }


def candidate_root(args: argparse.Namespace) -> Path:
    candidate_id = args.candidate_id or f"candidate_{args.date}"
    return MODEL_EXPERIMENTS_DIR / "training_candidates" / candidate_id


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    run_date = args.date
    root = candidate_root(args)
    candidate_model_dir = root / "models"
    candidate_artifact_dir = root / "artifacts"
    candidate_model = candidate_model_dir / "latest_lgbm.pkl"
    candidate_config = write_candidate_config(args, root)
    readiness_path = resolve_path(args.readiness) or ARTIFACTS_DIR / f"training_automation_readiness_{run_date}.json"
    output_path = resolve_path(args.output) or root / "training_candidate_flow.json"
    before_hash = sha256(LATEST_MODEL)
    ready, readiness_summary = readiness_ok(readiness_path)
    steps: list[dict[str, Any]] = []
    errors: list[str] = []

    if not ready:
        errors.append("training readiness is not READY_FOR_AUTOMATED_TRAINING_REVIEW")
    else:
        train_command = [
            sys.executable,
            "-m",
            "app.agent_b_modeling",
            "--data-dir",
            args.data_dir,
            "--model-dir",
            repo_path(candidate_model_dir) or str(candidate_model_dir),
            "--artifact-dir",
            repo_path(candidate_artifact_dir) or str(candidate_artifact_dir),
            "--config",
            repo_path(candidate_config) or str(candidate_config),
            "--horizon",
            str(args.horizon),
            "--threshold",
            str(args.threshold),
        ]
        if args.optuna_trials is not None:
            train_command.extend(["--optuna-trials", str(args.optuna_trials)])
        train_step = run_step(
            "candidate.train",
            train_command,
            env_overrides={
                "MLFLOW_TRACKING_URI": f"sqlite:///{(candidate_artifact_dir / 'mlflow.db').resolve()}",
                "PYTHONPYCACHEPREFIX": "/private/tmp/top10_pycache",
            },
        )
        steps.append(train_step)
        if train_step["status"] == "OK":
            sealed_output = candidate_artifact_dir / "sealed_oos_report.json"
            sealed_step = run_step(
                "candidate.sealed_oos",
                [
                    sys.executable,
                    "scripts/run_sealed_oos_gate.py",
                    "--model",
                    repo_path(candidate_model) or str(candidate_model),
                    "--artifact-dir",
                    repo_path(candidate_artifact_dir) or str(candidate_artifact_dir),
                    "--config",
                    repo_path(candidate_config) or str(candidate_config),
                    "--output",
                    repo_path(sealed_output) or str(sealed_output),
                ],
            )
            steps.append(sealed_step)
        else:
            errors.append("candidate training failed")

    after_hash = sha256(LATEST_MODEL)
    candidate_hash = sha256(candidate_model)
    if before_hash != after_hash:
        errors.append("models/latest_lgbm.pkl hash changed")
    if ready and candidate_hash is None:
        errors.append("candidate model was not created")

    sealed_report = read_json(candidate_artifact_dir / "sealed_oos_report.json")
    promotion_ready = False
    status = "OK" if not errors and all(step["status"] == "OK" for step in steps) else "FAILED"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": run_date,
        "status": status,
        "contract": {
            "candidate_training_only": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_refresh_production_baseline": True,
            "does_not_run_production_ranking": True,
            "does_not_enable_auto_retrain": True,
            "production_promotion_allowed": False,
        },
        "candidate_config": {
            "path": repo_path(candidate_config),
            "sealed_trade_days": args.sealed_trade_days,
            "min_train_trade_days": args.min_train_trade_days,
            "min_sealed_trade_days": args.min_sealed_trade_days,
        },
        "readiness": readiness_summary,
        "candidate": {
            "root": repo_path(root),
            "model": repo_path(candidate_model),
            "model_exists": candidate_model.exists(),
            "model_sha256": candidate_hash,
            "artifact_dir": repo_path(candidate_artifact_dir),
            "sealed_oos_report": repo_path(candidate_artifact_dir / "sealed_oos_report.json"),
            "sealed_oos_status": sealed_report.get("status", "NOT_RUN"),
        },
        "guards": {
            "models_latest_before_sha256": before_hash,
            "models_latest_after_sha256": after_hash,
            "models_latest_changed": before_hash != after_hash,
            "promotion_ready": promotion_ready,
        },
        "steps": steps,
        "errors": errors,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Training Candidate Flow",
        "",
        f"- status: `{payload['status']}`",
        f"- date: `{payload['date']}`",
        f"- readiness: `{payload['readiness'].get('status')}`",
        f"- candidate_model: `{payload['candidate'].get('model')}`",
        f"- candidate_sealed_oos_status: `{payload['candidate'].get('sealed_oos_status')}`",
        f"- models_latest_changed: `{payload['guards'].get('models_latest_changed')}`",
        f"- promotion_ready: `{payload['guards'].get('promotion_ready')}`",
        "",
        "## Steps",
        "",
        "| Step | Status |",
        "|---|---|",
    ]
    for step in payload["steps"]:
        lines.append(f"| `{step['name']}` | `{step['status']}` |")
    lines.extend(["", "## Errors", ""])
    lines.extend([f"- {item}" for item in payload["errors"]] or ["- none"])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output_path = resolve_path(args.output) or candidate_root(args) / "training_candidate_flow.json"
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
                "candidate_model": payload["candidate"]["model"],
                "sealed_oos_status": payload["candidate"]["sealed_oos_status"],
                "models_latest_changed": payload["guards"]["models_latest_changed"],
                "promotion_ready": payload["guards"]["promotion_ready"],
                "errors": payload["errors"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
