from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import scripts.run_representative_replay_drain_worker as worker


class RepresentativeReplayDrainWorkerTest(unittest.TestCase):
    def test_queue_summary_counts_pending_representatives_from_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            queue = Path(tmp) / "queue.json"
            queue.write_text(
                json.dumps(
                    {
                        "status": "OK",
                        "summary": {
                            "representative_replay_count": 144,
                            "deferred_low_priority_count": 3906,
                            "queue_count": 100,
                        },
                        "items": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with patch.object(worker, "queue_paths", return_value=(queue, queue.with_suffix(".md"))):
                summary = worker.queue_summary("2026-06-25")

        self.assertEqual(summary["representative_replay_count"], 144)
        self.assertEqual(summary["deferred_low_priority_count"], 3906)

    def test_queue_summary_falls_back_to_items_when_summary_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            queue = Path(tmp) / "queue.json"
            queue.write_text(
                json.dumps(
                    {
                        "status": "OK",
                        "items": [
                            {"queue_type": "REPRESENTATIVE_REPLAY", "current_status": "PENDING"},
                            {"queue_type": "REPRESENTATIVE_REPLAY", "current_status": "DONE"},
                            {"queue_type": "UNSUPPORTED", "current_status": "PENDING"},
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with patch.object(worker, "queue_paths", return_value=(queue, queue.with_suffix(".md"))):
                summary = worker.queue_summary("2026-06-25")

        self.assertEqual(summary["representative_replay_count"], 1)
        self.assertEqual(summary["queue_count"], 3)

    def test_idle_stop_reason_does_not_call_nonempty_queue_empty(self) -> None:
        self.assertEqual(worker.idle_stop_reason({"representative_replay_count": 144}), "max_batches_reached")
        self.assertEqual(worker.idle_stop_reason({"representative_replay_count": 0}), "queue_empty")


if __name__ == "__main__":
    unittest.main()
