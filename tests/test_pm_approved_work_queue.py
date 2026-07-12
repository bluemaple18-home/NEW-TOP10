from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_pm_approved_work_queue import build_payload, write_json, write_research_cards


class PMApprovedWorkQueueTests(unittest.TestCase):
    def test_approved_cards_route_to_work_queue_and_research_cards(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "artifacts" / "pm_review_cards" / "run"
            run_dir.mkdir(parents=True)
            (run_dir / "pm_decision_state.json").write_text(
                json.dumps(
                    {
                        "schema_version": "top10.pm_decision_state.v1",
                        "project_domain": "TOP10_STOCK",
                        "cards": {
                            "PMR1": {
                                "card_id": "PMR1",
                                "project_domain": "TOP10_STOCK",
                                "title": "研究卡",
                                "owner": "research_worker",
                                "next_harness": "research_worker",
                                "decision": "approve",
                                "decided_at": "2026-06-27T00:00:00Z",
                                "run_dir": "artifacts/pm_review_cards/run",
                            },
                            "PMR2": {
                                "card_id": "PMR2",
                                "project_domain": "TOP10_STOCK",
                                "title": "狀態卡",
                                "owner": "top10-card-state-recorder",
                                "next_harness": "top10-card-state-recorder",
                                "decision": "approve",
                                "decided_at": "2026-06-27T00:01:00Z",
                                "run_dir": "artifacts/pm_review_cards/run",
                            },
                            "PMR4": {
                                "card_id": "PMR4",
                                "project_domain": "TOP10_STOCK",
                                "title": "PM harness continuation",
                                "owner": "pm_research_harness",
                                "next_harness": "pm_research_harness",
                                "decision": "approve",
                                "decided_at": "2026-06-27T00:01:30Z",
                                "run_dir": "artifacts/pm_review_cards/run",
                            },
                            "PMR5": {
                                "card_id": "PMR5",
                                "project_domain": "TOP10_STOCK",
                                "title": "外部檢核分歧處置",
                                "owner": "disagreement_next_actions",
                                "next_harness": "disagreement_next_actions",
                                "decision": "approve",
                                "decided_at": "2026-06-27T00:01:45Z",
                                "run_dir": "artifacts/pm_review_cards/run",
                            },
                            "PMR3": {
                                "card_id": "PMR3",
                                "project_domain": "TOP10_STOCK",
                                "title": "否決卡",
                                "owner": "research_worker",
                                "next_harness": "research_worker",
                                "decision": "reject",
                                "decided_at": "2026-06-27T00:02:00Z",
                                "run_dir": "artifacts/pm_review_cards/run",
                            },
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            payload = build_payload(run_dir, "2026-06-27")
            output = run_dir / "approved_work_queue.json"
            research_output = Path(tmp) / "artifacts" / "autonomous_research" / "research_cards_2026-06-27.jsonl"
            write_json(output, payload)
            research_cards = write_research_cards(research_output, payload, "2026-06-27")

            self.assertEqual(payload["summary"]["approved_count"], 4)
            self.assertEqual(payload["project_domain"], "TOP10_STOCK")
            self.assertEqual(payload["summary"]["route_counts"]["research_worker"], 3)
            self.assertEqual(payload["summary"]["route_counts"]["pm_card_state"], 1)
            self.assertEqual(len(research_cards), 3)
            self.assertEqual(research_cards[0]["source_pm_card_id"], "PMR1")
            self.assertEqual(research_cards[1]["source_pm_card_id"], "PMR4")
            self.assertEqual(research_cards[2]["source_pm_card_id"], "PMR5")
            self.assertEqual(research_cards[2]["next_harness"], "disagreement_next_actions")
            self.assertEqual(research_cards[0]["project_domain"], "TOP10_STOCK")
            self.assertTrue(research_cards[0]["contract"]["research_only"])
            self.assertIn("blocked_conditions", research_cards[0])

    def test_missing_project_domain_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "artifacts" / "pm_review_cards" / "run"
            run_dir.mkdir(parents=True)
            (run_dir / "pm_decision_state.json").write_text(
                json.dumps(
                    {
                        "schema_version": "top10.pm_decision_state.v1",
                        "cards": {
                            "PMR1": {
                                "card_id": "PMR1",
                                "title": "舊卡",
                                "owner": "research_worker",
                                "next_harness": "research_worker",
                                "decision": "approve",
                                "run_dir": "artifacts/pm_review_cards/run",
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            payload = build_payload(run_dir, "2026-06-27")

            self.assertEqual(payload["status"], "SKIPPED")
            self.assertEqual(payload["items"], [])
            self.assertEqual(payload["summary"]["skipped_reason"], "project_domain mismatch or missing")


if __name__ == "__main__":
    unittest.main()
