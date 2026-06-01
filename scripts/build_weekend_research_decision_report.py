#!/usr/bin/env python3
"""整理週末研究矩陣的決策報告。

此腳本只讀研究 artifacts，將結果分成可升 shadow、觀察、淘汰與資料阻塞。
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "weekend-research-decision-report.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build weekend research decision report")
    parser.add_argument("--date", default=None, help="治理摘要日期；既有週末矩陣輸入仍由各 artifact 參數指定")
    parser.add_argument("--coverage", default="artifacts/research_dataset_coverage_2026-05-29.json")
    parser.add_argument("--strategy-comparison", default="artifacts/backtest/strategy_matrix_comparison_recent_2026-04-08_2026-05-13.json")
    parser.add_argument("--replay-comparison", default="artifacts/backtest/replay_variant_comparison_2026-04-08_2026-05-13.json")
    parser.add_argument("--industry-walkforward", default="artifacts/industry_momentum_walkforward_shadow.json")
    parser.add_argument("--factor-monitor", default="artifacts/factor_monitor_report.json")
    parser.add_argument("--weekend-matrix", default="artifacts/backtest/weekend_research_matrix_2026-04-08_2026-05-13.json")
    parser.add_argument("--window-stability", default="artifacts/backtest/replay_window_stability_2026-04-08_2026-05-13.json")
    parser.add_argument("--ledger-stats", default=None)
    parser.add_argument("--output", default="artifacts/backtest/weekend_research_decision_report_2026-04-08_2026-05-13.json")
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def load_json(path_text: str | Path) -> dict[str, Any]:
    path = resolve_path(path_text)
    if not path.exists():
        return {"_missing": True, "_path": repo_path(path)}
    return json.loads(path.read_text(encoding="utf-8"))


def latest_ledger_stats(run_date: str | None = None) -> dict[str, Any]:
    model_dir = PROJECT_ROOT / "artifacts" / "model_experiments"
    if run_date:
        preferred = model_dir / f"model_experiment_ledger_stats_{run_date}.json"
        if preferred.exists():
            return load_json(preferred)
    matches = sorted(model_dir.glob("model_experiment_ledger_stats_????-??-??.json"))
    return load_json(matches[-1]) if matches else {}


def f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def rows_by_variant(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        result.setdefault(str(row.get("variant")), []).append(row)
    return result


def best_by_horizon(rows: list[dict[str, Any]], variant: str, horizon: int) -> dict[str, Any] | None:
    matches = [
        row for row in rows
        if row.get("variant") == variant and int(row.get("horizon") or 0) == horizon
    ]
    if not matches:
        return None
    return max(matches, key=lambda row: f(row.get("score"), -999))


def replay_row(rows: list[dict[str, Any]], variant: str, horizon: int) -> dict[str, Any] | None:
    for row in rows:
        if row.get("variant") == variant and int(row.get("horizon") or 0) == horizon:
            return row
    return None


def report_variants(strategy: dict[str, Any], replay: dict[str, Any]) -> list[str]:
    strategy_order = [
        str(item.get("label"))
        for item in strategy.get("variants", [])
        if item.get("label")
    ]
    replay_order = [
        str(item.get("label"))
        for item in replay.get("variants", [])
        if item.get("label")
    ]
    replay_labels = set(replay_order)
    ordered = [variant for variant in strategy_order if variant in replay_labels]
    ordered.extend(variant for variant in replay_order if variant not in ordered)
    return ordered


def classify_variant(
    *,
    variant: str,
    strategy_rows: list[dict[str, Any]],
    replay_rows: list[dict[str, Any]],
    stability_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    h5_strategy = best_by_horizon(strategy_rows, variant, 5)
    h10_strategy = best_by_horizon(strategy_rows, variant, 10)
    h5_replay = replay_row(replay_rows, variant, 5)
    h10_replay = replay_row(replay_rows, variant, 10)
    current_h5 = replay_row(replay_rows, "current", 5)
    current_h10 = replay_row(replay_rows, "current", 10)

    h5_avg_delta = f((h5_replay or {}).get("delta_portfolio_avg_return"))
    h5_dd_delta = f((h5_replay or {}).get("delta_portfolio_max_drawdown"))
    h10_avg_delta = f((h10_replay or {}).get("delta_portfolio_avg_return"))
    h10_dd_delta = f((h10_replay or {}).get("delta_portfolio_max_drawdown"))
    h5_stability = next(
        (
            row for row in stability_rows
            if row.get("variant") == variant and int(row.get("horizon") or 0) == 5
        ),
        None,
    )

    decision = "MONITOR_ONLY"
    reasons: list[str] = []
    balanced_h5_delta = f((replay_row(replay_rows, "guard_balanced", 5) or {}).get("delta_portfolio_avg_return"))

    if variant == "current":
        decision = "BASELINE"
        reasons.append("baseline variant")
    elif h5_avg_delta > 0.004 and h5_dd_delta > 0.05:
        decision = "PROMOTE_TO_SHADOW"
        reasons.append("5d replay portfolio avg return and max drawdown both improve vs current")
    elif h5_avg_delta > 0:
        decision = "MONITOR_ONLY"
        reasons.append("5d improves but does not clear shadow promotion threshold")
    else:
        decision = "REJECT"
        reasons.append("5d replay does not improve enough")

    if variant == "guard_strict" and (h10_avg_delta <= 0 or h5_avg_delta < balanced_h5_delta):
        decision = "MONITOR_ONLY"
        reasons.append("strict guard is useful as risk bound but underperforms balanced return profile")
    if h5_stability:
        reasons.append(f"5d window stability={h5_stability.get('decision')}")
        if decision == "PROMOTE_TO_SHADOW" and h5_stability.get("decision") != "STABLE_SHADOW_CANDIDATE":
            decision = "MONITOR_ONLY"
            reasons.append("downgraded because 5d window stability did not clear stable candidate gate")
    if h10_avg_delta > 0 and h10_dd_delta < 0:
        reasons.append("10d return improves but drawdown worsens, keep separate from 5d strategy")

    return {
        "variant": variant,
        "decision": decision,
        "primary_horizon": 5 if decision == "PROMOTE_TO_SHADOW" else None,
        "strategy_best_5d": h5_strategy,
        "strategy_best_10d": h10_strategy,
        "replay_5d": h5_replay,
        "replay_10d": h10_replay,
        "stability_5d": h5_stability,
        "current_replay_5d": current_h5,
        "current_replay_10d": current_h10,
        "reasons": reasons,
    }


def build_data_backlog(coverage: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in coverage.get("dimensions", []):
        if row.get("status") != "BLOCKED_DATA":
            continue
        rows.append(
            {
                "dimension_id": row.get("dimension_id"),
                "label": row.get("label"),
                "status": row.get("status"),
                "latest_coverage": row.get("latest_coverage", row.get("latest_stock_coverage")),
                "required_next_step": next_step_for_blocker(str(row.get("dimension_id"))),
                "notes": row.get("notes", []),
            }
        )
    return rows


def next_step_for_blocker(dimension_id: str) -> str:
    if dimension_id == "monthly_revenue":
        return "補月營收 as-of join，latest coverage >= 70% 後再進矩陣"
    if dimension_id == "fundamentals_goodinfo":
        return "補 Goodinfo/MOPS cache 到 universe coverage >= 70%，並確認公布日 as-of"
    if dimension_id == "per_stock_chip_flow":
        return "建立個股日頻外資/投信/自營買賣超資料表，latest coverage >= 70%"
    return "補齊資料覆蓋與 as-of contract"


def factor_summary(factor_monitor: dict[str, Any]) -> dict[str, Any]:
    summary = factor_monitor.get("summary", {})
    top_abs = summary.get("top_abs_ic", [])
    return {
        "status": factor_monitor.get("status"),
        "factor_count": summary.get("factor_count"),
        "ok_count": summary.get("ok_count"),
        "warn_count": summary.get("warn_count"),
        "top_abs_ic": top_abs[:10],
    }


def weekend_matrix_contract_status(weekend: dict[str, Any]) -> dict[str, Any]:
    contract = weekend.get("contract") if isinstance(weekend.get("contract"), dict) else {}
    required = {
        "research_only": True,
        "does_not_fetch_data": True,
        "does_not_train_model": True,
        "does_not_change_production_ranking": True,
    }
    checks = {key: contract.get(key) is expected for key, expected in required.items()}
    step_failures = [
        {"name": step.get("name"), "status": step.get("status")}
        for step in weekend.get("steps", [])
        if step.get("status") != "OK"
    ]
    blockers: list[str] = []
    if weekend.get("_missing"):
        blockers.append("weekend matrix artifact missing")
    if weekend and not weekend.get("_missing") and weekend.get("status") != "OK":
        blockers.append("weekend matrix status is not OK")
    for key, ok in checks.items():
        if not ok:
            blockers.append(f"weekend matrix contract {key} is not satisfied")
    if step_failures:
        blockers.append("weekend matrix has failed steps")
    status = "OK" if not blockers else ("WARN" if weekend.get("_missing") else "FAILED")
    return {
        "status": status,
        "source_status": weekend.get("status"),
        "contract": contract,
        "contract_checks": checks,
        "failed_steps": step_failures,
        "blockers": blockers,
    }


def industry_decision(industry: dict[str, Any], coverage: dict[str, Any]) -> dict[str, Any]:
    latest_expected = coverage.get("inputs", {}).get("latest_date")
    latest_actual = industry.get("summary", {}).get("latest_trade_date")
    recommendation = industry.get("recommendation", {})
    decision = recommendation.get("decision") or "unknown"
    freshness = "STALE" if latest_expected and latest_actual and latest_actual != latest_expected else "CURRENT"
    return {
        "decision": "MONITOR_ONLY",
        "source_decision": decision,
        "freshness": freshness,
        "latest_expected": latest_expected,
        "latest_actual": latest_actual,
        "walkforward": industry.get("walkforward", {}),
        "reason": "產業動能可作分層/敘事；return uplift 小且集中度上升，不升主策略。",
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    coverage = load_json(args.coverage)
    strategy = load_json(args.strategy_comparison)
    replay = load_json(args.replay_comparison)
    industry = load_json(args.industry_walkforward)
    factor_monitor = load_json(args.factor_monitor)
    weekend = load_json(args.weekend_matrix)
    stability = load_json(args.window_stability)
    ledger_stats = load_json(args.ledger_stats) if args.ledger_stats else latest_ledger_stats(args.date)
    weekend_evidence = weekend_matrix_contract_status(weekend)

    strategy_rows = strategy.get("best_by_horizon", [])
    replay_rows = replay.get("rows", [])
    variants = report_variants(strategy, replay)
    decisions = [
        classify_variant(
            variant=str(variant),
            strategy_rows=strategy_rows,
            replay_rows=replay_rows,
            stability_rows=stability.get("summary", []),
        )
        for variant in variants
    ]

    missing_inputs = any(item.get("_missing") for item in [coverage, strategy, replay, industry, factor_monitor, weekend])
    report_status = "OK"
    if weekend_evidence["status"] == "FAILED":
        report_status = "FAILED"
    elif missing_inputs or weekend_evidence["status"] == "WARN":
        report_status = "WARN"
    safe_decisions = decisions if weekend_evidence["status"] == "OK" else [
        {**item, "decision": "MONITOR_ONLY", "primary_horizon": None, "reasons": [*item.get("reasons", []), "blocked because weekend matrix evidence is not OK"]}
        for item in decisions
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": report_status,
        "contract": {
            "research_only": weekend_evidence["contract_checks"].get("research_only") is True,
            "does_not_fetch_data": weekend_evidence["contract_checks"].get("does_not_fetch_data") is True,
            "does_not_train_model": weekend_evidence["contract_checks"].get("does_not_train_model") is True,
            "does_not_change_production_ranking": weekend_evidence["contract_checks"].get("does_not_change_production_ranking") is True,
            "decision_labels": ["BASELINE", "PROMOTE_TO_SHADOW", "MONITOR_ONLY", "REJECT", "BLOCKED_DATA"],
        },
        "inputs": {
            "coverage": repo_path(resolve_path(args.coverage)),
            "strategy_comparison": repo_path(resolve_path(args.strategy_comparison)),
            "replay_comparison": repo_path(resolve_path(args.replay_comparison)),
            "industry_walkforward": repo_path(resolve_path(args.industry_walkforward)),
            "factor_monitor": repo_path(resolve_path(args.factor_monitor)),
            "weekend_matrix": repo_path(resolve_path(args.weekend_matrix)),
            "window_stability": repo_path(resolve_path(args.window_stability)),
        },
        "summary": {
            "promote_to_shadow": [item["variant"] for item in safe_decisions if item["decision"] == "PROMOTE_TO_SHADOW"],
            "monitor_only": [item["variant"] for item in safe_decisions if item["decision"] == "MONITOR_ONLY"],
            "reject": [item["variant"] for item in safe_decisions if item["decision"] == "REJECT"],
            "blocked_data": coverage.get("summary", {}).get("blocked_dimensions", []),
            "report_blockers": weekend_evidence["blockers"],
            "recommended_next_test": "Run longer/rolling validation for 5d guard_balanced and overlay separately; keep 10d as separate risk track.",
        },
        "model_governance": {
            "available": bool(ledger_stats.get("summary")),
            "source": ledger_stats.get("ledger"),
            "candidate_hit_rate": ledger_stats.get("summary", {}).get("candidate_hit_rate"),
            "expired_count": ledger_stats.get("summary", {}).get("expired_count"),
            "repeated_failed_hypothesis_family": ledger_stats.get("summary", {}).get("repeated_failed_hypothesis_family", []),
            "next_research_priorities": ledger_stats.get("summary", {}).get("next_research_priorities", []),
            "blocked_promotion_reasons": ledger_stats.get("summary", {}).get("blocked_promotion_reasons", []),
        },
        "variant_decisions": safe_decisions,
        "industry_momentum": industry_decision(industry, coverage),
        "factor_monitor": factor_summary(factor_monitor),
        "window_stability": stability.get("summary", []),
        "data_backlog": build_data_backlog(coverage),
        "weekend_matrix_evidence": weekend_evidence,
        "weekend_matrix_steps": [
            {"name": step.get("name"), "status": step.get("status")}
            for step in weekend.get("steps", [])
        ],
    }


def pct(value: Any) -> str:
    if value is None:
        return "--"
    try:
        return f"{float(value):.2%}"
    except (TypeError, ValueError):
        return "--"


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Weekend Research Decision Report",
        "",
        f"- status：`{payload['status']}`",
        f"- generated_at：`{payload['generated_at']}`",
        f"- promote_to_shadow：`{payload['summary']['promote_to_shadow']}`",
        f"- monitor_only：`{payload['summary']['monitor_only']}`",
        f"- reject：`{payload['summary']['reject']}`",
        f"- blocked_data：`{payload['summary']['blocked_data']}`",
        "",
        "## Variant Decisions",
        "",
        "| Variant | Decision | 5d Avg Δ | 5d DD Δ | 10d Avg Δ | 10d DD Δ | Reasons |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for item in payload["variant_decisions"]:
        h5 = item.get("replay_5d") or {}
        h10 = item.get("replay_10d") or {}
        lines.append(
            "| {variant} | {decision} | {h5avg} | {h5dd} | {h10avg} | {h10dd} | {reasons} |".format(
                variant=item["variant"],
                decision=item["decision"],
                h5avg=pct(h5.get("delta_portfolio_avg_return")),
                h5dd=pct(h5.get("delta_portfolio_max_drawdown")),
                h10avg=pct(h10.get("delta_portfolio_avg_return")),
                h10dd=pct(h10.get("delta_portfolio_max_drawdown")),
                reasons="；".join(item.get("reasons", [])),
            )
        )
    lines.extend(["", "## Industry Momentum", ""])
    industry = payload["industry_momentum"]
    lines.append(f"- decision：`{industry['decision']}`")
    lines.append(f"- freshness：`{industry['freshness']}` expected={industry['latest_expected']} actual={industry['latest_actual']}")
    lines.append(f"- reason：{industry['reason']}")
    lines.extend(["", "## Data Backlog", "", "| Dimension | Coverage | Next Step |", "|---|---:|---|"])
    for row in payload["data_backlog"]:
        lines.append(f"| {row['label']} | {pct(row.get('latest_coverage'))} | {row['required_next_step']} |")
    governance = payload.get("model_governance", {})
    lines.extend(["", "## Model Governance", ""])
    if not governance.get("available"):
        lines.append("- ledger stats unavailable")
    else:
        lines.append(f"- candidate_hit_rate：`{governance.get('candidate_hit_rate')}`")
        lines.append(f"- expired_count：`{governance.get('expired_count')}`")
        for item in governance.get("next_research_priorities", []):
            lines.append(f"- next：{item}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_report(args)
    output_path = resolve_path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output_path.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "output": repo_path(output_path),
                "promote_to_shadow": payload["summary"]["promote_to_shadow"],
                "blocked_data": payload["summary"]["blocked_data"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if payload["status"] in {"OK", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
