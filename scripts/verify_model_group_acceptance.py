#!/usr/bin/env python3
"""模型組總驗收入口。

這支腳本只執行既有驗證與只讀健康報告，不訓練模型、不重跑 ranking、
不抓外部資料。它用來回答：模型組目前是否可營運，以及 auto retrain
是否已具備開啟條件。
"""

from __future__ import annotations

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
SCHEMA_VERSION = "model-group-acceptance.v1"


CHECKS: tuple[tuple[str, list[str]], ...] = (
    ("model.foundation", ["scripts/verify_model_foundation.py"]),
    ("sealed_oos.unit", ["scripts/verify_sealed_oos_gate.py"]),
    ("review.regressions", ["scripts/verify_review_fixes.py"]),
    ("data.contracts", ["scripts/verify_data_contracts.py"]),
    ("model.health.unit", ["scripts/verify_model_health_report.py"]),
    ("retrain.rollback", ["scripts/verify_retrain_rollback.py"]),
    ("model.health.report", ["scripts/generate_model_health_report.py"]),
)


def main() -> int:
    run_date = datetime.now().astimezone().strftime("%Y-%m-%d")
    output_path = ARTIFACTS_DIR / f"model_group_acceptance_{run_date}.json"
    steps = [run_check(name, args) for name, args in CHECKS]
    health = read_json(ARTIFACTS_DIR / "model_health_report_latest.json")
    config = read_config()
    commands_ok = all(step["exit_code"] == 0 for step in steps)
    health_status = str(health.get("status", "MISSING")).upper()
    auto_retrain_enabled = bool((config.get("monitor") or {}).get("auto_retrain", False))
    auto_retrain_readiness = "READY" if health_status == "OK" else "BLOCKED"
    status = acceptance_status(commands_ok, auto_retrain_enabled, auto_retrain_readiness)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_date": run_date,
        "status": status,
        "commands_ok": commands_ok,
        "model_health_status": health_status,
        "auto_retrain_enabled": auto_retrain_enabled,
        "auto_retrain_readiness": auto_retrain_readiness,
        "steps": steps,
        "health_report": {
            "path": str(ARTIFACTS_DIR / "model_health_report_latest.json"),
            "status": health_status,
            "checks": health.get("checks", []),
        },
        "notes": [
            "status=OK 代表模型組驗證入口可營運；不代表 auto retrain 可開啟。",
            "auto_retrain_readiness=BLOCKED 時，必須先處理 model health CRITICAL/WARN 來源。",
        ],
    }
    write_json(output_path, payload)
    print(
        "MODEL_GROUP_ACCEPTANCE_{status} health={health} auto_retrain={auto} output={output}".format(
            status=status,
            health=health_status,
            auto=auto_retrain_readiness,
            output=output_path,
        )
    )
    return 0 if status == "OK" else 1


def acceptance_status(commands_ok: bool, auto_retrain_enabled: bool, auto_retrain_readiness: str) -> str:
    if not commands_ok:
        return "FAILED"
    if auto_retrain_enabled and auto_retrain_readiness != "READY":
        return "FAILED"
    return "OK"


def run_check(name: str, args: list[str]) -> dict[str, Any]:
    command = [sys.executable, *args]
    env = os.environ.copy()
    env.setdefault("PYTHONPYCACHEPREFIX", "/private/tmp/top10_pycache")
    started_at = datetime.now(timezone.utc)
    completed = subprocess.run(command, cwd=PROJECT_ROOT, env=env, text=True, capture_output=True)
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


def read_config() -> dict[str, Any]:
    path = PROJECT_ROOT / "config" / "automation.yaml"
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
