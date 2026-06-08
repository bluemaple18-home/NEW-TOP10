#!/usr/bin/env python3
"""建立 shadow alpha 候選因子表。

輸出只寫到 artifacts/model_experiments/，不覆蓋 production features、不訓練模型、不改排名。
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.modeling.factor_registry import factor_definition_for_column


OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "model_experiments"
SCHEMA_VERSION = "alpha-candidate-features.v1"
ALPHA_COLUMNS = (
    "alpha_trend_stack_score",
    "alpha_breakout_volume_confirm",
    "alpha_volatility_compression_rank",
    "alpha_pullback_to_trend",
    "alpha_liquidity_rank",
)
REQUIRED_COLUMNS = (
    "date",
    "stock_id",
    "close",
    "ma5",
    "ma20",
    "ma60",
    "rsi",
    "bias_20",
    "break_20d_high",
    "volume_ratio_20d",
    "bb_width",
    "avg_value_20d",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build shadow alpha candidate features")
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _safe_numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(frame[column], errors="coerce")


def _date_rank(values: pd.Series, dates: pd.Series, *, ascending: bool = True) -> pd.Series:
    ranked = values.groupby(dates).rank(method="average", pct=True, ascending=ascending)
    return ranked.astype("Float64")


def compute_alpha_candidates(features: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in REQUIRED_COLUMNS if column not in features.columns]
    if missing:
        raise ValueError(f"features 缺少必要欄位：{missing}")

    frame = features[list(REQUIRED_COLUMNS)].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    if frame["date"].isna().any():
        raise ValueError("features date 欄位含不可解析日期")
    frame["stock_id"] = frame["stock_id"].astype(str).str.strip()
    frame = frame.sort_values(["date", "stock_id"]).copy()
    if frame.duplicated(["date", "stock_id"]).any():
        raise ValueError("features 含同股同交易日多筆資料，請先聚合成日頻資料")

    close = _safe_numeric(frame, "close")
    ma5 = _safe_numeric(frame, "ma5")
    ma20 = _safe_numeric(frame, "ma20")
    ma60 = _safe_numeric(frame, "ma60")
    rsi = _safe_numeric(frame, "rsi")
    bias_20 = _safe_numeric(frame, "bias_20")
    break_20d_high = _safe_numeric(frame, "break_20d_high").fillna(0)
    volume_ratio_20d = _safe_numeric(frame, "volume_ratio_20d")
    bb_width = _safe_numeric(frame, "bb_width")
    avg_value_20d = _safe_numeric(frame, "avg_value_20d")

    output = frame[["date", "stock_id"]].copy()
    output["alpha_trend_stack_score"] = (
        (close > ma20).astype("Int64")
        + (ma5 > ma20).astype("Int64")
        + (ma20 > ma60).astype("Int64")
    ).astype("Float64")
    output["alpha_breakout_volume_confirm"] = (
        break_20d_high.clip(lower=0, upper=1) * volume_ratio_20d.clip(lower=0, upper=3)
    ).astype("Float64")
    output["alpha_volatility_compression_rank"] = _date_rank(bb_width, frame["date"], ascending=False)
    output["alpha_pullback_to_trend"] = (
        (close > ma60)
        & rsi.between(40, 58, inclusive="both")
        & bias_20.between(-6, 3, inclusive="both")
    ).astype("Float64")
    output["alpha_liquidity_rank"] = _date_rank(np.log1p(avg_value_20d.clip(lower=0)), frame["date"], ascending=True)
    return output


def alpha_metadata(frame: pd.DataFrame, args: argparse.Namespace, output: Path) -> dict[str, Any]:
    latest_date = frame["date"].max()
    latest = frame[frame["date"] == latest_date]
    factor_definitions = {
        column: {
            **factor_definition_for_column(column, "alpha_candidate").__dict__,
            "formula_scope": "same-row daily features; rolling columns are precomputed from historical windows",
        }
        for column in ALPHA_COLUMNS
    }
    coverage = {column: round(float(frame[column].notna().mean()), 4) for column in ALPHA_COLUMNS}
    latest_coverage = {column: round(float(latest[column].notna().mean()), 4) for column in ALPHA_COLUMNS}
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "contract": {
            "materializer_only": True,
            "shadow_only": True,
            "uses_future_columns": False,
            "uses_labels_or_targets": False,
            "does_not_write_production_features": True,
            "does_not_train_model": True,
            "does_not_change_production_ranking": True,
            "production_promotion_allowed": False,
        },
        "inputs": {
            "features": repo_path(resolve_path(args.features)),
            "required_columns": list(REQUIRED_COLUMNS),
        },
        "output": repo_path(output),
        "summary": {
            "rows": int(len(frame)),
            "stocks": int(frame["stock_id"].nunique()),
            "dates": int(frame["date"].nunique()),
            "start_date": str(frame["date"].min().date()),
            "end_date": str(frame["date"].max().date()),
            "columns": ["date", "stock_id", *ALPHA_COLUMNS],
            "coverage": coverage,
            "latest_coverage": latest_coverage,
        },
        "factors": factor_definitions,
    }


def render_markdown(metadata: dict[str, Any]) -> str:
    summary = metadata["summary"]
    lines = [
        "# Alpha Candidate Features",
        "",
        f"- rows：`{summary['rows']}`",
        f"- stocks：`{summary['stocks']}`",
        f"- dates：`{summary['dates']}`",
        f"- window：`{summary['start_date']}` to `{summary['end_date']}`",
        f"- production_promotion_allowed：`{metadata['contract']['production_promotion_allowed']}`",
        "",
        "| Factor | Coverage | Latest Coverage |",
        "|---|---:|---:|",
    ]
    for column in ALPHA_COLUMNS:
        lines.append(f"| {column} | {summary['coverage'][column]:.1%} | {summary['latest_coverage'][column]:.1%} |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    features_path = resolve_path(args.features)
    features = pd.read_parquet(features_path, columns=list(REQUIRED_COLUMNS))
    frame = compute_alpha_candidates(features)
    output = resolve_path(args.output) if args.output else OUTPUT_DIR / f"alpha_candidate_features_{args.date}.parquet"
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(output, index=False)
    metadata = alpha_metadata(frame, args=args, output=output)
    output.with_suffix(".json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(metadata), encoding="utf-8")
    print(json.dumps({"status": "OK", "output": repo_path(output), **metadata["summary"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
