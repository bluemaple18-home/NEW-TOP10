#!/usr/bin/env python3
"""彙整固定本金零股出場策略研究報告。"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "odd-lot-exit-strategy-report.v1"
VARIANTS = (
    "production_baseline",
    "production_ptp25_third",
    "candidate_baseline",
    "candidate_ptp25_third",
    "candidate_ptp25_half",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build odd-lot exit strategy report")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--capital-levels", default="100000,300000,500000")
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


def artifact_path(variant: str, capital: int, run_date: str) -> Path:
    capital_label = f"{capital // 1000}k"
    if variant == "production_baseline":
        file_name = f"odd_lot_portfolio_production_top7_sl12_min5_{capital_label}_gross75_pos12_{run_date}.json"
    elif variant == "production_ptp25_third":
        file_name = f"odd_lot_portfolio_production_top7_sl12_min5_{capital_label}_exit_ptp25_third_runner_{run_date}.json"
    elif variant == "candidate_baseline":
        file_name = f"odd_lot_portfolio_candidate_top7_sl12_min5_{capital_label}_gross75_pos12_{run_date}.json"
    elif variant == "candidate_ptp25_third":
        file_name = f"odd_lot_portfolio_candidate_top7_sl12_min5_{capital_label}_exit_ptp25_third_runner_{run_date}.json"
    elif variant == "candidate_ptp25_half":
        file_name = f"odd_lot_portfolio_candidate_top7_sl12_min5_{capital_label}_exit_ptp25_half_runner_{run_date}.json"
    else:
        raise ValueError(f"unknown variant: {variant}")
    return PROJECT_ROOT / "artifacts" / "model_experiments" / file_name


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def risk_ratio(total_return: float, max_drawdown: float) -> float | None:
    if max_drawdown >= 0:
        return None
    return round(total_return / abs(max_drawdown), 6)


def row_for(variant: str, capital: int, path: Path) -> dict[str, Any]:
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


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, dict[str, Any]] = {}
    for variant in VARIANTS:
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


def add_comparisons(rows: list[dict[str, Any]]) -> None:
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


def decision(rows: list[dict[str, Any]], summary: dict[str, dict[str, Any]]) -> dict[str, Any]:
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


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    capital_levels = [int(float(value.strip())) for value in args.capital_levels.split(",") if value.strip()]
    rows: list[dict[str, Any]] = []
    missing: list[str | None] = []
    for capital in capital_levels:
        for variant in VARIANTS:
            path = artifact_path(variant, capital, args.date)
            if not path.exists():
                missing.append(repo_path(path))
                continue
            rows.append(row_for(variant, capital, path))
    add_comparisons(rows)
    summary = summarize(rows)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
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
            "capital_levels": capital_levels,
            "candidate_rule": "top7_sl12_min5_gross75_pos12",
            "exit_rule": "sell_one_third_at_25pct_profit_then_runner_to_stop_or_40d_horizon",
        },
        "summary": summary,
        "decision": decision(rows, summary),
        "rows": rows,
        "missing": missing,
    }


def write_markdown(payload: dict[str, Any], output: Path) -> None:
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
    output.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    output = resolve_path(args.output) or PROJECT_ROOT / "artifacts" / "model_experiments" / f"odd_lot_exit_strategy_report_{args.date}.json"
    if output is None:
        raise RuntimeError("output resolution failed")
    payload = build_payload(args)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(payload, output)
    print(json.dumps({"status": payload["status"], "decision": payload["decision"]["status"], "output": repo_path(output)}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
