#!/usr/bin/env python3
"""驗證每日 Top10 決策品質摘要的 read-only artifact 契約。"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_PATH = PROJECT_ROOT / "artifacts" / "decision_quality_verification_latest.json"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def write_ranking(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "stock_id",
                "stock_name",
                "risk_adjusted_score",
                "final_score",
                "model_prob",
                "prediction_score",
                "setup_score",
                "quality_score",
                "risk_penalty",
                "suggested_weight",
                "gross_exposure",
                "industry_name",
                "sector_name",
                "market_type",
                "market_regime",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "stock_id": "1111",
                "stock_name": "甲",
                "risk_adjusted_score": "2.5",
                "final_score": "9.1",
                "model_prob": "0.72",
                "prediction_score": "1.2",
                "setup_score": "0.8",
                "quality_score": "0.7",
                "risk_penalty": "0.2",
                "suggested_weight": "0.15",
                "gross_exposure": "0.6",
                "industry_name": "半導體",
                "sector_name": "電子",
                "market_type": "twse",
                "market_regime": "RISK_ON",
            }
        )
        writer.writerow(
            {
                "stock_id": "2222",
                "stock_name": "乙",
                "risk_adjusted_score": "1.5",
                "final_score": "8.2",
                "model_prob": "0.61",
                "prediction_score": "1.0",
                "setup_score": "0.5",
                "quality_score": "0.3",
                "risk_penalty": "0.3",
                "suggested_weight": "0.1",
                "gross_exposure": "0.6",
                "industry_name": "電力",
                "sector_name": "傳產",
                "market_type": "tpex",
                "market_regime": "RISK_ON",
            }
        )


def build_fixture(root: Path) -> dict[str, Path]:
    artifacts = root / "artifacts"
    backtest = artifacts / "backtest"
    ranking = artifacts / "ranking_2026-01-05.csv"
    artifacts.mkdir()
    backtest.mkdir()
    write_ranking(ranking)
    write_json(
        artifacts / "candidate_persistence_2026-01-05.json",
        {
            "schema_version": "candidate-persistence.v1",
            "ranking_date": "2026-01-05",
            "items": [
                {
                    "stock_id": "1111",
                    "first_seen_date": "2026-01-03",
                    "consecutive_ranked_days": 3,
                    "ranked_history_count": 3,
                    "previous_rank": 2,
                    "rank_delta": 1,
                },
                {
                    "stock_id": "2222",
                    "first_seen_date": "2026-01-05",
                    "consecutive_ranked_days": 1,
                    "ranked_history_count": 1,
                    "previous_rank": None,
                    "rank_delta": None,
                },
            ],
        },
    )
    write_json(
        backtest / "replay_2026-01-06.json",
        {
            "schema_version": "production-replay-backtest.v1",
            "trades": [
                {
                    "ranking_date": "2026-01-03",
                    "stock_id": "1111",
                    "horizon": 1,
                    "net_return": 0.05,
                    "mae": -0.01,
                    "mfe": 0.08,
                },
                {
                    "ranking_date": "2026-01-04",
                    "stock_id": "1111",
                    "horizon": 1,
                    "net_return": -0.01,
                    "mae": -0.03,
                    "mfe": 0.02,
                },
                {
                    "ranking_date": "2026-01-06",
                    "stock_id": "1111",
                    "horizon": 1,
                    "net_return": 9.99,
                    "mae": 0.0,
                    "mfe": 9.99,
                },
            ],
        },
    )
    write_json(
        backtest / "portfolio_replay_2026-01-06.json",
        {
            "schema_version": "overlap-portfolio-replay.v1",
            "inputs": {"horizon": 5, "max_gross_exposure": 0.65, "max_group_exposure": 0.3},
            "summary": {
                "final_equity": 1.08,
                "total_return": 0.08,
                "max_drawdown": -0.12,
                "trade_count": 20,
                "skipped_count": 2,
                "win_rate": 0.55,
                "avg_trade_return": 0.01,
                "max_gross_exposure": 0.64,
                "avg_gross_exposure": 0.41,
                "max_group_exposure": 0.29,
            },
        },
    )
    write_json(
        artifacts / "market_context_2026-01-05.json",
        {
            "schema_version": "market-context.tw.v1",
            "trade_date": "2026-01-05",
            "summary": {"domestic_context_label": "RISK_ON", "notes": ["synthetic"]},
            "taiex": {"close": 20000.0, "change_pct": 0.5},
            "breadth": {"advance_ratio": 0.6},
            "institutional": {"foreign_net": 1000.0},
            "futures": {"tx_close": 20050.0},
            "options": {"pcr": 105.0},
            "source_status": {"twse": {"status": "ok"}},
        },
    )
    return {"artifacts": artifacts, "ranking": ranking, "output": root / "decision_quality_2026-01-05.json"}


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="top10-decision-quality-") as tmp:
        paths = build_fixture(Path(tmp))
        completed = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "build_decision_quality.py"),
                "--ranking",
                str(paths["ranking"]),
                "--artifacts-dir",
                str(paths["artifacts"]),
                "--output",
                str(paths["output"]),
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
        payload = json.loads(paths["output"].read_text(encoding="utf-8"))
        first = payload["top10"][0]
        first_horizon = first["historical_backtest"]["horizons"]["1"]
        output_text = paths["output"].read_text(encoding="utf-8")
        checks = {
            "schema_ok": payload["schema_version"] == "decision-quality.v1",
            "read_only_contract": payload["contract"]["ranking_score_policy"].startswith("read_only_annotation"),
            "local_reference_mapping_declared": (
                "read_only_local_reference_mapping" in payload["contract"]["data_source_policy"]
                and payload["contract"].get("reference_scope")
                == "read-only data/reference mapping for neutral industry/sector/market annotation only"
            ),
            "top_count": payload["summary"]["top_count"] == 2,
            "score_copied_not_recomputed": first["scores"]["risk_adjusted_score"] == 2.5,
            "reference_annotation_added": first["reference"]["industry_name"] != "" and first["reference"]["sector_name"] != "",
            "persistence_included": first["persistence"]["consecutive_ranked_days"] == 3,
            "backtest_uses_only_past_rankings": first["historical_backtest"]["trade_count"] == 2,
            "future_replay_excluded": first_horizon["avg_net_return"] == 0.02,
            "future_portfolio_replay_rejected": payload["portfolio_replay_risk"]["available"] is False,
            "future_portfolio_replay_reason": payload["portfolio_replay_risk"].get("reason") == "portfolio_replay_date_mismatch",
            "future_portfolio_replay_alignment": payload["portfolio_replay_risk"].get("date_alignment") == "future",
            "future_portfolio_not_summary_available": payload["summary"]["portfolio_replay_risk_available"] is False,
            "market_context_exact": payload["market_context"]["date_alignment"] == "exact",
            "market_context_label": payload["summary"]["market_context_label"] == "RISK_ON",
            "no_nan_json_literal": "NaN" not in output_text,
        }
        status = "OK" if all(checks.values()) else "FAILED"
        ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
        ARTIFACT_PATH.write_text(
            json.dumps(
                {
                    "schema_version": "decision-quality-verification.v1",
                    "status": status,
                    "checks": checks,
                    "note": "uses TemporaryDirectory synthetic artifacts plus read-only local reference mapping; no ranking/model/API execution",
                },
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            ),
            encoding="utf-8",
        )
        if status == "OK":
            print(f"DECISION_QUALITY_OK output={ARTIFACT_PATH}")
            return 0
        print(f"DECISION_QUALITY_FAILED output={ARTIFACT_PATH}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
