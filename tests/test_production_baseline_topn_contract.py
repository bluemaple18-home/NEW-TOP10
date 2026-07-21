from __future__ import annotations

import argparse
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import build_production_baseline_harness as harness


def harness_args() -> argparse.Namespace:
    return argparse.Namespace(
        date="2026-07-21",
        start_date="2026-01-01",
        end_date="2026-07-21",
        data_dir="data/clean",
        model_dir="models",
        config="config/signals.yaml",
        stride=1,
        max_dates=None,
        top_n=10,
        legacy_per_date_load=False,
    )


class ProductionBaselineTopNContractTest(unittest.TestCase):
    def test_internal_generator_is_fixed_to_top10(self) -> None:
        args = harness_args()

        internal = harness.build_internal_args(args, Path("staging"), Path("manifest.json"))

        self.assertEqual(internal.top_n, 10)

    def test_recorded_generator_command_is_replayable_with_top10(self) -> None:
        args = harness_args()

        command = harness.build_generator_command(args, Path("artifacts/weekend_training/staging/test"))

        self.assertIn("--top-n", command)
        self.assertEqual(command[command.index("--top-n") + 1], "10")


if __name__ == "__main__":
    unittest.main()
