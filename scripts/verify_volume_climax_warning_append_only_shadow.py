#!/usr/bin/env python3
"""驗證 volume-climax warning shadow 的 regime 與 append-only 契約。"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_volume_climax_warning_append_only_shadow import (  # noqa: E402
    file_sha256,
    read_json,
    run,
    validate_ledger,
)


CONFIG_PATH = PROJECT_ROOT / "config/volume_climax_warning_shadow_v1.json"


def write_ranking(path: Path, regime: str) -> None:
    pd.DataFrame(
        [
            {"stock_id": "1101", "stock_name": "甲", "market_regime": regime},
            {"stock_id": "1102", "stock_name": "乙", "market_regime": regime},
        ]
    ).to_csv(path, index=False)


def refresh_summary(payload: dict, config: dict) -> None:
    observations = payload["observations"]
    payload["summary"] = {
        "observation_count": len(observations),
        "required_observation_count": int(config["required_observation_count"]),
        "raw_signal_count": sum(int(row["raw_signal_count"]) for row in observations),
        "active_warning_count": sum(int(row["active_warning_count"]) for row in observations),
        "status": "MONITORING" if observations else "WAITING_FOR_POST_SEAL_DATES",
        "promotion_ready": False,
    }


def assert_cli_rejects(
    *,
    payload: dict,
    ledger: Path,
    rankings: Path,
    features_path: Path,
) -> None:
    ledger.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts/run_volume_climax_warning_append_only_shadow.py"),
            "--config",
            str(CONFIG_PATH),
            "--ledger",
            str(ledger),
            "--rankings-dir",
            str(rankings),
            "--features",
            str(features_path),
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode != 0, completed.stdout


def verify_corrupt_ledgers(
    *,
    valid_payload: dict,
    ledger: Path,
    rankings: Path,
    features_path: Path,
) -> None:
    duplicate = deepcopy(valid_payload)
    duplicate["observations"].append(deepcopy(duplicate["observations"][0]))
    assert_cli_rejects(
        payload=duplicate,
        ledger=ledger,
        rankings=rankings,
        features_path=features_path,
    )

    pre_seal = deepcopy(valid_payload)
    row = pre_seal["observations"][0]
    old_name = next(iter(row["source_hashes"]["ranking_files"]))
    row["ranking_date"] = "2026-07-23"
    row["ranking_window_dates"] = ["2026-07-23"]
    row["source_hashes"]["ranking_files"] = {
        "ranking_2026-07-23.csv": row["source_hashes"]["ranking_files"][old_name]
    }
    refresh_summary(pre_seal, read_json(CONFIG_PATH))
    assert_cli_rejects(
        payload=pre_seal,
        ledger=ledger,
        rankings=rankings,
        features_path=features_path,
    )

    mutated_warning = deepcopy(valid_payload)
    mutated_warning["observations"][0]["warning_text"] = "語意遭改寫"
    assert_cli_rejects(
        payload=mutated_warning,
        ledger=ledger,
        rankings=rankings,
        features_path=features_path,
    )

    missing_source_hash = deepcopy(valid_payload)
    del missing_source_hash["observations"][0]["source_hashes"]["features_sha256"]
    assert_cli_rejects(
        payload=missing_source_hash,
        ledger=ledger,
        rankings=rankings,
        features_path=features_path,
    )

    for mutate in (
        lambda payload: payload.pop("config_sha256"),
        lambda payload: payload["observations"][0].update(production_ranking_changed=True),
        lambda payload: payload["observations"][0].update(push_sent=True),
    ):
        corrupted = deepcopy(valid_payload)
        mutate(corrupted)
        assert_cli_rejects(
            payload=corrupted,
            ledger=ledger,
            rankings=rankings,
            features_path=features_path,
        )


def verify_promotion_boundaries(valid_payload: dict) -> None:
    config = read_json(CONFIG_PATH)
    template = deepcopy(valid_payload["observations"][0])
    for count in (59, 60, 61):
        payload = deepcopy(valid_payload)
        payload["observations"] = []
        for offset in range(count):
            ranking_date = str(date(2026, 7, 24) + timedelta(days=offset))
            row = deepcopy(template)
            row["ranking_date"] = ranking_date
            row["ranking_window_dates"] = [ranking_date]
            row["source_hashes"]["ranking_files"] = {
                f"ranking_{ranking_date}.csv": "a" * 64
            }
            payload["observations"].append(row)
        refresh_summary(payload, config)
        payload["last_run_receipt"]["observations_appended"] = 0
        validate_ledger(payload, config=config, config_path=CONFIG_PATH)
        assert payload["summary"]["observation_count"] == count
        assert payload["summary"]["promotion_ready"] is False


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
        assert first_observation["production_ranking_changed"] is False
        assert first_observation["push_sent"] is False
        config = read_json(CONFIG_PATH)
        assert payload["config_sha256"] == file_sha256(CONFIG_PATH)
        assert payload["contract"] == config["contract"]
        assert payload["contract"]["warning_only"] is True
        assert payload["contract"]["changes_production_ranking"] is False
        assert payload["contract"]["sends_push"] is False
        assert payload["contract"]["production_promotion_allowed"] is False

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
        validate_ledger(payload, config=config, config_path=CONFIG_PATH)

        verify_corrupt_ledgers(
            valid_payload=payload,
            ledger=ledger,
            rankings=rankings,
            features_path=features_path,
        )
        verify_promotion_boundaries(payload)

    print("VOLUME_CLIMAX_WARNING_APPEND_ONLY_SHADOW_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
