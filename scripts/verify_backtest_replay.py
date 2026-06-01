#!/usr/bin/env python3
"""使用 synthetic ranking / OHLC 驗證 production replay 不同日進出場契約。"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKTEST_DIR = PROJECT_ROOT / "artifacts" / "backtest"


def path_is_portable(value: object) -> bool:
    if value is None or not isinstance(value, str):
        return True
    if not value.strip() or "~" in value or "://" in value:
        return False
    path = Path(value)
    if ".." in path.parts:
        return False
    if not path.is_absolute():
        return True
    try:
        path.resolve().relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        return True
    return False


def replay_inputs_portable(payload: dict[str, object]) -> bool:
    inputs = payload.get("inputs", {})
    if not isinstance(inputs, dict):
        return False
    ranking_files = inputs.get("ranking_files", [])
    return (
        path_is_portable(inputs.get("rankings_dir"))
        and path_is_portable(inputs.get("features"))
        and isinstance(ranking_files, list)
        and all(path_is_portable(item) for item in ranking_files)
    )


def latest_big_bull_replay() -> Path | None:
    matches = sorted(BACKTEST_DIR.glob("replay_big_bull_ranking_*.json"))
    return matches[-1] if matches else None


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="top10-backtest-replay-") as tmp:
        root = Path(tmp)
        rankings_dir = root / "artifacts"
        rankings_dir.mkdir()
        ranking_path = rankings_dir / "ranking_2026-01-02.csv"
        with ranking_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "stock_id",
                    "stock_name",
                    "model_prob",
                    "risk_adjusted_score",
                    "suggested_weight",
                    "max_position_weight",
                    "gross_exposure",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "stock_id": "1111",
                    "stock_name": "甲",
                    "model_prob": "0.7",
                    "risk_adjusted_score": "2",
                    "suggested_weight": "0.25",
                    "max_position_weight": "0.2",
                    "gross_exposure": "0.6",
                }
            )
            writer.writerow(
                {
                    "stock_id": "2222",
                    "stock_name": "乙",
                    "model_prob": "0.6",
                    "risk_adjusted_score": "1",
                    "suggested_weight": "0.2",
                    "max_position_weight": "0.2",
                    "gross_exposure": "0.6",
                }
            )
            writer.writerow(
                {
                    "stock_id": "3333",
                    "stock_name": "丙",
                    "model_prob": "0.5",
                    "risk_adjusted_score": "0.5",
                    "suggested_weight": "0.1",
                    "max_position_weight": "0.2",
                    "gross_exposure": "0.6",
                }
            )
            writer.writerow(
                {
                    "stock_id": "4444",
                    "stock_name": "丁",
                    "model_prob": "0.4",
                    "risk_adjusted_score": "0.2",
                    "suggested_weight": "0.05",
                    "max_position_weight": "0.2",
                    "gross_exposure": "0.6",
                }
            )

        features = pd.DataFrame(
            [
                {"stock_id": "1111", "trade_date": "2026-01-02", "open": 100, "high": 101, "low": 99, "close": 100},
                {"stock_id": "1111", "trade_date": "2026-01-06", "open": 111, "high": 115, "low": 105, "close": 108},
                {"stock_id": "2222", "trade_date": "2026-01-02", "open": 50, "high": 51, "low": 49, "close": 50},
                {"stock_id": "2222", "trade_date": "2026-01-05", "open": 50, "high": 50, "low": 45, "close": 46},
                {"stock_id": "2222", "trade_date": "2026-01-06", "open": 46, "high": 47, "low": 44, "close": 45},
                {"stock_id": "3333", "trade_date": "2026-01-02", "open": 30, "high": 31, "low": 29, "close": 30},
                {"stock_id": "3333", "trade_date": "2026-01-05", "open": 30, "high": 33, "low": 29, "close": 32},
                {"stock_id": "3333", "trade_date": "2026-01-07", "open": 32, "high": 34, "low": 31, "close": 33},
                {"stock_id": "4444", "trade_date": "2026-01-02", "open": 40, "high": 41, "low": 39, "close": 40},
                {"stock_id": "4444", "trade_date": "2026-01-05", "open": 40, "high": pd.NA, "low": pd.NA, "close": 42},
                {"stock_id": "4444", "trade_date": "2026-01-06", "open": 42, "high": 45, "low": 41, "close": 44},
            ]
        )
        features["trade_date"] = pd.to_datetime(features["trade_date"])
        features_path = root / "features.parquet"
        features.to_parquet(features_path)
        output = root / "replay.json"

        completed = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "run_backtest_replay.py"),
                "--rankings-dir",
                str(rankings_dir),
                "--features",
                str(features_path),
                "--horizons",
                "1,2",
                "--top-n",
                "4",
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
        output_text = output.read_text(encoding="utf-8")
        payload = json.loads(output_text)
        latest_replay_path = latest_big_bull_replay()
        latest_replay_payload = json.loads(latest_replay_path.read_text(encoding="utf-8")) if latest_replay_path else None
        first_trade = payload["trades"][0]
        portfolio_summary = payload["summary"]["portfolio_by_horizon"]
        skipped_by_stock = {item["stock_id"]: item for item in payload["skipped"] if item.get("reason") == "missing_entry_bar"}
        skipped_exit = {
            (item["stock_id"], item.get("horizon")): item
            for item in payload["skipped"]
            if item.get("reason") == "missing_exit_bar"
        }
        skipped_ohlc = {
            (item["stock_id"], item.get("horizon")): item
            for item in payload["skipped"]
            if item.get("reason") == "missing_ohlc_bar"
        }
        checks = {
            "schema_ok": payload["schema_version"] == "production-replay-backtest.v1",
            "trade_count": payload["summary"]["trade_count"] == 3,
            "entry_is_next_trade_day": first_trade["entry_date"] == "2026-01-05",
            "not_same_day_entry": first_trade["entry_date"] != first_trade["ranking_date"],
            "has_cost_adjusted_return": first_trade["net_return"] < -0.07,
            "horizon_summary": set(payload["summary"]["by_horizon"]) == {"1", "2"},
            "missing_d1_bar_skipped": "1111" in skipped_by_stock,
            "missing_d1_bar_expected_date": skipped_by_stock.get("1111", {}).get("expected_entry_date") == "2026-01-05",
            "no_drift_to_next_stock_bar": all(trade["stock_id"] != "1111" for trade in payload["trades"]),
            "missing_2d_exit_skipped": ("3333", 2) in skipped_exit,
            "missing_2d_exit_expected_date": skipped_exit.get(("3333", 2), {}).get("expected_exit_date") == "2026-01-06",
            "no_exit_drift_to_next_stock_bar": all(
                not (trade["stock_id"] == "3333" and trade["horizon"] == 2 and trade["exit_date"] == "2026-01-07")
                for trade in payload["trades"]
            ),
            "missing_ohlc_skipped": ("4444", 1) in skipped_ohlc and ("4444", 2) in skipped_ohlc,
            "missing_ohlc_expected_dates": skipped_ohlc.get(("4444", 1), {}).get("expected_entry_date") == "2026-01-05"
            and skipped_ohlc.get(("4444", 2), {}).get("expected_exit_date") == "2026-01-06",
            "no_nan_json_literal": "NaN" not in output_text,
            "no_missing_ohlc_trade": all(trade["stock_id"] != "4444" for trade in payload["trades"]),
            "portfolio_summary_exists": set(portfolio_summary) == {"1", "2"},
            "portfolio_observations_exist": len(payload["portfolio"]["observations"]) == 2,
            "equity_curve_exists": len(payload["portfolio"]["equity_curve"]) == 2,
            "contract_declares_bucket_equity_curve": payload["contract"].get("portfolio_equity_curve") == "bucket_only",
            "contract_declares_bucket_policy": payload["contract"].get("portfolio_policy")
            == "per-ranking-date bucket; no overlapping-position rebalance in v1",
            "synthetic_inputs_portable": replay_inputs_portable(payload),
            "latest_big_bull_replay_inputs_portable": latest_replay_payload is None or replay_inputs_portable(latest_replay_payload),
            "weights_are_capped": all(trade["portfolio_weight"] <= 0.2 for trade in payload["trades"]),
            "portfolio_return_is_weighted": portfolio_summary["1"]["observation_count"] == 1
            and -0.05 < portfolio_summary["1"]["avg_portfolio_return"] < 0.05,
        }
        ok = all(checks.values())
        artifact = PROJECT_ROOT / "artifacts" / "backtest_replay_verification_latest.json"
        artifact.write_text(
            json.dumps(
                {
                    "schema_version": "backtest-replay-verification.v1",
                    "status": "OK" if ok else "FAILED",
                    "checks": checks,
                    "note": "uses TemporaryDirectory synthetic ranking and OHLC data",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        if ok:
            print(f"BACKTEST_REPLAY_OK output={artifact}")
            return 0
        print(f"BACKTEST_REPLAY_FAILED output={artifact}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
