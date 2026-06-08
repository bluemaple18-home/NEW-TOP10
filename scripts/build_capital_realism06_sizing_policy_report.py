#!/usr/bin/env python3
"""彙整 CAPITAL-REALISM-06 小本金資金配置矩陣。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "capital-realism06-sizing-policy-report.v1"
RUN_DATE = "2026-06-05"
CASH_LEVELS = (300_000, 500_000, 1_000_000)
POSITION_SETUPS = (("p10", 0.10, 10), ("p12", 0.12, 8), ("p15", 0.15, 7))
MAX_NEW_PER_DAY = (1, 2, 3)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build CAPITAL-REALISM-06 sizing policy report")
    parser.add_argument(
        "--output",
        default=f"artifacts/model_experiments/capital_realism06_sizing_policy_report_{RUN_DATE}.json",
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


def load_run(label: str, max_open: int, max_new: int, cash: int) -> dict[str, Any]:
    path = (
        PROJECT_ROOT
        / "artifacts"
        / "backtest"
        / f"capital_realism06_sizing_current_{label}_open{max_open}_new{max_new}_{cash}_{RUN_DATE}.json"
    )
    payload = read_json(path)
    contract = payload.get("contract", {})
    inputs = payload.get("inputs", {})
    summary = payload.get("summary", {})
    return {
        "id": f"{label}_open{max_open}_new{max_new}_{cash}",
        "path": repo_path(path),
        "research_only": contract.get("research_only"),
        "changes_model": contract.get("changes_model"),
        "changes_ranking_score": contract.get("changes_ranking_score"),
        "buy_lot_size": contract.get("buy_lot_size"),
        "sell_lot_size": contract.get("sell_lot_size"),
        "initial_cash": int(cash),
        "max_position_pct": inputs.get("max_position_pct"),
        "max_open_positions": inputs.get("max_open_positions"),
        "max_new_positions_per_day": inputs.get("max_new_positions_per_day"),
        "gross_policy": inputs.get("gross_policy"),
        "scenario": inputs.get("scenario"),
        "entry_filter": inputs.get("entry_filter"),
        "total_return": summary.get("total_return"),
        "max_drawdown": summary.get("max_drawdown"),
        "final_equity": summary.get("final_equity"),
        "trade_count": summary.get("trade_count"),
        "win_rate": summary.get("win_rate"),
        "avg_cash_ratio": summary.get("avg_cash_ratio"),
        "max_gross_exposure": summary.get("max_gross_exposure"),
        "skip_reason_counts": summary.get("skip_reason_counts", {}),
    }


def setup_key(row: dict[str, Any]) -> str:
    return f"p{int(round(float(row['max_position_pct']) * 100)):02d}_open{row['max_open_positions']}_new{row['max_new_positions_per_day']}"


def build_payload(_: argparse.Namespace) -> dict[str, Any]:
    runs: dict[str, dict[str, Any]] = {}
    for label, _position_pct, max_open in POSITION_SETUPS:
        for max_new in MAX_NEW_PER_DAY:
            for cash in CASH_LEVELS:
                row = load_run(label, max_open, max_new, cash)
                runs[row["id"]] = row

    by_setup: dict[str, dict[str, Any]] = {}
    for key in sorted({setup_key(row) for row in runs.values()}):
        rows = [row for row in runs.values() if setup_key(row) == key]
        avg_return = sum(number(row["total_return"]) for row in rows) / len(rows)
        avg_drawdown = sum(number(row["max_drawdown"]) for row in rows) / len(rows)
        avg_cash = sum(number(row["avg_cash_ratio"]) for row in rows) / len(rows)
        by_setup[key] = {
            "run_ids": [row["id"] for row in rows],
            "avg_return": round(avg_return, 6),
            "avg_drawdown": round(avg_drawdown, 6),
            "avg_cash_ratio": round(avg_cash, 6),
            "min_return": round(min(number(row["total_return"]) for row in rows), 6),
            "worst_drawdown": round(min(number(row["max_drawdown"]) for row in rows), 6),
            "avg_trade_count": round(sum(number(row["trade_count"]) for row in rows) / len(rows), 2),
            "risk_adjusted_return": round(avg_return / abs(avg_drawdown), 6) if avg_drawdown else None,
        }

    return_leader = max(by_setup.items(), key=lambda item: item[1]["avg_return"])
    balanced_candidate = max(by_setup.items(), key=lambda item: item[1]["risk_adjusted_return"] or 0)

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
            "run_count": len(runs),
        },
        "runs": runs,
        "summary": {
            "by_setup": by_setup,
            "return_leader": {"setup": return_leader[0], **return_leader[1]},
            "balanced_candidate": {"setup": balanced_candidate[0], **balanced_candidate[1]},
        },
        "decision": {
            "status": "SIZING_POLICY_CANDIDATE_FOUND",
            "return_leader": return_leader[0],
            "balanced_candidate": balanced_candidate[0],
            "recommended_next_shadow": balanced_candidate[0],
            "production_change": False,
            "primary_read": (
                "每檔 10% / 最多 10 檔 / 每天最多新進 3 檔是報酬領先組；"
                "每檔 12% / 最多 8 檔 / 每天最多新進 2 檔的報酬略低，但回撤較小、風險報酬比較好，"
                "更適合當小白資金配置 shadow candidate。"
            ),
            "next_experiments": [
                "用 balanced candidate 跑 K9 / current ranking 對照，不混 entry/exit 新規則。",
                "把推薦訊息的部位語言改成本金分層，而不是模型把握度或建議百分比。",
                "若要上正式，先讓 current production 作比較組，不直接覆蓋。",
            ],
        },
    }


def pct(value: Any) -> str:
    if value is None:
        return "--"
    return f"{float(value):.2%}"


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# CAPITAL-REALISM-06 Sizing Policy Report",
        "",
        f"- status: `{payload['status']}`",
        f"- decision: `{payload['decision']['status']}`",
        f"- return_leader: `{payload['decision']['return_leader']}`",
        f"- balanced_candidate: `{payload['decision']['balanced_candidate']}`",
        "",
        "## By Setup",
        "",
        "| setup | avg return | avg DD | risk-adjusted | avg cash | avg trades |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for setup, row in sorted(payload["summary"]["by_setup"].items()):
        lines.append(
            f"| {setup} | {pct(row['avg_return'])} | {pct(row['avg_drawdown'])} | "
            f"{row['risk_adjusted_return']} | {pct(row['avg_cash_ratio'])} | {row['avg_trade_count']} |"
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "```json",
            json.dumps(payload["decision"], ensure_ascii=False, indent=2),
            "```",
            "",
        ]
    )
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
            {"status": payload["status"], "output": repo_path(output), "decision": payload["decision"]["status"]},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
