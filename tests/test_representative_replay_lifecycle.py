from __future__ import annotations

import unittest

from app.research import map_contract


class RepresentativeReplayLifecycleTests(unittest.TestCase):
    def test_completed_default_v2_replay_closes_only_the_base_scenario(self) -> None:
        topic = {
            "topic_id": "research:representative-topic",
            "candidate_dir": "artifacts/backtest/representative-topic",
        }
        dimensions = {
            "horizon": "3",
            "stop_loss": "none",
            "take_profit": "0.15",
            "group_exposure": "none",
            **map_contract.V2_DEFAULT_COORDINATES,
        }
        history = [
            {
                "schema_version": "research-map-run-history.v2",
                "map_version": "v2",
                "combo_id": map_contract.v2_combo_id(topic, dimensions),
                "dimensions": dimensions,
                "status": "completed",
                "decision": "LOW_INFORMATION",
                "insight_level": "low_information",
                "artifact_path": "artifacts/backtest/default-v2.json",
                "finished_at": "2099-01-01T00:00:00+00:00",
            }
        ]

        canonical_history = map_contract.canonicalize_lifecycle_history(history)
        scenarios = map_contract.apply_run_history(
            map_contract.build_combo_registry([topic]),
            canonical_history,
        )
        target = next(
            scenario
            for scenario in scenarios
            if scenario["combo_id"] == map_contract.combo_id(topic, dimensions)
        )

        self.assertEqual(canonical_history[0]["combo_id"], map_contract.combo_id(topic, dimensions))
        self.assertEqual(target["status"], "low_information")
        self.assertEqual(map_contract.completed_v2_expansion_count(canonical_history), 0)

    def test_completed_non_default_v2_replay_keeps_expansion_identity(self) -> None:
        topic = {"topic_id": "research:representative-topic"}
        dimensions = {
            "horizon": "3",
            "stop_loss": "none",
            "take_profit": "0.15",
            "group_exposure": "none",
            **map_contract.V2_DEFAULT_COORDINATES,
            "regime_gate": "BIG_BULL_ONLY",
        }
        expanded_combo_id = map_contract.v2_combo_id(topic, dimensions)
        history = [
            {
                "schema_version": "research-map-run-history.v2",
                "map_version": "v2",
                "combo_id": expanded_combo_id,
                "dimensions": dimensions,
                "status": "completed",
                "artifact_path": "artifacts/backtest/non-default-v2.json",
                "finished_at": "2099-01-01T00:00:00+00:00",
            }
        ]

        canonical_history = map_contract.canonicalize_lifecycle_history(history)

        self.assertEqual(canonical_history[0]["combo_id"], expanded_combo_id)
        self.assertEqual(map_contract.completed_v2_expansion_count(canonical_history), 1)


if __name__ == "__main__":
    unittest.main()
