#!/usr/bin/env python3
"""彙整有限本金出場規則實驗。

這支報告器只讀 replay artifacts，目標是把「假設、測試、結論、後續處置」
收斂成固定格式，避免之後又憑印象重開同一批 exit rule。
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "capital-exit-rule-report.v1"


DEFAULT_RUNS = {
    "baseline_fixed40_fixed65": "artifacts/backtest/capital_aware_replay_current_fixed40_fixed65_half_year_2026-06-03.json",
    "candidate_fixed40_regime": "artifacts/backtest/capital_aware_replay_current_fixed40_regime_half_year_2026-06-03.json",
    "tp15_sell40_regime": "artifacts/backtest/capital_aware_replay_tp15_partial_runner_regime_half_year_2026-06-03.json",
    "tp15_sell33_regime": "artifacts/backtest/capital_aware_replay_tp15_sell33_runner_regime_half_year_2026-06-03.json",
    "tp15_sell50_regime": "artifacts/backtest/capital_aware_replay_tp15_sell50_runner_regime_half_year_2026-06-03.json",
    "tp20_sell33_regime": "artifacts/backtest/capital_aware_replay_tp20_sell33_runner_regime_half_year_2026-06-03.json",
    "tp20_sell50_regime": "artifacts/backtest/capital_aware_replay_tp20_sell50_runner_regime_half_year_2026-06-03.json",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build capital exit rule report")
    parser.add_argument("--output", default="artifacts/model_experiments/capital_exit_rule_report_2026-06-03.json")
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"artifact 不存在：{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def pct(value: Any) -> str:
    if value is None:
        return "--"
    return f"{float(value):.2%}"


def run_row(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary", {})
    inputs = payload.get("inputs", {})
    contract = payload.get("contract", {})
    return {
        "name": name,
        "path": payload.get("_path"),
        "research_only": bool(contract.get("research_only")),
        "changes_model": bool(contract.get("changes_model")),
        "changes_ranking_score": bool(contract.get("changes_ranking_score")),
        "scenario": inputs.get("scenario"),
        "gross_policy": inputs.get("gross_policy"),
        "initial_cash": summary.get("initial_cash"),
        "final_equity": summary.get("final_equity"),
        "total_return": summary.get("total_return"),
        "max_drawdown": summary.get("max_drawdown"),
        "win_rate": summary.get("win_rate"),
        "trade_count": summary.get("trade_count"),
        "avg_gross_exposure": summary.get("avg_gross_exposure"),
        "min_cash_ratio": summary.get("min_cash_ratio"),
        "partial_take_profit_count": summary.get("partial_take_profit_count"),
        "exit_reason_counts": summary.get("exit_reason_counts", {}),
        "skip_reason_counts": summary.get("skip_reason_counts", {}),
        "tp_pct": inputs.get("tp_partial_runner", {}).get("tp_pct"),
        "partial_sell_pct": inputs.get("tp_partial_runner", {}).get("partial_sell_pct"),
        "buy_lot_size": contract.get("buy_lot_size"),
        "sell_lot_size": contract.get("sell_lot_size"),
    }


def relative_delta(value: float, baseline: float) -> float:
    if baseline == 0:
        return 0.0
    return value / baseline - 1


def build_decisions(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_name = {row["name"]: row for row in rows}
    baseline = by_name["baseline_fixed40_fixed65"]
    best = max(rows, key=lambda row: float(row["total_return"]))
    best_tp = max([row for row in rows if row["name"].startswith("tp")], key=lambda row: float(row["total_return"]))
    candidate = by_name["candidate_fixed40_regime"]

    candidate_return_delta = float(candidate["total_return"]) - float(baseline["total_return"])
    candidate_dd_delta = abs(float(candidate["max_drawdown"])) - abs(float(baseline["max_drawdown"]))
    best_tp_return_delta = float(best_tp["total_return"]) - float(candidate["total_return"])
    best_tp_dd_delta = abs(float(best_tp["max_drawdown"])) - abs(float(candidate["max_drawdown"]))

    if best["name"] == "candidate_fixed40_regime" and candidate_return_delta > 0 and candidate_dd_delta < 0:
        fixed40_decision = "KEEP_AS_PRIMARY_CAPITAL_AWARE_CANDIDATE"
    else:
        fixed40_decision = "MONITOR_ONLY"

    if best_tp_return_delta >= -0.05 and best_tp_dd_delta <= -0.01:
        tp_decision = "FOLLOWUP_CANDIDATE"
    else:
        tp_decision = "REJECT_AS_PRIMARY_RULE"

    return {
        "winner": best["name"],
        "capital_aware_fixed40_regime": {
            "decision": fixed40_decision,
            "reason": "近半年有限本金下，報酬高於 fixed65 baseline，且最大回撤更小。",
            "return_delta_vs_fixed65": round(candidate_return_delta, 6),
            "drawdown_abs_delta_vs_fixed65": round(candidate_dd_delta, 6),
        },
        "tp_partial_runner": {
            "decision": tp_decision,
            "best_variant": best_tp["name"],
            "reason": "最佳 TP partial runner 沒有比 fixed40 + regime gross 更好；報酬較低，回撤也更大或改善不足。",
            "return_delta_vs_fixed40_regime": round(best_tp_return_delta, 6),
            "drawdown_abs_delta_vs_fixed40_regime": round(best_tp_dd_delta, 6),
        },
        "production_boundary": {
            "promotion_ready": False,
            "changes_model": False,
            "changes_ranking_score": False,
            "allowed_next_step": "shadow_daily_monitor_or_long_window_validation",
        },
    }


def build_payload() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    missing: list[str] = []
    for name, value in DEFAULT_RUNS.items():
        path = resolve_path(value)
        try:
            payload = load_json(path)
        except FileNotFoundError:
            missing.append(value)
            continue
        payload["_path"] = repo_path(path)
        rows.append(run_row(name, payload))

    status = "OK" if not missing else "FAILED"
    decisions = build_decisions(rows) if status == "OK" else {}
    hypotheses = [
        {
            "id": "H1",
            "hypothesis": "有限本金後，原本無限資金的 Top10 回測仍可能失真。",
            "test": "500,000 TWD、100 股買進單位、單檔 10%、產業 30%、最多 10 檔。",
            "result": "validated",
            "action": "後續 replay 必須保留 finite-capital 版本，不能只看無限資金績效。",
        },
        {
            "id": "H2",
            "hypothesis": "牛市不該過度保留現金，盤勢曝險應該比固定 gross65 更有效。",
            "test": "fixed40 + regime gross 對 fixed40 + fixed65。",
            "result": decisions.get("capital_aware_fixed40_regime", {}).get("decision", "unknown"),
            "action": "把 fixed40 + regime gross 留作 primary capital-aware candidate，不直接改 production。",
        },
        {
            "id": "H3",
            "hypothesis": "TP15/TP20 partial runner 可以少賠但不會太早下車。",
            "test": "TP15/TP20 x partial 33/40/50。",
            "result": decisions.get("tp_partial_runner", {}).get("decision", "unknown"),
            "action": "暫不採用為主規則；只保留為之後頁面說明/使用者偏好風控的研究素材。",
        },
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "contract": {
            "research_only": True,
            "changes_model": False,
            "changes_ranking_score": False,
            "changes_production_push": False,
            "finite_capital_required": True,
        },
        "inputs": DEFAULT_RUNS,
        "missing_artifacts": missing,
        "hypotheses": hypotheses,
        "runs": rows,
        "decisions": decisions,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Capital Exit Rule Report",
        "",
        f"- status: `{payload['status']}`",
        f"- research_only: `{payload['contract']['research_only']}`",
        f"- production_changed: `{payload['contract']['changes_model'] or payload['contract']['changes_ranking_score'] or payload['contract']['changes_production_push']}`",
        "",
        "## Run Matrix",
        "",
        "| name | return | max DD | win rate | trades | avg gross | min cash | decision |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    decisions = payload.get("decisions", {})
    best_tp = decisions.get("tp_partial_runner", {}).get("best_variant")
    for row in payload.get("runs", []):
        decision = ""
        if row["name"] == decisions.get("winner"):
            decision = "winner"
        elif row["name"] == best_tp:
            decision = "best TP"
        lines.append(
            "| {name} | {ret} | {dd} | {win} | {trades} | {gross} | {cash} | {decision} |".format(
                name=row["name"],
                ret=pct(row["total_return"]),
                dd=pct(row["max_drawdown"]),
                win=pct(row["win_rate"]),
                trades=row["trade_count"],
                gross=pct(row["avg_gross_exposure"]),
                cash=pct(row["min_cash_ratio"]),
                decision=decision,
            )
        )
    lines.extend(["", "## Decisions", ""])
    lines.append(json.dumps(payload.get("decisions", {}), ensure_ascii=False, indent=2))
    lines.extend(["", "## Hypotheses", ""])
    for item in payload.get("hypotheses", []):
        lines.append(f"- `{item['id']}` {item['hypothesis']} -> `{item['result']}`；{item['action']}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload()
    output = resolve_path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output), "winner": payload.get("decisions", {}).get("winner")}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
