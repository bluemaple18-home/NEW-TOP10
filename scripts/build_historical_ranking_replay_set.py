#!/usr/bin/env python3
"""用目前模型產生研究用歷史 ranking set。

此腳本只寫指定 output-dir，不改 production ranking，不訓練模型。
用途是替 sealed / replay / window stability 建立足夠樣本。
"""

from __future__ import annotations

import argparse
import json
import sys
from contextlib import redirect_stdout
from datetime import date, datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agent_b_ranking import StockRanker
from app.modeling.feature_contract import load_m4_feature_frame
from app.signals.price_patterns import PRICE_PATTERN_COLUMNS, add_price_patterns


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build historical ranking replay set with current model")
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--data-dir", default="data/clean")
    parser.add_argument("--model-dir", default="models")
    parser.add_argument("--config", default="config/signals.yaml")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--stride", type=int, default=1, help="每 N 個交易日取一天")
    parser.add_argument("--max-dates", type=int, default=None)
    parser.add_argument("--legacy-per-date-load", action="store_true", help="使用舊版逐日重載 feature frame；只保留作回歸對照")
    parser.add_argument("--manifest", default=None)
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


def load_trade_dates(data_dir: Path, start_date: str, end_date: str, stride: int, max_dates: int | None) -> list[str]:
    features_path = data_dir / "features.parquet"
    if not features_path.exists():
        raise FileNotFoundError(f"features parquet 不存在：{features_path}")
    frame = pd.read_parquet(features_path, columns=["date"])
    dates = pd.to_datetime(frame["date"], errors="coerce").dropna().dt.normalize().drop_duplicates().sort_values()
    start = pd.to_datetime(start_date).normalize()
    end = pd.to_datetime(end_date).normalize()
    selected = [item.strftime("%Y-%m-%d") for item in dates if start <= item <= end]
    if stride > 1:
        selected = selected[::stride]
    if max_dates is not None:
        selected = selected[:max_dates]
    if not selected:
        raise ValueError(f"指定區間沒有交易日：{start_date}~{end_date}")
    return selected


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


def prepare_batch_frames(ranker: StockRanker) -> tuple[pd.DataFrame, pd.DataFrame]:
    features, feature_metadata = load_m4_feature_frame(
        data_dir=ranker.data_dir,
        project_root=ranker._project_root(),
        config_path=ranker.config_path,
    )
    features.attrs["m4_feature_metadata"] = feature_metadata
    ranker._ensure_unique_trade_keys(features, "m4_feature_frame")
    features = features.sort_values(["stock_id", "trade_date"]).copy()
    missing_price_patterns = [column for column in PRICE_PATTERN_COLUMNS if column not in features.columns]
    if missing_price_patterns:
        # 舊歷史 features 可能缺新型態欄位；研究 ranking 需補齊訓練契約，但不回寫 production data。
        pattern_source = features[["date", "stock_id", "high", "low", "close"]].copy()
        pattern_frame = add_price_patterns(pattern_source)
        for column in PRICE_PATTERN_COLUMNS:
            features[column] = pattern_frame[column].to_numpy()
    # 歷史研究一次算完整壓力線，避免逐日重建 rolling feature frame。
    features["ref_high_20d"] = features.groupby("stock_id")["high"].transform(lambda x: x.shift(1).rolling(20).max())
    features["ref_high_60d"] = features.groupby("stock_id")["high"].transform(lambda x: x.shift(1).rolling(60).max())
    universe = load_universe(ranker.data_dir, features)
    ranker._ensure_unique_trade_keys(universe, "universe.parquet")
    return features, universe


def daily_universe(universe: pd.DataFrame, target_trade_date: pd.Timestamp) -> pd.DataFrame:
    if "trade_date" in universe.columns:
        return universe[universe["trade_date"] == target_trade_date].copy()
    return universe


def stock_names(stock_ids: pd.Series) -> list[str]:
    try:
        from app.stock_names import get_stock_name
    except ImportError:
        from stock_names import get_stock_name
    return [get_stock_name(str(stock_id)) for stock_id in stock_ids]


