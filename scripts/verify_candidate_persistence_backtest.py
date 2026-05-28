#!/usr/bin/env python3
"""使用 synthetic ranking / OHLC 驗證入榜天數研究不偷看未來。"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def write_ranking(path: Path, rows: list[tuple[str, str]]) -> None:
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
        for stock_id, stock_name in rows:
            writer.writerow(
                {
                    "stock_id": stock_id,
                    "stock_name": stock_name,
                    "model_prob": "0.6",
                    "risk_adjusted_score": "1.0",
                    "suggested_weight": "0.1",
                    "max_position_weight": "0.2",
                    "gross_exposure": "0.5",
                }
            )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="top10-persistence-study-") as tmp:
        root = Path(tmp)
        rankings_dir = root / "artifacts"
        rankings_dir.mkdir()
        write_ranking(rankings_dir / "ranking_2026-01-02.csv", [("1111", "甲"), ("2222", "乙")])
        write_ranking(rankings_dir / "ranking_2026-01-05.csv", [("1111", "甲"), ("3333", "丙")])
        write_ranking(rankings_dir / "ranking_2026-01-06.csv", [("1111", "甲"), ("3333", "丙"), ("4444", "丁")])
        write_ranking(rankings_dir / "ranking_2026-01-07.csv", [("4444", "丁")])

        features = pd.DataFrame(
            [
                {"stock_id": stock, "trade_date": date, "open": open_, "high": high, "low": low, "close": close}
                for stock, prices in {
                    "1111": [(100, 106), (106, 109), (109, 112), (112, 114)],
                    "2222": [(50, 48), (48, 47), (47, 46), (46, 45)],
                    "3333": [(30, 31), (31, 33), (33, 34), (34, 35)],
                    "4444": [(40, 39), (39, 38), (38, 37), (37, 36)],
                }.items()
                for date, (open_, close) in zip(
                    ["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08"],
                    prices,
                    strict=False,
                )
                for high, low in [(max(open_, close) + 1, min(open_, close) - 1)]
            ]
        )
        features["trade_date"] = pd.to_datetime(features["trade_date"])
        features_path = root / "features.parquet"
        features.to_parquet(features_path)
        output = root / "persistence_study.json"

        completed = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "research_candidate_persistence_backtest.py"),
                "--rankings-dir",
                str(rankings_dir),
                "--features",
                str(features_path),
                "--horizons",
                "1",
                "--top-n",
                "3",
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
        buckets = payload["summary"]["by_horizon_and_streak"]
        bucket_names = set(buckets)
        trades = payload["trades"]
        checks = {
            "schema_ok": payload["schema_version"] == "candidate-persistence-backtest.v1",
            "model_feature_false": payload["contract"]["model_feature"] is False,
            "no_future_ranking_contract": payload["contract"]["uses_future_rankings"] is False,
            "has_streak_1": "1D::1" in bucket_names,
            "has_streak_2_3": "1D::2-3" in bucket_names,
            "streak_2_3_positive": buckets.get("1D::2-3", {}).get("avg_net_return", 0) > 0,
            "new_bucket_has_trade": buckets.get("1D::1", {}).get("trade_count", 0) > 0,
            "all_trades_have_streak": all(trade.get("consecutive_ranked_days") for trade in trades),
            "no_nan_json_literal": "NaN" not in output_text,
            "future_2026_01_07_not_used_for_2026_01_06_4444": any(
                trade["ranking_date"] == "2026-01-06"
                and trade["stock_id"] == "4444"
                and trade["consecutive_ranked_days"] == 1
                for trade in trades
            ),
        }
        ok = all(checks.values())
        artifact = PROJECT_ROOT / "artifacts" / "candidate_persistence_backtest_verification_latest.json"
        artifact.write_text(
            json.dumps(
                {
                    "schema_version": "candidate-persistence-backtest-verification.v1",
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
            print(f"CANDIDATE_PERSISTENCE_BACKTEST_OK output={artifact}")
            return 0
        print(f"CANDIDATE_PERSISTENCE_BACKTEST_FAILED output={artifact}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
