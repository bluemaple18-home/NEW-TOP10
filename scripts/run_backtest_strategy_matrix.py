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
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import run_portfolio_replay  # noqa: E402
from scripts import run_autonomous_research as regime_research  # noqa: E402


SCHEMA_VERSION = "backtest-strategy-matrix.v1"
MAX_DRAWDOWN_LIMIT = -0.25
NEIGHBOR_P_VALUE_LIMIT = 0.05
SCENARIO_PARAMETER_FIELDS = ("horizon", "stop_loss_pct", "take_profit_pct", "max_group_exposure")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="run backtest strategy matrix")
    parser.add_argument("--rankings-dir", default="artifacts")
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument(
        "--max-ranking-files",
        type=int,
        default=None,
        help="限制處理最近 N 份 ranking；預設跑完整期間，避免正式研究誤用抽樣結果",
    )
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
    parser.add_argument("--require-exact-regime", action="store_true")
    parser.add_argument("--market-regime-history", default=None)
    parser.add_argument("--base-regime", default=None)
    parser.add_argument("--family-tags", default="")
    parser.add_argument("--allowed-episode-ids", default=None)
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
        entry_delay_trade_days=1,
        max_ranking_files=base.max_ranking_files,
        initial_cash=1.0,
        max_gross_exposure=base.max_gross_exposure,
        market_regime_history=getattr(base, "market_regime_history", None),
        exact_regime_episode_by_date=getattr(base, "exact_regime_episode_by_date", None),
        big_bull_gross_exposure=None,
        high_choppy_gross_exposure=None,
        other_family_gross_exposure=None,
        max_position_weight=base.max_position_weight,
        fee_rate=base.fee_rate,
        tax_rate=base.tax_rate,
        slippage_rate=base.slippage_rate,
        group_map="data/reference/stock_industry_map.csv",
        group_column="industry_name",
        max_group_exposure=scenario["max_group_exposure"],
        stop_loss_pct=scenario["stop_loss_pct"],
        take_profit_pct=scenario["take_profit_pct"],
        trailing_stop_pct=None,
        min_event_holding_days=1,
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


def exact_regime_context(
    args: argparse.Namespace,
) -> tuple[dict[str, Any] | None, set[str] | None, dict[str, str] | None]:
    if not bool(args.require_exact_regime):
        return None, None, None
    if not args.market_regime_history or not args.base_regime:
        raise ValueError("--require-exact-regime 必須提供 --market-regime-history 與 --base-regime")
    path = run_portfolio_replay.resolve_path(args.market_regime_history)
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    as_of_check = regime_research.validate_as_of_regime_rows(rows)
    if not as_of_check["ok"]:
        raise ValueError(f"market regime history 不符合 as-of 契約：{as_of_check['violations'][:3]}")
    identity = regime_research.canonical_regime_identity(
        {
            "base_regime": args.base_regime,
            "family_tags": [item.strip() for item in args.family_tags.split(",") if item.strip()],
        }
    )
    requested_episode_ids = {
        item.strip()
        for item in str(getattr(args, "allowed_episode_ids", "") or "").split(",")
        if item.strip()
    }
    if not requested_episode_ids:
        raise ValueError("--require-exact-regime 必須提供 immutable --allowed-episode-ids")
    regime_id = regime_research.regime_identity_id(identity)
    episodes = [
        episode
        for episode in regime_research.build_regime_episodes(rows)
        if episode.get("regime_id") == regime_id
    ]
    by_id = {str(episode["episode_id"]): episode for episode in episodes}
    missing_episode_ids = sorted(requested_episode_ids - set(by_id))
    if missing_episode_ids:
        raise ValueError(f"immutable episode split 引用了未知 episode IDs：{missing_episode_ids}")
    allowed_dates: set[str] = set()
    episode_by_date: dict[str, str] = {}
    for episode_id in sorted(requested_episode_ids):
        for trade_date in by_id[episode_id]["trade_dates"]:
            if trade_date in episode_by_date:
                raise ValueError(f"immutable episode split 交易日重疊：{trade_date}")
            allowed_dates.add(str(trade_date))
            episode_by_date[str(trade_date)] = episode_id
    if not allowed_dates:
        raise ValueError(f"exact-match 盤勢沒有可用日期：{regime_research.regime_identity_id(identity)}")
    return identity, allowed_dates, episode_by_date


@contextmanager
def exact_ranking_file_scope(allowed_dates: set[str] | None):
    """在 portfolio replay 建立 entry plan 前限制 ranking date。"""

    if allowed_dates is None:
        yield
        return
    replay_module = run_portfolio_replay.run_backtest_replay
    original = replay_module.ranking_files

    def filtered(rankings_dir: Path, max_files: int | None) -> list[Path]:
        files = original(rankings_dir, None)
        exact = [path for path in files if replay_module.ranking_date(path) in allowed_dates]
        if not exact:
            raise FileNotFoundError("ranking artifacts 沒有 exact-match regime 日期")
        return exact[-max_files:] if max_files else exact

    replay_module.ranking_files = filtered
    try:
        yield
    finally:
        replay_module.ranking_files = original


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
        "combination_id": regime_research.canonical_json_hash(scenario),
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
        "p_value": exact_sign_test_p_value(replay.get("trades", [])),
        "robust_neighbor_lineage": [],
        "robust_neighbor_pass_count": 0,
        "drawdown_within_limit": max_drawdown is not None and max_drawdown >= MAX_DRAWDOWN_LIMIT,
    }


