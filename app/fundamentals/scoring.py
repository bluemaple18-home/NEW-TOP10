"""基本面 shadow score。

這個分數只作研究與解釋用途，不直接改 ranking 權重。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from .metrics import FinancialYearMetrics


@dataclass(frozen=True)
class FundamentalScore:
    stock_id: str
    year: str | None
    fundamental_quality_score: float | None
    profitability_score: float | None
    margin_score: float | None
    financial_health_score: float | None
    cashflow_score: float | None
    warning_penalty: float
    notes: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def score_fundamentals(
    stock_id: str,
    metrics: list[FinancialYearMetrics],
    warnings: Iterable[Any] = (),
    enforce_recency: bool = True,
) -> FundamentalScore:
    """把年度財務指標轉成 0-1 shadow score。"""

    if not metrics:
        return FundamentalScore(
            stock_id=str(stock_id),
            year=None,
            fundamental_quality_score=None,
            profitability_score=None,
            margin_score=None,
            financial_health_score=None,
            cashflow_score=None,
            warning_penalty=0.0,
            notes="尚無可評分的基本面 metrics。",
        )

    latest = metrics[0]
    if enforce_recency and _is_stale_year(latest.year):
        return FundamentalScore(
            stock_id=str(stock_id),
            year=latest.year,
            fundamental_quality_score=None,
            profitability_score=None,
            margin_score=None,
            financial_health_score=None,
            cashflow_score=None,
            warning_penalty=0.0,
            notes=f"最新財報年度 {latest.year} 過舊，暫不納入推薦評分。",
        )

    previous = metrics[1] if len(metrics) > 1 else None
    profitability = _mean_present(
        [
            _scale(latest.roe, 0, 20),
            _scale(latest.roa, 0, 10),
            _scale(latest.net_margin, 0, 20),
            _trend_score(latest.eps, previous.eps if previous else None, higher_is_better=True),
        ]
    )
    margin = _mean_present(
        [
            _scale(latest.gross_margin, 0, 50),
            _scale(latest.operating_margin, 0, 20),
        ]
    )
    financial_health = _mean_present(
        [
            _inverse_scale(latest.debt_ratio, 0, 100),
            _scale(latest.current_ratio, 80, 200),
        ]
    )
    cashflow = _mean_present(
        [
            _positive_cashflow_score(latest.free_cash_flow),
            _trend_score(latest.free_cash_flow, previous.free_cash_flow if previous else None, higher_is_better=True),
        ]
    )
    penalty = _warning_penalty(warnings)

    components = [profitability, margin, financial_health, cashflow]
    if all(component is None for component in components):
        quality = None
    else:
        quality = _clamp(
            0.35 * (profitability if profitability is not None else 0.5)
            + 0.25 * (margin if margin is not None else 0.5)
            + 0.25 * (financial_health if financial_health is not None else 0.5)
            + 0.15 * (cashflow if cashflow is not None else 0.5)
            - penalty
        )

    return FundamentalScore(
        stock_id=str(stock_id),
        year=latest.year,
        fundamental_quality_score=_round(quality),
        profitability_score=_round(profitability),
        margin_score=_round(margin),
        financial_health_score=_round(financial_health),
        cashflow_score=_round(cashflow),
        warning_penalty=round(penalty, 4),
        notes=_score_note(quality, penalty),
    )


def score_from_feature_row(row: Any) -> float | None:
    """從 feature frame 的 fundamental_* 欄位計算 row-level shadow score。"""

    metrics = [
        FinancialYearMetrics(
            year=str(getattr(row, "year", "")) or "row",
            gross_margin=_get(row, "fundamental_gross_margin"),
            operating_margin=_get(row, "fundamental_operating_margin"),
            net_margin=_get(row, "fundamental_net_margin"),
            current_ratio=_get(row, "fundamental_current_ratio"),
            debt_ratio=_get(row, "fundamental_debt_ratio"),
            roe=_get(row, "fundamental_roe"),
            roa=_get(row, "fundamental_roa"),
            free_cash_flow=_get(row, "fundamental_free_cash_flow"),
            eps=_get(row, "fundamental_eps"),
        )
    ]
    return score_fundamentals(
        stock_id=str(_get(row, "stock_id") or ""),
        metrics=metrics,
        enforce_recency=False,
    ).fundamental_quality_score


def _get(row: Any, key: str) -> Any:
    if isinstance(row, dict):
        return row.get(key)
    return getattr(row, key, None)


def _scale(value: float | None, low: float, high: float) -> float | None:
    parsed = _to_float(value)
    if parsed is None:
        return None
    if high <= low:
        return None
    return _clamp((parsed - low) / (high - low))


def _inverse_scale(value: float | None, low: float, high: float) -> float | None:
    scaled = _scale(value, low, high)
    if scaled is None:
        return None
    return _clamp(1 - scaled)


def _positive_cashflow_score(value: float | None) -> float | None:
    parsed = _to_float(value)
    if parsed is None:
        return None
    if parsed > 0:
        return 1.0
    if parsed == 0:
        return 0.5
    return 0.0


def _trend_score(latest: float | None, previous: float | None, higher_is_better: bool) -> float | None:
    latest_value = _to_float(latest)
    previous_value = _to_float(previous)
    if latest_value is None or previous_value is None:
        return None
    delta = latest_value - previous_value
    if abs(delta) < 1e-9:
        return 0.5
    improved = delta > 0 if higher_is_better else delta < 0
    return 1.0 if improved else 0.0


def _warning_penalty(warnings: Iterable[Any]) -> float:
    penalty = 0.0
    for warning in warnings:
        level = _get(warning, "level")
        if level == "error":
            penalty += 0.25
        elif level == "warn":
            penalty += 0.10
    return min(penalty, 0.4)


def _mean_present(values: list[float | None]) -> float | None:
    present = [float(value) for value in values if value is not None]
    if not present:
        return None
    return _clamp(sum(present) / len(present))


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if value != value:
            return None
    except TypeError:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_stale_year(year: str | None) -> bool:
    if year is None:
        return True
    try:
        parsed = int(str(year)[:4])
    except ValueError:
        return True
    current_year = datetime.now(timezone(timedelta(hours=8))).year
    return parsed < current_year - 2


def _round(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 4)


def _score_note(score: float | None, penalty: float) -> str:
    if score is None:
        return "資料不足，暫不評分。"
    if penalty > 0:
        return "已扣除合理性警示懲罰，需人工核對。"
    if score >= 0.75:
        return "基本面品質偏強，可作為動能候選支撐。"
    if score >= 0.5:
        return "基本面品質中性，適合作為輔助確認。"
    return "基本面品質偏弱，若技術面強勢仍需降低信任度。"
