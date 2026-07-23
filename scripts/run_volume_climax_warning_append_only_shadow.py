#!/usr/bin/env python3
"""累積 regime-conditioned volume-climax warning-only shadow ledger。"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "volume-climax-warning-shadow-ledger.v1"
RANKING_PATTERN = re.compile(r"^ranking_(\d{4}-\d{2}-\d{2})\.csv$")


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root 必須是 object：{path}")
    return payload


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(body)
        temporary = handle.name
    os.replace(temporary, path)


def normalize_stock_id(value: Any) -> str:
    text = str(value).strip()
    return text[:-2] if text.endswith(".0") else text


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ranking_files(directory: Path) -> list[tuple[str, Path]]:
    rows: list[tuple[str, Path]] = []
    for path in directory.glob("ranking_*.csv"):
        match = RANKING_PATTERN.fullmatch(path.name)
        if match:
            rows.append((match.group(1), path))
    return sorted(rows)


def new_ledger(config: dict[str, Any], config_path: Path) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "contract": config["contract"],
        "config": repo_path(config_path),
        "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
        "observations": [],
        "warnings_and_exclusions": [],
        "summary": {},
        "last_run_receipt": {},
    }


def build_observation(
    *,
    ranking_date: str,
    window: list[tuple[str, Path]],
    features: pd.DataFrame,
    features_sha256: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    current_ranking = pd.read_csv(window[-1][1], dtype={"stock_id": "string"})
    regimes = current_ranking["market_regime"].dropna().astype(str).unique().tolist()
    regime = regimes[0] if len(regimes) == 1 else "UNKNOWN"

    watchlist: dict[str, str] = {}
    for _, path in window:
        ranking = pd.read_csv(path, dtype={"stock_id": "string"})
        for row in ranking[["stock_id", "stock_name"]].itertuples(index=False):
            watchlist[normalize_stock_id(row.stock_id)] = str(row.stock_name)

    current_features = features.loc[
        (features["date"] == pd.Timestamp(ranking_date))
        & (features["stock_id"].isin(watchlist))
    ].copy()
    current_features["raw_signal"] = (
        current_features["volume_ratio_20d"].ge(float(config["volume_ratio_20d_min"]))
        & current_features["long_upper_shadow"].fillna(False).astype(bool)
    )
    flagged = current_features.loc[current_features["raw_signal"]].sort_values("stock_id")
    active = regime in set(config["active_regimes"])
    items = [
        {
            "stock_id": str(row.stock_id),
            "stock_name": watchlist.get(str(row.stock_id), str(row.stock_name)),
            "volume_ratio_20d": round(float(row.volume_ratio_20d), 6),
            "long_upper_shadow": bool(row.long_upper_shadow),
            "warning_active": active,
        }
        for row in flagged.itertuples(index=False)
    ]
    return {
        "ranking_date": ranking_date,
        "market_regime": regime,
        "ranking_window_dates": [date for date, _ in window],
        "source_hashes": {
            "features_sha256": features_sha256,
            "ranking_files": {
                path.name: file_sha256(path)
                for _, path in window
            },
        },
        "watchlist_stock_count": len(watchlist),
        "feature_rows_available": int(len(current_features)),
        "raw_signal_count": len(items),
        "active_warning_count": len(items) if active else 0,
        "warning_text": config["warning_text"] if active and items else None,
        "flagged_items": items,
        "production_ranking_changed": False,
        "push_sent": False,
    }


def run(
    *,
    config_path: Path,
    ledger_path: Path,
    rankings_dir: Path,
    features_path: Path,
    features: pd.DataFrame,
) -> dict[str, Any]:
    config = read_json(config_path)
    ledger = read_json(ledger_path) if ledger_path.exists() else new_ledger(config, config_path)
    if ledger["schema_version"] != SCHEMA_VERSION:
        raise ValueError("ledger schema_version 不符")
    if ledger["config_sha256"] != hashlib.sha256(config_path.read_bytes()).hexdigest():
        raise ValueError("frozen config 已變更；不得在原 ledger 續寫")

    existing = {str(row["ranking_date"]) for row in ledger["observations"]}
    files = ranking_files(rankings_dir)
    features_sha256 = file_sha256(features_path)
    appended = 0
    for index, (ranking_date, _) in enumerate(files):
        if ranking_date <= str(config["seal_date"]) or ranking_date in existing:
            continue
        window_size = int(config["watchlist_ranking_days"])
        window = files[max(0, index - window_size + 1) : index + 1]
        observation = build_observation(
            ranking_date=ranking_date,
            window=window,
            features=features,
            features_sha256=features_sha256,
            config=config,
        )
        ledger["observations"].append(observation)
        existing.add(ranking_date)
        appended += 1

    ledger["observations"] = sorted(ledger["observations"], key=lambda row: str(row["ranking_date"]))
    observation_count = len(ledger["observations"])
    required = int(config["required_observation_count"])
    ledger["summary"] = {
        "observation_count": observation_count,
        "required_observation_count": required,
        "raw_signal_count": sum(int(row["raw_signal_count"]) for row in ledger["observations"]),
        "active_warning_count": sum(int(row["active_warning_count"]) for row in ledger["observations"]),
        "status": "MONITORING" if observation_count else "WAITING_FOR_POST_SEAL_DATES",
        "promotion_ready": False,
    }
    ledger["last_run_receipt"] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "observations_appended": appended,
        "latest_ranking_date_seen": files[-1][0] if files else None,
        "features": repo_path(features_path),
        "rankings_dir": repo_path(rankings_dir),
    }
    atomic_write(ledger_path, ledger)
    return {
        "status": "OK",
        "ledger": repo_path(ledger_path),
        "observation_count": observation_count,
        "observations_appended": appended,
        "raw_signal_count": ledger["summary"]["raw_signal_count"],
        "active_warning_count": ledger["summary"]["active_warning_count"],
        "promotion_allowed": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="run append-only volume-climax warning shadow")
    parser.add_argument("--config", default="config/volume_climax_warning_shadow_v1.json")
    parser.add_argument(
        "--ledger",
        default="artifacts/model_experiments/volume_climax_warning_shadow_ledger_v1.json",
    )
    parser.add_argument("--rankings-dir", default="artifacts")
    parser.add_argument("--features", default="data/clean/features.parquet")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    features_path = resolve_path(args.features)
    features = pd.read_parquet(
        features_path,
        columns=["date", "stock_id", "stock_name", "volume_ratio_20d", "long_upper_shadow"],
    )
    features["date"] = pd.to_datetime(features["date"])
    features["stock_id"] = features["stock_id"].map(normalize_stock_id)
    result = run(
        config_path=resolve_path(args.config),
        ledger_path=resolve_path(args.ledger),
        rankings_dir=resolve_path(args.rankings_dir),
        features_path=features_path,
        features=features,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
