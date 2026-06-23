#!/usr/bin/env python3
"""建立 borrow-squeeze shadow materialized features。

此腳本抓取或重用 `TaiwanDailyShortSaleBalances`，並 join 本地發行股數，
產出「借券賣出餘額 / 發行股數」等研究用欄位。不覆寫 production features。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

RUN_DATE = "2026-06-21"
SCHEMA_VERSION = "borrow-squeeze-materialized-features.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build borrow-squeeze shadow materialized features")
    parser.add_argument("--stock-ids", default="2379,2454,2330")
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--seed-csv", nargs="*", default=[], help="既有 normalized CSV；符合 stock/date 的資料會先重用")
    parser.add_argument("--cache-dir", default="data/raw/borrow_squeeze/cache", help="per-stock normalized cache 目錄")
    parser.add_argument("--refresh-cache", action="store_true", help="忽略 cache，重新抓取指定 stock/date")
    parser.add_argument(
        "--issued-shares-json",
        nargs="*",
        default=[],
        help="發行股數 raw JSON；未指定時使用 data/raw/reference/tradable_universe 最新目錄",
    )
    parser.add_argument("--near-cap-ratio", type=float, default=0.095)
    parser.add_argument("--cap-hit-ratio", type=float, default=0.099)
    parser.add_argument("--output-csv", default=f"data/raw/borrow_squeeze/borrow_squeeze_materialized_{RUN_DATE}.csv")
    parser.add_argument(
        "--output",
        default=f"artifacts/model_experiments/borrow_squeeze_materialized_features_{RUN_DATE}.json",
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


def normalize_stock_id(value: Any) -> str:
    return str(value).strip().zfill(4)


def expected_columns() -> list[str]:
    return [
        "date",
        "stock_id",
        "margin_short_previous_day_balance",
        "margin_short_short_sales",
        "margin_short_short_covering",
        "margin_short_stock_redemption",
        "margin_short_current_day_balance",
        "margin_short_quota",
        "sbl_short_previous_day_balance",
        "sbl_short_sales",
        "sbl_returns",
        "sbl_adjustments",
        "sbl_current_day_balance",
        "sbl_quota",
        "sbl_short_covering",
        "sbl_balance_change_from_source",
        "sbl_balance_change_1d",
        "sbl_balance_change_5d",
        "sbl_balance_change_20d",
        "issued_shares",
        "issued_shares_lots",
        "sbl_balance_lots",
        "sbl_balance_to_issued_shares",
        "sbl_near_cap_flag",
        "sbl_cap_hit_flag",
        "sbl_pressure_score",
        "borrow_squeeze_available",
    ]


def cache_path(cache_dir: Path, stock_id: str, start_date: str, end_date: str) -> Path:
    return cache_dir / f"{normalize_stock_id(stock_id)}_{start_date}_{end_date}_daily_short_sale_balances.csv"


def read_normalized_csv(path: Path) -> Any:
    import pandas as pd

    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path, parse_dates=["date"], dtype={"stock_id": str})
    if frame.empty:
        return frame
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
    if seed.empty or "sbl_current_day_balance" not in seed.columns:
        return set()
    covered = seed.dropna(subset=["sbl_current_day_balance"])
    return set(covered["stock_id"].astype(str).str.zfill(4).unique())


def latest_reference_json_paths() -> list[Path]:
    reference_root = PROJECT_ROOT / "data" / "raw" / "reference" / "tradable_universe"
    if not reference_root.exists():
        return []
    dated_dirs = sorted([path for path in reference_root.iterdir() if path.is_dir()])
    if not dated_dirs:
        return []
    latest_dir = dated_dirs[-1]
    return sorted(latest_dir.glob("*.json"))


def parse_int(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).replace(",", "").strip()
    if not text or text in {"-", "－"}:
        return None
    match = re.search(r"-?\d+", text)
    if not match:
        return None
    return int(match.group(0))


def first_text(row: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        text = str(value).replace("\u3000", " ").strip()
        if text and text != "－":
            return text
    return ""


def load_issued_shares(paths: list[str]) -> tuple[dict[str, int], list[str]]:
    source_paths = [resolve_path(path) for path in paths] if paths else latest_reference_json_paths()
    shares: dict[str, int] = {}
    used_paths: list[str] = []
    code_keys = ["公司代號", "股票代號", "證券代號", "Code", "stockNo", "SecuritiesCompanyCode"]
    share_keys = [
        "已發行普通股數或TDR原股發行股數",
        "IssuedShares",
        "issued_shares",
        "已發行普通股數",
    ]
    capital_keys = ["實收資本額", "PaidinCapital", "paid_in_capital"]
    for path in source_paths:
        if not path.exists():
            continue
        rows = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            continue
        used_paths.append(repo_path(path))
        for row in rows:
            if not isinstance(row, dict):
                continue
            stock_id = first_text(row, code_keys)
            if not stock_id or not re.fullmatch(r"\d{4}", stock_id):
                continue
            issued = None
            for key in share_keys:
                issued = parse_int(row.get(key))
                if issued is not None:
                    break
            if issued is None:
                capital = None
                for key in capital_keys:
                    capital = parse_int(row.get(key))
                    if capital is not None:
                        break
                if capital is not None:
                    issued = capital // 10
            if issued is not None and issued > 0:
                shares[normalize_stock_id(stock_id)] = issued
    return shares, used_paths


def add_borrow_squeeze_metrics(frame: Any, issued_shares: dict[str, int], near_cap_ratio: float, cap_hit_ratio: float) -> Any:
    import pandas as pd

    if frame.empty:
        return frame
    working = frame.copy()
    working["date"] = pd.to_datetime(working["date"])
    working["stock_id"] = working["stock_id"].astype(str).str.zfill(4)
    if "sbl_current_day_balance" not in working.columns:
        working["sbl_current_day_balance"] = pd.NA
    working["sbl_current_day_balance"] = pd.to_numeric(working["sbl_current_day_balance"], errors="coerce")
    working = working.sort_values(["stock_id", "date"]).copy()
    working["issued_shares"] = working["stock_id"].map(issued_shares)
    working["issued_shares"] = pd.to_numeric(working["issued_shares"], errors="coerce")
    working["issued_shares_lots"] = working["issued_shares"] / 1000
    working["sbl_balance_lots"] = working["sbl_current_day_balance"] / 1000
    working["sbl_balance_to_issued_shares"] = working["sbl_current_day_balance"] / working["issued_shares"]
    if "sbl_balance_change_1d" not in working.columns:
        working["sbl_balance_change_1d"] = pd.NA
    diff_1d = working.groupby("stock_id")["sbl_current_day_balance"].diff()
    working["sbl_balance_change_1d"] = pd.to_numeric(working["sbl_balance_change_1d"], errors="coerce").fillna(diff_1d)
    working["sbl_balance_change_5d"] = working.groupby("stock_id")["sbl_current_day_balance"].diff(5)
    working["sbl_balance_change_20d"] = working.groupby("stock_id")["sbl_current_day_balance"].diff(20)
    working["sbl_near_cap_flag"] = working["sbl_balance_to_issued_shares"] >= near_cap_ratio
    working["sbl_cap_hit_flag"] = working["sbl_balance_to_issued_shares"] >= cap_hit_ratio
    working["sbl_pressure_score"] = (working["sbl_balance_to_issued_shares"] / 0.10 * 100).clip(lower=0, upper=100).round(2)
    source_available = (
        working["borrow_squeeze_available"].fillna(False).astype(bool)
        if "borrow_squeeze_available" in working.columns
        else True
    )
    working["borrow_squeeze_available"] = source_available & working["issued_shares"].notna()
    for column in expected_columns():
        if column not in working.columns:
            working[column] = pd.NA
    return working[expected_columns()]


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    import pandas as pd
    from app.finmind_integrator import FinMindIntegrator

    stock_ids = [normalize_stock_id(item) for item in args.stock_ids.split(",") if item.strip()]
    seed = load_seed_rows(args.seed_csv, stock_ids, args.start_date, args.end_date)
    seed_covered = covered_stock_ids(seed)
    fetch_stock_ids = [stock_id for stock_id in stock_ids if stock_id not in seed_covered]
    cache_dir = resolve_path(args.cache_dir)
    frames = []
    errors: list[str] = []
    cache_hits = 0
    network_fetches = 0
    integrator = FinMindIntegrator() if fetch_stock_ids else None

    for stock_id in fetch_stock_ids:
        path = cache_path(cache_dir, stock_id, args.start_date, args.end_date)
        try:
            if path.exists() and not args.refresh_cache:
                normalized = read_normalized_csv(path)
                cache_hits += 1
            else:
                if integrator is None or integrator.fetcher is None:
                    raise RuntimeError("FinMind fetcher unavailable")
                raw = integrator.fetcher.get_daily_short_sale_balances(stock_id, args.start_date, args.end_date)
                normalized = integrator._normalize_daily_short_sale_balances(raw, stock_id)
                write_normalized_cache(path, normalized, expected_columns())
                network_fetches += 1
            if not normalized.empty:
                frames.append(normalized)
        except Exception as exc:
            errors.append(f"{stock_id}: daily short sale balances fetch failed: {exc}")

    fetched = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    materialized = fetched
    if not seed.empty:
        materialized = pd.concat([seed, materialized], ignore_index=True) if not materialized.empty else seed
        materialized = materialized.drop_duplicates(subset=["date", "stock_id"], keep="last")

    issued_shares, issued_source_paths = load_issued_shares(args.issued_shares_json)
    materialized = add_borrow_squeeze_metrics(materialized, issued_shares, args.near_cap_ratio, args.cap_hit_ratio)

    output_csv = resolve_path(args.output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    if not materialized.empty:
        materialized.to_csv(output_csv, index=False)
    else:
        output_csv.write_text("", encoding="utf-8")

    blockers = []
    if materialized.empty:
        blockers.append("materialized borrow-squeeze frame is empty")
    if not issued_shares:
        blockers.append("issued shares reference is missing")
    issued_coverage = (
        float(materialized["issued_shares"].notna().mean())
        if not materialized.empty and "issued_shares" in materialized.columns
        else 0.0
    )
    available_count = (
        int(materialized["borrow_squeeze_available"].fillna(False).astype(bool).sum())
        if not materialized.empty and "borrow_squeeze_available" in materialized.columns
        else 0
    )
    if available_count <= 0:
        blockers.append("no rows have both SBL balance and issued shares")

    status = "OK" if not blockers else "BLOCKED"
    latest_date = None
    top_pressure_rows: list[dict[str, Any]] = []
    if not materialized.empty:
        latest_date = str(pd.to_datetime(materialized["date"]).max().date())
        top = materialized.sort_values("sbl_balance_to_issued_shares", ascending=False).head(10)
        for row in top.to_dict(orient="records"):
            top_pressure_rows.append(
                {
                    "date": str(pd.to_datetime(row["date"]).date()),
                    "stock_id": row["stock_id"],
                    "sbl_balance_lots": None if pd.isna(row["sbl_balance_lots"]) else round(float(row["sbl_balance_lots"]), 3),
                    "issued_shares_lots": None if pd.isna(row["issued_shares_lots"]) else round(float(row["issued_shares_lots"]), 3),
                    "sbl_balance_to_issued_shares": (
                        None
                        if pd.isna(row["sbl_balance_to_issued_shares"])
                        else round(float(row["sbl_balance_to_issued_shares"]), 6)
                    ),
                    "sbl_pressure_score": None if pd.isna(row["sbl_pressure_score"]) else float(row["sbl_pressure_score"]),
                }
            )

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
            "source_distinguishes_sbl_from_margin_short": True,
        },
        "inputs": {
            "stock_ids": stock_ids,
            "start_date": args.start_date,
            "end_date": args.end_date,
            "near_cap_ratio": args.near_cap_ratio,
            "cap_hit_ratio": args.cap_hit_ratio,
            "issued_shares_sources": issued_source_paths,
        },
        "outputs": {
            "csv": repo_path(output_csv),
        },
        "summary": {
            "row_count": int(len(materialized)),
            "stock_count": int(materialized["stock_id"].nunique()) if not materialized.empty else 0,
            "latest_date": latest_date,
            "columns": list(materialized.columns) if not materialized.empty else [],
            "seed_rows": int(len(seed)),
            "seed_covered_stock_count": len(seed_covered),
            "fetch_stock_count": len(fetch_stock_ids),
            "fetched_rows": int(len(fetched)),
            "issued_shares_stock_count": len(issued_shares),
            "issued_shares_coverage": round(issued_coverage, 6),
            "available_rows": available_count,
            "near_cap_count": int(materialized["sbl_near_cap_flag"].fillna(False).astype(bool).sum()) if not materialized.empty else 0,
            "cap_hit_count": int(materialized["sbl_cap_hit_flag"].fillna(False).astype(bool).sum()) if not materialized.empty else 0,
            "cache_hits": cache_hits,
            "network_fetches": network_fetches,
            "top_pressure_rows": top_pressure_rows,
            "errors": errors,
        },
        "blockers": blockers,
        "decision": {
            "status": "MATERIALIZED_SMOKE_OK" if status == "OK" else "MATERIALIZATION_BLOCKED",
            "production_status": "BLOCKED",
            "primary_read": (
                "borrow-squeeze shadow materialization 已可產出借券賣出餘額 / 發行股數；"
                "下一步需與價格突破、族群轉強一起 replay，不能直接進正式排名。"
                if status == "OK"
                else "borrow-squeeze shadow materialization 尚未產出可用資料。"
            ),
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Borrow Squeeze Materialized Features",
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
        f"- issued_shares_coverage: `{summary['issued_shares_coverage']}`",
        f"- available_rows: `{summary['available_rows']}`",
        f"- near_cap_count: `{summary['near_cap_count']}`",
        f"- cap_hit_count: `{summary['cap_hit_count']}`",
        f"- seed_rows: `{summary['seed_rows']}`",
        f"- fetch_stock_count: `{summary['fetch_stock_count']}`",
        f"- cache_hits: `{summary['cache_hits']}`",
        f"- network_fetches: `{summary['network_fetches']}`",
        f"- csv: `{payload['outputs']['csv']}`",
        "",
        "## Top Pressure Rows",
        "",
    ]
    for item in summary["top_pressure_rows"][:10]:
        lines.append(
            "- {date} {stock_id}: balance_lots={balance}, issued_lots={issued}, ratio={ratio}, score={score}".format(
                date=item["date"],
                stock_id=item["stock_id"],
                balance=item["sbl_balance_lots"],
                issued=item["issued_shares_lots"],
                ratio=item["sbl_balance_to_issued_shares"],
                score=item["sbl_pressure_score"],
            )
        )
    if not summary["top_pressure_rows"]:
        lines.append("- none")
    lines.extend(["", "## Blockers", ""])
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
