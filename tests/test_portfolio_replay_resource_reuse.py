from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pandas as pd

from scripts import run_portfolio_replay as replay
from scripts import run_backtest_replay


def test_exact_loader_keeps_global_calendar_but_projects_ohlc_to_ranked_stocks(
    tmp_path: Path,
) -> None:
    path = tmp_path / "features.parquet"
    pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-02", "2026-01-03", "2026-01-02"]),
            "stock_id": ["2330", "2330", "2317"],
            "open": [10.0, 11.0, 20.0],
            "high": [11.0, 12.0, 21.0],
            "low": [9.0, 10.0, 19.0],
            "close": [10.5, 11.5, 20.5],
        }
    ).to_parquet(path)

    dates = run_backtest_replay.load_market_trade_dates(path)
    prices = run_backtest_replay.load_price_frame_for_stocks(path, {"2330"})

    assert [item.isoformat() for item in dates] == ["2026-01-02", "2026-01-03"]
    assert prices["stock_id"].unique().tolist() == ["2330"]
    assert len(prices) == 2


def test_prepared_matrix_context_does_not_rebuild_large_lookups(monkeypatch) -> None:
    frame = pd.DataFrame(columns=["stock_id", "trade_date", "open", "high", "low", "close"])
    args = Namespace(
        rankings_dir="unused-rankings",
        features="unused-features.parquet",
        horizon=3,
        top_n=10,
        entry_delay_trade_days=1,
        max_ranking_files=1,
        initial_cash=1.0,
        max_gross_exposure=0.65,
        big_bull_gross_exposure=None,
        high_choppy_gross_exposure=None,
        other_family_gross_exposure=None,
        max_position_weight=0.2,
        max_group_exposure=0.35,
        group_map="unused.csv",
        group_column="industry_name",
        fee_rate=0.001425,
        tax_rate=0.003,
        slippage_rate=0.001,
        stop_loss_pct=0.08,
        take_profit_pct=0.15,
        trailing_stop_pct=None,
        min_event_holding_days=1,
        same_day_hit_priority="stop_loss",
        market_regime_history=None,
    )
    monkeypatch.setattr(
        replay.run_backtest_replay,
        "market_trade_dates",
        lambda _frame: (_ for _ in ()).throw(AssertionError("trade dates rebuilt")),
    )
    monkeypatch.setattr(
        replay,
        "price_lookup",
        lambda _frame: (_ for _ in ()).throw(AssertionError("price lookup rebuilt")),
    )
    monkeypatch.setattr(
        replay,
        "load_group_map",
        lambda *_args: (_ for _ in ()).throw(AssertionError("group map rebuilt")),
    )
    monkeypatch.setattr(replay, "build_entry_plans", lambda *_args: ([], []))

    result = replay.run_portfolio_from_price_frame(args, frame, [], {}, {})

    assert result["summary"]["trade_count"] == 0
