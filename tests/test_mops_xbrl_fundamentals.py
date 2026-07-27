from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd
import pytest

import app.fundamentals.mops_xbrl as mops_xbrl
from app.data.fundamental_repository import FundamentalRepository
from app.fundamentals.mops_xbrl import (
    build_cache_payload,
    completed_periods,
    conservative_available_from,
    parse_xbrl_document,
    parse_xbrl_zip,
)
from app.modeling.feature_contract import (
    FUNDAMENTAL_FEATURE_COLUMNS,
    FeatureFrameMetadata,
    FeatureGroupMetadata,
    build_m4_feature_frame,
    candidate_feature_columns,
)
from app.services.fundamental_service import FundamentalService
from scripts.build_fundamental_shadow_scores import _metrics_from_payload


def _document(revenue: str, report_type: str = "cr") -> str:
    del report_type
    return f"""
    <html><body><table>
      <tr><td>4000</td><td><span class="zh">營業收入合計</span></td>
          <td><ix:nonFraction name="Revenue">{revenue}</ix:nonFraction></td></tr>
      <tr><td>5900</td><td><span class="zh">營業毛利（毛損）</span></td>
          <td><ix:nonFraction name="GrossProfit">400</ix:nonFraction></td></tr>
      <tr><td>6900</td><td><span class="zh">營業利益（損失）</span></td>
          <td><ix:nonFraction name="OperatingIncome">200</ix:nonFraction></td></tr>
      <tr><td>8200</td><td><span class="zh">本期淨利（淨損）</span></td>
          <td><ix:nonFraction name="NetIncome">100</ix:nonFraction></td></tr>
      <tr><td>31XX</td><td><span class="zh">權益總計</span></td>
          <td><ix:nonFraction name="Equity">2,000</ix:nonFraction></td></tr>
      <tr><td>11XX</td><td><span class="zh">流動資產合計</span></td>
          <td><ix:nonFraction name="CurrentAssets">1,500</ix:nonFraction></td></tr>
      <tr><td>21XX</td><td><span class="zh">流動負債合計</span></td>
          <td><ix:nonFraction name="CurrentLiabilities">500</ix:nonFraction></td></tr>
      <tr><td>2XXX</td><td><span class="zh">負債總計</span></td>
          <td><ix:nonFraction name="Liabilities">3,000</ix:nonFraction></td></tr>
      <tr><td>1XXX</td><td><span class="zh">資產總計</span></td>
          <td><ix:nonFraction name="Assets">5,000</ix:nonFraction></td></tr>
      <tr><td>AAAA</td><td><span class="zh">營業活動之淨現金流入（流出）</span></td>
          <td><ix:nonFraction name="OperatingCashFlow">300</ix:nonFraction></td></tr>
      <tr><td>BBBB</td><td><span class="zh">取得不動產、廠房及設備</span></td>
          <td><ix:nonFraction name="Capex" sign="-">50</ix:nonFraction></td></tr>
      <tr><td>9750</td><td><span class="zh">基本每股盈餘合計</span></td>
          <td><ix:nonFraction name="EPS">2.5</ix:nonFraction></td></tr>
    </table></body></html>
    """


def _duration_context(context_id: str, start: str, end: str) -> str:
    return f"""
    <xbrli:context id="{context_id}">
      <xbrli:entity><xbrli:identifier scheme="TWSE">2330</xbrli:identifier></xbrli:entity>
      <xbrli:period>
        <xbrli:startDate>{start}</xbrli:startDate>
        <xbrli:endDate>{end}</xbrli:endDate>
      </xbrli:period>
    </xbrli:context>
    """


