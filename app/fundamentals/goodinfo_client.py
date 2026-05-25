"""Goodinfo 離線抓取 client。

這個 client 只應在 CLI/排程中使用，API 與排名流程不得直接呼叫。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import time
from typing import Any

import requests
from bs4 import BeautifulSoup

from .goodinfo import StatementTable, normalize_goodinfo_statements


REPORT_CATEGORIES = {
    "income_statement": "IS_YEAR",
    "balance_sheet": "BS_YEAR",
    "cash_flow": "CF_YEAR",
}


@dataclass(frozen=True)
class GoodinfoFetchResult:
    stock_id: str
    years: list[str]
    income_statement: StatementTable
    balance_sheet: StatementTable
    cash_flow: StatementTable
    source_urls: dict[str, str]
    fetched_at: str

    def to_cache_payload(self) -> dict[str, Any]:
        financials = normalize_goodinfo_statements(
            income_statement=self.income_statement,
            balance_sheet=self.balance_sheet,
            cash_flow=self.cash_flow,
            years=self.years,
        )
        return {
            "stock_id": self.stock_id,
            "source": "Goodinfo.tw",
            "updated_at": self.fetched_at,
            "source_urls": self.source_urls,
            "years": self.years,
            "financials_by_year": financials,
            "raw": {
                "income_statement": self.income_statement,
                "balance_sheet": self.balance_sheet,
                "cash_flow": self.cash_flow,
            },
            "notes": "Goodinfo cache，由離線匯入流程產生。",
        }


class GoodinfoClient:
    def __init__(self, timeout_seconds: int = 15, delay_seconds: float = 1.0):
        self.timeout_seconds = timeout_seconds
        self.delay_seconds = delay_seconds
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X) AppleWebKit/537.36",
                "Referer": "https://goodinfo.tw/",
            }
        )

    def fetch_all(self, stock_id: str) -> GoodinfoFetchResult:
        stock_id = str(stock_id).strip()
        tables: dict[str, StatementTable] = {}
        years: list[str] = []
        source_urls: dict[str, str] = {}

        for name, category in REPORT_CATEGORIES.items():
            soup, url = self._fetch_report(stock_id=stock_id, report_category=category)
            table, table_years = parse_financial_table(soup)
            tables[name] = table
            source_urls[name] = url
            if not years and table_years:
                years = table_years
            time.sleep(self.delay_seconds)

        return GoodinfoFetchResult(
            stock_id=stock_id,
            years=years[:5],
            income_statement=tables["income_statement"],
            balance_sheet=tables["balance_sheet"],
            cash_flow=tables["cash_flow"],
            source_urls=source_urls,
            fetched_at=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
        )

    def _fetch_report(self, stock_id: str, report_category: str) -> tuple[BeautifulSoup, str]:
        days_adjusted = _goodinfo_days_adjusted()
        url = (
            "https://goodinfo.tw/tw/StockFinDetail.asp"
            f"?RPT_CAT={report_category}&STOCK_ID={stock_id}&REINIT={days_adjusted:.10f}"
        )
        response = self.session.get(url, cookies={"CLIENT_KEY": _goodinfo_client_key(days_adjusted)}, timeout=self.timeout_seconds)
        response.encoding = "utf-8"
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser"), url


def parse_financial_table(soup: BeautifulSoup) -> tuple[StatementTable, list[str]]:
    """解析 Goodinfo 財報 HTML，回傳 `{欄位: {年度: 數值}}`。"""

    candidate_tables = soup.find_all("table")
    for table in candidate_tables:
        rows = table.find_all("tr")
        years = _extract_years(rows)
        if len(years) >= 2:
            parsed = _parse_rows(rows, years)
            if parsed:
                return parsed, years
    return {}, []


def _extract_years(rows) -> list[str]:
    for row in rows[:5]:
        values = [cell.get_text(strip=True) for cell in row.find_all(["td", "th"])]
        years = [value for value in values if _is_financial_year(value)]
        if len(years) >= 2:
            return years
    return []


def _is_financial_year(value: str) -> bool:
    if len(value) != 4 or not value.isdigit():
        return False
    year = int(value)
    current_year = datetime.now(timezone(timedelta(hours=8))).year
    return 2000 <= year <= current_year + 1


def _parse_rows(rows, years: list[str]) -> StatementTable:
    data: StatementTable = {}
    for row in rows:
        values = [cell.get_text(strip=True) for cell in row.find_all(["td", "th"])]
        if len(values) < 2 or not values[0]:
            continue
        field_name = values[0]
        if field_name in years:
            continue
        year_values: dict[str, float | None] = {}
        value_cells = values[1:]
        for idx, year in enumerate(years):
            value_idx = idx * 2 if len(value_cells) >= len(years) * 2 else idx
            if value_idx < len(value_cells):
                year_values[year] = parse_number(value_cells[value_idx])
        if any(value is not None for value in year_values.values()):
            data[field_name] = year_values
    return data


def parse_number(raw: str) -> float | None:
    cleaned = str(raw).replace(",", "").replace("%", "").replace("\u3000", "").strip()
    if cleaned in {"", "-", "--", "N/A"}:
        return None
    try:
        if cleaned.startswith("(") and cleaned.endswith(")"):
            return -float(cleaned[1:-1])
        return float(cleaned)
    except ValueError:
        return None


def _goodinfo_days_adjusted() -> float:
    taipei_offset_minutes = -480
    now_ms = time.time() * 1000
    return now_ms / 86_400_000 - taipei_offset_minutes / 1440


def _goodinfo_client_key(days_adjusted: float) -> str:
    taipei_offset_minutes = -480
    return f"2.8|38057.1435627105|46946.0324515993|{taipei_offset_minutes}|{days_adjusted}|{days_adjusted}"
