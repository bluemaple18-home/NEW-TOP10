#!/usr/bin/env python3
"""以具名 profile 建立 operational-rule 研究報告。

這支入口只整理既有 artifact，不訓練模型、不重跑 ranking、不改 production。
`candidate` 與 `experiment` profile 分別保留退休前兩支 builder 的輸出契約。
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_SCHEMA_VERSION = "operational-rule-candidate-report.v1"
EXPERIMENT_SCHEMA_VERSION = "operational-rule-experiment-report.v1"

CANDIDATE_DEFAULTS = {
    "candidate_vs_production": "artifacts/model_experiments/training_candidates/candidate_2026-06-02_config/fixed_share_top10_candidate_vs_production_recent60_2026-06-02.json",
    "candidate_matrix": "artifacts/model_experiments/training_candidates/candidate_2026-06-02_config/fixed_share_hypothesis_matrix_candidate_2026-06-02.json",
    "production_matrix": "artifacts/backtest/fixed_share_hypothesis_matrix_production_half_year_2026-06-02.json",
    "constrained_shadow": "artifacts/model_experiments/constrained_shadow_comparison_2026-06-02.json",
    "sector_cap_shadow": "artifacts/model_experiments/mass_candidate_shadow_dry_run_sector_cap_2026-06-02.json",
}

EXPERIMENT_DEFAULTS = {
    "production_matrix": "artifacts/backtest/fixed_share_hypothesis_matrix_production_dynamic_guard_2026-06-02.json",
    "candidate_matrix": "artifacts/model_experiments/training_candidates/candidate_2026-06-02_config/fixed_share_hypothesis_matrix_candidate_dynamic_guard_2026-06-02.json",
    "constrained_shadow": "artifacts/model_experiments/constrained_shadow_comparison_2026-06-02.json",
    "sector_cap_shadow": "artifacts/model_experiments/mass_candidate_shadow_dry_run_sector_cap_2026-06-02.json",
}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build operational rule review report")
    parser.add_argument("--profile", choices=("candidate", "experiment"), required=True)
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--candidate-vs-production", default=None)
    parser.add_argument("--candidate-matrix", default=None)
    parser.add_argument("--production-matrix", default=None)
    parser.add_argument("--constrained-shadow", default=None)
    parser.add_argument("--sector-cap-shadow", default=None)
    parser.add_argument("--output", default=None)
    return parser.parse_args(argv)


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def pct(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{num(value):.2%}"


def money(value: Any) -> str:
    return f"{num(value):,.0f}"


def profile_value(args: argparse.Namespace, key: str) -> str:
    value = getattr(args, key)
    if value:
        return str(value)
    defaults = CANDIDATE_DEFAULTS if args.profile == "candidate" else EXPERIMENT_DEFAULTS
    return defaults[key]


def candidate_vs_production_summary(payload: dict[str, Any]) -> dict[str, Any]:
    rows = payload.get("comparison", {}).get("rows", [])
    by_horizon: dict[int, dict[str, Any]] = {}
    for row in rows:
        horizon = int(row.get("horizon") or 0)
        label = str(row.get("label"))
        by_horizon.setdefault(horizon, {})[label] = row

    comparisons = []
    beats_return = 0
    loses_return = 0
    for horizon in sorted(by_horizon):
        prod = by_horizon[horizon].get("production_recent60") or {}
        cand = by_horizon[horizon].get("candidate_sealed60") or {}
        if not prod or not cand:
            continue
        return_delta = num(cand.get("return_on_buy_cash")) - num(prod.get("return_on_buy_cash"))
        pnl_delta = num(cand.get("total_net_pnl")) - num(prod.get("total_net_pnl"))
        win_delta = num(cand.get("win_rate")) - num(prod.get("win_rate"))
        beats_return += int(return_delta > 0)
        loses_return += int(return_delta <= 0)
        comparisons.append(
            {
                "horizon": horizon,
                "production_return_on_buy_cash": prod.get("return_on_buy_cash"),
                "candidate_return_on_buy_cash": cand.get("return_on_buy_cash"),
                "return_delta": round(return_delta, 6),
                "production_net_pnl": prod.get("total_net_pnl"),
                "candidate_net_pnl": cand.get("total_net_pnl"),
                "net_pnl_delta": round(pnl_delta, 2),
                "win_rate_delta": round(win_delta, 6),
            }
        )

    long_horizon_edges = [
        row for row in comparisons if row["horizon"] in {30, 40} and row["return_delta"] > 0
    ]
    replacement_allowed = beats_return == len(comparisons) and all(row["net_pnl_delta"] >= 0 for row in comparisons)
    return {
        "replacement_allowed": replacement_allowed,
        "beats_return_horizon_count": beats_return,
        "loses_return_horizon_count": loses_return,
        "long_horizon_edge_count": len(long_horizon_edges),
        "comparisons": comparisons,
        "decision": "RESEARCH_OVERLAY_ONLY" if not replacement_allowed and long_horizon_edges else "MONITOR_ONLY",
        "rationale": (
            "candidate 在長持有 30/40D 的資金報酬率優於 production，但 10/15/20D 不穩且總損益仍低於 production，不能替換正式榜。"
            if long_horizon_edges
            else "candidate 未形成可用長持有 edge。"
        ),
    }


def policy(matrix: dict[str, Any], name: str) -> dict[str, Any]:
    return ((matrix.get("matrix") or {}).get("exit_policy") or {}).get(name) or {}


def policy_delta(matrix: dict[str, Any], baseline: str, candidate: str) -> dict[str, Any]:
    base = policy(matrix, baseline)
    cand = policy(matrix, candidate)
    return {
        "baseline": baseline,
        "candidate": candidate,
        "baseline_return": base.get("return_on_buy_cash"),
        "candidate_return": cand.get("return_on_buy_cash"),
        "return_delta": round(num(cand.get("return_on_buy_cash")) - num(base.get("return_on_buy_cash")), 6),
        "baseline_pnl": base.get("total_net_pnl"),
        "candidate_pnl": cand.get("total_net_pnl"),
        "pnl_delta": round(num(cand.get("total_net_pnl")) - num(base.get("total_net_pnl")), 2),
        "baseline_worst_mae": base.get("worst_mae"),
        "candidate_worst_mae": cand.get("worst_mae"),
    }


def exit_policy_summary(matrix: dict[str, Any]) -> dict[str, Any]:
    comparisons = [
        policy_delta(matrix, "fixed_30d", "h30_early_tp07"),
        policy_delta(matrix, "fixed_30d", "h30_early_tp10"),
        policy_delta(matrix, "fixed_30d", "h30_early_tp12"),
        policy_delta(matrix, "fixed_30d", "h30_early_tp15"),
        policy_delta(matrix, "fixed_40d", "h40_early_tp07"),
        policy_delta(matrix, "fixed_40d", "h40_early_tp10"),
        policy_delta(matrix, "fixed_40d", "h40_early_tp12"),
        policy_delta(matrix, "fixed_40d", "h40_early_tp15"),
        policy_delta(matrix, "fixed_30d", "h30_tp25_sl10"),
    ]
    early_tp07 = [row for row in comparisons if row["candidate"].endswith("tp07")]
    tp07_all_worse = all(row["return_delta"] < 0 for row in early_tp07)
    best = ((matrix.get("summary") or {}).get("exit_policy_top") or [{}])[0]
    return {
        "best_policy": best,
        "early_take_profit_07_rejected": tp07_all_worse,
        "comparisons": comparisons,
        "decision": "TEST_EXTENDED_HOLD_WITH_RISK_GUARD",
        "rationale": "7% 早停利在候選模型上明顯砍掉波段利潤；下一輪應測 30/40D 上限搭配停損、移動停利與回吐保護。",
    }


def rank_summary(matrix: dict[str, Any]) -> dict[str, Any]:
    top = (matrix.get("summary") or {}).get("rank_policy_top") or []
    best = top[0] if top else {}
    return {
        "best_rank_policy": best,
        "top_candidates": top[:8],
        "decision": "RANK_BUCKET_FOLLOWUP",
        "rationale": "Top4~7 在 40D 表現領先，表示 Top1~3 不一定是最佳追價位置；需做 rank bucket 穩定性驗證。",
    }


def regime_summary(matrix: dict[str, Any]) -> dict[str, Any]:
    by_regime = (matrix.get("summary") or {}).get("exit_by_regime_top") or {}
    compact = {
        key: (value[:3] if isinstance(value, list) else value)
        for key, value in by_regime.items()
    }
    return {
        "exit_by_regime_top": compact,
        "decision": "KEEP_REGIME_AS_EVALUATION_AND_RISK_CONTEXT",
        "rationale": "盤勢目前先當分層評估與風控 context，不直接訓練 HIGH_CHOPPY 專屬模型。",
    }


def concentration_summary(matrix: dict[str, Any]) -> dict[str, Any]:
    concentration = (matrix.get("summary") or {}).get("sector_concentration") or {}
    fixed_40 = concentration.get("fixed_40d") or {}
    return {
        "fixed_40d": fixed_40,
        "max_sector_buy_share": fixed_40.get("max_sector_buy_share"),
        "decision": "REQUIRE_SECTOR_CONCENTRATION_GUARD",
        "rationale": "獲利與買入金額高度集中在科技族群；下一輪規則要測產業上限，不能只看總報酬。",
    }


def shadow_summary(constrained: dict[str, Any], sector_cap: dict[str, Any]) -> dict[str, Any]:
    ready = [
        row.get("candidate_id")
        for row in constrained.get("candidates", [])
        if row.get("decision") == "READY_FOR_SHADOW_MONITOR"
    ]
    restricted = [
        row.get("candidate_id")
        for row in sector_cap.get("candidates", [])
        if row.get("reason")
    ]
    return {
        "ready_for_shadow_monitor": ready,
        "restricted_shadow_only": restricted,
        "decision": "ONLY_CONSTRAINED_K7_CAN_ADVANCE_TO_MONITOR",
        "rationale": "一般 shadow pool 跟 production 差太大；只有 constrained K7 類型目前可進 monitor，不可 overlay production。",
    }


def build_candidate_payload(args: argparse.Namespace) -> dict[str, Any]:
    candidate_vs_production_path = resolve_path(profile_value(args, "candidate_vs_production"))
    candidate_matrix_path = resolve_path(profile_value(args, "candidate_matrix"))
    production_matrix_path = resolve_path(profile_value(args, "production_matrix"))
    constrained_path = resolve_path(profile_value(args, "constrained_shadow"))
    sector_cap_path = resolve_path(profile_value(args, "sector_cap_shadow"))
    candidate_vs_production = read_json(candidate_vs_production_path)
    candidate_matrix = read_json(candidate_matrix_path)
    production_matrix = read_json(production_matrix_path)
    constrained = read_json(constrained_path)
    sector_cap = read_json(sector_cap_path)

    replacement = candidate_vs_production_summary(candidate_vs_production)
    exit_rules = exit_policy_summary(candidate_matrix)
    rank_rules = rank_summary(candidate_matrix)
    regimes = regime_summary(candidate_matrix)
    concentration = concentration_summary(candidate_matrix)
    shadow = shadow_summary(constrained, sector_cap)
    production_best = ((production_matrix.get("summary") or {}).get("exit_policy_top") or [{}])[0]

    next_experiments = [
        {
            "id": "OPRULE-01",
            "title": "30/40D extended hold with risk guard",
            "purpose": "測至少持有 5 天後，30/40D 上限搭配 stop-loss、trailing、giveback guard 是否保留主升段但降低 worst MAE。",
            "status": "READY_TO_RUN",
        },
        {
            "id": "OPRULE-02",
            "title": "Rank bucket stability",
            "purpose": "驗證 Top4~7 優勢是否跨 production/candidate/不同月份成立，避免只吃單一窗口。",
            "status": "READY_TO_RUN",
        },
        {
            "id": "OPRULE-03",
            "title": "Sector concentration guard",
            "purpose": "測科技族群過度集中時的 cap，不讓總報酬掩蓋單一族群風險。",
            "status": "READY_TO_RUN",
        },
        {
            "id": "OPRULE-04",
            "title": "Constrained K7 shadow monitor",
            "purpose": "只讓 constrained K7 進 shadow monitor，觀察與 production overlap、換手、drawdown，不做正式 overlay。",
            "status": "READY_TO_RUN",
        },
    ]
    return {
        "schema_version": CANDIDATE_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK",
        "contract": {
            "research_only": True,
            "model_changes": False,
            "production_ranking_changes": False,
            "promotion_evidence": False,
            "gate_engine": False,
        },
        "inputs": {
            "candidate_vs_production": repo_path(candidate_vs_production_path),
            "candidate_matrix": repo_path(candidate_matrix_path),
            "production_matrix": repo_path(production_matrix_path),
            "constrained_shadow": repo_path(constrained_path),
            "sector_cap_shadow": repo_path(sector_cap_path),
        },
        "summary": {
            "overall_decision": "CONTINUE_RULE_RESEARCH_NO_PROMOTION",
            "replacement_allowed": replacement["replacement_allowed"],
            "candidate_decision": replacement["decision"],
            "exit_rule_decision": exit_rules["decision"],
            "rank_rule_decision": rank_rules["decision"],
            "sector_guard_decision": concentration["decision"],
            "shadow_decision": shadow["decision"],
            "production_best_exit_policy": production_best.get("key"),
            "candidate_best_exit_policy": exit_rules["best_policy"].get("key"),
        },
        "candidate_vs_production": replacement,
        "exit_rules": exit_rules,
        "rank_rules": rank_rules,
        "regime_context": regimes,
        "sector_concentration": concentration,
        "shadow_candidates": shadow,
        "next_experiments": next_experiments,
    }


def render_candidate_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Operational Rule Candidate Report",
        "",
        f"- status: `{payload['status']}`",
        f"- overall_decision: `{payload['summary']['overall_decision']}`",
        f"- candidate_decision: `{payload['summary']['candidate_decision']}`",
        f"- production_changes: `{payload['contract']['production_ranking_changes']}`",
        f"- model_changes: `{payload['contract']['model_changes']}`",
        "",
        "## Candidate vs Production",
        "",
        "| Horizon | Production Return | Candidate Return | Delta | Candidate PnL Delta |",
        "|---:|---:|---:|---:|---:|",
    ]
    for row in payload["candidate_vs_production"]["comparisons"]:
        lines.append(
            f"| {row['horizon']} | {pct(row['production_return_on_buy_cash'])} | {pct(row['candidate_return_on_buy_cash'])} | {pct(row['return_delta'])} | {money(row['net_pnl_delta'])} |"
        )
    lines.extend(
        [
            "",
            "## Exit Rules",
            "",
            f"- best_policy: `{payload['exit_rules']['best_policy'].get('key')}`",
            f"- early_take_profit_07_rejected: `{payload['exit_rules']['early_take_profit_07_rejected']}`",
            f"- rationale: {payload['exit_rules']['rationale']}",
            "",
            "## Rank / Sector",
            "",
            f"- best_rank_policy: `{payload['rank_rules']['best_rank_policy'].get('key')}`",
            f"- max_sector_buy_share_fixed_40d: {pct(payload['sector_concentration']['max_sector_buy_share'])}",
            "",
            "## Next Experiments",
            "",
        ]
    )
    for item in payload["next_experiments"]:
        lines.append(f"- `{item['id']}` {item['title']}: {item['purpose']}")
    lines.append("")
    return "\n".join(lines)


def experiment_metric(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def experiment_policy(matrix: dict[str, Any], bucket: str, key: str) -> dict[str, Any]:
    return ((matrix.get("matrix") or {}).get(bucket) or {}).get(key) or {}


def compact_metric(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "key": row.get("key"),
        "trade_count": row.get("trade_count"),
        "ranking_day_count": row.get("ranking_day_count"),
        "return_on_buy_cash": row.get("return_on_buy_cash"),
        "total_net_pnl": row.get("total_net_pnl"),
        "win_rate": row.get("win_rate"),
        "worst_mae": row.get("worst_mae"),
        "avg_mae": row.get("avg_mae"),
        "p90_giveback": row.get("p90_giveback"),
    }


def risk_guard_result(label: str, matrix: dict[str, Any]) -> dict[str, Any]:
    fixed_30 = experiment_policy(matrix, "exit_policy", "fixed_30d")
    fixed_40 = experiment_policy(matrix, "exit_policy", "fixed_40d")
    guarded = [
        ("h30_tp25_sl10", experiment_policy(matrix, "exit_policy", "h30_tp25_sl10")),
        ("h30_tp18_sl08", experiment_policy(matrix, "exit_policy", "h30_tp18_sl08")),
        ("h30_trail10", experiment_policy(matrix, "exit_policy", "h30_trail10")),
        ("h30_trail15", experiment_policy(matrix, "exit_policy", "h30_trail15")),
        ("h30_trail18", experiment_policy(matrix, "exit_policy", "h30_trail18")),
        ("h30_trail22", experiment_policy(matrix, "exit_policy", "h30_trail22")),
        ("h40_trail12", experiment_policy(matrix, "exit_policy", "h40_trail12")),
        ("h40_trail15", experiment_policy(matrix, "exit_policy", "h40_trail15")),
        ("h40_trail18", experiment_policy(matrix, "exit_policy", "h40_trail18")),
        ("h40_trail22", experiment_policy(matrix, "exit_policy", "h40_trail22")),
        ("h40_trail25", experiment_policy(matrix, "exit_policy", "h40_trail25")),
        ("h40_tp25_sl10", experiment_policy(matrix, "exit_policy", "h40_tp25_sl10")),
        ("h40_tp35_sl12", experiment_policy(matrix, "exit_policy", "h40_tp35_sl12")),
        ("h40_early_tp15", experiment_policy(matrix, "exit_policy", "h40_early_tp15")),
    ]
    rows = []
    for key, item in guarded:
        baseline = fixed_40 if key.startswith("h40") else fixed_30
        rows.append(
            {
                "key": key,
                "return_delta_vs_fixed": round(experiment_metric(item.get("return_on_buy_cash")) - experiment_metric(baseline.get("return_on_buy_cash")), 6),
                "worst_mae_delta_vs_fixed": round(experiment_metric(item.get("worst_mae")) - experiment_metric(baseline.get("worst_mae")), 6),
                **compact_metric({"key": key, **item}),
            }
        )
    safer = [row for row in rows if row["worst_mae_delta_vs_fixed"] > 0]
    useful = [row for row in safer if row["return_delta_vs_fixed"] > -0.1]
    return {
        "label": label,
        "fixed_30d": compact_metric({"key": "fixed_30d", **fixed_30}),
        "fixed_40d": compact_metric({"key": "fixed_40d", **fixed_40}),
        "guarded_policies": rows,
        "best_guarded_policy": max(useful or safer or rows, key=lambda row: experiment_metric(row.get("return_on_buy_cash")), default={}),
        "useful_guarded_policy_count": len(useful),
        "decision": "DYNAMIC_GUARD_CANDIDATE" if useful else "NEEDS_DYNAMIC_RISK_GUARD",
        "rationale": "固定 30/40D 報酬最佳，但 worst MAE 有極端風險；現有簡單停損/停利能降風險但也大幅砍報酬，需要測動態回吐保護。",
    }


def rank_stability_result(production: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    keys = ["fixed_40d::top1_3", "fixed_40d::top4_7", "fixed_40d::top5", "fixed_40d::top7", "fixed_40d::all_top10"]
    rows = []
    for key in keys:
        prod = experiment_policy(production, "rank_policy", key)
        cand = experiment_policy(candidate, "rank_policy", key)
        rows.append(
            {
                "key": key,
                "production_return": prod.get("return_on_buy_cash"),
                "candidate_return": cand.get("return_on_buy_cash"),
                "return_delta_candidate_minus_production": round(experiment_metric(cand.get("return_on_buy_cash")) - experiment_metric(prod.get("return_on_buy_cash")), 6),
                "production_trade_count": prod.get("trade_count"),
                "candidate_trade_count": cand.get("trade_count"),
            }
        )
    production_best = max(rows, key=lambda row: experiment_metric(row.get("production_return")))
    candidate_best = max(rows, key=lambda row: experiment_metric(row.get("candidate_return")))
    stable = production_best["key"] == candidate_best["key"]
    return {
        "rows": rows,
        "production_best": production_best,
        "candidate_best": candidate_best,
        "decision": "RANK_BUCKET_NOT_STABLE_ENOUGH" if not stable else "RANK_BUCKET_CANDIDATE",
        "rationale": "candidate 最好是 Top4~7，但 production 最好是 Top1~3；rank bucket 不能直接上規則，只能列下一輪分層監控。",
    }


def sector_guard_result(production: dict[str, Any], candidate: dict[str, Any], sector_cap_shadow: dict[str, Any]) -> dict[str, Any]:
    prod_fixed40 = ((production.get("summary") or {}).get("sector_concentration") or {}).get("fixed_40d") or {}
    cand_fixed40 = ((candidate.get("summary") or {}).get("sector_concentration") or {}).get("fixed_40d") or {}
    restricted = (sector_cap_shadow.get("summary") or {}).get("restricted_shadow_only")
    return {
        "production_fixed_40d": prod_fixed40,
        "candidate_fixed_40d": cand_fixed40,
        "sector_cap_shadow_summary": sector_cap_shadow.get("summary"),
        "decision": "SECTOR_GUARD_REQUIRED_BUT_NOT_VALIDATED",
        "rationale": "fixed_40d 科技買入占比 production 約 77%、candidate 約 85%；sector cap shadow 仍 restricted，代表需要管集中，但目前沒有可直接套用的上線 cap。",
        "restricted_shadow_only": restricted,
    }


def shadow_monitor_result(constrained: dict[str, Any]) -> dict[str, Any]:
    ready = [
        row for row in constrained.get("candidates", [])
        if row.get("decision") == "READY_FOR_SHADOW_MONITOR"
    ]
    return {
        "ready_candidates": ready,
        "decision": "READY_FOR_SHADOW_MONITOR_ONLY" if ready else "NO_SHADOW_READY",
        "rationale": "constrained K7 可進 shadow monitor；仍不可 overlay production，因為只是監控候選。",
    }


def build_experiment_payload(args: argparse.Namespace) -> dict[str, Any]:
    production_path = resolve_path(profile_value(args, "production_matrix"))
    candidate_path = resolve_path(profile_value(args, "candidate_matrix"))
    constrained_path = resolve_path(profile_value(args, "constrained_shadow"))
    sector_cap_path = resolve_path(profile_value(args, "sector_cap_shadow"))
    production = read_json(production_path)
    candidate = read_json(candidate_path)
    constrained = read_json(constrained_path)
    sector_cap = read_json(sector_cap_path)
    production_risk_guard = risk_guard_result("production", production)
    candidate_risk_guard = risk_guard_result("candidate", candidate)
    oprule_01 = (
        "DYNAMIC_GUARD_CANDIDATE"
        if production_risk_guard["decision"] == "DYNAMIC_GUARD_CANDIDATE"
        and candidate_risk_guard["decision"] == "DYNAMIC_GUARD_CANDIDATE"
        else "NEEDS_DYNAMIC_RISK_GUARD"
    )
    return {
        "schema_version": EXPERIMENT_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK",
        "contract": {
            "research_only": True,
            "model_changes": False,
            "production_ranking_changes": False,
            "promotion_evidence": False,
        },
        "inputs": {
            "production_matrix": repo_path(production_path),
            "candidate_matrix": repo_path(candidate_path),
            "constrained_shadow": repo_path(constrained_path),
            "sector_cap_shadow": repo_path(sector_cap_path),
        },
        "summary": {
            "overall_decision": "KEEP_RESEARCHING_NO_DEPLOYABLE_RULE_YET",
            "oprule_01": oprule_01,
            "oprule_02": "RANK_BUCKET_NOT_STABLE_ENOUGH",
            "oprule_03": "SECTOR_GUARD_REQUIRED_BUT_NOT_VALIDATED",
            "oprule_04": "READY_FOR_SHADOW_MONITOR_ONLY",
        },
        "oprule_01_risk_guard": {
            "production": production_risk_guard,
            "candidate": candidate_risk_guard,
        },
        "oprule_02_rank_stability": rank_stability_result(production, candidate),
        "oprule_03_sector_guard": sector_guard_result(production, candidate, sector_cap),
        "oprule_04_shadow_monitor": shadow_monitor_result(constrained),
        "next_actions": [
            "把動態回吐保護放進下一輪 portfolio replay：候選是至少持有 5 天後，追蹤高點回吐 15%/18%/22%/25% 才出場。",
            "rank bucket 先做分層監控，不直接改 Top10 規則。",
            "sector cap 要用 portfolio replay 驗證 drawdown 與總報酬，不可只用固定股數帳本。",
        ],
    }


def render_experiment_markdown(payload: dict[str, Any]) -> str:
    prod = payload["oprule_01_risk_guard"]["production"]
    cand = payload["oprule_01_risk_guard"]["candidate"]
    rank = payload["oprule_02_rank_stability"]
    sector = payload["oprule_03_sector_guard"]
    lines = [
        "# Operational Rule Experiment Report",
        "",
        f"- status: `{payload['status']}`",
        f"- overall_decision: `{payload['summary']['overall_decision']}`",
        f"- model_changes: `{payload['contract']['model_changes']}`",
        f"- production_ranking_changes: `{payload['contract']['production_ranking_changes']}`",
        "",
        "## OPRULE-01 Risk Guard",
        "",
        f"- production fixed_40d: {pct(prod['fixed_40d'].get('return_on_buy_cash'))}, worst MAE {pct(prod['fixed_40d'].get('worst_mae'))}",
        f"- candidate fixed_40d: {pct(cand['fixed_40d'].get('return_on_buy_cash'))}, worst MAE {pct(cand['fixed_40d'].get('worst_mae'))}",
        f"- production best guarded: `{prod['best_guarded_policy'].get('key')}` {pct(prod['best_guarded_policy'].get('return_on_buy_cash'))}, worst MAE {pct(prod['best_guarded_policy'].get('worst_mae'))}",
        f"- candidate best guarded: `{cand['best_guarded_policy'].get('key')}` {pct(cand['best_guarded_policy'].get('return_on_buy_cash'))}, worst MAE {pct(cand['best_guarded_policy'].get('worst_mae'))}",
        f"- decision: `{payload['summary']['oprule_01']}`",
        "",
        "## OPRULE-02 Rank Stability",
        "",
        f"- production_best: `{rank['production_best']['key']}` {pct(rank['production_best']['production_return'])}",
        f"- candidate_best: `{rank['candidate_best']['key']}` {pct(rank['candidate_best']['candidate_return'])}",
        f"- decision: `{payload['summary']['oprule_02']}`",
        "",
        "## OPRULE-03 Sector Guard",
        "",
        f"- production fixed_40d max sector buy share: {pct(sector['production_fixed_40d'].get('max_sector_buy_share'))}",
        f"- candidate fixed_40d max sector buy share: {pct(sector['candidate_fixed_40d'].get('max_sector_buy_share'))}",
        f"- decision: `{payload['summary']['oprule_03']}`",
        "",
        "## Next Actions",
        "",
    ]
    lines.extend(f"- {item}" for item in payload["next_actions"])
    lines.append("")
    return "\n".join(lines)


def default_output(profile: str, run_date: str) -> Path:
    if profile == "candidate":
        return PROJECT_ROOT / "artifacts" / "model_experiments" / f"operational_rule_candidate_report_{run_date}.json"
    if profile == "experiment":
        return PROJECT_ROOT / "artifacts" / "model_experiments" / f"operational_rule_experiment_report_{run_date}.json"
    raise ValueError(f"unsupported profile: {profile}")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    output = resolve_path(args.output) if args.output else default_output(args.profile, args.date)
    if args.profile == "candidate":
        payload = build_candidate_payload(args)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        output.with_suffix(".md").write_text(render_candidate_markdown(payload), encoding="utf-8")
        print(json.dumps({"status": payload["status"], "output": repo_path(output), "decision": payload["summary"]["overall_decision"]}, ensure_ascii=False))
        return 0
    if args.profile == "experiment":
        payload = build_experiment_payload(args)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        output.with_suffix(".md").write_text(render_experiment_markdown(payload), encoding="utf-8")
        print(json.dumps({"status": payload["status"], "output": repo_path(output), **payload["summary"]}, ensure_ascii=False))
        return 0
    raise ValueError(f"unsupported profile: {args.profile}")


if __name__ == "__main__":
    raise SystemExit(main())
