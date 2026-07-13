#!/usr/bin/env python3
"""以具名 profile 建立 odd-lot 決策研究報告。"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "odd-lot-decision-suite.v1"
PROFILES = ("exit_horizon", "exit_strategy", "regime_throttle", "candidate_decision")
EXIT_HORIZON_SCHEMA_VERSION = "odd-lot-exit-horizon-sensitivity-report.v1"
HORIZONS = (20, 40, 60)
EXIT_STRATEGY_SCHEMA_VERSION = "odd-lot-exit-strategy-report.v1"
EXIT_STRATEGY_VARIANTS = (
    "production_baseline",
    "production_ptp25_third",
    "candidate_baseline",
    "candidate_ptp25_third",
    "candidate_ptp25_half",
)
REGIME_THROTTLE_SCHEMA_VERSION = "odd-lot-regime-throttle-report.v1"
REGIME_THROTTLE_VARIANTS = ("baseline", "hc45", "hc55", "hc65")
CANDIDATE_DECISION_SCHEMA_VERSION = "odd-lot-candidate-decision-report.v1"


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


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def exit_horizon_artifact_path(kind: str, horizon: int, capital: int, run_date: str) -> Path:
    capital_label = f"{capital // 1000}k"
    if horizon == 40:
        names = {
            "candidate_baseline": f"odd_lot_portfolio_candidate_top7_sl12_min5_{capital_label}_gross75_pos12_{run_date}.json",
            "candidate_exit": f"odd_lot_portfolio_candidate_top7_sl12_min5_{capital_label}_exit_ptp25_third_runner_{run_date}.json",
            "production_exit": f"odd_lot_portfolio_production_top7_sl12_min5_{capital_label}_exit_ptp25_third_runner_{run_date}.json",
        }
    else:
        names = {
            "candidate_baseline": f"odd_lot_portfolio_candidate_top7_sl12_min5_{capital_label}_h{horizon}_baseline_{run_date}.json",
            "candidate_exit": f"odd_lot_portfolio_candidate_top7_sl12_min5_{capital_label}_h{horizon}_exit_ptp25_third_runner_{run_date}.json",
            "production_exit": f"odd_lot_portfolio_production_top7_sl12_min5_{capital_label}_h{horizon}_exit_ptp25_third_runner_{run_date}.json",
        }
    if kind not in names:
        raise ValueError(f"unknown kind: {kind}")
    return PROJECT_ROOT / "artifacts" / "model_experiments" / names[kind]


def return_drawdown_ratio(total_return: float, max_drawdown: float) -> float | None:
    if max_drawdown >= 0:
        return None
    return round(total_return / abs(max_drawdown), 6)


def exit_horizon_row(kind: str, horizon: int, capital: int, path: Path) -> dict[str, Any]:
    summary = read_json(path).get("summary", {})
    total_return = safe_float(summary.get("total_return"))
    max_drawdown = safe_float(summary.get("max_drawdown"))
    return {
        "kind": kind,
        "horizon": horizon,
        "capital": capital,
        "path": repo_path(path),
        "total_return": round(total_return, 6),
        "max_drawdown": round(max_drawdown, 6),
        "return_drawdown_ratio": return_drawdown_ratio(total_return, max_drawdown),
        "trade_count": summary.get("trade_count"),
        "skipped_count": summary.get("skipped_count"),
        "avg_cash_weight": summary.get("avg_cash_weight"),
    }


def add_exit_horizon_comparisons(rows: list[dict[str, Any]]) -> None:
    by_key = {(row["kind"], row["horizon"]): row for row in rows}
    for row in rows:
        baseline = by_key.get(("candidate_baseline", row["horizon"]), {})
        production = by_key.get(("production_exit", row["horizon"]), {})
        row["return_delta_vs_candidate_baseline"] = round(
            safe_float(row.get("total_return")) - safe_float(baseline.get("total_return")), 6
        )
        row["drawdown_delta_vs_candidate_baseline"] = round(
            safe_float(row.get("max_drawdown")) - safe_float(baseline.get("max_drawdown")), 6
        )
        row["return_delta_vs_production_exit"] = round(
            safe_float(row.get("total_return")) - safe_float(production.get("total_return")), 6
        )


def exit_horizon_decision(rows: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [row for row in rows if row["kind"] == "candidate_exit"]
    best_ratio = max(candidates, key=lambda row: safe_float(row.get("return_drawdown_ratio")), default=None)
    h40 = next((row for row in candidates if row["horizon"] == 40), {})
    h20 = next((row for row in candidates if row["horizon"] == 20), {})
    h60 = next((row for row in candidates if row["horizon"] == 60), {})
    status = "HORIZON_40_BALANCED_CANDIDATE" if best_ratio and best_ratio.get("horizon") == 40 else "HORIZON_FOLLOWUP_REQUIRED"
    return {
        "status": status,
        "selected_horizon": best_ratio.get("horizon") if best_ratio else None,
        "promotion_ready": False,
        "h20_return_vs_h40": round(safe_float(h20.get("total_return")) - safe_float(h40.get("total_return")), 6),
        "h20_drawdown_vs_h40": round(safe_float(h20.get("max_drawdown")) - safe_float(h40.get("max_drawdown")), 6),
        "h60_return_vs_h40": round(safe_float(h60.get("total_return")) - safe_float(h40.get("total_return")), 6),
        "h60_drawdown_vs_h40": round(safe_float(h60.get("max_drawdown")) - safe_float(h40.get("max_drawdown")), 6),
        "reason": "20D 報酬較高但回撤更深；60D 報酬與報酬/回撤比下降；40D 是目前平衡點。",
    }


def build_exit_horizon_section(date_text: str, capital: int) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    missing: list[str | None] = []
    for horizon in HORIZONS:
        for kind in ("candidate_baseline", "candidate_exit", "production_exit"):
            path = exit_horizon_artifact_path(kind, horizon, capital, date_text)
            if not path.exists():
                missing.append(repo_path(path))
                continue
            rows.append(exit_horizon_row(kind, horizon, capital, path))
    add_exit_horizon_comparisons(rows)
    return {
        "schema_version": EXIT_HORIZON_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": date_text,
        "status": "OK" if rows and not missing else "FAILED",
        "contract": {
            "research_only": True,
            "model_changes": False,
            "production_ranking_changes": False,
            "promotion_ready": False,
            "fixed_capital_odd_lot": True,
            "horizon_sensitivity_only": True,
        },
        "inputs": {
            "capital": capital,
            "horizons": list(HORIZONS),
            "exit_rule": "sell_one_third_at_25pct_profit_then_runner_to_stop_or_horizon",
        },
        "decision": exit_horizon_decision(rows),
        "rows": rows,
        "missing": missing,
    }


def exit_strategy_artifact_path(variant: str, capital: int, run_date: str) -> Path:
    capital_label = f"{capital // 1000}k"
    names = {
        "production_baseline": f"odd_lot_portfolio_production_top7_sl12_min5_{capital_label}_gross75_pos12_{run_date}.json",
        "production_ptp25_third": f"odd_lot_portfolio_production_top7_sl12_min5_{capital_label}_exit_ptp25_third_runner_{run_date}.json",
        "candidate_baseline": f"odd_lot_portfolio_candidate_top7_sl12_min5_{capital_label}_gross75_pos12_{run_date}.json",
        "candidate_ptp25_third": f"odd_lot_portfolio_candidate_top7_sl12_min5_{capital_label}_exit_ptp25_third_runner_{run_date}.json",
        "candidate_ptp25_half": f"odd_lot_portfolio_candidate_top7_sl12_min5_{capital_label}_exit_ptp25_half_runner_{run_date}.json",
    }
    if variant not in names:
        raise ValueError(f"unknown variant: {variant}")
    return PROJECT_ROOT / "artifacts" / "model_experiments" / names[variant]


def risk_ratio(total_return: float, max_drawdown: float) -> float | None:
    if max_drawdown >= 0:
        return None
    return round(total_return / abs(max_drawdown), 6)


def exit_strategy_row(variant: str, capital: int, path: Path) -> dict[str, Any]:
    payload = read_json(path)
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    total_return = safe_float(summary.get("total_return"))
    max_drawdown = safe_float(summary.get("max_drawdown"))
    return {
        "variant": variant,
        "capital": capital,
        "path": repo_path(path),
        "total_return": round(total_return, 6),
        "max_drawdown": round(max_drawdown, 6),
        "return_drawdown_ratio": risk_ratio(total_return, max_drawdown),
        "trade_count": summary.get("trade_count"),
        "win_rate": summary.get("win_rate"),
        "avg_cash_weight": summary.get("avg_cash_weight"),
        "below_minimum_odd_lot_count": summary.get("below_minimum_odd_lot_count"),
    }


def summarize_exit_strategy(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, dict[str, Any]] = {}
    for variant in EXIT_STRATEGY_VARIANTS:
        items = [row for row in rows if row["variant"] == variant]
        if not items:
            continue
        ratios = [safe_float(row.get("return_drawdown_ratio")) for row in items if row.get("return_drawdown_ratio") is not None]
        result[variant] = {
            "capital_count": len(items),
            "avg_return": round(sum(safe_float(row.get("total_return")) for row in items) / len(items), 6),
            "avg_max_drawdown": round(sum(safe_float(row.get("max_drawdown")) for row in items) / len(items), 6),
            "avg_return_drawdown_ratio": round(sum(ratios) / len(ratios), 6) if ratios else None,
            "min_return": min(safe_float(row.get("total_return")) for row in items),
            "worst_drawdown": min(safe_float(row.get("max_drawdown")) for row in items),
            "avg_trade_count": round(sum(safe_float(row.get("trade_count")) for row in items) / len(items), 6),
            "avg_cash_weight": round(sum(safe_float(row.get("avg_cash_weight")) for row in items) / len(items), 6),
        }
    return result


def add_exit_strategy_comparisons(rows: list[dict[str, Any]]) -> None:
    by_key = {(row["variant"], row["capital"]): row for row in rows}
    for row in rows:
        candidate_baseline = by_key.get(("candidate_baseline", row["capital"]), {})
        production_peer = by_key.get(("production_ptp25_third", row["capital"]), {})
        production_baseline = by_key.get(("production_baseline", row["capital"]), {})
        row["return_delta_vs_candidate_baseline"] = round(
            safe_float(row.get("total_return")) - safe_float(candidate_baseline.get("total_return")), 6
        )
        row["drawdown_delta_vs_candidate_baseline"] = round(
            safe_float(row.get("max_drawdown")) - safe_float(candidate_baseline.get("max_drawdown")), 6
        )
        row["return_delta_vs_production_peer"] = round(
            safe_float(row.get("total_return")) - safe_float(production_peer.get("total_return")), 6
        )
        row["drawdown_delta_vs_production_peer"] = round(
            safe_float(row.get("max_drawdown")) - safe_float(production_peer.get("max_drawdown")), 6
        )
        row["return_delta_vs_production_baseline"] = round(
            safe_float(row.get("total_return")) - safe_float(production_baseline.get("total_return")), 6
        )


def exit_strategy_decision(rows: list[dict[str, Any]], summary: dict[str, dict[str, Any]]) -> dict[str, Any]:
    third_rows = [row for row in rows if row["variant"] == "candidate_ptp25_third"]
    third = summary.get("candidate_ptp25_third", {})
    baseline = summary.get("candidate_baseline", {})
    beats_production_peer = all(safe_float(row.get("return_delta_vs_production_peer")) > 0 for row in third_rows)
    improves_drawdown = all(safe_float(row.get("drawdown_delta_vs_candidate_baseline")) > 0 for row in third_rows)
    ratio_better = safe_float(third.get("avg_return_drawdown_ratio")) > safe_float(baseline.get("avg_return_drawdown_ratio"))
    return_gap = safe_float(third.get("avg_return")) - safe_float(baseline.get("avg_return"))
    if beats_production_peer and improves_drawdown and ratio_better and return_gap >= -0.05:
        status = "EXIT_STRATEGY_FOLLOWUP_CANDIDATE"
        reason = "+25% 賣 1/3 在三個本金級距都勝過同規則 production，並降低候選 baseline 回撤；報酬有犧牲但仍在可研究範圍。"
    else:
        status = "EXIT_STRATEGY_MONITOR_ONLY"
        reason = "出場策略尚未同時通過 production peer、回撤與報酬保留檢查。"
    return {
        "status": status,
        "selected": "candidate_ptp25_third" if status == "EXIT_STRATEGY_FOLLOWUP_CANDIDATE" else None,
        "promotion_ready": False,
        "beats_production_peer_all_capitals": beats_production_peer,
        "improves_drawdown_all_capitals": improves_drawdown,
        "avg_return_gap_vs_candidate_baseline": round(return_gap, 6),
        "reason": reason,
    }


def build_exit_strategy_section(date_text: str, capital_levels: str) -> dict[str, Any]:
    capitals = [int(float(value.strip())) for value in capital_levels.split(",") if value.strip()]
    rows: list[dict[str, Any]] = []
    missing: list[str | None] = []
    for capital in capitals:
        for variant in EXIT_STRATEGY_VARIANTS:
            path = exit_strategy_artifact_path(variant, capital, date_text)
            if not path.exists():
                missing.append(repo_path(path))
                continue
            rows.append(exit_strategy_row(variant, capital, path))
    add_exit_strategy_comparisons(rows)
    summary = summarize_exit_strategy(rows)
    return {
        "schema_version": EXIT_STRATEGY_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": date_text,
        "status": "OK" if rows and not missing else "FAILED",
        "contract": {
            "research_only": True,
            "model_changes": False,
            "production_ranking_changes": False,
            "promotion_ready": False,
            "fixed_capital_odd_lot": True,
            "partial_take_profit_runner": True,
        },
        "inputs": {
            "capital_levels": capitals,
            "candidate_rule": "top7_sl12_min5_gross75_pos12",
            "exit_rule": "sell_one_third_at_25pct_profit_then_runner_to_stop_or_40d_horizon",
        },
        "summary": summary,
        "decision": exit_strategy_decision(rows, summary),
        "rows": rows,
        "missing": missing,
    }


def regime_throttle_artifact_path(name: str, capital: int, run_date: str) -> Path:
    capital_label = f"{capital // 1000}k"
    if name == "baseline":
        file_name = f"odd_lot_portfolio_candidate_top7_sl12_min5_{capital_label}_gross75_pos12_{run_date}.json"
    else:
        file_name = f"odd_lot_portfolio_candidate_top7_sl12_min5_{capital_label}_regime_signal_throttle_{name}_{run_date}.json"
    return PROJECT_ROOT / "artifacts" / "model_experiments" / file_name


def entry_limit_summary(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("daily") if isinstance(payload.get("daily"), list) else []
    buckets: dict[float, dict[str, Any]] = {}
    for row in rows:
        raw_limit = row.get("entry_gross_exposure_limit")
        if raw_limit is None:
            raw_limit = row.get("max_gross_exposure_limit")
        if raw_limit is None:
            continue
        limit = safe_float(raw_limit)
        bucket = buckets.setdefault(limit, {"entry_gross_exposure_limit": limit, "days": 0, "entries": 0})
        bucket["days"] += 1
        bucket["entries"] += int(row.get("entries") or 0)
    return [buckets[key] for key in sorted(buckets)]


def regime_throttle_row(name: str, path: Path, baseline_summary: dict[str, Any]) -> dict[str, Any]:
    payload = read_json(path)
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    total_return = safe_float(summary.get("total_return"))
    max_drawdown = safe_float(summary.get("max_drawdown"))
    baseline_return = safe_float(baseline_summary.get("total_return"))
    baseline_drawdown = safe_float(baseline_summary.get("max_drawdown"))
    return {
        "variant": name,
        "path": repo_path(path),
        "total_return": round(total_return, 6),
        "max_drawdown": round(max_drawdown, 6),
        "trade_count": summary.get("trade_count"),
        "avg_gross_exposure": summary.get("avg_gross_exposure"),
        "avg_cash_weight": summary.get("avg_cash_weight"),
        "return_delta_vs_baseline": round(total_return - baseline_return, 6),
        "drawdown_delta_vs_baseline": round(max_drawdown - baseline_drawdown, 6),
        "entry_limit_summary": entry_limit_summary(payload),
    }


def regime_throttle_decision(rows: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [row for row in rows if row["variant"] != "baseline"]
    improved_drawdown = [row for row in candidates if safe_float(row.get("drawdown_delta_vs_baseline")) > 0]
    improved_return = [row for row in candidates if safe_float(row.get("return_delta_vs_baseline")) > 0]
    best_return = max(candidates, key=lambda row: safe_float(row.get("return_delta_vs_baseline")), default=None)
    if improved_drawdown:
        status = "THROTTLE_FOLLOWUP_CANDIDATE"
        reason = "至少一個 HIGH_CHOPPY 降曝險版本改善回撤，可進下一輪多本金驗證。"
    elif improved_return:
        status = "THROTTLE_MONITOR_ONLY"
        reason = "降曝險版本有報酬改善，但沒有改善回撤；不可當風險控制升級證據。"
    else:
        status = "THROTTLE_REJECTED"
        reason = "降曝險沒有改善報酬或回撤。"
    return {
        "status": status,
        "promotion_ready": False,
        "selected_followup": best_return.get("variant") if best_return else None,
        "reason": reason,
    }


def build_regime_throttle_section(date_text: str, capital: int, variant: str, setting: str) -> dict[str, Any]:
    baseline_path = regime_throttle_artifact_path("baseline", capital, date_text)
    missing: list[str | None] = []
    if not baseline_path.exists():
        missing.append(repo_path(baseline_path))
        baseline_summary: dict[str, Any] = {}
    else:
        baseline_summary = read_json(baseline_path).get("summary", {})
    rows: list[dict[str, Any]] = []
    for name in REGIME_THROTTLE_VARIANTS:
        path = regime_throttle_artifact_path(name, capital, date_text)
        if not path.exists():
            missing.append(repo_path(path))
            continue
        rows.append(regime_throttle_row(name, path, baseline_summary))
    return {
        "schema_version": REGIME_THROTTLE_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": date_text,
        "status": "OK" if len(rows) == len(REGIME_THROTTLE_VARIANTS) and not missing else "FAILED",
        "contract": {
            "research_only": True,
            "model_changes": False,
            "production_ranking_changes": False,
            "promotion_ready": False,
            "fixed_capital_odd_lot": True,
            "signal_day_regime_controls_next_entry": True,
        },
        "inputs": {
            "capital": capital,
            "variant": variant,
            "setting": setting,
        },
        "decision": regime_throttle_decision(rows),
        "rows": rows,
        "missing": missing,
    }


def default_report_path(kind: str, run_date: str) -> Path:
    return PROJECT_ROOT / "artifacts" / "model_experiments" / f"odd_lot_{kind}_report_{run_date}.json"


def safe_get(payload: dict[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def candidate_decision(
    exit_report: dict[str, Any],
    horizon_report: dict[str, Any],
    throttle_report: dict[str, Any],
) -> dict[str, Any]:
    exit_status = safe_get(exit_report, "decision", "status")
    horizon_status = safe_get(horizon_report, "decision", "status")
    throttle_status = safe_get(throttle_report, "decision", "status")
    blockers: list[str] = []
    if exit_status != "EXIT_STRATEGY_FOLLOWUP_CANDIDATE":
        blockers.append(f"exit strategy is {exit_status}")
    if horizon_status != "HORIZON_40_BALANCED_CANDIDATE":
        blockers.append(f"horizon sensitivity is {horizon_status}")
    if throttle_status not in {"THROTTLE_MONITOR_ONLY", "THROTTLE_REJECTED"}:
        blockers.append(f"regime throttle has unresolved status {throttle_status}")
    if blockers:
        status = "BLOCKED"
        next_stage = None
        reason = "候選策略尚未通過出場、持有上限、盤勢降曝險三個研究閘門。"
    else:
        status = "READY_FOR_SHADOW_MONITOR"
        next_stage = "daily_shadow_candidate_replay"
        reason = "出場策略可進 shadow；HIGH_CHOPPY 降曝險不併入主線，只保留監控。"
    return {
        "status": status,
        "selected_candidate": "candidate_top7_gross75_pos12_sl12_ptp25_sell_one_third_runner_40d" if status != "BLOCKED" else None,
        "next_stage": next_stage,
        "promotion_ready": False,
        "model_promotion_ready": False,
        "production_ranking_change_ready": False,
        "blockers": blockers,
        "reason": reason,
    }


def build_candidate_decision_section(
    date_text: str,
    exit_strategy_report: str | Path | None,
    horizon_sensitivity_report: str | Path | None,
    regime_throttle_report: str | Path | None,
) -> dict[str, Any]:
    exit_path = resolve_path(exit_strategy_report) or default_report_path("exit_strategy", date_text)
    horizon_path = resolve_path(horizon_sensitivity_report) or default_report_path("exit_horizon_sensitivity", date_text)
    throttle_path = resolve_path(regime_throttle_report) or default_report_path("regime_throttle", date_text)
    missing = [repo_path(path) for path in (exit_path, horizon_path, throttle_path) if not path.exists()]
    exit_report = read_json(exit_path) if exit_path.exists() else {}
    horizon_report = read_json(horizon_path) if horizon_path.exists() else {}
    throttle_report = read_json(throttle_path) if throttle_path.exists() else {}
    decision = candidate_decision(exit_report, horizon_report, throttle_report) if not missing else {
        "status": "FAILED",
        "selected_candidate": None,
        "next_stage": None,
        "promotion_ready": False,
        "model_promotion_ready": False,
        "production_ranking_change_ready": False,
        "blockers": [f"missing report: {path}" for path in missing],
        "reason": "必要研究報告缺失。",
    }
    return {
        "schema_version": CANDIDATE_DECISION_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": date_text,
        "status": "OK" if not missing else "FAILED",
        "contract": {
            "research_only": True,
            "model_changes": False,
            "production_ranking_changes": False,
            "promotion_ready": False,
            "shadow_monitor_only": decision.get("status") == "READY_FOR_SHADOW_MONITOR",
        },
        "inputs": {
            "exit_strategy_report": repo_path(exit_path),
            "horizon_sensitivity_report": repo_path(horizon_path),
            "regime_throttle_report": repo_path(throttle_path),
        },
        "source_decisions": {
            "exit_strategy": safe_get(exit_report, "decision", "status"),
            "horizon_sensitivity": safe_get(horizon_report, "decision", "status"),
            "regime_throttle": safe_get(throttle_report, "decision", "status"),
        },
        "candidate_spec": {
            "ranking_source": "all-candidate top7",
            "gross_exposure": 0.75,
            "max_position_weight": 0.12,
            "stop_loss_pct": 0.12,
            "partial_take_profit_pct": 0.25,
            "partial_take_profit_fraction": 1 / 3,
            "runner_exit": "stop_loss_or_40d_horizon",
            "high_choppy_throttle": "monitor_only_not_included",
        },
        "decision": decision,
        "missing": missing,
    }


def build_section(
    profile: str,
    *,
    date_text: str,
    capital_levels: str = "100000,300000,500000",
    capital: int = 300_000,
    variant: str = "candidate_top7_sl12_min5",
    setting: str = "gross75_pos12",
    exit_strategy_report: str | Path | None = None,
    horizon_sensitivity_report: str | Path | None = None,
    regime_throttle_report: str | Path | None = None,
) -> dict[str, Any]:
    if profile == "exit_horizon":
        return build_exit_horizon_section(date_text, capital)
    if profile == "exit_strategy":
        return build_exit_strategy_section(date_text, capital_levels)
    if profile == "regime_throttle":
        return build_regime_throttle_section(date_text, capital, variant, setting)
    if profile == "candidate_decision":
        return build_candidate_decision_section(
            date_text,
            exit_strategy_report,
            horizon_sensitivity_report,
            regime_throttle_report,
        )
    raise ValueError(f"unknown profile: {profile}")


def build_suite(date_text: str, sections: dict[str, dict[str, Any]]) -> dict[str, Any]:
    results = {
        profile: {
            "schema_version": section.get("schema_version"),
            "status": section.get("status"),
            "decision": safe_get(section, "decision", "status"),
        }
        for profile, section in sections.items()
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": date_text,
        "status": "OK" if sections and all(section.get("status") == "OK" for section in sections.values()) else "FAILED",
        "contract": {
            "research_only": True,
            "model_changes": False,
            "production_ranking_changes": False,
            "promotion_ready": False,
        },
        "manifest": {
            "date": date_text,
            "profiles": list(sections),
            "inputs": {profile: section.get("inputs") for profile, section in sections.items()},
            "results": results,
        },
        "summary": {
            "profiles": list(sections),
            "decisions": {profile: result["decision"] for profile, result in results.items()},
        },
        "sections": sections,
    }


def render_exit_horizon_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Odd-Lot Exit Horizon Sensitivity",
        "",
        f"- status: {payload['status']}",
        f"- decision: {payload['decision']['status']}",
        f"- selected_horizon: {payload['decision'].get('selected_horizon')}",
        f"- promotion_ready: {payload['contract']['promotion_ready']}",
        "",
        "## Rows",
        "",
    ]
    for row in payload["rows"]:
        lines.append(
            "- h{horizon} {kind}: return={total_return}, maxDD={max_drawdown}, "
            "return_dd={return_drawdown_ratio}, skipped={skipped_count}".format(**row)
        )
    return "\n".join(lines) + "\n"


def render_exit_strategy_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Odd-Lot Exit Strategy",
        "",
        f"- status: {payload['status']}",
        f"- decision: {payload['decision']['status']}",
        f"- selected: {payload['decision'].get('selected')}",
        f"- promotion_ready: {payload['contract']['promotion_ready']}",
        "",
        "## Summary",
        "",
    ]
    for variant, item in payload["summary"].items():
        lines.append(
            f"- {variant}: avg_return={item.get('avg_return')}, avg_maxDD={item.get('avg_max_drawdown')}, "
            f"avg_return_dd={item.get('avg_return_drawdown_ratio')}, avg_cash={item.get('avg_cash_weight')}"
        )
    return "\n".join(lines) + "\n"


def render_regime_throttle_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Odd-Lot Regime Throttle",
        "",
        f"- status: {payload['status']}",
        f"- decision: {payload['decision']['status']}",
        f"- selected_followup: {payload['decision'].get('selected_followup')}",
        f"- promotion_ready: {payload['contract']['promotion_ready']}",
        "",
        "## Rows",
        "",
    ]
    for row in payload["rows"]:
        lines.append(
            "- {variant}: return={total_return}, maxDD={max_drawdown}, "
            "return_delta={return_delta_vs_baseline}, drawdown_delta={drawdown_delta_vs_baseline}, trades={trade_count}".format(**row)
        )
    return "\n".join(lines) + "\n"


def render_candidate_decision_markdown(payload: dict[str, Any]) -> str:
    decision = payload["decision"]
    lines = [
        "# Odd-Lot Candidate Decision",
        "",
        f"- status: {payload['status']}",
        f"- decision: {decision.get('status')}",
        f"- selected_candidate: {decision.get('selected_candidate')}",
        f"- next_stage: {decision.get('next_stage')}",
        f"- promotion_ready: {decision.get('promotion_ready')}",
        "",
        "## Source Decisions",
        "",
    ]
    for key, value in payload["source_decisions"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Candidate Spec", ""])
    for key, value in payload["candidate_spec"].items():
        lines.append(f"- {key}: {value}")
    return "\n".join(lines) + "\n"


SECTION_RENDERERS = {
    "exit_horizon": render_exit_horizon_markdown,
    "exit_strategy": render_exit_strategy_markdown,
    "regime_throttle": render_regime_throttle_markdown,
    "candidate_decision": render_candidate_decision_markdown,
}


def render_suite_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Odd-Lot Decision Suite",
        "",
        f"- status: {payload['status']}",
        f"- profiles: {', '.join(payload['summary']['profiles'])}",
        "",
    ]
    for profile, section in payload["sections"].items():
        lines.extend([f"## {profile}", "", *SECTION_RENDERERS[profile](section).splitlines()[2:], ""])
    return "\n".join(lines)


def default_profile_output(profile: str, date_text: str) -> Path:
    names = {
        "exit_horizon": f"odd_lot_exit_horizon_sensitivity_report_{date_text}.json",
        "exit_strategy": f"odd_lot_exit_strategy_report_{date_text}.json",
        "regime_throttle": f"odd_lot_regime_throttle_report_{date_text}.json",
        "candidate_decision": f"odd_lot_candidate_decision_report_{date_text}.json",
    }
    return PROJECT_ROOT / "artifacts" / "model_experiments" / names[profile]


def write_profile(profile: str, payload: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output.with_suffix(".md").write_text(SECTION_RENDERERS[profile](payload), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build odd-lot decision suite")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--profile", choices=("all", *PROFILES), default="all")
    parser.add_argument("--capital", type=int, default=300_000)
    parser.add_argument("--capital-levels", default="100000,300000,500000")
    parser.add_argument("--variant", default="candidate_top7_sl12_min5")
    parser.add_argument("--setting", default="gross75_pos12")
    parser.add_argument("--exit-strategy-report", default=None)
    parser.add_argument("--horizon-sensitivity-report", default=None)
    parser.add_argument("--regime-throttle-report", default=None)
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    common = {
        "date_text": args.date,
        "capital_levels": args.capital_levels,
        "capital": args.capital,
        "variant": args.variant,
        "setting": args.setting,
        "exit_strategy_report": args.exit_strategy_report,
        "horizon_sensitivity_report": args.horizon_sensitivity_report,
        "regime_throttle_report": args.regime_throttle_report,
    }
    if args.profile != "all":
        payload = build_section(args.profile, **common)
        output = resolve_path(args.output) if args.output else default_profile_output(args.profile, args.date)
        if output is None:
            raise RuntimeError("output resolution failed")
        write_profile(args.profile, payload, output)
        print(
            json.dumps(
                {
                    "status": payload["status"],
                    "decision": safe_get(payload, "decision", "status"),
                    "output": repo_path(output),
                    "profile": args.profile,
                },
                ensure_ascii=False,
            )
        )
        return 0 if payload["status"] == "OK" else 1

    sections = {
        profile: build_section(profile, **common)
        for profile in ("exit_horizon", "exit_strategy", "regime_throttle")
    }
    for profile, section in sections.items():
        write_profile(profile, section, default_profile_output(profile, args.date))
    common.update(
        {
            "exit_strategy_report": default_profile_output("exit_strategy", args.date),
            "horizon_sensitivity_report": default_profile_output("exit_horizon", args.date),
            "regime_throttle_report": default_profile_output("regime_throttle", args.date),
        }
    )
    sections["candidate_decision"] = build_section("candidate_decision", **common)
    write_profile(
        "candidate_decision",
        sections["candidate_decision"],
        default_profile_output("candidate_decision", args.date),
    )
    payload = build_suite(args.date, sections)
    output = (
        resolve_path(args.output)
        if args.output
        else PROJECT_ROOT / "artifacts" / "model_experiments" / f"odd_lot_decision_suite_{args.date}.json"
    )
    if output is None:
        raise RuntimeError("output resolution failed")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output.with_suffix(".md").write_text(render_suite_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "output": repo_path(output),
                "profiles": payload["summary"]["profiles"],
                "decisions": payload["summary"]["decisions"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
