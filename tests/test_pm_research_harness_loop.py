from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import run_pm_research_harness_loop as harness_loop
from scripts.run_pm_research_harness_loop import export_pm_review_cards, load_state


class PMResearchHarnessLoopTests(unittest.TestCase):
    def test_exports_unsent_research_decisions_as_pm_review_cards(self):
        with tempfile.TemporaryDirectory() as tmp:
            brief_path = Path(tmp) / "brief.json"
            brief_path.write_text(
                json.dumps(
                    {
                        "decision_requests": [
                            {
                                "id": "research-queue-strategy-matrix-test",
                                "title": "研究決策",
                                "formal_agent": "research_worker",
                                "artifact_paths": ["artifacts/autonomous_research/a.json"],
                                "metrics": {"score": 1},
                                "pm_card": {
                                    "topic_name": "研究主題",
                                    "system_area": "TOP10 research queue",
                                    "potential_improvement": "改善研究排序。",
                                    "decision_point": "是否核准研究。",
                                    "next_harness": "research_worker",
                                    "decision_boundary": "不代表上線。",
                                    "evidence": [{"item": "artifacts/autonomous_research/a.json", "relevance": "證據"}],
                                },
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            state = load_state(Path(tmp) / "missing.json")
            run_dir, sent_keys = export_pm_review_cards(brief_path, state, "2026-06-27", 5)

            self.assertIsNotNone(run_dir)
            assert run_dir is not None
            cards = json.loads((run_dir / "cards.json").read_text(encoding="utf-8"))
            self.assertEqual(cards["project_domain"], "TOP10_STOCK")
            self.assertEqual(len(cards["cards"]), 1)
            card_id = next(iter(cards["cards"]))
            self.assertTrue(card_id.startswith("RH260627-"))
            card_text = (run_dir / f"{card_id}.md").read_text(encoding="utf-8")
            self.assertIn("TOP10_STOCK", card_text)
            self.assertIn("研究主題", card_text)
            self.assertEqual(len(sent_keys), 1)

    def test_skips_non_stock_decisions_before_exporting_cards(self):
        with tempfile.TemporaryDirectory() as tmp:
            brief_path = Path(tmp) / "brief.json"
            brief_path.write_text(
                json.dumps(
                    {
                        "decision_requests": [
                            {
                                "id": "ai-vibe-radar-r01",
                                "title": "AI Vibe Radar 研究卡",
                                "formal_agent": "gemini-researcher",
                                "artifact_paths": ["artifacts/ai_vibe/r01.json"],
                                "pm_card": {
                                    "topic_name": "AI Vibe Radar",
                                    "system_area": "ai-core skill-intake",
                                    "next_harness": "gemini-researcher",
                                },
                            },
                            {
                                "id": "research-queue-strategy-matrix-stock",
                                "title": "候選策略需要追加樣本或風控檢查",
                                "formal_agent": "research_worker",
                                "artifact_paths": ["artifacts/autonomous_research/next_action_queue.json"],
                                "metrics": {"score": 1},
                                "pm_card": {
                                    "topic_name": "股票策略研究",
                                    "system_area": "TOP10 research queue",
                                    "potential_improvement": "改善研究排序。",
                                    "decision_point": "是否核准研究。",
                                    "next_harness": "research_worker",
                                    "decision_boundary": "不代表上線。",
                                    "evidence": [{"item": "artifacts/autonomous_research/next_action_queue.json", "relevance": "證據"}],
                                },
                            },
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            state = load_state(Path(tmp) / "missing.json")
            run_dir, sent_keys = export_pm_review_cards(brief_path, state, "2026-06-27", 5)

            self.assertIsNotNone(run_dir)
            assert run_dir is not None
            cards = json.loads((run_dir / "cards.json").read_text(encoding="utf-8"))
            self.assertEqual(len(cards["cards"]), 1)
            card_id = next(iter(cards["cards"]))
            card_text = (run_dir / f"{card_id}.md").read_text(encoding="utf-8")
            self.assertIn("股票策略研究", card_text)
            self.assertNotIn("AI Vibe Radar", card_text)
            self.assertEqual(len(sent_keys), 1)

    def test_current_queue_depth_reads_next_action_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            original_artifacts_dir = harness_loop.ARTIFACTS_DIR
            try:
                harness_loop.ARTIFACTS_DIR = Path(tmp) / "artifacts"
                queue_path = harness_loop.ARTIFACTS_DIR / "autonomous_research" / "next_action_queue.json"
                queue_path.parent.mkdir(parents=True)
                queue_path.write_text(
                    json.dumps(
                        {
                            "actions": [
                                {"id": "candidate-1"},
                                {"id": "candidate-2"},
                                "invalid-row",
                            ]
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )

                self.assertEqual(harness_loop.current_queue_depth(), 2)
            finally:
                harness_loop.ARTIFACTS_DIR = original_artifacts_dir

    def test_top_up_research_queue_from_registry_adds_revisit_topics(self):
        with tempfile.TemporaryDirectory() as tmp:
            original_artifacts_dir = harness_loop.ARTIFACTS_DIR
            try:
                harness_loop.ARTIFACTS_DIR = Path(tmp) / "artifacts"
                research_dir = harness_loop.ARTIFACTS_DIR / "autonomous_research"
                research_dir.mkdir(parents=True)
                (research_dir / "next_action_queue.json").write_text(
                    json.dumps({"actions": [{"topic_id": "existing", "manager_status": "confirmed_for_next_replay"}]}),
                    encoding="utf-8",
                )
                (research_dir / "topic_registry.json").write_text(
                    json.dumps(
                        {
                            "topics": [
                                {"topic_id": "low", "manager_status": "rejected", "score": 1},
                                {"topic_id": "high", "manager_status": "rejected", "score": 9},
                                {"topic_id": "candidate", "manager_status": "candidate", "score": 20},
                            ]
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )

                added = harness_loop.top_up_research_queue_from_registry(min_depth=3, max_items=10)
                queue = json.loads((research_dir / "next_action_queue.json").read_text(encoding="utf-8"))

                self.assertEqual(added, 2)
                self.assertEqual([item["topic_id"] for item in queue["actions"]], ["existing", "high", "low"])
                self.assertEqual(queue["actions"][1]["next_action"], "rerun_rejected_with_larger_window_or_risk_check")
                self.assertEqual(queue["actions"][1]["queue_reason"], "pm_harness_low_water_revisit")
            finally:
                harness_loop.ARTIFACTS_DIR = original_artifacts_dir


if __name__ == "__main__":
    unittest.main()
