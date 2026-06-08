#!/usr/bin/env python3
"""alpha constrained overlay 的 portfolio replay candidate。

讀 overlay replay 的每日 TopN 清單，用 OHLC 模擬 D+1 open 進、D+N close 出，
比較 baseline 與 overlay 的扣成本等權 bucket；不保存模型、不改 production ranking。
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
import sys
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import run_backtest_replay  # noqa: E402


OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "model_experiments"
SCHEMA_VERSION = "alpha-candidate-overlay-portfolio-replay.v1"
DECISION_PROMOTE = "PROMOTE_TO_PROMOTION_REVIEW_CANDIDATE"
DECISION_REJECTED = "REJECTED"
MIN_RETURN_DELTA = 0.0
MIN_POSITIVE_FOLDS = 2
MAX_TURNOVER_DELTA = 0.10
MAX_GROUP_EXPOSURE_DELTA = 0.0
MIN_FOLDS = 3
MIN_FOLD_DATES = 20
MIN_BUCKET_VALID_TRADES = 10
GROUP_EXPOSURE_REQUIRED = True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="research alpha constrained overlay portfolio replay")
    parser.add_argument("--overlay-replay", default=None)
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument("--group-map", default="data/reference/stock_industry_map.csv")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--horizon", type=int, default=10)
    parser.add_argument("--entry-delay-trade-days", type=int, default=1)
    parser.add_argument("--fee-rate", type=float, default=0.001425)
    parser.add_argument("--tax-rate", type=float, default=0.003)
    parser.add_argument("--slippage-rate", type=float, default=0.001)
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


def latest_overlay_replay() -> Path | None:
    matches = sorted(OUTPUT_DIR.glob("alpha_candidate_overlay_replay_????-??-??.json"))
    return matches[-1] if matches else None


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_group_map(path: Path | None) -> dict[str, str]:
    if path is None:
        raise RuntimeError("group map path resolution failed")
    if not path.exists():
        raise FileNotFoundError(f"group map missing: {path}")
    frame = pd.read_csv(path, dtype={"stock_id": str})
    if "stock_id" not in frame.columns or "industry_name" not in frame.columns:
        raise RuntimeError("group map must contain stock_id and industry_name columns")
    return {
        str(stock_id).zfill(4): str(industry).strip()
        for stock_id, industry in frame[["stock_id", "industry_name"]].dropna().itertuples(index=False, name=None)
        if str(industry).strip()
    }


def max_drawdown(returns: list[float]) -> float:
    equity = 1.0
    peak = 1.0
    worst = 0.0
    for value in returns:
        equity *= 1 + float(value)
        peak = max(peak, equity)
        worst = min(worst, equity / peak - 1)
    return round(worst, 6)


def turnover(rows: list[dict[str, Any]], key: str) -> float | None:
    if len(rows) < 2:
        return None
    values: list[float] = []
    previous: set[str] | None = None
    for row in rows:
        current = set(row[key])
        if previous is not None:
            values.append(1 - len(previous & current) / max(len(current), 1))
        previous = current
    return round(float(pd.Series(values).mean()), 6) if values else None


def max_group_exposure(stock_ids: list[str], group_map: dict[str, str]) -> float | None:
    if not stock_ids or not group_map:
        return None
    groups = [group_map.get(str(stock_id).zfill(4), "未分類") for stock_id in stock_ids]
    counts = pd.Series(groups).value_counts()
    return round(float(counts.iloc[0] / len(stock_ids)), 6) if not counts.empty else None


def simulate_stock(
    price_index: dict[str, pd.DataFrame],
    trade_dates: list[Any],
    ranking_date_text: str,
    stock_id: str,
    args: argparse.Namespace,
) -> dict[str, Any] | None:
    stock_prices = price_index.get(str(stock_id).zfill(4))
    if stock_prices is None:
        return None
    entry_date = run_backtest_replay.next_market_trade_date(trade_dates, ranking_date_text, args.entry_delay_trade_days)
    if entry_date is None:
        return None
    holding_dates = run_backtest_replay.market_holding_dates(trade_dates, entry_date, args.horizon)
    if holding_dates is None:
        return None
    holding = run_backtest_replay.stock_holding_bars(stock_prices, holding_dates)
    if holding is None or run_backtest_replay.has_missing_ohlc(holding):
        return None
    outcome = run_backtest_replay.simulate_trade(
        holding=holding,
        fee_rate=args.fee_rate,
        tax_rate=args.tax_rate,
        slippage_rate=args.slippage_rate,
    )
    if outcome is None:
        return None
    return {
        "stock_id": str(stock_id).zfill(4),
        "entry_date": outcome["entry_date"],
        "exit_date": outcome["exit_date"],
        "net_return": outcome["net_return"],
        "mae": outcome["mae"],
        "mfe": outcome["mfe"],
    }


def simulate_bucket(
    price_index: dict[str, pd.DataFrame],
    trade_dates: list[Any],
    ranking_date_text: str,
    stock_ids: list[str],
    group_map: dict[str, str],
    args: argparse.Namespace,
) -> dict[str, Any]:
    trades = [
        trade
        for stock_id in stock_ids
        if (trade := simulate_stock(price_index, trade_dates, ranking_date_text, stock_id, args)) is not None
    ]
    returns = pd.Series([trade["net_return"] for trade in trades], dtype=float)
    return {
        "stock_ids": [str(stock_id).zfill(4) for stock_id in stock_ids],
        "valid_trade_count": int(len(trades)),
        "avg_net_return": round(float(returns.mean()), 6) if not returns.empty else None,
        "hit_rate": round(float((returns > 0).mean()), 6) if not returns.empty else None,
        "avg_mae": round(float(pd.Series([trade["mae"] for trade in trades], dtype=float).mean()), 6) if trades else None,
        "avg_mfe": round(float(pd.Series([trade["mfe"] for trade in trades], dtype=float).mean()), 6) if trades else None,
        "max_group_exposure": max_group_exposure(stock_ids, group_map),
        "trades": trades,
    }


def daily_rows(payload: dict[str, Any], args: argparse.Namespace) -> list[dict[str, Any]]:
    features_path = resolve_path(args.features)
    if features_path is None:
        raise RuntimeError("features path resolution failed")
    price_frame = run_backtest_replay.load_price_frame(features_path)
    trade_dates = run_backtest_replay.market_trade_dates(price_frame)
    price_index = run_backtest_replay.build_price_index(price_frame)
    group_map = load_group_map(resolve_path(args.group_map))
    rows: list[dict[str, Any]] = []
    for row in payload.get("daily", []):
        date_text = str(row["trade_date"])
        baseline_ids = [str(stock_id).zfill(4) for stock_id in row.get("baseline_stock_ids", [])]
        overlay_ids = [str(stock_id).zfill(4) for stock_id in row.get("overlay_stock_ids", [])]
        baseline = simulate_bucket(price_index, trade_dates, date_text, baseline_ids, group_map, args)
        overlay = simulate_bucket(price_index, trade_dates, date_text, overlay_ids, group_map, args)
        baseline_return = baseline.get("avg_net_return")
        overlay_return = overlay.get("avg_net_return")
        rows.append(
            {
                "fold": row.get("fold"),
                "ranking_date": date_text,
                "baseline": baseline,
                "overlay": overlay,
                "return_delta": round(float(overlay_return) - float(baseline_return), 6)
                if overlay_return is not None and baseline_return is not None
                else None,
                "max_group_exposure_delta": round(float(overlay["max_group_exposure"]) - float(baseline["max_group_exposure"]), 6)
                if overlay.get("max_group_exposure") is not None and baseline.get("max_group_exposure") is not None
                else None,
            }
        )
    return rows


def summarize_variant(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    returns = [row[key]["avg_net_return"] for row in rows if row[key].get("avg_net_return") is not None]
    hit_rates = [row[key]["hit_rate"] for row in rows if row[key].get("hit_rate") is not None]
    group_exposures = [row[key]["max_group_exposure"] for row in rows if row[key].get("max_group_exposure") is not None]
    valid_trade_counts = [int(row[key].get("valid_trade_count") or 0) for row in rows]
    return {
        "date_count": len(returns),
        "avg_net_return": round(float(pd.Series(returns).mean()), 6) if returns else None,
        "hit_rate": round(float(pd.Series(hit_rates).mean()), 6) if hit_rates else None,
        "compounded_return": round(float((1 + pd.Series(returns, dtype=float)).prod() - 1), 6) if returns else None,
        "max_drawdown": max_drawdown(returns) if returns else None,
        "turnover": turnover([{f"{key}_stock_ids": row[key]["stock_ids"]} for row in rows], f"{key}_stock_ids"),
        "avg_max_group_exposure": round(float(pd.Series(group_exposures).mean()), 6) if group_exposures else None,
        "min_valid_trade_count": min(valid_trade_counts) if valid_trade_counts else 0,
        "incomplete_bucket_count": int(sum(value < MIN_BUCKET_VALID_TRADES for value in valid_trade_counts)),
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    baseline = summarize_variant(rows, "baseline")
    overlay = summarize_variant(rows, "overlay")
    deltas = [row["return_delta"] for row in rows if row.get("return_delta") is not None]
    group_deltas = [row["max_group_exposure_delta"] for row in rows if row.get("max_group_exposure_delta") is not None]
    folds = sorted({row.get("fold") for row in rows if row.get("fold") is not None})
    fold_rows = []
    for fold in folds:
        subset = [row for row in rows if row.get("fold") == fold]
        fold_rows.append(
            {
                "fold": fold,
                "baseline": summarize_variant(subset, "baseline"),
                "overlay": summarize_variant(subset, "overlay"),
                "return_delta": round(float(pd.Series([row["return_delta"] for row in subset if row.get("return_delta") is not None]).mean()), 6)
                if subset
                else None,
            }
        )
    return {
        "baseline": baseline,
        "overlay": overlay,
        "fold_count": len(fold_rows),
        "return_delta": round(float(pd.Series(deltas).mean()), 6) if deltas else None,
        "positive_day_count": int(sum(1 for value in deltas if value > 0)),
        "negative_day_count": int(sum(1 for value in deltas if value <= 0)),
        "positive_fold_count": int(sum(1 for row in fold_rows if (row.get("return_delta") or 0) > MIN_RETURN_DELTA)),
        "max_drawdown_delta": round(float(overlay["max_drawdown"]) - float(baseline["max_drawdown"]), 6)
        if overlay.get("max_drawdown") is not None and baseline.get("max_drawdown") is not None
        else None,
        "turnover_delta": round(float(overlay["turnover"]) - float(baseline["turnover"]), 6)
        if overlay.get("turnover") is not None and baseline.get("turnover") is not None
        else None,
        "avg_max_group_exposure_delta": round(float(pd.Series(group_deltas).mean()), 6) if group_deltas else None,
        "folds": fold_rows,
    }


def gate_failures(summary: dict[str, Any]) -> list[str]:
    failed: list[str] = []
    if summary.get("return_delta") is None or float(summary["return_delta"]) <= MIN_RETURN_DELTA:
        failed.append("return_delta<=0")
    if int(summary.get("positive_fold_count") or 0) < MIN_POSITIVE_FOLDS:
        failed.append(f"positive_folds<{MIN_POSITIVE_FOLDS}")
    if int(summary.get("fold_count") or 0) < MIN_FOLDS:
        failed.append(f"fold_count<{MIN_FOLDS}")
    for row in summary.get("folds", []) or []:
        fold = row.get("fold")
        baseline_dates = int((row.get("baseline") or {}).get("date_count") or 0)
        overlay_dates = int((row.get("overlay") or {}).get("date_count") or 0)
        if baseline_dates < MIN_FOLD_DATES or overlay_dates < MIN_FOLD_DATES:
            failed.append(f"fold_{fold}_date_count<{MIN_FOLD_DATES}")
    for key in ("baseline", "overlay"):
        variant = summary.get(key) or {}
        if int(variant.get("min_valid_trade_count") or 0) < MIN_BUCKET_VALID_TRADES:
            failed.append(f"{key}_min_valid_trade_count<{MIN_BUCKET_VALID_TRADES}")
        if int(variant.get("incomplete_bucket_count") or 0) > 0:
            failed.append(f"{key}_incomplete_bucket_count>0")
    if summary.get("max_drawdown_delta") is None or float(summary["max_drawdown_delta"]) < 0:
        failed.append("max_drawdown_worse")
    if summary.get("turnover_delta") is None or float(summary["turnover_delta"]) > MAX_TURNOVER_DELTA:
        failed.append(f"turnover_delta>{MAX_TURNOVER_DELTA}")
    if GROUP_EXPOSURE_REQUIRED and summary.get("avg_max_group_exposure_delta") is None:
        failed.append("group_exposure_missing")
    if summary.get("avg_max_group_exposure_delta") is not None and float(summary["avg_max_group_exposure_delta"]) > MAX_GROUP_EXPOSURE_DELTA:
        failed.append("group_exposure_worse")
    return failed


def decision_for(summary: dict[str, Any]) -> tuple[str, str, list[str]]:
    failed = gate_failures(summary)
    if failed:
        return DECISION_REJECTED, "portfolio replay 未通過：" + ", ".join(failed), failed
    return DECISION_PROMOTE, "portfolio replay 通過成本、回撤、turnover 與集中度 gate；可進 promotion review candidate。", []


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    overlay_replay_path = resolve_path(args.overlay_replay) or latest_overlay_replay()
    if overlay_replay_path is None:
        raise FileNotFoundError("找不到 alpha_candidate_overlay_replay_YYYY-MM-DD.json")
    overlay_replay = load_json(overlay_replay_path)
    rows = daily_rows(overlay_replay, args)
    summary = summarize(rows)
    decision, rationale, failed = decision_for(summary)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK",
        "research_question": "constrained alpha overlay 扣成本後是否優於 baseline portfolio bucket？",
        "layer": "trading",
        "pre_registered": True,
        "decision": decision,
        "decision_rationale": rationale,
        "decision_policy": {
            "min_return_delta": MIN_RETURN_DELTA,
            "min_positive_folds": MIN_POSITIVE_FOLDS,
            "min_folds": MIN_FOLDS,
            "min_fold_dates": MIN_FOLD_DATES,
            "min_bucket_valid_trades": MIN_BUCKET_VALID_TRADES,
            "max_turnover_delta": MAX_TURNOVER_DELTA,
            "max_group_exposure_delta": MAX_GROUP_EXPOSURE_DELTA,
            "group_exposure_required": GROUP_EXPOSURE_REQUIRED,
            "max_drawdown_must_not_worsen": True,
            "production_promotion_allowed": False,
        },
        "decision_diagnostics": {
            "failed": failed,
        },
        "contract": {
            "research_only": True,
            "portfolio_bucket_proxy": True,
            "does_not_train_model": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_write_production_features": True,
            "does_not_change_risk_adjusted_score": True,
            "does_not_change_production_ranking": True,
            "production_promotion_allowed": False,
            "entry_timing": f"D+{args.entry_delay_trade_days} open",
            "exit_timing": f"D+{args.horizon} close",
        },
        "inputs": {
            "overlay_replay": repo_path(overlay_replay_path),
            "features": repo_path(resolve_path(args.features)),
            "group_map": repo_path(resolve_path(args.group_map)),
            "horizon": args.horizon,
            "entry_delay_trade_days": args.entry_delay_trade_days,
            "costs": {
                "fee_rate": args.fee_rate,
                "tax_rate": args.tax_rate,
                "slippage_rate": args.slippage_rate,
            },
        },
        "summary": summary,
        "daily": rows,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Alpha Candidate Overlay Portfolio Replay",
        "",
        f"- decision：`{payload['decision']}`",
        f"- decision_rationale：{payload['decision_rationale']}",
        f"- return_delta：`{summary['return_delta']}`",
        f"- max_drawdown_delta：`{summary['max_drawdown_delta']}`",
        f"- turnover_delta：`{summary['turnover_delta']}`",
        f"- avg_max_group_exposure_delta：`{summary['avg_max_group_exposure_delta']}`",
        f"- production_promotion_allowed：`{payload['contract']['production_promotion_allowed']}`",
        "",
        "| Variant | Avg Net Return | Hit Rate | Compounded | Max DD | Turnover | Avg Max Group |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for key in ("baseline", "overlay"):
        item = summary[key]
        lines.append(
            f"| {key} | {item.get('avg_net_return')} | {item.get('hit_rate')} | {item.get('compounded_return')} | "
            f"{item.get('max_drawdown')} | {item.get('turnover')} | {item.get('avg_max_group_exposure')} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = resolve_path(args.output) or OUTPUT_DIR / f"alpha_candidate_overlay_portfolio_replay_{args.date}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output), "decision": payload["decision"], **payload["summary"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
