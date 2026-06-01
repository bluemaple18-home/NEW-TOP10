#!/usr/bin/env python3
"""產生 BIG_BULL family-only shadow ranking。

這支腳本只做 research artifact：模型只存在記憶體、輸出只寫到
artifacts/backtest/shadow_rankings_big_bull，不改 production ranking。
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import lightgbm as lgb
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.stock_names import get_stock_name  # noqa: E402
from scripts import research_regime_family_training_candidates as candidates  # noqa: E402


OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "backtest" / "shadow_rankings_big_bull"
SCHEMA_VERSION = "big-bull-shadow-ranking.v1"
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
    parser = argparse.ArgumentParser(description="build BIG_BULL family-only shadow ranking CSVs")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--data-dir", default="data/clean")
    parser.add_argument("--market-regime-history", default="artifacts/market_regime_history_2026-05-31.json")
    parser.add_argument("--dates-from-dir", default="artifacts/backtest/historical_rankings_current_model")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR.relative_to(PROJECT_ROOT)))
    parser.add_argument("--family", default="BIG_BULL")
    parser.add_argument("--horizon", type=int, default=10)
    parser.add_argument("--threshold", type=float, default=0.05)
    parser.add_argument("--embargo-trade-days", type=int, default=10)
    parser.add_argument("--min-train-family-dates", type=int, default=18)
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--num-boost-round", type=int, default=120)
    parser.add_argument("--max-ranking-files", type=int, default=None)
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


def ranking_date(path: Path) -> str:
    match = re.match(r"ranking_(\d{4}-\d{2}-\d{2})\.csv$", path.name)
    if not match:
        raise ValueError(f"ranking 檔名無法解析日期：{path}")
    return match.group(1)


def ranking_dates(path: Path, max_files: int | None) -> list[str]:
    files = sorted(
        [item for item in path.glob("ranking_*.csv") if re.match(r"ranking_\d{4}-\d{2}-\d{2}\.csv$", item.name)],
        key=ranking_date,
    )
    if not files:
        raise FileNotFoundError(f"找不到 ranking_*.csv：{path}")
    selected = files[-max_files:] if max_files else files
    return [ranking_date(item) for item in selected]


def training_dates_for_target(all_dates: list[pd.Timestamp], target: pd.Timestamp, embargo: int) -> list[pd.Timestamp]:
    ordered = sorted(pd.to_datetime(all_dates).unique())
    prior = [value for value in ordered if value < target]
    if embargo > 0:
        prior = prior[:-embargo] if len(prior) > embargo else []
    return prior


def train_model(train: pd.DataFrame, features: list[str], rounds: int) -> lgb.Booster:
    return lgb.train(
        candidates.model_params(),
        lgb.Dataset(train[features], label=train["target"], feature_name=features),
        num_boost_round=rounds,
    )


def stock_name(stock_id: str) -> str:
    try:
        return get_stock_name(stock_id)
    except Exception:
        return stock_id


def build_shadow_frame(day: pd.DataFrame, features: list[str], model: lgb.Booster, top_n: int, family: str) -> pd.DataFrame:
    scored = day.copy()
    scored["model_prob"] = model.predict(scored[features])
    scored = scored.sort_values("model_prob", ascending=False).head(top_n).copy()
    gross_exposure = 0.65
    max_position_weight = 0.2
    target_weight = round(min(max_position_weight, gross_exposure / max(len(scored), 1)), 6)
    allocated = round(target_weight * len(scored), 6)
    scored["stock_id"] = scored["stock_id"].astype(str).str.zfill(4)
    scored["stock_name"] = [stock_name(stock_id) for stock_id in scored["stock_id"]]
    scored["risk_adjusted_score"] = scored["model_prob"]
    scored["final_score"] = scored["model_prob"]
    scored["prediction_score"] = scored["model_prob"]
    scored["rule_score"] = 0.0
    scored["setup_score"] = 0.0
    scored["quality_score"] = 0.0
    scored["risk_penalty"] = 0.0
    scored["suggested_weight"] = target_weight
    scored["max_position_weight"] = max_position_weight
    scored["gross_exposure"] = gross_exposure
    scored["allocated_exposure"] = allocated
    scored["cash_weight"] = round(max(0.0, 1 - allocated), 6)
    scored["exposure_note"] = f"{family} research-only family model shadow ranking"
    scored["risk_reward"] = None
    scored["market_regime"] = family
    scored["reasons"] = "BIG_BULL family-only in-memory model ranking; research-only, not production evidence"
    return scored


def write_ranking(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = [col for col in OUT_COLS if col in frame.columns]
    frame[cols].to_csv(path, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_MINIMAL)


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    family = args.family.strip().upper()
    if family != "BIG_BULL":
        raise ValueError("此 shadow ranking builder 只允許 BIG_BULL family")
    dates_dir = resolve_path(args.dates_from_dir)
    output_dir = resolve_path(args.output_dir)
    if dates_dir is None or output_dir is None:
        raise RuntimeError("path resolution failed")
    requested_dates = ranking_dates(dates_dir, args.max_ranking_files)
    frame_args = argparse.Namespace(
        data_dir=args.data_dir,
        market_regime_history=args.market_regime_history,
        horizon=args.horizon,
        threshold=args.threshold,
    )
    frame, features, _regimes = candidates.labeled_frame(frame_args, [family])
    frame = frame.sort_values(["trade_date", "stock_id"]).copy()
    all_dates = sorted(pd.to_datetime(frame["trade_date"]).drop_duplicates().tolist())
    outputs: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for date_text in requested_dates:
        target = pd.Timestamp(date_text)
        day = frame[(frame["trade_date"] == target) & frame[f"family_{family}"]].copy()
        if day.empty:
            skipped.append({"date": date_text, "reason": "not_big_bull_family_date"})
            continue
        train_dates = training_dates_for_target(all_dates, target, args.embargo_trade_days)
        train = frame[frame["trade_date"].isin(train_dates) & frame[f"family_{family}"]].copy()
        train_family_dates = int(pd.to_datetime(train["trade_date"]).nunique())
        if train_family_dates < args.min_train_family_dates or train["target"].nunique() < 2:
            skipped.append(
                {
                    "date": date_text,
                    "reason": "insufficient_family_training_window",
                    "train_family_dates": train_family_dates,
                    "target_classes": int(train["target"].nunique()),
                }
            )
            continue
        model = train_model(train, features, args.num_boost_round)
        shadow = build_shadow_frame(day, features, model, args.top_n, family)
        out_path = output_dir / f"ranking_{date_text}.csv"
        write_ranking(out_path, shadow)
        outputs.append(
            {
                "date": date_text,
                "ranking": repo_path(out_path),
                "train_start_date": pd.Timestamp(min(train_dates)).date().isoformat() if train_dates else None,
                "train_end_date": pd.Timestamp(max(train_dates)).date().isoformat() if train_dates else None,
                "train_family_dates": train_family_dates,
                "ranked_count": int(len(shadow)),
            }
        )
    summary_path = output_dir / "big_bull_shadow_ranking.json"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK" if outputs else "WARN",
        "family": family,
        "contract": {
            "research_only": True,
            "in_memory_models_only": True,
            "family_only_training": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_risk_adjusted_score": True,
            "does_not_change_production_ranking": True,
            "production_promotion_allowed": False,
            "ranking_followup_only": True,
            "no_hindsight_policy": {
                "train_dates_end_before_ranking_date": True,
                "embargo_trade_days": args.embargo_trade_days,
                "family_definitions_pre_registered": True,
                "diagnostic_failures_cannot_define_same_run_filters": True,
            },
        },
        "inputs": {
            "dates_from_dir": repo_path(dates_dir),
            "output_dir": repo_path(output_dir),
            "data_dir": repo_path(resolve_path(args.data_dir)),
            "market_regime_history": repo_path(resolve_path(args.market_regime_history)),
            "requested_dates": requested_dates,
            "top_n": args.top_n,
            "num_boost_round": args.num_boost_round,
            "feature_count": len(features),
        },
        "summary": {
            "ranking_count": len(outputs),
            "skipped_count": len(skipped),
            "start_date": outputs[0]["date"] if outputs else None,
            "end_date": outputs[-1]["date"] if outputs else None,
            "summary_path": repo_path(summary_path),
        },
        "outputs": outputs,
        "skipped": skipped,
    }


def write_markdown(payload: dict[str, Any], output: Path) -> None:
    lines = [
        "# BIG_BULL Shadow Ranking",
        "",
        f"- status: {payload['status']}",
        f"- family: {payload['family']}",
        f"- ranking_count: {payload['summary']['ranking_count']}",
        f"- skipped_count: {payload['summary']['skipped_count']}",
        f"- production_promotion_allowed: {payload['contract']['production_promotion_allowed']}",
        "",
        "## Outputs",
    ]
    for row in payload.get("outputs", []):
        lines.append(
            f"- {row['date']}: {row['ranking']} "
            f"(train={row['train_start_date']}~{row['train_end_date']}, family_days={row['train_family_dates']})"
        )
    output.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    output_dir = resolve_path(args.output_dir)
    if output_dir is None:
        raise RuntimeError("output path resolution failed")
    payload = build_payload(args)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "big_bull_shadow_ranking.json"
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    write_markdown(payload, summary_path)
    print(json.dumps({"status": payload["status"], "output": repo_path(summary_path), **payload["summary"]}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
