"""M4-02 full feature training contract smoke test。

只驗證資料契約、feature selection、metadata 與 split guard，
不跑完整 LightGBM 訓練。
"""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agent_b_modeling import LightGBMTrainer
from app.data.fundamental_repository import FundamentalRepository


def main() -> int:
    verify_prepare_train_data_uses_all_feature_groups()
    verify_default_loader_builds_m4_contract()
    print("M4_FULL_FEATURES_OK")
    return 0


def verify_prepare_train_data_uses_all_feature_groups() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        clean_dir = root / "data" / "clean"
        clean_dir.mkdir(parents=True)
        _write_training_fixture(clean_dir)

        repository = FundamentalRepository(root)
        repository.write_cached(
            "1101",
            {
                "metrics": [
                    {"year": "2023", "roe": 12.5, "gross_margin": 38.0, "debt_ratio": 42.0},
                    {"year": "2024", "roe": 15.5, "gross_margin": 41.0, "debt_ratio": 39.0},
                ]
            },
        )

        old_cwd = Path.cwd()
        try:
            import os

            os.chdir(root)
            trainer = LightGBMTrainer(data_dir=str(clean_dir), model_dir=str(root / "models"), artifact_dir=str(root / "artifacts"))
            features = trainer.load_features()
        finally:
            os.chdir(old_cwd)

        labeled = trainer.generate_labels(features)
        X, y, feature_cols = trainer.prepare_train_data(labeled)
        metadata = trainer.model_metadata

    assert len(X) == len(y)
    assert "ma20" in feature_cols
    assert "event_break_20d_high" in feature_cols
    assert "fundamental_roe" in feature_cols
    assert "trade_date" not in feature_cols
    assert "target" not in feature_cols
    assert "future_return" not in feature_cols
    assert "future_close" not in feature_cols
    assert metadata["used_feature_groups"]["technical"]
    assert metadata["used_feature_groups"]["event"]
    assert "pattern" in metadata["used_feature_groups"]
    assert metadata["used_feature_groups"]["fundamental"]
    assert metadata["fundamental_cache_coverage"] == 1.0

    train_dates = pd.date_range("2024-01-01", periods=20).values
    val_dates = pd.date_range("2024-01-21", periods=5).values
    purged = trainer._purge_train_dates(train_dates, val_dates)
    assert pd.Timestamp(purged.max()) < pd.Timestamp("2024-01-11")


def verify_default_loader_builds_m4_contract() -> None:
    trainer = LightGBMTrainer(data_dir="data/clean")
    frame = trainer.load_features()
    X, _, feature_cols = trainer.prepare_train_data(_with_dummy_target(frame.head(50)))
    assert frame[["trade_date", "stock_id"]].duplicated().sum() == 0
    assert trainer.feature_metadata is not None
    assert set(trainer.feature_metadata.feature_groups) == {"technical", "event", "pattern", "fundamental"}
    assert any(col.startswith("event_") for col in feature_cols)
    assert any(col.startswith("fundamental_") for col in trainer.feature_metadata.feature_groups["fundamental"].columns)
    if trainer.feature_metadata.fundamental_cache_coverage < 0.8:
        assert not any(col.startswith("fundamental_") for col in feature_cols)
    assert len(X) == 50


def _with_dummy_target(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["target"] = 0
    result["future_return"] = 0.0
    result["entry_price"] = result["open"]
    result["exit_price"] = result["close"]
    result["future_close"] = result["close"]
    result["return_long"] = 0.0
    result["return_5d"] = 0.0
    return result


def _write_training_fixture(clean_dir: Path) -> None:
    rows = []
    events = []
    dates = pd.bdate_range("2024-04-01", periods=18)
    for date_index, date in enumerate(dates):
        rows.append(
            {
                "date": date,
                "stock_id": "1101",
                "symbol": "1101.TW",
                "open": 10 + date_index,
                "high": 11 + date_index,
                "low": 9 + date_index,
                "close": 10.5 + date_index,
                "volume": 1000 + date_index,
                "ma20": 10 + date_index / 10,
                "rsi": 50 + date_index / 10,
            }
        )
        events.append(
            {
                "date": date,
                "stock_id": "1101",
                "break_20d_high": 1 if date_index % 3 == 0 else 0,
            }
        )
    pd.DataFrame(rows).to_parquet(clean_dir / "features.parquet", index=False)
    pd.DataFrame(events).to_parquet(clean_dir / "events.parquet", index=False)


if __name__ == "__main__":
    raise SystemExit(main())
