#!/usr/bin/env python3
"""依盤勢切換 production / shadow ranking。

用途：研究 BIG_BULL-only 接法。BIG_BULL 日期使用 shadow/candidate ranking，
其他日期保留 production ranking。輸出獨立 ranking 目錄，不修改 production。
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_high_choppy_context_overlay import load_regime_frame  # noqa: E402
from scripts.research_regime_family_training_candidates import is_big_bull  # noqa: E402


SCHEMA_VERSION = "regime-conditional-shadow-ranking.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build regime conditional shadow rankings")
    parser.add_argument("--production-dir", required=True)
    parser.add_argument("--shadow-dir", required=True)
    parser.add_argument("--market-regime-history", default="artifacts/market_regime_history_2026-06-01.json")
    parser.add_argument("--active-family", default="BIG_BULL")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--top-n", type=int, default=10)
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def ranking_dates(path: Path) -> list[str]:
    return sorted(item.stem.removeprefix("ranking_") for item in path.glob("ranking_*.csv"))


def read_ranking(path: Path, top_n: int) -> pd.DataFrame:
    frame = pd.read_csv(path, encoding="utf-8-sig").head(top_n).copy()
    frame["stock_id"] = frame["stock_id"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(4)
    return frame


def write_ranking(path: Path, frame: pd.DataFrame, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    output = frame.copy().reset_index(drop=True)
    output["rank"] = range(1, len(output) + 1)
    output["regime_conditional_source"] = source
    output.to_csv(path, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_MINIMAL)


def active_dates(path: Path, family: str) -> set[str]:
    if family != "BIG_BULL":
        raise ValueError(f"unsupported active family: {family}")
    frame = load_regime_frame(path)
    frame["BIG_BULL"] = frame.apply(is_big_bull, axis=1)
    return {str(row.trade_date_text) for row in frame.itertuples(index=False) if bool(row.BIG_BULL)}


def build(args: argparse.Namespace) -> dict[str, Any]:
    production_dir = resolve_path(args.production_dir)
    shadow_dir = resolve_path(args.shadow_dir)
    output_dir = resolve_path(args.output_dir)
    regime_path = resolve_path(args.market_regime_history)
    dates = sorted(set(ranking_dates(production_dir)) & set(ranking_dates(shadow_dir)))
    active = active_dates(regime_path, args.active_family)
    rows = []
    outputs = []
    for date_text in dates:
        use_shadow = date_text in active
        source_dir = shadow_dir if use_shadow else production_dir
        source = "shadow_active_family" if use_shadow else "production_inactive_family"
        frame = read_ranking(source_dir / f"ranking_{date_text}.csv", args.top_n)
        output_path = output_dir / f"ranking_{date_text}.csv"
        write_ranking(output_path, frame, source)
        outputs.append(repo_path(output_path))
        rows.append({"date": date_text, "source": source, "active_family": bool(use_shadow)})
    shadow_count = sum(1 for row in rows if row["source"] == "shadow_active_family")
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "contract": {
            "research_only": True,
            "trains_model": False,
            "modifies_production_ranking": False,
            "active_family": args.active_family,
            "inactive_family_source": "production",
        },
        "inputs": {
            "production_dir": repo_path(production_dir),
            "shadow_dir": repo_path(shadow_dir),
            "market_regime_history": repo_path(regime_path),
            "output_dir": repo_path(output_dir),
            "top_n": args.top_n,
        },
        "summary": {
            "date_count": len(rows),
            "shadow_active_family_count": shadow_count,
            "production_inactive_family_count": len(rows) - shadow_count,
        },
        "rows": rows,
        "outputs": outputs,
    }


def main() -> int:
    args = parse_args()
    payload = build(args)
    output_dir = resolve_path(args.output_dir)
    summary_path = output_dir / "regime_conditional_shadow_ranking.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": "OK", "summary": repo_path(summary_path), **payload["summary"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
