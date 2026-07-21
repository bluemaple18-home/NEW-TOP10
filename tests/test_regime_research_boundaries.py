from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

from scripts.research_regime_shadow_ranking import PROJECT_ROOT, validate_research_output_dir
from scripts.run_weekend_research_matrix import matrix_commands


def test_shadow_output_accepts_isolated_backtest_directory() -> None:
    source = PROJECT_ROOT / "artifacts" / "backtest" / "historical_rankings_current_model"
    output = PROJECT_ROOT / "artifacts" / "backtest" / "shadow_rankings_test"

    assert validate_research_output_dir(source, output) == output


@pytest.mark.parametrize(
    "output",
    [
        PROJECT_ROOT / "artifacts",
        PROJECT_ROOT / "artifacts" / "backtest",
        PROJECT_ROOT / "data" / "clean",
        PROJECT_ROOT / "models",
    ],
)
def test_shadow_output_rejects_non_isolated_directory(output: Path) -> None:
    source = PROJECT_ROOT / "artifacts"

    with pytest.raises(ValueError, match="output-dir"):
        validate_research_output_dir(source, output)


def test_shadow_output_rejects_source_directory() -> None:
    source = PROJECT_ROOT / "artifacts" / "backtest" / "historical_rankings_current_model"

    with pytest.raises(ValueError, match="dates-from-dir"):
        validate_research_output_dir(source, source)


def test_weekend_matrix_contains_no_fetch_train_or_live_steps() -> None:
    args = Namespace(skip_heavy=False, features="data/clean/features.parquet", max_ranking_files=2)
    commands = matrix_commands(args)
    flattened = " ".join(part for _, command in commands for part in command).lower()

    assert "fetch" not in flattened
    assert "train_model" not in flattened
    assert "live" not in flattened
    assert "send" not in flattened
