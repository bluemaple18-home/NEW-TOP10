#!/usr/bin/env python3
"""建立 chip-flow shadow materialized features。

此腳本會抓取指定股票與日期區間的三大法人、融資融券資料，
輸出獨立 shadow CSV 與摘要 JSON，不覆寫 production features.parquet。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

RUN_DATE = "2026-06-06"
SCHEMA_VERSION = "chip-flow-materialized-features.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build chip-flow shadow materialized features")
    parser.add_argument("--stock-ids", default="2330,2317,2454")
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--seed-csv", nargs="*", default=[], help="既有 materialized CSV；符合 stock/date 的資料會先重用")
    parser.add_argument("--cache-dir", default="data/raw/chip/cache", help="per-stock normalized cache 目錄")
    parser.add_argument("--refresh-cache", action="store_true", help="忽略 cache，重新抓取指定 stock/date")
    parser.add_argument("--output-csv", default=f"data/raw/chip/chip_flow_materialized_{RUN_DATE}.csv")
    parser.add_argument(
        "--output",
        default=f"artifacts/model_experiments/chip_flow_materialized_features_{RUN_DATE}.json",
    )
    parser.add_argument("--markdown-output", default=None)
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def expected_columns() -> list[str]:
    return [
        "date",
        "stock_id",
        "foreign_buy",
        "trust_buy",
        "dealer_buy",
        "institutional_available",
        "margin_purchase_buy",
        "margin_purchase_sell",
        "margin_purchase_cash_repayment",
        "margin_purchase_today_balance",
        "margin_purchase_yesterday_balance",
        "short_sale_buy",
        "short_sale_sell",
        "short_sale_cash_repayment",
        "short_sale_today_balance",
        "short_sale_yesterday_balance",
        "margin_purchase_balance_change",
        "short_sale_balance_change",
        "margin_available",
    ]


def normalize_stock_id(value: Any) -> str:
    return str(value).strip().zfill(4)


def cache_path(cache_dir: Path, stock_id: str, start_date: str, end_date: str, source: str) -> Path:
    return cache_dir / f"{normalize_stock_id(stock_id)}_{start_date}_{end_date}_{source}.csv"


def read_normalized_cache(path: Path) -> Any:
    import pandas as pd

    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path, parse_dates=["date"], dtype={"stock_id": str})
    frame["stock_id"] = frame["stock_id"].astype(str).str.zfill(4)
    return frame


def write_normalized_cache(path: Path, frame: Any, columns: list[str]) -> None:
    import pandas as pd

    path.parent.mkdir(parents=True, exist_ok=True)
    if frame.empty:
        pd.DataFrame(columns=columns).to_csv(path, index=False)
        return
    frame.to_csv(path, index=False)


def load_seed_rows(paths: list[str], stock_ids: list[str], start_date: str, end_date: str) -> Any:
    import pandas as pd

    frames = []
    stock_set = set(stock_ids)
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    for value in paths:
        path = resolve_path(value)
        if not path.exists():
            continue
        frame = pd.read_csv(path, parse_dates=["date"], dtype={"stock_id": str})
        if frame.empty or "date" not in frame.columns or "stock_id" not in frame.columns:
            continue
        frame["stock_id"] = frame["stock_id"].astype(str).str.zfill(4)
        frame = frame[frame["stock_id"].isin(stock_set) & frame["date"].between(start, end)]
        if not frame.empty:
            frames.append(frame)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).drop_duplicates(subset=["date", "stock_id"], keep="last")


def covered_stock_ids(seed: Any) -> set[str]:
    if seed.empty:
        return set()
    required = {"institutional_available", "margin_available"}
    if not required.issubset(seed.columns):
        return set()
    covered = seed[
        seed["institutional_available"].fillna(False).astype(bool)
        & seed["margin_available"].fillna(False).astype(bool)
    ]
    return set(covered["stock_id"].astype(str).str.zfill(4).unique())


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    import pandas as pd
    from app.finmind_integrator import FinMindIntegrator

    stock_ids = [normalize_stock_id(item) for item in args.stock_ids.split(",") if item.strip()]
    institutional_frames = []
    margin_frames = []
    errors: list[str] = []
    cache_dir = resolve_path(args.cache_dir)
    seed = load_seed_rows(args.seed_csv, stock_ids, args.start_date, args.end_date)
    seed_covered = covered_stock_ids(seed)
    fetch_stock_ids = [stock_id for stock_id in stock_ids if stock_id not in seed_covered]
    integrator = FinMindIntegrator() if fetch_stock_ids else None
    cache_hits = {"institutional": 0, "margin": 0}
    network_fetches = {"institutional": 0, "margin": 0}

    for stock_id in fetch_stock_ids:
        inst_cache = cache_path(cache_dir, stock_id, args.start_date, args.end_date, "institutional")
        try:
            if inst_cache.exists() and not args.refresh_cache:
                normalized_inst = read_normalized_cache(inst_cache)
                cache_hits["institutional"] += 1
            else:
                raw_inst = integrator.fetcher.get_institutional_investors(stock_id, args.start_date, args.end_date)
                normalized_inst = integrator._normalize_institutional(raw_inst, stock_id)
                write_normalized_cache(
                    inst_cache,
                    normalized_inst,
                    ["date", "stock_id", "foreign_buy", "trust_buy", "dealer_buy", "institutional_available"],
                )
                network_fetches["institutional"] += 1
            if not normalized_inst.empty:
                institutional_frames.append(normalized_inst)
        except Exception as exc:
            errors.append(f"{stock_id}: institutional fetch failed: {exc}")

        margin_cache = cache_path(cache_dir, stock_id, args.start_date, args.end_date, "margin")
        try:
            if margin_cache.exists() and not args.refresh_cache:
                normalized_margin = read_normalized_cache(margin_cache)
                cache_hits["margin"] += 1
            else:
                raw_margin = integrator.fetcher.get_margin_purchase_short_sale(stock_id, args.start_date, args.end_date)
                normalized_margin = integrator._normalize_margin(raw_margin, stock_id)
                write_normalized_cache(
                    margin_cache,
                    normalized_margin,
                    [
                        "date",
                        "stock_id",
                        "margin_purchase_buy",
                        "margin_purchase_sell",
                        "margin_purchase_cash_repayment",
                        "margin_purchase_today_balance",
                        "margin_purchase_yesterday_balance",
                        "short_sale_buy",
                        "short_sale_sell",
                        "short_sale_cash_repayment",
                        "short_sale_today_balance",
                        "short_sale_yesterday_balance",
                        "margin_purchase_balance_change",
                        "short_sale_balance_change",
                        "margin_available",
                    ],
                )
                network_fetches["margin"] += 1
            if not normalized_margin.empty:
                margin_frames.append(normalized_margin)
        except Exception as exc:
            errors.append(f"{stock_id}: margin fetch failed: {exc}")

    institutional = pd.concat(institutional_frames, ignore_index=True) if institutional_frames else pd.DataFrame()
    margin = pd.concat(margin_frames, ignore_index=True) if margin_frames else pd.DataFrame()
    if not institutional.empty and not margin.empty:
        materialized = institutional.merge(margin, on=["date", "stock_id"], how="outer")
    elif not institutional.empty:
        materialized = institutional
    else:
        materialized = margin
    if not seed.empty:
        materialized = pd.concat([seed, materialized], ignore_index=True) if not materialized.empty else seed
        materialized = materialized.drop_duplicates(subset=["date", "stock_id"], keep="last")

    output_csv = resolve_path(args.output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    if not materialized.empty:
        materialized = materialized.sort_values(["date", "stock_id"]).copy()
        for column in expected_columns():
            if column not in materialized.columns:
                materialized[column] = pd.NA
        materialized = materialized[expected_columns()]
        materialized.to_csv(output_csv, index=False)
    else:
        output_csv.write_text("", encoding="utf-8")

    required = {"institutional_available", "margin_available"}
    available_cols = set(materialized.columns) if not materialized.empty else set()
    blockers = []
    if materialized.empty:
        blockers.append("materialized chip-flow frame is empty")
    if not required.issubset(available_cols):
        blockers.append("materialized frame missing availability flags")

    status = "OK" if not blockers else "BLOCKED"
    latest_date = None
    if not materialized.empty and "date" in materialized.columns:
        latest_date = str(pd.to_datetime(materialized["date"]).max().date())

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "contract": {
            "research_only": True,
            "shadow_materialization_only": True,
            "changes_model": False,
            "changes_production_ranking": False,
            "changes_risk_adjusted_score": False,
            "does_not_send_push": True,
            "does_not_write_production_features": True,
        },
        "inputs": {
            "stock_ids": stock_ids,
            "start_date": args.start_date,
            "end_date": args.end_date,
        },
        "outputs": {
            "csv": repo_path(output_csv),
        },
        "summary": {
            "row_count": int(len(materialized)),
            "stock_count": int(materialized["stock_id"].nunique()) if not materialized.empty and "stock_id" in materialized.columns else 0,
            "latest_date": latest_date,
            "columns": list(materialized.columns) if not materialized.empty else [],
            "institutional_rows": int(len(institutional)),
            "margin_rows": int(len(margin)),
            "seed_rows": int(len(seed)),
            "seed_covered_stock_count": len(seed_covered),
            "fetch_stock_count": len(fetch_stock_ids),
            "cache_hits": cache_hits,
            "network_fetches": network_fetches,
            "errors": errors,
        },
        "blockers": blockers,
        "decision": {
            "status": "MATERIALIZED_SMOKE_OK" if status == "OK" else "MATERIALIZATION_BLOCKED",
            "production_status": "BLOCKED",
            "primary_read": (
                "chip-flow shadow materialization smoke 可產出獨立資料；"
                "正式 replay 前仍需擴大日期/股票範圍，並與 ranking dates 對齊。"
                if status == "OK"
                else "chip-flow shadow materialization 尚未產出可用資料。"
            ),
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Chip Flow Materialized Features",
        "",
        f"- status: `{payload['status']}`",
        f"- decision: `{payload['decision']['status']}`",
        f"- production_status: `{payload['decision']['production_status']}`",
        "",
        "## Primary Read",
        "",
        payload["decision"]["primary_read"],
        "",
        "## Summary",
        "",
        f"- row_count: `{summary['row_count']}`",
        f"- stock_count: `{summary['stock_count']}`",
        f"- latest_date: `{summary['latest_date']}`",
        f"- institutional_rows: `{summary['institutional_rows']}`",
        f"- margin_rows: `{summary['margin_rows']}`",
        f"- seed_rows: `{summary.get('seed_rows', 0)}`",
        f"- seed_covered_stock_count: `{summary.get('seed_covered_stock_count', 0)}`",
        f"- fetch_stock_count: `{summary.get('fetch_stock_count', 0)}`",
        f"- cache_hits: `{summary.get('cache_hits', {})}`",
        f"- network_fetches: `{summary.get('network_fetches', {})}`",
        f"- csv: `{payload['outputs']['csv']}`",
        "",
        "## Blockers",
        "",
    ]
    lines.extend([f"- {item}" for item in payload["blockers"]] or ["- none"])
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    output_path = resolve_path(args.output)
    markdown_path = resolve_path(args.markdown_output) if args.markdown_output else output_path.with_suffix(".md")
    payload = build_payload(args)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "decision": payload["decision"]["status"],
                "output": repo_path(output_path),
                "csv": payload["outputs"]["csv"],
                "blockers": payload["blockers"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
