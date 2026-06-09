#!/usr/bin/env python3
"""比較 production Top10 與 guarded Top10 的研究用績效回測。

只產出 research artifact；不改正式 ranking、模型或推播來源。
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agent_b_ranking import StockRanker  # noqa: E402
from app.modeling.feature_contract import load_m4_feature_frame  # noqa: E402
from scripts import run_backtest_replay  # noqa: E402
from scripts.replay_guarded_top10_policy import (  # noqa: E402
    CANDIDATE_POOL_RULE,
    CANDIDATE_POOL_SIZE_CONTRACT,
    build_summary as guarded_build_summary,
    render_markdown as guarded_render_markdown,
    repo_path,
    rows_from_frame,
    stock_id_list,
)


SCHEMA_VERSION = "guarded-top10-performance-backtest.v1"
DECISION_STATUSES = {
    "GUARDED_OUTPERFORMS_RESEARCH_ONLY",
    "MIXED_MONITOR_ONLY",
    "GUARDED_UNDERPERFORMS",
    "INSUFFICIENT_DATA",
}
HORIZONS = (1, 3, 5, 10)
DEFAULT_PRODUCTION_DIRS = [
    "artifacts/backtest/historical_rankings_current_model_batch_dense_2023-11-21_2026-05-15",
    "artifacts",
]


@dataclass
class ReplayResources:
    ranker: StockRanker
    features: pd.DataFrame
    universe: pd.DataFrame
    output_dir: Path
    data_dir: Path
    model_dir: Path
    config_path: Path
    model_name: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="backtest guarded Top10 performance against production Top10")
    parser.add_argument("--window", required=True, choices=["recent_100", "recent_6m"])
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument("--data-dir", default="data/clean")
    parser.add_argument("--model-dir", default="models")
    parser.add_argument("--model", default="latest_lgbm.pkl")
    parser.add_argument("--config", default="config/signals.yaml")
    parser.add_argument("--production-dir", action="append", default=None, help="可重複指定；同日後指定者覆蓋前者")
    parser.add_argument("--guarded-dir", default="artifacts/research")
    parser.add_argument("--output-dir", default="artifacts/research")
    parser.add_argument("--market-regime-history", default=None)
    parser.add_argument("--as-of-date", default=None)
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--candidate-pool-size", type=int, default=CANDIDATE_POOL_SIZE_CONTRACT, choices=[CANDIDATE_POOL_SIZE_CONTRACT])
    parser.add_argument("--horizons", default="1,3,5,10")
    parser.add_argument("--entry-delay-trade-days", type=int, default=1)
    parser.add_argument("--fee-rate", type=float, default=0.001425)
    parser.add_argument("--tax-rate", type=float, default=0.003)
    parser.add_argument("--slippage-rate", type=float, default=0.001)
    parser.add_argument("--no-generate-guarded", action="store_true", help="缺 guarded replay artifact 時直接標記缺口")
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def parse_horizons(value: str) -> list[int]:
    horizons = [int(item.strip()) for item in value.split(",") if item.strip()]
    if sorted(horizons) != list(HORIZONS):
        raise ValueError("此卡固定比較 D+1/D+3/D+5/D+10，--horizons 必須是 1,3,5,10")
    return horizons


def ranking_date(path: Path) -> str:
    match = re.fullmatch(r"ranking_(\d{4}-\d{2}-\d{2})\.csv", path.name)
    if not match:
        raise ValueError(f"ranking 檔名無法解析日期：{path}")
    return match.group(1)


def production_ranking_map(dirs: list[str] | None) -> tuple[dict[str, Path], dict[str, Any]]:
    result: dict[str, Path] = {}
    source_by_date: dict[str, str] = {}
    overwritten: list[dict[str, Any]] = []
    source_counts: dict[str, int] = {}
    effective_dirs = dirs or DEFAULT_PRODUCTION_DIRS
    production_dirs = []
    for raw_dir in effective_dirs:
        directory = resolve_path(raw_dir)
        if not directory.exists():
            continue
        production_dirs.append(repo_path(directory))
        for path in sorted(directory.glob("ranking_????-??-??.csv")):
            date_text = ranking_date(path)
            if date_text in result:
                overwritten.append(
                    {
                        "date": date_text,
                        "previous": repo_path(result[date_text]),
                        "replacement": repo_path(path),
                    }
                )
            result[date_text] = path
            source_by_date[date_text] = repo_path(path)
    for source in source_by_date.values():
        source_dir = str(Path(source).parent)
        source_counts[source_dir] = source_counts.get(source_dir, 0) + 1
    if not result:
        raise FileNotFoundError("找不到 production ranking artifacts")
    return result, {
        "production_dirs": production_dirs,
        "overlap_policy": "later production-dir overrides earlier production-dir for the same ranking date",
        "production_source_by_date": source_by_date,
        "source_counts": source_counts,
        "overwritten_date_count": len(overwritten),
        "overwritten_dates_sample": overwritten[:50],
    }


def load_price_frame(path: Path) -> pd.DataFrame:
    frame = run_backtest_replay.load_price_frame(path)
    return frame.sort_values(["stock_id", "trade_date"]).reset_index(drop=True)


def select_window_dates(
    window: str,
    production_dates: list[str],
    price_dates: list[Any],
    as_of_date: str | None,
) -> tuple[list[str], dict[str, Any]]:
    max_production = max(production_dates)
    max_price = max(item.isoformat() for item in price_dates)
    end = pd.to_datetime(as_of_date or min(max_production, max_price)).normalize()
    available = [date for date in production_dates if pd.to_datetime(date).normalize() <= end]
    if window == "recent_100":
        selected = available[-100:]
        start = selected[0] if selected else None
        required_count = 100
    elif window == "recent_6m":
        start_ts = end - pd.DateOffset(months=6)
        selected = [date for date in available if pd.to_datetime(date).normalize() >= start_ts]
        start = start_ts.strftime("%Y-%m-%d")
        required_count = None
    else:
        raise ValueError(f"unsupported window: {window}")
    return selected, {
        "window": window,
        "as_of_date": end.strftime("%Y-%m-%d"),
        "start_boundary": start,
        "selected_start_date": selected[0] if selected else None,
        "selected_end_date": selected[-1] if selected else None,
        "selected_date_count": len(selected),
        "required_count": required_count,
        "available_production_date_count": len(available),
        "max_production_date": max_production,
        "max_price_date": max_price,
    }


def read_csv_ranking(path: Path, top_n: int, refs: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    items = []
    for rank, row in enumerate(rows[:top_n], start=1):
        stock_id = clean_stock_id(row.get("stock_id"))
        item = {
            "rank": rank,
            "stock_id": stock_id,
            "stock_name": row.get("stock_name") or refs.get(stock_id, {}).get("stock_name"),
            "suggested_weight": number(row.get("suggested_weight")),
            "max_position_weight": number(row.get("max_position_weight")),
            "gross_exposure": number(row.get("gross_exposure")),
            "risk_adjusted_score": number(row.get("risk_adjusted_score")),
            "model_prob": number(row.get("model_prob")),
        }
        item.update(reference_fields(stock_id, refs, row))
        items.append(item)
    return items


def read_guarded_items(path: Path, top_n: int, refs: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = []
    for rank, row in enumerate(payload.get("shadow_guarded_top10", [])[:top_n], start=1):
        stock_id = clean_stock_id(row.get("stock_id"))
        item = dict(row)
        item["rank"] = rank
        item["stock_id"] = stock_id
        item.update(reference_fields(stock_id, refs, row))
        items.append(item)
    return items, payload


def clean_stock_id(value: Any) -> str:
    return str(value or "").strip().replace(".0", "").zfill(4)


def number(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(parsed) else parsed


def reference_fields(stock_id: str, refs: dict[str, dict[str, Any]], row: dict[str, Any] | pd.Series) -> dict[str, Any]:
    ref = refs.get(stock_id, {})
    industry = value_from(row, "industry_name") or ref.get("industry_name")
    sector = value_from(row, "sector_name") or ref.get("sector_name")
    theme_tags = split_tags(value_from(row, "theme_tags") or ref.get("theme_tags"))
    return {
        "industry_name": industry or "UNKNOWN",
        "sector_name": sector or "UNKNOWN",
        "theme_tags": theme_tags,
    }


def value_from(row: dict[str, Any] | pd.Series, key: str) -> Any:
    if isinstance(row, pd.Series):
        return row.get(key)
    return row.get(key)


def split_tags(value: Any) -> list[str]:
    if value is None or (not isinstance(value, list) and pd.isna(value)):
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value).replace(",", "|").split("|") if part.strip()]


def load_reference_map(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    frame = pd.read_csv(path, dtype={"stock_id": str})
    result = {}
    for row in frame.to_dict("records"):
        stock_id = clean_stock_id(row.get("stock_id"))
        result[stock_id] = row
    return result


def load_universe(data_dir: Path, features: pd.DataFrame) -> pd.DataFrame:
    universe_path = data_dir / "universe.parquet"
    if universe_path.exists():
        universe = pd.read_parquet(universe_path)
        if not universe.empty:
            universe["stock_id"] = universe["stock_id"].astype(str).str.strip()
            if "date" in universe.columns:
                universe["date"] = pd.to_datetime(universe["date"], errors="coerce")
                universe["trade_date"] = universe["date"].dt.normalize()
            return universe
    return pd.DataFrame({"stock_id": features["stock_id"].astype(str).str.strip().unique()})


def prepare_replay_resources(args: argparse.Namespace, output_dir: Path) -> ReplayResources:
    data_dir = resolve_path(args.data_dir)
    model_dir = resolve_path(args.model_dir)
    config_path = resolve_path(args.config)
    ranker = StockRanker(
        data_dir=str(data_dir),
        model_dir=str(model_dir),
        artifact_dir=str(output_dir),
        config_path=str(config_path),
        generate_report=False,
        explain_top_n=0,
    )
    ranker.load_model(args.model)
    features, metadata = load_m4_feature_frame(data_dir=data_dir, project_root=ranker._project_root(), config_path=config_path)
    features.attrs["m4_feature_metadata"] = metadata
    ranker._ensure_unique_trade_keys(features, "m4_feature_frame")
    features = features.sort_values(["stock_id", "trade_date"]).copy()
    # 與 guarded selection replay 保持同一組交易計畫輔助欄位。
    features["ref_high_20d"] = features.groupby("stock_id")["high"].transform(lambda x: x.shift(1).rolling(20).max())
    features["ref_high_60d"] = features.groupby("stock_id")["high"].transform(lambda x: x.shift(1).rolling(60).max())
    features["ref_low_5d"] = features.groupby("stock_id")["low"].transform(lambda x: x.shift(1).rolling(5).min())
    features["ref_low_10d"] = features.groupby("stock_id")["low"].transform(lambda x: x.shift(1).rolling(10).min())
    features["ref_low_20d"] = features.groupby("stock_id")["low"].transform(lambda x: x.shift(1).rolling(20).min())
    features["prev_close"] = features.groupby("stock_id")["close"].shift(1)
    features["return_pct"] = (features["close"] / features["prev_close"] - 1.0) * 100.0
    universe = load_universe(data_dir, features)
    ranker._ensure_unique_trade_keys(universe, "universe.parquet")
    return ReplayResources(ranker, features, universe, output_dir, data_dir, model_dir, config_path, args.model)


def ensure_guarded_artifact(date_text: str, args: argparse.Namespace, resources: ReplayResources | None) -> Path | None:
    output_dir = resolve_path(args.guarded_dir)
    path = output_dir / f"guarded_top10_replay_{date_text}.json"
    if path.exists() and guarded_artifact_is_current(path, date_text):
        return path
    if args.no_generate_guarded:
        return None
    if resources is None:
        raise RuntimeError("guarded replay resources are not initialized")
    payload = build_guarded_replay_payload(resources, date_text, args.top_n)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    path.with_suffix(".md").write_text(guarded_render_markdown(payload), encoding="utf-8")
    return path


def guarded_artifact_is_current(path: Path, date_text: str) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    boundary = payload.get("regime_history_boundary")
    if not isinstance(boundary, dict):
        return False
    if boundary.get("end_date") != date_text:
        return False
    if int(boundary.get("future_rows_after_target") or 0) != 0:
        return False
    return True


def build_guarded_replay_payload(resources: ReplayResources, date_text: str, top_n: int) -> dict[str, Any]:
    target = pd.to_datetime(date_text).normalize()
    features = resources.features
    if not (features["trade_date"] == target).any():
        raise ValueError(f"找不到指定交易日資料: {date_text}")
    regime_start = target - pd.Timedelta(days=90)
    history = features[(features["trade_date"] >= regime_start) & (features["trade_date"] <= target)].copy()
    daily = features[features["trade_date"] == target].copy()
    if "trade_date" in resources.universe.columns:
        daily_universe = resources.universe[resources.universe["trade_date"] == target].copy()
    else:
        daily_universe = resources.universe
    valid = daily_universe["stock_id"].astype(str).str.strip().unique()
    frame = daily[daily["stock_id"].isin(valid)].copy()
    if frame.empty:
        raise ValueError(f"{date_text} 沒有可排名資料")
    float_cols = frame.select_dtypes(include=["float64"]).columns
    if len(float_cols) > 0:
        frame[float_cols] = frame[float_cols].astype("float32")
    scored = resources.ranker.calculate_scores(frame).reset_index(drop=True)
    scored["candidate_rank"] = range(1, len(scored) + 1)
    candidate_pool = scored.head(CANDIDATE_POOL_SIZE_CONTRACT).copy()
    target_for_regime = frame["date"].max() if "date" in frame else target
    market_regime = resources.ranker.market_regime_service.evaluate(history, target_date=target_for_regime)
    guarded_ranked = resources.ranker.ranking_policy.apply(
        candidate_pool,
        market_regime,
        apply_selection_guards=True,
    ).reset_index(drop=True)
    guarded_ranked["guarded_rank"] = range(1, len(guarded_ranked) + 1)
    guarded_top = guarded_ranked.head(top_n).copy()
    guarded_top = resources.ranker.portfolio_policy.apply(guarded_top, market_regime)
    guarded_top["guarded_rank"] = range(1, len(guarded_top) + 1)
    if "stock_name" not in guarded_top.columns or guarded_top["stock_name"].isna().any():
        try:
            from app.stock_names import get_stock_name
        except ImportError:
            from stock_names import get_stock_name
        guarded_top["stock_name"] = [get_stock_name(str(stock_id)) for stock_id in guarded_top["stock_id"]]
    output_json = resources.output_dir / f"guarded_top10_replay_{date_text}.json"
    output_md = output_json.with_suffix(".md")
    model_top = candidate_pool.head(top_n).copy()
    return {
        "schema_version": "guarded-top10-replay.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK",
        "task_id": "GUARDED-TOP10-REPLAY-01",
        "ranking_date": date_text,
        "contract": {
            "research_only": True,
            "does_not_train_model": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_production_ranking": True,
            "does_not_change_publish_source": True,
            "candidate_pool_rule": CANDIDATE_POOL_RULE,
            "guard_policy_source": "app.trading.ranking_policy.RankingPolicy",
            "tape_guard_source": "app.trading.tape_guard.add_tape_guard_columns",
            "chase_guard_boundary": "rr_guard WAIT_PULLBACK/WAIT_CONFIRM from RankingPolicy",
        },
        "inputs": {
            "data_dir": repo_path(resources.data_dir),
            "model": repo_path(resources.model_dir / resources.model_name),
            "config": repo_path(resources.config_path),
            "date": date_text,
            "candidate_pool_size": CANDIDATE_POOL_SIZE_CONTRACT,
            "top_n": top_n,
        },
        "regime_history_boundary": {
            "start_date": regime_start.strftime("%Y-%m-%d"),
            "end_date": target.strftime("%Y-%m-%d"),
            "future_rows_after_target": int((history["trade_date"] > target).sum()),
        },
        "outputs": {"json": repo_path(output_json), "markdown": repo_path(output_md)},
        "market_regime": {
            "label": market_regime.label,
            "risk_multiplier": clean_value(market_regime.risk_multiplier),
            "breadth_ma20": clean_value(market_regime.breadth_ma20),
        },
        "summary": guarded_build_summary(
            candidate_pool=candidate_pool,
            guarded_ranked=guarded_ranked,
            guarded_top=guarded_top,
            model_top_ids=stock_id_list(model_top),
            guarded_top_ids=stock_id_list(guarded_top),
            top_n=top_n,
        ),
        "model_top10_before_guard": rows_from_frame(model_top, rank_column="candidate_rank"),
        "candidate_pool_top80": rows_from_frame(candidate_pool, rank_column="candidate_rank"),
        "shadow_guarded_top10": rows_from_frame(guarded_top, rank_column="guarded_rank"),
    }


def clean_value(value: Any) -> Any:
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return clean_value(value.item())
    return value


def load_regime_map(path: Path | None) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    if path is None:
        matches = sorted((PROJECT_ROOT / "artifacts").glob("market_regime_history_????-??-??.json"))
        path = matches[-1] if matches else None
    if path is None or not path.exists():
        return {}, {"available": False, "source": None}
    try:
        from scripts.build_high_choppy_context_overlay import load_regime_frame, rolling_high_choppy
        from scripts.research_regime_family_training_candidates import is_big_bull
    except ImportError:
        return {}, {"available": False, "source": repo_path(path), "error": "regime helper import failed"}
    frame = load_regime_frame(path)
    frame["BIG_BULL"] = frame.apply(is_big_bull, axis=1)
    frame["HIGH_CHOPPY_CONTEXT"] = frame.apply(rolling_high_choppy, axis=1)
    result = {}
    for row in frame.itertuples(index=False):
        family = "HIGH_CHOPPY_CONTEXT" if bool(row.HIGH_CHOPPY_CONTEXT) else "BIG_BULL" if bool(row.BIG_BULL) else "OTHER"
        result[str(row.trade_date_text)] = {"family": family, "base_regime": str(getattr(row, "regime_label", "UNKNOWN"))}
    return result, {"available": True, "source": repo_path(path), "row_count": len(result)}


def simulate_variant(
    label: str,
    dates: list[str],
    items_by_date: dict[str, list[dict[str, Any]]],
    price_index: dict[str, pd.DataFrame],
    trade_dates: list[Any],
    horizons: list[int],
    args: argparse.Namespace,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    trades: list[dict[str, Any]] = []
    buckets: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for date_text in dates:
        items = items_by_date.get(date_text, [])
        entry_date = run_backtest_replay.next_market_trade_date(trade_dates, date_text, args.entry_delay_trade_days)
        if entry_date is None:
            skipped.append({"variant": label, "ranking_date": date_text, "reason": "missing_entry_date"})
            continue
        for horizon in horizons:
            horizon_trades: list[dict[str, Any]] = []
            holding_dates = run_backtest_replay.market_holding_dates(trade_dates, entry_date, horizon)
            if holding_dates is None:
                skipped.append({"variant": label, "ranking_date": date_text, "horizon": horizon, "reason": "insufficient_future_market_bars"})
                continue
            for item in items:
                stock_id = item["stock_id"]
                stock_prices = price_index.get(stock_id)
                if stock_prices is None:
                    skipped.append({"variant": label, "ranking_date": date_text, "stock_id": stock_id, "horizon": horizon, "reason": "missing_price_history"})
                    continue
                holding = run_backtest_replay.stock_holding_bars(stock_prices, holding_dates)
                if holding is None or run_backtest_replay.has_missing_ohlc(holding):
                    skipped.append({"variant": label, "ranking_date": date_text, "stock_id": stock_id, "horizon": horizon, "reason": "missing_holding_bars"})
                    continue
                outcome = run_backtest_replay.simulate_trade(holding, args.fee_rate, args.tax_rate, args.slippage_rate)
                if outcome is None:
                    skipped.append({"variant": label, "ranking_date": date_text, "stock_id": stock_id, "horizon": horizon, "reason": "invalid_ohlc_bar"})
                    continue
                trade = {
                    "variant": label,
                    "ranking_date": date_text,
                    "horizon": horizon,
                    "rank": item.get("rank"),
                    "stock_id": stock_id,
                    "stock_name": item.get("stock_name"),
                    "industry_name": item.get("industry_name"),
                    "sector_name": item.get("sector_name"),
                    "theme_tags": item.get("theme_tags", []),
                    **outcome,
                }
                trades.append(trade)
                horizon_trades.append(trade)
            if horizon_trades:
                returns = [float(item["net_return"]) for item in horizon_trades]
                buckets.append(
                    {
                        "variant": label,
                        "ranking_date": date_text,
                        "horizon": horizon,
                        "positions": len(horizon_trades),
                        "bucket_return": round(sum(returns) / len(returns), 6),
                    }
                )
    return trades, buckets, skipped


def summarize_variant(
    label: str,
    trades: list[dict[str, Any]],
    buckets: list[dict[str, Any]],
    dates: list[str],
    items_by_date: dict[str, list[dict[str, Any]]],
    regimes: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "variant": label,
        "trade_count": len(trades),
        "date_count": len(dates),
        "by_horizon": summarize_by_horizon(trades, buckets),
        "turnover": turnover_summary(dates, items_by_date),
        "concentration": concentration_summary(dates, items_by_date),
        "regime_slice": regime_slice_summary(buckets, regimes),
    }


def summarize_by_horizon(trades: list[dict[str, Any]], buckets: list[dict[str, Any]]) -> dict[str, Any]:
    result = {}
    trade_frame = pd.DataFrame(trades)
    bucket_frame = pd.DataFrame(buckets)
    for horizon in HORIZONS:
        trade_group = trade_frame[trade_frame["horizon"] == horizon] if not trade_frame.empty else pd.DataFrame()
        bucket_group = bucket_frame[bucket_frame["horizon"] == horizon] if not bucket_frame.empty else pd.DataFrame()
        returns = pd.to_numeric(trade_group.get("net_return"), errors="coerce") if not trade_group.empty else pd.Series(dtype=float)
        bucket_returns = pd.to_numeric(bucket_group.get("bucket_return"), errors="coerce") if not bucket_group.empty else pd.Series(dtype=float)
        result[str(horizon)] = {
            "trade_count": int(len(trade_group)),
            "avg_forward_return": rounded(returns.mean()) if len(returns) else None,
            "median_forward_return": rounded(returns.median()) if len(returns) else None,
            "trade_hit_rate": rounded((returns > 0).mean()) if len(returns) else None,
            "daily_bucket_count": int(len(bucket_group)),
            "daily_bucket_avg_return": rounded(bucket_returns.mean()) if len(bucket_returns) else None,
            "daily_bucket_hit_rate": rounded((bucket_returns > 0).mean()) if len(bucket_returns) else None,
            "worst_daily_bucket_return": rounded(bucket_returns.min()) if len(bucket_returns) else None,
            "overlapping_bucket_compound_proxy": rounded((1 + bucket_returns).prod() - 1) if len(bucket_returns) else None,
            "max_drawdown_proxy": rounded(max_drawdown(bucket_returns.tolist())) if len(bucket_returns) else None,
        }
    return result


def turnover_summary(dates: list[str], items_by_date: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    rows = []
    previous: set[str] | None = None
    for date_text in dates:
        current = {item["stock_id"] for item in items_by_date.get(date_text, [])}
        if previous is not None and current:
            overlap = len(previous & current)
            rows.append({"date": date_text, "overlap": overlap, "turnover": round(1 - overlap / max(len(current), 1), 6)})
        previous = current
    values = [row["turnover"] for row in rows]
    return {"observation_count": len(values), "avg_turnover": rounded(sum(values) / len(values)) if values else None, "max_turnover": max(values) if values else None}


def concentration_summary(dates: list[str], items_by_date: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    industry_shares = []
    theme_shares = []
    for date_text in dates:
        items = items_by_date.get(date_text, [])
        if not items:
            continue
        industry_counts: dict[str, int] = {}
        theme_counts: dict[str, int] = {}
        for item in items:
            industry = str(item.get("industry_name") or "UNKNOWN")
            industry_counts[industry] = industry_counts.get(industry, 0) + 1
            for tag in item.get("theme_tags") or []:
                theme_counts[str(tag)] = theme_counts.get(str(tag), 0) + 1
        industry_shares.append(max(industry_counts.values()) / len(items))
        if theme_counts:
            theme_shares.append(max(theme_counts.values()) / len(items))
    return {
        "avg_top_industry_share": rounded(sum(industry_shares) / len(industry_shares)) if industry_shares else None,
        "max_top_industry_share": rounded(max(industry_shares)) if industry_shares else None,
        "avg_top_theme_share": rounded(sum(theme_shares) / len(theme_shares)) if theme_shares else None,
        "max_top_theme_share": rounded(max(theme_shares)) if theme_shares else None,
    }


def regime_slice_summary(buckets: list[dict[str, Any]], regimes: dict[str, dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, dict[str, Any]] = {}
    for family in ("BIG_BULL", "HIGH_CHOPPY_CONTEXT", "OTHER", "UNKNOWN"):
        result[family] = {}
    by_horizon: dict[tuple[str, int], list[float]] = {}
    for bucket in buckets:
        date_text = str(bucket.get("ranking_date"))
        family = regimes.get(date_text, {}).get("family", "UNKNOWN")
        key = (family, int(bucket["horizon"]))
        by_horizon.setdefault(key, []).append(float(bucket["bucket_return"]))
    for family in result:
        for horizon in HORIZONS:
            values = by_horizon.get((family, horizon), [])
            result[family][str(horizon)] = {
                "daily_bucket_count": len(values),
                "avg_bucket_return": rounded(sum(values) / len(values)) if values else None,
                "hit_rate": rounded(sum(1 for value in values if value > 0) / len(values)) if values else None,
                "compound_return": rounded(compound(values)) if values else None,
            }
    return result


def group_return_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    frame = pd.DataFrame(rows)
    result = {}
    for horizon in HORIZONS:
        group = frame[frame["horizon"] == horizon] if not frame.empty else pd.DataFrame()
        returns = pd.to_numeric(group.get("net_return"), errors="coerce") if not group.empty else pd.Series(dtype=float)
        result[str(horizon)] = {
            "count": int(len(group)),
            "avg_return": rounded(returns.mean()) if len(returns) else None,
            "hit_rate": rounded((returns > 0).mean()) if len(returns) else None,
        }
    return result


def comparison_groups(
    dates: list[str],
    production_items: dict[str, list[dict[str, Any]]],
    guarded_items: dict[str, list[dict[str, Any]]],
    guarded_payloads: dict[str, dict[str, Any]],
    price_index: dict[str, pd.DataFrame],
    trade_dates: list[Any],
    horizons: list[int],
    args: argparse.Namespace,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    group_rows = {"guarded_added_vs_production": [], "production_removed_vs_guarded": [], "guard_blocked_model_top10": [], "guard_replacements": []}
    skipped = []
    for date_text in dates:
        production_ids = {item["stock_id"] for item in production_items.get(date_text, [])}
        guarded_ids = {item["stock_id"] for item in guarded_items.get(date_text, [])}
        payload = guarded_payloads.get(date_text, {})
        model_top = {clean_stock_id(item.get("stock_id")): item for item in payload.get("model_top10_before_guard", [])}
        guarded_top = {item["stock_id"]: item for item in guarded_items.get(date_text, [])}
        groups = {
            "guarded_added_vs_production": [item for item in guarded_items.get(date_text, []) if item["stock_id"] not in production_ids],
            "production_removed_vs_guarded": [item for item in production_items.get(date_text, []) if item["stock_id"] not in guarded_ids],
            "guard_blocked_model_top10": [dict(item, stock_id=clean_stock_id(item.get("stock_id"))) for stock_id, item in model_top.items() if stock_id not in guarded_top],
            "guard_replacements": [item for item in guarded_items.get(date_text, []) if item["stock_id"] not in model_top],
        }
        for name, items in groups.items():
            rows, miss = simulate_group_returns(name, date_text, items, price_index, trade_dates, horizons, args)
            group_rows[name].extend(rows)
            skipped.extend(miss)
    return {name: group_return_summary(rows) for name, rows in group_rows.items()}, skipped


def simulate_group_returns(
    group_name: str,
    date_text: str,
    items: list[dict[str, Any]],
    price_index: dict[str, pd.DataFrame],
    trade_dates: list[Any],
    horizons: list[int],
    args: argparse.Namespace,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = []
    skipped = []
    entry_date = run_backtest_replay.next_market_trade_date(trade_dates, date_text, args.entry_delay_trade_days)
    if entry_date is None:
        return rows, [{"group": group_name, "ranking_date": date_text, "reason": "missing_entry_date"}]
    for horizon in horizons:
        holding_dates = run_backtest_replay.market_holding_dates(trade_dates, entry_date, horizon)
        if holding_dates is None:
            skipped.append({"group": group_name, "ranking_date": date_text, "horizon": horizon, "reason": "insufficient_future_market_bars"})
            continue
        for item in items:
            stock_id = clean_stock_id(item.get("stock_id"))
            stock_prices = price_index.get(stock_id)
            if stock_prices is None:
                skipped.append({"group": group_name, "ranking_date": date_text, "stock_id": stock_id, "horizon": horizon, "reason": "missing_price_history"})
                continue
            holding = run_backtest_replay.stock_holding_bars(stock_prices, holding_dates)
            if holding is None or run_backtest_replay.has_missing_ohlc(holding):
                skipped.append({"group": group_name, "ranking_date": date_text, "stock_id": stock_id, "horizon": horizon, "reason": "missing_holding_bars"})
                continue
            outcome = run_backtest_replay.simulate_trade(holding, args.fee_rate, args.tax_rate, args.slippage_rate)
            if outcome is None:
                continue
            rows.append({"group": group_name, "ranking_date": date_text, "horizon": horizon, "stock_id": stock_id, **outcome})
    return rows, skipped


def max_drawdown(returns: list[float]) -> float:
    equity = 1.0
    peak = 1.0
    worst = 0.0
    for value in returns:
        equity *= 1 + float(value)
        peak = max(peak, equity)
        worst = min(worst, equity / peak - 1)
    return worst


def compound(values: list[float]) -> float:
    result = 1.0
    for value in values:
        result *= 1 + float(value)
    return result - 1


def rounded(value: Any, digits: int = 6) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return round(parsed, digits)


def delta(value: Any, baseline: Any) -> float | None:
    left = number(value)
    right = number(baseline)
    if left is None or right is None:
        return None
    return round(left - right, 6)


def build_comparison(production: dict[str, Any], guarded: dict[str, Any]) -> dict[str, Any]:
    rows = {}
    for horizon in HORIZONS:
        key = str(horizon)
        prod = production["by_horizon"].get(key, {})
        guard = guarded["by_horizon"].get(key, {})
        rows[key] = {
            "guarded_minus_production_daily_bucket_avg_return": delta(guard.get("daily_bucket_avg_return"), prod.get("daily_bucket_avg_return")),
            "guarded_minus_production_overlapping_bucket_compound_proxy": delta(
                guard.get("overlapping_bucket_compound_proxy"),
                prod.get("overlapping_bucket_compound_proxy"),
            ),
            "guarded_minus_production_daily_bucket_hit_rate": delta(guard.get("daily_bucket_hit_rate"), prod.get("daily_bucket_hit_rate")),
            "guarded_minus_production_max_drawdown_proxy": delta(guard.get("max_drawdown_proxy"), prod.get("max_drawdown_proxy")),
            "production": prod,
            "guarded": guard,
        }
    return rows


def decide(comparison: dict[str, Any], window_info: dict[str, Any]) -> dict[str, Any]:
    if int(window_info.get("selected_date_count") or 0) < 20:
        return {"status": "INSUFFICIENT_DATA", "promotion_ready": False, "reason": "可用日期少於 20，不能判斷績效。"}
    wins = 0
    losses = 0
    drawdown_ok = 0
    for row in comparison.values():
        avg_delta = number(row.get("guarded_minus_production_daily_bucket_avg_return")) or 0.0
        hit_delta = number(row.get("guarded_minus_production_daily_bucket_hit_rate")) or 0.0
        dd_delta = number(row.get("guarded_minus_production_max_drawdown_proxy"))
        if avg_delta > 0 and hit_delta >= 0:
            wins += 1
        if avg_delta < 0 and hit_delta <= 0:
            losses += 1
        if dd_delta is not None and dd_delta >= -0.01:
            drawdown_ok += 1
    if wins >= 3 and drawdown_ok >= 3:
        status = "GUARDED_OUTPERFORMS_RESEARCH_ONLY"
        reason = "多數 horizon 平均 bucket 報酬與 hit rate 優於 production，且 drawdown proxy 未明顯惡化；仍僅限研究。"
    elif losses >= 3:
        status = "GUARDED_UNDERPERFORMS"
        reason = "多數 horizon 報酬弱於 production。"
    else:
        status = "MIXED_MONITOR_ONLY"
        reason = "不同 horizon 或風險指標結論混合，只能監控。"
    return {"status": status, "promotion_ready": False, "reason": reason}


def run(args: argparse.Namespace) -> dict[str, Any]:
    horizons = parse_horizons(args.horizons)
    production_map, production_provenance = production_ranking_map(args.production_dir)
    price_frame = load_price_frame(resolve_path(args.features))
    trade_dates = run_backtest_replay.market_trade_dates(price_frame)
    price_index = run_backtest_replay.build_price_index(price_frame)
    dates, window_info = select_window_dates(args.window, sorted(production_map), trade_dates, args.as_of_date)
    refs = load_reference_map(PROJECT_ROOT / "data" / "reference" / "stock_industry_map.csv")
    regimes, regime_source = load_regime_map(resolve_path(args.market_regime_history) if args.market_regime_history else None)
    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    replay_resources = None if args.no_generate_guarded else prepare_replay_resources(args, output_dir)

    production_items: dict[str, list[dict[str, Any]]] = {}
    guarded_items: dict[str, list[dict[str, Any]]] = {}
    guarded_payloads: dict[str, dict[str, Any]] = {}
    guarded_outputs = []
    missing = []
    for date_text in dates:
        production_items[date_text] = read_csv_ranking(production_map[date_text], args.top_n, refs)
        guarded_path = ensure_guarded_artifact(date_text, args, replay_resources)
        if guarded_path is None:
            missing.append({"date": date_text, "reason": "missing_guarded_replay_artifact"})
            continue
        guarded, payload = read_guarded_items(guarded_path, args.top_n, refs)
        guarded_items[date_text] = guarded
        guarded_payloads[date_text] = payload
        guarded_outputs.append(repo_path(guarded_path))

    comparable_dates = [date for date in dates if date in guarded_items]
    prod_trades, prod_buckets, prod_skipped = simulate_variant("production", comparable_dates, production_items, price_index, trade_dates, horizons, args)
    guard_trades, guard_buckets, guard_skipped = simulate_variant("guarded", comparable_dates, guarded_items, price_index, trade_dates, horizons, args)
    production_summary = summarize_variant("production", prod_trades, prod_buckets, comparable_dates, production_items, regimes)
    guarded_summary = summarize_variant("guarded", guard_trades, guard_buckets, comparable_dates, guarded_items, regimes)
    comparison = build_comparison(production_summary, guarded_summary)
    group_quality, group_skipped = comparison_groups(
        comparable_dates,
        production_items,
        guarded_items,
        guarded_payloads,
        price_index,
        trade_dates,
        horizons,
        args,
    )
    decision = decide(comparison, {**window_info, "selected_date_count": len(comparable_dates)})
    run_date = datetime.now().strftime("%Y-%m-%d")
    output_json = output_dir / f"guarded_top10_performance_{args.window}_{run_date}.json"
    output_md = output_json.with_suffix(".md")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK" if decision["status"] != "INSUFFICIENT_DATA" else "INSUFFICIENT_DATA",
        "task_id": "GUARDED-TOP10-REPLAY-02",
        "contract": {
            "research_only": True,
            "performance_backtest": True,
            "candidate_pool_size": CANDIDATE_POOL_SIZE_CONTRACT,
            "candidate_pool_rule": CANDIDATE_POOL_RULE,
            "does_not_train_model": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_production_ranking": True,
            "does_not_change_publish_source": True,
            "promotion_output_disabled": True,
            "entry_timing": f"D+{args.entry_delay_trade_days} open",
            "exit_timing": "D+horizon close",
        },
        "inputs": {
            "window": args.window,
            "features": repo_path(resolve_path(args.features)),
            "production_dirs": production_provenance["production_dirs"],
            "guarded_dir": repo_path(resolve_path(args.guarded_dir)),
            "top_n": args.top_n,
            "horizons": horizons,
            "costs": {"fee_rate": args.fee_rate, "tax_rate": args.tax_rate, "slippage_rate": args.slippage_rate},
        },
        "production_baseline": production_provenance,
        "outputs": {"json": repo_path(output_json), "markdown": repo_path(output_md)},
        "window": {
            **window_info,
            "selected_dates": dates,
            "comparable_dates": comparable_dates,
            "comparable_date_count": len(comparable_dates),
            "missing": missing[:50],
        },
        "regime_source": regime_source,
        "decision": decision,
        "summary": {
            "production": production_summary,
            "guarded": guarded_summary,
            "comparison_by_horizon": comparison,
            "guarded_added_vs_removed_performance": {
                "guarded_added_vs_production": group_quality["guarded_added_vs_production"],
                "production_removed_vs_guarded": group_quality["production_removed_vs_guarded"],
            },
            "guard_hit_quality": {
                "guard_blocked_model_top10": group_quality["guard_blocked_model_top10"],
                "guard_replacements": group_quality["guard_replacements"],
            },
        },
        "guarded_replay_outputs": guarded_outputs,
        "skipped": {
            "production": prod_skipped[:200],
            "guarded": guard_skipped[:200],
            "comparison_groups": group_skipped[:200],
            "counts": {
                "production": len(prod_skipped),
                "guarded": len(guard_skipped),
                "comparison_groups": len(group_skipped),
            },
        },
    }
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output_md.write_text(render_markdown(payload), encoding="utf-8")
    return payload


def pct(value: Any) -> str:
    parsed = number(value)
    return "--" if parsed is None else f"{parsed:.2%}"


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# Guarded Top10 Performance Backtest | {payload['inputs']['window']}",
        "",
        f"- status: `{payload['status']}`",
        f"- decision: `{payload['decision']['status']}`",
        f"- promotion_ready: `{payload['decision']['promotion_ready']}`",
        f"- comparable dates: `{payload['window']['comparable_date_count']}` ({payload['window']['selected_start_date']} ~ {payload['window']['selected_end_date']})",
        f"- candidate pool: `Top{payload['contract']['candidate_pool_size']}`",
        "",
        "## Horizon Comparison",
        "",
        "| horizon | prod avg bucket | guarded avg bucket | delta | prod overlap compound proxy | guarded overlap compound proxy | delta | prod DD | guarded DD |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for horizon, row in payload["summary"]["comparison_by_horizon"].items():
        prod = row["production"]
        guard = row["guarded"]
        lines.append(
            f"| D+{horizon} | {pct(prod.get('daily_bucket_avg_return'))} | {pct(guard.get('daily_bucket_avg_return'))} | {pct(row.get('guarded_minus_production_daily_bucket_avg_return'))} | "
            f"{pct(prod.get('overlapping_bucket_compound_proxy'))} | {pct(guard.get('overlapping_bucket_compound_proxy'))} | {pct(row.get('guarded_minus_production_overlapping_bucket_compound_proxy'))} | "
            f"{pct(prod.get('max_drawdown_proxy'))} | {pct(guard.get('max_drawdown_proxy'))} |"
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"- {payload['decision']['reason']}",
            "",
            "## Guard Hit Quality",
            "",
            "Guard blocked model Top10 vs replacements, avg return:",
        ]
    )
    blocked = payload["summary"]["guard_hit_quality"]["guard_blocked_model_top10"]
    replacements = payload["summary"]["guard_hit_quality"]["guard_replacements"]
    for horizon in map(str, HORIZONS):
        lines.append(f"- D+{horizon}: blocked {pct(blocked[horizon].get('avg_return'))}, replacements {pct(replacements[horizon].get('avg_return'))}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = run(args)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "decision": payload["decision"]["status"],
                "output": payload["outputs"]["json"],
                "markdown": payload["outputs"]["markdown"],
                "comparable_date_count": payload["window"]["comparable_date_count"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
