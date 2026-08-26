"""儲存驗證專用的離線行情快照接縫。

這個模組只替換 FetchStage 的 provider acquisition；後續 ETL stage 維持原本組合。
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


VALIDATION_MODE_ENV = "TOP10_STORAGE_VALIDATION_MODE"
SNAPSHOT_INPUT_ENV = "TOP10_VALIDATION_SNAPSHOT_INPUT"
SNAPSHOT_SHA256_ENV = "TOP10_VALIDATION_SNAPSHOT_SHA256"
REQUIRED_COLUMNS = (
    "date",
    "stock_id",
    "stock_name",
    "market",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "value",
)
NUMERIC_COLUMNS = ("open", "high", "low", "close", "volume", "value")
MIN_STOCKS = 5
MIN_TRADE_DATES = 60
MIN_LATEST_COVERAGE = 0.95
REQUIRED_MARKETS = frozenset({"TWSE", "TPEX"})


class ValidationSnapshotError(ValueError):
    """離線驗證快照不符合代表性輸入契約。"""


@dataclass(frozen=True)
class ValidationSnapshot:
    """已驗證、可交給既有 FetchStage 後續流程的行情資料。"""

    frame: pd.DataFrame
    metadata: dict[str, Any]


class ValidationSnapshotProvider:
    """保留 FetchStage 需要的最小 provider 介面，且完全不連網。"""

    def __init__(self, frame: pd.DataFrame) -> None:
        self._frame = frame.copy()

    def fetch_historical_data(self, start_date: str, end_date: str) -> pd.DataFrame:
        start = pd.Timestamp(start_date).normalize()
        end = pd.Timestamp(end_date).normalize()
        return self._frame[(self._frame["date"] >= start) & (self._frame["date"] <= end)].copy()

    def fetch_suspended_stocks_list(self) -> list[str]:
        return []


def validation_mode_enabled() -> bool:
    return os.environ.get(VALIDATION_MODE_ENV, "").strip() == "1"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_validation_snapshot(path: Path | str, *, expected_sha256: str | None = None) -> ValidationSnapshot:
    """讀取並驗證已物化的真實行情快照；不合格資料一律拒絕。"""

    snapshot_path = Path(path)
    if not snapshot_path.is_file() or snapshot_path.is_symlink():
        raise ValidationSnapshotError("驗證行情快照必須是存在且非 symlink 的一般檔案")
    actual_sha256 = sha256_file(snapshot_path)
    if expected_sha256 and actual_sha256 != expected_sha256:
        raise ValidationSnapshotError("驗證行情快照 SHA-256 與 digest-pinned input 不符")
    frame = _read_snapshot(snapshot_path)
    normalized, coverage = _validate_and_normalize(frame)
    return ValidationSnapshot(
        frame=normalized,
        metadata={
            "path": str(snapshot_path),
            "sha256": actual_sha256,
            "size_bytes": snapshot_path.stat().st_size,
            "coverage": coverage,
        },
    )


def load_validation_snapshot_from_environment() -> ValidationSnapshot:
    """從 validation-only child 的 materialized input 讀取快照。"""

    path_text = os.environ.get(SNAPSHOT_INPUT_ENV)
    if not path_text:
        raise ValidationSnapshotError("validation mode 缺少 digest-pinned snapshot input")
    return load_validation_snapshot(
        Path(path_text),
        expected_sha256=os.environ.get(SNAPSHOT_SHA256_ENV) or None,
    )


def require_snapshot_window(snapshot: ValidationSnapshot, *, start_date: str, end_date: str) -> None:
    """拒絕只覆蓋局部日期的快照，避免把縮短 ETL 偽裝成代表性週期。"""

    requested_start = pd.Timestamp(start_date).normalize()
    requested_end = pd.Timestamp(end_date).normalize()
    actual_start = snapshot.frame["date"].min()
    actual_end = snapshot.frame["date"].max()
    if actual_start > requested_start or actual_end < requested_end:
        raise ValidationSnapshotError(
            "驗證行情快照未完整覆蓋 canonical ETL window："
            f"requested={requested_start.date()}..{requested_end.date()} "
            f"actual={actual_start.date()}..{actual_end.date()}"
        )


def _read_snapshot(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return pd.read_parquet(path)
    if suffix == ".csv":
        return pd.read_csv(path, dtype={"stock_id": "string"})
    raise ValidationSnapshotError("驗證行情快照僅接受 .parquet 或 .csv")


def _validate_and_normalize(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    if frame.empty:
        raise ValidationSnapshotError("驗證行情快照不可為空")
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValidationSnapshotError(f"驗證行情快照缺少必要欄位：{missing}")

    normalized = frame.copy()
    normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce").dt.normalize()
    if normalized["date"].isna().any():
        raise ValidationSnapshotError("驗證行情快照包含無效交易日")
    normalized["stock_id"] = normalized["stock_id"].astype(str).str.strip()
    normalized["stock_name"] = normalized["stock_name"].astype(str).str.strip()
    normalized["market"] = normalized["market"].astype(str).str.strip().str.upper()
    if (normalized["stock_id"] == "").any() or (normalized["stock_name"] == "").any():
        raise ValidationSnapshotError("驗證行情快照包含空白股票代號或名稱")

    for column in NUMERIC_COLUMNS:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
        if normalized[column].isna().any() or (normalized[column] <= 0).any():
            raise ValidationSnapshotError(f"驗證行情快照欄位 {column} 必須是正數")

    dates = normalized["date"]
    stock_count = int(normalized["stock_id"].nunique())
    date_count = int(dates.nunique())
    latest_date = dates.max()
    latest_stock_count = int(normalized.loc[dates == latest_date, "stock_id"].nunique())
    latest_coverage = latest_stock_count / stock_count if stock_count else 0.0
    markets = sorted(normalized["market"].dropna().unique().tolist())
    missing_markets = sorted(REQUIRED_MARKETS.difference(markets))
    if stock_count < MIN_STOCKS:
        raise ValidationSnapshotError(f"驗證行情快照股票覆蓋不足：{stock_count} < {MIN_STOCKS}")
    if date_count < MIN_TRADE_DATES:
        raise ValidationSnapshotError(f"驗證行情快照交易日覆蓋不足：{date_count} < {MIN_TRADE_DATES}")
    if latest_coverage < MIN_LATEST_COVERAGE:
        raise ValidationSnapshotError(
            f"驗證行情快照最新日股票覆蓋不足：{latest_coverage:.1%} < {MIN_LATEST_COVERAGE:.1%}"
        )
    if missing_markets:
        raise ValidationSnapshotError(f"驗證行情快照缺少市場覆蓋：{missing_markets}")

    return normalized, {
        "row_count": int(len(normalized)),
        "stock_count": stock_count,
        "trade_date_count": date_count,
        "start_date": dates.min().date().isoformat(),
        "end_date": latest_date.date().isoformat(),
        "latest_date": latest_date.date().isoformat(),
        "latest_stock_count": latest_stock_count,
        "latest_stock_coverage": latest_coverage,
        "markets": markets,
    }
