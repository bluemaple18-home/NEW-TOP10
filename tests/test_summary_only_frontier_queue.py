from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import build_weekend_frontier_queue as frontier
import build_weekend_training_rollup as rollup
import verify_weekend_frontier_queue as verifier


def representative(combo_id: str, priority: int) -> dict[str, object]:
    return {
        "combo_id": combo_id,
        "topic_id": f"topic-{combo_id}",
        "candidate_dir": f"artifacts/candidates/{combo_id}",
        "dimensions": {"horizon": "5"},
        "current_status": "PENDING",
        "burn_down_status": "REPRESENTATIVE_REPLAY_REQUIRED",
        "equivalence_key": f"eq-{combo_id}",
        "representative_combo_id": combo_id,
        "priority_score": priority,
        "source_artifact": None,
    }


class SummaryOnlyFrontierQueueTest(unittest.TestCase):
    def test_bounded_payload_materializes_only_next_representatives(self) -> None:
        rows = [
            representative("low", 1),
            representative("high", 9),
            representative("mid", 5),
            {
                **representative("unsupported", 99),
                "burn_down_status": "UNSUPPORTED_INPUT",
            },
        ]

        payload = frontier.build_bounded_payload(
            "2026-07-20",
            rows,
            inventory_count=2_866_752,
            representative_required_count=3,
            max_representatives=2,
        )

        self.assertEqual(payload["contract"]["materialization_mode"], "BOUNDED_REPRESENTATIVES")
        self.assertEqual(payload["summary"]["inventory_count"], 2_866_752)
        self.assertEqual(payload["summary"]["representative_required_count"], 3)
        self.assertEqual(payload["summary"]["representative_replay_count"], 2)
        self.assertEqual([row["combo_id"] for row in payload["items"]], ["high", "mid"])

    def test_verifier_accepts_bounded_queue_against_summary_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory_path = root / "inventory.json"
            queue_path = root / "queue.json"
            inventory_path.write_text(
                json.dumps(
                    {
                        "schema_version": "weekend-universe-inventory.v1",
                        "contract": {"records_inline": False},
                        "summary": {
                            "full_universe_total": 2_866_752,
                            "representative_required_count": 59_514,
                        },
                    }
                ),
                encoding="utf-8",
            )
            queue_path.write_text(
                json.dumps(
                    frontier.build_bounded_payload(
                        "2026-07-20",
                        [representative("next", 9)],
                        inventory_count=2_866_752,
                        representative_required_count=59_514,
                        max_representatives=1,
                    )
                ),
                encoding="utf-8",
            )

            result = verifier.build_payload("2026-07-20", queue_path, inventory_path)

        self.assertEqual(result["status"], "OK")
        self.assertFalse(result["errors"])

    def test_verifier_rejects_empty_bounded_queue_when_backlog_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory_path = root / "inventory.json"
            queue_path = root / "queue.json"
            inventory_path.write_text(
                json.dumps(
                    {
                        "summary": {
                            "full_universe_total": 2_866_752,
                            "representative_required_count": 59_514,
                        }
                    }
                ),
                encoding="utf-8",
            )
            queue_path.write_text(
                json.dumps(
                    {
                        "schema_version": "weekend-frontier-queue.v1",
                        "production_impact": "NO_PRODUCTION_CHANGE",
                        "contract": {"materialization_mode": "BOUNDED_REPRESENTATIVES"},
                        "policy": {"max_representatives": 144},
                        "summary": {
                            "inventory_count": 2_866_752,
                            "representative_required_count": 59_514,
                            "queue_count": 0,
                            "representative_replay_count": 0,
                        },
                        "items": [],
                    }
                ),
                encoding="utf-8",
            )

            result = verifier.build_payload("2026-07-20", queue_path, inventory_path)

        self.assertEqual(result["status"], "FAILED")
        self.assertIn("queue_count_matches_inventory_contract", {row["name"] for row in result["errors"]})

    def test_rollup_uses_inventory_equivalence_count_for_bounded_queue(self) -> None:
        count = rollup.pending_equivalence_inherited_count(
            {"REPRESENTATIVE_REPLAY": 144},
            {"EQUIVALENCE_INHERITED": 177_342},
            processed_before=30_461,
            materialization_mode="BOUNDED_REPRESENTATIVES",
        )

        self.assertEqual(count, 177_342)


if __name__ == "__main__":
    unittest.main()
