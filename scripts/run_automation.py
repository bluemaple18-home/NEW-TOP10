#!/usr/bin/env python3
"""NEW-TOP10 自動化統一入口。

Shell/launchd 只負責啟動這支程式；流程、狀態與設定集中在這裡。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pickle
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
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
    def __init__(self, mode: str, dry_run: bool = False, trigger: str = "manual"):
        self.mode = mode
        self.dry_run = dry_run
        self.trigger = trigger
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
            metadata={"project_root": str(PROJECT_ROOT), "trigger": trigger},
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
        self._run_command("etl", self._pipeline_run_command())
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
        self._run_command("model.health", ["python", "scripts/generate_model_health_report.py"])

    def _run_retrain(self) -> None:
        retrain_config = self.config.get("retrain", {})
        if not retrain_config.get("enabled", True):
            self._record_step("retrain.disabled", "SKIPPED", message="config retrain.enabled=false")
            return

        self._retrain_preflight()
        backup_path = self._backup_model()
        baseline_backup_path = self._backup_baseline()
        train_started_at = datetime.now(timezone.utc)
        self.status.metadata.setdefault("retrain", {})["train_started_at"] = train_started_at.isoformat()

        try:
            self._run_command("model.train", ["python", "-m", "app.agent_b_modeling"])
            self._validate_retrained_model("model.validate", train_started_at)
            if self._sealed_oos_enabled():
                sealed_started_at = datetime.now(timezone.utc)
                self._run_command("model.sealed_oos", ["python", "scripts/run_sealed_oos_gate.py"])
                self._record_sealed_oos_report("model.sealed_oos_artifact", fresh_after=sealed_started_at)
            if retrain_config.get("baseline_refresh_enabled", True):
                self._run_command("model.baseline", ["python", "scripts/refresh_model_baseline.py"])
            if retrain_config.get("ranking_smoke_enabled", True):
                ranking_started_at = datetime.now(timezone.utc)
                self._run_command("model.ranking_smoke", ["python", "-m", "app.agent_b_ranking"])
                self._record_latest_ranking("model.ranking_artifact", fresh_after=ranking_started_at)
            if retrain_config.get("monitor_after_train_enabled", True):
                monitor_started_at = datetime.now(timezone.utc)
                self.status.metadata.setdefault("retrain", {})["monitor_started_at"] = monitor_started_at.isoformat()
                self._run_monitor()
            else:
                monitor_started_at = None
            self._run_retrain_promotion_gate(monitor_started_at)
        except Exception as exc:
            if retrain_config.get("rollback_on_failure", True):
                self._restore_model_backup(backup_path, reason=str(exc))
                self._restore_baseline_backup(baseline_backup_path, reason=str(exc))
            raise
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

    def _pipeline_run_command(self) -> list[str]:
        command = ["python", "-m", "app.pipeline_cli", "run"]
        window: dict[str, str] = {}
        start_date = os.environ.get("TOP10_PIPELINE_START_DATE")
        end_date = os.environ.get("TOP10_PIPELINE_END_DATE")
        if start_date:
            command.extend(["--start-date", start_date])
            window["start_date"] = start_date
        if end_date:
            command.extend(["--end-date", end_date])
            window["end_date"] = end_date
        if window:
            self.status.metadata["pipeline_window"] = window
        return command

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

    def _retrain_preflight(self) -> None:
        self._record_step("retrain.schema", "OK", message=STATUS_SCHEMA_VERSION)
        self._record_step("retrain.run_date", "OK", message=self.run_date)
        self._record_model_existence()
        model_path = PROJECT_ROOT / "models" / "latest_lgbm.pkl"
        self.status.metadata.setdefault("retrain", {})["previous_model"] = self._model_snapshot(model_path)
        self._record_data_freshness("data.freshness.retrain_preflight")
        self._run_command("data.validate", ["python", "-m", "app.pipeline_cli", "validate"])

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
        coverage_errors: list[str] = []

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
            if filename == "features.parquet" and self._market_coverage_enabled():
                market_coverage = self._latest_market_coverage(pd, df, date_col)
                info["latest_market_coverage"] = market_coverage
                for item in market_coverage.get("markets", []):
                    if item.get("status") == "FAILED":
                        coverage_errors.append(
                            "{market} actual={actual} expected={expected} ratio={ratio} < min={minimum}".format(
                                market=item.get("market_type"),
                                actual=item.get("actual_count"),
                                expected=item.get("expected_count"),
                                ratio=item.get("coverage_ratio"),
                                minimum=market_coverage.get("min_coverage_ratio"),
                            )
                        )
            freshness["datasets"][filename] = info
            if lag_days > freshness["max_lag_days"]:
                stale_errors.append(f"{filename} latest={latest.isoformat()} lag_days={lag_days}")

        self.status.metadata["data_freshness"] = freshness
        errors = stale_errors + coverage_errors
        if errors:
            message = "; ".join(errors)
            self._record_step(step_name, "FAILED", message=message)
            raise RuntimeError(f"資料 freshness / 市場覆蓋檢查失敗：{message}")
        latest_summary = ", ".join(
            f"{name}:{info['latest_date']} lag={info['lag_days']}"
            for name, info in freshness["datasets"].items()
        )
        self._record_step(step_name, "OK", message=latest_summary)

    def _market_coverage_enabled(self) -> bool:
        return bool(self.config.get("daily", {}).get("market_coverage_enabled", True))

    def _latest_market_coverage(self, pd: Any, df: Any, date_col: str) -> dict[str, Any]:
        daily_config = self.config.get("daily", {})
        required_markets = [
            str(market).strip().lower()
            for market in daily_config.get("required_market_types", ["twse", "tpex"])
            if str(market).strip()
        ]
        min_ratio = float(daily_config.get("min_latest_market_coverage_ratio", 0.5))
        expected_counts = self._expected_market_counts(pd, required_markets)

        trade_dates = pd.to_datetime(df[date_col], errors="coerce").dt.normalize()
        latest = trade_dates.max()
        latest_df = df[trade_dates == latest].copy()
        if latest_df.empty:
            return {
                "latest_date": None,
                "min_coverage_ratio": min_ratio,
                "markets": [
                    {
                        "market_type": market.upper(),
                        "expected_count": expected_counts.get(market, 0),
                        "actual_count": 0,
                        "coverage_ratio": 0.0,
                        "status": "FAILED",
                    }
                    for market in required_markets
                ],
            }

        if "market" in latest_df.columns:
            latest_df["market_type"] = latest_df["market"].astype(str).str.strip().str.lower()
        else:
            latest_df["market_type"] = latest_df["stock_id"].astype(str).str.strip().map(self._stock_market_map(pd))

        actual_counts = (
            latest_df.dropna(subset=["market_type"])
            .assign(stock_id=lambda frame: frame["stock_id"].astype(str).str.strip())
            .groupby("market_type")["stock_id"]
            .nunique()
            .to_dict()
        )
        markets = []
        for market in required_markets:
            expected = int(expected_counts.get(market, 0))
            actual = int(actual_counts.get(market, 0))
            ratio = round(actual / expected, 4) if expected else 0.0
            status = "OK" if expected > 0 and ratio >= min_ratio else "FAILED"
            markets.append(
                {
                    "market_type": market.upper(),
                    "expected_count": expected,
                    "actual_count": actual,
                    "coverage_ratio": ratio,
                    "status": status,
                }
            )
        return {
            "latest_date": latest.date().isoformat() if pd.notna(latest) else None,
            "min_coverage_ratio": min_ratio,
            "markets": markets,
        }

    def _expected_market_counts(self, pd: Any, required_markets: list[str]) -> dict[str, int]:
        universe_path = PROJECT_ROOT / "data" / "reference" / "tradable_universe.csv"
        if not universe_path.exists():
            return {market: 0 for market in required_markets}
        universe = pd.read_csv(universe_path, dtype={"stock_id": str})
        if universe.empty or "market_type" not in universe.columns:
            return {market: 0 for market in required_markets}
        if "is_active" in universe.columns:
            universe = universe[universe["is_active"].map(self._truthy_value).fillna(True)]
        if "is_etf" in universe.columns:
            universe = universe[~universe["is_etf"].map(self._truthy_value).fillna(False)]
        universe["market_type"] = universe["market_type"].astype(str).str.strip().str.lower()
        counts = universe.groupby("market_type")["stock_id"].nunique().to_dict()
        return {market: int(counts.get(market, 0)) for market in required_markets}

    def _stock_market_map(self, pd: Any) -> dict[str, str]:
        universe_path = PROJECT_ROOT / "data" / "reference" / "tradable_universe.csv"
        if not universe_path.exists():
            return {}
        universe = pd.read_csv(universe_path, dtype={"stock_id": str})
        if universe.empty or "market_type" not in universe.columns:
            return {}
        universe["stock_id"] = universe["stock_id"].astype(str).str.strip()
        universe["market_type"] = universe["market_type"].astype(str).str.strip().str.lower()
        return dict(zip(universe["stock_id"], universe["market_type"], strict=False))

    @staticmethod
    def _truthy_value(value: Any) -> bool | None:
        if isinstance(value, bool):
            return value
        if value is None:
            return None
        text = str(value).strip().lower()
        if text in {"true", "1", "yes", "y"}:
            return True
        if text in {"false", "0", "no", "n"}:
            return False
        return None

    def _record_latest_ranking(self, step_name: str, fresh_after: datetime | None = None) -> None:
        expected_path = self._expected_ranking_path()
        self.status.metadata["expected_ranking_artifact"] = str(expected_path)
        if self.dry_run:
            self._record_step(step_name, "DRY_RUN", message=f"expected={expected_path}")
            return
        if not expected_path.exists():
            self._record_step(step_name, "FAILED", message=f"missing expected ranking artifact: {expected_path}")
            raise RuntimeError(f"ranking subprocess completed but expected artifact is missing: {expected_path}")
        if fresh_after is not None:
            ranking_mtime = datetime.fromtimestamp(expected_path.stat().st_mtime, tz=timezone.utc)
            if ranking_mtime < fresh_after:
                message = f"ranking artifact is stale: mtime={ranking_mtime.isoformat()} fresh_after={fresh_after.isoformat()}"
                self._record_step(step_name, "FAILED", message=message)
                raise RuntimeError(message)
        self.status.metadata["ranking_artifact"] = str(expected_path)
        self._record_step(step_name, "OK", message=str(expected_path))

    def _sealed_oos_enabled(self) -> bool:
        sealed_config = self.config.get("retrain", {}).get("sealed_oos", {})
        if not isinstance(sealed_config, dict):
            return True
        return self._truthy_value(sealed_config.get("enabled", True)) is not False

    def _record_sealed_oos_report(self, step_name: str, fresh_after: datetime | None = None) -> None:
        report_path = PROJECT_ROOT / "artifacts" / "sealed_oos_report_latest.json"
        if self.dry_run:
            self.status.metadata.setdefault("retrain", {})["expected_sealed_oos_report"] = str(report_path)
            self._record_step(step_name, "DRY_RUN", message=str(report_path))
            return
        if not report_path.exists():
            self._record_step(step_name, "FAILED", message=f"missing expected sealed OOS report: {report_path}")
            raise RuntimeError(f"sealed OOS gate completed but expected artifact is missing: {report_path}")
        if fresh_after is not None:
            report_mtime = datetime.fromtimestamp(report_path.stat().st_mtime, tz=timezone.utc)
            if report_mtime + timedelta(seconds=2) < fresh_after:
                message = f"sealed OOS report is stale: mtime={report_mtime.isoformat()} fresh_after={fresh_after.isoformat()}"
                self._record_step(step_name, "FAILED", message=message)
                raise RuntimeError(message)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        status = str(report.get("status", "FAILED")).upper()
        self.status.metadata.setdefault("retrain", {})["sealed_oos_report"] = {
            "path": str(report_path),
            "status": status,
            "failures": report.get("failures", []),
            "metrics": report.get("metrics", {}),
            "split": report.get("split", {}),
        }
        if status != "OK":
            message = f"sealed OOS gate status={status} failures={report.get('failures', [])}"
            self._record_step(step_name, "FAILED", message=message)
            raise RuntimeError(message)
        metrics = report.get("metrics", {})
        self._record_step(
            step_name,
            "OK",
            message="auc={auc} top_n_return_uplift={uplift}".format(
                auc=metrics.get("auc"),
                uplift=metrics.get("top_n_return_uplift"),
            ),
        )

    def _run_retrain_promotion_gate(self, monitor_started_at: datetime | None) -> None:
        retrain_config = self.config.get("retrain", {})
        if self.dry_run:
            self._record_step("retrain.promotion_gate", "DRY_RUN", message=f"trigger={self.trigger}")
            return
        if not retrain_config.get("promotion_gate_enabled", True):
            self._record_step("retrain.promotion_gate", "SKIPPED", message="config retrain.promotion_gate_enabled=false")
            return

        gate_triggers = {str(value) for value in retrain_config.get("promotion_gate_block_triggers", ["auto", "scheduled"])}
        if self.trigger not in gate_triggers:
            self._record_step("retrain.promotion_gate", "SKIPPED", message=f"trigger={self.trigger}")
            return
        if monitor_started_at is None:
            message = "auto retrain promotion gate requires fresh monitor reports"
            self._record_step("retrain.promotion_gate", "FAILED", message=message)
            raise RuntimeError(message)

        psi_path = PROJECT_ROOT / "artifacts" / "psi_report.json"
        factor_path = PROJECT_ROOT / "artifacts" / "factor_monitor_report.json"
        try:
            psi_report = self._read_fresh_json_report(psi_path, monitor_started_at)
            factor_report = self._read_fresh_json_report(factor_path, monitor_started_at)
        except RuntimeError as exc:
            self._record_step("retrain.promotion_gate", "FAILED", message=str(exc))
            raise

        psi_status = str(psi_report.get("status", "UNKNOWN")).upper()
        factor_status = str(factor_report.get("status", "UNKNOWN")).upper()
        factor_summary = factor_report.get("summary") if isinstance(factor_report.get("summary"), dict) else {}
        factor_warn_count = int(factor_summary.get("warn_count") or 0)
        blocked_psi = {str(value).upper() for value in retrain_config.get("promotion_gate_block_psi_statuses", ["CRITICAL"])}
        blocked_factor = {str(value).upper() for value in retrain_config.get("promotion_gate_block_factor_statuses", ["WARN"])}
        max_factor_warn_count = retrain_config.get("promotion_gate_max_factor_warn_count", 0)

        blocked_reasons: list[str] = []
        if psi_status in blocked_psi:
            blocked_reasons.append(f"psi_status={psi_status}")
        if factor_status in blocked_factor:
            blocked_reasons.append(f"factor_status={factor_status}")
        if max_factor_warn_count is not None and factor_warn_count > int(max_factor_warn_count):
            blocked_reasons.append(f"factor_warn_count={factor_warn_count}>{int(max_factor_warn_count)}")

        gate_payload = {
            "trigger": self.trigger,
            "psi_status": psi_status,
            "factor_status": factor_status,
            "factor_warn_count": factor_warn_count,
            "blocked_reasons": blocked_reasons,
            "reports": {"psi": str(psi_path), "factor": str(factor_path)},
        }
        self.status.metadata.setdefault("retrain", {})["promotion_gate"] = gate_payload
        if blocked_reasons:
            message = "auto retrain promotion blocked: " + ", ".join(blocked_reasons)
            self._record_step("retrain.promotion_gate", "FAILED", message=message)
            raise RuntimeError(message)
        self._record_step("retrain.promotion_gate", "OK", message=f"psi={psi_status} factor={factor_status}")

    def _read_fresh_json_report(self, path: Path, fresh_after: datetime) -> dict[str, Any]:
        if not path.exists():
            raise RuntimeError(f"missing monitor report for promotion gate: {path}")
        artifact_mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        # 檔案系統 timestamp 可能有低解析度，保留 2 秒容忍避免同秒寫入誤判。
        if artifact_mtime + timedelta(seconds=2) < fresh_after:
            raise RuntimeError(
                f"stale monitor report for promotion gate: {path} mtime={artifact_mtime.isoformat()} "
                f"fresh_after={fresh_after.isoformat()}"
            )
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise RuntimeError(f"monitor report is not a JSON object: {path}")
        return payload

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

    def _backup_model(self) -> Path | None:
        model_path = PROJECT_ROOT / "models" / "latest_lgbm.pkl"
        if not model_path.exists():
            self._record_step("model.backup", "SKIPPED", message="models/latest_lgbm.pkl 不存在")
            return None
        backup_name = f"lgbm_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl"
        backup_path = PROJECT_ROOT / "models" / "backup" / backup_name
        if self.dry_run:
            self._record_step("model.backup", "DRY_RUN", message=str(backup_path))
            self.status.metadata.setdefault("retrain", {})["expected_backup_model"] = str(backup_path)
            return backup_path
        shutil.copy2(model_path, backup_path)
        self.status.metadata.setdefault("retrain", {})["backup_model"] = self._model_snapshot(backup_path)
        self._record_step("model.backup", "OK", message=str(backup_path))
        return backup_path

    def _restore_model_backup(self, backup_path: Path | None, reason: str) -> None:
        if backup_path is None:
            self._record_step("model.rollback", "SKIPPED", message="no backup model available")
            return
        model_path = PROJECT_ROOT / "models" / "latest_lgbm.pkl"
        if self.dry_run:
            self._record_step("model.rollback", "DRY_RUN", message=f"restore={backup_path} reason={reason}")
            return
        if not backup_path.exists():
            self._record_step("model.rollback", "FAILED", message=f"backup missing: {backup_path}")
            raise RuntimeError(f"模型回滾失敗，備份不存在：{backup_path}")
        shutil.copy2(backup_path, model_path)
        self.status.metadata.setdefault("retrain", {})["rollback"] = {
            "restored_from": str(backup_path),
            "reason": reason,
            "restored_model": self._model_snapshot(model_path),
        }
        self._record_step("model.rollback", "OK", message=f"restored={backup_path}")

    def _backup_baseline(self) -> Path | None:
        baseline_path = PROJECT_ROOT / "models" / "baseline_stats.json"
        if not baseline_path.exists():
            self._record_step("model.baseline.backup", "SKIPPED", message="models/baseline_stats.json 不存在")
            return None
        backup_name = f"baseline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        backup_path = PROJECT_ROOT / "models" / "backup" / backup_name
        if self.dry_run:
            self._record_step("model.baseline.backup", "DRY_RUN", message=str(backup_path))
            self.status.metadata.setdefault("retrain", {})["expected_backup_baseline"] = str(backup_path)
            return backup_path
        shutil.copy2(baseline_path, backup_path)
        self.status.metadata.setdefault("retrain", {})["backup_baseline"] = self._file_snapshot(backup_path)
        self._record_step("model.baseline.backup", "OK", message=str(backup_path))
        return backup_path

    def _restore_baseline_backup(self, backup_path: Path | None, reason: str) -> None:
        if backup_path is None:
            self._record_step("model.baseline.rollback", "SKIPPED", message="no baseline backup available")
            return
        baseline_path = PROJECT_ROOT / "models" / "baseline_stats.json"
        if self.dry_run:
            self._record_step("model.baseline.rollback", "DRY_RUN", message=f"restore={backup_path} reason={reason}")
            return
        if not backup_path.exists():
            self._record_step("model.baseline.rollback", "FAILED", message=f"baseline backup missing: {backup_path}")
            raise RuntimeError(f"baseline 回滾失敗，備份不存在：{backup_path}")
        shutil.copy2(backup_path, baseline_path)
        self.status.metadata.setdefault("retrain", {})["baseline_rollback"] = {
            "restored_from": str(backup_path),
            "reason": reason,
            "restored_baseline": self._file_snapshot(baseline_path),
        }
        self._record_step("model.baseline.rollback", "OK", message=f"restored={backup_path}")

    def _validate_retrained_model(self, step_name: str, train_started_at: datetime) -> None:
        model_path = PROJECT_ROOT / "models" / "latest_lgbm.pkl"
        if self.dry_run:
            self._record_step(step_name, "DRY_RUN", message=str(model_path))
            return
        if not model_path.exists():
            self._record_step(step_name, "FAILED", message="models/latest_lgbm.pkl 不存在")
            raise RuntimeError("model.train completed but models/latest_lgbm.pkl is missing")

        model_mtime = datetime.fromtimestamp(model_path.stat().st_mtime, tz=timezone.utc)
        if model_mtime < train_started_at:
            message = f"model artifact is stale: mtime={model_mtime.isoformat()} train_started={train_started_at.isoformat()}"
            self._record_step(step_name, "FAILED", message=message)
            raise RuntimeError(message)

        with model_path.open("rb") as handle:
            payload = pickle.load(handle)
        if not isinstance(payload, dict):
            self._record_step(step_name, "FAILED", message="new model payload is not dict")
            raise RuntimeError("新模型不是最新 dict 格式，拒絕覆蓋正式模型")

        model = payload.get("model")
        feature_names = payload.get("feature_names")
        if not feature_names and hasattr(model, "feature_name"):
            feature_names = model.feature_name()
        feature_count = len(feature_names or [])
        min_feature_count = int(self.config.get("retrain", {}).get("min_feature_count", 50))
        if feature_count < min_feature_count:
            message = f"feature_count={feature_count} < min_feature_count={min_feature_count}"
            self._record_step(step_name, "FAILED", message=message)
            raise RuntimeError(message)
        if payload.get("metadata") is None:
            self._record_step(step_name, "FAILED", message="new model missing metadata")
            raise RuntimeError("新模型缺少 metadata")

        previous_sha = (self.status.metadata.get("retrain", {}).get("previous_model") or {}).get("sha256")
        new_snapshot = self._model_snapshot(model_path)
        new_snapshot["feature_count"] = feature_count
        new_snapshot["sha256_changed"] = bool(previous_sha and previous_sha != new_snapshot.get("sha256"))
        self.status.metadata.setdefault("retrain", {})["new_model"] = new_snapshot
        self._record_step(step_name, "OK", message=f"features={feature_count} sha256_changed={new_snapshot['sha256_changed']}")

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
        if self.mode == "retrain":
            summary_path = PROJECT_ROOT / "artifacts" / f"retrain_run_summary_{self.run_date}.json"
            summary_path.write_text(
                json.dumps(self._automation_summary_payload(payload), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def _daily_summary_payload(self, status_payload: dict[str, Any]) -> dict[str, Any]:
        return self._automation_summary_payload(status_payload)

    def _automation_summary_payload(self, status_payload: dict[str, Any]) -> dict[str, Any]:
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

    def _model_snapshot(self, path: Path) -> dict[str, Any]:
        return self._file_snapshot(path)

    def _file_snapshot(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {"path": str(path), "exists": False}
        stat = path.stat()
        return {
            "path": str(path),
            "exists": True,
            "size_bytes": stat.st_size,
            "mtime": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            "sha256": self._sha256(path),
        }

    def _sha256(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

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
    parser.add_argument(
        "--trigger",
        choices=["manual", "scheduled", "auto"],
        default="manual",
        help="標記啟動來源；auto/scheduled retrain 會套用 promotion gate",
    )
    args = parser.parse_args()
    return AutomationRunner(mode=args.mode, dry_run=args.dry_run, trigger=args.trigger).run()


if __name__ == "__main__":
    raise SystemExit(main())
