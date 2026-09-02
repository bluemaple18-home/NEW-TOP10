from __future__ import annotations

from argparse import Namespace

import pandas as pd

from scripts import run_portfolio_replay as replay


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
