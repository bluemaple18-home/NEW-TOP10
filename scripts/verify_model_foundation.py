"""模型底座 smoke test。"""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile

from bs4 import BeautifulSoup
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.fundamentals import compute_financial_metrics, normalize_goodinfo_statements, sanity_check, score_fundamentals
from app.fundamentals.goodinfo_client import parse_financial_table, parse_number
from app.modeling import (
    FUNDAMENTAL_FEATURE_COLUMNS,
    build_factor_run_manifest,
    build_m4_feature_frame,
    candidate_feature_columns,
    validate_factor_registry,
)
from app.modeling import MODEL_SPECS, validate_model_registry
from app.pipeline.fundamental_stage import FundamentalStage
from app.services.fundamental_service import FundamentalService
from app.data.fundamental_repository import FundamentalRepository


def main() -> int:
    issues = validate_model_registry()
    for issue in issues:
        print(f"{issue.severity} {issue.model_id}: {issue.message}")

    sample = {
        "2024": {
            "revenue": 1000,
            "gross_profit": 420,
            "operating_income": 180,
            "net_income": 120,
            "current_assets": 600,
            "current_liabilities": 300,
            "total_liabilities": 700,
            "total_assets": 1500,
            "equity": 800,
            "operating_cash_flow": 160,
            "capex": -60,
            "eps": 4.2,
        }
    }
    metrics = compute_financial_metrics(sample)
    normalized = normalize_goodinfo_statements(
        income_statement={
            "營業收入合計": {"2024": 1000},
            "營業毛利（毛損）": {"2024": 420},
            "營業利益（損失）": {"2024": 180},
            "稅後淨利": {"2024": 120},
            "每股稅後盈餘(元)": {"2024": 4.2},
        },
        balance_sheet={
            "流動資產合計": {"2024": 600},
            "流動負債合計": {"2024": 300},
            "負債總額": {"2024": 700},
            "資產總額": {"2024": 1500},
            "股東權益總額": {"2024": 800},
        },
        cash_flow={
            "營業活動之淨現金流入（出）": {"2024": 160},
            "固定資產（增加）減少": {"2024": -60},
        },
        years=["2024"],
    )
    normalized_metrics = compute_financial_metrics(normalized)
    assert len(MODEL_SPECS) == 11
    assert not any(issue.severity == "ERROR" for issue in issues)
    assert metrics[0].gross_margin == 42.0
    assert metrics[0].free_cash_flow == 100.0
    assert normalized_metrics[0].roe == 15.0
    assert sanity_check(normalized_metrics) == []
    score = score_fundamentals("1101", normalized_metrics)
    assert score.fundamental_quality_score is not None
    assert 0 <= score.fundamental_quality_score <= 1
    assert score.profitability_score is not None
    assert parse_number("(1,234)") == -1234.0
    assert parse_number("--") is None
    verify_goodinfo_parser_skips_quote_tables()
    verify_fundamental_stage_does_not_create_dummy_data()
    service = FundamentalService(FundamentalRepository(PROJECT_ROOT))
    missing = service.stock_fundamentals("FAKE")
    assert missing.available is False
    cached = service.stock_fundamentals("2330")
    if cached.available:
        assert cached.source_links is not None
        assert cached.source_links.income_statement
        assert cached.source_links.mops
        assert cached.years_covered
        assert {dimension.id for dimension in cached.dimensions} == {"operations", "profitability", "financial_health"}
        assert any(item.key == "roe" for dimension in cached.dimensions for item in dimension.items)
    verify_m4_feature_contract()
    print(f"MODEL_FOUNDATION_OK specs={len(MODEL_SPECS)}")
    return 0


def verify_goodinfo_parser_skips_quote_tables() -> None:
    soup = BeautifulSoup(
        """
        <html><body>
          <table>
            <tr><th>成交價</th><th>2265</th><th>2270</th><th>2310</th></tr>
            <tr><td>買進</td><td>2260</td><td>2255</td><td>2250</td></tr>
          </table>
          <table>
            <tr><th>項目</th><th>2024</th><th>百分比</th><th>2023</th><th>百分比</th></tr>
            <tr><td>營業收入合計</td><td>1000</td><td>100</td><td>900</td><td>100</td></tr>
            <tr><td>營業毛利（毛損）</td><td>420</td><td>42</td><td>360</td><td>40</td></tr>
          </table>
        </body></html>
        """,
        "html.parser",
    )
    table, years = parse_financial_table(soup)
    assert years == ["2024", "2023"]
    assert table["營業收入合計"]["2024"] == 1000
    assert table["營業毛利（毛損）"]["2023"] == 360


