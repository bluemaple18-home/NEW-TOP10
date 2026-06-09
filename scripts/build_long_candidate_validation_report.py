#!/usr/bin/env python3
"""彙整長區間候選策略驗證報告。"""

from __future__ import annotations

import argparse
import re
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "long-candidate-validation-report.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build long candidate validation report")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--production-rankings-dir", required=True)
    parser.add_argument("--candidate-rankings-dir", required=True)
    parser.add_argument("--gap-report", required=True)
    parser.add_argument("--production-backtest", required=True)
    parser.add_argument("--candidate-backtest", required=True)
    parser.add_argument("--regime-attribution", required=True)
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


def ranking_dates(path: Path) -> set[str]:
    return {item.stem.removeprefix("ranking_") for item in path.glob("ranking_*.csv")}


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def load_required(path_value: str) -> tuple[Path, dict[str, Any]]:
    path = resolve_path(path_value)
    if path is None or not path.exists():
        raise FileNotFoundError(f"找不到必要 artifact：{path_value}")
    return path, read_json(path)


def portfolio_path(side: str, capital_label: str, suffix: str) -> Path:
    return (
        PROJECT_ROOT
        / "artifacts"
        / "model_experiments"
        / f"odd_lot_portfolio_{side}_top7_sl12_min5_{capital_label}_2023-11-21_2026-05-15_{suffix}_2026-06-10.json"
    )


