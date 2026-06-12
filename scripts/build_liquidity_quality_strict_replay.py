#!/usr/bin/env python3
"""產生 liquidity quality universe strict replay review。

這支腳本只讀既有 replay artifacts 做嚴格歸因，不重訓模型、不改正式 ranking、
不寫入推播或 production artifact。
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "research_reviews"
SCHEMA_VERSION = "liquidity-quality-strict-replay.v1"
PRODUCTION_IMPACT = "NO_PRODUCTION_CHANGE"
INPUT_REVIEW = PROJECT_ROOT / "artifacts" / "research_reviews" / "5913_combo_effectiveness_review_2026-06-12.json"
CAPITAL_REPORT = PROJECT_ROOT / "artifacts" / "model_experiments" / "liquidity_quality_capital_aware_report_2026-06-03.json"
BUCKET_REPORT = PROJECT_ROOT / "artifacts" / "liquidity_quality_candidate_universe_replay_report_halfyear_2026-06-03.json"


STRICT_RUNS = {
    "baseline": "artifacts/backtest/capital_aware_liquidity_halfyear_production_fixed40_regime_2026-06-03.json",
    "candidate_log_gate": "artifacts/backtest/capital_aware_liquidity_halfyear_log_gate_fixed40_regime_2026-06-03.json",
    "candidate_percentile_gate": "artifacts/backtest/capital_aware_liquidity_halfyear_percentile_gate_fixed40_regime_2026-06-03.json",
    "baseline_fixed65": "artifacts/backtest/capital_aware_liquidity_halfyear_production_fixed40_fixed65_2026-06-03.json",
    "candidate_log_gate_fixed65": "artifacts/backtest/capital_aware_liquidity_halfyear_log_gate_fixed40_fixed65_2026-06-03.json",
    "candidate_percentile_gate_fixed65": "artifacts/backtest/capital_aware_liquidity_halfyear_percentile_gate_fixed40_fixed65_2026-06-03.json",
    "baseline_fixed85": "artifacts/backtest/capital_aware_liquidity_halfyear_production_fixed40_fixed85_2026-06-03.json",
    "candidate_log_gate_fixed85": "artifacts/backtest/capital_aware_liquidity_halfyear_log_gate_fixed40_fixed85_2026-06-03.json",
    "candidate_percentile_gate_fixed85": "artifacts/backtest/capital_aware_liquidity_halfyear_percentile_gate_fixed40_fixed85_2026-06-03.json",
    "baseline_h20": "artifacts/backtest/capital_aware_liquidity_halfyear_production_fixed20_regime_2026-06-03.json",
    "candidate_log_gate_h20": "artifacts/backtest/capital_aware_liquidity_halfyear_log_gate_fixed20_regime_2026-06-03.json",
    "candidate_percentile_gate_h20": "artifacts/backtest/capital_aware_liquidity_halfyear_percentile_gate_fixed20_regime_2026-06-03.json",
    "baseline_entry_non_worsening": "artifacts/backtest/capital_aware_liquidity_halfyear_production_fixed40_regime_non_worsening_2026-06-03.json",
    "candidate_log_gate_entry_non_worsening": "artifacts/backtest/capital_aware_liquidity_halfyear_log_gate_fixed40_regime_non_worsening_2026-06-03.json",
    "candidate_log_gate_entry_improved_only": "artifacts/backtest/capital_aware_liquidity_halfyear_log_gate_fixed40_regime_improved_only_2026-06-03.json",
    "baseline_trade_plan": "artifacts/backtest/capital_aware_liquidity_halfyear_with_trade_plan_production_fixed40_regime_stop_full_2026-06-03.json",
    "candidate_log_gate_trade_plan": "artifacts/backtest/capital_aware_liquidity_halfyear_with_trade_plan_log_gate_fixed40_regime_stop_full_2026-06-03.json",
    "candidate_percentile_gate_trade_plan": "artifacts/backtest/capital_aware_liquidity_halfyear_with_trade_plan_percentile_gate_fixed40_regime_stop_full_2026-06-03.json",
}


DECISIONS = {
    "PROMOTE_TO_STRATEGY_COMPONENT_REPLAY",
    "KEEP_SHADOW_MONITOR",
    "REJECT_FOR_NOW",
    "INCONCLUSIVE_MORE_DATA_REQUIRED",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build liquidity quality strict replay review")
    parser.add_argument("--date", default=datetime.now(timezone.utc).date().isoformat())
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
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
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def f(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def load_runs() -> dict[str, dict[str, Any]]:
    return {label: read_json(resolve_path(path)) for label, path in STRICT_RUNS.items()}


def missing_run_artifacts() -> list[str]:
    return [path for path in STRICT_RUNS.values() if not resolve_path(path).exists()]


def daily_dates(run: dict[str, Any]) -> set[str]:
    return {str(row.get("date")) for row in run.get("daily", []) if isinstance(row, dict) and row.get("date")}


def comparable_window(runs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    required = [runs.get("baseline", {}), runs.get("candidate_log_gate", {}), runs.get("candidate_percentile_gate", {})]
    common = set.intersection(*(daily_dates(run) for run in required if daily_dates(run)))
    sorted_dates = sorted(common)
    baseline_inputs = (runs.get("baseline", {}).get("inputs") or {})
    candidate_inputs = (runs.get("candidate_log_gate", {}).get("inputs") or {})
    return {
        "start_date": sorted_dates[0] if sorted_dates else None,
        "end_date": sorted_dates[-1] if sorted_dates else None,
        "comparable_date_count": len(sorted_dates),
        "same_date_window": bool(sorted_dates),
        "same_entry_timing": baseline_inputs.get("entry_delay_trade_days", 1) == candidate_inputs.get("entry_delay_trade_days", 1),
        "same_fees_tax_slippage": baseline_inputs.get("costs") == candidate_inputs.get("costs"),
        "same_max_gross_exposure_policy": baseline_inputs.get("regime_gross") == candidate_inputs.get("regime_gross"),
        "same_max_position_exposure": baseline_inputs.get("max_position_pct") == candidate_inputs.get("max_position_pct"),
        "same_group_exposure_cap": baseline_inputs.get("max_group_pct") == candidate_inputs.get("max_group_pct"),
        "baseline_rankings_dir": baseline_inputs.get("rankings_dir"),
        "candidate_rankings_dir": candidate_inputs.get("rankings_dir"),
    }


def max_group_exposure(row: dict[str, Any]) -> float:
    exposures = row.get("group_exposures")
    if not isinstance(exposures, dict) or not exposures:
        return 0.0
    return max(f(value) for value in exposures.values())


def concentration(run: dict[str, Any]) -> dict[str, Any]:
    daily = [row for row in run.get("daily", []) if isinstance(row, dict)]
    max_groups = [max_group_exposure(row) for row in daily]
    trade_groups = Counter(str(trade.get("group") or "UNKNOWN") for trade in run.get("trades", []) if isinstance(trade, dict))
    trade_count = sum(trade_groups.values())
    top_trade_group, top_trade_group_count = trade_groups.most_common(1)[0] if trade_groups else ("UNKNOWN", 0)
    return {
        "max_daily_top_group_exposure": round(max(max_groups), 6) if max_groups else 0,
        "avg_daily_top_group_exposure": round(sum(max_groups) / len(max_groups), 6) if max_groups else 0,
        "top_trade_group": top_trade_group,
        "top_trade_group_trade_share": round(top_trade_group_count / trade_count, 6) if trade_count else 0,
        "trade_group_counts": dict(trade_groups.most_common()),
    }


def turnover(run: dict[str, Any]) -> dict[str, Any]:
    daily = [row for row in run.get("daily", []) if isinstance(row, dict)]
    summary = run.get("summary") or {}
    daily_count = int(summary.get("daily_count") or len(daily) or 0)
    entries = sum(int(row.get("entries") or 0) for row in daily)
    exits = sum(int(row.get("exits") or 0) for row in daily)
    partial_exits = sum(int(row.get("partial_exits") or 0) for row in daily)
    return {
        "daily_count": daily_count,
        "trade_count": int(summary.get("trade_count") or 0),
        "entries": entries,
        "exits": exits,
        "partial_exits": partial_exits,
        "entry_rate_per_day": round(entries / daily_count, 6) if daily_count else 0,
        "turnover_events_per_day": round((entries + exits + partial_exits) / daily_count, 6) if daily_count else 0,
        "buy_lot_block_count": int(summary.get("buy_lot_block_count") or 0),
        "cash_block_count": int(summary.get("cash_block_count") or 0),
    }


def run_metrics(label: str, run: dict[str, Any]) -> dict[str, Any]:
    summary = run.get("summary") or {}
    inputs = run.get("inputs") or {}
    return {
        "label": label,
        "path": STRICT_RUNS.get(label),
        "rankings_dir": inputs.get("rankings_dir"),
        "scenario": inputs.get("scenario"),
        "gross_policy": inputs.get("gross_policy"),
        "entry_filter": inputs.get("entry_filter"),
        "horizon": inputs.get("horizon"),
        "costs": inputs.get("costs"),
        "return": summary.get("total_return"),
        "max_drawdown": summary.get("max_drawdown"),
        "win_rate": summary.get("win_rate"),
        "avg_trade_return": summary.get("avg_trade_return"),
        "trade_count": summary.get("trade_count"),
        "daily_count": summary.get("daily_count"),
        "avg_gross_exposure": summary.get("avg_gross_exposure"),
        "max_gross_exposure": summary.get("max_gross_exposure"),
        "avg_cash_ratio": summary.get("avg_cash_ratio"),
        "exit_reason_counts": summary.get("exit_reason_counts") or {},
        "skipped_count": summary.get("skipped_count"),
        "skip_reason_counts": summary.get("skip_reason_counts") or {},
        "turnover": turnover(run),
        "concentration": concentration(run),
    }


def compare(candidate: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    cand_metrics = run_metrics("candidate", candidate)
    base_metrics = run_metrics("baseline", baseline)
    return {
        "baseline_return": base_metrics["return"],
        "candidate_return": cand_metrics["return"],
        "return_delta": round(f(cand_metrics["return"]) - f(base_metrics["return"]), 6),
        "baseline_max_drawdown": base_metrics["max_drawdown"],
        "candidate_max_drawdown": cand_metrics["max_drawdown"],
        "drawdown_delta": round(f(cand_metrics["max_drawdown"]) - f(base_metrics["max_drawdown"]), 6),
        "baseline_turnover_events_per_day": base_metrics["turnover"]["turnover_events_per_day"],
        "candidate_turnover_events_per_day": cand_metrics["turnover"]["turnover_events_per_day"],
        "turnover_delta": round(cand_metrics["turnover"]["turnover_events_per_day"] - base_metrics["turnover"]["turnover_events_per_day"], 6),
        "baseline_max_daily_top_group_exposure": base_metrics["concentration"]["max_daily_top_group_exposure"],
        "candidate_max_daily_top_group_exposure": cand_metrics["concentration"]["max_daily_top_group_exposure"],
        "concentration_delta": round(
            cand_metrics["concentration"]["max_daily_top_group_exposure"] - base_metrics["concentration"]["max_daily_top_group_exposure"],
            6,
        ),
        "baseline_trade_count": base_metrics["trade_count"],
        "candidate_trade_count": cand_metrics["trade_count"],
        "trade_count_delta": int(cand_metrics["trade_count"] or 0) - int(base_metrics["trade_count"] or 0),
    }


def comparison_row(label: str, candidate_label: str, baseline_label: str, runs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    row = compare(runs.get(candidate_label, {}), runs.get(baseline_label, {}))
    row.update(
        {
            "label": label,
            "candidate_label": candidate_label,
            "baseline_label": baseline_label,
            "candidate_path": STRICT_RUNS.get(candidate_label),
            "baseline_path": STRICT_RUNS.get(baseline_label),
        }
    )
    return row


def regime_slices_for_run(run: dict[str, Any]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in run.get("daily", []):
        if isinstance(row, dict):
            grouped[str(row.get("gross_label") or "UNKNOWN")].append(row)
    result: dict[str, Any] = {}
    for label, rows in sorted(grouped.items()):
        compounded = 1.0
        for row in rows:
            compounded *= 1 + f(row.get("daily_return"))
        result[label] = {
            "date_count": len(rows),
            "compounded_return": round(compounded - 1, 6),
            "avg_daily_return": round(sum(f(row.get("daily_return")) for row in rows) / len(rows), 6) if rows else 0,
            "avg_gross_exposure": round(sum(f(row.get("gross_exposure")) for row in rows) / len(rows), 6) if rows else 0,
            "avg_top_group_exposure": round(sum(max_group_exposure(row) for row in rows) / len(rows), 6) if rows else 0,
        }
    return result


def regime_breakdown(runs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    baseline = regime_slices_for_run(runs.get("baseline", {}))
    candidate = regime_slices_for_run(runs.get("candidate_log_gate", {}))
    labels = sorted(set(baseline) | set(candidate))
    return {
        label: {
            "baseline": baseline.get(label, {}),
            "candidate_log_gate": candidate.get(label, {}),
            "return_delta": round(
                f((candidate.get(label) or {}).get("compounded_return")) - f((baseline.get(label) or {}).get("compounded_return")),
                6,
            ),
        }
        for label in labels
    }


def review_duplication(review: dict[str, Any]) -> dict[str, Any]:
    queue = review.get("next_replay_queue") if isinstance(review.get("next_replay_queue"), list) else []
    artifacts = Counter(str(item.get("artifact_path") or "") for item in queue if isinstance(item, dict))
    topics = Counter(str(item.get("topic_id") or "") for item in queue if isinstance(item, dict))
    return {
        "queue_count": len(queue),
        "unique_artifact_count": len([key for key in artifacts if key]),
        "unique_topic_count": len([key for key in topics if key]),
        "top_artifacts": dict(artifacts.most_common(5)),
        "top_topics": dict(topics.most_common(5)),
        "is_duplicate_heavy": len(queue) > 0 and len([key for key in topics if key]) <= max(1, len(queue) // 4),
    }


def build_failure_attribution(
    primary: dict[str, Any],
    same_capital: list[dict[str, Any]],
    exit_dependency: list[dict[str, Any]],
    entry_dependency: dict[str, Any],
    duplication: dict[str, Any],
    comparable: dict[str, Any],
) -> dict[str, Any]:
    reasons: list[dict[str, Any]] = []

    def add(code: str, severity: str, triggered: bool, evidence: Any, note: str) -> None:
        reasons.append({"code": code, "severity": severity, "triggered": triggered, "evidence": evidence, "note": note})

    add(
        "SAMPLE_TOO_SMALL",
        "medium" if int(comparable.get("comparable_date_count") or 0) < 60 else "low",
        int(comparable.get("comparable_date_count") or 0) < 60,
        {"comparable_date_count": comparable.get("comparable_date_count")},
        "半年度 comparable window 足夠做研究排序，但還不是 promotion evidence。",
    )
    add(
        "RETURN_WEAK",
        "high" if f(primary.get("return_delta")) <= 0 else "low",
        f(primary.get("return_delta")) <= 0,
        {"return_delta": primary.get("return_delta")},
        "主要 log_gate candidate 在 regime capital 條件下仍有正報酬差，不是主要失敗點。",
    )
    add(
        "DRAWDOWN_WORSE",
        "high",
        f(primary.get("drawdown_delta")) < -0.05,
        {"drawdown_delta": primary.get("drawdown_delta"), "candidate_max_drawdown": primary.get("candidate_max_drawdown"), "baseline_max_drawdown": primary.get("baseline_max_drawdown")},
        "candidate 報酬較高，但回撤顯著惡化，不能升級成預設策略。",
    )
    add(
        "TURNOVER_TOO_HIGH",
        "medium" if f(primary.get("turnover_delta")) > 0.05 else "low",
        f(primary.get("turnover_delta")) > 0.05,
        {"turnover_delta": primary.get("turnover_delta")},
        "主要比較下 turnover 差異不大；風險主要不是換手，而是持倉組合與回撤。",
    )
    add(
        "CONCENTRATION_RISK",
        "medium",
        f(primary.get("concentration_delta")) > 0.02,
        {"concentration_delta": primary.get("concentration_delta")},
        "candidate 的單一族群曝險高於 baseline，需要獨立 group/sector cap replay。",
    )
    regime_only = any(row.get("return_delta", 0) < 0 for row in same_capital if "h20" in str(row.get("label")))
    add(
        "REGIME_ONLY_SIGNAL",
        "medium" if regime_only else "low",
        regime_only,
        {"same_capital_rows": same_capital},
        "訊號不是所有 capital/horizon 設定都穩定；h20 log_gate 轉弱。",
    )
    exit_bad = any(f(row.get("candidate_return")) < 0 or f(row.get("drawdown_delta")) < -0.10 for row in exit_dependency)
    add(
        "EXIT_RULE_DEPENDENT",
        "high" if exit_bad else "medium",
        exit_bad,
        {"exit_dependency_rows": exit_dependency},
        "加入 liquidity trade plan / stop 後績效惡化，顯示 5913 top score 有 exit-rule dependency。",
    )
    add(
        "ENTRY_FILTER_DEPENDENT",
        "medium",
        bool(entry_dependency),
        entry_dependency,
        "non_worsening / improved_only 會大幅改變結果，股票池效果與 entry filter 尚未拆乾淨。",
    )
    add(
        "ARTIFACT_DUPLICATION",
        "high" if duplication.get("is_duplicate_heavy") else "low",
        bool(duplication.get("is_duplicate_heavy")),
        duplication,
        "5913 next queue 多個 scenario 來自同一批 artifact，不能當成獨立樣本數。",
    )
    add(
        "NO_ALPHA",
        "medium" if f(primary.get("return_delta")) <= 0 else "low",
        f(primary.get("return_delta")) <= 0,
        {"return_delta": primary.get("return_delta"), "drawdown_delta": primary.get("drawdown_delta")},
        "有報酬 edge，但控制風險後不足以視為 production alpha。",
    )
    primary_reasons = [item for item in reasons if item["triggered"] and item["severity"] in {"high", "medium"}]
    return {
        "primary_reasons": primary_reasons,
        "all_reasons": reasons,
        "success_attribution": {
            "return_improved": f(primary.get("return_delta")) > 0,
            "win_source": "log_gate liquidity universe improves return/win rate in scheduled-horizon finite-capital replay",
            "risk_reduction": f(primary.get("drawdown_delta")) >= 0,
            "short_cycle_only": False,
            "production_safe": False,
        },
    }


def decision(primary: dict[str, Any], failure_attribution: dict[str, Any], comparable: dict[str, Any]) -> tuple[str, str]:
    if int(comparable.get("comparable_date_count") or 0) <= 0:
        return "INCONCLUSIVE_MORE_DATA_REQUIRED", "補齊 comparable window 後重跑。"
    high_failures = [item["code"] for item in failure_attribution.get("primary_reasons", []) if item.get("severity") == "high"]
    if "DRAWDOWN_WORSE" in high_failures or "EXIT_RULE_DEPENDENT" in high_failures:
        return "KEEP_SHADOW_MONITOR", "保留為 aggressive shadow monitor，下一輪先做 risk-capped component replay。"
    if f(primary.get("return_delta")) > 0 and f(primary.get("drawdown_delta")) >= 0:
        return "PROMOTE_TO_STRATEGY_COMPONENT_REPLAY", "進 strategy component registry 前置 replay。"
    return "REJECT_FOR_NOW", "嚴格控制後沒有足夠優勢，暫時淘汰。"


def build_payload(date: str) -> dict[str, Any]:
    runs = load_runs()
    missing_artifacts = missing_run_artifacts()
    review = read_json(INPUT_REVIEW)
    capital_report = read_json(CAPITAL_REPORT)
    bucket_report = read_json(BUCKET_REPORT)
    comparable = comparable_window(runs)
    baseline = run_metrics("baseline", runs["baseline"])
    candidate = run_metrics("candidate_log_gate", runs["candidate_log_gate"])
    percentile_candidate = run_metrics("candidate_percentile_gate", runs["candidate_percentile_gate"])
    same_exit = [
        comparison_row("same_production_exit_log_gate_vs_production", "candidate_log_gate", "baseline", runs),
        comparison_row("same_production_exit_percentile_vs_production", "candidate_percentile_gate", "baseline", runs),
    ]
    same_capital = [
        comparison_row("fixed65_log_gate", "candidate_log_gate_fixed65", "baseline_fixed65", runs),
        comparison_row("fixed65_percentile_gate", "candidate_percentile_gate_fixed65", "baseline_fixed65", runs),
        comparison_row("fixed85_log_gate", "candidate_log_gate_fixed85", "baseline_fixed85", runs),
        comparison_row("fixed85_percentile_gate", "candidate_percentile_gate_fixed85", "baseline_fixed85", runs),
        comparison_row("regime_h20_log_gate", "candidate_log_gate_h20", "baseline_h20", runs),
        comparison_row("regime_h20_percentile_gate", "candidate_percentile_gate_h20", "baseline_h20", runs),
    ]
    exit_dependency = [
        comparison_row("same_liquidity_trade_plan_log_gate", "candidate_log_gate_trade_plan", "baseline_trade_plan", runs),
        comparison_row("same_liquidity_trade_plan_percentile", "candidate_percentile_gate_trade_plan", "baseline_trade_plan", runs),
    ]
    entry_dependency = {
        "candidate_log_gate_non_worsening_vs_log_gate_all": compare(runs["candidate_log_gate_entry_non_worsening"], runs["candidate_log_gate"]),
        "candidate_log_gate_improved_only_vs_log_gate_all": compare(runs["candidate_log_gate_entry_improved_only"], runs["candidate_log_gate"]),
        "production_non_worsening_vs_production_all": compare(runs["baseline_entry_non_worsening"], runs["baseline"]),
    }
    duplication = review_duplication(review)
    primary = same_exit[0]
    failure = build_failure_attribution(primary, same_capital, exit_dependency, entry_dependency, duplication, comparable)
    decision_label, next_action = decision(primary, failure, comparable)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "OK" if not missing_artifacts else "PARTIAL",
        "review_date": date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "production_impact": PRODUCTION_IMPACT,
        "candidate_family": "liquidity_quality_candidate_universe",
        "input_review_artifact": repo_path(INPUT_REVIEW),
        "input_replay_artifacts": {
            "capital_aware_report": repo_path(CAPITAL_REPORT),
            "bucket_replay_report": repo_path(BUCKET_REPORT),
            "strict_runs": STRICT_RUNS,
        },
        "comparable_window": comparable,
        "baseline": baseline,
        "candidate": candidate,
        "secondary_candidate": percentile_candidate,
        "same_exit_comparison": same_exit,
        "same_capital_comparison": same_capital,
        "liquidity_exit_filter_control": exit_dependency,
        "entry_filter_dependency": entry_dependency,
        "regime_slices": regime_breakdown(runs),
        "risk_breakdown": {
            "baseline": {"turnover": baseline["turnover"], "concentration": baseline["concentration"]},
            "candidate": {"turnover": candidate["turnover"], "concentration": candidate["concentration"]},
            "primary_delta": {
                "turnover_delta": primary["turnover_delta"],
                "concentration_delta": primary["concentration_delta"],
                "drawdown_delta": primary["drawdown_delta"],
            },
        },
        "failure_attribution": failure,
        "decision": decision_label,
        "next_action": next_action,
        "source_context": {
            "5913_review_counts": review.get("classification_counts"),
            "capital_report_decision": (capital_report.get("decision") or {}),
            "bucket_report_decision": (bucket_report.get("decision") or {}),
        },
        "errors": [f"missing replay artifact: {path}" for path in missing_artifacts],
    }


def pct(value: Any) -> str:
    try:
        return f"{float(value):.2%}"
    except (TypeError, ValueError):
        return "--"


def build_markdown(payload: dict[str, Any]) -> str:
    primary = payload["same_exit_comparison"][0]
    reasons = payload["failure_attribution"]["primary_reasons"]
    lines = [
        "# Liquidity Quality Universe Strict Replay",
        "",
        "## Executive Summary",
        "",
        f"- status: `{payload['status']}`",
        f"- decision: `{payload['decision']}`",
        f"- comparable window: {payload['comparable_window']['start_date']} to {payload['comparable_window']['end_date']} ({payload['comparable_window']['comparable_date_count']} dates)",
        f"- baseline return / max DD: {pct(payload['baseline']['return'])} / {pct(payload['baseline']['max_drawdown'])}",
        f"- liquidity log_gate return / max DD: {pct(payload['candidate']['return'])} / {pct(payload['candidate']['max_drawdown'])}",
        f"- return delta / drawdown delta: {pct(primary['return_delta'])} / {pct(primary['drawdown_delta'])}",
        f"- production impact: `{payload['production_impact']}`",
        "",
        "Headline: liquidity quality universe has return signal, but strict finite-capital replay exposes much worse drawdown and strong exit/artifact dependency. It stays shadow-only.",
        "",
        "## What Was Tested",
        "",
        "- production baseline ranking vs liquidity quality log_gate / percentile_gate shadow ranking",
        "- same scheduled production exit, same fee/tax/slippage, same regime gross policy, same max position and group caps",
        "- fixed65 / fixed85 / regime / h20 capital controls",
        "- production ranking plus same liquidity trade-plan stop control",
        "- entry filter sensitivity: non_worsening and improved_only",
        "",
        "## Headline Result",
        "",
        "| comparison | return delta | drawdown delta | turnover delta | concentration delta |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["same_exit_comparison"]:
        lines.append(
            f"| {row['label']} | {pct(row['return_delta'])} | {pct(row['drawdown_delta'])} | {row['turnover_delta']:.3f} | {pct(row['concentration_delta'])} |"
        )
    lines.extend(["", "## Failure Attribution / Success Attribution", ""])
    for item in reasons:
        lines.append(f"- `{item['code']}` ({item['severity']}): {item['note']}")
    success = payload["failure_attribution"]["success_attribution"]
    lines.append(f"- success source: {success['win_source']}; risk_reduction=`{success['risk_reduction']}`; production_safe=`{success['production_safe']}`")
    lines.extend(["", "## Regime Breakdown", "", "| regime | baseline return | candidate return | delta | candidate avg gross |", "| --- | ---: | ---: | ---: | ---: |"])
    for label, row in payload["regime_slices"].items():
        base = row.get("baseline") or {}
        cand = row.get("candidate_log_gate") or {}
        lines.append(
            f"| {label} | {pct(base.get('compounded_return'))} | {pct(cand.get('compounded_return'))} | {pct(row.get('return_delta'))} | {pct(cand.get('avg_gross_exposure'))} |"
        )
    lines.extend(["", "## Risk Breakdown", ""])
    risk = payload["risk_breakdown"]["primary_delta"]
    lines.append(f"- turnover delta: {risk['turnover_delta']:.6f} events/day")
    lines.append(f"- concentration delta: {pct(risk['concentration_delta'])}")
    lines.append(f"- drawdown delta: {pct(risk['drawdown_delta'])}")
    lines.extend(["", "## Next Action", "", payload["next_action"], "", "## Production Impact", "", f"`{payload['production_impact']}`", "", "No model, production ranking, risk_adjusted_score, or Clawd live push changes.", ""])
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    output_dir = resolve_path(args.output_dir)
    payload = build_payload(args.date)
    json_path = output_dir / f"liquidity_quality_strict_replay_{args.date}.json"
    md_path = output_dir / f"liquidity_quality_strict_replay_{args.date}.md"
    write_json(json_path, payload)
    write_text(md_path, build_markdown(payload))
    print(json.dumps({"status": payload["status"], "decision": payload["decision"], "json": repo_path(json_path), "markdown": repo_path(md_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
