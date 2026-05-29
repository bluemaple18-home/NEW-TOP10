#!/usr/bin/env python3
"""依市場盤勢做 feature group 消融研究。

本腳本只讀既有 data/clean 與 market regime artifact，不訓練模型、不改 ranking。
它用每日橫斷面 IC 與 Top/Bottom 分位差，先判斷哪些資訊維度在不同盤勢下有訊號。
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.modeling.feature_contract import load_m4_feature_frame  # noqa: E402
from app.monitoring.factor_monitor import _daily_cross_sectional_ic, _t_stat  # noqa: E402


SCHEMA_VERSION = "feature-group-ablation-by-regime.v1"
PRICE_VOLUME_EXACT_COLUMNS = {
    "open",
    "high",
    "low",
    "close",
    "volume",
    "transactions",
    "value",
    "obv",
}
PRICE_VOLUME_PREFIXES = (
    "avg_volume",
    "volume_ratio",
    "avg_value",
)


@dataclass(frozen=True)
class FeatureMetric:
    group: str
    feature: str
    regime_label: str
    horizon: int
    rows: int
    days: int
    coverage: float
    ic_mean: float | None
    ic_median: float | None
    abs_ic_mean: float | None
    ic_t_stat: float | None
    ic_direction_consistency: float | None
    top_bottom_spread_mean: float | None
    top_bottom_spread_median: float | None
    status: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="feature group ablation by market regime")
    parser.add_argument("--data-dir", default="data/clean")
    parser.add_argument("--market-regime-history", default="artifacts/market_regime_history_2026-05-29.json")
    parser.add_argument("--industry-map", default="data/reference/stock_industry_map.csv")
    parser.add_argument("--horizons", default="1,3,5,10")
    parser.add_argument("--min-days", type=int, default=8)
    parser.add_argument("--min-daily-stocks", type=int, default=30)
    parser.add_argument("--top-features-per-group", type=int, default=8)
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def resolve_path(value: str | None) -> Path | None:
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


def parse_horizons(value: str) -> list[int]:
    horizons = [int(item.strip()) for item in value.split(",") if item.strip()]
    if not horizons:
        raise ValueError("--horizons 不可為空")
    return sorted(set(horizons))


def load_regime_map(path: Path) -> dict[str, str]:
    if not path.exists():
        raise FileNotFoundError(f"market regime history 不存在：{path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    mapping: dict[str, str] = {}
    for row in payload.get("rows", []):
        date = str(row.get("trade_date") or "").strip()
        label = str(row.get("regime_label") or "").strip()
        if date and label:
            mapping[date] = label
    if not mapping:
        raise ValueError(f"market regime history 沒有可用 rows：{path}")
    return mapping


def load_frame(data_dir: Path, regime_path: Path, industry_path: Path | None) -> tuple[pd.DataFrame, dict[str, list[str]], dict[str, Any]]:
    frame, metadata = load_m4_feature_frame(data_dir=data_dir, project_root=PROJECT_ROOT)
    frame = frame.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce").dt.normalize()
    frame["stock_id"] = frame["stock_id"].astype(str).str.strip().str.zfill(4)
    frame = frame.dropna(subset=["trade_date", "stock_id"]).sort_values(["stock_id", "trade_date"]).copy()
    frame["trade_date_text"] = frame["trade_date"].dt.date.astype(str)
    regime_map = load_regime_map(regime_path)
    frame["regime_label"] = frame["trade_date_text"].map(regime_map).fillna("UNKNOWN")
    frame = attach_industry_factors(frame, industry_path)
    groups = feature_groups(frame, metadata.feature_groups)
    contract = {
        "feature_metadata": metadata.to_dict(),
        "regime_history": repo_path(regime_path),
        "industry_map": repo_path(industry_path),
        "research_only": True,
        "trains_model": False,
        "changes_ranking": False,
        "anti_overfit_note": "這是第一層濾噪證據，只能決定 shadow 實驗優先序，不可直接調 production 權重。",
    }
    return frame, groups, contract


def attach_industry_factors(frame: pd.DataFrame, industry_path: Path | None) -> pd.DataFrame:
    result = frame.copy()
    if industry_path is None or not industry_path.exists():
        return result
    industry = pd.read_csv(industry_path, dtype={"stock_id": str})
    industry["stock_id"] = industry["stock_id"].astype(str).str.strip().str.zfill(4)
    keep = [col for col in ["stock_id", "sector_name", "industry_name"] if col in industry.columns]
    if "stock_id" not in keep:
        return result
    result = result.merge(industry[keep].drop_duplicates("stock_id"), on="stock_id", how="left")
    result["sector_name"] = result.get("sector_name", "unknown").fillna("unknown")
    result["industry_name"] = result.get("industry_name", "unknown").fillna("unknown")
    daily_return = result.groupby("stock_id", sort=False)["close"].pct_change()
    result["_daily_return"] = daily_return
    for group_col in ["sector_name", "industry_name"]:
        prefix = "sector" if group_col == "sector_name" else "industry"
        result[f"{prefix}_return_1d_loo"] = leave_one_out_mean(result, group_col, "_daily_return")
        result[f"{prefix}_breadth_ma20_loo"] = leave_one_out_mean(result, group_col, "_above_ma20")
    result = result.drop(columns=["_daily_return", "_above_ma20"], errors="ignore")
    return result


def leave_one_out_mean(frame: pd.DataFrame, group_col: str, value_col: str) -> pd.Series:
    if value_col == "_above_ma20" and value_col not in frame.columns:
        close = pd.to_numeric(frame["close"], errors="coerce")
        ma20 = pd.to_numeric(frame["ma20"], errors="coerce")
        frame[value_col] = (close > ma20).astype(float)
    values = pd.to_numeric(frame[value_col], errors="coerce")
    grouped = frame.assign(_value=values).groupby(["trade_date", group_col], dropna=False)["_value"]
    sums = grouped.transform("sum")
    counts = grouped.transform("count")
    peers = counts - 1
    loo = (sums - values) / peers.where(peers > 0)
    return loo


def feature_groups(frame: pd.DataFrame, metadata_groups: dict[str, Any]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    technical = [col for col in metadata_groups.get("technical").columns if col in frame.columns]
    price_volume = [
        col
        for col in technical
        if col in PRICE_VOLUME_EXACT_COLUMNS or any(col.startswith(prefix) for prefix in PRICE_VOLUME_PREFIXES)
    ]
    trend_momentum = [col for col in technical if col not in set(price_volume)]
    groups["price_volume"] = numeric_columns(frame, price_volume)
    groups["trend_momentum"] = numeric_columns(frame, trend_momentum)
    for name in ["event", "pattern", "fundamental"]:
        groups[name] = numeric_columns(frame, [col for col in metadata_groups.get(name).columns if col in frame.columns])
    groups["industry_momentum"] = numeric_columns(
        frame,
        [
            "sector_return_1d_loo",
            "sector_breadth_ma20_loo",
            "industry_return_1d_loo",
            "industry_breadth_ma20_loo",
        ],
    )
    return {name: cols for name, cols in groups.items() if cols}


def numeric_columns(frame: pd.DataFrame, columns: list[str]) -> list[str]:
    return [col for col in columns if col in frame.columns and pd.api.types.is_numeric_dtype(frame[col])]


def add_forward_returns(frame: pd.DataFrame, horizons: list[int]) -> pd.DataFrame:
    result = frame.sort_values(["stock_id", "trade_date"]).copy()
    next_open = result.groupby("stock_id", sort=False)["open"].shift(-1)
    for horizon in horizons:
        exit_close = result.groupby("stock_id", sort=False)["close"].shift(-horizon)
        result[f"future_return_{horizon}d"] = (exit_close - next_open) / next_open
    return result


def evaluate_feature(
    frame: pd.DataFrame,
    group_name: str,
    feature: str,
    regime: str,
    horizon: int,
    min_days: int,
    min_daily_stocks: int,
) -> FeatureMetric:
    target = f"future_return_{horizon}d"
    valid = frame.loc[
        frame["regime_label"].eq(regime),
        ["trade_date", "stock_id", feature, target],
    ].rename(columns={feature: "factor", target: "future_return"})
    valid["factor"] = pd.to_numeric(valid["factor"], errors="coerce")
    valid["future_return"] = pd.to_numeric(valid["future_return"], errors="coerce")
    valid = valid.dropna(subset=["factor", "future_return"])
    valid = valid.groupby("trade_date").filter(lambda group: len(group) >= min_daily_stocks)
    if valid.empty:
        return empty_metric(group_name, feature, regime, horizon)
    ic = _daily_cross_sectional_ic(valid)
    spreads = daily_top_bottom_spreads(valid)
    days = int(valid["trade_date"].nunique())
    rows = int(len(valid))
    coverage = round(rows / max(1, int(frame.loc[frame["regime_label"].eq(regime), target].notna().sum())), 6)
    ic_mean = round_or_none(ic.mean())
    abs_ic_mean = round_or_none(ic.abs().mean())
    ic_t = round_or_none(_t_stat(ic))
    direction_consistency = round_or_none(ic_direction_consistency(ic))
    spread_mean = round_or_none(spreads.mean())
    status = metric_status(
        days=days,
        min_days=min_days,
        abs_ic_mean=abs_ic_mean,
        ic_t_stat=ic_t,
        direction_consistency=direction_consistency,
        spread_mean=spread_mean,
    )
    return FeatureMetric(
        group=group_name,
        feature=feature,
        regime_label=regime,
        horizon=horizon,
        rows=rows,
        days=days,
        coverage=coverage,
        ic_mean=ic_mean,
        ic_median=round_or_none(ic.median()),
        abs_ic_mean=abs_ic_mean,
        ic_t_stat=ic_t,
        ic_direction_consistency=direction_consistency,
        top_bottom_spread_mean=spread_mean,
        top_bottom_spread_median=round_or_none(spreads.median()),
        status=status,
    )


def empty_metric(group_name: str, feature: str, regime: str, horizon: int) -> FeatureMetric:
    return FeatureMetric(
        group=group_name,
        feature=feature,
        regime_label=regime,
        horizon=horizon,
        rows=0,
        days=0,
        coverage=0.0,
        ic_mean=None,
        ic_median=None,
        abs_ic_mean=None,
        ic_t_stat=None,
        ic_direction_consistency=None,
        top_bottom_spread_mean=None,
        top_bottom_spread_median=None,
        status="INSUFFICIENT_DATA",
    )


def daily_top_bottom_spreads(valid: pd.DataFrame) -> pd.Series:
    values: list[float] = []
    for _, group in valid.groupby("trade_date"):
        if len(group) < 10 or group["factor"].nunique(dropna=True) < 3:
            continue
        top_cut = group["factor"].quantile(0.8)
        bottom_cut = group["factor"].quantile(0.2)
        top = group.loc[group["factor"] >= top_cut, "future_return"].mean()
        bottom = group.loc[group["factor"] <= bottom_cut, "future_return"].mean()
        if pd.notna(top) and pd.notna(bottom):
            values.append(float(top - bottom))
    return pd.Series(values, dtype=float)


def ic_direction_consistency(ic: pd.Series) -> float | None:
    if ic.empty:
        return None
    positive = float((ic > 0).mean())
    negative = float((ic < 0).mean())
    return max(positive, negative)


def metric_status(
    days: int,
    min_days: int,
    abs_ic_mean: float | None,
    ic_t_stat: float | None,
    direction_consistency: float | None,
    spread_mean: float | None,
) -> str:
    if days < min_days:
        return "INSUFFICIENT_DAYS"
    if abs_ic_mean is None:
        return "NO_SIGNAL"
    enough_direction = direction_consistency is not None and direction_consistency >= 0.60
    enough_t = ic_t_stat is not None and abs(ic_t_stat) >= 1.20
    enough_spread = spread_mean is not None and abs(spread_mean) >= 0.004
    if abs_ic_mean >= 0.04 and enough_t and enough_direction and enough_spread:
        return "SHADOW_CANDIDATE"
    if abs_ic_mean >= 0.03 and direction_consistency is not None and direction_consistency >= 0.55:
        return "WATCH"
    return "WEAK_OR_NOISY"


def round_or_none(value: Any, digits: int = 6) -> float | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(parsed):
        return None
    return round(float(parsed), digits)


def summarize(metrics: list[FeatureMetric], top_n: int) -> dict[str, Any]:
    frame = pd.DataFrame([asdict(metric) for metric in metrics])
    if frame.empty:
        return {"feature_count": 0, "groups": [], "regimes": []}
    candidates = frame[frame["status"].isin(["SHADOW_CANDIDATE", "WATCH"])].copy()
    group_rows = []
    for (regime, horizon, group), data in frame.groupby(["regime_label", "horizon", "group"], dropna=False):
        candidate_data = data[data["status"].isin(["SHADOW_CANDIDATE", "WATCH"])].copy()
        rank_source = candidate_data if not candidate_data.empty else data
        ranked = rank_source.sort_values(["abs_ic_mean", "days"], ascending=[False, False], na_position="last")
        top = ranked.head(top_n)
        candidate_count = int(len(candidate_data))
        group_rows.append(
            {
                "regime_label": regime,
                "horizon": int(horizon),
                "group": group,
                "feature_count": int(len(data)),
                "candidate_count": candidate_count,
                "best_abs_ic_mean": round_or_none(top["abs_ic_mean"].max()),
                "best_feature": str(top.iloc[0]["feature"]) if not top.empty else None,
                "top_features": [
                    {
                        "feature": str(row["feature"]),
                        "status": str(row["status"]),
                        "days": int(row["days"]),
                        "ic_mean": round_or_none(row["ic_mean"]),
                        "abs_ic_mean": round_or_none(row["abs_ic_mean"]),
                        "direction_consistency": round_or_none(row["ic_direction_consistency"]),
                        "t_stat": round_or_none(row["ic_t_stat"]),
                        "spread_mean": round_or_none(row["top_bottom_spread_mean"]),
                    }
                    for _, row in top.iterrows()
                ],
            }
        )
    return {
        "feature_count": int(frame["feature"].nunique()),
        "metric_rows": int(len(frame)),
        "candidate_metric_rows": int(len(candidates)),
        "groups": sorted(frame["group"].unique().tolist()),
        "regimes": sorted(frame["regime_label"].unique().tolist()),
        "by_regime_horizon_group": group_rows,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Feature Group Ablation By Market Regime",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- rows: {payload['inputs']['rows']}",
        f"- horizons: {payload['inputs']['horizons']}",
        f"- regimes: {', '.join(payload['summary']['regimes'])}",
        "",
        "## Group Highlights",
        "",
        "| Regime | H | Group | Candidates | Best Feature | Best Abs IC | Top Features |",
        "|---|---:|---|---:|---|---:|---|",
    ]
    rows = payload["summary"]["by_regime_horizon_group"]
    for row in sorted(rows, key=lambda item: (item["regime_label"], item["horizon"], item["group"])):
        if row["candidate_count"] <= 0:
            continue
        top_features = ", ".join(
            f"{item['feature']}({item['status']}, IC={fmt_num(item['abs_ic_mean'])})"
            for item in row["top_features"][:3]
        )
        lines.append(
            "| {regime} | {horizon} | {group} | {count} | {feature} | {ic} | {top} |".format(
                regime=row["regime_label"],
                horizon=row["horizon"],
                group=row["group"],
                count=row["candidate_count"],
                feature=row["best_feature"],
                ic=fmt_num(row["best_abs_ic_mean"]),
                top=top_features,
            )
        )
    return "\n".join(lines) + "\n"


def fmt_num(value: Any) -> str:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(parsed):
        return "--"
    return f"{float(parsed):.4f}"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    data_dir = resolve_path(args.data_dir)
    regime_path = resolve_path(args.market_regime_history)
    industry_path = resolve_path(args.industry_map)
    assert data_dir is not None and regime_path is not None
    horizons = parse_horizons(args.horizons)
    frame, groups, contract = load_frame(data_dir, regime_path, industry_path)
    frame = add_forward_returns(frame, horizons)
    regimes = sorted(regime for regime in frame["regime_label"].dropna().unique().tolist() if regime != "UNKNOWN")
    metrics: list[FeatureMetric] = []
    for horizon in horizons:
        for regime in regimes:
            for group_name, columns in groups.items():
                for feature in columns:
                    metrics.append(
                        evaluate_feature(
                            frame,
                            group_name=group_name,
                            feature=feature,
                            regime=regime,
                            horizon=horizon,
                            min_days=args.min_days,
                            min_daily_stocks=args.min_daily_stocks,
                        )
                    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "contract": contract,
        "inputs": {
            "data_dir": repo_path(data_dir),
            "market_regime_history": repo_path(regime_path),
            "industry_map": repo_path(industry_path),
            "horizons": horizons,
            "rows": int(len(frame)),
            "stocks": int(frame["stock_id"].nunique()),
            "start_date": str(frame["trade_date"].min().date()),
            "end_date": str(frame["trade_date"].max().date()),
            "min_days": args.min_days,
            "min_daily_stocks": args.min_daily_stocks,
        },
        "feature_groups": {name: columns for name, columns in groups.items()},
        "summary": summarize(metrics, args.top_features_per_group),
        "metrics": [asdict(metric) for metric in metrics],
    }


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output_path = resolve_path(args.output) or PROJECT_ROOT / "artifacts" / "feature_group_ablation_by_regime_latest.json"
    assert output_path is not None
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output_path.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "OK",
                "output": str(output_path),
                "markdown": str(output_path.with_suffix(".md")),
                "candidate_metric_rows": payload["summary"]["candidate_metric_rows"],
                "groups": payload["summary"]["groups"],
                "regimes": payload["summary"]["regimes"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
