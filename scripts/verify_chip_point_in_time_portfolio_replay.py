#!/usr/bin/env python3
"""驗證 chip portfolio replay 的排序與 gate。"""

from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from argparse import Namespace
from datetime import date

from scripts.research_chip_point_in_time_portfolio_replay import (
    compare_variant,
    pairwise_gap_receipt,
    score_daily,
    variant_prefix,
)


def verify_score_daily() -> None:
    daily = pd.DataFrame(
        {
            "stock_id": [f"{index:04d}" for index in range(1, 11)],
            "regime_label": ["RISK_OFF"] * 10,
            "liq": list(range(10)),
            "chip": list(reversed(range(10))),
        }
    )
    selected = {
        "RISK_OFF": {
            "liquidity_activity": [{"feature": "liq", "direction": 1}],
            "chip_flow": [{"feature": "chip", "direction": 1}],
        }
    }
    scored = score_daily(daily, selected, top_n=3)
    assert scored is not None
    assert scored["baseline"] == ["0010", "0009", "0008"]
    assert len(scored["chip_0.10"]) == 3
    assert len(scored["chip_0.20"]) == 3
    event_selected = {
        "RISK_OFF": {
            "liquidity_activity": [{"feature": "liq", "direction": 1}],
            "event": [{"feature": "chip", "direction": 1}],
        }
    }
    event_scored = score_daily(daily, event_selected, top_n=3, primary_group="event")
    assert event_scored is not None
    assert set(event_scored) == {"baseline", "event_0.10", "event_0.20"}
    assert variant_prefix("chip_flow") == "chip"
    assert variant_prefix("event") == "event"
    constrained = score_daily(
        daily,
        event_selected,
        top_n=5,
        primary_group="event",
        overlay_weights=[0.10],
        min_retain_baseline=3,
        candidate_pool_multiplier=2,
    )
    assert constrained is not None
    assert set(constrained["baseline"][:3]).issubset(set(constrained["event_0.10"]))
    assert len(constrained["event_0.10"]) == 5


def bucket(stock_ids: list[str], value: float, exposure: float = 0.3) -> dict:
    return {
        "stock_ids": stock_ids,
        "valid_trade_count": 10,
        "avg_net_return": value,
        "hit_rate": 0.6,
        "max_group_exposure": exposure,
    }


def verify_gate() -> None:
    rows = []
    for fold in range(1, 6):
        for day in range(3):
            base_ids = [f"{index:04d}" for index in range(10)]
            overlay_ids = [f"{index:04d}" for index in range(1, 11)]
            rows.append(
                {
                    "fold": fold,
                    "baseline": bucket(base_ids, 0.01),
                    "chip_0.10": bucket(overlay_ids, 0.011),
                }
            )
    result = compare_variant(rows, "chip_0.10")
    assert result["decision"] == "SHADOW_CANDIDATE"
    assert result["positive_fold_count"] == 5


def verify_incomplete_bucket_rejected() -> None:
    rows = [
        {
            "fold": 1,
            "baseline": bucket([f"{index:04d}" for index in range(10)], 0.01),
            "chip_0.10": {
                **bucket([f"{index:04d}" for index in range(9)], 0.02),
                "valid_trade_count": 9,
            },
        }
    ]
    result = compare_variant(rows, "chip_0.10")
    assert "incomplete_bucket_count>0" in result["failed"]


def verify_pairwise_gap_requires_market_match() -> None:
    row = {
        "fold": 1,
        "ranking_date": "2026-04-01",
        "baseline": {
            **bucket(["8299"], 0.01),
            "valid_trade_count": 0,
            "trades": [],
        },
    }
    trade_dates = [
        date(2026, 4, 1),
        date(2026, 4, 2),
        date(2026, 4, 7),
        date(2026, 4, 8),
        date(2026, 4, 9),
        date(2026, 4, 10),
        date(2026, 4, 13),
        date(2026, 4, 14),
        date(2026, 4, 15),
        date(2026, 4, 16),
        date(2026, 4, 17),
    ]
    args = Namespace(entry_delay_trade_days=1, horizon=10)
    receipt = pairwise_gap_receipt(
        row,
        variant_keys=["baseline"],
        trade_dates=trade_dates,
        stock_market={"8299": "TPEX"},
        known_gaps=[{"date": "2026-04-13", "market": "TPEX"}],
        args=args,
    )
    assert receipt is not None
    rejected = pairwise_gap_receipt(
        row,
        variant_keys=["baseline"],
        trade_dates=trade_dates,
        stock_market={"8299": "TWSE"},
        known_gaps=[{"date": "2026-04-13", "market": "TPEX"}],
        args=args,
    )
    assert rejected is None


def main() -> int:
    verify_score_daily()
    verify_gate()
    verify_incomplete_bucket_rejected()
    verify_pairwise_gap_requires_market_match()
    print("CHIP_POINT_IN_TIME_PORTFOLIO_REPLAY_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
