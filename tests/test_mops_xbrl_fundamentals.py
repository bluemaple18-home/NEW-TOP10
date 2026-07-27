from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import pandas as pd

from app.data.fundamental_repository import FundamentalRepository
from app.fundamentals.mops_xbrl import (
    build_cache_payload,
    completed_periods,
    conservative_available_from,
    parse_xbrl_document,
    parse_xbrl_zip,
)
from app.modeling.feature_contract import build_m4_feature_frame
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