def verify_fundamental_stage_does_not_create_dummy_data() -> None:
    features = pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2026-05-15"),
                "stock_id": "2330",
                "open": 100,
                "high": 101,
                "low": 99,
                "close": 100,
                "volume": 1000,
            }
        ]
    )

    class EmptyTWSE:
        def fetch_revenue_batch(self, start_date: str, end_date: str, save_to_disk: bool = True) -> pd.DataFrame:
            return pd.DataFrame()

    class EmptyOrchestrator:
        twse = EmptyTWSE()

    context = {"orchestrator": EmptyOrchestrator(), "stats": {}}
    result = FundamentalStage().execute(features, context)
    assert result["revenue_yoy"].isna().all()
    assert result["revenue_mom"].isna().all()
    assert "roe" not in result.columns
    assert "gross_margin" not in result.columns
    assert context["stats"]["revenue"]["dummy_used"] is False


def verify_m4_feature_contract() -> None:
    features = pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2024-01-02 10:00"),
                "stock_id": "1101",
                "symbol": "1101.TW",
                "open": 10,
                "high": 11,
                "low": 9,
                "close": 10.5,
                "volume": 1000,
                "ma20": 10,
                "rsi": 50,
                "volume_spike": 1,
                "future_alpha": 99,
            },
            {
                "date": pd.Timestamp("2025-04-02 10:00"),
                "stock_id": "1101",
                "symbol": "1101.TW",
                "open": 12,
                "high": 13,
                "low": 11,
                "close": 12.5,
                "volume": 1200,
                "ma20": 11,
                "rsi": 55,
                "volume_spike": 0,
                "future_alpha": 88,
            },
        ]
    )
    events = pd.DataFrame(
        [
            {"date": pd.Timestamp("2024-01-02"), "stock_id": "1101", "break_20d_high": 1, "volume_spike": 1},
            {"date": pd.Timestamp("2025-04-02"), "stock_id": "1101", "break_20d_high": 0, "volume_spike": 0},
        ]
    )

    with tempfile.TemporaryDirectory() as tmp:
        repository = FundamentalRepository(Path(tmp))
        repository.write_cached(
            "1101",
            {
                "metrics": [
                    {
                        "year": "2024",
                        "gross_margin": 42.0,
                        "roe": 15.0,
                        "debt_ratio": 46.6667,
                    }
                ]
            },
        )
        frame, metadata = build_m4_feature_frame(features, events, repository)

    assert not frame.duplicated(["trade_date", "stock_id"]).any()
    assert set(["technical", "event", "pattern", "fundamental"]) == set(metadata.feature_groups)
    assert "event_break_20d_high" in metadata.feature_groups["event"].columns
    assert "event_volume_spike" in metadata.feature_groups["event"].columns
    assert "volume_spike" not in metadata.feature_groups["technical"].columns
    assert "fundamental_roe" in frame.columns
    assert "fundamental_gross_margin" in frame.columns
    assert "fundamental_debt_ratio" in frame.columns
    assert set(FUNDAMENTAL_FEATURE_COLUMNS).issubset(frame.columns)
    assert all(str(frame[col].dtype) == "Float64" for col in FUNDAMENTAL_FEATURE_COLUMNS)
    early = frame.loc[frame["trade_date"] == pd.Timestamp("2024-01-02"), "fundamental_roe"].iloc[0]
    late = frame.loc[frame["trade_date"] == pd.Timestamp("2025-04-02"), "fundamental_roe"].iloc[0]
    assert pd.isna(early)
    assert late == 15.0
    candidates = candidate_feature_columns(frame, metadata)
    assert "ma20" in candidates
    assert "volume_spike" not in candidates
    assert "event_break_20d_high" in candidates
    assert "event_volume_spike" in candidates
    assert set(FUNDAMENTAL_FEATURE_COLUMNS).issubset(candidates)
    assert "future_alpha" not in candidates
    factor_issues = validate_factor_registry(frame, metadata)
    assert any(issue.factor_id == "future_alpha" and issue.severity == "ERROR" for issue in factor_issues)
    manifest = build_factor_run_manifest(frame, metadata)
    assert manifest["status"] == "FAILED"
    assert manifest["contract"]["does_not_train_model"] is True
    assert manifest["contract"]["does_not_change_production_ranking"] is True


if __name__ == "__main__":
    raise SystemExit(main())
