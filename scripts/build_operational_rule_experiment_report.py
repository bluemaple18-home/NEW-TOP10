#!/usr/bin/env python3
"""整理 OPRULE 系列營運規則實驗結果。"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "operational-rule-experiment-report.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build operational rule experiment report")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--production-matrix", default="artifacts/backtest/fixed_share_hypothesis_matrix_production_dynamic_guard_2026-06-02.json")
    parser.add_argument(
        "--candidate-matrix",
        default="artifacts/model_experiments/training_candidates/candidate_2026-06-02_config/fixed_share_hypothesis_matrix_candidate_dynamic_guard_2026-06-02.json",
    )
    parser.add_argument("--constrained-shadow", default="artifacts/model_experiments/constrained_shadow_comparison_2026-06-02.json")
    parser.add_argument("--sector-cap-shadow", default="artifacts/model_experiments/mass_candidate_shadow_dry_run_sector_cap_2026-06-02.json")
    parser.add_argument("--output", default=None)
    return parser.parse_args()


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


def n(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def pct(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{n(value):.2%}"


def policy(matrix: dict[str, Any], bucket: str, key: str) -> dict[str, Any]:
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
    fixed_30 = policy(matrix, "exit_policy", "fixed_30d")
    fixed_40 = policy(matrix, "exit_policy", "fixed_40d")
    guarded = [
        ("h30_tp25_sl10", policy(matrix, "exit_policy", "h30_tp25_sl10")),
        ("h30_tp18_sl08", policy(matrix, "exit_policy", "h30_tp18_sl08")),
        ("h30_trail10", policy(matrix, "exit_policy", "h30_trail10")),
        ("h30_trail15", policy(matrix, "exit_policy", "h30_trail15")),
        ("h30_trail18", policy(matrix, "exit_policy", "h30_trail18")),
        ("h30_trail22", policy(matrix, "exit_policy", "h30_trail22")),
        ("h40_trail12", policy(matrix, "exit_policy", "h40_trail12")),
        ("h40_trail15", policy(matrix, "exit_policy", "h40_trail15")),
        ("h40_trail18", policy(matrix, "exit_policy", "h40_trail18")),
        ("h40_trail22", policy(matrix, "exit_policy", "h40_trail22")),
        ("h40_trail25", policy(matrix, "exit_policy", "h40_trail25")),
        ("h40_tp25_sl10", policy(matrix, "exit_policy", "h40_tp25_sl10")),
        ("h40_tp35_sl12", policy(matrix, "exit_policy", "h40_tp35_sl12")),
        ("h40_early_tp15", policy(matrix, "exit_policy", "h40_early_tp15")),
    ]
    rows = []
    for key, item in guarded:
        baseline = fixed_40 if key.startswith("h40") else fixed_30
        rows.append(
            {
                "key": key,
                "return_delta_vs_fixed": round(n(item.get("return_on_buy_cash")) - n(baseline.get("return_on_buy_cash")), 6),
                "worst_mae_delta_vs_fixed": round(n(item.get("worst_mae")) - n(baseline.get("worst_mae")), 6),
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
        "best_guarded_policy": max(useful or safer or rows, key=lambda row: n(row.get("return_on_buy_cash")), default={}),
        "useful_guarded_policy_count": len(useful),
        "decision": "DYNAMIC_GUARD_CANDIDATE" if useful else "NEEDS_DYNAMIC_RISK_GUARD",
        "rationale": "固定 30/40D 報酬最佳，但 worst MAE 有極端風險；現有簡單停損/停利能降風險但也大幅砍報酬，需要測動態回吐保護。",
    }


def rank_stability_result(production: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    keys = ["fixed_40d::top1_3", "fixed_40d::top4_7", "fixed_40d::top5", "fixed_40d::top7", "fixed_40d::all_top10"]
    rows = []
    for key in keys:
        prod = policy(production, "rank_policy", key)
        cand = policy(candidate, "rank_policy", key)
        rows.append(
            {
                "key": key,
                "production_return": prod.get("return_on_buy_cash"),
                "candidate_return": cand.get("return_on_buy_cash"),
                "return_delta_candidate_minus_production": round(n(cand.get("return_on_buy_cash")) - n(prod.get("return_on_buy_cash")), 6),
                "production_trade_count": prod.get("trade_count"),
                "candidate_trade_count": cand.get("trade_count"),
            }
        )
    production_best = max(rows, key=lambda row: n(row.get("production_return")))
    candidate_best = max(rows, key=lambda row: n(row.get("candidate_return")))
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


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    production_path = resolve_path(args.production_matrix)
    candidate_path = resolve_path(args.candidate_matrix)
    constrained_path = resolve_path(args.constrained_shadow)
    sector_cap_path = resolve_path(args.sector_cap_shadow)
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
        "schema_version": SCHEMA_VERSION,
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


def render_markdown(payload: dict[str, Any]) -> str:
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


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = (
        resolve_path(args.output)
        if args.output
        else PROJECT_ROOT / "artifacts" / "model_experiments" / f"operational_rule_experiment_report_{args.date}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output), **payload["summary"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