def _cash_flow_document(
    *,
    period: str,
    current_operating_cash_flow: int,
    current_capex: int,
    prior_operating_cash_flow: int = 9999,
    prior_capex: int = -999,
) -> str:
    year = int(period[:4])
    quarter = int(period[-1])
    end = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}[quarter]
    current_context = f"From{year}0101To{year}{end.replace('-', '')}"
    prior_context = f"From{year - 1}0101To{year - 1}{end.replace('-', '')}"
    return f"""
    <html><body>
      {_duration_context(prior_context, f"{year - 1}-01-01", f"{year - 1}-{end}")}
      {_duration_context(current_context, f"{year}-01-01", f"{year}-{end}")}
      <table>
        <tr><td><span class="zh">營業收入合計</span></td>
          <td><ix:nonFraction contextRef="{prior_context}">900</ix:nonFraction></td>
          <td><ix:nonFraction contextRef="{current_context}">1,000</ix:nonFraction></td></tr>
        <tr><td><span class="zh">營業活動之淨現金流入（流出）</span></td>
          <td><ix:nonFraction contextRef="{prior_context}">{prior_operating_cash_flow}</ix:nonFraction></td>
          <td><ix:nonFraction contextRef="{current_context}">{current_operating_cash_flow}</ix:nonFraction></td></tr>
        <tr><td><span class="zh">取得不動產、廠房及設備</span></td>
          <td><ix:nonFraction contextRef="{prior_context}" sign="-">{abs(prior_capex)}</ix:nonFraction></td>
          <td><ix:nonFraction contextRef="{current_context}" sign="-">{abs(current_capex)}</ix:nonFraction></td></tr>
      </table>
    </body></html>
    """


def test_parse_xbrl_document_computes_existing_metric_contract() -> None:
    metric = parse_xbrl_document(_document("1,000"), stock_id="2330", period="2024Q1")

    assert metric is not None
    assert metric["year"] == "2024Q1"
    assert metric["available_from"] == "2024-06-01"
    assert metric["gross_margin"] == 40.0
    assert metric["operating_margin"] == 20.0
    assert metric["net_margin"] == 10.0
    assert metric["current_ratio"] == 300.0
    assert metric["debt_ratio"] == 60.0
    assert metric["roe"] == 5.0
    assert metric["roa"] == 2.0
    assert metric["free_cash_flow"] == 250.0
    assert metric["eps"] == 2.5


def test_parse_xbrl_zip_prefers_consolidated_report(tmp_path: Path) -> None:
    path = tmp_path / "tifrs-2024Q1.zip"
    with ZipFile(path, "w") as archive:
        archive.writestr("tifrs-fr1-m1-ci-ir-2330-2024Q1.html", _document("500"))
        archive.writestr("tifrs-fr1-m1-ci-cr-2330-2024Q1.html", _document("1,000"))
        archive.writestr("tifrs-fr1-m1-ci-cr-9999-2024Q1.html", _document("9,999"))

    parsed = parse_xbrl_zip(path, universe={"2330"})

    assert set(parsed) == {"2330"}
    assert parsed["2330"]["gross_margin"] == 40.0


def test_period_and_availability_contracts() -> None:
    assert completed_periods("2024Q4", "2026Q1") == [
        "2024Q4",
        "2025Q1",
        "2025Q2",
        "2025Q3",
        "2025Q4",
        "2026Q1",
    ]
    assert conservative_available_from("2024Q4") == "2025-05-01"
    assert conservative_available_from("2025Q2") == "2025-08-30"
    assert conservative_available_from("2025Q3") == "2025-11-30"


def test_service_ignores_point_in_time_metadata_in_metric_items() -> None:
    metric = parse_xbrl_document(_document("1,000"), stock_id="2330", period="2024Q1")
    payload = build_cache_payload("2330", [metric], ["2024Q1"])
    service = FundamentalService(repository=None)  # type: ignore[arg-type]

    loaded = service._load_metrics(payload)

    assert loaded[0].year == "2024Q1"
    assert loaded[0].roe == 5.0
    assert _metrics_from_payload(payload)[0].year == "2024Q1"


def test_feature_join_keeps_quarterly_metric_hidden_before_available_date(tmp_path: Path) -> None:
    metric = parse_xbrl_document(_document("1,000"), stock_id="2330", period="2024Q1")
    repository = FundamentalRepository(tmp_path)
    repository.write_cached("2330", build_cache_payload("2330", [metric], ["2024Q1"]))
    features = pd.DataFrame(
        {
            "date": ["2024-05-31", "2024-06-03"],
            "stock_id": ["2330", "2330"],
            "close": [100.0, 101.0],
        }
    )

    frame, _ = build_m4_feature_frame(
        features=features,
        fundamental_repository=repository,
        config_path=tmp_path / "missing-signals.yaml",
    )

    assert pd.isna(frame.loc[frame["trade_date"] == pd.Timestamp("2024-05-31"), "fundamental_roe"]).all()
    assert frame.loc[frame["trade_date"] == pd.Timestamp("2024-06-03"), "fundamental_roe"].iloc[0] == 5.0


