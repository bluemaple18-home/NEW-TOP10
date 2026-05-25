"""Goodinfo 財報資料正規化。

只負責把外部欄位名稱轉成內部標準欄位；抓取、快取與 UI 另行處理。
"""

from __future__ import annotations

from typing import Iterable


StatementTable = dict[str, dict[str, float | None]]


FIELD_PATTERNS: dict[str, tuple[tuple[str, ...], ...]] = {
    "revenue": (("營業收入",), ("收入合計",)),
    "gross_profit": (("毛利",),),
    "selling_expense": (("推銷",), ("銷售", "費用")),
    "admin_expense": (("管理費用",),),
    "rd_expense": (("研究",), ("研發",)),
    "operating_income": (("營業利益",),),
    "net_income": (("稅後淨利",), ("本期淨利",)),
    "eps": (("每股", "盈餘"), ("EPS",)),
    "cash": (("現金及約當現金",),),
    "inventory": (("存貨",),),
    "current_assets": (("流動資產合計",),),
    "current_liabilities": (("流動負債合計",),),
    "total_liabilities": (("負債總額",),),
    "equity": (("股東權益總額",), ("權益總額",)),
    "total_assets": (("資產總額",),),
    "operating_cash_flow": (("營業活動", "淨現金"),),
    "investing_cash_flow": (("投資活動", "淨現金"),),
    "financing_cash_flow": (("融資活動", "淨現金"),),
    "capex": (("固定資產",), ("資本支出",)),
    "cash_dividend": (("發放現金股利",), ("現金股利",)),
}


def normalize_goodinfo_statements(
    income_statement: StatementTable,
    balance_sheet: StatementTable,
    cash_flow: StatementTable,
    years: Iterable[str],
) -> dict[str, dict[str, float | None]]:
    """將 Goodinfo 三張表轉成年度標準欄位。"""

    years = [str(year) for year in years]
    sources = {
        "income": income_statement,
        "balance": balance_sheet,
        "cash_flow": cash_flow,
    }
    field_source = {
        "revenue": "income",
        "gross_profit": "income",
        "selling_expense": "income",
        "admin_expense": "income",
        "rd_expense": "income",
        "operating_income": "income",
        "net_income": "income",
        "eps": "income",
        "cash": "balance",
        "inventory": "balance",
        "current_assets": "balance",
        "current_liabilities": "balance",
        "total_liabilities": "balance",
        "equity": "balance",
        "total_assets": "balance",
        "operating_cash_flow": "cash_flow",
        "investing_cash_flow": "cash_flow",
        "financing_cash_flow": "cash_flow",
        "capex": "cash_flow",
        "cash_dividend": "cash_flow",
    }

    normalized = {year: {} for year in years}
    for canonical, source_name in field_source.items():
        table = sources[source_name]
        raw_key = find_matching_field(table.keys(), FIELD_PATTERNS[canonical])
        for year in years:
            normalized[year][canonical] = table.get(raw_key, {}).get(year) if raw_key else None
    return normalized


def find_matching_field(field_names: Iterable[str], patterns: tuple[tuple[str, ...], ...]) -> str | None:
    for pattern in patterns:
        for field_name in field_names:
            normalized = str(field_name).replace("　", "").replace(" ", "")
            if all(token.lower() in normalized.lower() for token in pattern):
                return field_name
    return None
