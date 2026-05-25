"""看盤資料 repository。

目前資料來源仍是既有 pipeline 產物；未來改 DuckDB/Postgres 時只換這層。
"""

from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
import re
from typing import Any

import pandas as pd


class MarketRepository:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.data_dir = project_root / "data" / "clean"
        self.artifacts_dir = project_root / "artifacts"

    def features_exists(self) -> bool:
        return self.features_path.exists()

    def ranking_file_count(self) -> int:
        return len(list(self.artifacts_dir.glob("ranking_*.csv")))

    def latest_weekly_snapshot_path(self) -> Path | None:
        snapshot_files = sorted(
            self.artifacts_dir.glob("weekly_candidate_snapshot_*.json"),
            key=self._weekly_snapshot_sort_key,
        )
        return snapshot_files[-1] if snapshot_files else None

    @property
    def features_path(self) -> Path:
        return self.data_dir / "features.parquet"

    @lru_cache(maxsize=1)
    def load_features(self) -> pd.DataFrame:
        if not self.features_path.exists():
            raise FileNotFoundError(f"找不到特徵檔：{self.features_path}")

        df = pd.read_parquet(self.features_path)
        df["stock_id"] = df["stock_id"].astype(str).str.strip()
        df["date"] = pd.to_datetime(df["date"])
        return df.sort_values(["stock_id", "date"])

    @lru_cache(maxsize=1)
    def load_latest_ranking(self) -> tuple[pd.DataFrame, str | None]:
        ranking_files = sorted(self.artifacts_dir.glob("ranking_*.csv"), key=self._ranking_sort_key)
        if not ranking_files:
            return pd.DataFrame(), None

        latest_file = ranking_files[-1]
        df = pd.read_csv(latest_file, dtype={"stock_id": str})
        df["stock_id"] = df["stock_id"].astype(str).str.strip()
        return df, latest_file.stem.replace("ranking_", "")

    @lru_cache(maxsize=1)
    def load_latest_weekly_snapshot(self) -> tuple[pd.DataFrame, dict[str, Any] | None]:
        snapshot_path = self.latest_weekly_snapshot_path()
        if snapshot_path is None:
            return pd.DataFrame(), None

        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
        rows = payload.get("model_pool") or []
        if not rows:
            return pd.DataFrame(), {**payload, "artifact_path": str(snapshot_path)}
        frame = pd.DataFrame(rows)
        if "ranking" in frame.columns:
            ranking_rows = []
            for row in rows:
                ranking = row.get("ranking") or {}
                ranking_rows.append(ranking)
            frame = pd.DataFrame(ranking_rows)
        if "stock_id" in frame.columns:
            frame["stock_id"] = frame["stock_id"].astype(str).str.strip()
        return frame, {**payload, "artifact_path": str(snapshot_path)}

    def _ranking_sort_key(self, path: Path) -> tuple[pd.Timestamp, float]:
        match = re.match(r"ranking_(\d{4}-\d{2}-\d{2})$", path.stem)
        if match:
            return pd.Timestamp(match.group(1)), path.stat().st_mtime
        return pd.Timestamp.min, path.stat().st_mtime

    def _weekly_snapshot_sort_key(self, path: Path) -> tuple[pd.Timestamp, float]:
        match = re.match(r"weekly_candidate_snapshot_(\d{4}-\d{2}-\d{2})$", path.stem)
        if match:
            return pd.Timestamp(match.group(1)), path.stat().st_mtime
        return pd.Timestamp.min, path.stat().st_mtime

    def clear_cache(self) -> None:
        self.load_features.cache_clear()
        self.load_latest_ranking.cache_clear()
        self.load_latest_weekly_snapshot.cache_clear()
