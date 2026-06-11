#!/usr/bin/env python3
"""建立 ranking isolation 與 regime normalization 報告。"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_strategy_composition_replay import (  # noqa: E402
    build_filtered_rankings,
    compact_performance,
    compare_to_production,
    regime_map,
    repo_path,
    resolve_path,
    rows_by_date,
    sector_map,
    write_replay,
)


SCHEMA_VERSION = "strategy-composition-isolation.v1"
DEFAULT_LONG_REPORT = "artifacts/model_experiments/long_candidate_validation_report_2026-06-10.json"
DEFAULT_REGIME_HISTORY = "artifacts/model_experiments/market_regime_history_2023-11-21_2026-05-15.json"
DEFAULT_INDUSTRY_MAP = "data/reference/stock_industry_map.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build strategy composition isolation")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--long-report", default=DEFAULT_LONG_REPORT)
    parser.add_argument("--market-regime-history", default=DEFAULT_REGIME_HISTORY)
    parser.add_argument("--industry-map", default=DEFAULT_INDUSTRY_MAP)
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


def copy_all_rankings(source: Path, target: Path) -> Path:
    target.mkdir(parents=True, exist_ok=True)
    for file in source.glob("ranking_*.csv"):
        shutil.copy2(file, target / file.name)
    return target


def active_dates(regimes: dict[str, dict[str, Any]], family: str) -> set[str]:
    if family == "BIG_BULL":
        return {date_text for date_text, row in regimes.items() if row.get("family") == "BIG_BULL"}
    if family == "HIGH_CHOPPY_CONTEXT":
        return {date_text for date_text, row in regimes.items() if row.get("family") == "HIGH_CHOPPY_CONTEXT"}
    if family == "NON_BIG_BULL_NON_HIGH_CHOPPY":
        return {date_text for date_text, row in regimes.items() if row.get("family") == "NON_BIG_BULL_NON_HIGH_CHOPPY"}
    raise ValueError(f"unsupported family: {family}")


def daily_slice(payload: dict[str, Any], dates: set[str]) -> list[dict[str, Any]]:
    rows = rows_by_date(payload)
    return [rows[date_text] for date_text in sorted(dates) if date_text in rows]


def product_return(rows: list[dict[str, Any]]) -> float | None:
    if not rows:
        return None
    value = 1.0
    for row in rows:
        value *= 1 + n(row.get("daily_return"))
    return round(value - 1, 6)


def exposure_adjusted_return(rows: list[dict[str, Any]]) -> float | None:
    adjusted = []
    for row in rows:
        exposure = n(row.get("gross_exposure"))
        if exposure <= 0:
            continue
        adjusted.append(n(row.get("daily_return")) / exposure)
    return round(sum(adjusted) / len(adjusted), 6) if adjusted else None


def active_day_comparison(
    production: dict[str, Any],
    candidate: dict[str, Any],
    regimes: dict[str, dict[str, Any]],
    family: str,
) -> dict[str, Any]:
    dates = active_dates(regimes, family)
    prod_rows = daily_slice(production, dates)
    cand_rows = daily_slice(candidate, dates)
    common_dates = {str(row["date"]) for row in prod_rows} & {str(row["date"]) for row in cand_rows}
    prod_common = daily_slice(production, common_dates)
    cand_common = daily_slice(candidate, common_dates)
    prod_return = product_return(prod_common)
    cand_return = product_return(cand_common)
    prod_adj = exposure_adjusted_return(prod_common)
    cand_adj = exposure_adjusted_return(cand_common)
    return {
        "family": family,
        "active_date_count": len(dates),
        "common_daily_count": len(common_dates),
        "production_active_return": prod_return,
        "candidate_active_return": cand_return,
        "return_delta": round(n(cand_return) - n(prod_return), 6) if prod_return is not None and cand_return is not None else None,
        "production_exposure_adjusted_daily_return": prod_adj,
        "candidate_exposure_adjusted_daily_return": cand_adj,
        "exposure_adjusted_delta": round(n(cand_adj) - n(prod_adj), 6) if prod_adj is not None and cand_adj is not None else None,
        "production_avg_gross_exposure": round(sum(n(row.get("gross_exposure")) for row in prod_common) / len(prod_common), 6) if prod_common else None,
        "candidate_avg_gross_exposure": round(sum(n(row.get("gross_exposure")) for row in cand_common) / len(cand_common), 6) if cand_common else None,
    }


def trade_slice(payload: dict[str, Any], regimes: dict[str, dict[str, Any]], family: str) -> list[dict[str, Any]]:
    trades = payload.get("trades") if isinstance(payload.get("trades"), list) else []
    return [trade for trade in trades if regimes.get(str(trade.get("ranking_date")), {}).get("family") == family]


def weighted_trade_return(trades: list[dict[str, Any]]) -> float | None:
    total = sum(n(trade.get("entry_notional")) for trade in trades)
    if total <= 0:
        return None
    value = sum(n(trade.get("net_return")) * n(trade.get("entry_notional")) for trade in trades) / total
    return round(value, 6)


def trade_regime_comparison(
    production: dict[str, Any],
    candidate: dict[str, Any],
    regimes: dict[str, dict[str, Any]],
    family: str,
) -> dict[str, Any]:
    prod_trades = trade_slice(production, regimes, family)
    cand_trades = trade_slice(candidate, regimes, family)
    prod_returns = [n(trade.get("net_return")) for trade in prod_trades]
    cand_returns = [n(trade.get("net_return")) for trade in cand_trades]
    prod_weighted = weighted_trade_return(prod_trades)
    cand_weighted = weighted_trade_return(cand_trades)
    return {
        "family": family,
        "production_trade_count": len(prod_trades),
        "candidate_trade_count": len(cand_trades),
        "production_avg_trade_return": round(sum(prod_returns) / len(prod_returns), 6) if prod_returns else None,
        "candidate_avg_trade_return": round(sum(cand_returns) / len(cand_returns), 6) if cand_returns else None,
        "avg_trade_return_delta": round(
            n(round(sum(cand_returns) / len(cand_returns), 6) if cand_returns else None)
            - n(round(sum(prod_returns) / len(prod_returns), 6) if prod_returns else None),
            6,
        ),
        "production_weighted_trade_return": prod_weighted,
        "candidate_weighted_trade_return": cand_weighted,
        "weighted_trade_return_delta": round(n(cand_weighted) - n(prod_weighted), 6) if prod_weighted is not None and cand_weighted is not None else None,
        "sample_status": "OK" if len(prod_trades) >= 30 and len(cand_trades) >= 30 else "LOW_SAMPLE",
    }


def isolation_pair(
    production: dict[str, Any],
    candidate: dict[str, Any],
    sectors: dict[str, str],
) -> dict[str, Any]:
    production_perf = compact_performance(production, sectors)
    candidate_perf = compact_performance(candidate, sectors)
    candidate_perf["comparison_vs_production"] = compare_to_production(candidate_perf, production_perf)
    return {
        "production": production_perf,
        "candidate": candidate_perf,
        "ranking_delta": candidate_perf["comparison_vs_production"],
        "candidate_ranking_better": (
            n(candidate_perf["comparison_vs_production"]["return_delta"]) > 0
            and n(candidate_perf["comparison_vs_production"]["risk_adjusted_delta"]) > 0
        ),
    }


def decision(payload: dict[str, Any]) -> dict[str, Any]:
    trail10 = payload["same_exit_ranking_isolation"]["trail10_same_exit"]
    proxy = payload["same_exit_ranking_isolation"]["production_proxy_same_exit"]
    regimes = payload["regime_normalization"]
    blockers = []
    warnings = []
    if not trail10["candidate_ranking_better"] and not proxy["candidate_ranking_better"]:
        blockers.append("candidate_ranking_does_not_win_under_same_exit_rules")
    if regimes["BIG_BULL"]["active_day"]["return_delta"] is not None and n(regimes["BIG_BULL"]["active_day"]["return_delta"]) <= 0:
        blockers.append("BIG_BULL_gate_not_positive_after_active_day_normalization")
    if regimes["HIGH_CHOPPY_CONTEXT"]["trade_level"]["sample_status"] == "LOW_SAMPLE":
        warnings.append("HIGH_CHOPPY_CONTEXT_low_sample_after_normalization")
    if blockers:
        status = "KEEP_SHADOW_MONITOR"
    elif warnings:
        status = "NEEDS_MORE_DATA_CONTRACT"
    else:
        status = "RETAIN_CANDIDATE_FOR_PROMOTION_REVIEW"
    return {
        "status": status,
        "promotion_ready": False,
        "production_switch_ready": False,
        "blocked_reasons": blockers,
        "warnings": warnings,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    long_path = resolve_path(args.long_report)
    regime_path = resolve_path(args.market_regime_history)
    industry_path = resolve_path(args.industry_map)
    for path in [long_path, regime_path, industry_path]:
        if path is None or not path.exists():
            raise FileNotFoundError(f"找不到必要輸入：{path}")
    long_report = read_json(long_path)
    production_dir = resolve_path((long_report.get("inputs") or {}).get("production_rankings_dir"))
    candidate_dir = resolve_path((long_report.get("inputs") or {}).get("candidate_rankings_dir"))
    if production_dir is None or candidate_dir is None or not production_dir.exists() or not candidate_dir.exists():
        raise FileNotFoundError("long report ranking dirs are missing")

    work_root = PROJECT_ROOT / "artifacts" / "model_experiments" / f"strategy_composition_isolation_work_{args.date}"
    regimes = regime_map(regime_path)
    generated_dirs = build_filtered_rankings(production_dir, candidate_dir, regimes, work_root)
    all_candidate_dir = copy_all_rankings(candidate_dir, work_root / "candidate_all_rankings")
    all_production_dir = copy_all_rankings(production_dir, work_root / "production_all_rankings")

    replays = {
        "production_trail10": write_replay(all_production_dir, work_root / f"production_trail10_same_exit_{args.date}.json", "trail10"),
        "candidate_trail10": write_replay(all_candidate_dir, work_root / f"candidate_trail10_same_exit_{args.date}.json", "trail10"),
        "production_proxy": write_replay(all_production_dir, work_root / f"production_proxy_same_exit_{args.date}.json", "production_proxy"),
        "candidate_proxy": write_replay(all_candidate_dir, work_root / f"candidate_proxy_same_exit_{args.date}.json", "production_proxy"),
        "candidate_big_bull_only": write_replay(
            generated_dirs["candidate_trail10_big_bull_only"],
            work_root / f"candidate_big_bull_only_trail10_{args.date}.json",
            "trail10",
        ),
    }
    sectors = sector_map(industry_path)
    same_exit = {
        "trail10_same_exit": isolation_pair(replays["production_trail10"], replays["candidate_trail10"], sectors),
        "production_proxy_same_exit": isolation_pair(replays["production_proxy"], replays["candidate_proxy"], sectors),
    }
    families = ["BIG_BULL", "HIGH_CHOPPY_CONTEXT", "NON_BIG_BULL_NON_HIGH_CHOPPY"]
    regime_norm = {}
    for family in families:
        regime_norm[family] = {
            "active_day": active_day_comparison(replays["production_trail10"], replays["candidate_trail10"], regimes, family),
            "trade_level": trade_regime_comparison(replays["production_trail10"], replays["candidate_trail10"], regimes, family),
            "gate_active_day": active_day_comparison(replays["production_trail10"], replays["candidate_big_bull_only"], regimes, family)
            if family == "BIG_BULL"
            else None,
        }
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK",
        "contract": {
            "research_only": True,
            "same_exit_ranking_isolation": True,
            "regime_gated_equity_normalization": True,
            "no_new_data_fetch": True,
            "no_model_training": True,
            "changes_production_ranking": False,
            "changes_risk_adjusted_score": False,
            "changes_clawd_message": False,
            "promotion_ready": False,
            "production_switch_ready": False,
        },
        "inputs": {
            "long_report": repo_path(long_path),
            "market_regime_history": repo_path(regime_path),
            "industry_map": repo_path(industry_path),
            "production_rankings_dir": repo_path(production_dir),
            "candidate_rankings_dir": repo_path(candidate_dir),
            "generated_work_root": repo_path(work_root),
        },
        "capital_policy": {
            "initial_cash": 300_000,
            "odd_lot": True,
            "max_position_weight": 0.15,
            "max_gross_exposure": 0.85,
            "costs": {"fee_rate": 0.001425, "tax_rate": 0.003, "slippage_rate": 0.001},
        },
        "same_exit_ranking_isolation": same_exit,
        "regime_normalization": regime_norm,
        "replay_artifacts": {
            name: repo_path(work_root / file_name)
            for name, file_name in {
                "production_trail10": f"production_trail10_same_exit_{args.date}.json",
                "candidate_trail10": f"candidate_trail10_same_exit_{args.date}.json",
                "production_proxy": f"production_proxy_same_exit_{args.date}.json",
                "candidate_proxy": f"candidate_proxy_same_exit_{args.date}.json",
                "candidate_big_bull_only": f"candidate_big_bull_only_trail10_{args.date}.json",
            }.items()
        },
        "coverage_notes": {
            "feature_window": "uses repo data/clean/features.parquet through existing odd-lot replay",
            "normalization_boundary": "active-day metrics compare only dates in the same regime family; trade-level metrics bucket by ranking_date",
        },
    }
    decision_payload = decision(payload)
    payload["decision"] = decision_payload["status"]
    payload["blocked_reasons"] = decision_payload["blocked_reasons"]
    payload["warnings"] = decision_payload["warnings"]
    payload["next_recommended_action"] = "KEEP_SHADOW_UNTIL_RANKING_ISOLATION_AND_REGIME_NORMALIZATION_TURN_POSITIVE"
    return payload


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Strategy Composition Isolation",
        "",
        f"- status: `{payload['status']}`",
        f"- decision: `{payload['decision']}`",
        f"- promotion_ready: `{payload['contract']['promotion_ready']}`",
        "",
        "## Same Exit Ranking Isolation",
        "",
        "| Exit | Candidate Return Delta | Candidate Risk Adj Delta | Candidate Better |",
        "|---|---:|---:|---|",
    ]
    for name, row in payload["same_exit_ranking_isolation"].items():
        delta = row["ranking_delta"]
        lines.append(
            f"| {name} | {pct(delta['return_delta'])} | {delta['risk_adjusted_delta']} | {row['candidate_ranking_better']} |"
        )
    lines.extend(["", "## Regime Normalization", ""])
    lines.append("| Regime | Active Return Delta | Exposure Adj Delta | Trade Sample |")
    lines.append("|---|---:|---:|---|")
    for family, row in payload["regime_normalization"].items():
        active = row["active_day"]
        trade = row["trade_level"]
        lines.append(
            f"| {family} | {pct(active['return_delta'])} | {active['exposure_adjusted_delta']} | {trade['sample_status']} |"
        )
    lines.extend(["", "## Blockers", ""])
    lines.extend([f"- {item}" for item in payload["blocked_reasons"]] or ["- none"])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    output = resolve_path(args.output) or PROJECT_ROOT / "artifacts" / "model_experiments" / f"strategy_composition_isolation_{args.date}.json"
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
