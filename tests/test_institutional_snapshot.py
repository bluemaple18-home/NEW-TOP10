"""法人來源快照、缺口處理及離線 ETL 真實欄位驗證。"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
import pytest

from app.finmind_integrator import FinMindIntegrator, InstitutionalDataError
from app.pipeline.institutional_snapshot import InstitutionalSnapshotError, load_institutional_snapshot_from_environment


def _quotes() -> pd.DataFrame:
    dates = pd.bdate_range("2026-01-02", periods=80)
    return pd.DataFrame([
        {"date": day, "stock_id": sid, "stock_name": f"股票{sid}", "market": "TWSE" if index < 3 else "TPEX", "open": 50 + index, "high": 51 + index, "low": 49 + index, "close": 50 + index + offset / 100, "volume": 100000 + offset, "value": (50 + index + offset / 100) * (100000 + offset)}
        for index, sid in enumerate(("1101", "1216", "1301", "2330", "3008", "6488"))
        for offset, day in enumerate(dates)
    ])


def _source(quotes: pd.DataFrame) -> pd.DataFrame:
    names = ("Foreign_Investor", "Investment_Trust", "Dealer_self", "Dealer_Hedging")
    return pd.DataFrame([
        {"date": row.date, "stock_id": row.stock_id, "name": name, "buy": 100 + i, "sell": 10 + i}
        for row in quotes[["date", "stock_id"]].itertuples(index=False)
        for i, name in enumerate(names)
    ])


def _pin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, frame: pd.DataFrame) -> Path:
    path = tmp_path / "institutional.parquet"
    frame.to_parquet(path, index=False)
    monkeypatch.setenv("TOP10_VALIDATION_INSTITUTIONAL_INPUT", str(path))
    monkeypatch.setenv("TOP10_VALIDATION_INSTITUTIONAL_SHA256", hashlib.sha256(path.read_bytes()).hexdigest())
    monkeypatch.setenv("TOP10_REQUIRE_INSTITUTIONAL_SNAPSHOT", "1")
    return path


def test_snapshot_rejects_missing_tampered_and_zero_filled_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    quotes = _quotes().head(2)
    source = _source(quotes)
    monkeypatch.setenv("TOP10_REQUIRE_INSTITUTIONAL_SNAPSHOT", "1")
    with pytest.raises(InstitutionalSnapshotError, match="路徑或 SHA"):
        load_institutional_snapshot_from_environment()
    path = _pin(tmp_path, monkeypatch, source)
    loaded, metadata = load_institutional_snapshot_from_environment()
    assert len(loaded) == 8 and metadata["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    with path.open("ab") as handle:
        handle.write(b"changed")
    with pytest.raises(InstitutionalSnapshotError, match="SHA-256"):
        load_institutional_snapshot_from_environment()
    bad = source.copy()
    bad.loc[0, "buy"] = pd.NA
    _pin(tmp_path, monkeypatch, bad)
    with pytest.raises(InstitutionalSnapshotError, match="非負整數"):
        load_institutional_snapshot_from_environment()


def test_institutional_merge_rejects_missing_pair_and_category() -> None:
    quotes = _quotes().head(2)
    source = _source(quotes)
    integrator = FinMindIntegrator(offline=True)
    enriched = integrator.integrate_chip_data(quotes, top_n=2, include_margin=False, institutional_source=source)
    assert enriched["institutional_available"].all()
    assert enriched["foreign_buy"].tolist() == [90, 90]
    assert enriched["dealer_buy"].tolist() == [180, 180]
    absent = source[source["date"] != quotes.iloc[1]["date"]]
    with pytest.raises(InstitutionalDataError, match="必要行情鍵"):
        integrator.integrate_chip_data(quotes, top_n=2, include_margin=False, institutional_source=absent)
    partial = source[~((source["date"] == quotes.iloc[0]["date"]) & source["name"].eq("Investment_Trust"))]
    with pytest.raises(InstitutionalDataError, match="必要行情鍵"):
        integrator.integrate_chip_data(quotes, top_n=2, include_margin=False, institutional_source=partial)


def test_official_fallback_uses_actual_net_fields_and_rejects_unresolved(monkeypatch: pytest.MonkeyPatch) -> None:
    quotes = _quotes().iloc[:2].copy()
    quotes["date"] = pd.to_datetime(["2026-10-21", "2026-10-22"])
    raw = _source(quotes.iloc[:1])

    class Fetcher:
        def get_institutional_investors(self, *_args: object) -> pd.DataFrame:
            return raw

    integrator = FinMindIntegrator(offline=True)
    integrator.fetcher = Fetcher()
    from app.tskg import twse_t86
    monkeypatch.setattr(twse_t86, "fetch_t86_snapshot", lambda day: {"source_id": "twse-t86", "integrity": {"canonical_sha256": "abc"}, "records": [{"stock_id": "1101", "foreign_ex_dealer_net_shares": -30, "investment_trust_net_shares": 20, "dealer_total_net_shares": -10}]})
    enriched = integrator.integrate_chip_data(quotes, top_n=1, include_margin=False)
    assert enriched["foreign_buy"].tolist() == [90, -30]
    assert enriched["trust_buy"].tolist() == [90, 20]
    assert len(integrator.official_fallbacks) == 1
    monkeypatch.setattr(twse_t86, "fetch_t86_snapshot", lambda day: {"source_id": "twse-t86", "integrity": {"canonical_sha256": "abc"}, "records": []})
    with pytest.raises(InstitutionalDataError, match="官方 T86 也缺"):
        FinMindIntegrator._official_twse_fallback(integrator, pd.DataFrame({"date": [pd.Timestamp("2026-10-22")], "stock_id": ["1101"], "market": ["TWSE"]}))


def test_offline_etl_wires_real_raw_shares_into_derived_features(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.pipeline import ETLPipeline, EventStage, FetchStage, FilterStage, FundamentalStage, IndicatorStage
    from app.pipeline import fetch_stage

    quotes = _quotes()
    price = tmp_path / "quotes.parquet"
    quotes.to_parquet(price, index=False)
    _pin(tmp_path, monkeypatch, _source(quotes))
    monkeypatch.setenv("TOP10_STORAGE_VALIDATION_MODE", "1")
    monkeypatch.setenv("TOP10_VALIDATION_SNAPSHOT_INPUT", str(price))

    class NoNetwork:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            raise AssertionError("離線驗收不可建構即時資料 provider")

    monkeypatch.setattr(fetch_stage, "DataFetcherOrchestrator", NoNetwork)
    pipeline = (ETLPipeline(data_dir=str(tmp_path / "out/data"), artifacts_dir=str(tmp_path / "out/artifacts"))
                .add_stage(FetchStage()).add_stage(IndicatorStage()).add_stage(FundamentalStage()).add_stage(EventStage()).add_stage(FilterStage()))
    pipeline.run(start_date="2026-01-02", end_date=quotes["date"].max().strftime("%Y-%m-%d"))
    features = pd.read_parquet(tmp_path / "out/data/clean/features.parquet")
    assert pipeline.context["stats"]["finmind"]["status"] == "ok"
    assert features["institutional_available"].all()
    assert {"inst_buy_ratio_3d", "inst_buy_ratio_5d", "inst_buy_ratio_10d", "trust_buy_days_5d"}.issubset(features.columns)
    assert features["inst_buy_ratio_5d"].notna().sum() > 0
