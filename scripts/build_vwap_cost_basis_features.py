#!/usr/bin/env python3
"""建立 VWAP / 成本線 research-only 候選特徵。

輸出只寫到 artifacts/model_experiments/，不覆蓋 production features、
不訓練模型、不改 ranking。第一步先驗證 `value / volume` 單位是否可用；
若不可用，仍保留 rolling close-volume proxy 供研究比對。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.volume_indicators import VolumeIndicators  # noqa: E402

OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "model_experiments"
SCHEMA_VERSION = "vwap-cost-basis-features.v1"
VWAP_COLUMNS = (
    "daily_vwap",
    "rolling_vwap_5d",
    "rolling_vwap_20d",
    "close_vs_vwap_5d",
    "close_vs_vwap_20d",
    "vwap_reclaim_20d",
    "vwap_loss_20d",
)
REQUIRED_COLUMNS = ("date", "stock_id", "open", "high", "low", "close", "volume", "value")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build VWAP cost-basis research-only features")
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


def compute_vwap_cost_basis(features: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    missing = [column for column in REQUIRED_COLUMNS if column not in features.columns]
    if missing:
        raise ValueError(f"features 缺少必要欄位：{missing}")

    frame = features[list(REQUIRED_COLUMNS)].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    if frame["date"].isna().any():
        raise ValueError("features date 欄位含不可解析日期")
    frame["stock_id"] = frame["stock_id"].astype(str).str.strip()
    frame = frame.sort_values(["stock_id", "date"]).copy()
    if frame.duplicated(["date", "stock_id"]).any():
        raise ValueError("features 含同股同交易日多筆資料，請先聚合成日頻資料")

    volume_indicators = VolumeIndicators(frame)
    calculated = volume_indicators.calculate_vwap_cost_basis(periods=[5, 20])
    output = calculated[["date", "stock_id", *VWAP_COLUMNS]].copy()
    return output, volume_indicators.vwap_diagnostics


def metadata(frame: pd.DataFrame, diagnostics: dict[str, Any], args: argparse.Namespace, output: Path) -> dict[str, Any]:
    latest_date = frame["date"].max()
    latest = frame[frame["date"] == latest_date]
    coverage = {column: round(float(frame[column].notna().mean()), 4) for column in VWAP_COLUMNS}
    latest_coverage = {column: round(float(latest[column].notna().mean()), 4) for column in VWAP_COLUMNS}
    extreme_ratio = {
        column: round(float(pd.to_numeric(frame[column], errors="coerce").abs().gt(1.0).mean()), 6)
        for column in ("close_vs_vwap_5d", "close_vs_vwap_20d")
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "contract": {
            "materializer_only": True,
            "shadow_only": True,
            "research_lane": "FIRST_WAVE_INSERT",
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
            "columns": ["date", "stock_id", *VWAP_COLUMNS],
            "coverage": coverage,
            "latest_coverage": latest_coverage,
            "extreme_ratio": extreme_ratio,
            "diagnostics": diagnostics,
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    diagnostics = summary["diagnostics"]
    lines = [
        "# VWAP Cost Basis Features",
        "",
        f"- rows：`{summary['rows']}`",
        f"- stocks：`{summary['stocks']}`",
        f"- dates：`{summary['dates']}`",
        f"- window：`{summary['start_date']}` to `{summary['end_date']}`",
        f"- research_lane：`{payload['contract']['research_lane']}`",
        f"- production_promotion_allowed：`{payload['contract']['production_promotion_allowed']}`",
        f"- daily_vwap_source：`{diagnostics['daily_vwap_source']}`",
        f"- value_volume_unit_usable：`{diagnostics['value_volume_unit_usable']}`",
        "",
        "| Feature | Coverage | Latest Coverage |",
        "|---|---:|---:|",
    ]
    for column in VWAP_COLUMNS:
        lines.append(f"| {column} | {summary['coverage'][column]:.1%} | {summary['latest_coverage'][column]:.1%} |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    features_path = resolve_path(args.features)
    features = pd.read_parquet(features_path, columns=list(REQUIRED_COLUMNS))
    frame, diagnostics = compute_vwap_cost_basis(features)
    output = resolve_path(args.output) if args.output else OUTPUT_DIR / f"vwap_cost_basis_features_{args.date}.parquet"
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(output, index=False)
    payload = metadata(frame, diagnostics=diagnostics, args=args, output=output)
    output.with_suffix(".json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": "OK", "output": repo_path(output), **payload["summary"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
