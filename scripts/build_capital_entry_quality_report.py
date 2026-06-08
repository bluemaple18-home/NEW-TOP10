#!/usr/bin/env python3
"""彙整有限本金入場品質 filter 實驗。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "capital-entry-quality-report.v1"


RUNS = {
    "baseline_half": "artifacts/backtest/capital_aware_replay_current_fixed40_fixed65_half_year_2026-06-03.json",
    "baseline_long": "artifacts/backtest/capital_aware_replay_current_fixed40_fixed65_long_dense_2026-06-03.json",
    "first_day_half": "artifacts/backtest/capital_aware_replay_fixed40_fixed65_first_day_half_year_2026-06-03.json",
    "first_day_long": "artifacts/backtest/capital_aware_replay_fixed40_fixed65_first_day_long_dense_2026-06-03.json",
    "streak2_half": "artifacts/backtest/capital_aware_replay_fixed40_fixed65_streak2_half_year_2026-06-03.json",
    "streak2_long": "artifacts/backtest/capital_aware_replay_fixed40_fixed65_streak2_long_dense_2026-06-03.json",
    "improved_or_new_half": "artifacts/backtest/capital_aware_replay_fixed40_fixed65_improved_or_new_half_year_2026-06-03.json",
    "improved_or_new_long": "artifacts/backtest/capital_aware_replay_fixed40_fixed65_improved_or_new_long_dense_2026-06-03.json",
    "non_worsening_half": "artifacts/backtest/capital_aware_replay_fixed40_fixed65_non_worsening_half_year_2026-06-03.json",
    "non_worsening_long": "artifacts/backtest/capital_aware_replay_fixed40_fixed65_non_worsening_long_dense_2026-06-03.json",
    "improved_only_half": "artifacts/backtest/capital_aware_replay_fixed40_fixed65_improved_only_half_year_2026-06-03.json",
    "improved_only_long": "artifacts/backtest/capital_aware_replay_fixed40_fixed65_improved_only_long_dense_2026-06-03.json",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build capital entry quality report")
    parser.add_argument("--output", default="artifacts/model_experiments/capital_entry_quality_report_2026-06-03.json")
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


def row(name: str, path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload["summary"]
    inputs = payload["inputs"]
    return {
        "name": name,
        "path": repo_path(path),
        "entry_filter": inputs.get("entry_filter", "all"),
        "total_return": summary["total_return"],
        "max_drawdown": summary["max_drawdown"],
        "win_rate": summary.get("win_rate"),
        "trade_count": summary.get("trade_count"),
        "avg_gross_exposure": summary.get("avg_gross_exposure"),
        "skipped_count": summary.get("skipped_count"),
        "skip_reason_counts": summary.get("skip_reason_counts", {}),
    }


def pair(rows: dict[str, dict[str, Any]], prefix: str) -> dict[str, Any]:
    return {"half": rows[f"{prefix}_half"], "long": rows[f"{prefix}_long"]}


def deltas(candidate: dict[str, Any], baseline: dict[str, Any]) -> dict[str, float]:
    return {
        "return_delta": round(float(candidate["total_return"]) - float(baseline["total_return"]), 6),
        "drawdown_abs_delta": round(abs(float(candidate["max_drawdown"])) - abs(float(baseline["max_drawdown"])), 6),
    }


def build_payload() -> dict[str, Any]:
    rows: dict[str, dict[str, Any]] = {}
    for name, value in RUNS.items():
        path = resolve_path(value)
        rows[name] = row(name, path, load_json(path))

    baseline = pair(rows, "baseline")
    candidates = {
        "first_day": pair(rows, "first_day"),
        "streak2": pair(rows, "streak2"),
        "improved_or_new": pair(rows, "improved_or_new"),
        "non_worsening": pair(rows, "non_worsening"),
        "improved_only": pair(rows, "improved_only"),
    }
    comparisons = {
        name: {
            "half": deltas(item["half"], baseline["half"]),
            "long": deltas(item["long"], baseline["long"]),
        }
        for name, item in candidates.items()
    }
    decision = {
        "default_rule": "fixed40_fixed65_all_entries",
        "balanced_shadow_candidate": "non_worsening",
        "conservative_shadow_candidate": "improved_only",
        "bull_market_diagnostic_only": "first_day",
        "rejected_as_default": ["first_day", "streak2", "improved_or_new", "improved_only"],
        "production_ready": False,
        "reason": "first_day 近半年強但長區間失效；non_worsening 長短期最平衡；improved_only 可大幅降長區間回撤但報酬犧牲太多，只能作保守 shadow。",
        "next_step": "daily_shadow_monitor_non_worsening_and_improved_only",
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK",
        "contract": {
            "research_only": True,
            "uses_future_rankings_for_filters": False,
            "changes_model": False,
            "changes_ranking_score": False,
            "changes_production_push": False,
        },
        "runs": rows,
        "comparisons_vs_baseline": comparisons,
        "decision": decision,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    rows = payload["runs"]
    lines = [
        "# Capital Entry Quality Report",
        "",
        f"- status: `{payload['status']}`",
        f"- production_ready: `{payload['decision']['production_ready']}`",
        f"- balanced_shadow_candidate: `{payload['decision']['balanced_shadow_candidate']}`",
        f"- conservative_shadow_candidate: `{payload['decision']['conservative_shadow_candidate']}`",
        "",
        "## Runs",
        "",
        "| name | filter | return | max DD | win rate | trades | avg gross |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name in sorted(rows):
        item = rows[name]
        lines.append(
            f"| {name} | {item['entry_filter']} | {pct(item['total_return'])} | {pct(item['max_drawdown'])} | {pct(item['win_rate'])} | {item['trade_count']} | {pct(item['avg_gross_exposure'])} |"
        )
    lines.extend(["", "## Deltas Vs Baseline", "", json.dumps(payload["comparisons_vs_baseline"], ensure_ascii=False, indent=2), "", "## Decision", "", json.dumps(payload["decision"], ensure_ascii=False, indent=2), ""])
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload()
    output = resolve_path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output), "decision": payload["decision"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
