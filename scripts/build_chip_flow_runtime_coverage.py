#!/usr/bin/env python3
"""建立 chip-flow runtime coverage audit。

預設 static 模式只用標準函式庫檢查本地 artifact/header，不抓外部資料。
local / finmind-smoke 模式會在函式內延遲載入 pandas/FinMind，供 .venv 完整環境使用。
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
RUN_DATE = "2026-06-06"
SCHEMA_VERSION = "chip-flow-runtime-coverage.v1"


CHIP_COLUMNS = [
    "foreign_buy",
    "trust_buy",
    "dealer_buy",
    "institutional_available",
    "margin_purchase_today_balance",
    "margin_purchase_yesterday_balance",
    "margin_purchase_balance_change",
    "short_sale_today_balance",
    "short_sale_yesterday_balance",
    "short_sale_balance_change",
    "margin_available",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build chip-flow runtime coverage audit")
    parser.add_argument("--mode", choices=["static", "local", "finmind-smoke"], default="static")
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument("--stock-ids", default="2330,2317,2454")
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--output", default=f"artifacts/chip_flow_runtime_coverage_{RUN_DATE}.json")
    parser.add_argument("--markdown-output", default=None)
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def latest_ranking_file() -> Path | None:
    pattern = re.compile(r"ranking_\d{4}-\d{2}-\d{2}\.csv$")
    files = sorted([path for path in (PROJECT_ROOT / "artifacts").glob("ranking_*.csv") if pattern.match(path.name)])
    return files[-1] if files else None


def csv_header(path: Path | None) -> list[str]:
    if path is None or not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        try:
            return next(reader)
        except StopIteration:
            return []


def base_contract(mode: str) -> dict[str, Any]:
    return {
        "research_only": True,
        "coverage_audit_only": True,
        "changes_model": False,
        "changes_production_ranking": False,
        "changes_risk_adjusted_score": False,
        "does_not_send_push": True,
        "mode": mode,
    }


def static_payload(args: argparse.Namespace) -> dict[str, Any]:
    ranking_path = latest_ranking_file()
    header = csv_header(ranking_path)
    ranking_chip_cols = [col for col in CHIP_COLUMNS if col in header]
    blockers = [
        "static mode does not execute runtime FinMind fetch",
        "local Python environment lacks project data dependencies unless run through .venv/uv",
    ]
    if not ranking_chip_cols:
        blockers.append("latest production ranking exposes no chip-flow columns")
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "BLOCKED",
        "contract": base_contract(args.mode),
        "inputs": {
            "latest_ranking": repo_path(ranking_path),
            "features": args.features,
        },
        "coverage": {
            "runtime_data_checked": False,
            "latest_ranking_chip_columns": ranking_chip_cols,
            "institutional_available_rate": None,
            "margin_available_rate": None,
            "latest_asof_date": None,
            "checked_stock_count": 0,
        },
        "blockers": blockers,
        "decision": {
            "status": "RUNTIME_COVERAGE_NOT_MEASURED",
            "production_status": "BLOCKED",
            "primary_read": "目前只能確認 production ranking 尚未暴露 chip 欄位；尚未完成實際 FinMind/runtime coverage。",
        },
    }


def local_payload(args: argparse.Namespace) -> dict[str, Any]:
    import pandas as pd

    features_path = resolve_path(args.features)
    if not features_path.exists():
        raise FileNotFoundError(f"features missing: {features_path}")
    frame = pd.read_parquet(features_path)
    present_cols = [col for col in CHIP_COLUMNS if col in frame.columns]
    missing_cols = [col for col in CHIP_COLUMNS if col not in frame.columns]
    coverage: dict[str, Any] = {
        "runtime_data_checked": True,
        "features": repo_path(features_path),
        "present_chip_columns": present_cols,
        "missing_chip_columns": missing_cols,
        "checked_row_count": int(len(frame)),
        "checked_stock_count": int(frame["stock_id"].nunique()) if "stock_id" in frame.columns else None,
        "latest_asof_date": None,
        "institutional_available_rate": None,
        "margin_available_rate": None,
    }
    if "date" in frame.columns:
        coverage["latest_asof_date"] = str(pd.to_datetime(frame["date"]).max().date())
    for col, key in [
        ("institutional_available", "institutional_available_rate"),
        ("margin_available", "margin_available_rate"),
    ]:
        if col in frame.columns:
            coverage[key] = round(float(frame[col].fillna(False).astype(bool).mean()), 6)

    blockers = []
    if missing_cols:
        blockers.append("features missing chip-flow columns")
    if coverage.get("institutional_available_rate") in (None, 0):
        blockers.append("institutional runtime coverage is missing or zero")
    if coverage.get("margin_available_rate") in (None, 0):
        blockers.append("margin runtime coverage is missing or zero")
    status = "OK" if not blockers else "BLOCKED"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "contract": base_contract(args.mode),
        "inputs": {"features": repo_path(features_path)},
        "coverage": coverage,
        "blockers": blockers,
        "decision": {
            "status": "RUNTIME_COVERAGE_OK" if status == "OK" else "RUNTIME_COVERAGE_BLOCKED",
            "production_status": "BLOCKED",
            "primary_read": "本地 features coverage 已檢查；仍需 warning-only replay 才能進提醒。",
        },
    }


def finmind_smoke_payload(args: argparse.Namespace) -> dict[str, Any]:
    import pandas as pd
    from app.finmind_integrator import FinMindIntegrator

    end_date = args.end_date or datetime.now().strftime("%Y-%m-%d")
    start_date = args.start_date or end_date
    stock_ids = [item.strip() for item in args.stock_ids.split(",") if item.strip()]
    rows: list[dict[str, Any]] = []
    for stock_id in stock_ids:
        rows.append({"date": start_date, "stock_id": stock_id, "volume": 1, "close": 1})
    frame = pd.DataFrame(rows)
    integrator = FinMindIntegrator()
    result = integrator.integrate_chip_data(frame, top_n=len(stock_ids), include_margin=True)
    institutional_rate = (
        float(result["institutional_available"].fillna(False).astype(bool).mean())
        if "institutional_available" in result.columns
        else 0.0
    )
    margin_rate = (
        float(result["margin_available"].fillna(False).astype(bool).mean())
        if "margin_available" in result.columns
        else 0.0
    )
    blockers = []
    if institutional_rate == 0:
        blockers.append("FinMind institutional smoke coverage is zero")
    if margin_rate == 0:
        blockers.append("FinMind margin smoke coverage is zero")
    status = "OK" if not blockers else "BLOCKED"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "contract": {**base_contract(args.mode), "does_fetch_network_data": True},
        "inputs": {"stock_ids": stock_ids, "start_date": start_date, "end_date": end_date},
        "coverage": {
            "runtime_data_checked": True,
            "checked_stock_count": len(stock_ids),
            "institutional_available_rate": round(institutional_rate, 6),
            "margin_available_rate": round(margin_rate, 6),
            "latest_asof_date": end_date,
        },
        "blockers": blockers,
        "decision": {
            "status": "RUNTIME_COVERAGE_OK" if status == "OK" else "RUNTIME_COVERAGE_BLOCKED",
            "production_status": "BLOCKED",
            "primary_read": "FinMind smoke coverage 已檢查；正式前仍需批次 coverage 與 warning-only replay。",
        },
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.mode == "local":
        return local_payload(args)
    if args.mode == "finmind-smoke":
        return finmind_smoke_payload(args)
    return static_payload(args)


def render_markdown(payload: dict[str, Any]) -> str:
    coverage = payload.get("coverage") or {}
    lines = [
        "# Chip Flow Runtime Coverage",
        "",
        f"- status: `{payload['status']}`",
        f"- decision: `{payload['decision']['status']}`",
        f"- mode: `{payload['contract']['mode']}`",
        f"- production_status: `{payload['decision']['production_status']}`",
        "",
        "## Primary Read",
        "",
        payload["decision"]["primary_read"],
        "",
        "## Coverage",
        "",
    ]
    for key, value in coverage.items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Blockers", ""])
    lines.extend([f"- {item}" for item in payload.get("blockers") or []] or ["- none"])
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
                "markdown": repo_path(markdown_path),
                "blockers": payload.get("blockers") or [],
            },
            ensure_ascii=False,
        )
    )
    return 0 if payload["status"] in {"OK", "BLOCKED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
