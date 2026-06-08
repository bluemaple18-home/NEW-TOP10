#!/usr/bin/env python3
"""彙整 CAPITAL-REALISM-02 entry guard / stop policy follow-up。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "capital-realism02-followup-report.v1"
RUN_DATE = "2026-06-05"
VARIANTS = ("baseline", "k9")
CASH_LEVELS = (300_000, 500_000, 1_000_000)
PREMIUMS = ("003", "005", "008")
STOP_POLICIES = ("stop8_full", "stop8_half", "stop12_full")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build CAPITAL-REALISM-02 follow-up report")
    parser.add_argument(
        "--output",
        default=f"artifacts/model_experiments/capital_realism02_followup_report_{RUN_DATE}.json",
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


def load_run(path: Path, run_id: str) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"artifact missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    contract = payload.get("contract", {})
    inputs = payload.get("inputs", {})
    summary = payload.get("summary", {})
    return {
        "id": run_id,
        "path": repo_path(path),
        "research_only": contract.get("research_only"),
        "changes_model": contract.get("changes_model"),
        "changes_ranking_score": contract.get("changes_ranking_score"),
        "buy_lot_size": contract.get("buy_lot_size"),
        "sell_lot_size": contract.get("sell_lot_size"),
        "initial_cash": inputs.get("initial_cash"),
        "variant": run_id.split("_")[0],
        "total_return": summary.get("total_return"),
        "max_drawdown": summary.get("max_drawdown"),
        "final_equity": summary.get("final_equity"),
        "trade_count": summary.get("trade_count"),
        "skip_reason_counts": summary.get("skip_reason_counts", {}),
        "exit_reason_counts": summary.get("exit_reason_counts", {}),
    }


def number(value: Any) -> float:
    return 0.0 if value is None else float(value)


def build_payload(_: argparse.Namespace) -> dict[str, Any]:
    entry_guard_runs: dict[str, dict[str, Any]] = {}
    stop_policy_runs: dict[str, dict[str, Any]] = {}

    for variant in VARIANTS:
        for cash in CASH_LEVELS:
            for premium in PREMIUMS:
                run_id = f"{variant}_fixed40_all_p{premium}_{cash}"
                path = PROJECT_ROOT / "artifacts" / "backtest" / f"capital_realism02_entry_guard_{run_id}_{RUN_DATE}.json"
                entry_guard_runs[run_id] = load_run(path, run_id)
            for policy in STOP_POLICIES:
                run_id = f"{variant}_fixed40_all_{policy}_{cash}"
                path = PROJECT_ROOT / "artifacts" / "backtest" / f"capital_realism02_stop_policy_{run_id}_{RUN_DATE}.json"
                stop_policy_runs[run_id] = load_run(path, run_id)

    guard_trigger_count = sum(
        int(row.get("skip_reason_counts", {}).get("entry_price_too_high", 0))
        for row in entry_guard_runs.values()
    )
    stop_best_by_cash: dict[str, dict[str, Any]] = {}
    for cash in CASH_LEVELS:
        subset = [row for row in stop_policy_runs.values() if int(float(row["initial_cash"])) == cash]
        best_return = max(subset, key=lambda row: number(row.get("total_return")))
        best_drawdown = max(subset, key=lambda row: number(row.get("max_drawdown")))
        stop_best_by_cash[str(cash)] = {
            "best_return": best_return["id"],
            "best_return_value": best_return["total_return"],
            "best_return_drawdown": best_return["max_drawdown"],
            "lowest_drawdown": best_drawdown["id"],
            "lowest_drawdown_value": best_drawdown["max_drawdown"],
            "lowest_drawdown_return": best_drawdown["total_return"],
        }

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
            "entry_guard_run_count": len(entry_guard_runs),
            "stop_policy_run_count": len(stop_policy_runs),
        },
        "entry_guard_runs": entry_guard_runs,
        "stop_policy_runs": stop_policy_runs,
        "summary": {
            "entry_guard_trigger_count": guard_trigger_count,
            "stop_best_by_cash": stop_best_by_cash,
        },
        "decision": {
            "status": "FOLLOWUP_COMPLETE_NO_PRODUCTION_CHANGE",
            "entry_price_guard": "NO_EFFECT_IN_CURRENT_HALF_YEAR_SAMPLE",
            "stop_policy": "REJECT_MECHANICAL_STOP_AS_DEFAULT",
            "partial_stop": "RESEARCH_ONLY",
            "primary_read": (
                "D+1 追價 guard 在目前成交樣本沒有觸發；問題不在隔天開太高。"
                "機械停損多數降低報酬，且不穩定降低回撤；不能直接做成推播預設賣出規則。"
            ),
            "next_experiments": [
                "改測 drawdown state：只在個股跌破且排名/族群/大盤同步轉弱時降曝險。",
                "把警告和推薦拆開：近期 Top10 追蹤池只提醒風險，不當個人賣出指令。",
                "capital tier shadow：50 萬 K9 non_worsening 保留觀察，不上正式。",
            ],
        },
    }


def pct(value: Any) -> str:
    if value is None:
        return "--"
    return f"{float(value):.2%}"


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# CAPITAL-REALISM-02 Follow-up Report",
        "",
        f"- status: `{payload['status']}`",
        f"- decision: `{payload['decision']['status']}`",
        f"- entry_price_guard: `{payload['decision']['entry_price_guard']}`",
        f"- stop_policy: `{payload['decision']['stop_policy']}`",
        "",
        "## 白話結論",
        "",
        payload["decision"]["primary_read"],
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(payload["summary"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Decision",
        "",
        "```json",
        json.dumps(payload["decision"], ensure_ascii=False, indent=2),
        "```",
        "",
    ]
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
