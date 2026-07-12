from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from app.reports.core import StockReportGenerator
from app.reports.formatters.markdown_formatter import MarkdownFormatter
from app.reports.logic.analyzer import StockAnalyzer


class DailyBriefReportTest(unittest.TestCase):
    def _ranked_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "stock_id": "2330",
                    "stock_name": "台積電",
                    "model_prob": 0.78,
                    "risk_adjusted_score": 2.15,
                    "prediction_score": 0.78,
                    "setup_score": 0.65,
                    "quality_score": 0.9,
                    "risk_penalty": 0.18,
                    "risk_reward": 1.9,
                    "execution_risk_reward": 1.4,
                    "positive_signals": "突破20日|月線支撐|",
                    "risk_signals": "",
                    "rr_guard_action": "ALLOW",
                    "market_regime": "RISK_OFF",
                    "strategy_route_regime": "RISK_OFF",
                    "strategy_route_production": "base_regime_risk_multiplier",
                    "strategy_route_shadow": "selloff_protection|feature_group_k9_shadow_fill",
                    "strategy_route_report_only": "trail10_exit_rule|industry_theme_context",
                    "strategy_route_blocked": "high_entry_chase_protection|chip_warning_overlay",
                    "strategy_route_mutates_production_score": True,
                    "trade_plan": {
                        "entry_zone": {"low": 610.0, "high": 619.15},
                        "invalidation": "跌破 585.00 (月線支撐)",
                        "target_price": 670.0,
                        "risk_reward": 1.9,
                    },
                }
            ]
        )

    def _features_df(self) -> pd.DataFrame:
        rows = []
        for day in range(25):
            rows.append(
                {
                    "date": pd.Timestamp("2026-06-01") + pd.Timedelta(days=day),
                    "stock_id": "2330",
                    "open": 580 + day,
                    "high": 590 + day,
                    "low": 570 + day,
                    "close": 586 + day,
                    "ma20": 588.0,
                    "rsi": 62.4,
                }
            )
        rows[-1]["close"] = 620.0
        rows[-1]["high"] = 622.0
        return pd.DataFrame(rows)

    def test_prepare_report_data_builds_verifiable_daily_brief(self):
        data = StockAnalyzer().prepare_report_data(self._ranked_df(), self._features_df())
        recommendation = data["recommendations"][0]
        brief = recommendation["daily_brief"]

        self.assertEqual(brief["schema_version"], "top10.daily_brief.v1")
        self.assertIn("模型勝率 78.0%", brief["why_pick"][0])
        self.assertIn("risk_adjusted_score", brief["score_breakdown"])
        self.assertEqual(brief["strategy_route"]["regime"], "RISK_OFF")
        self.assertIn("急殺保護", brief["strategy_route"]["summary"])
        self.assertTrue(any(item["status"] == "not_supported" for item in brief["data_coverage"]))

    def test_markdown_renders_daily_brief_sections(self):
        data = StockAnalyzer().prepare_report_data(self._ranked_df(), self._features_df())
        markdown = MarkdownFormatter().format(data)

        self.assertIn("### 入選理由", markdown)
        self.assertIn("### 風險警報", markdown)
        self.assertIn("### 正向催化", markdown)
        self.assertIn("### 策略路由", markdown)
        self.assertIn("急殺保護", markdown)
        self.assertIn("not_supported", markdown)

    def test_report_generator_keeps_markdown_json_html_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            generator = StockReportGenerator(artifacts_dir=tmp)
            generator.generate_report(ranked_df=self._ranked_df(), features_df=self._features_df())

            root = Path(tmp)
            self.assertTrue((root / "analysis_report.md").exists())
            self.assertTrue((root / "analysis_report.json").exists())
            self.assertTrue((root / "analysis_report.html").exists())
            payload = json.loads((root / "analysis_report.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["recommendations"][0]["daily_brief"]["schema_version"], "top10.daily_brief.v1")


if __name__ == "__main__":
    unittest.main()
