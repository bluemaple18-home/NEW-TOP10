#!/usr/bin/env python3
"""VWAP / 成本線第一輪研究。

只讀正式 features.parquet 與 market regime artifact，不訓練模型、不改 ranking。
輸出 IC、top/bottom spread、單因子 Top10 proxy，用來判斷 cost_basis 是否值得
進下一關 ablation / replay。
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "vwap-cost-basis-research.v1"
VWAP_FEATURES = (
    "daily_vwap",
    "rolling_vwap_5d",
    "rolling_vwap_20d",
    "close_vs_vwap_5d",
    "close_vs_vwap_20d",
    "vwap_reclaim_20d",
    "vwap_loss_20d",
)


@dataclass(frozen=True)
class FactorMetric:
    feature: str
    horizon: int
    regime_label: str
    rows: int
    days: int
    coverage: float
    ic_mean: float | None
    ic_t_stat: float | None
    direction_consistency: float | None
    top_bottom_spread_mean: float | None
    top10_minus_universe_return: float | None
    top10_hit_rate_delta: float | None
    preferred_direction: str | None
    status: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="research VWAP cost-basis features")
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument("--market-regime-history", default="artifacts/market_regime_history_2026-06-01.json")
    parser.add_argument("--horizons", default="1,3,5,10")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--min-days", type=int, default=8)
    parser.add_argument("--min-daily-stocks", type=int, default=30)
    parser.add_argument("--top-n", type=int, default=10)
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


def parse_horizons(value: str) -> list[int]:
    horizons = sorted({int(item.strip()) for item in value.split(",") if item.strip()})
    if not horizons:
        raise ValueError("--horizons 不可為空")
    return horizons


def load_regime_map(path: Path) -> dict[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        str(row.get("trade_date")): str(row.get("regime_label"))
        for row in payload.get("rows", [])
        if row.get("trade_date") and row.get("regime_label")
    }


def load_frame(features_path: Path, regime_path: Path, horizons: list[int]) -> pd.DataFrame:
    required = ["date", "stock_id", "open", "close", *VWAP_FEATURES]
    frame = pd.read_parquet(features_path, columns=required)
    frame["trade_date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["trade_date_text"] = frame["trade_date"].dt.date.astype(str)
    frame["stock_id"] = frame["stock_id"].astype(str).str.strip().str.zfill(4)
    frame = frame.dropna(subset=["trade_date", "stock_id"]).sort_values(["stock_id", "trade_date"]).copy()
    regime_map = load_regime_map(regime_path)
    frame["regime_label"] = frame["trade_date_text"].map(regime_map).fillna("UNKNOWN")
    next_open = frame.groupby("stock_id", sort=False)["open"].shift(-1)
    for horizon in horizons:
        exit_close = frame.groupby("stock_id", sort=False)["close"].shift(-horizon)
        frame[f"future_return_{horizon}d"] = (exit_close - next_open) / next_open
    return frame


def evaluate_feature(
    frame: pd.DataFrame,
    feature: str,
    horizon: int,
    regime: str,
    min_days: int,
    min_daily_stocks: int,
    top_n: int,
) -> FactorMetric:
    target = f"future_return_{horizon}d"
    scope = frame if regime == "ALL" else frame[frame["regime_label"].eq(regime)]
    valid = scope[["trade_date", "stock_id", feature, target]].rename(columns={feature: "factor", target: "future_return"}).copy()
    valid["factor"] = pd.to_numeric(valid["factor"], errors="coerce")
    valid["future_return"] = pd.to_numeric(valid["future_return"], errors="coerce")
    valid = valid.dropna(subset=["factor", "future_return"])
    valid = valid.groupby("trade_date").filter(lambda group: len(group) >= min_daily_stocks)
    denominator = int(scope[target].notna().sum())
    if valid.empty:
        return FactorMetric(feature, horizon, regime, 0, 0, 0.0, None, None, None, None, None, None, None, "INSUFFICIENT_DATA")

    daily_rows = []
    top_bottom_spreads = []
    top10_deltas = []
    top10_hit_deltas = []
    for _, group in valid.groupby("trade_date", sort=True):
        if group["factor"].nunique(dropna=True) < 3:
            continue
        ic = group["factor"].rank(method="average").corr(group["future_return"].rank(method="average"))
        top_cut = group["factor"].quantile(0.8)
        bottom_cut = group["factor"].quantile(0.2)
        top = group[group["factor"] >= top_cut]["future_return"]
        bottom = group[group["factor"] <= bottom_cut]["future_return"]
        if pd.notna(ic):
            daily_rows.append(float(ic))
        if not top.empty and not bottom.empty:
            top_bottom_spreads.append(float(top.mean() - bottom.mean()))
        ranked = group.sort_values("factor", ascending=False).head(top_n)
        universe = group["future_return"]
        if not ranked.empty and not universe.empty:
            top10_deltas.append(float(ranked["future_return"].mean() - universe.mean()))
            top10_hit_deltas.append(float((ranked["future_return"] > 0).mean() - (universe > 0).mean()))

    ic_series = pd.Series(daily_rows, dtype=float)
    spread_series = pd.Series(top_bottom_spreads, dtype=float)
    top10_delta = pd.Series(top10_deltas, dtype=float)
    hit_delta = pd.Series(top10_hit_deltas, dtype=float)
    days = int(valid["trade_date"].nunique())
    ic_mean = round_or_none(ic_series.mean())
    spread_mean = round_or_none(spread_series.mean())
    preferred_direction = None
    if ic_mean is not None:
        preferred_direction = "HIGHER_IS_BETTER" if ic_mean > 0 else "LOWER_IS_BETTER"
    status = metric_status(
        days=days,
        min_days=min_days,
        ic_mean=ic_mean,
        ic_t_stat=t_stat(ic_series),
        direction_consistency=direction_consistency(ic_series),
        spread_mean=spread_mean,
        top10_delta=round_or_none(top10_delta.mean()),
    )
    return FactorMetric(
        feature=feature,
        horizon=horizon,
        regime_label=regime,
        rows=int(len(valid)),
        days=days,
        coverage=round(len(valid) / max(1, denominator), 6),
        ic_mean=ic_mean,
        ic_t_stat=t_stat(ic_series),
        direction_consistency=direction_consistency(ic_series),
        top_bottom_spread_mean=spread_mean,
        top10_minus_universe_return=round_or_none(top10_delta.mean()),
        top10_hit_rate_delta=round_or_none(hit_delta.mean()),
        preferred_direction=preferred_direction,
        status=status,
    )


def direction_consistency(values: pd.Series) -> float | None:
    if values.empty:
        return None
    return round(float(max((values > 0).mean(), (values < 0).mean())), 6)


def t_stat(values: pd.Series) -> float | None:
    if len(values) < 2:
        return None
    std = values.std(ddof=1)
    if pd.isna(std) or std == 0:
        return None
    return round(float(values.mean() / (std / (len(values) ** 0.5))), 6)


def metric_status(
    *,
    days: int,
    min_days: int,
    ic_mean: float | None,
    ic_t_stat: float | None,
    direction_consistency: float | None,
    spread_mean: float | None,
    top10_delta: float | None,
) -> str:
    if days < min_days:
        return "INSUFFICIENT_DAYS"
    if ic_mean is None:
        return "NO_SIGNAL"
    if (
        abs(ic_mean) >= 0.03
        and ic_t_stat is not None
        and abs(ic_t_stat) >= 1.2
        and direction_consistency is not None
        and direction_consistency >= 0.58
        and spread_mean is not None
        and abs(spread_mean) >= 0.003
    ):
        return "SHADOW_CANDIDATE"
    if abs(ic_mean) >= 0.02 or (top10_delta is not None and abs(top10_delta) >= 0.002):
        return "WATCH"
    return "WEAK_OR_NOISY"


def round_or_none(value: Any, digits: int = 6) -> float | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(parsed):
        return None
    return round(float(parsed), digits)


def decision(metrics: list[FactorMetric]) -> dict[str, Any]:
    candidates = [metric for metric in metrics if metric.status == "SHADOW_CANDIDATE"]
    watches = [metric for metric in metrics if metric.status == "WATCH"]
    best = sorted(metrics, key=lambda item: abs(item.ic_mean or 0), reverse=True)[:8]
    return {
        "status": "FIRST_WAVE_SIGNAL_FOUND" if candidates else "WATCH_ONLY" if watches else "NO_CLEAR_SIGNAL",
        "candidate_count": len(candidates),
        "watch_count": len(watches),
        "recommended_next_step": (
            "run model ablation and Top10 replay with cost_basis family"
            if candidates
            else "keep as entry-quality/risk-guard watch; do not promote"
            if watches
            else "do not promote; only retain formal dimension for future monitoring"
        ),
        "top_metrics": [asdict(item) for item in best],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# VWAP Cost Basis Research",
        "",
        f"- generated_at：`{payload['generated_at']}`",
        f"- decision：`{payload['decision']['status']}`",
        f"- next_step：`{payload['decision']['recommended_next_step']}`",
        f"- rows：`{payload['inputs']['rows']}`",
        f"- regimes：`{', '.join(payload['summary']['regimes'])}`",
        "",
        "| Feature | H | Regime | Status | IC | t | Spread | Top10 Delta | Direction |",
        "|---|---:|---|---|---:|---:|---:|---:|---|",
    ]
    highlight = [
        row
        for row in payload["metrics"]
        if row["status"] in {"SHADOW_CANDIDATE", "WATCH"}
    ]
    if not highlight:
        highlight = payload["decision"]["top_metrics"]
    for row in sorted(highlight, key=lambda item: (item["status"], -abs(item.get("ic_mean") or 0)))[:30]:
        lines.append(
            "| {feature} | {horizon} | {regime} | {status} | {ic} | {t} | {spread} | {top10} | {direction} |".format(
                feature=row["feature"],
                horizon=row["horizon"],
                regime=row["regime_label"],
                status=row["status"],
                ic=fmt(row.get("ic_mean")),
                t=fmt(row.get("ic_t_stat")),
                spread=fmt(row.get("top_bottom_spread_mean")),
                top10=fmt(row.get("top10_minus_universe_return")),
                direction=row.get("preferred_direction") or "--",
            )
        )
    return "\n".join(lines) + "\n"


def fmt(value: Any) -> str:
    if value is None:
        return "--"
    return f"{float(value):.4f}"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    features_path = resolve_path(args.features)
    regime_path = resolve_path(args.market_regime_history)
    assert features_path is not None and regime_path is not None
    horizons = parse_horizons(args.horizons)
    frame = load_frame(features_path, regime_path, horizons)
    regimes = ["ALL", *sorted(regime for regime in frame["regime_label"].dropna().unique() if regime != "UNKNOWN")]
    metrics = [
        evaluate_feature(
            frame,
            feature=feature,
            horizon=horizon,
            regime=regime,
            min_days=args.min_days,
            min_daily_stocks=args.min_daily_stocks,
            top_n=args.top_n,
        )
        for feature in VWAP_FEATURES
        for horizon in horizons
        for regime in regimes
    ]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "contract": {
            "research_only": True,
            "reads_formal_features_parquet": True,
            "does_not_train_model": True,
            "does_not_change_ranking": True,
            "does_not_change_production_features": True,
            "production_ready": False,
        },
        "inputs": {
            "features": repo_path(features_path),
            "market_regime_history": repo_path(regime_path),
            "horizons": horizons,
            "rows": int(len(frame)),
            "stocks": int(frame["stock_id"].nunique()),
            "start_date": str(frame["trade_date"].min().date()),
            "end_date": str(frame["trade_date"].max().date()),
            "features_tested": list(VWAP_FEATURES),
        },
        "summary": {
            "regimes": regimes,
            "metric_rows": len(metrics),
            "status_counts": pd.Series([metric.status for metric in metrics]).value_counts().to_dict(),
        },
        "decision": decision(metrics),
        "metrics": [asdict(metric) for metric in metrics],
    }
    return payload


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = resolve_path(args.output) or PROJECT_ROOT / "artifacts" / "model_experiments" / f"vwap_cost_basis_research_{args.date}.json"
    assert output is not None
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "OK",
                "output": repo_path(output),
                "decision": payload["decision"]["status"],
                "status_counts": payload["summary"]["status_counts"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
