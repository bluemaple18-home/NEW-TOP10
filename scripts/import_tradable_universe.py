#!/usr/bin/env python3
"""離線匯入上市櫃可交易股票 universe。

這支腳本只允許離線重跑，不應放進 API request path。外部來源失敗時會保留
既有 `data/reference/tradable_universe.csv`，並把失敗原因寫到 summary artifact。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
import argparse
import csv
import json
from pathlib import Path
import sys
from typing import Any

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.data.reference_repository import MARKET_TYPES, TRADABLE_STOCK_ID_PATTERN


FIELDS = [
    "stock_id",
    "stock_name",
    "market_type",
    "is_etf",
    "is_active",
    "source",
    "updated_at",
]

DEFAULT_SOURCES = {
    "twse_openapi": {
        "url": "https://openapi.twse.com.tw/v1/opendata/t187ap03_L",
        "market_type": "twse",
        "code_keys": ["公司代號", "股票代號", "證券代號", "Code", "stockNo"],
        "name_keys": ["公司簡稱", "公司名稱", "股票名稱", "證券名稱", "Name", "stockName"],
        "date_keys": ["出表日期", "Date", "資料日期"],
    },
    "tpex_openapi": {
        "url": "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O",
        "market_type": "tpex",
        "code_keys": ["SecuritiesCompanyCode", "公司代號", "股票代號", "Code", "stockNo"],
        "name_keys": ["CompanyAbbreviation", "CompanyName", "公司簡稱", "公司名稱", "Name", "stockName"],
        "date_keys": ["Date", "出表日期", "資料日期"],
    },
}


@dataclass(frozen=True)
class UniverseItem:
    stock_id: str
    stock_name: str
    market_type: str
    is_etf: bool
    is_active: bool
    source: str
    updated_at: str


@dataclass
class SourceSummary:
    source: str
    url: str
    market_type: str
    status: str
    raw_rows: int = 0
    valid_rows: int = 0
    invalid_rows: int = 0
    error: str = ""
    raw_path: str | None = None


def main() -> int:
    parser = argparse.ArgumentParser(description="Import TWSE/TPEx tradable stock universe")
    parser.add_argument("--sources", help="Comma-separated source names; default: twse_openapi,tpex_openapi")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and validate, but do not update local CSV")
    parser.add_argument("--allow-partial", action="store_true", help="Write rows if at least one selected source succeeds")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--output", default="data/reference/tradable_universe.csv")
    parser.add_argument("--summary", default="artifacts/tradable_universe_import_summary.json")
    args = parser.parse_args()

    selected_sources = parse_sources(args.sources)
    invalid_sources = [source for source in selected_sources if source not in DEFAULT_SOURCES]
    if invalid_sources:
        print(f"unknown_sources={','.join(invalid_sources)}")
        return 2

    raw_dir = PROJECT_ROOT / "data" / "raw" / "reference" / "tradable_universe" / date.today().isoformat()
    all_items: list[UniverseItem] = []
    summaries: list[SourceSummary] = []
    for source in selected_sources:
        summary, items = fetch_source(source, DEFAULT_SOURCES[source], raw_dir=raw_dir, timeout=args.timeout)
        summaries.append(summary)
        all_items.extend(items)
        print(
            f"{source}: status={summary.status} raw={summary.raw_rows} "
            f"valid={summary.valid_rows} invalid={summary.invalid_rows}"
        )
        if summary.error:
            print(f"  {summary.error}")

    failed_sources = [summary.source for summary in summaries if summary.status == "FAILED"]
    deduped_items, duplicate_removed = dedupe_items(all_items)
    can_write = bool(deduped_items) and not args.dry_run and (not failed_sources or args.allow_partial)
    output_path = PROJECT_ROOT / args.output
    preserved_existing = False
    if can_write:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        write_csv(output_path, deduped_items)
    elif output_path.exists():
        preserved_existing = True

    summary_path = PROJECT_ROOT / args.summary
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": args.dry_run,
        "allow_partial": args.allow_partial,
        "selected_sources": selected_sources,
        "sources": [asdict(summary) for summary in summaries],
        "raw_rows": sum(summary.raw_rows for summary in summaries),
        "valid_rows": sum(summary.valid_rows for summary in summaries),
        "invalid_rows": sum(summary.invalid_rows for summary in summaries),
        "deduped_rows": len(deduped_items),
        "duplicate_removed": duplicate_removed,
        "failed_sources": failed_sources,
        "output_path": str(output_path),
        "wrote_output": can_write,
        "preserved_existing": preserved_existing,
    }
    summary_path.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"tradable_universe_import_summary={summary_path}")

    if failed_sources and not args.allow_partial:
        return 1
    if not deduped_items:
        return 1
    return 0


def parse_sources(value: str | None) -> list[str]:
    if not value:
        return ["twse_openapi", "tpex_openapi"]
    return [source.strip() for source in value.split(",") if source.strip()]


def fetch_source(
    source: str,
    config: dict[str, Any],
    raw_dir: Path,
    timeout: float,
) -> tuple[SourceSummary, list[UniverseItem]]:
    summary = SourceSummary(source=source, url=config["url"], market_type=config["market_type"], status="FAILED")
    try:
        response = requests.get(config["url"], timeout=timeout, headers={"User-Agent": "TOP10new-universe-import/1.0"})
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list):
            raise ValueError("OpenAPI response is not a JSON array")
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_path = raw_dir / f"{source}.json"
        raw_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        summary.raw_path = str(raw_path)
        summary.raw_rows = len(rows)
        items: list[UniverseItem] = []
        for row in rows:
            item = normalize_row(row, source=source, config=config)
            if item is None:
                summary.invalid_rows += 1
                continue
            items.append(item)
        summary.valid_rows = len(items)
        summary.status = "OK" if items else "EMPTY"
        return summary, items
    except Exception as exc:
        summary.error = f"{type(exc).__name__}: {exc}"
        return summary, []


def normalize_row(row: object, source: str, config: dict[str, Any]) -> UniverseItem | None:
    if not isinstance(row, dict):
        return None
    stock_id = first_text(row, config["code_keys"])
    stock_name = first_text(row, config["name_keys"])
    market_type = str(config["market_type"]).strip()
    if market_type not in MARKET_TYPES:
        return None
    if not stock_id or not TRADABLE_STOCK_ID_PATTERN.fullmatch(stock_id):
        return None
    if not stock_name:
        return None
    return UniverseItem(
        stock_id=stock_id,
        stock_name=stock_name,
        market_type=market_type,
        is_etf=False,
        is_active=True,
        source=source,
        updated_at=parse_source_date(first_text(row, config["date_keys"])),
    )


def first_text(row: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        text = str(value).replace("\u3000", " ").strip()
        if text and text != "－":
            return text
    return ""


def parse_source_date(value: str) -> str:
    text = str(value or "").strip()
    if len(text) == 7 and text.isdigit():
        year = int(text[:3]) + 1911
        return f"{year:04d}-{text[3:5]}-{text[5:7]}"
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return text or datetime.now(timezone.utc).date().isoformat()


def dedupe_items(items: list[UniverseItem]) -> tuple[list[UniverseItem], int]:
    by_stock_id: dict[str, UniverseItem] = {}
    for item in items:
        existing = by_stock_id.get(item.stock_id)
        if existing is None or existing.source != "twse_openapi":
            by_stock_id[item.stock_id] = item
    deduped = sorted(by_stock_id.values(), key=lambda item: (item.market_type, item.stock_id))
    return deduped, len(items) - len(deduped)


def write_csv(path: Path, items: list[UniverseItem]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for item in items:
            row = asdict(item)
            row["is_etf"] = "true" if item.is_etf else "false"
            row["is_active"] = "true" if item.is_active else "false"
            writer.writerow(row)


if __name__ == "__main__":
    raise SystemExit(main())
