#!/usr/bin/env python3
"""整理近半年出場規則 portfolio-level replay 結論。"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "exit-rule-portfolio-level-report.v1"


VARIANTS = {
    "h40_fixed65": "artifacts/backtest/portfolio_replay_half_year_dense_h40_fixed65_2026-06-02.json",
    "h40_gross55": "artifacts/backtest/portfolio_replay_half_year_dense_h40_gross55_2026-06-02.json",
    "h40_tp15_fixed65": "artifacts/backtest/portfolio_replay_half_year_dense_h40_tp15_fixed65_2026-06-02.json",
    "h40_tp15_gross55": "artifacts/backtest/portfolio_replay_half_year_dense_h40_tp15_gross55_2026-06-02.json",
    "h30_tp25_sl10_fixed65": "artifacts/backtest/portfolio_replay_half_year_dense_h30_tp25_sl10_fixed65_2026-06-02.json",
    "h30_tp25_sl10_gross55": "artifacts/backtest/portfolio_replay_half_year_dense_h30_tp25_sl10_gross55_2026-06-02.json",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build exit rule portfolio-level report")
    parser.add_argument("--date", default=date.today().isoformat())
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
    return f"{n(value):.2%}"


def exit_counts(payload: dict[str, Any]) -> dict[str, int]:
    daily = payload.get("daily") or []
    return {
        "scheduled": sum(int(row.get("scheduled_exits") or 0) for row in daily),
        "stop_loss": sum(int(row.get("stop_loss_exits") or 0) for row in daily),
        "take_profit": sum(int(row.get("take_profit_exits") or 0) for row in daily),
        "trailing_stop": sum(int(row.get("trailing_stop_exits") or 0) for row in daily),
    }


def compact(label: str, path_text: str) -> dict[str, Any]:
    path = resolve_path(path_text)
    payload = read_json(path)
    summary = payload.get("summary") or {}
    return {
        "label": label,
        "path": repo_path(path),
        "exists": bool(payload),
        "total_return": summary.get("total_return"),
        "max_drawdown": summary.get("max_drawdown"),
        "trade_count": summary.get("trade_count"),
        "win_rate": summary.get("win_rate"),
        "avg_trade_return": summary.get("avg_trade_return"),
        "avg_gross_exposure": summary.get("avg_gross_exposure"),
        "exit_counts": exit_counts(payload),
        "inputs": payload.get("inputs") or {},
    }


def delta(row: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    return {
        "total_return_delta": round(n(row.get("total_return")) - n(baseline.get("total_return")), 6),
        "max_drawdown_delta": round(n(row.get("max_drawdown")) - n(baseline.get("max_drawdown")), 6),
        "win_rate_delta": round(n(row.get("win_rate")) - n(baseline.get("win_rate")), 6),
        "avg_gross_delta": round(n(row.get("avg_gross_exposure")) - n(baseline.get("avg_gross_exposure")), 6),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    rows = {label: compact(label, path) for label, path in VARIANTS.items()}
    baseline = rows["h40_fixed65"]
    comparisons = {label: delta(row, baseline) for label, row in rows.items() if label != "h40_fixed65"}
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK" if all(row["exists"] for row in rows.values()) else "MISSING_INPUT",
        "contract": {
            "research_only": True,
            "portfolio_level_replay": True,
            "does_not_train_model": True,
            "does_not_change_production_ranking": True,
            "does_not_change_risk_adjusted_score": True,
            "production_default_allowed": False,
        },
        "summary": {
            "decision": "PORTFOLIO_LEVEL_SUPPORTS_EXIT_RULE_SHADOW",
            "highest_return": "h40_fixed65",
            "primary_shadow_candidate": "h40_tp15_fixed65",
            "defensive_shadow_candidate": "h30_tp25_sl10_fixed65",
            "gross55_combination": "MONITOR_ONLY_LOWER_DRAWDOWN_LOWER_RETURN",
            "next_gate": "RUN_ROLLING_OR_REGIME_SLICED_EXIT_RULE_REPLAY",
        },
        "rows": rows,
        "comparisons_vs_h40_fixed65": comparisons,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    rows = payload["rows"]
    comps = payload["comparisons_vs_h40_fixed65"]
    lines = [
        "# Exit Rule Portfolio-Level Report",
        "",
        f"- status: `{payload['status']}`",
        f"- decision: `{payload['summary']['decision']}`",
        f"- primary_shadow_candidate: `{payload['summary']['primary_shadow_candidate']}`",
        f"- defensive_shadow_candidate: `{payload['summary']['defensive_shadow_candidate']}`",
        "",
        "| Variant | Return | DD | Win | Avg Gross | Take | Stop | Δ Return | Δ DD |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in VARIANTS:
        row = rows[label]
        comp = comps.get(label) or {}
        exits = row["exit_counts"]
        lines.append(
            "| {label} | {ret} | {dd} | {win} | {gross} | {take} | {stop} | {dret} | {ddd} |".format(
                label=label,
                ret=pct(row.get("total_return")),
                dd=pct(row.get("max_drawdown")),
                win=pct(row.get("win_rate")),
                gross=pct(row.get("avg_gross_exposure")),
                take=exits.get("take_profit", 0),
                stop=exits.get("stop_loss", 0),
                dret=pct(comp.get("total_return_delta")) if comp else "--",
                ddd=pct(comp.get("max_drawdown_delta")) if comp else "--",
            )
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = (
        resolve_path(args.output)
        if args.output
        else PROJECT_ROOT / "artifacts" / "model_experiments" / f"exit_rule_portfolio_level_report_{args.date}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output), **payload["summary"]}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