def run_batch_ranking_for_date(
    ranker: StockRanker,
    features: pd.DataFrame,
    universe: pd.DataFrame,
    date_text: str,
) -> Path:
    target_trade_date = pd.to_datetime(date_text).normalize()
    if not (features["trade_date"] == target_trade_date).any():
        raise ValueError(f"找不到指定交易日資料: {date_text}")
    history_df = features[features["trade_date"] >= target_trade_date - pd.Timedelta(days=90)].copy()
    daily_features = features[features["trade_date"] == target_trade_date].copy()
    valid_stocks = daily_universe(universe, target_trade_date)["stock_id"].astype(str).str.strip().unique()
    df = daily_features[daily_features["stock_id"].isin(valid_stocks)].copy()
    if df.empty:
        raise ValueError(f"指定交易日無 universe 可排名: {date_text}")
    float_cols = df.select_dtypes(include=["float64"]).columns
    if len(float_cols) > 0:
        df[float_cols] = df[float_cols].astype("float32")

    rank_df = ranker.calculate_scores(df)
    target_for_regime = df["date"].max() if "date" in df else target_trade_date
    market_regime = ranker.market_regime_service.evaluate(history_df, target_date=target_for_regime)
    rank_df = ranker.ranking_policy.apply(rank_df, market_regime)
    top10 = rank_df.head(10).copy()
    top10 = ranker.portfolio_policy.apply(top10, market_regime)
    if "stock_name" not in top10.columns or top10["stock_name"].isnull().any():
        top10["stock_name"] = stock_names(top10["stock_id"])
    today_str = pd.Timestamp(top10["trade_date"].max()).strftime("%Y-%m-%d") if "trade_date" in top10.columns else date_text
    path = ranker.artifact_dir / f"ranking_{today_str}.csv"
    out_cols = [
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
    top10[[col for col in out_cols if col in top10.columns]].to_csv(path, index=False, encoding="utf-8-sig")
    return path


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    data_dir = resolve_path(args.data_dir)
    model_dir = resolve_path(args.model_dir)
    config_path = resolve_path(args.config)
    assert data_dir is not None and model_dir is not None and config_path is not None

    run_date = date.today().isoformat()
    output_dir = resolve_path(args.output_dir) or PROJECT_ROOT / "artifacts" / "research_rankings" / f"current_model_{args.start_date}_{args.end_date}"
    manifest_path = resolve_path(args.manifest) or output_dir / "manifest.json"
    output_dir.mkdir(parents=True, exist_ok=True)

    dates = load_trade_dates(
        data_dir=data_dir,
        start_date=args.start_date,
        end_date=args.end_date,
        stride=max(args.stride, 1),
        max_dates=args.max_dates,
    )

    ranker = StockRanker(
        data_dir=str(data_dir),
        model_dir=str(model_dir),
        artifact_dir=str(output_dir),
        config_path=str(config_path),
        generate_report=False,
        explain_top_n=0,
    )
    ranker.load_model()
    batch_frames = None if args.legacy_per_date_load else prepare_batch_frames(ranker)

    outputs: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for date_text in dates:
        try:
            captured_stdout = StringIO()
            with redirect_stdout(captured_stdout):
                if batch_frames is None:
                    path = ranker.run_ranking(date_text)
                else:
                    features, universe = batch_frames
                    path = run_batch_ranking_for_date(ranker, features, universe, date_text)
            outputs.append({"date": date_text, "path": repo_path(Path(path)), "stdout_tail": captured_stdout.getvalue()[-1000:]})
        except Exception as exc:
            failures.append({"date": date_text, "error": str(exc)})

    payload = {
        "schema_version": "historical-ranking-replay-set.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_date": run_date,
        "status": "OK" if not failures else "FAILED",
        "contract": {
            "research_only": True,
            "does_not_train_model": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_production_ranking": True,
        },
        "inputs": {
            "data_dir": repo_path(data_dir),
            "model_dir": repo_path(model_dir),
            "config": repo_path(config_path),
            "start_date": args.start_date,
            "end_date": args.end_date,
            "stride": args.stride,
            "max_dates": args.max_dates,
            "batch_mode": not args.legacy_per_date_load,
        },
        "outputs": {
            "output_dir": repo_path(output_dir),
            "manifest": repo_path(manifest_path),
            "ranking_count": len(outputs),
            "rankings": outputs,
        },
        "failures": failures,
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return payload


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "output_dir": payload["outputs"]["output_dir"],
                "manifest": payload["outputs"]["manifest"],
                "ranking_count": payload["outputs"]["ranking_count"],
                "failure_count": len(payload["failures"]),
            },
            ensure_ascii=False,
        )
    )
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
