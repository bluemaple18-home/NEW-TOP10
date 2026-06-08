#!/usr/bin/env python3
"""彙整有限本金防守 overlay 掃描。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "capital-defensive-overlay-report.v1"


RUNS = {
    "fixed65_long": "artifacts/backtest/capital_aware_replay_current_fixed40_fixed65_long_dense_2026-06-03.json",
    "fixed65_half": "artifacts/backtest/capital_aware_replay_current_fixed40_fixed65_half_year_2026-06-03.json",
    "full_regime_long": "artifacts/backtest/capital_aware_replay_current_fixed40_regime_long_dense_2026-06-03.json",
    "full_regime_half": "artifacts/backtest/capital_aware_replay_current_fixed40_regime_half_year_2026-06-03.json",
    "riskoff30_else65_long": "artifacts/backtest/capital_aware_replay_fixed40_riskoff30_else65_long_dense_2026-06-03.json",
    "riskoff30_else65_half": "artifacts/backtest/capital_aware_replay_fixed40_riskoff30_else65_half_year_2026-06-03.json",
    "riskoff40_else65_long": "artifacts/backtest/capital_aware_replay_fixed40_riskoff40_else65_long_dense_2026-06-03.json",
    "riskoff40_else65_half": "artifacts/backtest/capital_aware_replay_fixed40_riskoff40_else65_half_year_2026-06-03.json",
    "fixed60_long": "artifacts/backtest/capital_aware_replay_fixed40_fixed60_long_dense_2026-06-03.json",
    "fixed60_half": "artifacts/backtest/capital_aware_replay_fixed40_fixed60_half_year_2026-06-03.json",
    "fixed55_long": "artifacts/backtest/capital_aware_replay_fixed40_fixed55_long_dense_2026-06-03.json",
    "fixed55_half": "artifacts/backtest/capital_aware_replay_fixed40_fixed55_half_year_2026-06-03.json",
    "pos08_long": "artifacts/backtest/capital_aware_replay_fixed40_fixed65_pos08_long_dense_2026-06-03.json",
    "pos08_half": "artifacts/backtest/capital_aware_replay_fixed40_fixed65_pos08_half_year_2026-06-03.json",
    "group25_long": "artifacts/backtest/capital_aware_replay_fixed40_fixed65_group25_long_dense_2026-06-03.json",
    "group25_half": "artifacts/backtest/capital_aware_replay_fixed40_fixed65_group25_half_year_2026-06-03.json",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build capital defensive overlay report")
    parser.add_argument("--output", default="artifacts/model_experiments/capital_defensive_overlay_report_2026-06-03.json")
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
        "scenario": inputs.get("scenario"),
        "gross_policy": inputs.get("gross_policy"),
        "fixed_gross": inputs.get("fixed_gross"),
        "total_return": summary["total_return"],
        "max_drawdown": summary["max_drawdown"],
        "win_rate": summary.get("win_rate"),
        "trade_count": summary.get("trade_count"),
        "avg_gross_exposure": summary.get("avg_gross_exposure"),
        "min_cash_ratio": summary.get("min_cash_ratio"),
    }


def pair(rows: dict[str, dict[str, Any]], prefix: str) -> dict[str, Any]:
    return {"long": rows[f"{prefix}_long"], "half": rows[f"{prefix}_half"]}


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

    fixed65 = pair(rows, "fixed65")
    candidates = {
        "full_regime": pair(rows, "full_regime"),
        "riskoff30_else65": pair(rows, "riskoff30_else65"),
        "riskoff40_else65": pair(rows, "riskoff40_else65"),
        "fixed60": pair(rows, "fixed60"),
        "fixed55": pair(rows, "fixed55"),
        "pos08": pair(rows, "pos08"),
        "group25": pair(rows, "group25"),
    }
    comparisons: dict[str, Any] = {}
    for name, item in candidates.items():
        comparisons[name] = {
            "long": deltas(item["long"], fixed65["long"]),
            "half": deltas(item["half"], fixed65["half"]),
        }

    decision = {
        "default_rule": "fixed40_fixed65",
        "conservative_profile_candidate": "fixed60",
        "rejected_as_default": ["full_regime", "riskoff30_else65", "riskoff40_else65", "fixed55", "pos08", "group25"],
        "production_ready": False,
        "reason": "沒有任何 overlay 同時在長區間與近半年明顯優於 fixed65；fixed60 可作保守 profile shadow，但不能取代預設。",
        "next_step": "test_entry_quality_and_persistence_filters",
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK",
        "contract": {
            "research_only": True,
            "changes_model": False,
            "changes_ranking_score": False,
            "changes_production_push": False,
        },
        "runs": rows,
        "comparisons_vs_fixed65": comparisons,
        "decision": decision,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    rows = payload["runs"]
    comparisons = payload["comparisons_vs_fixed65"]
    lines = [
        "# Capital Defensive Overlay Report",
        "",
        f"- status: `{payload['status']}`",
        f"- production_ready: `{payload['decision']['production_ready']}`",
        f"- default_rule: `{payload['decision']['default_rule']}`",
        f"- conservative_profile_candidate: `{payload['decision']['conservative_profile_candidate']}`",
        "",
        "## Runs",
        "",
        "| name | return | max DD | win rate | avg gross | min cash |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name in sorted(rows):
        item = rows[name]
        lines.append(
            f"| {name} | {pct(item['total_return'])} | {pct(item['max_drawdown'])} | {pct(item['win_rate'])} | {pct(item['avg_gross_exposure'])} | {pct(item['min_cash_ratio'])} |"
        )
    lines.extend(["", "## Deltas Vs Fixed65", "", json.dumps(comparisons, ensure_ascii=False, indent=2), "", "## Decision", "", json.dumps(payload["decision"], ensure_ascii=False, indent=2), ""])
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
