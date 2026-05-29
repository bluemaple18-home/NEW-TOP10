#!/usr/bin/env python3
"""使用 synthetic ranking / OHLC 驗證策略矩陣回測。"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def score_for_sort(row: dict[str, object]) -> float:
    score = row.get("score")
    return float(score) if score is not None else -999.0


def write_ranking(path: Path) -> None:
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
        for stock_id, stock_name in [("1111", "甲"), ("2222", "乙")]:
            writer.writerow(
                {
                    "stock_id": stock_id,
                    "stock_name": stock_name,
                    "model_prob": "0.7",
                    "risk_adjusted_score": "1.0",
                    "suggested_weight": "0.2",
                    "max_position_weight": "0.2",
                    "gross_exposure": "0.4",
                }
            )


def write_group_map(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["stock_id", "industry_name"])
        writer.writeheader()
        writer.writerow({"stock_id": "1111", "industry_name": "AI"})
        writer.writerow({"stock_id": "2222", "industry_name": "AI"})


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="top10-strategy-matrix-") as tmp:
        root = Path(tmp)
        rankings_dir = root / "artifacts"
        rankings_dir.mkdir()
        write_ranking(rankings_dir / "ranking_2026-01-02.csv")
        features = pd.DataFrame(
            [
                {"stock_id": "1111", "trade_date": "2026-01-05", "open": 100, "high": 115, "low": 99, "close": 110},
                {"stock_id": "1111", "trade_date": "2026-01-06", "open": 110, "high": 112, "low": 104, "close": 106},
                {"stock_id": "1111", "trade_date": "2026-01-07", "open": 106, "high": 108, "low": 105, "close": 107},
                {"stock_id": "2222", "trade_date": "2026-01-05", "open": 50, "high": 51, "low": 44, "close": 45},
                {"stock_id": "2222", "trade_date": "2026-01-06", "open": 45, "high": 46, "low": 42, "close": 43},
                {"stock_id": "2222", "trade_date": "2026-01-07", "open": 43, "high": 44, "low": 42, "close": 43},
            ]
        )
        features["trade_date"] = pd.to_datetime(features["trade_date"])
        features_path = root / "features.parquet"
        features.to_parquet(features_path)
        group_map = root / "stock_industry_map.csv"
        write_group_map(group_map)
        output = root / "strategy_matrix.json"

        completed = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "run_backtest_strategy_matrix.py"),
                "--rankings-dir",
                str(rankings_dir),
                "--features",
                str(features_path),
                "--max-ranking-files",
                "1",
                "--top-n",
                "2",
                "--horizons",
                "1,2",
                "--stop-loss-pcts",
                "none,0.05",
                "--take-profit-pcts",
                "none,0.1",
                "--max-group-exposures",
                "none,0.3",
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
        scenarios = payload.get("scenarios", [])
        score_boundary_rows = [
            {"scenario_id": "pos", "score": 0.1},
            {"scenario_id": "zero", "score": 0.0},
            {"scenario_id": "neg", "score": -0.1},
            {"scenario_id": "none", "score": None},
        ]
        score_boundary_order = [
            row["scenario_id"]
            for row in sorted(
                score_boundary_rows,
                key=lambda item: (item["score"] is not None, score_for_sort(item)),
                reverse=True,
            )
        ]
        checks = {
            "schema_ok": payload.get("schema_version") == "backtest-strategy-matrix.v1",
            "contract_no_model_change": payload["contract"]["model_feature"] is False
            and payload["contract"]["ranking_score_change"] is False,
            "features_load_once_contract": payload["contract"]["features_load_policy"] == "load_once_per_matrix",
            "scenario_count": payload["summary"]["scenario_count"] == 16,
            "best_scenario_exists": bool(payload["summary"]["best_scenario_id"]),
            "rows_sorted": all(
                score_for_sort(scenarios[index]) >= score_for_sort(scenarios[index + 1])
                for index in range(len(scenarios) - 1)
            ),
            "score_zero_sorts_before_negative": score_boundary_order == ["pos", "zero", "neg", "none"],
            "event_counts_exist": any(row.get("exit_reason_counts", {}).get("take_profit", 0) > 0 for row in scenarios),
            "group_cap_scenarios_exist": any(row.get("max_group_exposure") == 0.3 for row in scenarios),
            "no_nan_json_literal": "NaN" not in output_text,
        }
        ok = all(checks.values())
        artifact = PROJECT_ROOT / "artifacts" / "backtest_strategy_matrix_verification_latest.json"
        artifact.write_text(
            json.dumps(
                {
                    "schema_version": "backtest-strategy-matrix-verification.v1",
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
            print(f"BACKTEST_STRATEGY_MATRIX_OK output={artifact}")
            return 0
        print(f"BACKTEST_STRATEGY_MATRIX_FAILED output={artifact}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
