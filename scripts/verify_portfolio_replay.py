#!/usr/bin/env python3
"""使用 synthetic ranking / OHLC 驗證重疊持倉 portfolio replay 契約。"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def write_ranking(path: Path, rows: list[tuple[str, str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
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
        for stock_id, stock_name, weight in rows:
            writer.writerow(
                {
                    "stock_id": stock_id,
                    "stock_name": stock_name,
                    "model_prob": "0.6",
                    "risk_adjusted_score": "1.0",
                    "suggested_weight": weight,
                    "max_position_weight": "0.2",
                    "gross_exposure": "0.4",
                }
            )


def price_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    prices = {
        "1111": [100, 102, 104, 106],
        "2222": [50, 51, 52, 53],
        "3333": [30, 31, 32, 33],
        "4444": [40, 39, 38, 37],
        "5555": [20, 21, 22, 23],
    }
    dates = ["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08"]
    for stock_id, closes in prices.items():
        for index, date in enumerate(dates):
            close = closes[index]
            open_ = close - 1
            high = close + 1
            low = close - 2
            if stock_id == "5555" and date == "2026-01-06":
                high = pd.NA
                low = pd.NA
            rows.append(
                {
                    "stock_id": stock_id,
                    "trade_date": date,
                    "open": open_,
                    "high": high,
                    "low": low,
                    "close": close,
                }
            )
    return rows


def drift_price_rows() -> list[dict[str, object]]:
    return [
        {"stock_id": "9999", "trade_date": "2026-02-02", "open": 100, "high": 100, "low": 100, "close": 100},
        {"stock_id": "9999", "trade_date": "2026-02-03", "open": 100, "high": 200, "low": 100, "close": 200},
        {"stock_id": "9999", "trade_date": "2026-02-04", "open": 200, "high": 200, "low": 200, "close": 200},
    ]


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="top10-portfolio-replay-") as tmp:
        root = Path(tmp)
        rankings_dir = root / "artifacts"
        rankings_dir.mkdir()
        write_ranking(rankings_dir / "ranking_2026-01-02.csv", [("1111", "甲", "0.2"), ("2222", "乙", "0.2")])
        write_ranking(
            rankings_dir / "ranking_2026-01-05.csv",
            [("3333", "丙", "0.2"), ("4444", "丁", "0.2"), ("5555", "戊", "0.2")],
        )

        features = pd.DataFrame(price_rows())
        features["trade_date"] = pd.to_datetime(features["trade_date"])
        features_path = root / "features.parquet"
        features.to_parquet(features_path)
        output = root / "portfolio_replay.json"

        completed = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "run_portfolio_replay.py"),
                "--rankings-dir",
                str(rankings_dir),
                "--features",
                str(features_path),
                "--horizon",
                "3",
                "--top-n",
                "3",
                "--max-gross-exposure",
                "0.8",
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

        drift_rankings_dir = root / "drift_artifacts"
        drift_rankings_dir.mkdir()
        with (drift_rankings_dir / "ranking_2026-02-02.csv").open("w", encoding="utf-8", newline="") as handle:
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
                    "stock_id": "9999",
                    "stock_name": "飆",
                    "model_prob": "0.9",
                    "risk_adjusted_score": "2.0",
                    "suggested_weight": "0.5",
                    "max_position_weight": "0.5",
                    "gross_exposure": "0.5",
                }
            )
        drift_features = pd.DataFrame(drift_price_rows())
        drift_features["trade_date"] = pd.to_datetime(drift_features["trade_date"])
        drift_features_path = root / "drift_features.parquet"
        drift_features.to_parquet(drift_features_path)
        drift_output = root / "portfolio_replay_drift.json"
        drift_completed = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "run_portfolio_replay.py"),
                "--rankings-dir",
                str(drift_rankings_dir),
                "--features",
                str(drift_features_path),
                "--horizon",
                "2",
                "--top-n",
                "1",
                "--max-gross-exposure",
                "0.5",
                "--max-position-weight",
                "0.5",
                "--output",
                str(drift_output),
            ],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if drift_completed.returncode != 0:
            print(drift_completed.stdout)
            print(drift_completed.stderr, file=sys.stderr)
            return drift_completed.returncode

        output_text = output.read_text(encoding="utf-8")
        payload = json.loads(output_text)
        drift_payload = json.loads(drift_output.read_text(encoding="utf-8"))
        daily = payload["daily"]
        trades = payload["trades"]
        skipped = payload["skipped"]
        max_positions = max(item["positions"] for item in daily)
        entry_dates = {trade["stock_id"]: trade["entry_date"] for trade in trades}
        ranking_dates = {trade["stock_id"]: trade["ranking_date"] for trade in trades}
        skipped_reasons = {(item.get("stock_id"), item.get("reason")) for item in skipped}
        checks = {
            "schema_ok": payload["schema_version"] == "overlap-portfolio-replay.v1",
            "contract_declares_overlap": payload["contract"]["overlapping_positions"] is True,
            "model_feature_false": payload["contract"]["model_feature"] is False,
            "trade_count": payload["summary"]["trade_count"] == 4,
            "entry_is_next_trade_day_first_bucket": entry_dates.get("1111") == "2026-01-05",
            "entry_is_next_trade_day_second_bucket": entry_dates.get("3333") == "2026-01-06",
            "not_same_day_entry": all(entry_dates[stock_id] != ranking_dates[stock_id] for stock_id in entry_dates),
            "overlapping_positions_exist": max_positions == 4,
            "gross_exposure_capped": payload["summary"]["max_gross_exposure"] <= 0.800001,
            "has_entries_and_exits": any(item["entries"] > 0 for item in daily) and any(item["exits"] > 0 for item in daily),
            "missing_ohlc_skipped": ("5555", "missing_ohlc_bar") in skipped_reasons,
            "missing_ohlc_not_traded": all(trade["stock_id"] != "5555" for trade in trades),
            "equity_curve_moved": payload["summary"]["final_equity"] != 1.0,
            "no_nan_json_literal": "NaN" not in output_text,
            "drift_gross_exposure_capped": drift_payload["summary"]["max_gross_exposure"] <= 0.500001,
            "drift_deleverage_recorded": any(item.get("deleveraged_notional", 0) > 0 for item in drift_payload["daily"]),
        }
        ok = all(checks.values())
        artifact = PROJECT_ROOT / "artifacts" / "portfolio_replay_verification_latest.json"
        artifact.write_text(
            json.dumps(
                {
                    "schema_version": "portfolio-replay-verification.v1",
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
            print(f"PORTFOLIO_REPLAY_OK output={artifact}")
            return 0
        print(f"PORTFOLIO_REPLAY_FAILED output={artifact}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
