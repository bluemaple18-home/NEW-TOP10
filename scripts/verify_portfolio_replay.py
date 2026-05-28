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


def event_price_rows() -> list[dict[str, object]]:
    return [
        {"stock_id": "7777", "trade_date": "2026-03-02", "open": 100, "high": 101, "low": 99, "close": 100},
        {"stock_id": "7777", "trade_date": "2026-03-03", "open": 100, "high": 103, "low": 94, "close": 101},
        {"stock_id": "7777", "trade_date": "2026-03-04", "open": 101, "high": 103, "low": 100, "close": 102},
        {"stock_id": "8888", "trade_date": "2026-03-02", "open": 50, "high": 51, "low": 49, "close": 50},
        {"stock_id": "8888", "trade_date": "2026-03-03", "open": 50, "high": 56, "low": 49, "close": 55},
        {"stock_id": "8888", "trade_date": "2026-03-04", "open": 55, "high": 56, "low": 54, "close": 55},
    ]


def multi_group_price_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index in range(10):
        stock_id = f"66{index:02d}"
        rows.append({"stock_id": stock_id, "trade_date": "2026-04-02", "open": 100, "high": 100, "low": 100, "close": 100})
        rows.append({"stock_id": stock_id, "trade_date": "2026-04-03", "open": 100, "high": 200, "low": 100, "close": 200})
        rows.append({"stock_id": stock_id, "trade_date": "2026-04-06", "open": 200, "high": 200, "low": 200, "close": 200})
    return rows


