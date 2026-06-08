#!/usr/bin/env python3
"""彙整零股有限本金 replay 矩陣。

這份報告把「小白可買零股」正式納入資金規則研究：

- 買賣單位用 1 股，不再用 100 股當預設限制。
- 比較 production baseline、K8、K9 在不同本金與出場規則下的表現。
- 只產研究 artifact，不改模型、不改 ranking、不改推播。
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "odd-lot-capital-matrix-report.v1"
RUN_DATE = "2026-06-04"
VARIANTS = ("baseline", "k8", "k9")
SCENARIOS = ("fixed40", "tp15_partial_runner")
CASH_LEVELS = (300_000, 500_000, 1_000_000)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build odd-lot capital matrix report")
    parser.add_argument(
        "--output",
        default=f"artifacts/model_experiments/odd_lot_capital_matrix_report_{RUN_DATE}.json",
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


def run_path(variant: str, scenario: str, cash: int) -> Path:
    return PROJECT_ROOT / "artifacts" / "backtest" / f"odd_lot_capital_{variant}_{scenario}_{cash}_{RUN_DATE}.json"


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"artifact 不存在：{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def summarize_run(variant: str, scenario: str, cash: int) -> dict[str, Any]:
    path = run_path(variant, scenario, cash)
    payload = read_json(path)
    contract = payload.get("contract", {})
    inputs = payload.get("inputs", {})
    summary = payload.get("summary", {})
    return {
        "variant": variant,
        "scenario": scenario,
        "initial_cash": cash,
        "path": repo_path(path),
        "research_only": contract.get("research_only"),
        "changes_model": contract.get("changes_model"),
        "changes_ranking_score": contract.get("changes_ranking_score"),
        "finite_capital": contract.get("finite_capital"),
        "buy_lot_size": contract.get("buy_lot_size"),
        "sell_lot_size": contract.get("sell_lot_size"),
        "entry_timing": contract.get("entry_timing"),
        "rankings_dir": inputs.get("rankings_dir"),
        "gross_policy": inputs.get("gross_policy"),
        "horizon": inputs.get("horizon"),
        "final_equity": summary.get("final_equity"),
        "total_return": summary.get("total_return"),
        "max_drawdown": summary.get("max_drawdown"),
        "trade_count": summary.get("trade_count"),
        "win_rate": summary.get("win_rate"),
        "avg_gross_exposure": summary.get("avg_gross_exposure"),
        "avg_cash_ratio": summary.get("avg_cash_ratio"),
        "buy_lot_block_count": summary.get("buy_lot_block_count"),
        "cash_block_count": summary.get("cash_block_count"),
        "exit_reason_counts": summary.get("exit_reason_counts", {}),
    }


def numeric(value: Any) -> float:
    if value is None:
        return 0.0
    return float(value)


def delta(candidate: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    return {
        "return_delta": round(numeric(candidate.get("total_return")) - numeric(baseline.get("total_return")), 6),
        "drawdown_delta": round(numeric(candidate.get("max_drawdown")) - numeric(baseline.get("max_drawdown")), 6),
        "final_equity_delta": round(numeric(candidate.get("final_equity")) - numeric(baseline.get("final_equity")), 2),
    }


def best_by_return(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return max(rows, key=lambda row: numeric(row.get("total_return")))


def build_payload(_: argparse.Namespace) -> dict[str, Any]:
    runs: dict[str, dict[str, Any]] = {}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for scenario in SCENARIOS:
        for cash in CASH_LEVELS:
            group_key = f"{scenario}_{cash}"
            grouped[group_key] = []
            for variant in VARIANTS:
                row = summarize_run(variant, scenario, cash)
                runs[f"{variant}_{scenario}_{cash}"] = row
                grouped[group_key].append(row)

    comparisons: dict[str, Any] = {}
    winners: dict[str, str] = {}
    for group_key, rows in grouped.items():
        baseline = next(row for row in rows if row["variant"] == "baseline")
        comparisons[group_key] = {
            "k8_vs_baseline": delta(next(row for row in rows if row["variant"] == "k8"), baseline),
            "k9_vs_baseline": delta(next(row for row in rows if row["variant"] == "k9"), baseline),
        }
        winners[group_key] = str(best_by_return(rows)["variant"])

    fixed40_winners = {
        cash: winners[f"fixed40_{cash}"]
        for cash in CASH_LEVELS
    }
    tp15_winners = {
        cash: winners[f"tp15_partial_runner_{cash}"]
        for cash in CASH_LEVELS
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
            "buy_lot_size": 1,
            "sell_lot_size": 1,
            "initial_cash_levels": list(CASH_LEVELS),
            "scenarios": list(SCENARIOS),
        },
        "runs": runs,
        "comparisons": comparisons,
        "winners_by_return": winners,
        "decision": {
            "status": "CAPITAL_RULES_NEED_MORE_WORK",
            "ranking_decision": "KEEP_K9_MINIMAL_OVERLAY_WITH_BASELINE_CONTROL",
            "odd_lot_policy": "ADOPT_AS_DEFAULT_CAPITAL_REPLAY_ASSUMPTION",
            "tp15_partial_runner": "REJECT_AS_DEFAULT_EXIT_RULE",
            "primary_read": (
                "零股讓小本金可以參與高價股，但 K9 在有限本金下不是穩定報酬勝出；"
                "它仍可作為保守排名微調，資金與出場規則要分開訓練。"
            ),
            "fixed40_return_winners": fixed40_winners,
            "tp15_return_winners": tp15_winners,
            "next_experiments": [
                "entry-zone guard：只在合理價格帶內承接，不追過熱開盤價",
                "dynamic exit state machine：停損、減碼、續抱分層，不再只測 TP15 一刀規則",
                "capital tier policy：30萬 / 50萬 / 100萬 各自檢查持股數、單檔上限與現金水位",
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
        "# Odd-Lot Capital Matrix Report",
        "",
        f"- status: `{payload['status']}`",
        f"- decision: `{payload['decision']['status']}`",
        f"- ranking_decision: `{payload['decision']['ranking_decision']}`",
        f"- odd_lot_policy: `{payload['decision']['odd_lot_policy']}`",
        f"- tp15_partial_runner: `{payload['decision']['tp15_partial_runner']}`",
        "",
        "## 白話結論",
        "",
        payload["decision"]["primary_read"],
        "",
        "零股是假設主線，因為使用者不必買整張；但這不等於 K9 或 TP15 出場規則自動變好。",
        "",
        "## Runs",
        "",
        "| variant | scenario | cash | return | max DD | final equity | win rate | trades | avg cash |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for key in sorted(payload["runs"].keys()):
        row = payload["runs"][key]
        lines.append(
            "| {variant} | {scenario} | {cash} | {ret} | {dd} | {equity} | {win} | {trades} | {cash_ratio} |".format(
                variant=row["variant"],
                scenario=row["scenario"],
                cash=money(row.get("initial_cash")),
                ret=pct(row.get("total_return")),
                dd=pct(row.get("max_drawdown")),
                equity=money(row.get("final_equity")),
                win=pct(row.get("win_rate")),
                trades=row.get("trade_count"),
                cash_ratio=pct(row.get("avg_cash_ratio")),
            )
        )
    lines.extend(
        [
            "",
            "## Decisions",
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
            {
                "status": payload["status"],
                "output": repo_path(output),
                "decision": payload["decision"]["status"],
                "odd_lot_policy": payload["decision"]["odd_lot_policy"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
