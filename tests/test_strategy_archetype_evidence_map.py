from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_strategy_archetype_evidence_map import build_payload, render_markdown


class StrategyArchetypeEvidenceMapTest(unittest.TestCase):
    def test_builds_pm_readable_archetypes_without_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            artifacts = Path(tmp)
            (artifacts / "research_map").mkdir(parents=True)
            (artifacts / "weekend_training").mkdir()
            (artifacts / "autonomous_research").mkdir()

            (artifacts / "research_map" / "research_fog_map_latest.json").write_text(
                json.dumps(
                    {
                        "status": "OK",
                        "summary": {
                            "base_processed": 10,
                            "base_universe_total": 10,
                            "base_progress_pct": 1.0,
                            "expanded_processed": 4,
                            "expanded_universe_total": 100,
                            "expanded_progress_pct": 0.04,
                        },
                        "burn_down_progress": {
                            "classified_total": 100,
                            "full_universe_total": 100,
                            "classified_progress_pct": 1.0,
                            "counts": {"unsupported_count": 20},
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (artifacts / "research_map" / "research_fog_map_verification_latest.json").write_text(
                json.dumps({"status": "OK"}, ensure_ascii=False),
                encoding="utf-8",
            )
            (artifacts / "weekend_training" / "weekend_training_rollup_2026-07-01.json").write_text(
                json.dumps(
                    {
                        "summary": {
                            "unsupported_count": 20,
                            "unsupported_category_counts": {"UNSUPPORTED_REGIME_SLICE_NO_DATA": 8},
                            "unsupported_reason_top_counts": {"UNSUPPORTED_REGIME_GATE:RISK_OFF_ONLY": 8},
                            "unsupported_non_unblockable_count": 0,
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (artifacts / "autonomous_research" / "research_campaign_progress_2026-07-01.json").write_text(
                json.dumps(
                    {
                        "insights": {
                            "followup_signals": [
                                {
                                    "topic_id": "strategy-matrix:shadow_rankings_regime_overlay_recent",
                                    "dimensions": {
                                        "horizon": "3",
                                        "stop_loss": "0.08",
                                        "group_exposure": "0.35",
                                    },
                                    "decision": "PARTIAL_SCORE_ONLY",
                                    "artifact_path": "artifacts/autonomous_research/example.json",
                                }
                            ]
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (artifacts / "autonomous_research" / "next_action_queue.json").write_text(
                json.dumps(
                    {
                        "actions": [
                            {
                                "topic_id": "strategy-matrix:liquidity_log_gate",
                                "candidate_dir": "artifacts/backtest/liquidity_quality/log_gate",
                                "manager_status": "confirmed_for_next_replay",
                                "next_action": "promote_to_longer_replay_candidate",
                                "score": 26,
                            },
                            {
                                "topic_id": "strategy-matrix:shadow_rankings_regime_overlay_recent",
                                "candidate_dir": "artifacts/backtest/shadow_rankings_regime_overlay_recent",
                                "manager_status": "partial_needs_followup",
                                "next_action": "rerun_with_larger_window_or_add_risk_check",
                                "score": 34,
                            },
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (artifacts / "autonomous_research" / "manager_summary.json").write_text(
                json.dumps({"status": "OK", "next_action_count": 2}, ensure_ascii=False),
                encoding="utf-8",
            )

            payload = build_payload("2026-07-01", artifacts)

            self.assertEqual(payload["schema_version"], "strategy-archetype-evidence-map.v1")
            self.assertTrue(payload["execution_boundary"]["research_only"])
            self.assertTrue(payload["execution_boundary"]["does_not_change_ranking"])
            self.assertTrue(payload["execution_boundary"]["does_not_mark_promotion_ready"])

            archetype_ids = [item["archetype_id"] for item in payload["archetypes"]]
            self.assertIn("high_entry_chase_protection", archetype_ids)
            self.assertIn("selloff_protection", archetype_ids)

            markdown = render_markdown(payload)
            self.assertIn("高位防追高型", markdown)
            self.assertIn("急殺保護型", markdown)
            self.assertIn("不改 ranking", markdown)


if __name__ == "__main__":
    unittest.main()
