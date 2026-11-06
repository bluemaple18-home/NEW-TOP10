"""離線法人原始快照的內容雜湊與欄位契約。"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pandas as pd

INPUT_ENV = "TOP10_VALIDATION_INSTITUTIONAL_INPUT"
SHA_ENV = "TOP10_VALIDATION_INSTITUTIONAL_SHA256"
REQUIRED_ENV = "TOP10_REQUIRE_INSTITUTIONAL_SNAPSHOT"
COLUMNS = {"date", "stock_id", "name", "buy", "sell"}


class InstitutionalSnapshotError(ValueError):
    """法人來源不存在、不可信或內容不完整。"""


def load_institutional_snapshot_from_environment() -> tuple[pd.DataFrame, dict[str, object]]:
    """僅讀取 digest-pinned 實體檔，禁止以行情或衍生特徵代替法人原始值。"""
    location = os.environ.get(INPUT_ENV, "")
    expected = os.environ.get(SHA_ENV, "")
    if not location or not expected or len(expected) != 64:
        raise InstitutionalSnapshotError("離線法人快照路徑或 SHA-256 不完整")
    path = Path(location)
    if not path.is_file() or path.is_symlink() or path.suffix != ".parquet":
        raise InstitutionalSnapshotError("離線法人快照必須是存在的 parquet 一般檔案")
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    if sha != expected:
        raise InstitutionalSnapshotError("離線法人快照 SHA-256 不符")
    frame = pd.read_parquet(path)
    if frame.empty or set(frame.columns) != COLUMNS:
        raise InstitutionalSnapshotError("離線法人快照為空或欄位契約不符")
    frame = frame.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["stock_id"] = frame["stock_id"].astype(str).str.strip()
    frame["name"] = frame["name"].astype(str).str.strip()
    if frame["date"].isna().any() or frame["stock_id"].eq("").any() or frame["name"].eq("").any():
        raise InstitutionalSnapshotError("法人快照含空白或錯誤識別欄位")
    for column in ("buy", "sell"):
        numeric = pd.to_numeric(frame[column], errors="coerce")
        if numeric.isna().any() or (numeric < 0).any() or (numeric != numeric.astype("int64")).any():
            raise InstitutionalSnapshotError(f"法人快照 {column} 必須是非負整數股數")
        frame[column] = numeric.astype("int64")
    if frame[["date", "stock_id", "name"]].duplicated().any():
        raise InstitutionalSnapshotError("法人快照包含重複交易日／股票／法人類別")
    return frame, {"path": str(path), "sha256": sha, "rows": len(frame), "stocks": int(frame["stock_id"].nunique()), "start_date": frame["date"].min().date().isoformat(), "end_date": frame["date"].max().date().isoformat()}
