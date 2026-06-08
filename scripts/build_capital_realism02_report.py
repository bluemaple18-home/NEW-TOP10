#!/usr/bin/env python3
"""彙整 CAPITAL-REALISM-02 零股資金與動態出場矩陣。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "capital-realism02-report.v1"
RUN_DATE = "2026-06-05"
VARIANTS = ("baseline", "k9")
SCENARIOS = ("fixed40", "tp20_runner_stop8")
ENTRY_FILTERS = ("all", "non_worsening", "improved_only")
CASH_LEVELS = (300_000, 500_000, 1_000_000)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build CAPITAL-REALISM-02 report")
    parser.add_argument(
        "--output",
        default=f"artifacts/model_experiments/capital_realism02_report_{RUN_DATE}.json",
    )
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def artifact_path(variant: str, scenario: str, entry_filter: str, cash: int) -> Path:
    return (
        PROJECT_ROOT
        / "artifacts"
        / "backtest"
        / f"capital_realism02_{variant}_{scenario}_{entry_filter}_{cash}_{RUN_DATE}.json"
    )


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"artifact missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def summarize_run(variant: str, scenario: str, entry_filter: str, cash: int) -> dict[str, Any]:
    path = artifact_path(variant, scenario, entry_filter, cash)
    payload = read_json(path)
    contract = payload.get("contract", {})
    inputs = payload.get("inputs", {})
    summary = payload.get("summary", {})
    return {
        "id": f"{variant}_{scenario}_{entry_filter}_{cash}",
        "variant": variant,
        "scenario": scenario,
        "entry_filter": entry_filter,
        "initial_cash": cash,
        "path": repo_path(path),
        "research_only": contract.get("research_only"),
        "changes_model": contract.get("changes_model"),
        "changes_ranking_score": contract.get("changes_ranking_score"),
        "finite_capital": contract.get("finite_capital"),
        "buy_lot_size": contract.get("buy_lot_size"),
        "sell_lot_size": contract.get("sell_lot_size"),
        "gross_policy": inputs.get("gross_policy"),
        "horizon": inputs.get("horizon"),
        "total_return": summary.get("total_return"),
        "max_drawdown": summary.get("max_drawdown"),
        "final_equity": summary.get("final_equity"),
        "trade_count": summary.get("trade_count"),
        "win_rate": summary.get("win_rate"),
        "avg_cash_ratio": summary.get("avg_cash_ratio"),
        "exit_reason_counts": summary.get("exit_reason_counts", {}),
        "skip_reason_counts": summary.get("skip_reason_counts", {}),
    }


def value(row: dict[str, Any], key: str) -> float:
    raw = row.get(key)
    return 0.0 if raw is None else float(raw)


def build_payload(_: argparse.Namespace) -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    for variant in VARIANTS:
        for scenario in SCENARIOS:
            for entry_filter in ENTRY_FILTERS:
                for cash in CASH_LEVELS:
                    runs.append(summarize_run(variant, scenario, entry_filter, cash))

    winners_by_cash: dict[str, dict[str, Any]] = {}
    for cash in CASH_LEVELS:
        subset = [row for row in runs if int(row["initial_cash"]) == cash]
        best_return = max(subset, key=lambda row: value(row, "total_return"))
        best_drawdown = max(subset, key=lambda row: value(row, "max_drawdown"))
        winners_by_cash[str(cash)] = {
            "best_return": best_return["id"],
            "best_return_value": best_return["total_return"],
            "best_return_drawdown": best_return["max_drawdown"],
            "lowest_drawdown": best_drawdown["id"],
            "lowest_drawdown_value": best_drawdown["max_drawdown"],
            "lowest_drawdown_return": best_drawdown["total_return"],
        }

    fixed40_rows = [row for row in runs if row["scenario"] == "fixed40"]
    runner_rows = [row for row in runs if row["scenario"] == "tp20_runner_stop8"]
    fixed40_avg_return = sum(value(row, "total_return") for row in fixed40_rows) / len(fixed40_rows)
    runner_avg_return = sum(value(row, "total_return") for row in runner_rows) / len(runner_rows)
    fixed40_avg_dd = sum(value(row, "max_drawdown") for row in fixed40_rows) / len(fixed40_rows)
    runner_avg_dd = sum(value(row, "max_drawdown") for row in runner_rows) / len(runner_rows)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK",
        "contract": {
            "research_only": True,
            "changes_model": False,
            "changes_production_ranking": False,
            "changes_risk_adjusted_score": False,
            "finite_capital": True,
            "odd_lot_default": True,
            "buy_lot_size": 1,
            "sell_lot_size": 1,
            "run_count": len(runs),
        },
        "runs": {row["id"]: row for row in runs},
        "summary": {
            "winners_by_cash": winners_by_cash,
            "fixed40_avg_return": round(fixed40_avg_return, 6),
            "tp20_runner_stop8_avg_return": round(runner_avg_return, 6),
            "fixed40_avg_drawdown": round(fixed40_avg_dd, 6),
            "tp20_runner_stop8_avg_drawdown": round(runner_avg_dd, 6),
        },
        "decision": {
            "status": "ENTRY_EXIT_POLICY_NOT_READY",
            "fixed40_all": "KEEP_AS_CURRENT_COMPARISON_BASELINE",
            "k9_non_worsening": "CAPITAL_TIER_CANDIDATE_FOR_500K_ONLY",
            "tp20_runner_stop8": "REJECT_AS_DEFAULT_FOR_NOW",
            "entry_filter_policy": "DO_NOT_USE_SINGLE_GLOBAL_FILTER",
            "primary_read": (
                "固定 40 天仍是目前最強比較組；entry filter 會和本金層互動，不能做成全域開關。"
                "TP20 runner stop8 平均報酬明顯低於 fixed40，暫不當預設出場規則。"
            ),
            "next_experiments": [
                "測 entry price guard：避免 D+1 開盤追高，不只看入榜天數/排名變化。",
                "測分段停損：跌破警戒先降曝險，不一定立刻全出。",
                "把 50 萬 K9 non_worsening 當 capital-tier shadow，不上正式。",
            ],
        },
    }


def pct(value_: Any) -> str:
    if value_ is None:
        return "--"
    return f"{float(value_):.2%}"


def money(value_: Any) -> str:
    if value_ is None:
        return "--"
    return f"{float(value_):,.0f}"


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# CAPITAL-REALISM-02 Report",
        "",
        f"- status: `{payload['status']}`",
        f"- decision: `{payload['decision']['status']}`",
        f"- fixed40_all: `{payload['decision']['fixed40_all']}`",
        f"- k9_non_worsening: `{payload['decision']['k9_non_worsening']}`",
        f"- tp20_runner_stop8: `{payload['decision']['tp20_runner_stop8']}`",
        "",
        "## 白話結論",
        "",
        payload["decision"]["primary_read"],
        "",
        "## Winners By Cash",
        "",
        "```json",
        json.dumps(payload["summary"]["winners_by_cash"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Runs",
        "",
        "| id | return | max DD | final equity | trades | avg cash |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for run_id, row in sorted(payload["runs"].items()):
        lines.append(
            f"| {run_id} | {pct(row.get('total_return'))} | {pct(row.get('max_drawdown'))} | "
            f"{money(row.get('final_equity'))} | {row.get('trade_count')} | {pct(row.get('avg_cash_ratio'))} |"
        )
    lines.extend(["", "## Decision", "", "```json", json.dumps(payload["decision"], ensure_ascii=False, indent=2), "```", ""])
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = resolve_path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "output": repo_path(output),
                "decision": payload["decision"]["status"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
