#!/usr/bin/env python3
"""建立 production ranking 操盤規則 replay 報告。"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import run_odd_lot_portfolio_replay  # noqa: E402
from scripts.build_strategy_composition_replay import (  # noqa: E402
    compact_performance,
    repo_path,
    resolve_path,
    sector_map,
)


SCHEMA_VERSION = "production-tactics-replay.v1"
DEFAULT_LONG_REPORT = "artifacts/model_experiments/long_candidate_validation_report_2026-06-10.json"
DEFAULT_REGIME_HISTORY = "artifacts/model_experiments/market_regime_history_2023-11-21_2026-05-15.json"
DEFAULT_INDUSTRY_MAP = "data/reference/stock_industry_map.csv"
DEFAULT_FEATURES = "data/clean/features.parquet"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build production tactics replay")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--long-report", default=DEFAULT_LONG_REPORT)
    parser.add_argument("--market-regime-history", default=DEFAULT_REGIME_HISTORY)
    parser.add_argument("--industry-map", default=DEFAULT_INDUSTRY_MAP)
    parser.add_argument("--features", default=DEFAULT_FEATURES)
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def n(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def pct(value: Any) -> str:
    if value is None:
        return "--"
    return f"{float(value):.2%}"


def replay_args(rankings_dir: Path, features: Path, regime_history: Path, policy: dict[str, Any], output: Path) -> SimpleNamespace:
    return SimpleNamespace(
        rankings_dir=str(rankings_dir),
        features=str(features),
        horizon=40,
        top_n=10,
        entry_delay_trade_days=1,
        max_ranking_files=None,
        initial_cash=300_000.0,
        max_gross_exposure=float(policy["default_gross_exposure"]),
        market_regime_history=str(regime_history),
        big_bull_gross_exposure=float(policy["big_bull_gross_exposure"]),
        high_choppy_gross_exposure=float(policy["high_choppy_gross_exposure"]),
        other_family_gross_exposure=float(policy["other_family_gross_exposure"]),
        max_position_weight=float(policy["max_position_weight"]),
        min_shares=1,
        lot_size=1,
        fee_rate=0.001425,
        tax_rate=0.003,
        slippage_rate=0.001,
        stop_loss_pct=policy.get("stop_loss_pct"),
        take_profit_pct=None,
        partial_take_profit_pct=policy.get("partial_take_profit_pct"),
        partial_take_profit_fraction=policy.get("partial_take_profit_fraction", 0.5),
        trailing_stop_pct=policy.get("trailing_stop_pct"),
        min_event_holding_days=5,
        same_day_hit_priority="stop_loss",
        output=str(output),
    )


def write_replay(rankings_dir: Path, features: Path, regime_history: Path, policy: dict[str, Any], output: Path) -> dict[str, Any]:
    payload = run_odd_lot_portfolio_replay.build_payload(replay_args(rankings_dir, features, regime_history, policy, output))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    output.with_suffix(".md").write_text(run_odd_lot_portfolio_replay.render_markdown(payload), encoding="utf-8")
    return payload


def trade_holding_days(trade: dict[str, Any]) -> int | None:
    try:
        start = datetime.fromisoformat(str(trade.get("entry_date"))).date()
        end = datetime.fromisoformat(str(trade.get("exit_date"))).date()
        return (end - start).days
    except ValueError:
        return None


def exit_reason_counts(payload: dict[str, Any]) -> dict[str, int]:
    trades = payload.get("trades") if isinstance(payload.get("trades"), list) else []
    return dict(Counter(str(trade.get("exit_reason")) for trade in trades))


def performance_row(payload: dict[str, Any], sectors: dict[str, str], baseline: dict[str, Any] | None = None) -> dict[str, Any]:
    row = compact_performance(payload, sectors)
    trades = payload.get("trades") if isinstance(payload.get("trades"), list) else []
    holding = [value for value in (trade_holding_days(trade) for trade in trades) if value is not None]
    row["average_holding_days"] = round(sum(holding) / len(holding), 6) if holding else None
    row["exit_reason_counts"] = exit_reason_counts(payload)
    if baseline:
        row["comparison_vs_baseline"] = {
            "return_delta": round(n(row.get("total_return")) - n(baseline.get("total_return")), 6),
            "drawdown_delta": round(n(row.get("max_drawdown")) - n(baseline.get("max_drawdown")), 6),
            "risk_adjusted_delta": round(n(row.get("risk_adjusted_return")) - n(baseline.get("risk_adjusted_return")), 6),
            "cash_utilization_delta": round(n(row.get("cash_utilization")) - n(baseline.get("cash_utilization")), 6),
        }
    return row


def policy_matrix() -> dict[str, dict[str, Any]]:
    base_capital = {
        "default_gross_exposure": 0.75,
        "big_bull_gross_exposure": 0.90,
        "high_choppy_gross_exposure": 0.75,
        "other_family_gross_exposure": 0.65,
    }
    return {
        "production_current_baseline": {
            **base_capital,
            "exit_rule": "fixed_40d_no_forced_event_exit",
            "warning_rule": "none",
            "max_position_weight": 0.10,
        },
        "production_trail10_exit": {
            **base_capital,
            "exit_rule": "trail10_after_min5_no_hard_stop",
            "warning_rule": "none",
            "max_position_weight": 0.10,
            "trailing_stop_pct": 0.10,
        },
        "production_hard_stop_then_trail10": {
            **base_capital,
            "exit_rule": "hard_stop12_then_trail10_after_min5",
            "warning_rule": "none",
            "max_position_weight": 0.10,
            "stop_loss_pct": 0.12,
            "trailing_stop_pct": 0.10,
        },
        "production_partial_take_profit_runner": {
            **base_capital,
            "exit_rule": "hard_stop12_partial_tp25_sell_one_third_runner",
            "warning_rule": "none",
            "max_position_weight": 0.12,
            "stop_loss_pct": 0.12,
            "partial_take_profit_pct": 0.25,
            "partial_take_profit_fraction": 1 / 3,
        },
        "production_warning_only_no_forced_sell": {
            **base_capital,
            "exit_rule": "fixed_40d_no_forced_event_exit",
            "warning_rule": "lookback_5_10_20_non_personal_warning_only",
            "max_position_weight": 0.10,
        },
        "production_aggressive_capital_fixed40": {
            **base_capital,
            "exit_rule": "fixed_40d_no_forced_event_exit",
            "warning_rule": "none",
            "max_position_weight": 0.12,
        },
        "production_max_capital_fixed40": {
            **base_capital,
            "exit_rule": "fixed_40d_no_forced_event_exit",
            "warning_rule": "none",
            "max_position_weight": 0.15,
        },
    }


def read_ranking(path: Path, top_n: int) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = []
        for rank, row in enumerate(csv.DictReader(handle), start=1):
            if rank > top_n:
                break
            rows.append(
                {
                    "rank": rank,
                    "stock_id": str(row.get("stock_id", "")).strip().replace(".0", "").zfill(4),
                    "stock_name": row.get("stock_name"),
                    "risk_penalty": n(row.get("risk_penalty"), default=None),
                }
            )
        return rows


def ranking_files(rankings_dir: Path) -> list[Path]:
    return sorted(rankings_dir.glob("ranking_*.csv"), key=lambda path: path.stem.removeprefix("ranking_"))


def load_feature_lookup(path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    frame = pd.read_parquet(path)
    date_column = "trade_date" if "trade_date" in frame.columns else "date"
    frame = frame.copy()
    frame["date_text"] = pd.to_datetime(frame[date_column]).dt.date.astype(str)
    frame["stock_id"] = frame["stock_id"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(4)
    columns = [col for col in ["close", "ma5", "ma10", "ma20", "long_upper_shadow"] if col in frame.columns]
    return {
        (str(row.stock_id), str(row.date_text)): {column: getattr(row, column) for column in columns}
        for row in frame[["stock_id", "date_text", *columns]].itertuples(index=False)
    }


def warning_level(row: dict[str, Any] | None, dropped: bool) -> str:
    if row is None:
        return "WATCH"
    close = n(row.get("close"), default=None)
    ma10 = n(row.get("ma10"), default=None)
    ma20 = n(row.get("ma20"), default=None)
    upper = bool(row.get("long_upper_shadow")) if row.get("long_upper_shadow") is not None else False
    if dropped and close is not None and ma20 is not None and close < ma20:
        return "RISK_ALERT"
    if close is not None and ma20 is not None and close < ma20:
        return "RISK_ALERT"
    if dropped or upper or (close is not None and ma10 is not None and close < ma10):
        return "WEAKENING"
    return "WATCH"


def warning_replay(rankings_dir: Path, features_path: Path, lookbacks: list[int]) -> dict[str, Any]:
    files = ranking_files(rankings_dir)
    feature_lookup = load_feature_lookup(features_path)
    rows_by_file = {path: read_ranking(path, 10) for path in files}
    result = {}
    for lookback in lookbacks:
        level_counts: Counter[str] = Counter()
        watchlist_sizes = []
        dropped_total = 0
        replay_dates = 0
        for index, path in enumerate(files):
            if index + 1 < lookback:
                continue
            date_text = path.stem.removeprefix("ranking_")
            current_ids = {row["stock_id"] for row in rows_by_file[path]}
            window = files[index - lookback + 1 : index + 1]
            history: dict[str, list[dict[str, Any]]] = {}
            for file in window:
                for row in rows_by_file[file]:
                    history.setdefault(row["stock_id"], []).append(row)
            replay_dates += 1
            watchlist_sizes.append(len(history))
            for stock_id in history:
                dropped = stock_id not in current_ids
                dropped_total += 1 if dropped else 0
                level_counts[warning_level(feature_lookup.get((stock_id, date_text)), dropped)] += 1
        total_items = sum(level_counts.values())
        result[f"lookback_{lookback}"] = {
            "lookback_trading_days": lookback,
            "replay_dates": replay_dates,
            "avg_watchlist_size": round(sum(watchlist_sizes) / len(watchlist_sizes), 6) if watchlist_sizes else None,
            "warning_level_counts": dict(level_counts),
            "risk_alert_ratio": round(level_counts.get("RISK_ALERT", 0) / total_items, 6) if total_items else None,
            "weakening_ratio": round(level_counts.get("WEAKENING", 0) / total_items, 6) if total_items else None,
            "dropped_from_current_top10_count": dropped_total,
            "contract": {
                "non_personal_warning_only": True,
                "does_not_force_sell": True,
                "blocked_message_terms": ["賣出", "停損", "全賣", "出場", "減碼"],
            },
        }
    return result


def windows(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    daily = payload.get("daily") if isinstance(payload.get("daily"), list) else []
    groups = {"full": daily, "recent_100": daily[-100:], "recent_6m": daily[-126:]}
    result = {}
    for name, rows in groups.items():
        equity = 1.0
        peak = 1.0
        worst = 0.0
        for row in rows:
            equity *= 1 + n(row.get("daily_return"))
            peak = max(peak, equity)
            worst = min(worst, equity / peak - 1)
        result[name] = {
            "start": rows[0]["date"] if rows else None,
            "end": rows[-1]["date"] if rows else None,
            "daily_count": len(rows),
            "total_return": round(equity - 1, 6) if rows else None,
            "max_drawdown": round(worst, 6) if rows else None,
        }
    return result


def registry_update_proposal() -> dict[str, Any]:
    return {
        "candidate_ranking": {
            "proposed_status": "DIAGNOSTIC_ONLY",
            "reason": "same-exit isolation 未贏 production，regime gate 也未救回。",
        },
        "trail10": {
            "proposed_status": "REUSABLE_CANDIDATE",
            "reason": "candidate ranking 失敗不代表 trail10 exit rule 自動淘汰；可搭 production ranking 測。",
        },
        "BIG_BULL_gate": {
            "proposed_status": "NEEDS_TEST",
            "reason": "不得用來救 candidate ranking；仍可當 production capital context。",
        },
        "HIGH_CHOPPY": {
            "proposed_status": "MONITOR_ONLY",
            "reason": "樣本不足，不進正式 gate。",
        },
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    long_path = resolve_path(args.long_report)
    regime_path = resolve_path(args.market_regime_history)
    industry_path = resolve_path(args.industry_map)
    features_path = resolve_path(args.features)
    for path in [long_path, regime_path, industry_path, features_path]:
        if path is None or not path.exists():
            raise FileNotFoundError(f"找不到必要輸入：{path}")
    long_report = read_json(long_path)
    production_dir = resolve_path((long_report.get("inputs") or {}).get("production_rankings_dir"))
    if production_dir is None or not production_dir.exists():
        raise FileNotFoundError("production ranking dir missing")

    work_root = PROJECT_ROOT / "artifacts" / "model_experiments" / f"production_tactics_replay_work_{args.date}"
    policies = policy_matrix()
    sectors = sector_map(industry_path)
    replay_payloads = {}
    for variant_id, policy in policies.items():
        replay_payloads[variant_id] = write_replay(
            production_dir,
            features_path,
            regime_path,
            policy,
            work_root / f"{variant_id}_{args.date}.json",
        )
    baseline_perf = performance_row(replay_payloads["production_current_baseline"], sectors)
    performance = {}
    variants = {}
    window_rows = {}
    for variant_id, payload in replay_payloads.items():
        policy = policies[variant_id]
        performance[variant_id] = performance_row(payload, sectors, baseline_perf)
        variants[variant_id] = {
            "ranking_source": "production_ranking",
            "entry_rule": "Top10 ranking on D close, enter D+1 open",
            "exit_rule": policy["exit_rule"],
            "warning_rule": policy["warning_rule"],
            "capital_rule": "300k odd-lot, regime gross 90/75/65, finite cash",
            "max_position_weight": policy["max_position_weight"],
            "max_gross_exposure": {
                "BIG_BULL": policy["big_bull_gross_exposure"],
                "HIGH_CHOPPY_CONTEXT": policy["high_choppy_gross_exposure"],
                "OTHER": policy["other_family_gross_exposure"],
            },
            "artifact": repo_path(work_root / f"{variant_id}_{args.date}.json"),
        }
        window_rows[variant_id] = windows(payload)
    warning = warning_replay(production_dir, features_path, [5, 10, 20])
    best_variant = max(performance.items(), key=lambda item: n(item[1].get("risk_adjusted_return")))[0]
    trail10_delta = performance["production_trail10_exit"]["comparison_vs_baseline"]
    blockers = []
    warnings_list = []
    if best_variant == "production_current_baseline":
        warnings_list.append("baseline_remains_best_risk_adjusted_variant")
    if n(trail10_delta.get("return_delta")) <= 0:
        warnings_list.append("trail10_does_not_improve_total_return_vs_baseline")
    if any((row.get("contract") or {}).get("does_not_force_sell") is not True for row in warning.values()):
        blockers.append("warning_policy_contains_forced_sell")
    decision = "KEEP_PRODUCTION_RANKING_TEST_TACTICS_IN_SHADOW" if not blockers else "NEEDS_MORE_DATA_CONTRACT"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK",
        "contract": {
            "research_only": True,
            "production_ranking_source_unchanged": True,
            "no_new_data_fetch": True,
            "no_model_training": True,
            "changes_model": False,
            "changes_production_ranking_score": False,
            "changes_clawd_live_send": False,
            "finite_capital": True,
            "odd_lot": True,
            "no_fixed_100_share_unlimited_capital_conclusion": True,
            "promotion_ready": False,
            "production_switch_ready": False,
        },
        "inputs": {
            "long_report": repo_path(long_path),
            "production_rankings_dir": repo_path(production_dir),
            "features": repo_path(features_path),
            "market_regime_history": repo_path(regime_path),
            "industry_map": repo_path(industry_path),
            "generated_work_root": repo_path(work_root),
        },
        "registry_update_proposal": registry_update_proposal(),
        "variants": variants,
        "capital_policy": {
            "initial_cash": 300_000,
            "odd_lot": True,
            "position_caps_tested": [0.10, 0.12, 0.15],
            "regime_gross_exposure": {"BIG_BULL": 0.90, "HIGH_CHOPPY_CONTEXT": 0.75, "OTHER": 0.65},
        },
        "entry_exit_policy": {variant_id: policy["exit_rule"] for variant_id, policy in policies.items()},
        "warning_policy": warning,
        "windows": window_rows,
        "performance": performance,
        "decision": decision,
        "best_next_shadow_variant": best_variant,
        "blocked_reasons": blockers,
        "warnings": warnings_list,
        "next_recommended_action": f"SHADOW_{best_variant}_WITHOUT_CHANGING_PRODUCTION_RANKING",
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Production Tactics Replay",
        "",
        f"- status: `{payload['status']}`",
        f"- decision: `{payload['decision']}`",
        f"- best_next_shadow_variant: `{payload['best_next_shadow_variant']}`",
        f"- promotion_ready: `{payload['contract']['promotion_ready']}`",
        "",
        "## Performance",
        "",
        "| Variant | Return | MaxDD | Risk Adj | Cash Util | Avg Hold | Turnover |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for variant_id, row in payload["performance"].items():
        lines.append(
            f"| {variant_id} | {pct(row['total_return'])} | {pct(row['max_drawdown'])} | "
            f"{row['risk_adjusted_return']} | {pct(row['cash_utilization'])} | {row['average_holding_days']} | {row['turnover']} |"
        )
    lines.extend(["", "## Warning Policy", ""])
    for label, row in payload["warning_policy"].items():
        lines.append(
            f"- {label}: dates={row['replay_dates']}, avg_watchlist={row['avg_watchlist_size']}, "
            f"risk_alert_ratio={pct(row['risk_alert_ratio'])}, weakening_ratio={pct(row['weakening_ratio'])}"
        )
    lines.extend(["", "## Blockers", ""])
    lines.extend([f"- {item}" for item in payload["blocked_reasons"]] or ["- none"])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    output = resolve_path(args.output) or PROJECT_ROOT / "artifacts" / "model_experiments" / f"production_tactics_replay_{args.date}.json"
    if output is None:
        raise RuntimeError("output resolution failed")
    payload = build_payload(args)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "decision": payload["decision"], "output": repo_path(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
