#!/usr/bin/env python3
"""產生依市場盤勢調整的 shadow ranking。

此腳本只產生研究用 ranking CSV，不訓練模型、不修改 production config。
目的：把 by-regime feature group 消融結果轉成可 replay 的 shadow 排名。
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
from scripts.research_feature_group_ablation_by_regime import attach_industry_factors  # noqa: E402


SCHEMA_VERSION = "regime-shadow-ranking.v1"
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
    "shadow_market_regime",
    "shadow_score",
    "reasons",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build regime-aware shadow ranking CSVs")
    parser.add_argument("--dates-from-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--market-regime-history", default="artifacts/market_regime_history_2026-05-29.json")
    parser.add_argument("--industry-map", default="data/reference/stock_industry_map.csv")
    parser.add_argument(
        "--risk-profile",
        choices=["baseline", "shadow_regime_guard_balanced", "shadow_regime_guard"],
        default="baseline",
        help="baseline 只改排序；shadow_regime_guard* 依詳細盤勢壓低總曝險",
    )
    parser.add_argument("--top-n", type=int, default=10, help="輸出 shadow ranking 檔的檔數")
    parser.add_argument("--max-sector-count", type=int, default=None, help="研究用 group cap；每個 group 最多保留 N 檔")
    parser.add_argument("--sector-cap-column", default="industry_name", help="研究用 group cap 欄位；預設對齊 portfolio replay 的 industry_name")
    parser.add_argument("--limit", type=int, default=None)
    return parser.parse_args()


def resolve_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def ranking_dates(path: Path, limit: int | None) -> list[str]:
    dates = []
    for file_path in sorted(path.glob("ranking_*.csv")):
        name = file_path.name
        if len(name) == len("ranking_YYYY-MM-DD.csv"):
            dates.append(name.removeprefix("ranking_").removesuffix(".csv"))
    return dates[-limit:] if limit else dates


def load_regime_map(path: Path) -> dict[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        str(row.get("trade_date")): str(row.get("regime_label"))
        for row in payload.get("rows", [])
        if row.get("trade_date") and row.get("regime_label")
    }


def percentile(series: pd.Series, ascending: bool = True) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    ranked = values.rank(pct=True, ascending=ascending)
    return ranked.fillna(0.5).clip(0, 1)


def factor_columns(history: pd.DataFrame, date_text: str, industry_map: Path) -> pd.DataFrame:
    enriched = attach_industry_factors(history.copy(), industry_map)
    target_date = pd.to_datetime(date_text).normalize()
    daily = enriched[pd.to_datetime(enriched["trade_date"], errors="coerce").dt.normalize() == target_date].copy()
    keep = [
        "stock_id",
        "trade_date",
        "sector_return_1d_loo",
        "sector_breadth_ma20_loo",
        "industry_return_1d_loo",
        "industry_breadth_ma20_loo",
    ]
    return daily[[col for col in keep if col in daily.columns]]


def apply_regime_shadow_score(frame: pd.DataFrame, regime_label: str) -> pd.DataFrame:
    df = frame.copy()
    prediction = pd.to_numeric(df["prediction_score"], errors="coerce").fillna(0.5)
    quality = pd.to_numeric(df["quality_score"], errors="coerce").fillna(0.5)
    risk = pd.to_numeric(df["risk_penalty"], errors="coerce").fillna(0.0)
    base = prediction + quality - risk

    volume_rank = percentile(df.get("avg_volume_20d", pd.Series(index=df.index, dtype=float)))
    value_rank = percentile(df.get("avg_value_20d", pd.Series(index=df.index, dtype=float)))
    volume_heat = (volume_rank + value_rank) / 2
    industry_strength = percentile(df.get("industry_breadth_ma20_loo", pd.Series(index=df.index, dtype=float)))
    sector_strength = percentile(df.get("sector_return_1d_loo", pd.Series(index=df.index, dtype=float)))
    trend_extension = percentile(df.get("pct_from_low_60d", pd.Series(index=df.index, dtype=float)))
    bb_width = percentile(df.get("bb_width", pd.Series(index=df.index, dtype=float)))

    if regime_label == "NARROW_LEADER":
        score = base + 0.32 * industry_strength + 0.24 * sector_strength + 0.18 * volume_heat
    elif regime_label == "EARLY_REVERSAL":
        score = base + 0.32 * sector_strength + 0.22 * industry_strength + 0.18 * volume_heat
    elif regime_label == "MIXED_NEUTRAL":
        score = base - 0.30 * volume_heat + 0.18 * industry_strength - 0.12 * trend_extension
    elif regime_label == "RISK_OFF":
        score = base + 0.25 * (1 - trend_extension) + 0.20 * (1 - bb_width) + 0.14 * industry_strength
    elif regime_label == "PANIC_SELLING":
        score = base + 0.28 * volume_heat + 0.20 * (1 - bb_width) + 0.16 * sector_strength
    else:
        score = base + 0.10 * industry_strength

    df["shadow_market_regime"] = regime_label
    df["shadow_score"] = score.clip(lower=0)
    df["risk_adjusted_score"] = df["shadow_score"]
    return df.sort_values("shadow_score", ascending=False)


def shadow_regime_gross_exposure(regime_label: str, current_gross: float, risk_profile: str) -> float:
    """用詳細盤勢對研究版 ranking 做總曝險上限，避免 RISK_OFF 被舊中性盤放太大。"""
    caps_by_profile = {
        "shadow_regime_guard_balanced": {
            "PANIC_SELLING": 0.35,
            "RISK_OFF": 0.50,
            "MIXED_NEUTRAL": 0.50,
            "EARLY_REVERSAL": 0.60,
            "NARROW_LEADER": 0.65,
            "UNKNOWN": 0.35,
        },
        "shadow_regime_guard": {
            "PANIC_SELLING": 0.30,
            "RISK_OFF": 0.35,
            "MIXED_NEUTRAL": 0.45,
            "EARLY_REVERSAL": 0.55,
            "NARROW_LEADER": 0.65,
            "UNKNOWN": 0.30,
        },
    }
    caps = caps_by_profile.get(risk_profile, caps_by_profile["shadow_regime_guard"])
    return min(float(current_gross), caps.get(regime_label, 0.45))


def apply_shadow_regime_risk_profile(frame: pd.DataFrame, regime_label: str, risk_profile: str) -> pd.DataFrame:
    if risk_profile == "baseline" or frame.empty:
        return frame

    df = frame.copy()
    current_gross = pd.to_numeric(df.get("gross_exposure", 0.0), errors="coerce").dropna()
    source_gross = float(current_gross.iloc[0]) if not current_gross.empty else 0.65
    target_gross = shadow_regime_gross_exposure(regime_label, source_gross, risk_profile)

    suggested = pd.to_numeric(df.get("suggested_weight", 0.0), errors="coerce").fillna(0.0).clip(lower=0.0)
    if suggested.sum() <= 0:
        suggested = pd.Series(1 / len(df), index=df.index, dtype=float)
    weights = suggested / suggested.sum() * target_gross

    position_cap = min(0.12, max(0.03, target_gross / max(len(df), 1) * 1.8))
    risk_penalty = pd.to_numeric(df.get("risk_penalty", 0.0), errors="coerce").fillna(0.0).clip(0, 1.5)
    risk_cap_factor = (1 - risk_penalty * 0.35).clip(0.45, 1.0)
    caps = (position_cap * risk_cap_factor).clip(upper=target_gross)
    weights = weights.clip(upper=caps)

    remaining = target_gross - float(weights.sum())
    for _ in range(5):
        if remaining <= 1e-9:
            break
        room = (caps - weights).clip(lower=0)
        if room.sum() <= 1e-9:
            break
        add = room / room.sum() * remaining
        weights = (weights + add).clip(upper=caps)
        remaining = target_gross - float(weights.sum())

    allocated = float(weights.sum())
    df["gross_exposure"] = round(target_gross, 4)
    df["max_position_weight"] = caps.round(4)
    df["suggested_weight"] = weights.round(4)
    df["allocated_exposure"] = round(allocated, 4)
    df["cash_weight"] = round(max(0.0, 1.0 - allocated), 4)
    df["exposure_note"] = f"shadow 盤勢 {regime_label}；研究版總曝險上限 {target_gross:.0%}"
    return df


def apply_sector_count_cap(
    frame: pd.DataFrame,
    industry_path: Path,
    top_n: int,
    max_sector_count: int | None,
    group_column: str = "industry_name",
) -> pd.DataFrame:
    """研究用 group cap rerank；不改分數，只限制輸出 TopN 的同族群集中度。"""

    if max_sector_count is None or max_sector_count <= 0 or frame.empty:
        return frame.head(top_n).copy()
    df = frame.copy()
    cap_column = group_column if group_column in df.columns else ""
    if not cap_column:
        industry = pd.read_csv(industry_path, dtype={"stock_id": str}) if industry_path.exists() else pd.DataFrame()
        if not industry.empty and {"stock_id", group_column}.issubset(industry.columns):
            industry["stock_id"] = industry["stock_id"].astype(str).str.zfill(4)
            df["stock_id"] = df["stock_id"].astype(str).str.zfill(4)
            df = df.merge(industry[["stock_id", group_column]].drop_duplicates("stock_id"), on="stock_id", how="left")
            cap_column = group_column
    if not cap_column and "sector_name" in df.columns:
        cap_column = "sector_name"
    if not cap_column:
        return frame.head(top_n).copy()
    df[cap_column] = df.get(cap_column, "未分類").fillna("未分類")

    selected = []
    group_counts: dict[str, int] = {}
    for _, row in df.iterrows():
        group = str(row.get(cap_column) or "未分類")
        if group_counts.get(group, 0) >= max_sector_count:
            continue
        selected.append(row)
        group_counts[group] = group_counts.get(group, 0) + 1
        if len(selected) >= top_n:
            break
    if len(selected) < top_n:
        selected_ids = {str(row["stock_id"]).zfill(4) for row in selected}
        for _, row in df.iterrows():
            stock_id = str(row.get("stock_id")).zfill(4)
            if stock_id in selected_ids:
                continue
            selected.append(row)
            selected_ids.add(stock_id)
            if len(selected) >= top_n:
                break
    return pd.DataFrame(selected).reset_index(drop=True)


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
    regime_path = resolve_path(args.market_regime_history)
    industry_path = resolve_path(args.industry_map)
    dates = ranking_dates(source_dir, args.limit)
    if not dates:
        raise FileNotFoundError(f"找不到 ranking_*.csv 日期：{source_dir}")
    regime_map = load_regime_map(regime_path)

    ranker = StockRanker(artifact_dir=str(output_dir))
    ranker.load_model()
    ranker._enrich_with_shap = lambda df, top_n=20: df

    outputs = []
    regimes_used: dict[str, int] = {}
    for date_text in dates:
        daily, history = ranker.load_daily_data(date_text)
        if daily.empty:
            raise ValueError(f"{date_text} 無 ranking 資料")
        base = ranker.calculate_scores(daily)
        factors = factor_columns(history, date_text, industry_path)
        merge_keys = ["stock_id"]
        base = base.merge(factors.drop(columns=["trade_date"], errors="ignore"), on=merge_keys, how="left")
        regime = ranker.market_regime_service.evaluate(history, target_date=base["date"].max() if "date" in base else None)
        scored = ranker.ranking_policy.apply(base, regime)
        shadow_regime = regime_map.get(date_text, "UNKNOWN")
        shadow = apply_regime_shadow_score(scored, shadow_regime).copy()
        shadow = apply_sector_count_cap(
            shadow,
            industry_path,
            top_n=args.top_n,
            max_sector_count=args.max_sector_count,
            group_column=args.sector_cap_column,
        )
        shadow = ranker.portfolio_policy.apply(shadow, regime)
        shadow = apply_shadow_regime_risk_profile(shadow, shadow_regime, args.risk_profile)
        shadow = ensure_names(shadow)
        out_path = output_dir / f"ranking_{date_text}.csv"
        write_ranking(out_path, shadow)
        outputs.append(repo_path(out_path))
        regimes_used[shadow_regime] = regimes_used.get(shadow_regime, 0) + 1
        print(f"REGIME_SHADOW_RANKING {shadow_regime} {date_text} {out_path}")

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "contract": {
            "research_only": True,
            "trains_model": False,
            "modifies_production_config": False,
            "uses_market_regime_history": True,
            "risk_profile": args.risk_profile,
            "top_n": args.top_n,
            "max_sector_count": args.max_sector_count,
            "sector_cap_column": args.sector_cap_column,
            "anti_overfit_note": "這是 shadow ranking replay，不可直接轉成 production 權重。",
        },
        "inputs": {
            "dates_from_dir": repo_path(source_dir),
            "output_dir": repo_path(output_dir),
            "market_regime_history": repo_path(regime_path),
            "industry_map": repo_path(industry_path),
            "date_count": len(dates),
            "dates": dates,
        },
        "regimes_used": regimes_used,
        "outputs": outputs,
    }


def main() -> int:
    args = parse_args()
    payload = build_shadow(args)
    output_dir = resolve_path(args.output_dir)
    summary_path = output_dir / "regime_shadow_ranking.json"
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"status": "OK", "summary": str(summary_path), "ranking_count": len(payload["outputs"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