def exact_sign_test_p_value(trades: list[dict[str, Any]]) -> float | None:
    returns = [finite(row.get("net_return")) for row in trades]
    non_zero = [value for value in returns if value is not None and value != 0]
    if not non_zero:
        return None
    wins = sum(value > 0 for value in non_zero)
    sample_count = len(non_zero)
    tail = sum(math.comb(sample_count, count) for count in range(wins, sample_count + 1))
    return round(tail / (2**sample_count), 12)


def annotate_statistical_lineage(rows: list[dict[str, Any]]) -> None:
    family_id = regime_research.canonical_json_hash(sorted(str(row["combination_id"]) for row in rows))
    for row in rows:
        lineage = []
        for neighbor in rows:
            if neighbor is row:
                continue
            differing_fields = sum(row.get(field) != neighbor.get(field) for field in SCENARIO_PARAMETER_FIELDS)
            if differing_fields != 1:
                continue
            p_value = finite(neighbor.get("p_value"))
            if (
                p_value is not None
                and p_value <= NEIGHBOR_P_VALUE_LIMIT
                and bool(neighbor.get("drawdown_within_limit"))
                and (finite(neighbor.get("total_return")) or 0.0) > 0
            ):
                lineage.append(str(neighbor["combination_id"]))
        row["correction_family_id"] = family_id
        row["robust_neighbor_lineage"] = sorted(lineage)
        row["robust_neighbor_pass_count"] = len(lineage)


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
    regime_identity, allowed_dates, episode_by_date = exact_regime_context(args)
    args.exact_regime_episode_by_date = episode_by_date
    rows: list[dict[str, Any]] = []
    with exact_ranking_file_scope(allowed_dates):
        for scenario in scenarios:
            replay = run_portfolio_replay.run_portfolio_from_price_frame(replay_args(args, scenario), price_frame)
            rows.append(matrix_row(scenario, replay))
    annotate_statistical_lineage(rows)
    ranked_rows = sorted(rows, key=lambda item: (item["score"] is not None, score_sort_value(item)), reverse=True)
    best = ranked_rows[0] if ranked_rows else None
    statistical_gate = regime_research.multiple_testing_gate(ranked_rows) if args.require_exact_regime else None
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "contract": {
            "source": "portfolio_replay_matrix",
            "research_stage": "COARSE_SCREEN",
            "model_feature": False,
            "ranking_score_change": False,
            "resource_mode": "read_existing_artifacts_only",
            "features_load_policy": "load_once_per_matrix",
            "same_day_hit_priority": args.same_day_hit_priority,
            "exact_match_regime_required": bool(args.require_exact_regime),
            "transition_and_unknown_excluded": bool(args.require_exact_regime),
            "production_promotion_allowed": False,
            "raw_best_is_diagnostic_only": bool(args.require_exact_regime),
        },
        "inputs": {
            "rankings_dir": str(run_portfolio_replay.resolve_path(args.rankings_dir)),
            "features": str(run_portfolio_replay.resolve_path(args.features)),
            "max_ranking_files": args.max_ranking_files,
            "top_n": args.top_n,
            "scenario_count": len(rows),
            "regime_identity": regime_identity,
            "exact_match_ranking_date_count": len(allowed_dates or []),
            "exact_match_episode_ids": sorted(set((episode_by_date or {}).values())),
            "market_regime_history": args.market_regime_history,
            "exact_match_dataset_hash": (
                regime_research.canonical_json_hash(sorted(allowed_dates)) if allowed_dates is not None else None
            ),
            "parameter_space_hash": regime_research.canonical_json_hash(scenarios),
            "correction_family_id": rows[0]["correction_family_id"] if rows else None,
        },
        "summary": {
            "scenario_count": len(rows),
            "best_scenario_id": best.get("scenario_id") if best else None,
            "best_score": best.get("score") if best else None,
            "positive_return_count": sum((row.get("total_return") or 0) > 0 for row in rows),
            "negative_return_count": sum((row.get("total_return") or 0) < 0 for row in rows),
            "statistical_gate": statistical_gate,
            "formal_candidate_scenario_ids": (statistical_gate or {}).get("eligible_ids", []),
            "round_decision": (
                regime_research.research_round_decision(
                    [{"passed": True} for _ in (statistical_gate or {}).get("eligible_ids", [])],
                    sufficient_evidence=bool((statistical_gate or {}).get("evidence_complete")),
                )
                if args.require_exact_regime
                else None
            ),
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
