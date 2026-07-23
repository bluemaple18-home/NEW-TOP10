#!/usr/bin/env python3
"""驗證 volume-climax warning shadow 的 regime 與 append-only 契約。"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_volume_climax_warning_append_only_shadow import read_json, run  # noqa: E402


CONFIG_PATH = PROJECT_ROOT / "config/volume_climax_warning_shadow_v1.json"


def write_ranking(path: Path, regime: str) -> None:
    pd.DataFrame(
        [
            {"stock_id": "1101", "stock_name": "甲", "market_regime": regime},
            {"stock_id": "1102", "stock_name": "乙", "market_regime": regime},
        ]
    ).to_csv(path, index=False)


def main() -> int:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        rankings = root / "rankings"
        rankings.mkdir()
        ledger = root / "ledger.json"
        features_path = root / "features.parquet"
        features = pd.DataFrame(
            [
                {
                    "date": pd.Timestamp("2026-07-24"),
                    "stock_id": "1101",
                    "stock_name": "甲",
                    "volume_ratio_20d": 2.0,
                    "long_upper_shadow": True,
                },
                {
                    "date": pd.Timestamp("2026-07-24"),
                    "stock_id": "1102",
                    "stock_name": "乙",
                    "volume_ratio_20d": 3.0,
                    "long_upper_shadow": False,
                },
                {
                    "date": pd.Timestamp("2026-07-25"),
                    "stock_id": "1101",
                    "stock_name": "甲",
                    "volume_ratio_20d": 2.1,
                    "long_upper_shadow": True,
                },
                {
                    "date": pd.Timestamp("2026-07-25"),
                    "stock_id": "1102",
                    "stock_name": "乙",
                    "volume_ratio_20d": 1.0,
                    "long_upper_shadow": True,
                },
            ]
        )
        features.to_parquet(features_path, index=False)
        write_ranking(rankings / "ranking_2026-07-24.csv", "RISK_ON")

        first = run(
            config_path=CONFIG_PATH,
            ledger_path=ledger,
            rankings_dir=rankings,
            features_path=features_path,
            features=features,
        )
        assert first["observations_appended"] == 1
        payload = read_json(ledger)
        first_observation = json.loads(json.dumps(payload["observations"][0]))
        assert first_observation["raw_signal_count"] == 1
        assert first_observation["active_warning_count"] == 1
        assert first_observation["warning_text"] == "短線追價要保守"

        second = run(
            config_path=CONFIG_PATH,
            ledger_path=ledger,
            rankings_dir=rankings,
            features_path=features_path,
            features=features,
        )
        assert second["observations_appended"] == 0
        assert read_json(ledger)["observations"] == [first_observation]

        write_ranking(rankings / "ranking_2026-07-25.csv", "RISK_OFF")
        third = run(
            config_path=CONFIG_PATH,
            ledger_path=ledger,
            rankings_dir=rankings,
            features_path=features_path,
            features=features,
        )
        assert third["observations_appended"] == 1
        payload = read_json(ledger)
        assert payload["observations"][0] == first_observation
        assert payload["observations"][1]["raw_signal_count"] == 1
        assert payload["observations"][1]["active_warning_count"] == 0
        assert payload["observations"][1]["warning_text"] is None
        assert payload["summary"]["promotion_ready"] is False

    print("VOLUME_CLIMAX_WARNING_APPEND_ONLY_SHADOW_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
