"""本地 ETL 產物修復工具。

用途是從既有 `features.parquet` 重建衍生產物，避免只是缺 events/universe 就必須重跑外部抓資料。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from app.event_detector import EventDetector
from app.risk_filter import RiskFilter
from app.volume_indicators import VolumeIndicators


@dataclass(frozen=True)
class RepairResult:
    features_path: str
    events_path: str
    universe_path: str
    feature_rows: int
    event_rows: int
    universe_rows: int


class LocalOutputRepair:
    """只使用本地 features 重建必要衍生檔。"""

    def __init__(self, data_dir: str | Path = "data"):
        self.data_dir = Path(data_dir)
        self.clean_dir = self.data_dir / "clean"

    def repair(self) -> RepairResult:
        features_path = self.clean_dir / "features.parquet"
        if not features_path.exists():
            raise FileNotFoundError(f"找不到 features：{features_path}")

        features = pd.read_parquet(features_path)
        features = self._normalize_features(features)

        events = EventDetector(features).detect_all_events()
        universe = RiskFilter(features).apply_all_filters(
            suspended_list=[],
            min_listing_days=60,
            min_avg_value=10_000_000,
            min_price=10.0,
        )

        events_path = self.clean_dir / "events.parquet"
        universe_path = self.clean_dir / "universe.parquet"
        features.to_parquet(features_path, index=False)
        events.to_parquet(events_path, index=False)
        universe.to_parquet(universe_path, index=False)

        return RepairResult(
            features_path=str(features_path),
            events_path=str(events_path),
            universe_path=str(universe_path),
            feature_rows=len(features),
            event_rows=len(events),
            universe_rows=len(universe),
        )

    def _normalize_features(self, features: pd.DataFrame) -> pd.DataFrame:
        df = features.copy()
        df["date"] = pd.to_datetime(df["date"])
        df["stock_id"] = df["stock_id"].astype(str).str.strip()
        df = df.sort_values(["stock_id", "date"]).reset_index(drop=True)

        if "avg_value_20d" not in df.columns:
            df = VolumeIndicators(df).calculate_avg_trading_value(period=20)

        if "low_20d" not in df.columns and "low" in df.columns:
            df["low_20d"] = df.groupby("stock_id")["low"].transform(lambda values: values.shift(1).rolling(20).min())

        return df
