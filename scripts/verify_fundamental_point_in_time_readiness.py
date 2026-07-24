#!/usr/bin/env python3
"""以獨立資料路徑重算 Fundamental point-in-time readiness。"""

from __future__ import annotations

from bisect import bisect_right
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_PATH = PROJECT_ROOT / "docs/evidence/RESEARCH-FUNDAMENTAL-READINESS-01/artifact.json"
FEATURES_PATH = PROJECT_ROOT / "data/clean/features.parquet"
CACHE_DIR = PROJECT_ROOT / "data/fundamentals"
REGIME_PATH = PROJECT_ROOT / "artifacts/model_experiments/market_regime_history_append_only_2026-07-22.json"
HOLDING_HORIZON = 10
RESEARCH_DAYS = 252
TOP_N = 200
RESEARCH_MIN_STOCKS = 30
RESEARCH_MIN_COVERAGE = 0.70
MODEL_MIN_COVERAGE = 0.80
METRIC_NAMES = (
    "roe",
    "gross_margin",
    "debt_ratio",
    "operating_margin",
    "net_margin",
    "current_ratio",
    "roa",
    "free_cash_flow",
    "eps",
)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cache_manifest(cache_dir: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    files = sorted(cache_dir.glob("*.json"))
    for path in files:
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return len(files), digest.hexdigest()


def normalize_stock_id(value: Any) -> str:
    text = str(value).strip()
    return text[:-2] if text.endswith(".0") else text


def available_from(row: dict[str, Any], payload: dict[str, Any]) -> pd.Timestamp | None:
    for key in ("available_from", "published_at", "as_of_date"):
        value = row.get(key) or payload.get(key)
        if value:
            parsed = pd.to_datetime(value, errors="coerce")
            if pd.notna(parsed):
                return pd.Timestamp(parsed).normalize()
    try:
        year = int(str(row["year"])[:4])
    except (KeyError, TypeError, ValueError):
        return None
    quarter = row.get("quarter") or row.get("fiscal_quarter")
    if quarter:
        try:
            quarter_number = int(str(quarter).lower().replace("q", ""))
        except ValueError:
            quarter_number = 0
        month = {1: 3, 2: 6, 3: 9, 4: 12}.get(quarter_number)
        if month:
            quarter_end = pd.Timestamp(year=year, month=month, day=1) + pd.offsets.MonthEnd(0)
            return pd.Timestamp(quarter_end + pd.Timedelta(days=45)).normalize()
    return pd.Timestamp(year=year + 1, month=4, day=1)


def raw_row_has_metric(row: dict[str, Any]) -> bool:
    if any(row.get(name) is not None for name in METRIC_NAMES):
        return True
    pairs = (
        ("gross_profit", "revenue"),
        ("operating_income", "revenue"),
        ("net_income", "revenue"),
        ("current_assets", "current_liabilities"),
        ("total_liabilities", "total_assets"),
        ("net_income", "equity"),
        ("net_income", "total_assets"),
    )
    if any(row.get(left) is not None and row.get(right) not in (None, 0) for left, right in pairs):
        return True
    return row.get("operating_cash_flow") is not None or row.get("eps") is not None


def availability_records(cache_dir: Path) -> dict[str, list[tuple[pd.Timestamp, bool]]]:
    records: dict[str, list[tuple[pd.Timestamp, bool]]] = {}
    for path in sorted(cache_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        stock_id = normalize_stock_id(payload.get("stock_id") or path.stem)
        source_rows: list[dict[str, Any]] = []
        if isinstance(payload.get("metrics"), list):
            source_rows = [dict(row) for row in payload["metrics"] if isinstance(row, dict)]
        elif isinstance(payload.get("financials_by_year"), dict):
            source_rows = [
                {"year": str(year), **dict(row)}
                for year, row in payload["financials_by_year"].items()
                if isinstance(row, dict)
            ]
        stock_records = [
            (date_value, raw_row_has_metric(row))
            for row in source_rows
            if (date_value := available_from(row, payload)) is not None
        ]
        if stock_records:
            records[stock_id] = sorted(stock_records)
    return records


def point_in_time_available(
    stock_id: str,
    trade_date: pd.Timestamp,
    records: dict[str, list[tuple[pd.Timestamp, bool]]],
) -> bool:
    stock_records = records.get(stock_id, [])
    dates = [item[0] for item in stock_records]
    index = bisect_right(dates, trade_date) - 1
    return index >= 0 and stock_records[index][1]


def distribution(series: pd.Series) -> dict[str, float]:
    return {
        "min": round(float(series.min()), 6),
        "median": round(float(series.median()), 6),
        "max": round(float(series.max()), 6),
    }


def recompute_readiness(features_path: Path, cache_dir: Path) -> dict[str, Any]:
    frame = pd.read_parquet(features_path, columns=["date", "stock_id", "avg_value_20d"])
    frame["trade_date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["stock_id"] = frame["stock_id"].map(normalize_stock_id)
    if frame[["trade_date", "stock_id"]].isna().any().any():
        raise ValueError("features 含不可解析 point-in-time key")
    if frame.duplicated(["trade_date", "stock_id"]).any():
        raise ValueError("features point-in-time key 不唯一")
    frame["avg_value_20d"] = pd.to_numeric(frame["avg_value_20d"], errors="coerce")
    records = availability_records(cache_dir)
    frame["fundamental_available"] = [
        point_in_time_available(stock_id, trade_date, records)
        for stock_id, trade_date in frame[["stock_id", "trade_date"]].itertuples(index=False)
    ]

    feature_stocks = int(frame["stock_id"].nunique())
    usable_stocks = int(frame.loc[frame["fundamental_available"], "stock_id"].nunique())
    ranked = frame.dropna(subset=["avg_value_20d"]).sort_values(
        ["trade_date", "avg_value_20d", "stock_id"],
        ascending=[True, False, True],
    )
    ranked["_liquidity_rank"] = ranked.groupby("trade_date", sort=False).cumcount() + 1
    universe = ranked.loc[ranked["_liquidity_rank"] <= TOP_N]
    daily = (
        universe.groupby("trade_date", sort=True)
        .agg(
            selected_stocks=("stock_id", "nunique"),
            available_stocks=("fundamental_available", "sum"),
        )
        .reset_index()
    )
    if daily.empty:
        raise ValueError("沒有可重算的 point-in-time liquidity universe")
    daily["coverage"] = daily["available_stocks"] / daily["selected_stocks"]
    mature = daily.iloc[:-HOLDING_HORIZON]
    recent = mature.tail(RESEARCH_DAYS)
    latest = daily.iloc[-1]
    days_meeting = int(
        ((recent["available_stocks"] >= RESEARCH_MIN_STOCKS) & (recent["coverage"] >= RESEARCH_MIN_COVERAGE)).sum()
    )
    model_coverage = usable_stocks / feature_stocks if feature_stocks else 0.0
    research_ready = len(recent) == RESEARCH_DAYS and days_meeting == RESEARCH_DAYS
    model_ready = model_coverage >= MODEL_MIN_COVERAGE
    return {
        "decision": (
            "READY_FOR_POINT_IN_TIME_RESEARCH"
            if research_ready and model_ready
            else "BLOCKED_DATA_COVERAGE"
        ),
        "coverage": {
            "feature_stocks": feature_stocks,
            "usable_fundamental_stocks": usable_stocks,
            "usable_stock_coverage": round(model_coverage, 6),
            "latest_point_in_time_top200": {
                "selected_stocks": int(latest["selected_stocks"]),
                "available_stocks": int(latest["available_stocks"]),
                "coverage": round(float(latest["coverage"]), 6),
            },
            "recent_252_trade_days": {
                "days": int(len(recent)),
                "start_date": str(pd.Timestamp(recent["trade_date"].min()).date()),
                "end_date": str(pd.Timestamp(recent["trade_date"].max()).date()),
                "available_stock_count": distribution(recent["available_stocks"]),
                "coverage": distribution(recent["coverage"]),
                "days_meeting_research_gate": days_meeting,
            },
        },
    }


def assert_matches_oracle(artifact: dict[str, Any], oracle: dict[str, Any]) -> None:
    assert artifact["decision"] == oracle["decision"]
    assert artifact["coverage"] == oracle["coverage"]


def verify_mutation_fixture() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        cache_dir = root / "fundamentals"
        cache_dir.mkdir()
        dates = pd.bdate_range("2025-01-01", periods=263)
        features = pd.DataFrame(
            [
                {"date": trade_date, "stock_id": stock_id, "avg_value_20d": liquidity}
                for trade_date in dates
                for stock_id, liquidity in (("1101", 2.0), ("1102", 1.0))
            ]
        )
        features_path = root / "features.parquet"
        features.to_parquet(features_path, index=False)
        cache_path = cache_dir / "1101.json"
        payload = {
            "stock_id": "1101",
            "metrics": [{"year": "2024", "available_from": "2025-01-01", "gross_margin": 20.0}],
        }
        cache_path.write_text(json.dumps(payload), encoding="utf-8")
        expected = recompute_readiness(features_path, cache_dir)
        synthetic_artifact = {"decision": expected["decision"], "coverage": deepcopy(expected["coverage"])}

        payload["metrics"][0]["available_from"] = "2030-01-01"
        cache_path.write_text(json.dumps(payload), encoding="utf-8")
        mutated = recompute_readiness(features_path, cache_dir)
        try:
            assert_matches_oracle(synthetic_artifact, mutated)
        except AssertionError:
            pass
        else:
            raise AssertionError("point-in-time available_from mutation 未被獨立 oracle 捕捉")


def main() -> int:
    artifact = json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))
    oracle = recompute_readiness(FEATURES_PATH, CACHE_DIR)
    assert_matches_oracle(artifact, oracle)
    assert artifact["schema_version"] == "fundamental-point-in-time-readiness.v1"
    assert artifact["status"] == "OK"
    assert artifact["promotion_allowed"] is False
    assert artifact["gates"] == {
        "research_min_daily_stocks": RESEARCH_MIN_STOCKS,
        "research_min_daily_coverage": RESEARCH_MIN_COVERAGE,
        "research_required_trade_days": RESEARCH_DAYS,
        "holding_horizon_trade_days": HOLDING_HORIZON,
        "model_min_stock_coverage": MODEL_MIN_COVERAGE,
    }
    cache_files, cache_sha = cache_manifest(CACHE_DIR)
    assert artifact["inputs"]["features_sha256"] == file_sha256(FEATURES_PATH)
    assert artifact["inputs"]["regime_history_sha256"] == file_sha256(REGIME_PATH)
    assert artifact["inputs"]["fundamental_cache_files"] == cache_files
    assert artifact["inputs"]["fundamental_cache_manifest_sha256"] == cache_sha
    reason_codes = {row["reason_code"] for row in artifact["warnings_and_exclusions"]}
    if oracle["coverage"]["usable_stock_coverage"] < MODEL_MIN_COVERAGE:
        assert "FUNDAMENTAL_CACHE_COVERAGE_BELOW_MODEL_GATE" in reason_codes
    if oracle["coverage"]["recent_252_trade_days"]["days_meeting_research_gate"] < RESEARCH_DAYS:
        assert "POINT_IN_TIME_DAILY_COVERAGE_BELOW_RESEARCH_GATE" in reason_codes
    verify_mutation_fixture()
    print("FUNDAMENTAL_POINT_IN_TIME_READINESS_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
