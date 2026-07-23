from __future__ import annotations

import unittest

from app.automation.daily_orchestrator import run_daily, run_daily_final_artifacts


class RecordingActions:
    def __init__(self, *, non_trading_day: bool = False) -> None:
        self.calls: list[str] = []
        self.non_trading_day = non_trading_day
        self.market_context_t86_path: str | None = None

    def __getattr__(self, name: str):
        def record(*args, **kwargs):
            self.calls.append(name)
            if name == "expected_ranking_path":
                return "ranking.csv"
            if name == "run_daily_report":
                return "daily-report.json"
            return None

        return record

    def should_skip_non_trading_day(self, config) -> bool:
        self.calls.append("should_skip_non_trading_day")
        return self.non_trading_day

    def non_trading_day_reason(self) -> str:
        self.calls.append("non_trading_day_reason")
        return "non_trading_day weekday=6"

    def run_tskg_t86(self, config) -> str:
        self.calls.append("run_tskg_t86")
        return "t86.json"

    def run_market_context(self, config, t86_path) -> None:
        self.calls.append("run_market_context")
        self.market_context_t86_path = t86_path


class DailyAutomationOrchestratorTest(unittest.TestCase):
    def test_primary_flow_preserves_production_order(self) -> None:
        actions = RecordingActions()
        run_daily(actions, {"enabled": True})

        self.assertEqual(
            actions.calls,
            [
                "should_skip_non_trading_day",
                "guard_resource_profile",
                "preflight",
                "run_etl",
                "validate_data",
                "record_data_freshness",
                "run_ranking",
                "record_ranking",
                "expected_ranking_path",
                "run_candidate_persistence",
                "run_weekly_snapshot",
                "run_tskg_t86",
                "run_market_context",
                "run_daily_recommendation_performance",
                "run_decision_quality",
                "run_daily_performance_review",
                "run_gross55_shadow_monitor",
                "run_capital_entry_quality_shadow_monitor",
                "run_candidate_trail10_shadow_monitor",
                "run_overlap_first_recommendation_shadow",
                "run_shadow_historical_evidence_report",
                "run_overlay_append_only_shadow",
                "run_daily_shadow_status_report",
                "record_api_cache_clear_skipped",
                "run_postcheck",
            ],
        )
        self.assertEqual(actions.market_context_t86_path, "t86.json")

    def test_disabled_flow_stops_before_trading_day_check(self) -> None:
        actions = RecordingActions()
        run_daily(actions, {"enabled": False})
        self.assertEqual(actions.calls, ["skip"])

    def test_non_trading_day_flow_stops_before_side_effects(self) -> None:
        actions = RecordingActions(non_trading_day=True)
        run_daily(actions, {"enabled": True})
        self.assertEqual(
            actions.calls,
            ["should_skip_non_trading_day", "non_trading_day_reason", "skip"],
        )

    def test_final_artifacts_preserve_report_then_payload_order(self) -> None:
        actions = RecordingActions()
        run_daily_final_artifacts(actions, {})
        self.assertEqual(
            actions.calls,
            ["expected_ranking_path", "run_daily_report", "run_clawd_payload"],
        )


if __name__ == "__main__":
    unittest.main()
