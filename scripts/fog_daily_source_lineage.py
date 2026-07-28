#!/usr/bin/env python3
"""Fog daily artifact 的 canonical features source lineage。"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pandas as pd


SCHEMA_VERSION = "fog-daily-source-lineage.v1"
EXACT_KEYS = {
    "schema_version",
    "features_path",
    "features_sha256",
    "daily_source_date",
}


class DailySourceLineageError(RuntimeError):
    """Daily source lineage 無法由 canonical features重算。"""

    def __init__(self, reason_code: str, detail: str = "") -> None:
        super().__init__(f"{reason_code}: {detail}" if detail else reason_code)
        self.reason_code = reason_code


def _resolve_features(root: str | Path, relative_path: object) -> tuple[Path, str]:
    root_path = Path(root).resolve()
    if not isinstance(relative_path, str) or not relative_path:
        raise DailySourceLineageError("DAILY_SOURCE_PATH_REJECT", "features_path 非字串")
    candidate = Path(relative_path)
    if candidate.is_absolute():
        raise DailySourceLineageError("DAILY_SOURCE_PATH_REJECT", "只接受 repo-relative path")
    resolved = (root_path / candidate).resolve()
    try:
        canonical_relative = resolved.relative_to(root_path).as_posix()
    except ValueError as error:
        raise DailySourceLineageError("DAILY_SOURCE_PATH_REJECT", relative_path) from error
    if not resolved.is_file():
        raise DailySourceLineageError("DAILY_SOURCE_LOAD_FAILED", canonical_relative)
    return resolved, canonical_relative


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _latest_source_date(path: Path, market_run_date: str) -> str:
    try:
        market_date = pd.Timestamp(market_run_date).normalize()
    except (TypeError, ValueError) as error:
        raise DailySourceLineageError(
            "DAILY_SOURCE_MARKET_DATE_REJECT",
            str(market_run_date),
        ) from error
    series = None
    for column in ("date", "trade_date"):
        try:
            series = pd.read_parquet(path, columns=[column])[column]
            break
        except Exception:
            continue
    if series is None:
        raise DailySourceLineageError(
            "DAILY_SOURCE_DATE_COLUMN_REJECT",
            path.name,
        )
    dates = pd.to_datetime(series, errors="coerce").dropna().dt.normalize()
    eligible = dates[dates <= market_date]
    if eligible.empty:
        raise DailySourceLineageError(
            "DAILY_SOURCE_DATE_UNAVAILABLE",
            market_run_date,
        )
    return eligible.max().date().isoformat()


def build_daily_source_lineage(
    *,
    root: str | Path,
    features_path: object,
    market_run_date: str,
) -> dict[str, str]:
    features, canonical_relative = _resolve_features(root, features_path)
    return {
        "schema_version": SCHEMA_VERSION,
        "features_path": canonical_relative,
        "features_sha256": _sha256(features),
        "daily_source_date": _latest_source_date(features, market_run_date),
    }


def verify_daily_source_lineage(
    *,
    root: str | Path,
    lineage: object,
    market_run_date: str,
) -> dict[str, Any]:
    if not isinstance(lineage, dict) or set(lineage) != EXACT_KEYS:
        return {
            "ok": False,
            "reason_codes": ["DAILY_SOURCE_LINEAGE_SCHEMA_REJECT"],
            "daily_source_date": None,
        }
    if lineage.get("schema_version") != SCHEMA_VERSION:
        return {
            "ok": False,
            "reason_codes": ["DAILY_SOURCE_LINEAGE_SCHEMA_REJECT"],
            "daily_source_date": None,
        }
    try:
        canonical = build_daily_source_lineage(
            root=root,
            features_path=lineage.get("features_path"),
            market_run_date=market_run_date,
        )
    except DailySourceLineageError as error:
        return {
            "ok": False,
            "reason_codes": [error.reason_code],
            "daily_source_date": None,
        }
    reason_codes: list[str] = []
    if lineage.get("features_sha256") != canonical["features_sha256"]:
        reason_codes.append("DAILY_SOURCE_HASH_MISMATCH")
    if lineage.get("daily_source_date") != canonical["daily_source_date"]:
        reason_codes.append("DAILY_SOURCE_DATE_MISMATCH")
    return {
        "ok": not reason_codes,
        "reason_codes": reason_codes,
        "daily_source_date": canonical["daily_source_date"],
    }
