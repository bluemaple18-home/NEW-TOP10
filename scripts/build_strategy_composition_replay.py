#!/usr/bin/env python3
"""建立 candidate ranking + trail10 條件式策略 replay 報告。"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_high_choppy_context_overlay import load_regime_frame, rolling_high_choppy  # noqa: E402
from scripts.research_regime_family_training_candidates import is_big_bull  # noqa: E402
from scripts import run_odd_lot_portfolio_replay  # noqa: E402


SCHEMA_VERSION = "strategy-composition-replay.v1"

DEFAULT_REGISTRY = "artifacts/model_experiments/strategy_component_registry_2026-06-10.json"
DEFAULT_LONG_REPORT = "artifacts/model_experiments/long_candidate_validation_report_2026-06-10.json"
DEFAULT_RETENTION = "artifacts/model_experiments/candidate_trail10_retention_diagnostics_2026-06-10.json"
DEFAULT_REGIME_HISTORY = "artifacts/model_experiments/market_regime_history_2023-11-21_2026-05-15.json"
DEFAULT_INDUSTRY_MAP = "data/reference/stock_industry_map.csv"

PRODUCTION_BASELINE = (
    "artifacts/model_experiments/"
    "odd_lot_portfolio_production_top7_sl12_min5_300k_2023-11-21_2026-05-15_exit_ptp25_third_runner_2026-06-10.json"
)
CANDIDATE_TRAIL10 = (
    "artifacts/model_experiments/"
    "odd_lot_portfolio_candidate_top7_sl12_min5_300k_2023-11-21_2026-05-15_exit_matrix_trail10_2026-06-10.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build strategy composition replay")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--registry", default=DEFAULT_REGISTRY)
    parser.add_argument("--long-report", default=DEFAULT_LONG_REPORT)
    parser.add_argument("--retention-diagnostics", default=DEFAULT_RETENTION)
    parser.add_argument("--market-regime-history", default=DEFAULT_REGIME_HISTORY)
    parser.add_argument("--industry-map", default=DEFAULT_INDUSTRY_MAP)
    parser.add_argument("--production-baseline", default=PRODUCTION_BASELINE)
    parser.add_argument("--candidate-trail10", default=CANDIDATE_TRAIL10)
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


def registry_components(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("components") if isinstance(payload.get("components"), list) else []
    return {str(row.get("component_id")): row for row in rows if isinstance(row, dict)}


def ranking_dates(path: Path) -> list[str]:
    return sorted(item.stem.removeprefix("ranking_") for item in path.glob("ranking_*.csv"))


def regime_map(path: Path) -> dict[str, dict[str, Any]]:
    frame = load_regime_frame(path)
    frame["BIG_BULL"] = frame.apply(is_big_bull, axis=1)
    frame["HIGH_CHOPPY_CONTEXT"] = frame.apply(rolling_high_choppy, axis=1)
    result: dict[str, dict[str, Any]] = {}
    for row in frame.itertuples(index=False):
        date_text = str(row.trade_date_text)
        high_choppy = bool(row.HIGH_CHOPPY_CONTEXT)
        big_bull = bool(row.BIG_BULL)
        if high_choppy:
            family = "HIGH_CHOPPY_CONTEXT"
        elif big_bull:
            family = "BIG_BULL"
        else:
            family = "NON_BIG_BULL_NON_HIGH_CHOPPY"
        result[date_text] = {
            "family": family,
            "big_bull": big_bull,
            "high_choppy_context": high_choppy,
            "base_regime": str(getattr(row, "regime_label", "")),
        }
    return result


def copy_ranking(source: Path, target: Path, source_label: str) -> None:
    frame = pd.read_csv(source, encoding="utf-8-sig")
    frame["strategy_composition_source"] = source_label
    target.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(target, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_MINIMAL)


def build_filtered_rankings(
    production_dir: Path,
    candidate_dir: Path,
    regimes: dict[str, dict[str, Any]],
    output_root: Path,
) -> dict[str, Path]:
    dates = sorted(set(ranking_dates(production_dir)) & set(ranking_dates(candidate_dir)))
    big_bull_dir = output_root / "candidate_trail10_big_bull_only_rankings"
    conditional_dir = output_root / "candidate_trail10_regime_conditional_rankings"
    for date_text in dates:
        family = regimes.get(date_text, {}).get("family")
        candidate_file = candidate_dir / f"ranking_{date_text}.csv"
        production_file = production_dir / f"ranking_{date_text}.csv"
        if family == "BIG_BULL":
            copy_ranking(candidate_file, big_bull_dir / candidate_file.name, "candidate_big_bull")
            copy_ranking(candidate_file, conditional_dir / candidate_file.name, "candidate_big_bull")
        else:
            copy_ranking(production_file, conditional_dir / production_file.name, "production_inactive_regime")
    return {
        "candidate_trail10_big_bull_only": big_bull_dir,
        "candidate_trail10_regime_conditional": conditional_dir,
    }


def replay_args(rankings_dir: Path, output: Path, exit_policy: str) -> SimpleNamespace:
    partial_take_profit_pct = 0.25 if exit_policy == "production_proxy" else None
    partial_take_profit_fraction = 1 / 3 if exit_policy == "production_proxy" else 0.5
    trailing_stop_pct = 0.10 if exit_policy == "trail10" else None
    return SimpleNamespace(
        rankings_dir=str(rankings_dir),
        features="data/clean/features.parquet",
        horizon=40,
        top_n=7,
        entry_delay_trade_days=1,
        max_ranking_files=None,
        initial_cash=300_000.0,
        max_gross_exposure=0.85,
        market_regime_history=None,
        big_bull_gross_exposure=None,
        high_choppy_gross_exposure=None,
        other_family_gross_exposure=None,
        max_position_weight=0.15,
        min_shares=1,
        lot_size=1,
        fee_rate=0.001425,
        tax_rate=0.003,
        slippage_rate=0.001,
        stop_loss_pct=0.12,
        take_profit_pct=None,
        partial_take_profit_pct=partial_take_profit_pct,
        partial_take_profit_fraction=partial_take_profit_fraction,
        trailing_stop_pct=trailing_stop_pct,
        min_event_holding_days=5,
        same_day_hit_priority="stop_loss",
        output=str(output),
    )


def write_replay(rankings_dir: Path, output: Path, exit_policy: str) -> dict[str, Any]:
    payload = run_odd_lot_portfolio_replay.build_payload(replay_args(rankings_dir, output, exit_policy))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    output.with_suffix(".md").write_text(run_odd_lot_portfolio_replay.render_markdown(payload), encoding="utf-8")
    return payload


def product_return(rows: list[dict[str, Any]]) -> float | None:
    if not rows:
        return None
    value = 1.0
    for row in rows:
        value *= 1 + n(row.get("daily_return"))
    return round(value - 1, 6)


def max_drawdown(rows: list[dict[str, Any]]) -> float | None:
    if not rows:
        return None
    equity = 1.0
    peak = 1.0
    worst = 0.0
    for row in rows:
        equity *= 1 + n(row.get("daily_return"))
        peak = max(peak, equity)
        worst = min(worst, equity / peak - 1)
    return round(worst, 6)


def trade_holding_days(trade: dict[str, Any]) -> int | None:
    try:
        start = datetime.fromisoformat(str(trade.get("entry_date"))).date()
        end = datetime.fromisoformat(str(trade.get("exit_date"))).date()
        return (end - start).days
    except ValueError:
        return None


def sector_map(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    frame = pd.read_csv(path, dtype={"stock_id": str})
    if "stock_id" not in frame.columns or "sector_name" not in frame.columns:
        return {}
    return {
        str(row.stock_id).replace(".0", "").zfill(4): str(row.sector_name)
        for row in frame.itertuples(index=False)
    }


def concentration(trades: list[dict[str, Any]], sectors: dict[str, str]) -> dict[str, Any]:
    totals: dict[str, float] = {}
    total = 0.0
    for trade in trades:
        sector = sectors.get(str(trade.get("stock_id")).zfill(4), "UNKNOWN")
        amount = n(trade.get("entry_notional"))
        totals[sector] = totals.get(sector, 0.0) + amount
        total += amount
    if total <= 0:
        return {"top_sector": None, "top_sector_share": None, "sector_count": 0}
    top_sector, top_value = max(totals.items(), key=lambda item: item[1])
    return {
        "top_sector": top_sector,
        "top_sector_share": round(top_value / total, 6),
        "sector_count": len(totals),
    }


def compact_performance(payload: dict[str, Any], sectors: dict[str, str]) -> dict[str, Any]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    trades = payload.get("trades") if isinstance(payload.get("trades"), list) else []
    daily_count = int(summary.get("daily_count") or 0)
    holding = [value for value in (trade_holding_days(trade) for trade in trades) if value is not None]
    total_return = n(summary.get("total_return"))
    max_dd = n(summary.get("max_drawdown"))
    return {
        "total_return": round(total_return, 6),
        "max_drawdown": round(max_dd, 6),
        "risk_adjusted_return": round(total_return / abs(max_dd), 6) if max_dd < 0 else None,
        "turnover": round(len(trades) / daily_count, 6) if daily_count else None,
        "hit_rate": summary.get("win_rate"),
        "average_holding_days": round(sum(holding) / len(holding), 6) if holding else None,
        "cash_utilization": round(1 - n(summary.get("avg_cash_weight")), 6),
        "sector_concentration": concentration(trades, sectors),
        "trade_count": len(trades),
        "daily_count": daily_count,
    }


def rows_by_date(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    daily = payload.get("daily") if isinstance(payload.get("daily"), list) else []
    return {str(row.get("date")): row for row in daily}


def window_rows(payload: dict[str, Any], selected_dates: list[str]) -> dict[str, dict[str, Any]]:
    by_date = rows_by_date(payload)
    daily = [by_date[date_text] for date_text in selected_dates if date_text in by_date]
    windows = {
        "long_window": daily,
        "recent_100": daily[-100:],
        "recent_6m": daily[-126:],
    }
    result = {}
    for name, rows in windows.items():
        result[name] = {
            "start": rows[0]["date"] if rows else None,
            "end": rows[-1]["date"] if rows else None,
            "daily_count": len(rows),
            "total_return": product_return(rows),
            "max_drawdown": max_drawdown(rows),
        }
    return result


def regime_slices(payload: dict[str, Any], regimes: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    trades = payload.get("trades") if isinstance(payload.get("trades"), list) else []
    buckets = {
        "ALL": trades,
        "BIG_BULL": [],
        "HIGH_CHOPPY_CONTEXT": [],
        "NON_BIG_BULL_NON_HIGH_CHOPPY": [],
        "UNKNOWN": [],
    }
    for trade in trades:
        family = regimes.get(str(trade.get("ranking_date")), {}).get("family", "UNKNOWN")
        buckets.setdefault(family, []).append(trade)
    result = {}
    for family, rows in buckets.items():
        returns = [n(row.get("net_return")) for row in rows]
        result[family] = {
            "trade_count": len(rows),
            "avg_net_return": round(sum(returns) / len(returns), 6) if returns else None,
            "hit_rate": round(sum(value > 0 for value in returns) / len(returns), 6) if returns else None,
            "total_net_return_proxy": round(sum(returns), 6) if returns else None,
        }
    return result


def compare_to_production(variant: dict[str, Any], production: dict[str, Any]) -> dict[str, Any]:
    return {
        "return_delta": round(n(variant.get("total_return")) - n(production.get("total_return")), 6),
        "drawdown_delta": round(n(variant.get("max_drawdown")) - n(production.get("max_drawdown")), 6),
        "risk_adjusted_delta": round(n(variant.get("risk_adjusted_return")) - n(production.get("risk_adjusted_return")), 6),
        "hit_rate_delta": round(n(variant.get("hit_rate")) - n(production.get("hit_rate")), 6),
        "cash_utilization_delta": round(n(variant.get("cash_utilization")) - n(production.get("cash_utilization")), 6),
    }


def variant_contract(
    name: str,
    ranking_source: str,
    regime_gate: str,
    component_statuses: dict[str, str],
    artifact: Path,
) -> dict[str, Any]:
    is_production = name == "production_baseline"
    return {
        "variant_id": name,
        "artifact": repo_path(artifact),
        "ranking_source": ranking_source,
        "entry_rule": "Top7 ranking on D close, enter D+1 open",
        "exit_rule": "production_ptp25_sell_one_third_runner_proxy" if is_production else "trail10_after_min5",
        "capital_rule": "initial_cash=300000, odd_lot=True, max_position_weight=0.15, max_gross_exposure=0.85",
        "regime_gate": regime_gate,
        "sector_concentration_rule": "measured_only_no_hard_cap",
        "message_eligibility": "shadow_summary_only" if not is_production else "existing_production_baseline",
        "allowed_production_use": [] if not is_production else ["baseline_comparison_only"],
        "blocked_production_use": ["promotion_ready", "direct_publish_switch", "clawd_message_change"],
        "component_statuses": component_statuses,
    }


def choose_decision(
    performance: dict[str, Any],
    windows: dict[str, Any],
    regimes: dict[str, Any],
    retention: dict[str, Any],
) -> dict[str, Any]:
    production = performance["production_baseline"]
    global_candidate = performance["candidate_trail10_global"]
    conditional = performance["candidate_trail10_regime_conditional"]
    recent_100_delta = n(windows["candidate_trail10_global"]["recent_100"]["return_delta_vs_production"])
    recent_6m_delta = n(windows["candidate_trail10_global"]["recent_6m"]["return_delta_vs_production"])
    conditional_long_delta = n(conditional["comparison_vs_production"]["return_delta"])
    conditional_dd_delta = n(conditional["comparison_vs_production"]["drawdown_delta"])
    big_bull_delta = n(
        regimes["candidate_trail10_global"]["BIG_BULL"]["avg_net_return_delta_vs_production"]
    )
    high_choppy_count = int(regimes["candidate_trail10_global"]["HIGH_CHOPPY_CONTEXT"]["candidate"].get("trade_count") or 0)
    conditional_high_choppy_count = int(
        regimes["candidate_trail10_regime_conditional"]["HIGH_CHOPPY_CONTEXT"]["candidate"].get("trade_count") or 0
    )
    blockers: list[str] = []
    warnings: list[str] = []
    if recent_100_delta < 0:
        blockers.append("candidate_trail10_global_recent_100_underperforms_production")
    if recent_6m_delta < 0:
        blockers.append("candidate_trail10_global_recent_6m_underperforms_production")
    if conditional_long_delta <= 0:
        blockers.append("regime_conditional_switch_does_not_beat_production_return")
    if conditional_dd_delta < 0:
        warnings.append("regime_conditional_switch_has_deeper_drawdown_than_production")
    if big_bull_delta < 0:
        warnings.append("BIG_BULL_avg_trade_return_is_below_production_peer")
    if high_choppy_count == 0 and conditional_high_choppy_count < 30:
        warnings.append("HIGH_CHOPPY_CONTEXT_has_too_few_candidate_trades_in_this_replay")

    if blockers:
        status = "KEEP_SHADOW_MONITOR"
    elif conditional_long_delta > 0 and n(conditional["risk_adjusted_return"]) >= n(production["risk_adjusted_return"]):
        status = "ADOPT_CONDITIONAL_SWITCH"
    elif n(global_candidate["total_return"]) <= n(production["total_return"]):
        status = "REJECT_COMPOSITION"
    else:
        status = "KEEP_SHADOW_MONITOR"

    global_return_delta = n(global_candidate["comparison_vs_production"]["return_delta"])
    conditional_return_delta = n(conditional["comparison_vs_production"]["return_delta"])
    if global_return_delta > 0:
        production_vs_candidate = "candidate+trail10 在本次同資金重跑勝過 production。"
    else:
        production_vs_candidate = "production baseline 在本次同資金重跑勝過 candidate+trail10。"
    if conditional_return_delta > 0 and status == "ADOPT_CONDITIONAL_SWITCH":
        candidate_scope = "candidate 目前只適合條件式切換，不是全市場無條件替換。"
    elif conditional_return_delta > 0:
        candidate_scope = "條件式版本有部分優勢，但近期窗口未解除前只能 shadow。"
    else:
        candidate_scope = "BIG_BULL-only 與 regime-conditional 都沒有勝過 production，不支持條件式上線。"
    if high_choppy_count == 0 and conditional_high_choppy_count < 30:
        high_choppy = "HIGH_CHOPPY_CONTEXT 樣本太少，只能 monitor。"
    else:
        high_choppy = "HIGH_CHOPPY_CONTEXT 目前不是明確加分條件，仍只能 monitor。"
    return {
        "status": status,
        "production_switch_ready": False,
        "promotion_ready": False,
        "blocked_reasons": blockers,
        "warnings": warnings,
        "plain_language": {
            "production_vs_candidate": production_vs_candidate,
            "candidate_scope": candidate_scope,
            "high_choppy": high_choppy,
            "daily_message_impact": "正式上線前不改每日推播；若未來採用，只能新增條件式 shadow/候補說明，不覆蓋 production Top10。",
        },
        "source_retention_decision": (retention.get("decision") or {}).get("candidate_trail10"),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    registry_path = resolve_path(args.registry)
    long_path = resolve_path(args.long_report)
    retention_path = resolve_path(args.retention_diagnostics)
    regime_path = resolve_path(args.market_regime_history)
    industry_path = resolve_path(args.industry_map)
    production_path = resolve_path(args.production_baseline)
    candidate_path = resolve_path(args.candidate_trail10)
    required = [registry_path, long_path, retention_path, regime_path, industry_path, production_path, candidate_path]
    for path in required:
        if path is None or not path.exists():
            raise FileNotFoundError(f"找不到必要輸入：{path}")

    registry = read_json(registry_path)
    long_report = read_json(long_path)
    retention = read_json(retention_path)
    components = registry_components(registry)
    statuses = {
        "candidate_ranking": str((components.get("candidate_ranking") or {}).get("status")),
        "trail10": str((components.get("trail10") or {}).get("status")),
        "market_regime_history": str((components.get("market_regime_history") or {}).get("status")),
    }
    production_dir = resolve_path((long_report.get("inputs") or {}).get("production_rankings_dir"))
    candidate_dir = resolve_path((long_report.get("inputs") or {}).get("candidate_rankings_dir"))
    if production_dir is None or candidate_dir is None or not production_dir.exists() or not candidate_dir.exists():
        raise FileNotFoundError("long report ranking dirs are missing")

    regimes = regime_map(regime_path)
    work_root = PROJECT_ROOT / "artifacts" / "model_experiments" / f"strategy_composition_replay_work_{args.date}"
    ranking_dirs = build_filtered_rankings(production_dir, candidate_dir, regimes, work_root)
    production_replay_path = work_root / f"odd_lot_portfolio_production_baseline_{args.date}.json"
    candidate_global_path = work_root / f"odd_lot_portfolio_candidate_trail10_global_{args.date}.json"
    big_bull_path = work_root / f"odd_lot_portfolio_candidate_trail10_big_bull_only_{args.date}.json"
    conditional_path = work_root / f"odd_lot_portfolio_candidate_trail10_regime_conditional_{args.date}.json"
    production_replay = write_replay(production_dir, production_replay_path, "production_proxy")
    candidate_global = write_replay(candidate_dir, candidate_global_path, "trail10")
    big_bull = write_replay(ranking_dirs["candidate_trail10_big_bull_only"], big_bull_path, "trail10")
    conditional = write_replay(ranking_dirs["candidate_trail10_regime_conditional"], conditional_path, "trail10")

    sectors = sector_map(industry_path)
    variants = {
        "production_baseline": variant_contract(
            "production_baseline",
            "production_ranking",
            "ALL",
            {"production_ranking": "CURRENT_PRODUCTION"},
            production_replay_path,
        ),
        "candidate_trail10_global": variant_contract(
            "candidate_trail10_global",
            "candidate_ranking",
            "ALL",
            statuses,
            candidate_global_path,
        ),
        "candidate_trail10_big_bull_only": variant_contract(
            "candidate_trail10_big_bull_only",
            "candidate_ranking",
            "BIG_BULL only; no new entry outside BIG_BULL",
            statuses,
            big_bull_path,
        ),
        "candidate_trail10_regime_conditional": variant_contract(
            "candidate_trail10_regime_conditional",
            "candidate_ranking in BIG_BULL, production ranking otherwise",
            "BIG_BULL conditional switch using same trail10 exit in replay",
            statuses,
            conditional_path,
        ),
    }
    replay_payloads = {
        "production_baseline": production_replay,
        "candidate_trail10_global": candidate_global,
        "candidate_trail10_big_bull_only": big_bull,
        "candidate_trail10_regime_conditional": conditional,
    }
    performance = {name: compact_performance(payload, sectors) for name, payload in replay_payloads.items()}
    production_perf = performance["production_baseline"]
    for name, row in performance.items():
        row["comparison_vs_production"] = compare_to_production(row, production_perf)
    common_dates = sorted(set.intersection(*(set(rows_by_date(payload)) for payload in replay_payloads.values())))
    windows = {name: window_rows(payload, common_dates) for name, payload in replay_payloads.items()}
    for name, rows in windows.items():
        for window_name, row in rows.items():
            row["return_delta_vs_production"] = round(
                n(row.get("total_return")) - n(windows["production_baseline"][window_name].get("total_return")),
                6,
            )
            row["drawdown_delta_vs_production"] = round(
                n(row.get("max_drawdown")) - n(windows["production_baseline"][window_name].get("max_drawdown")),
                6,
            )
    regime_rows = {name: regime_slices(payload, regimes) for name, payload in replay_payloads.items()}
    for name, rows in regime_rows.items():
        if name == "production_baseline":
            continue
        for family, row in rows.items():
            production_row = regime_rows["production_baseline"].get(family, {})
            row["candidate"] = {
                key: row.get(key)
                for key in ["trade_count", "avg_net_return", "hit_rate", "total_net_return_proxy"]
            }
            row["production"] = production_row
            row["avg_net_return_delta_vs_production"] = round(
                n(row["candidate"].get("avg_net_return")) - n(production_row.get("avg_net_return")),
                6,
            )
    positive_folds = {}
    for name, rows in windows.items():
        if name == "production_baseline":
            continue
        positive_folds[name] = sum(1 for row in rows.values() if n(row.get("return_delta_vs_production")) > 0)
    decision_payload = choose_decision(performance, windows, regime_rows, retention)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK",
        "contract": {
            "research_only": True,
            "uses_existing_historical_data": True,
            "no_new_data_fetch": True,
            "no_model_training": True,
            "changes_production_ranking": False,
            "changes_risk_adjusted_score": False,
            "changes_clawd_message": False,
            "no_future_regime_data": True,
            "promotion_ready": False,
            "production_switch_ready": False,
        },
        "inputs": {
            "registry": repo_path(registry_path),
            "long_report": repo_path(long_path),
            "retention_diagnostics": repo_path(retention_path),
            "market_regime_history": repo_path(regime_path),
            "industry_map": repo_path(industry_path),
            "production_rankings_dir": repo_path(production_dir),
            "candidate_rankings_dir": repo_path(candidate_dir),
            "source_production_baseline_reference": repo_path(production_path),
            "source_candidate_trail10_reference": repo_path(candidate_path),
            "generated_work_root": repo_path(work_root),
            "common_replay_daily_count": len(common_dates),
        },
        "variants": variants,
        "capital_policy": {
            "initial_cash": 300_000,
            "odd_lot": True,
            "max_position_weight": 0.15,
            "max_gross_exposure": 0.85,
            "costs": {"fee_rate": 0.001425, "tax_rate": 0.003, "slippage_rate": 0.001},
        },
        "entry_exit_policy": {
            "entry": "D+1 open",
            "minimum_holding_trade_days": 5,
            "production_baseline_exit": "production ptp25 sell-one-third runner proxy",
            "candidate_exit": "trail10",
        },
        "windows": windows,
        "regime_slices": regime_rows,
        "performance": performance,
        "positive_folds": positive_folds,
        "historical_reference": {
            "note": "以下為既有長窗 artifact 摘要，只作背景；本次 decision 以同資金/同成本重跑的共同區間為準。",
            "retention_summary": retention.get("summary"),
            "long_report_coverage": long_report.get("coverage"),
            "long_report_decision": long_report.get("decision"),
        },
        "coverage_notes": {
            "fair_replay_common_window": "四個 variants 共同可比較日；避免拿不同日曆窗口互比。",
            "common_replay_daily_count": len(common_dates),
            "local_features_window": {
                "start": min(common_dates) if common_dates else None,
                "end": max(common_dates) if common_dates else None,
            },
        },
        "decision": decision_payload["status"],
        "blocked_reasons": decision_payload["blocked_reasons"],
        "warnings": decision_payload["warnings"],
        "next_recommended_action": "KEEP_DAILY_SHADOW_AND_RECHECK_RECENT_WINDOWS_BEFORE_ANY_SWITCH",
        "plain_language": decision_payload["plain_language"],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Strategy Composition Replay",
        "",
        f"- status: `{payload['status']}`",
        f"- decision: `{payload['decision']}`",
        f"- promotion_ready: `{payload['contract']['promotion_ready']}`",
        f"- production_switch_ready: `{payload['contract']['production_switch_ready']}`",
        "",
        "## Performance",
        "",
        "| Variant | Return | MaxDD | Risk Adj | Hit Rate | Cash Utilization |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, row in payload["performance"].items():
        lines.append(
            f"| {name} | {pct(row['total_return'])} | {pct(row['max_drawdown'])} | "
            f"{row['risk_adjusted_return']} | {pct(row['hit_rate'])} | {pct(row['cash_utilization'])} |"
        )
    lines.extend(["", "## Blockers", ""])
    lines.extend([f"- {item}" for item in payload["blocked_reasons"]] or ["- none"])
    lines.extend(["", "## Plain Language", ""])
    for key, value in payload["plain_language"].items():
        lines.append(f"- {key}: {value}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    output = resolve_path(args.output) or PROJECT_ROOT / "artifacts" / "model_experiments" / f"strategy_composition_replay_{args.date}.json"
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
