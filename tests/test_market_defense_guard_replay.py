from scripts import build_market_defense_guard_replay as replay


def test_classify_risk_off_block_for_breadth_and_three_day_drop():
    row = {
        "market_return_3d": -0.025,
        "market_return_5d": -0.01,
        "drawdown_from_20d_high": -0.02,
        "breadth_ma20": 0.30,
        "down_streak": 2,
    }

    result = replay.classify_defense_level(row)

    assert result["level"] == "RISK_OFF_BLOCK"


def test_fragile_breadth_is_watch_only_when_defense_level_is_normal():
    row = {
        "defense_level": "NORMAL",
        "market_return_3d": -0.005,
        "drawdown_from_20d_high": -0.01,
        "breadth_ma20": 0.20,
    }

    assert replay.fragility_watch(row) == "FRAGILE_BREADTH"

    defensive_row = {**row, "defense_level": "DEFENSIVE"}
    assert replay.fragility_watch(defensive_row) is None
