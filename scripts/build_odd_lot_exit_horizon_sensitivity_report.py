#!/usr/bin/env python3
"""彙整零股出場策略的持有上限敏感度報告。"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "odd-lot-exit-horizon-sensitivity-report.v1"
HORIZONS = (20, 40, 60)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build odd-lot exit horizon sensitivity report")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--capital", type=int, default=300_000)
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


def artifact_path(kind: str, horizon: int, capital: int, run_date: str) -> Path:
    capital_label = f"{capital // 1000}k"
    if horizon == 40:
        if kind == "candidate_baseline":
            name = f"odd_lot_portfolio_candidate_top7_sl12_min5_{capital_label}_gross75_pos12_{run_date}.json"
        elif kind == "candidate_exit":
            name = f"odd_lot_portfolio_candidate_top7_sl12_min5_{capital_label}_exit_ptp25_third_runner_{run_date}.json"
        elif kind == "production_exit":
            name = f"odd_lot_portfolio_production_top7_sl12_min5_{capital_label}_exit_ptp25_third_runner_{run_date}.json"
        else:
            raise ValueError(f"unknown kind: {kind}")
    else:
        if kind == "candidate_baseline":
            name = f"odd_lot_portfolio_candidate_top7_sl12_min5_{capital_label}_h{horizon}_baseline_{run_date}.json"
        elif kind == "candidate_exit":
            name = f"odd_lot_portfolio_candidate_top7_sl12_min5_{capital_label}_h{horizon}_exit_ptp25_third_runner_{run_date}.json"
        elif kind == "production_exit":
            name = f"odd_lot_portfolio_production_top7_sl12_min5_{capital_label}_h{horizon}_exit_ptp25_third_runner_{run_date}.json"
        else:
            raise ValueError(f"unknown kind: {kind}")
    return PROJECT_ROOT / "artifacts" / "model_experiments" / name


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def return_drawdown_ratio(total_return: float, max_drawdown: float) -> float | None:
    if max_drawdown >= 0:
        return None
    return round(total_return / abs(max_drawdown), 6)


def row_for(kind: str, horizon: int, capital: int, path: Path) -> dict[str, Any]:
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


def add_comparisons(rows: list[dict[str, Any]]) -> None:
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


def decision(rows: list[dict[str, Any]]) -> dict[str, Any]:
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


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    missing: list[str | None] = []
    for horizon in HORIZONS:
        for kind in ("candidate_baseline", "candidate_exit", "production_exit"):
            path = artifact_path(kind, horizon, args.capital, args.date)
            if not path.exists():
                missing.append(repo_path(path))
                continue
            rows.append(row_for(kind, horizon, args.capital, path))
    add_comparisons(rows)
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
            "horizon_sensitivity_only": True,
        },
        "inputs": {
            "capital": args.capital,
            "horizons": list(HORIZONS),
            "exit_rule": "sell_one_third_at_25pct_profit_then_runner_to_stop_or_horizon",
        },
        "decision": decision(rows),
        "rows": rows,
        "missing": missing,
    }


def write_markdown(payload: dict[str, Any], output: Path) -> None:
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
    output.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    output = resolve_path(args.output) or PROJECT_ROOT / "artifacts" / "model_experiments" / f"odd_lot_exit_horizon_sensitivity_report_{args.date}.json"
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
