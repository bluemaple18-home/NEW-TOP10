from __future__ import annotations

import json
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import ANY, call, patch

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
                            {
                                "queue_type": "REPRESENTATIVE_REPLAY",
                                "current_status": "PENDING",
                                "combo_id": "pending-combo",
                                "representative_combo_id": "representative-combo",
                            },
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
        self.assertEqual(summary["representative_combo_ids"], ["representative-combo"])

    def test_idle_stop_reason_does_not_call_nonempty_queue_empty(self) -> None:
        self.assertEqual(worker.idle_stop_reason({"representative_replay_count": 144}), "max_batches_reached")
        self.assertEqual(worker.idle_stop_reason({"representative_replay_count": 0}), "queue_empty")

    def test_batch_progress_accepts_identity_change_but_not_forced_duplicate_append(self) -> None:
        before = {"representative_combo_ids": ["combo-a", "combo-b"]}
        after = {"representative_combo_ids": ["combo-b", "combo-c"]}

        identity_progress = worker.batch_progress_evidence(
            before,
            after,
            {"appended_run_history_count": 0},
            force_append=False,
        )
        forced_duplicate = worker.batch_progress_evidence(
            before,
            before,
            {"appended_run_history_count": 24},
            force_append=True,
        )

        self.assertTrue(identity_progress["progressed"])
        self.assertTrue(identity_progress["representative_identity_changed"])
        self.assertFalse(forced_duplicate["progressed"])
        self.assertTrue(forced_duplicate["force_append_ignored_as_progress"])

    def test_drain_stops_after_first_successful_batch_without_new_evidence_or_identity_change(self) -> None:
        args = Namespace(
            date="2099-01-05",
            run_id="no-progress-fixture",
            artifacts_dir=Path("artifacts"),
            batch_size=24,
            max_batches=6,
            max_seconds=3600,
            rerun=False,
            force_append=False,
            skip_initial_linkage=True,
            lock_dir=Path("logs/representative_replay_drain.lock"),
            no_lock=True,
        )
        unchanged_queue = {
            "queue_path": "artifacts/weekend_training/weekend_frontier_queue_2099-01-05.json",
            "status": "OK",
            "representative_replay_count": 144,
            "deferred_low_priority_count": 3906,
            "queue_count": 144,
            "representative_combo_ids": [f"combo-{index:03d}" for index in range(144)],
        }
        successful_command = worker.CommandResult(
            name="fixture",
            command=["fixture"],
            returncode=0,
            stdout="",
            stderr="",
            started_at="2099-01-05T00:00:00+00:00",
            finished_at="2099-01-05T00:00:01+00:00",
        )
        written_payloads: list[dict[str, object]] = []

        with (
            patch.object(worker, "parse_args", return_value=args),
            patch.object(worker, "resolve_path", side_effect=lambda value: worker.PROJECT_ROOT / value),
            patch.object(worker, "queue_summary", return_value=unchanged_queue.copy()),
            patch.object(worker, "run_command", return_value=successful_command) as run_command,
            patch.object(worker, "representative_paths", return_value=(Path("representative.json"), Path("representative.md"))),
            patch.object(
                worker,
                "read_json",
                return_value={
                    "summary": {
                        "selected_count": 24,
                        "completed_count": 24,
                        "appended_run_history_count": 0,
                    }
                },
            ),
            patch.object(worker, "write_progress", side_effect=lambda _path, payload: written_payloads.append(payload)),
            patch.object(worker, "write_research_worker_event"),
        ):
            exit_code = worker.main()

        replay_calls = [
            entry
            for entry in run_command.call_args_list
            if str(entry.args[0]).startswith("representative_replay_batch_")
        ]
        self.assertEqual(exit_code, 1)
        self.assertEqual(replay_calls, [call("representative_replay_batch_1", ANY)])
        self.assertEqual(written_payloads[-1]["status"], "NO_PROGRESS")
        self.assertEqual(written_payloads[-1]["stop_reason"], "no_progress")
        self.assertEqual(written_payloads[-1]["summary"]["batch_count"], 1)  # type: ignore[index]


if __name__ == "__main__":
    unittest.main()
