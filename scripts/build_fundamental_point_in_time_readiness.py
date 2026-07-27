#!/usr/bin/env python3
"""建立 Fundamental point-in-time 研究資料 readiness artifact。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.modeling.feature_contract import FUNDAMENTAL_FEATURE_COLUMNS  # noqa: E402
from scripts.research_feature_group_ablation_by_regime import load_frame  # noqa: E402
from scripts.research_feature_group_regime_walkforward import apply_research_universe  # noqa: E402


SCHEMA_VERSION = "fundamental-point-in-time-readiness.v1"
DEFAULT_OUTPUT = PROJECT_ROOT / "docs/evidence/RESEARCH-FUNDAMENTAL-READINESS-01/artifact.json"
REGIME_PATH = PROJECT_ROOT / "artifacts/model_experiments/market_regime_history_append_only_2026-07-22.json"
INDUSTRY_PATH = PROJECT_ROOT / "data/reference/stock_industry_map.csv"
HOLDING_HORIZON = 10


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cache_manifest(cache_dir: Path) -> tuple[int, str]:
    files = sorted(cache_dir.glob("*.json"))
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return len(files), digest.hexdigest()


def distribution(series: pd.Series) -> dict[str, float]:
    return {
        "min": round(float(series.min()), 6),
        "median": round(float(series.median()), 6),
        "max": round(float(series.max()), 6),
    }


def build_payload() -> dict[str, Any]:
    frame, _, contract = load_frame(
        PROJECT_ROOT / "data/clean",
        REGIME_PATH,
        INDUSTRY_PATH,
    )
    feature_stocks = int(frame["stock_id"].nunique())
    available = frame[list(FUNDAMENTAL_FEATURE_COLUMNS)].notna().any(axis=1)
    usable_stocks = int(frame.loc[available, "stock_id"].nunique())
    cache_files, cache_sha = cache_manifest(PROJECT_ROOT / "data/fundamentals")

    universe, universe_receipt = apply_research_universe(
        frame,
        mode="point-in-time-liquidity",
        liquidity_top_n=200,
    )
    universe = universe.copy()
    universe["fundamental_available"] = universe[list(FUNDAMENTAL_FEATURE_COLUMNS)].notna().any(axis=1)
    daily = (
        universe.groupby("trade_date", sort=True)
        .agg(
            selected_stocks=("stock_id", "nunique"),
            available_stocks=("fundamental_available", "sum"),
        )
        .reset_index()
    )
    daily["coverage"] = daily["available_stocks"] / daily["selected_stocks"]
    # D+10 標籤尚未成熟的最近十個交易日不得進 readiness 判定。
    mature = daily.iloc[:-HOLDING_HORIZON].copy()
    recent = mature.tail(252).copy()
    research_ready = bool(
        len(recent) == 252
        and (recent["available_stocks"] >= 30).all()
        and (recent["coverage"] >= 0.70).all()
    )
    model_coverage = usable_stocks / feature_stocks if feature_stocks else 0.0
    decision = "READY_FOR_POINT_IN_TIME_RESEARCH" if research_ready and model_coverage >= 0.80 else "BLOCKED_DATA_COVERAGE"
    latest = daily.iloc[-1]
    warnings = []
    if model_coverage < 0.80:
        warnings.append(
            {
                "record": "fundamental-cache",
                "reason_code": "FUNDAMENTAL_CACHE_COVERAGE_BELOW_MODEL_GATE",
                "stage": "readiness",
                "impact_count": feature_stocks - usable_stocks,
            }
        )
    failing_days = recent[(recent["available_stocks"] < 30) | (recent["coverage"] < 0.70)]
    if len(failing_days):
        warnings.append(
            {
                "record": "recent-252-trade-days",
                "reason_code": "POINT_IN_TIME_DAILY_COVERAGE_BELOW_RESEARCH_GATE",
                "stage": "readiness",
                "impact_count": int(len(failing_days)),
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "OK",
        "decision": decision,
        "as_of_date": str(pd.Timestamp(daily["trade_date"].max()).date()),
        "source_and_grain": "data/clean stock_id × trade_date + quarterly/annual fundamental cache as-of join",
        "inputs": {
            "features": "data/clean/features.parquet",
            "features_sha256": file_sha256(PROJECT_ROOT / "data/clean/features.parquet"),
            "regime_history": str(REGIME_PATH.relative_to(PROJECT_ROOT)),
            "regime_history_sha256": file_sha256(REGIME_PATH),
            "fundamental_cache_dir": "data/fundamentals",
            "fundamental_cache_files": cache_files,
            "fundamental_cache_manifest_sha256": cache_sha,
        },
        "coverage": {
            "feature_stocks": feature_stocks,
            "usable_fundamental_stocks": usable_stocks,
            "usable_stock_coverage": round(model_coverage, 6),
            "latest_point_in_time_top200": {
                "selected_stocks": int(latest["selected_stocks"]),
                "available_stocks": int(latest["available_stocks"]),
                "coverage": round(float(latest["coverage"]), 6),
            },
            "recent_252_trade_days": {
                "days": int(len(recent)),
                "start_date": str(pd.Timestamp(recent["trade_date"].min()).date()),
                "end_date": str(pd.Timestamp(recent["trade_date"].max()).date()),
                "available_stock_count": distribution(recent["available_stocks"]),
                "coverage": distribution(recent["coverage"]),
                "days_meeting_research_gate": int(
                    ((recent["available_stocks"] >= 30) & (recent["coverage"] >= 0.70)).sum()
                ),
            },
        },
        "gates": {
            "research_min_daily_stocks": 30,
            "research_min_daily_coverage": 0.70,
            "research_required_trade_days": 252,
            "holding_horizon_trade_days": HOLDING_HORIZON,
            "model_min_stock_coverage": 0.80,
        },
        "source_contract": contract,
        "universe_receipt": universe_receipt,
        "warnings_and_exclusions": warnings,
        "selection_bias_note": "低 coverage cache 並非隨機樣本；既有 IC／spread 不可外推至完整 universe。",
        "promotion_allowed": False,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    coverage = payload["coverage"]
    latest = coverage["latest_point_in_time_top200"]
    recent = coverage["recent_252_trade_days"]
    return "\n".join(
        [
            "# Fundamental Point-in-time Readiness",
            "",
            f"- decision：`{payload['decision']}`",
            f"- as of：`{payload['as_of_date']}`",
            f"- usable stocks：`{coverage['usable_fundamental_stocks']}/{coverage['feature_stocks']}`",
            f"- usable stock coverage：`{coverage['usable_stock_coverage']:.2%}`",
            f"- latest Top200 coverage：`{latest['available_stocks']}/{latest['selected_stocks']}`（`{latest['coverage']:.2%}`）",
            f"- recent 252 days meeting research gate：`{recent['days_meeting_research_gate']}/{recent['days']}`",
            "- promotion allowed：`false`",
            "",
            "低 coverage cache 並非隨機樣本；既有正向 IC／spread 不可當作完整 universe 選股結論。",
            "",
        ]
    )


def main() -> int:
    output = DEFAULT_OUTPUT
    payload = build_payload()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "decision": payload["decision"],
                "output": str(output.relative_to(PROJECT_ROOT)),
                "usable_stock_coverage": payload["coverage"]["usable_stock_coverage"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
