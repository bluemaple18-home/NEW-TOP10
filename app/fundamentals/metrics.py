"""基本面財務指標計算。

輸入採標準化年度欄位，資料來源可來自 Goodinfo、公開資訊觀測站或未來的資料庫。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class FinancialYearMetrics:
    year: str
    gross_margin: float | None
    operating_margin: float | None
    net_margin: float | None
    current_ratio: float | None
    debt_ratio: float | None
    roe: float | None
    roa: float | None
    free_cash_flow: float | None
    eps: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compute_financial_metrics(financials_by_year: dict[str, dict[str, float | None]]) -> list[FinancialYearMetrics]:
    """從標準化財報欄位計算年度基本面品質指標。"""

    metrics: list[FinancialYearMetrics] = []
    for year in sorted(financials_by_year, reverse=True):
        row = financials_by_year[year]
        revenue = row.get("revenue")
        gross_profit = row.get("gross_profit")
        operating_income = row.get("operating_income")
        net_income = row.get("net_income")
        current_assets = row.get("current_assets")
        current_liabilities = row.get("current_liabilities")
        total_liabilities = row.get("total_liabilities")
        total_assets = row.get("total_assets")
        equity = row.get("equity")
        operating_cash_flow = row.get("operating_cash_flow")
        capex = row.get("capex")

        metrics.append(
            FinancialYearMetrics(
                year=str(year),
                gross_margin=_ratio(gross_profit, revenue),
                operating_margin=_ratio(operating_income, revenue),
                net_margin=_ratio(net_income, revenue),
                current_ratio=_ratio(current_assets, current_liabilities),
                debt_ratio=_ratio(total_liabilities, total_assets),
                roe=_ratio(net_income, equity),
                roa=_ratio(net_income, total_assets),
                free_cash_flow=_free_cash_flow(operating_cash_flow, capex),
                eps=row.get("eps"),
            )
        )
    return metrics


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return round(float(numerator) / float(denominator) * 100, 4)


def _free_cash_flow(operating_cash_flow: float | None, capex: float | None) -> float | None:
    if operating_cash_flow is None:
        return None
    if capex is None:
        return float(operating_cash_flow)
    return round(float(operating_cash_flow) + float(capex), 4)
