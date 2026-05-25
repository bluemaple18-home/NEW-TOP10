#!/usr/bin/env python3
"""NEW-TOP10 自動化統一入口。

Shell/launchd 只負責啟動這支程式；流程、狀態與設定集中在這裡。
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = PROJECT_ROOT / "artifacts" / "automation_status.json"
STATUS_SCHEMA_VERSION = "daily-run-status.v1"


@dataclass
class StepResult:
    name: str
    status: str
    command: list[str] | None = None
    message: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    exit_code: int | None = None


@dataclass
class AutomationStatus:
    schema_version: str
    mode: str
    status: str
    dry_run: bool
    started_at: str
    run_date: str
    finished_at: str | None = None
    skip_reason: str | None = None
    steps: list[StepResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class AutomationRunner:
    def __init__(self, mode: str, dry_run: bool = False):
        self.mode = mode
        self.dry_run = dry_run
        self.config = self._load_config()
        self.tz = ZoneInfo(self.config.get("timezone", "Asia/Taipei"))
        self.run_date = self._today_local().strftime("%Y-%m-%d")
        self.status = AutomationStatus(
            schema_version=STATUS_SCHEMA_VERSION,
            mode=mode,
            status="RUNNING",
            dry_run=dry_run,
            started_at=self._now(),
            run_date=self.run_date,
            metadata={"project_root": str(PROJECT_ROOT)},
        )

    def run(self) -> int:
        try:
            self._preflight()
            if self.mode == "daily":
                self._run_daily()
            elif self.mode == "monitor":
                self._run_monitor()
            elif self.mode == "retrain":
                self._run_retrain()
            elif self.mode == "reference":
                self._run_reference()
            elif self.mode == "status":
                self._run_status()
            else:
                raise ValueError(f"未知模式：{self.mode}")
        except Exception as exc:
            self.status.status = "FAILED"
            self.status.errors.append(str(exc))
            self._write_status()
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

        if self.status.status == "RUNNING":
            self.status.status = "OK"
        self._write_status()
        return 0

    def _run_daily(self) -> None:
        daily_config = self.config.get("daily", {})
        if not daily_config.get("enabled", True):
            self._skip("daily.disabled", "config daily.enabled=false")
            return

        if self._should_skip_non_trading_day(daily_config):
            self._skip("daily.trading_day_gate", f"non_trading_day weekday={self._today_local().weekday()}")
            return

        self._daily_preflight()
        self._run_command("etl", ["python", "-m", "app.pipeline_cli", "run"])
        self._run_command("data.validate", ["python", "-m", "app.pipeline_cli", "validate"])
        self._record_data_freshness("data.freshness.after_etl")
        self._run_command("ranking", ["python", "-m", "app.agent_b_ranking"])
        self._record_latest_ranking("ranking.artifact")
        ranking_path = self._expected_ranking_path()
        self._run_weekly_snapshot(daily_config, ranking_path)
        report_path = self._run_daily_report(daily_config, ranking_path)
        self._run_clawd_payload(daily_config, report_path)
        self._record_step("api.cache.clear", "SKIPPED", message="如 API 常駐，請由服務自行呼叫 POST /api/cache/clear")
        self._run_daily_postcheck(daily_config)

    def _run_monitor(self) -> None:
        if not self.config.get("monitor", {}).get("enabled", True):
            self._record_step("monitor.disabled", "SKIPPED", message="config monitor.enabled=false")
            return
        self._run_command("psi.monitor", ["python", "-m", "app.model_monitor"])
        self._run_command("factor.monitor", ["python", "scripts/monitor_factors.py"])
        self._run_command("industry_momentum.monitor", ["python", "scripts/monitor_industry_momentum.py"])

    def _run_retrain(self) -> None:
        if not self.config.get("retrain", {}).get("enabled", True):
            self._record_step("retrain.disabled", "SKIPPED", message="config retrain.enabled=false")
            return

        self._backup_model()
        self._run_command("model.train", ["python", "-m", "app.agent_b_modeling"])
        self._run_monitor()
        self._cleanup_backups()

    def _run_reference(self) -> None:
        if not self.config.get("reference", {}).get("enabled", True):
            self._record_step("reference.disabled", "SKIPPED", message="config reference.enabled=false")
            return
        self._run_command("reference.probe", ["python", "scripts/probe_reference_sources.py"])
        self._run_command("reference.import", ["python", "scripts/import_reference_sources.py", "--allow-partial"])

    def _run_status(self) -> None:
        self._run_command("data.validate", ["python", "-m", "app.pipeline_cli", "validate"])
        self._record_step("status", "OK", message="狀態檢查完成")

    def _run_daily_postcheck(self, daily_config: dict[str, Any]) -> None:
        if not daily_config.get("postcheck_enabled", False):
            self._record_step("daily.postcheck", "SKIPPED", message="config daily.postcheck_enabled=false")
            return

        command = ["python", "scripts/run_daily_postcheck.py"]
        if not daily_config.get("postcheck_api_enabled", True):
            command.append("--skip-api")
        if daily_config.get("postcheck_frontend_enabled", False):
            command.append("--include-frontend")
        self._run_command("daily.postcheck", command)

    def _run_weekly_snapshot(self, daily_config: dict[str, Any], ranking_path: Path) -> None:
        if not daily_config.get("weekly_snapshot_enabled", True):
            self._record_step("weekly.snapshot", "SKIPPED", message="config daily.weekly_snapshot_enabled=false")
            return
        command = ["python", "scripts/build_weekly_candidate_snapshot.py", "--ranking", str(ranking_path)]
        self._run_command("weekly.snapshot", command)

    def _run_daily_report(self, daily_config: dict[str, Any], ranking_path: Path) -> Path | None:
        report_path = PROJECT_ROOT / "artifacts" / f"daily_report_{self._latest_feature_date()}.json"
        self.status.metadata["expected_daily_report_artifact"] = str(report_path)
        if not daily_config.get("daily_report_enabled", True):
            self._record_step("daily.report", "SKIPPED", message="config daily.daily_report_enabled=false")
            return None

        command = ["python", "scripts/generate_daily_report.py", "--ranking", str(ranking_path)]
        self._run_command("daily.report", command)
        if not self.dry_run:
            if not report_path.exists():
                self._record_step("daily.report.artifact", "FAILED", message=f"missing expected daily report: {report_path}")
                raise RuntimeError(f"daily report completed but expected artifact is missing: {report_path}")
            self.status.metadata["daily_report_artifact"] = str(report_path)
            self._record_step("daily.report.artifact", "OK", message=str(report_path))
        return report_path

    def _run_clawd_payload(self, daily_config: dict[str, Any], report_path: Path | None) -> None:
        payload_path = PROJECT_ROOT / "artifacts" / f"clawd_publish_payload_{self._latest_feature_date()}.json"
        message_path = PROJECT_ROOT / "artifacts" / f"clawd_publish_message_{self._latest_feature_date()}.md"
        self.status.metadata["expected_clawd_publish_payload"] = str(payload_path)
        self.status.metadata["expected_clawd_publish_message"] = str(message_path)
        if not daily_config.get("clawd_payload_enabled", True):
            self._record_step("clawd.payload", "SKIPPED", message="config daily.clawd_payload_enabled=false")
            return
        if report_path is None:
            self._record_step("clawd.payload", "SKIPPED", message="daily report disabled; no source report")
            return

        notify_config = self.config.get("notify", {})
        command = ["python", "scripts/build_clawd_publish_payload.py", "--report", str(report_path)]
        channel = notify_config.get("clawd_channel")
        target = notify_config.get("clawd_to")
        if channel:
            command.extend(["--channel", str(channel)])
        if target:
            command.extend(["--to", str(target)])
        self._run_command("clawd.payload", command)
        if not self.dry_run:
            missing = [str(path) for path in [payload_path, message_path] if not path.exists()]
            if missing:
                self._record_step("clawd.payload.artifact", "FAILED", message=f"missing expected Clawd artifacts: {missing}")
                raise RuntimeError(f"clawd payload completed but expected artifacts are missing: {missing}")
            self.status.metadata["clawd_publish_payload"] = str(payload_path)
            self.status.metadata["clawd_publish_message"] = str(message_path)
            self._record_step("clawd.payload.artifact", "OK", message=str(payload_path))

    def _preflight(self) -> None:
        self._record_step("preflight.project_root", "OK", message=str(PROJECT_ROOT))
        if shutil.which("uv") is None:
            raise RuntimeError("找不到 uv，請先安裝 uv 或修正 PATH")
        for path in [PROJECT_ROOT / "config" / "automation.yaml", PROJECT_ROOT / "requirements.txt"]:
            if not path.exists():
                raise RuntimeError(f"必要檔案不存在：{path}")
        (PROJECT_ROOT / "artifacts").mkdir(exist_ok=True)
        (PROJECT_ROOT / "logs").mkdir(exist_ok=True)
        (PROJECT_ROOT / "models" / "backup").mkdir(parents=True, exist_ok=True)

    def _daily_preflight(self) -> None:
        self._record_step("daily.schema", "OK", message=STATUS_SCHEMA_VERSION)
        self._record_step("daily.run_date", "OK", message=self.run_date)
        self._record_model_existence()
        self._record_data_freshness("data.freshness.preflight")

    def _should_skip_non_trading_day(self, daily_config: dict[str, Any]) -> bool:
        weekend_enabled = bool(daily_config.get("weekend_enabled", False))
        weekday = self._today_local().weekday()
        # 台股週六、週日不開盤；國定假日 calendar 尚未接入，先由資料新鮮度 gate 揭露。
        return weekday >= 5 and not weekend_enabled

    def _record_model_existence(self) -> None:
        model_path = PROJECT_ROOT / "models" / "latest_lgbm.pkl"
        if model_path.exists():
            self._record_step("model.exists", "OK", message=str(model_path))
            self.status.metadata["model"] = {
                "path": str(model_path),
                "exists": True,
                "mtime": datetime.fromtimestamp(model_path.stat().st_mtime, tz=timezone.utc).isoformat(),
            }
            return
        self._record_step("model.exists", "FAILED", message="models/latest_lgbm.pkl 不存在")
        self.status.metadata["model"] = {"path": str(model_path), "exists": False}
        raise RuntimeError("models/latest_lgbm.pkl 不存在，daily ranking 不可使用 fallback model")

    def _record_data_freshness(self, step_name: str) -> None:
        try:
            import pandas as pd
        except ImportError as exc:
            raise RuntimeError(f"缺少 pandas，無法檢查 data freshness: {exc}") from exc

        clean_dir = PROJECT_ROOT / "data" / "clean"
        required = ["features.parquet", "events.parquet", "universe.parquet"]
        freshness: dict[str, Any] = {"datasets": {}, "max_lag_days": self._daily_max_data_lag_days()}
        stale_errors: list[str] = []

        for filename in required:
            path = clean_dir / filename
            if not path.exists():
                raise RuntimeError(f"必要資料不存在：{path}")
            df = pd.read_parquet(path, columns=None)
            date_col = "trade_date" if "trade_date" in df.columns else "date" if "date" in df.columns else None
            if date_col is None:
                raise RuntimeError(f"{filename} 缺少 date/trade_date 欄位")
            latest = pd.to_datetime(df[date_col]).max().date()
            lag_days = (self._today_local().date() - latest).days
            info = {
                "path": str(path),
                "rows": int(len(df)),
                "date_column": date_col,
                "latest_date": latest.isoformat(),
                "lag_days": int(lag_days),
            }
            freshness["datasets"][filename] = info
            if lag_days > freshness["max_lag_days"]:
                stale_errors.append(f"{filename} latest={latest.isoformat()} lag_days={lag_days}")

        self.status.metadata["data_freshness"] = freshness
        if stale_errors:
            message = "; ".join(stale_errors)
            self._record_step(step_name, "FAILED", message=message)
            raise RuntimeError(f"資料過舊：{message}")
        latest_summary = ", ".join(
            f"{name}:{info['latest_date']} lag={info['lag_days']}"
            for name, info in freshness["datasets"].items()
        )
        self._record_step(step_name, "OK", message=latest_summary)

    def _record_latest_ranking(self, step_name: str) -> None:
        expected_path = self._expected_ranking_path()
        self.status.metadata["expected_ranking_artifact"] = str(expected_path)
        if self.dry_run:
            self._record_step(step_name, "DRY_RUN", message=f"expected={expected_path}")
            return
        if not expected_path.exists():
            self._record_step(step_name, "FAILED", message=f"missing expected ranking artifact: {expected_path}")
            raise RuntimeError(f"ranking subprocess completed but expected artifact is missing: {expected_path}")
        self.status.metadata["ranking_artifact"] = str(expected_path)
        self._record_step(step_name, "OK", message=str(expected_path))

    def _expected_ranking_path(self) -> Path:
        return PROJECT_ROOT / "artifacts" / f"ranking_{self._latest_feature_date()}.csv"

    def _latest_feature_date(self) -> str:
        freshness = self.status.metadata.get("data_freshness", {})
        features = freshness.get("datasets", {}).get("features.parquet", {})
        return features.get("latest_date", self.run_date)

    def _daily_max_data_lag_days(self) -> int:
        return int(self.config.get("daily", {}).get("max_data_lag_days", 7))

    def _skip(self, step_name: str, reason: str) -> None:
        self.status.status = "SKIPPED"
        self.status.skip_reason = reason
        self._record_step(step_name, "SKIPPED", message=reason)

    def _backup_model(self) -> None:
        model_path = PROJECT_ROOT / "models" / "latest_lgbm.pkl"
        if not model_path.exists():
            self._record_step("model.backup", "SKIPPED", message="models/latest_lgbm.pkl 不存在")
            return
        backup_name = f"lgbm_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl"
        backup_path = PROJECT_ROOT / "models" / "backup" / backup_name
        if self.dry_run:
            self._record_step("model.backup", "DRY_RUN", message=str(backup_path))
            return
        shutil.copy2(model_path, backup_path)
        self._record_step("model.backup", "OK", message=str(backup_path))

    def _cleanup_backups(self) -> None:
        keep_days = int(self.config.get("retrain", {}).get("backup_keep_days", 30))
        self._run_command(
            "backup.cleanup",
            ["find", "models/backup", "-name", "lgbm_*.pkl", "-mtime", f"+{keep_days}", "-delete"],
        )

    def _run_command(self, name: str, command: list[str], allow_failure: bool = False) -> None:
        started_at = self._now()
        if self.dry_run:
            self.status.steps.append(
                StepResult(name=name, status="DRY_RUN", command=command, started_at=started_at, finished_at=self._now())
            )
            return

        completed = subprocess.run(command, cwd=PROJECT_ROOT)
        result = StepResult(
            name=name,
            status="OK" if completed.returncode == 0 else "FAILED",
            command=command,
            started_at=started_at,
            finished_at=self._now(),
            exit_code=completed.returncode,
        )
        self.status.steps.append(result)
        if completed.returncode != 0 and not allow_failure:
            raise RuntimeError(f"{name} 失敗，exit_code={completed.returncode}")

    def _record_step(self, name: str, status: str, message: str | None = None) -> None:
        self.status.steps.append(
            StepResult(name=name, status=status, message=message, started_at=self._now(), finished_at=self._now())
        )

    def _write_status(self) -> None:
        self.status.finished_at = self._now()
        STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(self.status)
        STATUS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        if self.mode == "daily":
            summary_path = PROJECT_ROOT / "artifacts" / f"daily_run_summary_{self.run_date}.json"
            summary_path.write_text(
                json.dumps(self._daily_summary_payload(payload), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def _daily_summary_payload(self, status_payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "schema_version": STATUS_SCHEMA_VERSION,
            "run_date": self.run_date,
            "mode": self.mode,
            "status": status_payload["status"],
            "dry_run": self.dry_run,
            "skip_reason": status_payload.get("skip_reason"),
            "started_at": status_payload["started_at"],
            "finished_at": status_payload.get("finished_at"),
            "errors": status_payload.get("errors", []),
            "step_summary": [
                {
                    "name": step["name"],
                    "status": step["status"],
                    "message": step.get("message"),
                    "exit_code": step.get("exit_code"),
                }
                for step in status_payload.get("steps", [])
            ],
            "metadata": status_payload.get("metadata", {}),
        }

    def _load_config(self) -> dict[str, Any]:
        config_path = PROJECT_ROOT / "config" / "automation.yaml"
        if not config_path.exists():
            return {}
        return yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _today_local(self) -> datetime:
        override = os.environ.get("TOP10_RUN_DATE")
        if override:
            return datetime.fromisoformat(override).replace(tzinfo=self.tz)
        return datetime.now(self.tz)


def main() -> int:
    parser = argparse.ArgumentParser(description="NEW-TOP10 automation runner")
    parser.add_argument("mode", choices=["daily", "monitor", "retrain", "reference", "status"])
    parser.add_argument("--dry-run", action="store_true", help="只檢查流程，不執行長任務")
    args = parser.parse_args()
    return AutomationRunner(mode=args.mode, dry_run=args.dry_run).run()


if __name__ == "__main__":
    raise SystemExit(main())
