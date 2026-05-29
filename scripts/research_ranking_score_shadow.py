#!/usr/bin/env python3
"""產生 ranking score shadow artifacts，測試規則分數是否拖累 replay。

此腳本不訓練模型、不修改 production config。它只用同一顆模型與同一批日期，
改變 decision-layer score 後輸出 shadow ranking CSV，供 replay 比較。
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

from app.agent_b_ranking import StockRanker  # noqa: E402
from app.stock_names import get_stock_name  # noqa: E402


SCHEMA_VERSION = "ranking-score-shadow.v1"
OUT_COLS = [
    "stock_id",
    "stock_name",
    "close",
    "risk_adjusted_score",
    "final_score",
    "model_prob",
    "rule_score",
    "prediction_score",
    "setup_score",
    "quality_score",
    "risk_penalty",
    "suggested_weight",
    "max_position_weight",
    "gross_exposure",
    "allocated_exposure",
    "cash_weight",
    "exposure_note",
    "risk_reward",
    "market_regime",
    "reasons",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build shadow ranking CSVs with alternate score formula")
    parser.add_argument("--dates-from-dir", required=True, help="讀取此目錄的 ranking_YYYY-MM-DD.csv 日期")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--variant",
        choices=["no_setup", "conservative_setup", "model_only"],
        default="no_setup",
    )
    parser.add_argument("--limit", type=int, default=None)
    return parser.parse_args()


def resolve_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def ranking_dates(path: Path, limit: int | None) -> list[str]:
    dates = []
    for file_path in sorted(path.glob("ranking_*.csv")):
        name = file_path.name
        if len(name) == len("ranking_YYYY-MM-DD.csv"):
            dates.append(name.removeprefix("ranking_").removesuffix(".csv"))
    return dates[-limit:] if limit else dates


def apply_shadow_score(frame: pd.DataFrame, variant: str) -> pd.DataFrame:
    df = frame.copy()
    prediction = pd.to_numeric(df["prediction_score"], errors="coerce").fillna(0.5)
    setup = pd.to_numeric(df["setup_score"], errors="coerce").fillna(0.0)
    quality = pd.to_numeric(df["quality_score"], errors="coerce").fillna(0.5)
    risk = pd.to_numeric(df["risk_penalty"], errors="coerce").fillna(0.0)

    if variant == "model_only":
        score = prediction
    elif variant == "conservative_setup":
        score = prediction + (0.25 * setup) + quality - risk
    else:
        score = prediction + quality - risk

    df["risk_adjusted_score"] = score.clip(lower=0)
    df["shadow_variant"] = variant
    return df.sort_values("risk_adjusted_score", ascending=False)


def ensure_names(frame: pd.DataFrame) -> pd.DataFrame:
    df = frame.copy()
    if "stock_name" not in df.columns:
        df["stock_name"] = ""
    missing = df["stock_name"].isna() | (df["stock_name"].astype(str).str.strip() == "")
    if missing.any():
        df.loc[missing, "stock_name"] = [get_stock_name(str(stock_id)) for stock_id in df.loc[missing, "stock_id"]]
    return df


def write_ranking(path: Path, frame: pd.DataFrame) -> None:
    cols = [col for col in OUT_COLS if col in frame.columns]
    path.parent.mkdir(parents=True, exist_ok=True)
    frame[cols].to_csv(path, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_MINIMAL)


def build_shadow(args: argparse.Namespace) -> dict[str, Any]:
    source_dir = resolve_path(args.dates_from_dir)
    output_dir = resolve_path(args.output_dir)
    dates = ranking_dates(source_dir, args.limit)
    if not dates:
        raise FileNotFoundError(f"找不到 ranking_*.csv 日期：{source_dir}")

    ranker = StockRanker(artifact_dir=str(output_dir))
    ranker.load_model()
    ranker._enrich_with_shap = lambda df, top_n=20: df

    outputs = []
    for date_text in dates:
        daily, history = ranker.load_daily_data(date_text)
        if daily.empty:
            raise ValueError(f"{date_text} 無 ranking 資料")
        base = ranker.calculate_scores(daily)
        regime = ranker.market_regime_service.evaluate(history, target_date=base["date"].max() if "date" in base else None)
        scored = ranker.ranking_policy.apply(base, regime)
        shadow = apply_shadow_score(scored, args.variant).head(10).copy()
        shadow = ranker.portfolio_policy.apply(shadow, regime)
        shadow = ensure_names(shadow)
        out_path = output_dir / f"ranking_{date_text}.csv"
        write_ranking(out_path, shadow)
        outputs.append(str(out_path))
        print(f"SHADOW_RANKING {args.variant} {date_text} {out_path}")

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "contract": {
            "research_only": True,
            "trains_model": False,
            "modifies_production_config": False,
            "variant": args.variant,
        },
        "inputs": {
            "dates_from_dir": str(source_dir),
            "output_dir": str(output_dir),
            "date_count": len(dates),
            "dates": dates,
        },
        "outputs": outputs,
    }


def main() -> int:
    args = parse_args()
    payload = build_shadow(args)
    output_dir = resolve_path(args.output_dir)
    summary_path = output_dir / f"ranking_score_shadow_{args.variant}.json"
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"status": "OK", "summary": str(summary_path), "ranking_count": len(payload["outputs"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
