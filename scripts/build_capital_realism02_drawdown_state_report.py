#!/usr/bin/env python3
"""彙整 CAPITAL-REALISM-02 drawdown state 出場測試。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "capital-realism02-drawdown-state-report.v1"
RUN_DATE = "2026-06-05"
VARIANTS = ("baseline", "k9")
CASH_LEVELS = (300_000, 500_000, 1_000_000)
DRAWDOWN_LEVELS = ("015", "020", "025")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build CAPITAL-REALISM-02 drawdown state report")
    parser.add_argument(
        "--output",
        default=f"artifacts/model_experiments/capital_realism02_drawdown_state_report_{RUN_DATE}.json",
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


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"artifact missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def number(value: Any) -> float:
    return 0.0 if value is None else float(value)


def load_run(path: Path, run_id: str, variant: str, cash: int, drawdown: str) -> dict[str, Any]:
    payload = read_json(path)
    contract = payload.get("contract", {})
    inputs = payload.get("inputs", {})
    runner = inputs.get("tp_partial_runner", {})
    summary = payload.get("summary", {})
    return {
        "id": run_id,
        "path": repo_path(path),
        "variant": variant,
        "initial_cash": cash,
        "drawdown_level": drawdown,
        "scenario": inputs.get("scenario"),
        "entry_filter": inputs.get("entry_filter"),
        "research_only": contract.get("research_only"),
        "changes_model": contract.get("changes_model"),
        "changes_ranking_score": contract.get("changes_ranking_score"),
        "finite_capital": contract.get("finite_capital"),
        "buy_lot_size": contract.get("buy_lot_size"),
        "sell_lot_size": contract.get("sell_lot_size"),
        "drawdown_state_enabled": runner.get("drawdown_state_enabled"),
        "runner_drawdown_pct": runner.get("runner_drawdown_pct"),
        "total_return": summary.get("total_return"),
        "max_drawdown": summary.get("max_drawdown"),
        "final_equity": summary.get("final_equity"),
        "trade_count": summary.get("trade_count"),
        "avg_cash_ratio": summary.get("avg_cash_ratio"),
        "exit_reason_counts": summary.get("exit_reason_counts", {}),
        "skip_reason_counts": summary.get("skip_reason_counts", {}),
    }


def load_fixed40_reference() -> dict[str, dict[str, Any]]:
    report = read_json(PROJECT_ROOT / "artifacts" / "model_experiments" / f"capital_realism02_report_{RUN_DATE}.json")
    runs = report.get("runs", {})
    refs: dict[str, dict[str, Any]] = {}
    for variant in VARIANTS:
        for cash in CASH_LEVELS:
            run_id = f"{variant}_fixed40_all_{cash}"
            row = runs.get(run_id)
            if not row:
                raise KeyError(f"fixed40 reference missing: {run_id}")
            refs[run_id] = row
    return refs


def build_payload(_: argparse.Namespace) -> dict[str, Any]:
    runs: dict[str, dict[str, Any]] = {}
    comparisons: dict[str, dict[str, Any]] = {}
    fixed40_refs = load_fixed40_reference()

    for variant in VARIANTS:
        for cash in CASH_LEVELS:
            ref_id = f"{variant}_fixed40_all_{cash}"
            ref = fixed40_refs[ref_id]
            for drawdown in DRAWDOWN_LEVELS:
                run_id = f"{variant}_fixed40_all_dd{drawdown}_{cash}"
                path = (
                    PROJECT_ROOT
                    / "artifacts"
                    / "backtest"
                    / f"capital_realism02_drawdown_state_{run_id}_{RUN_DATE}.json"
                )
                row = load_run(path, run_id, variant, cash, drawdown)
                runs[run_id] = row
                comparisons[run_id] = {
                    "run_id": run_id,
                    "fixed40_reference_id": ref_id,
                    "return_delta_vs_fixed40": round(number(row.get("total_return")) - number(ref.get("total_return")), 6),
                    "drawdown_delta_vs_fixed40": round(number(row.get("max_drawdown")) - number(ref.get("max_drawdown")), 6),
                    "trade_count_delta_vs_fixed40": int(row.get("trade_count") or 0) - int(ref.get("trade_count") or 0),
                    "exit_reason_counts": row.get("exit_reason_counts", {}),
                }

    best_return = max(runs.values(), key=lambda row: number(row.get("total_return")))
    best_drawdown = max(runs.values(), key=lambda row: number(row.get("max_drawdown")))
    avg_return_delta = sum(row["return_delta_vs_fixed40"] for row in comparisons.values()) / len(comparisons)
    avg_drawdown_delta = sum(row["drawdown_delta_vs_fixed40"] for row in comparisons.values()) / len(comparisons)
    return_degraded_count = sum(1 for row in comparisons.values() if row["return_delta_vs_fixed40"] < 0)
    drawdown_improved_count = sum(1 for row in comparisons.values() if row["drawdown_delta_vs_fixed40"] > 0)

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
            "drawdown_state_run_count": len(runs),
            "fixed40_reference_count": len(fixed40_refs),
        },
        "runs": runs,
        "comparisons": comparisons,
        "summary": {
            "best_return_run": best_return["id"],
            "best_return_value": best_return["total_return"],
            "best_return_drawdown": best_return["max_drawdown"],
            "lowest_drawdown_run": best_drawdown["id"],
            "lowest_drawdown_value": best_drawdown["max_drawdown"],
            "lowest_drawdown_return": best_drawdown["total_return"],
            "avg_return_delta_vs_fixed40": round(avg_return_delta, 6),
            "avg_drawdown_delta_vs_fixed40": round(avg_drawdown_delta, 6),
            "return_degraded_count": return_degraded_count,
            "drawdown_improved_count": drawdown_improved_count,
        },
        "decision": {
            "status": "DRAWDOWN_STATE_REJECT_AS_DEFAULT",
            "drawdown_state": "TOO_AGGRESSIVE_CURRENT_ENGINE",
            "recommendation_channel": "NO_CHANGE",
            "warning_channel": "NEXT_RESEARCH_TARGET",
            "primary_read": (
                "初版 drawdown state 不能當每日推薦的預設出場。"
                "它確實會讓部位更快出場，但在半年的牛市/高檔震盪樣本裡，"
                "報酬幾乎全面輸給 fixed40，比較像把波段行情提早洗掉。"
            ),
            "next_experiments": [
                "把推薦和警告拆開：推薦仍產 Top10，警告只追蹤近 7 天入榜股票的轉弱狀態。",
                "警告不做個人賣出指令，只標示未進場者別追、已持有者自行檢查。",
                "重新測 warning-only state：個股跌破 + 排名降溫 + 族群/大盤轉弱一起成立才提高警示。",
                "若未來要賣出規則，先測分段降曝險，不直接全出。",
            ],
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
        "# CAPITAL-REALISM-02 Drawdown State Report",
        "",
        f"- status: `{payload['status']}`",
        f"- decision: `{payload['decision']['status']}`",
        f"- drawdown_state: `{payload['decision']['drawdown_state']}`",
        f"- recommendation_channel: `{payload['decision']['recommendation_channel']}`",
        f"- warning_channel: `{payload['decision']['warning_channel']}`",
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
        "## Runs",
        "",
        "| id | return | max DD | return delta | DD delta | final equity | exits |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for run_id, row in sorted(payload["runs"].items()):
        comp = payload["comparisons"][run_id]
        lines.append(
            f"| {run_id} | {pct(row.get('total_return'))} | {pct(row.get('max_drawdown'))} | "
            f"{pct(comp.get('return_delta_vs_fixed40'))} | {pct(comp.get('drawdown_delta_vs_fixed40'))} | "
            f"{money(row.get('final_equity'))} | {json.dumps(row.get('exit_reason_counts', {}), ensure_ascii=False)} |"
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
