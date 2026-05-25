#!/usr/bin/env python3
"""小批驗證真實 universe 接入 ETL 重建路徑。

這支腳本只輸出 probe artifact，不覆蓋 `data/clean/features.parquet`、
`events.parquet` 或 `universe.parquet`。
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import argparse
import json
from pathlib import Path
import sys
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.data.reference_repository import ReferenceRepository
from app.data_fetcher import DataFetcherOrchestrator
from app.event_detector import EventDetector
from app.indicators import TechnicalIndicators
from app.risk_filter import RiskFilter
from app.volume_indicators import VolumeIndicators


REQUIRED_FEATURE_COLUMNS = {
    "date",
    "stock_id",
    "stock_name",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "avg_value_20d",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe real tradable universe rebuild without overwriting clean outputs")
    parser.add_argument("--limit", type=int, default=20, help="Total sample stocks, split across TWSE/TPEx when possible")
    parser.add_argument("--days", type=int, default=35, help="Calendar days to fetch for rolling/liquidity probe")
    parser.add_argument("--end-date", default=None, help="YYYY-MM-DD; default is previous calendar day")
    parser.add_argument("--output", default="artifacts/universe_rebuild_probe.json")
    parser.add_argument("--artifact-dir", default="artifacts/universe_rebuild_probe")
    args = parser.parse_args()

    current = inspect_current_outputs()
    sample_ids = select_sample_ids(limit=args.limit)
    date_window = resolve_window(days=args.days, end_date=args.end_date)
    probe = run_probe(
        sample_ids=sample_ids,
        start_date=date_window["start_date"],
        end_date=date_window["end_date"],
        artifact_dir=PROJECT_ROOT / args.artifact_dir,
    )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "current_outputs": current,
        "tradable_universe": inspect_tradable_universe(),
        "sample_ids": sample_ids,
        "probe_window": date_window,
        "probe": probe,
        "entry_points": {
            "daily_runner": "scripts/run_daily.sh -> python -m scripts.run_automation daily",
            "automation": "scripts/run_automation.py:_run_daily",
            "pipeline": "app.pipeline_cli: build_pipeline()",
            "stages": [
                "FetchStage",
                "IndicatorStage",
                "FundamentalStage",
                "EventStage",
                "FilterStage",
                "ReportStage",
            ],
            "ranking": "app.agent_b_ranking.StockRanker.load_daily_data",
        },
        "rebuild_plan": rebuild_plan(probe),
    }

    output_path = PROJECT_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"universe_rebuild_probe={output_path}")
    print(
        "probe_status="
        f"{probe['status']} sample={len(sample_ids)} raw_rows={probe.get('raw_rows', 0)} "
        f"feature_rows={probe.get('feature_rows', 0)} universe_rows={probe.get('universe_rows', 0)}"
    )
    return 0 if probe["status"] in {"OK", "PARTIAL"} else 1


def inspect_current_outputs() -> dict[str, Any]:
    clean_dir = PROJECT_ROOT / "data" / "clean"
    result: dict[str, Any] = {}
    for name in ["features", "events", "universe"]:
        path = clean_dir / f"{name}.parquet"
        if not path.exists():
            result[name] = {"exists": False}
            continue
        df = pd.read_parquet(path)
        stock_ids = sorted(df["stock_id"].astype(str).str.strip().unique().tolist()) if "stock_id" in df.columns else []
        result[name] = {
            "exists": True,
            "path": str(path),
            "rows": int(len(df)),
            "columns": int(len(df.columns)),
            "stocks": int(len(stock_ids)),
            "first_stock_id": stock_ids[0] if stock_ids else None,
            "last_stock_id": stock_ids[-1] if stock_ids else None,
            "looks_like_1101_1200_fixture": stock_ids == [str(stock_id) for stock_id in range(1101, 1201)],
            "start_date": str(pd.to_datetime(df["date"]).min()) if "date" in df.columns and not df.empty else None,
            "end_date": str(pd.to_datetime(df["date"]).max()) if "date" in df.columns and not df.empty else None,
        }
    return result


def inspect_tradable_universe() -> dict[str, Any]:
    repository = ReferenceRepository(PROJECT_ROOT)
    response = repository.tradable_universe()
    by_market: dict[str, int] = {}
    for item in response.items:
        by_market[item.market_type] = by_market.get(item.market_type, 0) + 1
    return {
        "available": response.available,
        "stocks": len(response.items),
        "by_market": by_market,
        "path": str(repository.tradable_universe_path),
    }


def select_sample_ids(limit: int) -> list[str]:
    repository = ReferenceRepository(PROJECT_ROOT)
    universe = repository.tradable_universe(active_only=True, include_etfs=False).items
    twse = [item.stock_id for item in universe if item.market_type == "twse"]
    tpex = [item.stock_id for item in universe if item.market_type == "tpex"]
    left = max(limit, 1)
    tpex_take = min(len(tpex), left // 2)
    twse_take = min(len(twse), left - tpex_take)
    selected = [*twse[:twse_take], *tpex[:tpex_take]]
    if len(selected) < left:
        selected.extend([item.stock_id for item in universe if item.stock_id not in set(selected)][: left - len(selected)])
    return selected[:left]


def resolve_window(days: int, end_date: str | None) -> dict[str, str]:
    end = pd.to_datetime(end_date).date() if end_date else (datetime.now() - timedelta(days=1)).date()
    start = end - timedelta(days=max(days, 1) - 1)
    return {"start_date": start.isoformat(), "end_date": end.isoformat(), "days": str(days)}


def run_probe(sample_ids: list[str], start_date: str, end_date: str, artifact_dir: Path) -> dict[str, Any]:
    if not sample_ids:
        return {"status": "FAILED", "error": "tradable universe sample is empty"}
    try:
        orchestrator = DataFetcherOrchestrator(data_dir=str(PROJECT_ROOT / "data" / "raw" / "universe_rebuild_probe"))
        raw = orchestrator.fetch_historical_data(start_date=start_date, end_date=end_date)
        if raw.empty:
            return {"status": "FAILED", "error": "fetch_historical_data returned empty"}
        raw["stock_id"] = raw["stock_id"].astype(str).str.strip()
        sample = raw[raw["stock_id"].isin(sample_ids)].copy()
        if sample.empty:
            return {
                "status": "FAILED",
                "error": "sample ids were not present in fetched market data",
                "raw_rows": int(len(raw)),
                "raw_stocks": int(raw["stock_id"].nunique()),
            }

        features = TechnicalIndicators(sample).calculate_all_indicators()
        features = VolumeIndicators(features).calculate_all_volume_indicators()
        events = EventDetector(features).detect_all_events()
        universe = RiskFilter(features).apply_all_filters(
            suspended_list=[],
            min_listing_days=min(20, max(1, features["date"].nunique() // 2)),
            min_avg_value=10_000_000,
            min_price=10.0,
        )
        artifact_dir.mkdir(parents=True, exist_ok=True)
        features_path = artifact_dir / "features.parquet"
        events_path = artifact_dir / "events.parquet"
        universe_path = artifact_dir / "universe.parquet"
        features.to_parquet(features_path, index=False)
        events.to_parquet(events_path, index=False)
        universe.to_parquet(universe_path, index=False)
        missing_required = sorted(REQUIRED_FEATURE_COLUMNS - set(features.columns))
        present_sample_ids = sorted(features["stock_id"].astype(str).str.strip().unique().tolist())
        missing_sample_ids = sorted(set(sample_ids) - set(present_sample_ids))
        market_counts = features.groupby("market")["stock_id"].nunique().to_dict() if "market" in features.columns else {}
        status = "OK" if not missing_required and not missing_sample_ids and len(features) > 0 else "PARTIAL"
        return {
            "status": status,
            "raw_rows": int(len(raw)),
            "raw_stocks": int(raw["stock_id"].nunique()),
            "feature_rows": int(len(features)),
            "feature_stocks": int(features["stock_id"].nunique()),
            "features_path": str(features_path),
            "present_sample_ids": present_sample_ids,
            "missing_sample_ids": missing_sample_ids,
            "market_stock_counts": {str(key): int(value) for key, value in market_counts.items()},
            "event_rows": int(len(events)),
            "event_columns": int(len(events.columns)),
            "events_path": str(events_path),
            "universe_rows": int(len(universe)),
            "universe_stocks": int(universe["stock_id"].nunique()) if not universe.empty else 0,
            "universe_path": str(universe_path),
            "missing_required_columns": missing_required,
            "feature_columns": list(features.columns),
            "date_min": str(features["date"].min()),
            "date_max": str(features["date"].max()),
            "notes": [
                "Probe 僅驗證小批 schema / fetch / event / filter 路徑，不覆蓋正式 clean parquet。",
                "短日期窗無法完整代表 60 日上市天數與長週期指標，正式重建仍需較長窗口。",
            ],
        }
    except Exception as exc:
        return {"status": "FAILED", "error": f"{type(exc).__name__}: {exc}"}


def rebuild_plan(probe: dict[str, Any]) -> dict[str, Any]:
    missing_sample_ids = probe.get("missing_sample_ids", [])
    can_full_rebuild = probe.get("status") == "OK" and probe.get("feature_rows", 0) > 0
    return {
        "can_enter_full_rebuild": can_full_rebuild,
        "do_not_overwrite_before_backup": True,
        "recommended_steps": [
            "先備份 data/clean/features.parquet、events.parquet、universe.parquet 與 latest ranking artifact。",
            "用 app.pipeline_cli run 重跑完整日期窗，讓 FetchStage 從 TWSE/TPEx 全市場資料建立 features。",
            "跑 app.pipeline_cli validate、scripts/verify_data_contracts.py、scripts/verify_model_foundation.py。",
            "再跑 UQ-04 fundamental shadow score，確認 coverage / IC / ranking sensitivity。",
        ],
        "known_risks": [
            f"Probe missing sample ids: {missing_sample_ids}" if missing_sample_ids else "Probe sample fully present.",
            "FundamentalStage 已禁止缺資料時產生 dummy revenue；月營收真實匯入仍需另卡補齊。",
            "全量重建會打 TWSE/TPEx 日行情 API，需控制日期窗與請求速率。",
        ],
    }


if __name__ == "__main__":
    raise SystemExit(main())
