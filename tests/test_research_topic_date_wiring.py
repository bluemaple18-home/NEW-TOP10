from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import build_research_campaign_progress as progress
import research_map_linkage_smoke as linkage


RUN_DATE = "2099-01-08"


class FakeAutonomousModule:
    def __init__(self) -> None:
        self.observed_date: str | None = None

    def generate_topics(self, args: Any) -> list[Any]:
        self.observed_date = args.date
        return []

    def topic_to_json(self, topic: Any) -> dict[str, Any]:
        raise AssertionError(f"unexpected topic: {topic}")


def test_campaign_progress_passes_explicit_date_to_topic_generation(
    monkeypatch,
    tmp_path: Path,
) -> None:
    fake = FakeAutonomousModule()
    monkeypatch.setattr(progress, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(progress, "load_autonomous_module", lambda: fake)

    payload = progress.build_payload(
        argparse.Namespace(
            date=RUN_DATE,
            baseline_dir="artifacts/backtest/historical_rankings_current_model",
            min_ranking_files=3,
            max_ranking_files=8,
            max_topics=100,
            batch_size=20,
        )
    )

    assert fake.observed_date == RUN_DATE
    assert payload["date"] == RUN_DATE


def test_linkage_smoke_passes_explicit_date_to_topic_generation(
    monkeypatch,
    tmp_path: Path,
) -> None:
    fake = FakeAutonomousModule()
    monkeypatch.setattr(linkage, "AUTO_DIR", tmp_path)
    monkeypatch.setattr(linkage, "load_autonomous_module", lambda: fake)

    assert linkage.load_topics(RUN_DATE, max_topics=100) == []
    assert fake.observed_date == RUN_DATE
