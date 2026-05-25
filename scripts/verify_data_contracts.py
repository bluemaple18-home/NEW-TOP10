"""驗證資料契約檢查器本身。

使用 repo 內既有 `data/test/*_test.parquet`，不依賴外部 API、不觸發 ETL。
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.api.main import app, market_service, stock_detail_service
from app.data.market_repository import MarketRepository
from app.data.reference_repository import MARKET_TYPES, ReferenceRepository, STOCK_ID_PATTERN, TRADABLE_STOCK_ID_PATTERN
from app.pipeline.validation import PipelineDataValidator


def main() -> int:
    project_root = PROJECT_ROOT
    validator = PipelineDataValidator(data_dir=project_root / "data")
    test_dir = project_root / "data" / "test"

    contracts = [
        replace(validator.features_contract(), path=test_dir / "features_test.parquet"),
        replace(validator.events_contract(), path=test_dir / "events_test.parquet"),
        replace(validator.universe_contract(), path=test_dir / "universe_test.parquet"),
    ]

    failed = False
    for contract in contracts:
        summary = validator.validate_contract(contract)
        errors = [issue for issue in summary.issues if issue.severity == "ERROR"]
        warnings = [issue for issue in summary.issues if issue.severity == "WARN"]
        print(
            f"{summary.dataset}: rows={summary.rows}, cols={summary.columns}, "
            f"stocks={summary.stocks}, errors={len(errors)}, warnings={len(warnings)}"
        )
        for issue in summary.issues:
            column = f" [{issue.column}]" if issue.column else ""
            print(f"  {issue.severity}{column} {issue.message}")
        failed = failed or bool(errors)

    failed = verify_reference_files(project_root) or failed
    failed = verify_stock_detail_api_smoke() or failed
    failed = verify_stock_detail_signal_dedup() or failed
    return 1 if failed else 0


def verify_reference_files(project_root: Path) -> bool:
    failed = False
    repository = ReferenceRepository(project_root)
    industry_required = {
        "stock_id",
        "industry_code",
        "industry_name",
        "sector_name",
        "market_type",
        "theme_tags",
        "source",
        "updated_at",
    }
    etf_required = {
        "stock_id",
        "etf_id",
        "etf_name",
        "weight",
        "is_major_holding",
        "source",
        "updated_at",
    }
    concept_required = {
        "stock_id",
        "canonical_concept_id",
        "canonical_name",
        "raw_concept_name",
        "concept_type",
        "source",
        "source_url",
        "observed_at",
        "confidence",
        "match_method",
    }
    tradable_required = {
        "stock_id",
        "stock_name",
        "market_type",
        "is_etf",
        "is_active",
        "source",
        "updated_at",
    }

    industry = repository.load_industry_map()
    etfs = repository.load_etf_exposure()
    concepts = repository.load_concept_membership()
    tradable = repository.load_tradable_universe()
    print(f"reference_industry: rows={len(industry)}, path={repository.industry_path.exists()}")
    print(f"reference_etfs: rows={len(etfs)}, path={repository.etf_path.exists()}")
    print(f"reference_concepts: rows={len(concepts)}, path={repository.concept_path.exists()}")
    print(f"tradable_universe: rows={len(tradable)}, path={repository.tradable_universe_path.exists()}")

    if repository.tradable_universe_path.exists():
        missing = tradable_required - set(tradable.columns)
        if missing:
            print(f"  ERROR tradable_universe missing columns={sorted(missing)}")
            failed = True
        if not tradable.empty:
            invalid_ids = ~tradable["stock_id"].astype(str).map(lambda value: bool(TRADABLE_STOCK_ID_PATTERN.fullmatch(value)))
            duplicated = tradable["stock_id"].duplicated()
            blank_names = tradable["stock_name"].isna() | (tradable["stock_name"].astype(str).str.strip() == "")
            invalid_market = ~tradable["market_type"].astype(str).str.strip().isin(MARKET_TYPES)
            failed = failed or bool(invalid_ids.any() or duplicated.any() or blank_names.any() or invalid_market.any())
            print(
                "  tradable_valid="
                f"{not invalid_ids.any()} unique={not duplicated.any()} "
                f"nonblank={not blank_names.any()} market_type={not invalid_market.any()}"
            )
            item = repository.tradable_universe_item(str(tradable["stock_id"].iloc[0]))
            failed = failed or item is None

    if repository.industry_path.exists():
        missing = industry_required - set(industry.columns)
        if missing:
            print(f"  ERROR industry missing columns={sorted(missing)}")
            failed = True
        if not industry.empty:
            invalid_ids = ~industry["stock_id"].astype(str).map(lambda value: bool(STOCK_ID_PATTERN.fullmatch(value)))
            duplicated = industry["stock_id"].duplicated()
            blank_industry = industry["industry_name"].isna() | (industry["industry_name"].astype(str).str.strip() == "")
            failed = failed or bool(invalid_ids.any() or duplicated.any() or blank_industry.any())
            print(
                "  industry_valid="
                f"{not invalid_ids.any()} unique={not duplicated.any()} nonblank={not blank_industry.any()}"
            )

    if repository.etf_path.exists():
        missing = etf_required - set(etfs.columns)
        if missing:
            print(f"  ERROR etf missing columns={sorted(missing)}")
            failed = True
        if not etfs.empty:
            invalid_stock_ids = ~etfs["stock_id"].astype(str).map(lambda value: bool(STOCK_ID_PATTERN.fullmatch(value)))
            invalid_etf_ids = ~etfs["etf_id"].astype(str).map(lambda value: bool(STOCK_ID_PATTERN.fullmatch(value)))
            duplicated = etfs[["stock_id", "etf_id"]].duplicated()
            weights = pd.to_numeric(etfs["weight"], errors="coerce")
            invalid_weights = weights.notna() & ~weights.between(0, 1)
            failed = failed or bool(invalid_stock_ids.any() or invalid_etf_ids.any() or duplicated.any() or invalid_weights.any())
            print(
                "  etf_valid="
                f"{not invalid_stock_ids.any() and not invalid_etf_ids.any()} "
                f"unique={not duplicated.any()} weight_range={not invalid_weights.any()}"
            )
    if repository.concept_path.exists():
        missing = concept_required - set(concepts.columns)
        if missing:
            print(f"  ERROR concept missing columns={sorted(missing)}")
            failed = True
        if not concepts.empty:
            invalid_stock_ids = ~concepts["stock_id"].astype(str).map(lambda value: bool(STOCK_ID_PATTERN.fullmatch(value)))
            blank_concepts = concepts["canonical_concept_id"].isna() | (
                concepts["canonical_concept_id"].astype(str).str.strip() == ""
            )
            confidence = pd.to_numeric(concepts["confidence"], errors="coerce")
            invalid_confidence = confidence.notna() & ~confidence.between(0, 1)
            failed = failed or bool(invalid_stock_ids.any() or blank_concepts.any() or invalid_confidence.any())
            print(
                "  concept_valid="
                f"{not invalid_stock_ids.any()} nonblank={not blank_concepts.any()} "
                f"confidence_range={not invalid_confidence.any()}"
            )
    return failed


def verify_stock_detail_api_smoke() -> bool:
    try:
        from fastapi.testclient import TestClient
    except (ImportError, RuntimeError) as exc:
        print(f"stock_detail_api: skipped TestClient ({exc}); running direct service smoke")
        return verify_stock_detail_service_smoke()

    client = TestClient(app)
    stock_id = str(MarketRepository(PROJECT_ROOT).load_features()["stock_id"].iloc[0])

    detail = client.get(f"/api/stocks/{stock_id}/detail?limit=30")
    print(f"stock_detail: status={detail.status_code}, stock_id={stock_id}")
    if detail.status_code != 200:
        return True
    payload = detail.json()
    failed = False
    for section in ("price", "reference", "fundamentals", "trade_plan", "backtest"):
        section_payload = payload.get(section, {})
        has_available = "available" in section_payload
        print(f"  {section}: available={section_payload.get('available')}, contract={has_available}")
        failed = failed or not has_available

    ohlcv = client.get(f"/api/stocks/{stock_id}/ohlcv?limit=30")
    fundamentals = client.get(f"/api/stocks/{stock_id}/fundamentals")
    missing_detail = client.get("/api/stocks/NO_SUCH/detail?limit=30")
    invalid_detail = client.get("/api/stocks/%25%25/detail?limit=30")
    reference = client.get(f"/api/stocks/{stock_id}/reference")
    ranking = client.get("/api/rankings/latest?limit=10")
    weekly = client.get("/api/weekly-candidates?risk_style=balanced&target_type=stocks&holding_period=swing&entry_preference=mixed&risk_limit=excludeThemes&limit=10")
    print(f"ohlcv: status={ohlcv.status_code}")
    print(f"fundamentals: status={fundamentals.status_code}")
    print(f"missing_detail: status={missing_detail.status_code}")
    print(f"invalid_detail: status={invalid_detail.status_code}")
    print(f"reference: status={reference.status_code}")
    print(f"ranking: status={ranking.status_code}")
    print(f"weekly_candidates: status={weekly.status_code}")
    failed = failed or ohlcv.status_code != 200
    failed = failed or fundamentals.status_code != 200
    failed = failed or missing_detail.status_code != 200
    failed = failed or invalid_detail.status_code != 422
    failed = failed or reference.status_code != 200
    failed = failed or ranking.status_code != 200
    failed = failed or weekly.status_code != 200
    if reference.status_code == 200:
        reference_payload = reference.json()
        failed = failed or "industry" not in reference_payload
        failed = failed or "etfs" not in reference_payload
        failed = failed or "concepts" not in reference_payload
    if ranking.status_code == 200:
        ranking_payload = ranking.json()
        failed = failed or "reference_summary" not in ranking_payload
        first_item = (ranking_payload.get("items") or [{}])[0]
        failed = failed or "industry_name" not in first_item
        failed = failed or "major_etfs" not in first_item
        failed = failed or "concept_tags" not in first_item
    if weekly.status_code == 200:
        weekly_payload = weekly.json()
        failed = failed or "market_summary" not in weekly_payload
        failed = failed or "status_order" not in weekly_payload
        first_candidate = (weekly_payload.get("stock_candidates") or [{}])[0]
        failed = failed or "status" not in first_candidate
        failed = failed or "ranking" not in first_candidate
        primary_reasons = [
            reason
            for candidate in weekly_payload.get("stock_candidates", [])
            for reason in candidate.get("primary_reasons", [])
        ]
        has_unverified_industry_signal = any("共振" in str(reason) for reason in primary_reasons)
        failed = failed or has_unverified_industry_signal
        print(f"weekly_primary_reasons_no_industry_signal={not has_unverified_industry_signal}")
    if missing_detail.status_code == 200:
        missing_payload = missing_detail.json()
        failed = failed or missing_payload.get("price", {}).get("available") is not False
        failed = failed or "reference" not in missing_payload
        failed = failed or missing_payload.get("backtest", {}).get("available") is not False
        failed = failed or missing_payload.get("backtest", {}).get("scope") != "system"
        failed = failed or "系統層回測" not in str(missing_payload.get("backtest", {}).get("notes"))
    if detail.status_code == 200:
        backtest = payload.get("backtest", {})
        failed = failed or backtest.get("scope") != "system"
        if backtest.get("available"):
            failed = failed or "非個股專屬" not in str(backtest.get("notes"))
    return failed


def verify_stock_detail_service_smoke() -> bool:
    stock_id = str(MarketRepository(PROJECT_ROOT).load_features()["stock_id"].iloc[0])
    failed = False
    detail = stock_detail_service.stock_detail(stock_id, limit=30)
    ranking = market_service.latest_ranking(limit=10)
    reference = market_service.reference_repository.stock_reference(stock_id)
    print(f"stock_detail_service: stock_id={stock_id}, reference={detail.reference.available}")
    failed = failed or not detail.price.available
    failed = failed or not hasattr(detail, "reference")
    failed = failed or not hasattr(reference, "industry")
    failed = failed or ranking.reference_summary is None
    first_item = ranking.items[0].model_dump() if ranking.items else {}
    failed = failed or "industry_name" not in first_item
    failed = failed or "major_etfs" not in first_item
    failed = failed or "concept_tags" not in first_item
    try:
        stock_detail_service.stock_detail("%%", limit=30)
        failed = True
    except ValueError:
        pass
    missing = stock_detail_service.stock_detail("NO_SUCH", limit=30)
    failed = failed or missing.price.available is not False
    failed = failed or missing.backtest.available is not False
    return failed


def verify_stock_detail_signal_dedup() -> bool:
    bars = [
        {
            "time": "2026-01-20",
            "open": 86.0,
            "high": 86.1,
            "low": 82.0,
            "close": 86.0,
            "candle_doji": 1,
            "candle_dragonfly_doji": 1,
            "candle_tombstone_doji": 0,
            "candle_hammer": 1,
        },
        {
            "time": "2026-01-21",
            "open": 86.0,
            "high": 90.0,
            "low": 85.9,
            "close": 86.0,
            "candle_doji": 1,
            "candle_dragonfly_doji": 0,
            "candle_tombstone_doji": 1,
        },
        {
            "time": "2026-01-22",
            "open": 86.0,
            "high": 90.0,
            "low": 85.0,
            "close": 89.5,
            "candle_doji": 1,
            "candle_bull_engulfing": 1,
        },
    ]
    signals = stock_detail_service._pattern_signals(bars)
    by_date = {
        date: {signal.signal_id for signal in signals if signal.date == date}
        for date in ("2026-01-20", "2026-01-21", "2026-01-22")
    }
    dragonfly_clean = by_date["2026-01-20"] == {"candle_dragonfly_doji"}
    tombstone_clean = by_date["2026-01-21"] == {"candle_tombstone_doji"}
    engulfing_clean = by_date["2026-01-22"] == {"candle_bull_engulfing"}
    print(
        "stock_detail_pattern_signal_priority="
        f"{dragonfly_clean and tombstone_clean and engulfing_clean} "
        f"dragonfly={sorted(by_date['2026-01-20'])} "
        f"tombstone={sorted(by_date['2026-01-21'])} "
        f"engulfing={sorted(by_date['2026-01-22'])}"
    )
    return not (dragonfly_clean and tombstone_clean and engulfing_clean)


if __name__ == "__main__":
    raise SystemExit(main())
