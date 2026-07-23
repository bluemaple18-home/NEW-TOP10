#!/usr/bin/env python3
"""驗證 overlay historical robustness artifact 的固定契約與可重算性。"""

from __future__ import annotations

import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_overlay_robustness_replay import (  # noqa: E402
    SCHEMA_VERSION,
    candidate_result,
    resolve_path,
)


ARTIFACT = PROJECT_ROOT / "docs/evidence/OVERLAY-ROBUSTNESS-REPLAY-01/artifact.json"


def main() -> int:
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["status"] == "OK"
    contract = payload["contract"]
    assert contract == {
        "paired_daily_delta": True,
        "bootstrap": "fold-stratified-circular-moving-block",
        "block_length": 10,
        "repetitions": 10000,
        "seed": 20260723,
        "confidence_interval": 0.95,
        "prospective_acceptance_replacement": False,
        "promotion_allowed": False,
    }
    expected = [
        candidate_result(
            label="chip_overlay_0.10",
            path=resolve_path(
                "artifacts/model_experiments/chip_point_in_time_portfolio_replay_2026-07-23.json"
            ),
            variant="chip_0.10",
            block_length=10,
            repetitions=10000,
            seed=20260723,
        ),
        candidate_result(
            label="event_constrained_overlay_0.10",
            path=resolve_path(
                "artifacts/model_experiments/event_constrained_portfolio_replay_2026-07-23.json"
            ),
            variant="event_0.10",
            block_length=10,
            repetitions=10000,
            seed=20260723,
        ),
    ]
    assert payload["candidates"] == expected
    assert all(row["promotion_allowed"] is False for row in payload["candidates"])
    print("OVERLAY_ROBUSTNESS_REPLAY_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
