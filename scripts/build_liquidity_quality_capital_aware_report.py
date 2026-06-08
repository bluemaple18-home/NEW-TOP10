#!/usr/bin/env python3
"""彙整流動性品質 shadow 的有限本金 replay。

這份報告用來區分兩件事：

- bucket replay 顯示 liquidity score 有 ranking 訊號。
- 有限本金 replay 才能判斷它適不適合小白當預設推播規則。
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "liquidity-quality-capital-aware-report.v1"

DEFAULT_RUNS = {
    "production_fixed65": "artifacts/backtest/capital_aware_liquidity_halfyear_production_fixed40_fixed65_2026-06-03.json",
    "log_gate_fixed65": "artifacts/backtest/capital_aware_liquidity_halfyear_log_gate_fixed40_fixed65_2026-06-03.json",
    "percentile_gate_fixed65": "artifacts/backtest/capital_aware_liquidity_halfyear_percentile_gate_fixed40_fixed65_2026-06-03.json",
    "production_fixed85": "artifacts/backtest/capital_aware_liquidity_halfyear_production_fixed40_fixed85_2026-06-03.json",
    "log_gate_fixed85": "artifacts/backtest/capital_aware_liquidity_halfyear_log_gate_fixed40_fixed85_2026-06-03.json",
    "percentile_gate_fixed85": "artifacts/backtest/capital_aware_liquidity_halfyear_percentile_gate_fixed40_fixed85_2026-06-03.json",
    "production_regime": "artifacts/backtest/capital_aware_liquidity_halfyear_production_fixed40_regime_2026-06-03.json",
    "log_gate_regime": "artifacts/backtest/capital_aware_liquidity_halfyear_log_gate_fixed40_regime_2026-06-03.json",
    "percentile_gate_regime": "artifacts/backtest/capital_aware_liquidity_halfyear_percentile_gate_fixed40_regime_2026-06-03.json",
    "production_regime_non_worsening": "artifacts/backtest/capital_aware_liquidity_halfyear_production_fixed40_regime_non_worsening_2026-06-03.json",
    "log_gate_regime_non_worsening": "artifacts/backtest/capital_aware_liquidity_halfyear_log_gate_fixed40_regime_non_worsening_2026-06-03.json",
    "log_gate_regime_improved_only": "artifacts/backtest/capital_aware_liquidity_halfyear_log_gate_fixed40_regime_improved_only_2026-06-03.json",
    "production_regime_h20": "artifacts/backtest/capital_aware_liquidity_halfyear_production_fixed20_regime_2026-06-03.json",
    "log_gate_regime_h20": "artifacts/backtest/capital_aware_liquidity_halfyear_log_gate_fixed20_regime_2026-06-03.json",
    "percentile_gate_regime_h20": "artifacts/backtest/capital_aware_liquidity_halfyear_percentile_gate_fixed20_regime_2026-06-03.json",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build liquidity quality capital-aware report")
    parser.add_argument("--output", default="artifacts/model_experiments/liquidity_quality_capital_aware_report_2026-06-03.json")
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
        raise FileNotFoundError(f"artifact 不存在：{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def run_summary(label: str, path_text: str) -> dict[str, Any]:
    path = resolve_path(path_text)
    payload = read_json(path)
    summary = payload.get("summary", {})
    inputs = payload.get("inputs", {})
    return {
        "label": label,
        "path": repo_path(path),
        "rankings_dir": inputs.get("rankings_dir"),
        "scenario": inputs.get("scenario"),
        "gross_policy": inputs.get("gross_policy"),
        "entry_filter": inputs.get("entry_filter"),
        "initial_cash": summary.get("initial_cash"),
        "final_equity": summary.get("final_equity"),
        "total_return": summary.get("total_return"),
        "max_drawdown": summary.get("max_drawdown"),
        "win_rate": summary.get("win_rate"),
        "trade_count": summary.get("trade_count"),
        "avg_gross_exposure": summary.get("avg_gross_exposure"),
        "avg_cash_ratio": summary.get("avg_cash_ratio"),
        "buy_lot_block_count": summary.get("buy_lot_block_count"),
        "cash_block_count": summary.get("cash_block_count"),
    }


def delta(candidate: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    cand_return = float(candidate.get("total_return") or 0)
    base_return = float(baseline.get("total_return") or 0)
    cand_dd = float(candidate.get("max_drawdown") or 0)
    base_dd = float(baseline.get("max_drawdown") or 0)
    return {
        "return_delta": round(cand_return - base_return, 6),
        "drawdown_delta": round(cand_dd - base_dd, 6),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    runs = {label: run_summary(label, path) for label, path in DEFAULT_RUNS.items()}
    comparisons = {
        "fixed65": {
            "log_gate": delta(runs["log_gate_fixed65"], runs["production_fixed65"]),
            "percentile_gate": delta(runs["percentile_gate_fixed65"], runs["production_fixed65"]),
        },
        "fixed85": {
            "log_gate": delta(runs["log_gate_fixed85"], runs["production_fixed85"]),
            "percentile_gate": delta(runs["percentile_gate_fixed85"], runs["production_fixed85"]),
        },
        "regime": {
            "log_gate": delta(runs["log_gate_regime"], runs["production_regime"]),
            "percentile_gate": delta(runs["percentile_gate_regime"], runs["production_regime"]),
        },
        "entry_filter": {
            "log_gate_non_worsening_vs_log_gate_all": delta(runs["log_gate_regime_non_worsening"], runs["log_gate_regime"]),
            "log_gate_improved_only_vs_log_gate_all": delta(runs["log_gate_regime_improved_only"], runs["log_gate_regime"]),
            "production_non_worsening_vs_production_all": delta(runs["production_regime_non_worsening"], runs["production_regime"]),
        },
        "horizon20": {
            "log_gate": delta(runs["log_gate_regime_h20"], runs["production_regime_h20"]),
            "percentile_gate": delta(runs["percentile_gate_regime_h20"], runs["production_regime_h20"]),
        },
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK",
        "contract": {
            "research_only": True,
            "changes_production_ranking": False,
            "changes_risk_adjusted_score": False,
            "changes_model": False,
            "finite_capital": True,
            "initial_cash": 500_000,
            "ranking_source": "liquidity candidate-universe shadow rankings",
        },
        "runs": runs,
        "comparisons": comparisons,
        "decision": {
            "status": "AGGRESSIVE_SHADOW_ONLY",
            "production_ready": False,
            "default_liquidity_score_change": "REJECT_AS_DEFAULT",
            "primary_reason": "log_gate / percentile_gate 在部分情境提高報酬，但有限本金回撤顯著放大；不適合小白預設推播。",
            "allowed_next_use": "aggressive shadow monitor or page-level liquidity/risk explanation",
            "blocked_use": "do not merge into production risk_adjusted_score yet",
            "safer_baseline": "production_regime",
        },
    }


def pct(value: Any) -> str:
    if value is None:
        return "--"
    return f"{float(value):.2%}"


def money(value: Any) -> str:
    if value is None:
        return "--"
    return f"{float(value):,.0f}"


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Liquidity Quality Capital-Aware Report",
        "",
        f"- status: `{payload['status']}`",
        f"- decision: `{payload['decision']['status']}`",
        f"- production_ready: `{payload['decision']['production_ready']}`",
        f"- default_liquidity_score_change: `{payload['decision']['default_liquidity_score_change']}`",
        "",
        "## Runs",
        "",
        "| label | return | max DD | win rate | final equity | avg cash | trades |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, row in payload["runs"].items():
        lines.append(
            f"| {label} | {pct(row.get('total_return'))} | {pct(row.get('max_drawdown'))} | {pct(row.get('win_rate'))} | {money(row.get('final_equity'))} | {pct(row.get('avg_cash_ratio'))} | {row.get('trade_count')} |"
        )
    lines.extend(["", "## Decision", "", json.dumps(payload["decision"], ensure_ascii=False, indent=2), ""])
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = resolve_path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output), "decision": payload["decision"]["status"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
