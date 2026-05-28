#!/usr/bin/env python3
"""使用 synthetic artifacts 驗證 backtest acceptance report。"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="top10-backtest-acceptance-") as tmp:
        root = Path(tmp)
        portfolio = root / "portfolio_replay_2026-01-01.json"
        persistence = root / "persistence_study_2026-01-01.json"
        output = root / "acceptance_report.json"
        portfolio.write_text(
            json.dumps(
                {
                    "schema_version": "overlap-portfolio-replay.v1",
                    "contract": {
                        "overlapping_positions": True,
                        "group_exposure_policy": "optional",
                        "event_exit_policy": "optional",
                        "model_feature": False,
                    },
                    "inputs": {
                        "max_gross_exposure": 0.65,
                        "max_group_exposure": 0.35,
                        "stop_loss_pct": 0.08,
                        "take_profit_pct": 0.15,
                    },
                    "summary": {
                        "final_equity": 1.02,
                        "total_return": 0.02,
                        "max_drawdown": -0.04,
                        "trade_count": 2,
                        "max_gross_exposure": 0.6,
                        "max_group_exposure": 0.3,
                    },
                    "trades": [
                        {"exit_reason": "stop_loss", "ambiguous_intraday_order": False},
                        {"exit_reason": "take_profit", "ambiguous_intraday_order": False},
                    ],
                },
                ensure_ascii=False,
                allow_nan=False,
            ),
            encoding="utf-8",
        )
        persistence.write_text(
            json.dumps(
                {
                    "schema_version": "candidate-persistence-backtest.v1",
                    "contract": {
                        "model_feature": False,
                        "uses_future_rankings": False,
                    },
                    "summary": {
                        "trade_count": 2,
                        "by_horizon_and_streak": {"1D::1": {"trade_count": 1}},
                        "by_rank_delta_direction": {"1D::new_or_unknown": {"trade_count": 1}},
                    },
                },
                ensure_ascii=False,
                allow_nan=False,
            ),
            encoding="utf-8",
        )
        completed = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "generate_backtest_acceptance_report.py"),
                "--portfolio",
                str(portfolio),
                "--persistence",
                str(persistence),
                "--output",
                str(output),
            ],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            print(completed.stdout)
            print(completed.stderr, file=sys.stderr)
            return completed.returncode

        missing_exposure_portfolio = root / "portfolio_missing_exposure.json"
        missing_exposure_output = root / "acceptance_report_missing_exposure.json"
        missing_exposure_portfolio.write_text(
            json.dumps(
                {
                    "schema_version": "overlap-portfolio-replay.v1",
                    "contract": {
                        "overlapping_positions": True,
                        "group_exposure_policy": "optional",
                        "model_feature": False,
                    },
                    "inputs": {
                        "max_gross_exposure": 0.65,
                        "max_group_exposure": 0.35,
                    },
                    "summary": {
                        "trade_count": 2,
                    },
                    "trades": [],
                },
                ensure_ascii=False,
                allow_nan=False,
            ),
            encoding="utf-8",
        )
        missing_exposure_completed = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "generate_backtest_acceptance_report.py"),
                "--portfolio",
                str(missing_exposure_portfolio),
                "--persistence",
                str(persistence),
                "--output",
                str(missing_exposure_output),
            ],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        missing_exposure_payload = (
            json.loads(missing_exposure_output.read_text(encoding="utf-8")) if missing_exposure_output.exists() else {}
        )

        missing_gross_input_portfolio = root / "portfolio_missing_gross_input.json"
        missing_gross_input_output = root / "acceptance_report_missing_gross_input.json"
        missing_gross_input_portfolio.write_text(
            json.dumps(
                {
                    "schema_version": "overlap-portfolio-replay.v1",
                    "contract": {
                        "overlapping_positions": True,
                        "model_feature": False,
                    },
                    "inputs": {},
                    "summary": {
                        "trade_count": 2,
                        "max_gross_exposure": 999,
                    },
                    "trades": [],
                },
                ensure_ascii=False,
                allow_nan=False,
            ),
            encoding="utf-8",
        )
        missing_gross_input_completed = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "generate_backtest_acceptance_report.py"),
                "--portfolio",
                str(missing_gross_input_portfolio),
                "--persistence",
                str(persistence),
                "--output",
                str(missing_gross_input_output),
            ],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        missing_gross_input_payload = (
            json.loads(missing_gross_input_output.read_text(encoding="utf-8")) if missing_gross_input_output.exists() else {}
        )

        missing_rank_delta_persistence = root / "persistence_missing_rank_delta.json"
        missing_rank_delta_output = root / "acceptance_report_missing_rank_delta.json"
        missing_rank_delta_persistence.write_text(
            json.dumps(
                {
                    "schema_version": "candidate-persistence-backtest.v1",
                    "contract": {
                        "model_feature": False,
                        "uses_future_rankings": False,
                    },
                    "summary": {
                        "trade_count": 2,
                        "by_horizon_and_streak": {"1D::1": {"trade_count": 1}},
                    },
                },
                ensure_ascii=False,
                allow_nan=False,
            ),
            encoding="utf-8",
        )
        missing_rank_delta_completed = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "generate_backtest_acceptance_report.py"),
                "--portfolio",
                str(portfolio),
                "--persistence",
                str(missing_rank_delta_persistence),
                "--output",
                str(missing_rank_delta_output),
            ],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        missing_rank_delta_payload = (
            json.loads(missing_rank_delta_output.read_text(encoding="utf-8")) if missing_rank_delta_output.exists() else {}
        )
        output_text = output.read_text(encoding="utf-8")
        payload = json.loads(output_text)
        checks = {
            "schema_ok": payload["schema_version"] == "backtest-acceptance-report.v1",
            "status_ok": payload["status"] == "OK",
            "portfolio_checks_ok": all(payload["checks"]["portfolio"].values()),
            "persistence_checks_ok": all(payload["checks"]["persistence"].values()),
            "decision_no_production_change": payload["decision"]["production_model_change"] is False
            and payload["decision"]["ranking_score_change"] is False,
            "no_nan_json_literal": "NaN" not in output_text,
            "missing_exposure_metric_fails": missing_exposure_completed.returncode != 0
            and missing_exposure_payload.get("status") == "FAILED",
            "missing_exposure_metric_check_false": missing_exposure_payload.get("checks", {})
            .get("portfolio", {})
            .get("gross_exposure_metric_present")
            is False,
            "missing_group_metric_check_false": missing_exposure_payload.get("checks", {})
            .get("portfolio", {})
            .get("group_exposure_metric_present")
            is False,
            "missing_gross_input_fails": missing_gross_input_completed.returncode != 0
            and missing_gross_input_payload.get("status") == "FAILED",
            "missing_gross_input_check_false": missing_gross_input_payload.get("checks", {})
            .get("portfolio", {})
            .get("gross_exposure_cap_numeric")
            is False,
            "missing_rank_delta_summary_fails": missing_rank_delta_completed.returncode != 0
            and missing_rank_delta_payload.get("status") == "FAILED",
            "missing_rank_delta_check_false": missing_rank_delta_payload.get("checks", {})
            .get("persistence", {})
            .get("rank_delta_direction_summary_exists")
            is False,
        }
        ok = all(checks.values())
        artifact = PROJECT_ROOT / "artifacts" / "backtest_acceptance_verification_latest.json"
        artifact.write_text(
            json.dumps(
                {
                    "schema_version": "backtest-acceptance-verification.v1",
                    "status": "OK" if ok else "FAILED",
                    "checks": checks,
                    "note": "uses TemporaryDirectory synthetic artifacts",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        if ok:
            print(f"BACKTEST_ACCEPTANCE_OK output={artifact}")
            return 0
        print(f"BACKTEST_ACCEPTANCE_FAILED output={artifact}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
