"""基本面 service。

輸入只接受本地 cache，避免 UI/API request 即時觸發外部爬蟲。
"""

from __future__ import annotations

from app.contracts import (
    FundamentalDimensionSummary,
    FundamentalMetricItem,
    FundamentalSourceLinks,
    FundamentalTrendItem,
    FundamentalWarningItem,
    StockFundamentalsResponse,
)
from app.data.fundamental_repository import FundamentalRepository
from app.fundamentals import compute_financial_metrics, sanity_check
from app.fundamentals.metrics import FinancialYearMetrics


DIMENSION_SPECS = (
    (
        "operations",
        "經營品質",
        (
            ("gross_margin", "毛利率", "higher"),
            ("operating_margin", "營業利益率", "higher"),
        ),
    ),
    (
        "profitability",
        "獲利能力",
        (
            ("eps", "EPS", "higher"),
            ("roe", "ROE", "higher"),
            ("net_margin", "淨利率", "higher"),
        ),
    ),
    (
        "financial_health",
        "財務健全度",
        (
            ("current_ratio", "流動比率", "higher"),
            ("debt_ratio", "負債比率", "lower"),
            ("free_cash_flow", "自由現金流", "higher"),
        ),
    ),
)


class FundamentalService:
    def __init__(self, repository: FundamentalRepository):
        self.repository = repository

    def stock_fundamentals(self, stock_id: str) -> StockFundamentalsResponse:
        payload = self.repository.load_cached(stock_id)
        if payload is None:
            return StockFundamentalsResponse(
                stock_id=str(stock_id),
                available=False,
                notes="尚無基本面 cache；請先執行離線 Goodinfo/MOPS 匯入流程。",
            )

        metrics = self._load_metrics(payload)
        warnings = [FundamentalWarningItem(**warning.to_dict()) for warning in sanity_check(metrics)]
        warnings.extend(FundamentalWarningItem(**item) for item in payload.get("warnings", []))

        return StockFundamentalsResponse(
            stock_id=str(stock_id),
            available=True,
            source=payload.get("source"),
            updated_at=payload.get("updated_at"),
            source_links=self._source_links(str(stock_id), payload),
            years_covered=list(payload.get("years") or [item.year for item in metrics]),
            metrics=[FundamentalMetricItem(**item.to_dict()) for item in metrics],
            dimensions=self._dimension_summaries(metrics),
            warnings=warnings,
            notes=payload.get("notes"),
        )

    def clear_cache(self) -> None:
        self.repository.clear_cache()

    def _load_metrics(self, payload: dict) -> list:
        if payload.get("metrics"):
            return [FinancialYearMetrics(**item) for item in payload["metrics"]]
        financials = payload.get("financials_by_year") or {}
        return compute_financial_metrics(financials)

    def _source_links(self, stock_id: str, payload: dict) -> FundamentalSourceLinks:
        urls = payload.get("source_urls") or {}
        return FundamentalSourceLinks(
            income_statement=urls.get("income_statement"),
            balance_sheet=urls.get("balance_sheet"),
            cash_flow=urls.get("cash_flow"),
            mops=f"https://mops.twse.com.tw/mops/web/t05st01?step=1&co_id={stock_id}&TYPEK=sii",
            mops_otc=f"https://mops.twse.com.tw/mops/web/t05st01?step=1&co_id={stock_id}&TYPEK=otc",
        )

    def _dimension_summaries(self, metrics: list[FinancialYearMetrics]) -> list[FundamentalDimensionSummary]:
        if not metrics:
            return []
        result = []
        for dimension_id, label, fields in DIMENSION_SPECS:
            items = [self._trend_item(metrics, key=key, label=field_label, preference=preference) for key, field_label, preference in fields]
            items = [item for item in items if item.latest_value is not None]
            result.append(
                FundamentalDimensionSummary(
                    id=dimension_id,
                    label=label,
                    items=items,
                    highlights=[item.summary for item in items[:3]],
                )
            )
        return result

    def _trend_item(
        self,
        metrics: list[FinancialYearMetrics],
        key: str,
        label: str,
        preference: str,
    ) -> FundamentalTrendItem:
        latest = metrics[0]
        previous = metrics[1] if len(metrics) > 1 else None
        latest_value = getattr(latest, key)
        previous_value = getattr(previous, key) if previous else None
        change = None
        if latest_value is not None and previous_value is not None:
            change = round(float(latest_value) - float(previous_value), 4)
        direction = self._direction(change)
        tone = self._tone(direction, preference)
        return FundamentalTrendItem(
            key=key,
            label=label,
            latest_year=latest.year,
            latest_value=latest_value,
            previous_year=previous.year if previous else None,
            previous_value=previous_value,
            change=change,
            direction=direction,
            tone=tone,
            summary=self._summary(label, latest, latest_value, previous, previous_value, change, direction, preference),
        )

    def _direction(self, change: float | None) -> str:
        if change is None:
            return "neutral"
        if abs(change) < 0.1:
            return "neutral"
        return "up" if change > 0 else "down"

    def _tone(self, direction: str, preference: str) -> str:
        if direction == "neutral":
            return "neutral"
        improves = (direction == "up" and preference == "higher") or (direction == "down" and preference == "lower")
        return "positive" if improves else "warning"

    def _summary(
        self,
        label: str,
        latest: FinancialYearMetrics,
        latest_value: float | None,
        previous: FinancialYearMetrics | None,
        previous_value: float | None,
        change: float | None,
        direction: str,
        preference: str,
    ) -> str:
        if latest_value is None:
            return f"{label}缺資料，暫不納入判斷。"
        if previous is None or previous_value is None or change is None:
            return f"{latest.year} {label}為 {latest_value:.2f}，尚無可比較年度。"
        verb = "上升" if direction == "up" else "下降" if direction == "down" else "持平"
        if direction == "neutral":
            meaning = "變化不大"
        else:
            improved = (direction == "up" and preference == "higher") or (direction == "down" and preference == "lower")
            meaning = "改善" if improved else "轉弱"
        return f"{label} {previous.year} {previous_value:.2f} → {latest.year} {latest_value:.2f}，{verb} {change:+.2f}，{meaning}。"