def test_high_coverage_fundamentals_stay_out_of_production_candidates() -> None:
    frame = pd.DataFrame(
        {
            "technical_signal": [1.0],
            **{column: [1.0] for column in FUNDAMENTAL_FEATURE_COLUMNS},
        }
    )
    metadata = FeatureFrameMetadata(
        feature_groups={
            "technical": FeatureGroupMetadata(
                columns=["technical_signal"],
                coverage={"technical_signal": 1.0},
                missing_ratio={"technical_signal": 0.0},
            ),
            "fundamental": FeatureGroupMetadata(
                columns=list(FUNDAMENTAL_FEATURE_COLUMNS),
                coverage={column: 0.998 for column in FUNDAMENTAL_FEATURE_COLUMNS},
                missing_ratio={column: 0.002 for column in FUNDAMENTAL_FEATURE_COLUMNS},
            ),
        },
        rows=500,
        stocks=500,
        start_date="2025-01-01",
        end_date="2025-01-01",
        fundamental_cache_coverage=0.998,
        notes=[],
    )

    candidates = candidate_feature_columns(frame, metadata)

    assert "technical_signal" in candidates
    assert set(candidates).isdisjoint(FUNDAMENTAL_FEATURE_COLUMNS)


def test_cash_flow_contexts_select_current_period_and_normalize_ytd_to_quarter() -> None:
    cumulative = {
        "2025Q1": (100, -10),
        "2025Q2": (250, -30),
        "2025Q3": (450, -60),
        "2025Q4": (700, -100),
    }
    parsed = [
        parse_xbrl_document(
            _cash_flow_document(
                period=period,
                current_operating_cash_flow=operating_cash_flow,
                current_capex=capex,
            ),
            stock_id="2330",
            period=period,
        )
        for period, (operating_cash_flow, capex) in cumulative.items()
    ]

    payload = build_cache_payload("2330", parsed, cumulative)
    by_period = {item["year"]: item for item in payload["metrics"]}

    assert by_period["2025Q1"]["free_cash_flow"] == 90.0
    assert by_period["2025Q2"]["free_cash_flow"] == 130.0
    assert by_period["2025Q3"]["free_cash_flow"] == 170.0
    assert by_period["2025Q4"]["free_cash_flow"] == 210.0
    assert all(item["cash_flow_grain"] == "single_quarter" for item in by_period.values())


def test_ytd_cash_flow_without_previous_quarter_fails_closed() -> None:
    metric = parse_xbrl_document(
        _cash_flow_document(
            period="2025Q2",
            current_operating_cash_flow=250,
            current_capex=-30,
        ),
        stock_id="2330",
        period="2025Q2",
    )

    payload = build_cache_payload("2330", [metric], ["2025Q2"])

    assert payload["metrics"][0]["free_cash_flow"] is None
    assert payload["metrics"][0]["cash_flow_grain"] == "missing_previous_ytd"


def test_zip_member_count_limit_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "member-count.zip"
    with ZipFile(path, "w") as archive:
        archive.writestr("one.txt", "1")
        archive.writestr("two.txt", "2")
    monkeypatch.setattr(mops_xbrl, "MAX_ZIP_MEMBERS", 1, raising=False)

    with pytest.raises(ValueError, match="member 數量"):
        parse_xbrl_zip(path)


def test_zip_high_compression_member_metadata_fails_before_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "high-compression.zip"
    member = "tifrs-fr1-m1-ci-cr-2330-2025Q2.html"
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(member, "A" * 4096)
    with ZipFile(path) as archive:
        info = archive.getinfo(member)
        assert info.file_size == 4096
        assert info.compress_size < 100
    monkeypatch.setattr(mops_xbrl, "MAX_ZIP_MEMBER_UNCOMPRESSED_BYTES", 1024, raising=False)

    with pytest.raises(ValueError, match="單檔未壓縮大小"):
        parse_xbrl_zip(path)


def test_zip_total_uncompressed_limit_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "total-size.zip"
    with ZipFile(path, "w") as archive:
        archive.writestr("one.txt", "1234")
        archive.writestr("two.txt", "5678")
    monkeypatch.setattr(mops_xbrl, "MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES", 7, raising=False)

    with pytest.raises(ValueError, match="總未壓縮大小"):
        parse_xbrl_zip(path)
