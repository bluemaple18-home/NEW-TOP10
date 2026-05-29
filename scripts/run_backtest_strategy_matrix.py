#!/usr/bin/env python3
"""執行 portfolio replay 策略矩陣。

此腳本只讀既有 ranking artifacts 與 features parquet，不訓練模型、不重跑 ETL。
用途是比較 horizon、停損、停利、同族群曝險上限等參數組合的穩定度。
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import run_portfolio_replay  # noqa: E402


SCHEMA_VERSION = "backtest-strategy-matrix.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="run backtest strategy matrix")
    parser.add_argument("--rankings-dir", default="artifacts")
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument("--max-ranking-files", type=int, default=8)
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--horizons", default="3,5,10")
    parser.add_argument("--stop-loss-pcts", default="none,0.08")
    parser.add_argument("--take-profit-pcts", default="none,0.15")
    parser.add_argument("--max-group-exposures", default="none,0.35")
    parser.add_argument("--max-gross-exposure", type=float, default=0.65)
    parser.add_argument("--max-position-weight", type=float, default=0.2)
    parser.add_argument("--fee-rate", type=float, default=0.001425)
    parser.add_argument("--tax-rate", type=float, default=0.003)
    parser.add_argument("--slippage-rate", type=float, default=0.001)
    parser.add_argument("--same-day-hit-priority", choices=["stop_loss", "take_profit"], default="stop_loss")
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def parse_int_list(value: str) -> list[int]:
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def parse_optional_float_list(value: str) -> list[float | None]:
    result: list[float | None] = []
    for item in value.split(","):
        token = item.strip().lower()
        if not token:
            continue
        result.append(None if token in {"none", "null", "-"} else float(token))
    return result


def replay_args(base: argparse.Namespace, scenario: dict[str, Any]) -> argparse.Namespace:
    return argparse.Namespace(
        rankings_dir=base.rankings_dir,
        features=base.features,
        horizon=scenario["horizon"],
        top_n=base.top_n,
        max_ranking_files=base.max_ranking_files,
        initial_cash=1.0,
        max_gross_exposure=base.max_gross_exposure,
        max_position_weight=base.max_position_weight,
        fee_rate=base.fee_rate,
        tax_rate=base.tax_rate,
        slippage_rate=base.slippage_rate,
        group_map="data/reference/stock_industry_map.csv",
        group_column="industry_name",
        max_group_exposure=scenario["max_group_exposure"],
        stop_loss_pct=scenario["stop_loss_pct"],
        take_profit_pct=scenario["take_profit_pct"],
        same_day_hit_priority=base.same_day_hit_priority,
        output=None,
    )


def scenario_id(scenario: dict[str, Any]) -> str:
    return "h{horizon}_sl{sl}_tp{tp}_gc{gc}".format(
        horizon=scenario["horizon"],
        sl=fmt_token(scenario["stop_loss_pct"]),
        tp=fmt_token(scenario["take_profit_pct"]),
        gc=fmt_token(scenario["max_group_exposure"]),
    )


def fmt_token(value: Any) -> str:
    if value is None:
        return "none"
    return str(value).replace(".", "p")


def event_counts(trades: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for trade in trades:
        reason = str(trade.get("exit_reason") or "unknown")
        counts[reason] = counts.get(reason, 0) + 1
    return counts


def matrix_row(scenario: dict[str, Any], replay: dict[str, Any]) -> dict[str, Any]:
    summary = replay.get("summary", {})
    total_return = finite(summary.get("total_return"))
    max_drawdown = finite(summary.get("max_drawdown"))
    avg_trade_return = finite(summary.get("avg_trade_return"))
    win_rate = finite(summary.get("win_rate"))
    score = strategy_score(total_return, max_drawdown, win_rate, avg_trade_return)
    return {
        "scenario_id": scenario_id(scenario),
        "horizon": scenario["horizon"],
        "stop_loss_pct": scenario["stop_loss_pct"],
        "take_profit_pct": scenario["take_profit_pct"],
        "max_group_exposure": scenario["max_group_exposure"],
        "final_equity": summary.get("final_equity"),
        "total_return": total_return,
        "max_drawdown": max_drawdown,
        "trade_count": int(summary.get("trade_count") or 0),
        "win_rate": win_rate,
        "avg_trade_return": avg_trade_return,
        "max_gross_exposure": summary.get("max_gross_exposure"),
        "max_group_exposure_observed": summary.get("max_group_exposure"),
        "exit_reason_counts": event_counts(replay.get("trades", [])),
        "score": score,
    }


def finite(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def strategy_score(
    total_return: float | None,
    max_drawdown: float | None,
    win_rate: float | None,
    avg_trade_return: float | None,
) -> float | None:
    if total_return is None or max_drawdown is None:
        return None
    drawdown_penalty = abs(min(max_drawdown, 0.0))
    win_bonus = (win_rate or 0.0) * 0.1
    trade_bonus = (avg_trade_return or 0.0) * 2
    return round(total_return - drawdown_penalty + win_bonus + trade_bonus, 6)


def score_sort_value(item: dict[str, Any]) -> float:
    score = item.get("score")
    return float(score) if score is not None else -999.0


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    price_frame = run_portfolio_replay.run_backtest_replay.load_price_frame(
        run_portfolio_replay.resolve_path(args.features)
    )
    scenarios = [
        {
            "horizon": horizon,
            "stop_loss_pct": stop_loss_pct,
            "take_profit_pct": take_profit_pct,
            "max_group_exposure": max_group_exposure,
        }
        for horizon, stop_loss_pct, take_profit_pct, max_group_exposure in itertools.product(
            parse_int_list(args.horizons),
            parse_optional_float_list(args.stop_loss_pcts),
            parse_optional_float_list(args.take_profit_pcts),
            parse_optional_float_list(args.max_group_exposures),
        )
    ]
    rows: list[dict[str, Any]] = []
    for scenario in scenarios:
        replay = run_portfolio_replay.run_portfolio_from_price_frame(replay_args(args, scenario), price_frame)
        rows.append(matrix_row(scenario, replay))
    ranked_rows = sorted(rows, key=lambda item: (item["score"] is not None, score_sort_value(item)), reverse=True)
    best = ranked_rows[0] if ranked_rows else None
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "contract": {
            "source": "portfolio_replay_matrix",
            "model_feature": False,
            "ranking_score_change": False,
            "resource_mode": "read_existing_artifacts_only",
            "features_load_policy": "load_once_per_matrix",
            "same_day_hit_priority": args.same_day_hit_priority,
        },
        "inputs": {
            "rankings_dir": str(run_portfolio_replay.resolve_path(args.rankings_dir)),
            "features": str(run_portfolio_replay.resolve_path(args.features)),
            "max_ranking_files": args.max_ranking_files,
            "top_n": args.top_n,
            "scenario_count": len(rows),
        },
        "summary": {
            "scenario_count": len(rows),
            "best_scenario_id": best.get("scenario_id") if best else None,
            "best_score": best.get("score") if best else None,
            "positive_return_count": sum((row.get("total_return") or 0) > 0 for row in rows),
            "negative_return_count": sum((row.get("total_return") or 0) < 0 for row in rows),
        },
        "scenarios": ranked_rows,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Backtest Strategy Matrix",
        "",
        f"- status：OK",
        f"- scenario_count：{payload['summary']['scenario_count']}",
        f"- best_scenario_id：{payload['summary']['best_scenario_id']}",
        f"- best_score：{payload['summary']['best_score']}",
        "",
        "| Scenario | Return | Max DD | Win | Trades | Score |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in payload["scenarios"][:20]:
        lines.append(
            "| {scenario_id} | {ret} | {dd} | {win} | {trades} | {score} |".format(
                scenario_id=row["scenario_id"],
                ret=pct(row["total_return"]),
                dd=pct(row["max_drawdown"]),
                win=pct(row["win_rate"]),
                trades=row["trade_count"],
                score=row["score"],
            )
        )
    lines.append("")
    return "\n".join(lines)


def pct(value: Any) -> str:
    if value is None:
        return "--"
    return f"{float(value):.2%}"


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    run_date = datetime.now().strftime("%Y-%m-%d")
    output_path = Path(args.output).expanduser() if args.output else PROJECT_ROOT / "artifacts" / "backtest" / f"strategy_matrix_{run_date}.json"
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path
    md_path = output_path.with_suffix(".md")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": "OK", "output": str(output_path), "markdown": str(md_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
