#!/usr/bin/env python3
"""故障注入驗證 retrain 失敗時會回滾正式模型。

此腳本使用 TemporaryDirectory 與 monkeypatch 後的 PROJECT_ROOT，不讀寫正式
`models/latest_lgbm.pkl`。它只驗證 AutomationRunner 的 backup/rollback 控制流。
"""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from types import MethodType
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import scripts.run_automation as automation


ORIGINAL_MODEL_BYTES = b"old-stable-model"
TRAINED_MODEL_BYTES = b"new-unsafe-model"


def _prepare_temp_project(root: Path) -> None:
    (root / "artifacts").mkdir(parents=True)
    (root / "logs").mkdir(parents=True)
    (root / "models" / "backup").mkdir(parents=True)
    (root / "config").mkdir(parents=True)
    (root / "requirements.txt").write_text("", encoding="utf-8")
    (root / "config" / "automation.yaml").write_text(
        "\n".join(
            [
                'timezone: "Asia/Taipei"',
                "retrain:",
                "  enabled: true",
                "  rollback_on_failure: true",
                "  ranking_smoke_enabled: true",
                "  monitor_after_train_enabled: true",
            ]
        ),
        encoding="utf-8",
    )
    (root / "models" / "latest_lgbm.pkl").write_bytes(ORIGINAL_MODEL_BYTES)


def _run_case(case_name: str) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix=f"top10-retrain-rollback-{case_name}-") as tmp:
        temp_root = Path(tmp)
        _prepare_temp_project(temp_root)

        original_root = automation.PROJECT_ROOT
        original_status_path = automation.STATUS_PATH
        automation.PROJECT_ROOT = temp_root
        automation.STATUS_PATH = temp_root / "artifacts" / "automation_status.json"
        try:
            runner = automation.AutomationRunner(mode="retrain", dry_run=False)
            runner.config.setdefault("retrain", {})
            if case_name == "monitor":
                runner.config["retrain"]["ranking_smoke_enabled"] = False

            def fake_preflight(self: automation.AutomationRunner) -> None:
                self._record_step("retrain.preflight.injected", "OK", message=case_name)

            def fake_run_command(self: automation.AutomationRunner, name: str, command: list[str], allow_failure: bool = False) -> None:
                if name == "model.train":
                    (temp_root / "models" / "latest_lgbm.pkl").write_bytes(TRAINED_MODEL_BYTES)
                    self._record_step(name, "OK", message="injected train wrote unsafe model")
                    return
                if case_name == "ranking" and name == "model.ranking_smoke":
                    self._record_step(name, "FAILED", message="injected ranking failure")
                    raise RuntimeError("injected ranking failure")
                self._record_step(name, "OK", message="injected ok")

            def fake_validate(self: automation.AutomationRunner, step_name: str, train_started_at: datetime) -> None:
                if case_name == "validate":
                    self._record_step(step_name, "FAILED", message="injected validate failure")
                    raise RuntimeError("injected validate failure")
                self._record_step(step_name, "OK", message="injected validate ok")

            def fake_monitor(self: automation.AutomationRunner) -> None:
                if case_name == "monitor":
                    self._record_step("psi.monitor", "FAILED", message="injected monitor failure")
                    raise RuntimeError("injected monitor failure")
                self._record_step("psi.monitor", "OK", message="injected monitor ok")

            runner._retrain_preflight = MethodType(fake_preflight, runner)
            runner._run_command = MethodType(fake_run_command, runner)
            runner._validate_retrained_model = MethodType(fake_validate, runner)
            runner._run_monitor = MethodType(fake_monitor, runner)

            error = None
            try:
                runner._run_retrain()
            except RuntimeError as exc:
                error = str(exc)

            model_bytes = (temp_root / "models" / "latest_lgbm.pkl").read_bytes()
            rollback_steps = [step for step in runner.status.steps if step.name == "model.rollback"]
            backup_steps = [step for step in runner.status.steps if step.name == "model.backup"]
            passed = bool(error) and model_bytes == ORIGINAL_MODEL_BYTES and bool(rollback_steps) and rollback_steps[-1].status == "OK"
            return {
                "case": case_name,
                "passed": passed,
                "error": error,
                "backup_status": backup_steps[-1].status if backup_steps else None,
                "rollback_status": rollback_steps[-1].status if rollback_steps else None,
                "restored_original_model": model_bytes == ORIGINAL_MODEL_BYTES,
                "step_summary": [{"name": step.name, "status": step.status, "message": step.message} for step in runner.status.steps],
            }
        finally:
            automation.PROJECT_ROOT = original_root
            automation.STATUS_PATH = original_status_path


def main() -> int:
    cases = [_run_case(case_name) for case_name in ["validate", "ranking", "monitor"]]
    ok = all(bool(case["passed"]) for case in cases)
    run_date = datetime.now(ZoneInfo("Asia/Taipei")).strftime("%Y-%m-%d")
    output_path = automation.PROJECT_ROOT / "artifacts" / f"retrain_rollback_injection_{run_date}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "retrain-rollback-injection.v1",
        "status": "OK" if ok else "FAILED",
        "run_date": run_date,
        "cases": cases,
        "note": "uses TemporaryDirectory and does not touch production models/latest_lgbm.pkl",
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": str(output_path)}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
