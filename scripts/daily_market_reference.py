"""Daily 上市櫃參考檔的共同准入計數。"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def _truthy_value(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    return None


def expected_market_counts(root: Path, required_markets: list[str]) -> dict[str, int]:
    path = root / "data" / "reference" / "tradable_universe.csv"
    if not path.is_file() or path.stat().st_size == 0:
        return {market: 0 for market in required_markets}
    universe = pd.read_csv(path, dtype={"stock_id": str})
    if universe.empty or not {"stock_id", "market_type"}.issubset(universe.columns):
        return {market: 0 for market in required_markets}
    if "is_active" in universe.columns:
        universe = universe[universe["is_active"].map(_truthy_value).fillna(True)]
    if "is_etf" in universe.columns:
        universe = universe[~universe["is_etf"].map(_truthy_value).fillna(False)]
    universe["stock_id"] = universe["stock_id"].fillna("").astype(str).str.strip()
    universe = universe[universe["stock_id"].str.fullmatch(r"\d{4}")]
    universe["market_type"] = universe["market_type"].astype(str).str.strip().str.lower()
    counts = universe.groupby("market_type")["stock_id"].nunique().to_dict()
    return {market: int(counts.get(market, 0)) for market in required_markets}