def write_group_map(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["stock_id", "industry_name"])
        writer.writeheader()
        writer.writerow({"stock_id": "1111", "industry_name": "AI"})
        writer.writerow({"stock_id": "2222", "industry_name": "AI"})
        writer.writerow({"stock_id": "3333", "industry_name": "電力"})
        writer.writerow({"stock_id": "4444", "industry_name": "電力"})
        writer.writerow({"stock_id": "5555", "industry_name": "電力"})
        writer.writerow({"stock_id": "9999", "industry_name": "飆股"})
        writer.writerow({"stock_id": "7777", "industry_name": "事件"})
        writer.writerow({"stock_id": "8888", "industry_name": "事件"})
        for index in range(10):
            writer.writerow({"stock_id": f"66{index:02d}", "industry_name": f"G{index}"})


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
        group_map_path = root / "stock_industry_map.csv"
        write_group_map(group_map_path)
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

        group_output = root / "portfolio_replay_group.json"
        group_completed = subprocess.run(
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
                "--max-group-exposure",
                "0.3",
                "--group-map",
                str(group_map_path),
                "--output",
                str(group_output),
            ],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if group_completed.returncode != 0:
            print(group_completed.stdout)
            print(group_completed.stderr, file=sys.stderr)
            return group_completed.returncode

        event_rankings_dir = root / "event_artifacts"
        event_rankings_dir.mkdir()
        write_ranking(event_rankings_dir / "ranking_2026-03-02.csv", [("7777", "停損", "0.2"), ("8888", "停利", "0.2")])
        event_features = pd.DataFrame(event_price_rows())
        event_features["trade_date"] = pd.to_datetime(event_features["trade_date"])
        event_features_path = root / "event_features.parquet"
        event_features.to_parquet(event_features_path)
        event_output = root / "portfolio_replay_event.json"
        event_completed = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "run_portfolio_replay.py"),
                "--rankings-dir",
                str(event_rankings_dir),
                "--features",
                str(event_features_path),
                "--horizon",
                "2",
                "--top-n",
                "2",
                "--stop-loss-pct",
                "0.05",
                "--take-profit-pct",
                "0.1",
                "--output",
                str(event_output),
            ],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if event_completed.returncode != 0:
            print(event_completed.stdout)
            print(event_completed.stderr, file=sys.stderr)
            return event_completed.returncode

        multi_group_rankings_dir = root / "multi_group_artifacts"
        multi_group_rankings_dir.mkdir()
        write_ranking(
            multi_group_rankings_dir / "ranking_2026-04-02.csv",
            [(f"66{index:02d}", f"G{index}", "0.05") for index in range(10)],
        )
        multi_group_features = pd.DataFrame(multi_group_price_rows())
        multi_group_features["trade_date"] = pd.to_datetime(multi_group_features["trade_date"])
        multi_group_features_path = root / "multi_group_features.parquet"
        multi_group_features.to_parquet(multi_group_features_path)
        multi_group_output = root / "portfolio_replay_multi_group.json"
        multi_group_completed = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "run_portfolio_replay.py"),
                "--rankings-dir",
                str(multi_group_rankings_dir),
                "--features",
                str(multi_group_features_path),
                "--horizon",
                "2",
                "--top-n",
                "10",
                "--max-gross-exposure",
                "1.0",
                "--max-position-weight",
                "0.05",
                "--max-group-exposure",
                "0.05",
                "--group-map",
                str(group_map_path),
                "--output",
                str(multi_group_output),
            ],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if multi_group_completed.returncode != 0:
            print(multi_group_completed.stdout)
            print(multi_group_completed.stderr, file=sys.stderr)
            return multi_group_completed.returncode

        output_text = output.read_text(encoding="utf-8")
        payload = json.loads(output_text)
        drift_payload = json.loads(drift_output.read_text(encoding="utf-8"))
        group_output_text = group_output.read_text(encoding="utf-8")
        group_payload = json.loads(group_output_text)
        event_output_text = event_output.read_text(encoding="utf-8")
        event_payload = json.loads(event_output_text)
        multi_group_output_text = multi_group_output.read_text(encoding="utf-8")
        multi_group_payload = json.loads(multi_group_output_text)
        daily = payload["daily"]
        trades = payload["trades"]
        skipped = payload["skipped"]
        max_positions = max(item["positions"] for item in daily)
        entry_dates = {trade["stock_id"]: trade["entry_date"] for trade in trades}
        ranking_dates = {trade["stock_id"]: trade["ranking_date"] for trade in trades}
        skipped_reasons = {(item.get("stock_id"), item.get("reason")) for item in skipped}
        event_reasons = {trade["stock_id"]: trade["exit_reason"] for trade in event_payload["trades"]}
        event_exit_dates = {trade["stock_id"]: trade["exit_date"] for trade in event_payload["trades"]}
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
            "group_exposure_capped": group_payload["summary"]["max_group_exposure"] <= 0.300001,
            "group_exposure_contract": group_payload["contract"]["group_exposure_policy"]
            == "optional max_group_exposure caps same-group exposure at entry and after close",
            "group_exposure_artifact_exists": any(item.get("group_exposures") for item in group_payload["daily"]),
            "group_no_nan_json_literal": "NaN" not in group_output_text,
            "event_exit_contract": event_payload["contract"]["event_exit_policy"]
            == "optional stop_loss/take_profit exits are evaluated on each market bar before scheduled horizon close",
            "stop_loss_exit": event_reasons.get("7777") == "stop_loss",
            "take_profit_exit": event_reasons.get("8888") == "take_profit",
            "event_exits_before_horizon_close": event_exit_dates.get("7777") == "2026-03-03"
            and event_exit_dates.get("8888") == "2026-03-03",
            "event_daily_counts": any(
                item.get("stop_loss_exits") == 1 and item.get("take_profit_exits") == 1 for item in event_payload["daily"]
            ),
            "event_no_nan_json_literal": "NaN" not in event_output_text,
            "multi_group_drift_capped": multi_group_payload["summary"]["max_group_exposure"] <= 0.050001,
            "multi_group_all_groups_checked": len(
                {
                    group
                    for item in multi_group_payload["daily"]
                    for group in item.get("group_exposures", {})
                }
            )
            == 10,
            "multi_group_deleverage_recorded": sum(
                int(item.get("group_deleverage_count", 0)) for item in multi_group_payload["daily"]
            )
            >= 10,
            "multi_group_no_nan_json_literal": "NaN" not in multi_group_output_text,
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