def portfolio_summary(side: str, capital_label: str, suffix: str) -> dict[str, Any]:
    path = portfolio_path(side, capital_label, suffix)
    payload = read_json(path) if path.exists() else {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    return {
        "path": repo_path(path),
        "exists": path.exists(),
        "total_return": safe_float(summary.get("total_return")),
        "max_drawdown": safe_float(summary.get("max_drawdown")),
        "trade_count": int(summary.get("trade_count") or 0),
        "win_rate": safe_float(summary.get("win_rate")),
        "avg_cash_weight": safe_float(summary.get("avg_cash_weight")),
        "avg_gross_exposure": safe_float(summary.get("avg_gross_exposure")),
        "skipped_count": int(summary.get("skipped_count") or 0),
    }


def capital_matrix() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    suffix = "exit_ptp25_third_runner"
    for capital in ("100k", "300k", "500k"):
        production = portfolio_summary("production", capital, suffix)
        candidate = portfolio_summary("candidate", capital, suffix)
        rows.append(
            {
                "capital": capital,
                "production": production,
                "candidate": candidate,
                "return_delta": round(candidate["total_return"] - production["total_return"], 6),
                "drawdown_delta": round(candidate["max_drawdown"] - production["max_drawdown"], 6),
                "candidate_return_better": candidate["total_return"] > production["total_return"],
                "candidate_drawdown_better": candidate["max_drawdown"] > production["max_drawdown"],
            }
        )
    return rows


def exit_rule_comparison() -> dict[str, Any]:
    production_base = portfolio_summary("production", "300k", "gross75_pos12")
    candidate_base = portfolio_summary("candidate", "300k", "gross75_pos12")
    production_exit = portfolio_summary("production", "300k", "exit_ptp25_third_runner")
    candidate_exit = portfolio_summary("candidate", "300k", "exit_ptp25_third_runner")
    return {
        "production_baseline": production_base,
        "candidate_baseline": candidate_base,
        "production_exit": production_exit,
        "candidate_exit": candidate_exit,
        "candidate_exit_return_delta_vs_baseline": round(candidate_exit["total_return"] - candidate_base["total_return"], 6),
        "candidate_exit_drawdown_delta_vs_baseline": round(candidate_exit["max_drawdown"] - candidate_base["max_drawdown"], 6),
        "production_exit_return_delta_vs_baseline": round(production_exit["total_return"] - production_base["total_return"], 6),
        "production_exit_drawdown_delta_vs_baseline": round(production_exit["max_drawdown"] - production_base["max_drawdown"], 6),
    }


def exit_matrix() -> dict[str, Any]:
    pattern = (
        PROJECT_ROOT
        / "artifacts"
        / "model_experiments"
        / "odd_lot_portfolio_candidate_top7_sl12_min5_300k_2023-11-21_2026-05-15_exit_matrix_*_2026-06-10.json"
    )
    rows: list[dict[str, Any]] = []
    for path in sorted(pattern.parent.glob(pattern.name)):
        match = re.match(
            r"odd_lot_portfolio_candidate_top7_sl12_min5_300k_2023-11-21_2026-05-15_exit_matrix_(.+)_2026-06-10\.json",
            path.name,
        )
        if not match:
            continue
        summary = (read_json(path).get("summary") or {})
        total_return = safe_float(summary.get("total_return"))
        max_drawdown = safe_float(summary.get("max_drawdown"))
        rows.append(
            {
                "variant": match.group(1),
                "path": repo_path(path),
                "total_return": total_return,
                "max_drawdown": max_drawdown,
                "return_drawdown_ratio": round(total_return / abs(max_drawdown), 6) if max_drawdown < 0 else None,
                "trade_count": int(summary.get("trade_count") or 0),
                "win_rate": safe_float(summary.get("win_rate")),
                "skipped_count": int(summary.get("skipped_count") or 0),
            }
        )
    best = max(rows, key=lambda row: safe_float(row.get("return_drawdown_ratio")), default=None)
    return {
        "variant_count": len(rows),
        "best_by_return_drawdown_ratio": best,
        "rows": sorted(rows, key=lambda row: safe_float(row.get("return_drawdown_ratio")), reverse=True),
    }


def backtest_horizon_comparison(production: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    prod = ((production.get("summary") or {}).get("by_horizon") or {})
    cand = ((candidate.get("summary") or {}).get("by_horizon") or {})
    result: dict[str, Any] = {}
    for horizon in sorted(set(prod) | set(cand), key=lambda value: int(value)):
        prod_row = prod.get(horizon) or {}
        cand_row = cand.get(horizon) or {}
        result[horizon] = {
            "production_avg_net_return": safe_float(prod_row.get("avg_net_return")),
            "candidate_avg_net_return": safe_float(cand_row.get("avg_net_return")),
            "avg_net_return_delta": round(safe_float(cand_row.get("avg_net_return")) - safe_float(prod_row.get("avg_net_return")), 6),
            "production_hit_rate": safe_float(prod_row.get("hit_rate")),
            "candidate_hit_rate": safe_float(cand_row.get("hit_rate")),
            "hit_rate_delta": round(safe_float(cand_row.get("hit_rate")) - safe_float(prod_row.get("hit_rate")), 6),
        }
    return result


def decision(
    capital_rows: list[dict[str, Any]],
    exit_comparison: dict[str, Any],
    matrix: dict[str, Any],
    regime: dict[str, Any],
) -> dict[str, Any]:
    all_capital_return_better = all(row["candidate_return_better"] for row in capital_rows)
    all_capital_drawdown_better = all(row["candidate_drawdown_better"] for row in capital_rows)
    exit_hurts_candidate_return = safe_float(exit_comparison.get("candidate_exit_return_delta_vs_baseline")) < 0
    exit_hurts_candidate_drawdown = safe_float(exit_comparison.get("candidate_exit_drawdown_delta_vs_baseline")) < 0
    best_exit = matrix.get("best_by_return_drawdown_ratio") if isinstance(matrix.get("best_by_return_drawdown_ratio"), dict) else {}
    baseline = exit_comparison.get("candidate_baseline") if isinstance(exit_comparison.get("candidate_baseline"), dict) else {}
    best_exit_supported = (
        best_exit.get("variant") == "trail10"
        and safe_float(best_exit.get("total_return")) > safe_float(baseline.get("total_return"))
        and safe_float(best_exit.get("max_drawdown")) > safe_float(baseline.get("max_drawdown"))
    )
    comparison = regime.get("comparison") if isinstance(regime.get("comparison"), dict) else {}
    big_bull_delta = safe_float((comparison.get("BIG_BULL") or {}).get("avg_net_return_delta"))
    other_delta = safe_float((comparison.get("OTHER") or {}).get("avg_net_return_delta"))
    blockers: list[str] = []
    warnings: list[str] = []
    if not all_capital_return_better:
        blockers.append("candidate does not beat production return across all capital levels")
    if not all_capital_drawdown_better:
        blockers.append("candidate does not improve drawdown across all capital levels")
    if exit_hurts_candidate_return and exit_hurts_candidate_drawdown:
        warnings.append("+25% sell-one-third exit rule hurts candidate baseline return and drawdown in 300k replay")
    if not best_exit_supported:
        blockers.append("no exit rule improves candidate baseline return and drawdown")
    if big_bull_delta < 0:
        warnings.append("BIG_BULL per-trade average return is below production peer")
    if other_delta <= 0:
        warnings.append("OTHER regime attribution does not beat production peer")
    if blockers:
        status = "BLOCKED"
        next_stage = "fix_blockers"
    elif warnings:
        status = "READY_FOR_SHADOW_WITH_TRAIL10_EXIT_CANDIDATE"
        next_stage = "shadow_monitor_candidate_ranking_with_trail10_exit_candidate"
    else:
        status = "READY_FOR_PROMOTION_REVIEW_CANDIDATE"
        next_stage = "promotion_review_candidate_ranking"
    return {
        "status": status,
        "promotion_ready": False,
        "production_switch_ready": False,
        "candidate_ranking_supported": all_capital_return_better and all_capital_drawdown_better,
        "exit_rule_supported": best_exit_supported,
        "selected_exit_rule": best_exit.get("variant"),
        "blockers": blockers,
        "warnings": warnings,
        "next_stage": next_stage,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    production_dir = resolve_path(args.production_rankings_dir)
    candidate_dir = resolve_path(args.candidate_rankings_dir)
    if production_dir is None or candidate_dir is None:
        raise RuntimeError("ranking dir resolution failed")
    gap_path, gap_report = load_required(args.gap_report)
    production_backtest_path, production_backtest = load_required(args.production_backtest)
    candidate_backtest_path, candidate_backtest = load_required(args.candidate_backtest)
    regime_path, regime_report = load_required(args.regime_attribution)
    production_dates = ranking_dates(production_dir)
    candidate_dates = ranking_dates(candidate_dir)
    capital_rows = capital_matrix()
    exit_comparison = exit_rule_comparison()
    matrix = exit_matrix()
    horizon_comparison = backtest_horizon_comparison(production_backtest, candidate_backtest)
    decision_payload = decision(capital_rows, exit_comparison, matrix, regime_report)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK",
        "contract": {
            "research_only": True,
            "model_changes": False,
            "production_ranking_changes": False,
            "production_publish_changes": False,
            "promotion_ready": False,
        },
        "inputs": {
            "production_rankings_dir": repo_path(production_dir),
            "candidate_rankings_dir": repo_path(candidate_dir),
            "gap_report": repo_path(gap_path),
            "production_backtest": repo_path(production_backtest_path),
            "candidate_backtest": repo_path(candidate_backtest_path),
            "regime_attribution": repo_path(regime_path),
        },
        "coverage": {
            "production_ranking_days": len(production_dates),
            "candidate_ranking_days": len(candidate_dates),
            "comparable_days": len(production_dates & candidate_dates),
            "missing_candidate_dates": sorted(production_dates - candidate_dates),
            "gap_decision": (gap_report.get("decision") or {}).get("status"),
        },
        "ranking_day_backtest_by_horizon": horizon_comparison,
        "odd_lot_capital_matrix": capital_rows,
        "exit_rule_comparison_300k": exit_comparison,
        "exit_rule_matrix_300k": matrix,
        "regime_attribution": regime_report.get("comparison"),
        "decision": decision_payload,
    }


def write_markdown(payload: dict[str, Any], output: Path) -> None:
    decision_payload = payload["decision"]
    lines = [
        "# Long Candidate Validation",
        "",
        f"- status: `{payload['status']}`",
        f"- decision: `{decision_payload['status']}`",
        f"- comparable_days: `{payload['coverage']['comparable_days']}`",
        f"- promotion_ready: `{decision_payload['promotion_ready']}`",
        f"- production_switch_ready: `{decision_payload['production_switch_ready']}`",
        "",
        "## Odd-Lot Capital Matrix",
        "",
        "| Capital | Production Return | Candidate Return | Return Delta | Production MaxDD | Candidate MaxDD | DD Delta |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["odd_lot_capital_matrix"]:
        lines.append(
            "| {capital} | {pr:.6f} | {cr:.6f} | {rd:.6f} | {pd:.6f} | {cd:.6f} | {dd:.6f} |".format(
                capital=row["capital"],
                pr=row["production"]["total_return"],
                cr=row["candidate"]["total_return"],
                rd=row["return_delta"],
                pd=row["production"]["max_drawdown"],
                cd=row["candidate"]["max_drawdown"],
                dd=row["drawdown_delta"],
            )
        )
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {item}" for item in decision_payload["warnings"]] or ["- none"])
    lines.extend(["", "## Blockers", ""])
    lines.extend([f"- {item}" for item in decision_payload["blockers"]] or ["- none"])
    lines.append("")
    output.with_suffix(".md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    output = resolve_path(args.output) or PROJECT_ROOT / "artifacts" / "model_experiments" / f"long_candidate_validation_report_{args.date}.json"
    if output is None:
        raise RuntimeError("output resolution failed")
    payload = build_payload(args)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(payload, output)
    print(json.dumps({"status": payload["status"], "decision": payload["decision"]["status"], "output": repo_path(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
