#!/usr/bin/env python3
"""驗證 portfolio risk overlay 預設關閉時不改 production ranking / sizing。"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml
from pandas.testing import assert_frame_equal


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.trading import (  # noqa: E402
    MarketRegime,
    PortfolioPolicy,
    PortfolioRiskOverlay,
    PortfolioRiskOverlayConfig,
    RankingPolicy,
)


def sample_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "stock_id": "1101",
                "model_prob": 0.62,
                "rule_score": 3,
                "avg_value_20d": 80_000_000,
                "avg_volume_20d": 10_000,
                "industry_breadth_ma20_loo": 0.8,
                "sector_return_1d_loo": 0.02,
                "pct_from_low_60d": 0.35,
                "bb_width": 0.12,
                "close": 50,
                "ma20": 45,
                "shadow_market_regime": "PANIC_SELLING",
            },
            {
                "stock_id": "2201",
                "model_prob": 0.58,
                "rule_score": 2,
                "avg_value_20d": 50_000_000,
                "avg_volume_20d": 8_000,
                "industry_breadth_ma20_loo": 0.4,
                "sector_return_1d_loo": -0.01,
                "pct_from_low_60d": 0.55,
                "bb_width": 0.18,
                "close": 42,
                "ma20": 40,
                "shadow_market_regime": "PANIC_SELLING",
            },
            {
                "stock_id": "3301",
                "model_prob": 0.51,
                "rule_score": 1,
                "avg_value_20d": 25_000_000,
                "avg_volume_20d": 5_000,
                "industry_breadth_ma20_loo": 0.2,
                "sector_return_1d_loo": -0.03,
                "pct_from_low_60d": 0.75,
                "bb_width": 0.24,
                "close": 30,
                "ma20": 32,
                "shadow_market_regime": "PANIC_SELLING",
            },
        ]
    )


def assert_same(left: pd.DataFrame, right: pd.DataFrame) -> None:
    assert_frame_equal(
        left.reset_index(drop=True),
        right.reset_index(drop=True),
        check_dtype=False,
        check_like=False,
    )


def main() -> int:
    frame = sample_frame()
    regime = MarketRegime("RISK_ON", 1.08, 0.6, 0.2, 55, "on")
    disabled = PortfolioRiskOverlay(
        PortfolioRiskOverlayConfig(
            enabled=False,
            score_overlay_enabled=False,
            sizing_overlay_enabled=False,
            risk_profile="shadow_regime_guard",
        )
    )
    enabled = PortfolioRiskOverlay(
        PortfolioRiskOverlayConfig(
            enabled=True,
            score_overlay_enabled=True,
            sizing_overlay_enabled=True,
            risk_profile="shadow_regime_guard",
        )
    )

    ranking_default = RankingPolicy().apply(frame, regime)
    ranking_disabled = RankingPolicy(portfolio_overlay=disabled).apply(frame, regime)
    allocation_default = PortfolioPolicy(base_max_position_weight=0.2).apply(ranking_default, regime)
    allocation_disabled = PortfolioPolicy(base_max_position_weight=0.2, portfolio_overlay=disabled).apply(ranking_disabled, regime)

    ranking_enabled = RankingPolicy(portfolio_overlay=enabled).apply(frame, regime)
    allocation_enabled = PortfolioPolicy(base_max_position_weight=0.2, portfolio_overlay=enabled).apply(ranking_enabled, regime)

    config = yaml.safe_load((PROJECT_ROOT / "config" / "signals.yaml").read_text(encoding="utf-8")) or {}
    overlay_config = config.get("portfolio_risk_overlay", {})

    checks: dict[str, bool] = {}
    try:
        assert_same(ranking_default, ranking_disabled)
        checks["ranking_default_off_exact_match"] = True
    except AssertionError:
        checks["ranking_default_off_exact_match"] = False
    try:
        assert_same(allocation_default, allocation_disabled)
        checks["allocation_default_off_exact_match"] = True
    except AssertionError:
        checks["allocation_default_off_exact_match"] = False

    checks.update(
        {
            "config_default_disabled": overlay_config.get("enabled") is False,
            "config_score_overlay_disabled": overlay_config.get("score_overlay_enabled") is False,
            "config_sizing_overlay_disabled": overlay_config.get("sizing_overlay_enabled") is False,
            "enabled_adds_overlay_score": "portfolio_overlay_score" in ranking_enabled.columns,
            "enabled_adds_overlay_regime": allocation_enabled.get("portfolio_overlay_regime") is not None,
            "enabled_caps_panic_selling_gross": float(allocation_enabled["gross_exposure"].iloc[0]) <= 0.300001,
            "enabled_preserves_weight_cap": bool(
                (allocation_enabled["suggested_weight"] <= allocation_enabled["max_position_weight"] + 1e-9).all()
            ),
        }
    )
    ok = all(checks.values())
    output = PROJECT_ROOT / "artifacts" / "model_experiments" / "portfolio_risk_overlay_default_off_verification_latest.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "schema_version": "portfolio-risk-overlay-default-off-verification.v1",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "status": "OK" if ok else "FAILED",
                "checks": checks,
                "contract": {
                    "default_off_no_production_behavior_change": checks["ranking_default_off_exact_match"]
                    and checks["allocation_default_off_exact_match"],
                    "production_promotion_allowed": False,
                },
            },
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"status": "OK" if ok else "FAILED", "output": str(output), "checks": checks}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
