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
READY_AUTO_RETRAIN_STATES = {"READY", "READY_WITH_MONITORING_WARNINGS"}
REVENUE_FEATURES = {"revenue_yoy", "revenue_mom"}


CHECKS: tuple[tuple[str, list[str]], ...] = (
    ("model.foundation", ["scripts/verify_model_foundation.py"]),
    ("sealed_oos.unit", ["scripts/verify_sealed_oos_gate.py"]),
    ("production.write_guard", ["scripts/verify_production_write_guard.py"]),
    ("review.regressions", ["scripts/verify_review_fixes.py"]),
    ("data.pipeline.validate", ["-m", "app.pipeline_cli", "validate", "--json"]),
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
    auto_retrain_readiness, readiness_reason, readiness_warnings = assess_auto_retrain_readiness(health)
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
        "auto_retrain_readiness_reason": readiness_reason,
        "auto_retrain_readiness_warnings": readiness_warnings,
        "steps": steps,
        "health_report": {
            "path": str(ARTIFACTS_DIR / "model_health_report_latest.json"),
            "status": health_status,
            "checks": health.get("checks", []),
        },
        "notes": [
            "status=OK 代表模型組驗證入口可營運；不代表 auto retrain 可開啟。",
            "auto_retrain_readiness=READY_WITH_MONITORING_WARNINGS 代表可進訓練啟動 review；promotion 仍需後續 gate。",
            "auto_retrain_readiness=BLOCKED 時，必須先處理 model health CRITICAL/未分類 WARN 來源。",
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
    if auto_retrain_enabled and auto_retrain_readiness not in READY_AUTO_RETRAIN_STATES:
        return "FAILED"
    return "OK"


def assess_auto_retrain_readiness(health: dict[str, Any]) -> tuple[str, str, list[dict[str, Any]]]:
    """把可接受的監控降級和真 blocker 拆開。

    這裡只判斷「是否可進入訓練啟動 review」。即使回傳
    READY_WITH_MONITORING_WARNINGS，正式 promotion 仍需 sealed OOS、replay、
    no-hindsight 與 retrain promotion gate。
    """

    health_status = str(health.get("status", "MISSING")).upper()
    checks = [row for row in health.get("checks", []) if isinstance(row, dict)]
    non_ok = [row for row in checks if str(row.get("status", "")).upper() != "OK"]
    if health_status == "OK" and not non_ok:
        return "READY", "model health OK", []
    if health_status not in {"WARN", "OK"}:
        return "BLOCKED", f"model health is {health_status}", non_ok

    baseline = health.get("baseline") if isinstance(health.get("baseline"), dict) else {}
    skipped = {str(item) for item in baseline.get("skipped_empty_model_features") or []}
    missing = {str(item) for item in baseline.get("missing_model_features") or []}

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for row in non_ok:
        name = str(row.get("name"))
        status = str(row.get("status", "")).upper()
        if status in {"CRITICAL", "FAILED"}:
            rejected.append(row)
        elif name == "monitor.psi_baseline" and not missing and skipped and skipped.issubset(REVENUE_FEATURES):
            accepted.append(
                {
                    **row,
                    "readiness_category": "data_unavailable_with_explicit_degradation",
                    "reason": "月營收特徵目前全空；允許 technical-only training launch review，但不可據此 promotion。",
                }
            )
        elif name == "monitor.factor":
            accepted.append(
                {
                    **row,
                    "readiness_category": "acceptable_monitoring_warning",
                    "reason": "factor monitor warning 由 retrain promotion gate 擋正式升版；不阻塞訓練啟動。",
                }
            )
        elif name == "ranking.realized_outcome":
            accepted.append(
                {
                    **row,
                    "readiness_category": "acceptable_monitoring_warning",
                    "reason": "10d outcome 尚未成熟；不當作模型失敗。",
                }
            )
        else:
            rejected.append(row)

    if rejected:
        return "BLOCKED", "unclassified or critical model health checks", rejected
    if accepted:
        return "READY_WITH_MONITORING_WARNINGS", "only accepted monitoring warnings remain", accepted
    return "BLOCKED", f"model health is {health_status}", non_ok


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
