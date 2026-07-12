from __future__ import annotations

import unittest

import pandas as pd

from app.trading import MarketRegime, RankingPolicy, StrategyComponentRegistry


class StrategyComponentRegistryTest(unittest.TestCase):
    def test_default_routes_components_by_regime(self) -> None:
        registry = StrategyComponentRegistry.default()

        risk_on = registry.route("RISK_ON")
        risk_off = registry.route("RISK_OFF")
        panic = registry.route("PANIC_SELLING")

        self.assertIn("base_regime_risk_multiplier", risk_on.production)
        self.assertIn("high_entry_chase_protection", risk_on.shadow)
        self.assertIn("selloff_protection", risk_off.shadow)
        self.assertIn("vwap_regime_gated_entry", panic.shadow)
        self.assertIn("feature_group_k9_shadow_fill", risk_off.shadow)
        self.assertIn("trail10_exit_rule", risk_on.report_only)
        self.assertIn("industry_theme_context", risk_on.report_only)
        self.assertIn("high_entry_chase_protection", panic.blocked)
        self.assertIn("chip_warning_overlay", risk_on.blocked)
        self.assertIn("base_regime_risk_multiplier", risk_off.production_mutators)

    def test_unreviewed_shadow_component_cannot_be_promoted_by_config_only(self) -> None:
        with self.assertRaises(ValueError):
            StrategyComponentRegistry.from_mapping(
                {
                    "components": {
                        "high_entry_chase_protection": {
                            "runtime_status": "production",
                        }
                    }
                }
            )

    def test_ranking_policy_adds_route_metadata_without_changing_order(self) -> None:
        frame = pd.DataFrame(
            [
                {"stock_id": "1101", "model_prob": 0.62, "rule_score": 3, "avg_value_20d": 80_000_000, "close": 50, "ma20": 45},
                {"stock_id": "2201", "model_prob": 0.58, "rule_score": 2, "avg_value_20d": 50_000_000, "close": 42, "ma20": 40},
                {"stock_id": "3301", "model_prob": 0.51, "rule_score": 1, "avg_value_20d": 25_000_000, "close": 30, "ma20": 32},
            ]
        )
        regime = MarketRegime("RISK_OFF", 0.72, 0.32, 0.1, 45, "弱勢")

        ranked = RankingPolicy().apply(frame, regime)

        self.assertEqual(ranked["stock_id"].tolist(), ["1101", "2201", "3301"])
        self.assertTrue((ranked["strategy_route_regime"] == "RISK_OFF").all())
        self.assertTrue(ranked["strategy_route_shadow"].str.contains("selloff_protection").all())
        self.assertTrue(ranked["strategy_route_mutates_production_score"].all())


if __name__ == "__main__":
    unittest.main()
