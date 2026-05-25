"""基本面合理性檢查。"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .metrics import FinancialYearMetrics


@dataclass(frozen=True)
class FundamentalWarning:
    level: str
    field: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def sanity_check(metrics: list[FinancialYearMetrics]) -> list[FundamentalWarning]:
    warnings: list[FundamentalWarning] = []
    for item in metrics:
        if item.gross_margin is not None:
            if item.gross_margin > 100:
                warnings.append(FundamentalWarning("error", f"{item.year} 毛利率", f"{item.gross_margin:.1f}% 超過 100%，請核對原始財報"))
            elif item.gross_margin < -50:
                warnings.append(FundamentalWarning("error", f"{item.year} 毛利率", f"{item.gross_margin:.1f}% 低於 -50%，請核對特殊損失"))
        if item.current_ratio is not None and item.current_ratio < 0:
            warnings.append(FundamentalWarning("error", f"{item.year} 流動比率", f"{item.current_ratio:.1f}% 為負值"))
        if item.debt_ratio is not None and item.debt_ratio > 100:
            warnings.append(FundamentalWarning("warn", f"{item.year} 負債比率", f"{item.debt_ratio:.1f}% 超過 100%，需確認產業與資本結構"))
        if item.roe is not None and item.roe > 100:
            warnings.append(FundamentalWarning("warn", f"{item.year} ROE", f"{item.roe:.1f}% 超過 100%，可能為高槓桿或權益偏低"))

    by_year = {item.year: item for item in metrics}
    years = sorted(by_year)
    for prev, curr in zip(years, years[1:]):
        prev_margin = by_year[prev].net_margin
        curr_margin = by_year[curr].net_margin
        if prev_margin is None or curr_margin is None:
            continue
        delta = curr_margin - prev_margin
        if abs(delta) > 30:
            warnings.append(FundamentalWarning("warn", f"{prev}->{curr} 淨利率", f"波動 {delta:+.1f} 個百分點，需確認一次性損益"))
    return warnings
