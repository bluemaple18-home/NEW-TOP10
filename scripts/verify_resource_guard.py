#!/usr/bin/env python3
"""驗證本機資源 guard 不會誤觸正式長任務。

此腳本使用 TemporaryDirectory 與 monkeypatch，不讀寫正式模型與資料。
它只驗證 automation 控制流：local_safe 會擋正式 retrain、擋無日期窗 daily，
且 monitor 會跳過重型 industry momentum。
"""

from __future__ import annotations

import json
import plistlib
import sys
import tempfile
from pathlib import Path
from types import MethodType

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import scripts.run_automation as automation


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
                "execution:",
                '  resource_profile: "standard"',
                "daily:",
                "  enabled: true",
                "  weekend_enabled: true",
                "retrain:",
                "  enabled: true",
                "monitor:",
                "  enabled: true",
            ]
        ),
        encoding="utf-8",
    )
    (root / "models" / "latest_lgbm.pkl").write_bytes(b"stable-model")


def _with_temp_runner(mode: str, profile: str, dry_run: bool = False) -> automation.AutomationRunner:
    return automation.AutomationRunner(mode=mode, dry_run=dry_run, resource_profile=profile)


def _run_guard_cases() -> list[dict[str, object]]:
    cases: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="top10-resource-guard-") as tmp:
        temp_root = Path(tmp)
        _prepare_temp_project(temp_root)
        original_root = automation.PROJECT_ROOT
        original_status_path = automation.STATUS_PATH
        automation.PROJECT_ROOT = temp_root
        automation.STATUS_PATH = temp_root / "artifacts" / "automation_status.json"
        try:
            retrain_runner = _with_temp_runner("retrain", "local_safe")
            retrain_exit = retrain_runner.run()
            cases.append(
                {
                    "case": "local_safe_blocks_formal_retrain",
                    "passed": retrain_exit == 1
                    and any(step.name == "resource_guard.retrain" and step.status == "FAILED" for step in retrain_runner.status.steps),
                    "exit_code": retrain_exit,
                    "steps": [{"name": step.name, "status": step.status} for step in retrain_runner.status.steps],
                }
            )

            daily_runner = _with_temp_runner("daily", "local_safe")
            daily_exit = daily_runner.run()
            cases.append(
                {
                    "case": "local_safe_blocks_daily_without_window",
                    "passed": daily_exit == 1
                    and any(step.name == "resource_guard.daily" and step.status == "FAILED" for step in daily_runner.status.steps),
                    "exit_code": daily_exit,
                    "steps": [{"name": step.name, "status": step.status} for step in daily_runner.status.steps],
                }
            )

            monitor_runner = _with_temp_runner("monitor", "local_safe")

            def fake_run_command(
                self: automation.AutomationRunner,
                name: str,
                command: list[str],
                allow_failure: bool = False,
            ) -> None:
                self._record_step(name, "OK", message="injected lightweight command")

            monitor_runner._run_command = MethodType(fake_run_command, monitor_runner)
            monitor_exit = monitor_runner.run()
            cases.append(
                {
                    "case": "local_safe_skips_heavy_industry_monitor",
                    "passed": monitor_exit == 0
                    and any(
                        step.name == "industry_momentum.monitor" and step.status == "SKIPPED"
                        for step in monitor_runner.status.steps
                    ),
                    "exit_code": monitor_exit,
                    "steps": [{"name": step.name, "status": step.status} for step in monitor_runner.status.steps],
                }
            )
        finally:
            automation.PROJECT_ROOT = original_root
            automation.STATUS_PATH = original_status_path
    return cases


def _run_schedule_entry_cases() -> list[dict[str, object]]:
    cases: list[dict[str, object]] = []
    cron_text = (PROJECT_ROOT / "scripts" / "setup_cron.sh").read_text(encoding="utf-8")
    cron_expected = "TOP10_RESOURCE_PROFILE=host_full bash scripts/daily_retrain.sh monitor --trigger scheduled"
    cases.append(
        {
            "case": "cron_monitor_uses_host_full",
            "passed": cron_expected in cron_text,
            "expected": cron_expected,
        }
    )

    plist_path = PROJECT_ROOT / "scripts" / "com.new-top10.retrain.plist"
    with plist_path.open("rb") as handle:
        retrain_plist = plistlib.load(handle)
    program_args = retrain_plist.get("ProgramArguments", [])
    env = retrain_plist.get("EnvironmentVariables", {})
    cases.append(
        {
            "case": "launchd_monitor_uses_host_full",
            "passed": env.get("TOP10_RESOURCE_PROFILE") == "host_full"
            and program_args == [
                "/bin/bash",
                "__PROJECT_DIR__/scripts/daily_retrain.sh",
                "monitor",
                "--trigger",
                "scheduled",
            ],
            "env": env,
            "program_args": program_args,
        }
    )
    return cases


def main() -> int:
    cases = _run_guard_cases() + _run_schedule_entry_cases()
    ok = all(bool(case["passed"]) for case in cases)
    output_path = PROJECT_ROOT / "artifacts" / "resource_guard_latest.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                "schema_version": "resource-guard-verification.v1",
                "status": "OK" if ok else "FAILED",
                "cases": cases,
                "note": "uses TemporaryDirectory and does not run ETL, retrain, or heavy monitor",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    if ok:
        print(f"RESOURCE_GUARD_OK output={output_path}")
        return 0
    print(f"RESOURCE_GUARD_FAILED output={output_path}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
