#!/usr/bin/env python3
"""整理營運規則的 portfolio replay 證據。"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "operational-portfolio-rule-report.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build operational portfolio rule report")
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
    if value is None:
        return "n/a"
    return f"{n(value):.2%}"


def compact(label: str, path: str) -> dict[str, Any]:
    resolved = resolve_path(path)
    payload = read_json(resolved)
    summary = payload.get("summary") or {}
    daily = payload.get("daily") or []
    return {
        "label": label,
        "path": repo_path(resolved),
        "exists": bool(payload),
        "total_return": summary.get("total_return"),
        "max_drawdown": summary.get("max_drawdown"),
        "trade_count": summary.get("trade_count"),
        "skipped_count": summary.get("skipped_count"),
        "win_rate": summary.get("win_rate"),
        "avg_trade_return": summary.get("avg_trade_return"),
        "max_gross_exposure": summary.get("max_gross_exposure"),
        "max_group_exposure": summary.get("max_group_exposure"),
        "avg_gross_exposure": summary.get("avg_gross_exposure"),
        "inputs": payload.get("inputs") or {},
        "contract": payload.get("contract") or {},
        "rolling_20d": rolling_stats(daily, 20),
        "rolling_40d": rolling_stats(daily, 40),
    }


def rolling_stats(daily: list[dict[str, Any]], window: int) -> dict[str, Any]:
    if len(daily) < window:
        return {"window": window, "count": 0}
    rows = sorted(daily, key=lambda item: str(item.get("date") or ""))
    returns = []
    drawdowns = []
    for index in range(0, len(rows) - window + 1):
        slice_rows = rows[index : index + window]
        start_equity = n(slice_rows[0].get("equity"))
        end_equity = n(slice_rows[-1].get("equity"))
        if start_equity <= 0:
            continue
        values = [n(row.get("equity")) for row in slice_rows]
        high = values[0]
        worst_dd = 0.0
        for value in values:
            high = max(high, value)
            worst_dd = min(worst_dd, value / high - 1 if high else 0.0)
        returns.append(end_equity / start_equity - 1)
        drawdowns.append(worst_dd)
    if not returns:
        return {"window": window, "count": 0}
    return {
        "window": window,
        "count": len(returns),
        "avg_return": round(sum(returns) / len(returns), 6),
        "worst_return": round(min(returns), 6),
        "positive_rate": round(sum(value > 0 for value in returns) / len(returns), 6),
        "worst_drawdown": round(min(drawdowns), 6),
    }


def delta(row: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "return_delta_vs_baseline": round(n(row.get("total_return")) - n(baseline.get("total_return")), 6),
        "drawdown_delta_vs_baseline": round(n(row.get("max_drawdown")) - n(baseline.get("max_drawdown")), 6),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    rows = {
        "production_fixed40": compact("production_fixed40", "artifacts/backtest/portfolio_replay_production_fixed40_2026-06-02.json"),
        "production_fixed20": compact("production_fixed20", "artifacts/backtest/portfolio_replay_production_fixed20_2026-06-02.json"),
        "production_fixed30": compact("production_fixed30", "artifacts/backtest/portfolio_replay_production_fixed30_2026-06-02.json"),
        "production_trail25": compact("production_trail25", "artifacts/backtest/portfolio_replay_production_h40_trail25_2026-06-02.json"),
        "production_sl10": compact("production_sl10", "artifacts/backtest/portfolio_replay_production_h40_sl10_min5_2026-06-02.json"),
        "production_tp35_sl12": compact("production_tp35_sl12", "artifacts/backtest/portfolio_replay_production_h40_tp35_sl12_min5_2026-06-02.json"),
        "production_sector45": compact("production_sector45", "artifacts/backtest/portfolio_replay_production_fixed40_sector45_2026-06-02.json"),
        "production_sector35": compact("production_sector35", "artifacts/backtest/portfolio_replay_production_fixed40_sector35_2026-06-02.json"),
        "production_top3": compact("production_top3", "artifacts/backtest/portfolio_replay_production_fixed40_top3_2026-06-02.json"),
        "production_top5": compact("production_top5", "artifacts/backtest/portfolio_replay_production_fixed40_top5_2026-06-02.json"),
        "production_top7": compact("production_top7", "artifacts/backtest/portfolio_replay_production_fixed40_top7_2026-06-02.json"),
        "candidate_fixed40": compact(
            "candidate_fixed40",
            "artifacts/model_experiments/training_candidates/candidate_2026-06-02_config/portfolio_replay_candidate_fixed40_2026-06-02.json",
        ),
        "candidate_fixed20": compact(
            "candidate_fixed20",
            "artifacts/model_experiments/training_candidates/candidate_2026-06-02_config/portfolio_replay_candidate_fixed20_2026-06-02.json",
        ),
        "candidate_fixed30": compact(
            "candidate_fixed30",
            "artifacts/model_experiments/training_candidates/candidate_2026-06-02_config/portfolio_replay_candidate_fixed30_2026-06-02.json",
        ),
        "candidate_trail25": compact(
            "candidate_trail25",
            "artifacts/model_experiments/training_candidates/candidate_2026-06-02_config/portfolio_replay_candidate_h40_trail25_2026-06-02.json",
        ),
        "candidate_sl10": compact(
            "candidate_sl10",
            "artifacts/model_experiments/training_candidates/candidate_2026-06-02_config/portfolio_replay_candidate_h40_sl10_min5_2026-06-02.json",
        ),
        "candidate_tp35_sl12": compact(
            "candidate_tp35_sl12",
            "artifacts/model_experiments/training_candidates/candidate_2026-06-02_config/portfolio_replay_candidate_h40_tp35_sl12_min5_2026-06-02.json",
        ),
        "candidate_sector45": compact(
            "candidate_sector45",
            "artifacts/model_experiments/training_candidates/candidate_2026-06-02_config/portfolio_replay_candidate_fixed40_sector45_2026-06-02.json",
        ),
        "candidate_sector35": compact(
            "candidate_sector35",
            "artifacts/model_experiments/training_candidates/candidate_2026-06-02_config/portfolio_replay_candidate_fixed40_sector35_2026-06-02.json",
        ),
        "candidate_top3": compact(
            "candidate_top3",
            "artifacts/model_experiments/training_candidates/candidate_2026-06-02_config/portfolio_replay_candidate_fixed40_top3_2026-06-02.json",
        ),
        "candidate_top5": compact(
            "candidate_top5",
            "artifacts/model_experiments/training_candidates/candidate_2026-06-02_config/portfolio_replay_candidate_fixed40_top5_2026-06-02.json",
        ),
        "candidate_top7": compact(
            "candidate_top7",
            "artifacts/model_experiments/training_candidates/candidate_2026-06-02_config/portfolio_replay_candidate_fixed40_top7_2026-06-02.json",
        ),
    }
    prod_fixed = rows["production_fixed40"]
    cand_fixed = rows["candidate_fixed40"]
    comparisons = {
        "production_trail25": delta(rows["production_trail25"], prod_fixed),
        "production_sl10": delta(rows["production_sl10"], prod_fixed),
        "production_tp35_sl12": delta(rows["production_tp35_sl12"], prod_fixed),
        "production_sector45": delta(rows["production_sector45"], prod_fixed),
        "production_sector35": delta(rows["production_sector35"], prod_fixed),
        "candidate_trail25": delta(rows["candidate_trail25"], cand_fixed),
        "candidate_sl10": delta(rows["candidate_sl10"], cand_fixed),
        "candidate_tp35_sl12": delta(rows["candidate_tp35_sl12"], cand_fixed),
        "candidate_sector45": delta(rows["candidate_sector45"], cand_fixed),
        "candidate_sector35": delta(rows["candidate_sector35"], cand_fixed),
        "production_top3": delta(rows["production_top3"], prod_fixed),
        "production_top5": delta(rows["production_top5"], prod_fixed),
        "production_top7": delta(rows["production_top7"], prod_fixed),
        "candidate_top3": delta(rows["candidate_top3"], cand_fixed),
        "candidate_top5": delta(rows["candidate_top5"], cand_fixed),
        "candidate_top7": delta(rows["candidate_top7"], cand_fixed),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK" if all(row["exists"] for row in rows.values()) else "MISSING_INPUT",
        "contract": {
            "research_only": True,
            "model_changes": False,
            "production_ranking_changes": False,
            "promotion_evidence": False,
        },
        "summary": {
            "overall_decision": "PORTFOLIO_RULE_RESEARCH_ONLY",
            "holding_rule": "PRODUCTION_40D_BASELINE_CANDIDATE_MIXED",
            "exit_rule": "KEEP_FIXED40_FOR_NOW",
            "trailing_rule": "REJECT_TRAIL25_FOR_PORTFOLIO",
            "stop_rule": "REJECT_SIMPLE_STOP_RULES_FOR_NOW",
            "sector_rule": "PRODUCTION_SECTOR45_MONITOR_CANDIDATE",
            "topn_rule": "KEEP_TOP10_WITH_TOP3_AGGRESSIVE_MONITOR",
            "candidate_overlay": "NO_CANDIDATE_OVERLAY",
        },
        "rows": rows,
        "comparisons": comparisons,
        "next_actions": [
            "production fixed_40d 仍是 portfolio 層主基準；trail25 不進下一關。",
            "持有天數以 production 40D 為主研究基準；candidate 20D 較好但不穩，不改主線。",
            "sl10 與 tp35/sl12 不穩定：不是砍報酬，就是只在 candidate 上改善。",
            "sector45 對 production 報酬傷害很小，可進更長區間與 rolling-window 監控。",
            "Top10 不改；Top3 只可做積極核心觀察標籤，因為報酬高但回撤也高。",
            "candidate fixed40/sector cap 都不可替代 production；candidate 只保留 research-only。",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    rows = payload["rows"]
    comps = payload["comparisons"]
    lines = [
        "# Operational Portfolio Rule Report",
        "",
        f"- status: `{payload['status']}`",
        f"- overall_decision: `{payload['summary']['overall_decision']}`",
        f"- exit_rule: `{payload['summary']['exit_rule']}`",
        f"- sector_rule: `{payload['summary']['sector_rule']}`",
        "",
        "## Production",
        "",
        f"- fixed20: return {pct(rows['production_fixed20'].get('total_return'))}, max DD {pct(rows['production_fixed20'].get('max_drawdown'))}",
        f"- fixed30: return {pct(rows['production_fixed30'].get('total_return'))}, max DD {pct(rows['production_fixed30'].get('max_drawdown'))}",
        f"- fixed40: return {pct(rows['production_fixed40'].get('total_return'))}, max DD {pct(rows['production_fixed40'].get('max_drawdown'))}",
        f"- trail25: return {pct(rows['production_trail25'].get('total_return'))}, max DD {pct(rows['production_trail25'].get('max_drawdown'))}, delta {pct(comps['production_trail25'].get('return_delta_vs_baseline'))}",
        f"- sl10/min5: return {pct(rows['production_sl10'].get('total_return'))}, max DD {pct(rows['production_sl10'].get('max_drawdown'))}, delta {pct(comps['production_sl10'].get('return_delta_vs_baseline'))}",
        f"- tp35/sl12/min5: return {pct(rows['production_tp35_sl12'].get('total_return'))}, max DD {pct(rows['production_tp35_sl12'].get('max_drawdown'))}, delta {pct(comps['production_tp35_sl12'].get('return_delta_vs_baseline'))}",
        f"- sector45: return {pct(rows['production_sector45'].get('total_return'))}, max DD {pct(rows['production_sector45'].get('max_drawdown'))}, delta {pct(comps['production_sector45'].get('return_delta_vs_baseline'))}",
        f"- sector35: return {pct(rows['production_sector35'].get('total_return'))}, max DD {pct(rows['production_sector35'].get('max_drawdown'))}, delta {pct(comps['production_sector35'].get('return_delta_vs_baseline'))}",
        f"- fixed40 rolling20 worst: {pct(rows['production_fixed40']['rolling_20d'].get('worst_return'))}",
        f"- sector45 rolling20 worst: {pct(rows['production_sector45']['rolling_20d'].get('worst_return'))}",
        f"- top3: return {pct(rows['production_top3'].get('total_return'))}, max DD {pct(rows['production_top3'].get('max_drawdown'))}, delta {pct(comps['production_top3'].get('return_delta_vs_baseline'))}",
        f"- top7: return {pct(rows['production_top7'].get('total_return'))}, max DD {pct(rows['production_top7'].get('max_drawdown'))}, delta {pct(comps['production_top7'].get('return_delta_vs_baseline'))}",
        "",
        "## Candidate",
        "",
        f"- fixed20: return {pct(rows['candidate_fixed20'].get('total_return'))}, max DD {pct(rows['candidate_fixed20'].get('max_drawdown'))}",
        f"- fixed30: return {pct(rows['candidate_fixed30'].get('total_return'))}, max DD {pct(rows['candidate_fixed30'].get('max_drawdown'))}",
        f"- fixed40: return {pct(rows['candidate_fixed40'].get('total_return'))}, max DD {pct(rows['candidate_fixed40'].get('max_drawdown'))}",
        f"- trail25: return {pct(rows['candidate_trail25'].get('total_return'))}, max DD {pct(rows['candidate_trail25'].get('max_drawdown'))}, delta {pct(comps['candidate_trail25'].get('return_delta_vs_baseline'))}",
        f"- sl10/min5: return {pct(rows['candidate_sl10'].get('total_return'))}, max DD {pct(rows['candidate_sl10'].get('max_drawdown'))}, delta {pct(comps['candidate_sl10'].get('return_delta_vs_baseline'))}",
        f"- tp35/sl12/min5: return {pct(rows['candidate_tp35_sl12'].get('total_return'))}, max DD {pct(rows['candidate_tp35_sl12'].get('max_drawdown'))}, delta {pct(comps['candidate_tp35_sl12'].get('return_delta_vs_baseline'))}",
        f"- sector45: return {pct(rows['candidate_sector45'].get('total_return'))}, max DD {pct(rows['candidate_sector45'].get('max_drawdown'))}, delta {pct(comps['candidate_sector45'].get('return_delta_vs_baseline'))}",
        f"- top3: return {pct(rows['candidate_top3'].get('total_return'))}, max DD {pct(rows['candidate_top3'].get('max_drawdown'))}, delta {pct(comps['candidate_top3'].get('return_delta_vs_baseline'))}",
        f"- top7: return {pct(rows['candidate_top7'].get('total_return'))}, max DD {pct(rows['candidate_top7'].get('max_drawdown'))}, delta {pct(comps['candidate_top7'].get('return_delta_vs_baseline'))}",
        "",
        "## Next Actions",
        "",
    ]
    lines.extend(f"- {item}" for item in payload["next_actions"])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = (
        resolve_path(args.output)
        if args.output
        else PROJECT_ROOT / "artifacts" / "model_experiments" / f"operational_portfolio_rule_report_{args.date}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output), **payload["summary"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
