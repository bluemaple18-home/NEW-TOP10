#!/usr/bin/env python3
"""檢查 shadow alpha 候選因子的離線訊號品質。

只計算 coverage、每日橫斷面 IC 與 top-bottom spread；不訓練模型、不改排名。
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

from app.labels import LabelGenerator


OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "model_experiments"
SCHEMA_VERSION = "alpha-candidate-signal-check.v1"
KEY_COLUMNS = ("date", "stock_id")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="research shadow alpha candidate signal quality")
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument("--alpha-artifact", default=None)
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--horizon", type=int, default=10)
    parser.add_argument("--min-ic-days", type=int, default=5)
    parser.add_argument("--min-coverage", type=float, default=0.8)
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def resolve_path(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def latest_alpha_artifact() -> Path | None:
    matches = sorted(OUTPUT_DIR.glob("alpha_candidate_features_????-??-??.parquet"))
    return matches[-1] if matches else None


def load_labeled_features(path: Path, horizon: int) -> pd.DataFrame:
    frame = pd.read_parquet(path, columns=["date", "stock_id", "open", "close"])
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    if frame["date"].isna().any():
        raise ValueError("features date 欄位含不可解析日期")
    frame["stock_id"] = frame["stock_id"].astype(str).str.strip()
    if frame.duplicated(list(KEY_COLUMNS)).any():
        raise ValueError("features 含同股同交易日多筆資料")
    labeled = LabelGenerator(horizon=horizon).generate_labels(frame)
    return labeled.dropna(subset=["future_return"]).copy()


def load_alpha_frame(path: Path) -> tuple[pd.DataFrame, list[str]]:
    frame = pd.read_parquet(path)
    missing = [column for column in KEY_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"alpha artifact 缺少必要欄位：{missing}")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    if frame["date"].isna().any():
        raise ValueError("alpha artifact date 欄位含不可解析日期")
    frame["stock_id"] = frame["stock_id"].astype(str).str.strip()
    if frame.duplicated(list(KEY_COLUMNS)).any():
        raise ValueError("alpha artifact 含同股同交易日多筆資料")
    factors = [
        column
        for column in frame.columns
        if column not in KEY_COLUMNS and pd.api.types.is_numeric_dtype(frame[column])
    ]
    if not factors:
        raise ValueError("alpha artifact 沒有可檢查的數值因子")
    return frame, factors


def _spearman(left: pd.Series, right: pd.Series) -> float | None:
    if left.nunique(dropna=True) < 2 or right.nunique(dropna=True) < 2:
        return None
    value = left.corr(right, method="spearman")
    if pd.isna(value):
        return None
    return float(value)


def _t_stat(values: pd.Series) -> float | None:
    if len(values) < 2:
        return None
    std = values.std(ddof=1)
    if pd.isna(std) or std == 0:
        return None
    return float(values.mean() / (std / np.sqrt(len(values))))


def daily_ic(valid: pd.DataFrame, factor: str) -> pd.Series:
    values: list[float] = []
    for _, group in valid.groupby("date"):
        if len(group) < 3:
            continue
        value = _spearman(group[factor], group["future_return"])
        if value is not None:
            values.append(value)
    return pd.Series(values, dtype=float)


def daily_spread(valid: pd.DataFrame, factor: str) -> pd.Series:
    values: list[float] = []
    for _, group in valid.groupby("date"):
        if len(group) < 5 or group[factor].nunique(dropna=True) < 2:
            continue
        ranks = group[factor].rank(method="average", pct=True)
        top = group.loc[ranks >= 0.8, "future_return"]
        bottom = group.loc[ranks <= 0.2, "future_return"]
        if top.empty or bottom.empty:
            continue
        values.append(float(top.mean() - bottom.mean()))
    return pd.Series(values, dtype=float)


def metric_for_factor(frame: pd.DataFrame, factor: str, min_ic_days: int, min_coverage: float) -> dict[str, Any]:
    values = pd.to_numeric(frame[factor], errors="coerce")
    valid = pd.DataFrame(
        {
            "date": frame["date"],
            "stock_id": frame["stock_id"],
            factor: values,
            "future_return": pd.to_numeric(frame["future_return"], errors="coerce"),
        }
    ).dropna()
    latest_date = frame["date"].max()
    coverage = float(values.notna().mean()) if len(values) else 0.0
    latest_coverage = float(values[frame["date"] == latest_date].notna().mean()) if len(values) else 0.0
    ic = daily_ic(valid, factor)
    spread = daily_spread(valid, factor)
    ic_mean = float(ic.mean()) if not ic.empty else None
    spread_mean = float(spread.mean()) if not spread.empty else None
    status = "MONITOR_ONLY"
    if (
        coverage >= min_coverage
        and len(ic) >= min_ic_days
        and ic_mean is not None
        and ic_mean >= 0.005
        and (spread_mean is None or spread_mean > 0)
    ):
        status = "SHADOW_CANDIDATE"
    return {
        "factor": factor,
        "status": status,
        "coverage": round(coverage, 4),
        "latest_coverage": round(latest_coverage, 4),
        "observations": int(len(valid)),
        "ic_mean": round(ic_mean, 6) if ic_mean is not None else None,
        "ic_median": round(float(ic.median()), 6) if not ic.empty else None,
        "ic_t_stat": round(_t_stat(ic), 6) if _t_stat(ic) is not None else None,
        "ic_days": int(len(ic)),
        "top_bottom_spread_mean": round(spread_mean, 6) if spread_mean is not None else None,
        "spread_days": int(len(spread)),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    features_path = resolve_path(args.features)
    if features_path is None:
        raise RuntimeError("features path resolution failed")
    alpha_path = resolve_path(args.alpha_artifact) or latest_alpha_artifact()
    if alpha_path is None:
        raise FileNotFoundError("找不到 alpha_candidate_features_YYYY-MM-DD.parquet，請先跑 build_alpha_candidate_features.py")
    labeled = load_labeled_features(features_path, horizon=args.horizon)
    alpha, factors = load_alpha_frame(alpha_path)
    frame = labeled.merge(alpha, on=list(KEY_COLUMNS), how="inner", validate="one_to_one")
    if frame.empty:
        raise RuntimeError("features labels 與 alpha artifact 沒有可重疊資料")
    metrics = [
        metric_for_factor(frame, factor=factor, min_ic_days=args.min_ic_days, min_coverage=args.min_coverage)
        for factor in factors
    ]
    candidates = [row["factor"] for row in metrics if row["status"] == "SHADOW_CANDIDATE"]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK",
        "contract": {
            "research_only": True,
            "does_not_train_model": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_write_production_features": True,
            "does_not_change_production_ranking": True,
            "production_promotion_allowed": False,
        },
        "inputs": {
            "features": repo_path(features_path),
            "alpha_artifact": repo_path(alpha_path),
            "horizon": args.horizon,
            "min_ic_days": args.min_ic_days,
            "min_coverage": args.min_coverage,
        },
        "summary": {
            "rows": int(len(frame)),
            "stocks": int(frame["stock_id"].nunique()),
            "dates": int(frame["date"].nunique()),
            "factor_count": len(factors),
            "shadow_candidate_count": len(candidates),
            "shadow_candidates": candidates,
        },
        "metrics": metrics,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Alpha Candidate Signal Check",
        "",
        f"- factor_count：`{summary['factor_count']}`",
        f"- shadow_candidate_count：`{summary['shadow_candidate_count']}`",
        f"- production_promotion_allowed：`{payload['contract']['production_promotion_allowed']}`",
        "",
        "| Factor | Status | IC Mean | Spread Mean | Coverage | Latest |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in payload["metrics"]:
        lines.append(
            f"| {row['factor']} | {row['status']} | {row['ic_mean']} | "
            f"{row['top_bottom_spread_mean']} | {row['coverage']:.1%} | {row['latest_coverage']:.1%} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = resolve_path(args.output) or OUTPUT_DIR / f"alpha_candidate_signal_check_{args.date}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output), **payload["summary"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
