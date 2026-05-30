#!/usr/bin/env python3
"""驗證 retrain 會在備份模型前先擋掉 sealed OOS 資料窗不足。

此驗證只使用 TemporaryDirectory，不讀寫正式 data/ 或 models/。
"""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from types import MethodType
from zoneinfo import ZoneInfo

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import scripts.run_automation as automation


def _write_config(root: Path) -> None:
    (root / "config" / "automation.yaml").write_text(
        "\n".join(
            [
                'timezone: "Asia/Taipei"',
                "daily:",
                "  max_data_lag_days: 999",
                "  market_coverage_enabled: false",
                "retrain:",
                "  enabled: true",
                "  rollback_on_failure: true",
                "  ranking_smoke_enabled: false",
                "  monitor_after_train_enabled: false",
                "  baseline_refresh_enabled: false",
                "  promotion_gate_enabled: false",
                "  sealed_oos:",
                "    enabled: true",
                "    sealed_trade_days: 60",
                "    embargo_trade_days: 10",
                "    min_train_trade_days: 252",
                "    min_sealed_trade_days: 40",
                "    min_sealed_samples: 500",
                "    min_positive_labels: 20",
                "    min_negative_labels: 20",
            ]
        ),
        encoding="utf-8",
    )


def _write_clean_data(root: Path, total_trade_days: int) -> None:
    dates = pd.bdate_range(end="2026-05-29", periods=total_trade_days)
    rows = [
        {"date": date, "stock_id": stock_id}
        for date in dates
        for stock_id in ["2330", "2317"]
    ]
    frame = pd.DataFrame(rows)
    clean_dir = root / "data" / "clean"
    clean_dir.mkdir(parents=True)
    for name in ["features", "events", "universe"]:
        frame.to_parquet(clean_dir / f"{name}.parquet", index=False)


def _prepare_temp_project(root: Path, total_trade_days: int) -> None:
    (root / "artifacts").mkdir(parents=True)
    (root / "logs").mkdir(parents=True)
    (root / "models" / "backup").mkdir(parents=True)
    (root / "models" / "latest_lgbm.pkl").write_bytes(b"stable-model")
    (root / "config").mkdir(parents=True)
    _write_config(root)
    _write_clean_data(root, total_trade_days)


def _runner_case(case_name: str, total_trade_days: int, run_full_retrain: bool) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix=f"top10-sealed-capacity-{case_name}-") as tmp:
        temp_root = Path(tmp)
        _prepare_temp_project(temp_root, total_trade_days)

        original_root = automation.PROJECT_ROOT
        original_status_path = automation.STATUS_PATH
        automation.PROJECT_ROOT = temp_root
        automation.STATUS_PATH = temp_root / "artifacts" / "automation_status.json"
        try:
            runner = automation.AutomationRunner(mode="retrain", dry_run=False, resource_profile="host_full")

            def fake_run_command(self: automation.AutomationRunner, name: str, command: list[str], allow_failure: bool = False) -> None:
                if name == "data.validate":
                    self._record_step(name, "OK", message="injected data.validate")
                    return
                self._record_step(name, "FAILED", message=f"unexpected command: {command}")
                raise RuntimeError(f"unexpected command: {name}")

            runner._run_command = MethodType(fake_run_command, runner)

            error = None
            try:
                if run_full_retrain:
                    runner._run_retrain()
                else:
                    runner._retrain_preflight()
            except RuntimeError as exc:
                error = str(exc)

            steps = [{"name": step.name, "status": step.status, "message": step.message} for step in runner.status.steps]
            capacity = runner.status.metadata.get("retrain", {}).get("sealed_oos_capacity", {})
            return {
                "case": case_name,
                "total_trade_days": total_trade_days,
                "mature_trade_days": capacity.get("mature_trade_days"),
                "error": error,
                "has_backup_step": any(step["name"] == "model.backup" for step in steps),
                "has_train_step": any(step["name"] == "model.train" for step in steps),
                "capacity_step": next((step for step in steps if step["name"] == "sealed_oos.capacity.retrain_preflight"), None),
                "steps": steps,
            }
        finally:
            automation.PROJECT_ROOT = original_root
            automation.STATUS_PATH = original_status_path


def main() -> int:
    cases = [
        _runner_case("insufficient_min_days_blocks_before_backup", total_trade_days=244, run_full_retrain=True),
        _runner_case("configured_window_blocks_before_train", total_trade_days=322, run_full_retrain=False),
        _runner_case("enough_days_passes_preflight", total_trade_days=340, run_full_retrain=False),
    ]

    checks = [
        bool(cases[0]["error"]) and "sealed OOS 交易日不足" in str(cases[0]["error"]) and not cases[0]["has_backup_step"] and not cases[0]["has_train_step"],
        bool(cases[1]["error"]) and "sealed OOS 指定視窗過長" in str(cases[1]["error"]),
        cases[2]["error"] is None and cases[2]["capacity_step"] and cases[2]["capacity_step"]["status"] == "OK",
    ]
    ok = all(checks)
    run_date = datetime.now(ZoneInfo("Asia/Taipei")).strftime("%Y-%m-%d")
    output_path = PROJECT_ROOT / "artifacts" / f"retrain_sealed_oos_capacity_preflight_{run_date}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "retrain-sealed-oos-capacity-preflight.v1",
        "status": "OK" if ok else "FAILED",
        "run_date": run_date,
        "cases": cases,
        "note": "TemporaryDirectory only; verifies capacity gate runs before model backup/train",
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": str(output_path)}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
