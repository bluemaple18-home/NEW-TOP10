#!/usr/bin/env python3
"""彙整有限本金長區間驗證。

用來確認 CAPITAL-01 的近半年 winner 是否只是吃到最近牛市。
這裡不做 production gate，只做研究結論與下一步收斂。
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "capital-long-validation-report.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build capital long validation report")
    parser.add_argument("--fixed65", default="artifacts/backtest/capital_aware_replay_current_fixed40_fixed65_long_dense_2026-06-03.json")
    parser.add_argument("--regime", default="artifacts/backtest/capital_aware_replay_current_fixed40_regime_long_dense_2026-06-03.json")
    parser.add_argument("--near-term-report", default="artifacts/model_experiments/capital_exit_rule_report_2026-06-03.json")
    parser.add_argument("--output", default="artifacts/model_experiments/capital_long_validation_report_2026-06-03.json")
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


def family(label: str) -> str:
    if label == "BIG_BULL":
        return "BIG_BULL"
    if label == "HIGH_CHOPPY_CONTEXT":
        return "HIGH_CHOPPY_CONTEXT"
    if label in {"RISK_OFF", "PANIC_SELLING"}:
        return "RISK_OFF"
    return "OTHER"


def compound(returns: list[float]) -> float:
    value = 1.0
    for item in returns:
        value *= 1.0 + item
    return value - 1.0


def segment_compare(fixed: dict[str, Any], regime: dict[str, Any]) -> list[dict[str, Any]]:
    fixed_by_date = {item["date"]: item for item in fixed.get("daily", [])}
    regime_by_date = {item["date"]: item for item in regime.get("daily", [])}
    buckets: dict[str, dict[str, list[float]]] = {}
    for date_text, regime_day in regime_by_date.items():
        fixed_day = fixed_by_date.get(date_text)
        if not fixed_day:
            continue
        bucket = family(str(regime_day.get("gross_label") or "OTHER"))
        target = buckets.setdefault(bucket, {"fixed": [], "regime": []})
        target["fixed"].append(float(fixed_day.get("daily_return") or 0.0))
        target["regime"].append(float(regime_day.get("daily_return") or 0.0))

    rows: list[dict[str, Any]] = []
    for bucket, values in sorted(buckets.items()):
        fixed_return = compound(values["fixed"])
        regime_return = compound(values["regime"])
        rows.append(
            {
                "family": bucket,
                "days": len(values["fixed"]),
                "fixed65_compound_return": round(fixed_return, 6),
                "regime_compound_return": round(regime_return, 6),
                "delta": round(regime_return - fixed_return, 6),
            }
        )
    return rows


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    fixed_path = resolve_path(args.fixed65)
    regime_path = resolve_path(args.regime)
    near_path = resolve_path(args.near_term_report)
    fixed = load_json(fixed_path)
    regime = load_json(regime_path)
    near = load_json(near_path)

    fixed_summary = fixed["summary"]
    regime_summary = regime["summary"]
    return_delta = float(regime_summary["total_return"]) - float(fixed_summary["total_return"])
    dd_abs_delta = abs(float(regime_summary["max_drawdown"])) - abs(float(fixed_summary["max_drawdown"]))
    production_allowed = return_delta >= -0.05 and dd_abs_delta <= -0.05
    decision = "LONG_VALIDATION_BLOCKS_PRODUCTION_CHANGE"
    if production_allowed:
        decision = "READY_FOR_ADDITIONAL_SHADOW_REVIEW"

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
        "inputs": {
            "fixed65": repo_path(fixed_path),
            "regime": repo_path(regime_path),
            "near_term_report": repo_path(near_path),
        },
        "near_term_winner": near.get("decisions", {}).get("winner"),
        "long_window": {
            "fixed65": fixed_summary,
            "regime": regime_summary,
            "return_delta": round(return_delta, 6),
            "drawdown_abs_delta": round(dd_abs_delta, 6),
        },
        "segments": segment_compare(fixed, regime),
        "decision": {
            "status": decision,
            "production_ready": False,
            "reason": "近半年 regime gross 表現最佳，但長區間報酬明顯低於 fixed65，回撤改善不足以支持直接升正式。",
            "allowed_next_step": "tune_regime_gross_or_keep_shadow_monitor",
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    long_window = payload["long_window"]
    fixed = long_window["fixed65"]
    regime = long_window["regime"]
    lines = [
        "# Capital Long Validation Report",
        "",
        f"- status: `{payload['status']}`",
        f"- decision: `{payload['decision']['status']}`",
        f"- production_ready: `{payload['decision']['production_ready']}`",
        "",
        "## Long Window",
        "",
        "| rule | return | max DD | win rate | trades |",
        "| --- | ---: | ---: | ---: | ---: |",
        f"| fixed40 + fixed65 | {pct(fixed['total_return'])} | {pct(fixed['max_drawdown'])} | {pct(fixed['win_rate'])} | {fixed['trade_count']} |",
        f"| fixed40 + regime gross | {pct(regime['total_return'])} | {pct(regime['max_drawdown'])} | {pct(regime['win_rate'])} | {regime['trade_count']} |",
        "",
        "## Regime Segments",
        "",
        "| family | days | fixed65 return | regime return | delta |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in payload.get("segments", []):
        lines.append(
            f"| {row['family']} | {row['days']} | {pct(row['fixed65_compound_return'])} | {pct(row['regime_compound_return'])} | {pct(row['delta'])} |"
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
