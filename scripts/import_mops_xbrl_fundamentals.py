"""以 MOPS 官方季度 XBRL 整批檔回填基本面 cache。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.data.fundamental_repository import FundamentalRepository
from app.fundamentals.mops_xbrl import (
    build_cache_payload,
    completed_periods,
    download_xbrl_zip,
    parse_xbrl_zip,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Import MOPS quarterly XBRL fundamentals")
    parser.add_argument("--start-period", default="2024Q4")
    parser.add_argument("--end-period", default="2026Q1")
    parser.add_argument("--features-path", default="data/clean/features.parquet")
    parser.add_argument("--download-dir", default="data/fundamental_xbrl")
    parser.add_argument("--summary-path", default="artifacts/mops_xbrl_import_summary.json")
    args = parser.parse_args()

    features_path = PROJECT_ROOT / args.features_path
    universe = _stock_universe(features_path)
    periods = completed_periods(args.start_period, args.end_period)
    records: dict[str, list[dict]] = {}
    period_results = []

    for period in periods:
        zip_path = download_xbrl_zip(period, PROJECT_ROOT / args.download_dir)
        parsed = parse_xbrl_zip(zip_path, universe=universe)
        for stock_id, metric in parsed.items():
            records.setdefault(stock_id, []).append(metric)
        period_results.append(
            {
                "period": period,
                "zip_path": str(zip_path.relative_to(PROJECT_ROOT)),
                "matched_stocks": len(parsed),
            }
        )
        print(f"MOPS_XBRL_PERIOD period={period} matched={len(parsed)}")

    repository = FundamentalRepository(PROJECT_ROOT)
    for stock_id, metrics in records.items():
        repository.write_cached(
            stock_id,
            build_cache_payload(stock_id, metrics=metrics, source_periods=periods),
        )

    covered = len(records)
    summary = {
        "source": "MOPS XBRL",
        "periods": periods,
        "universe_stocks": len(universe),
        "covered_stocks": covered,
        "coverage": round(covered / len(universe), 4) if universe else 0.0,
        "period_results": period_results,
        "availability_policy": "statutory_conservative",
        "revision_limit": "官方整批檔可能反映後續更補正版本，不是逐版本歷史快照。",
    }
    summary_path = PROJECT_ROOT / args.summary_path
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        "MOPS_XBRL_IMPORT "
        f"covered={covered}/{len(universe)} coverage={summary['coverage']:.2%} "
        f"summary={summary_path}"
    )
    return 0 if summary["coverage"] >= 0.8 else 2


def _stock_universe(features_path: Path) -> set[str]:
    if not features_path.exists():
        raise FileNotFoundError(f"找不到 features：{features_path}")
    features = pd.read_parquet(features_path, columns=["stock_id"])
    return set(features["stock_id"].astype(str).str.strip().unique())


if __name__ == "__main__":
    raise SystemExit(main())
