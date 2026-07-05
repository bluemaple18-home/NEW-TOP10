from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
