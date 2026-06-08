#!/usr/bin/env python3
"""跨盤勢與 rolling 視角驗證營運規則候選。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_high_choppy_context_overlay import load_regime_frame, rolling_high_choppy  # noqa: E402
from scripts.build_operational_portfolio_rule_report import n, repo_path, resolve_path, rolling_stats  # noqa: E402
from scripts.research_regime_family_training_candidates import is_big_bull  # noqa: E402


SCHEMA_VERSION = "operational-rule-validation-report.v1"


VARIANTS = {
    "production_fixed40": "artifacts/backtest/portfolio_replay_production_fixed40_2026-06-02.json",
    "production_sector45": "artifacts/backtest/portfolio_replay_production_fixed40_sector45_2026-06-02.json",
    "production_gross55": "artifacts/backtest/portfolio_replay_production_fixed40_gross55_2026-06-02.json",
    "production_sector45_gross55": "artifacts/backtest/portfolio_replay_production_fixed40_sector45_gross55_2026-06-02.json",
    "production_dynamic_family_exposure": "artifacts/backtest/portfolio_replay_production_fixed40_dynamic_family_exposure_2026-06-02.json",
    "production_sector45_dynamic_family_exposure": "artifacts/backtest/portfolio_replay_production_fixed40_sector45_dynamic_family_exposure_2026-06-02.json",
    "production_top3": "artifacts/backtest/portfolio_replay_production_fixed40_top3_2026-06-02.json",
    "production_top3_sector45": "artifacts/backtest/portfolio_replay_production_fixed40_top3_sector45_2026-06-02.json",
    "candidate_fixed40": "artifacts/model_experiments/training_candidates/candidate_2026-06-02_config/portfolio_replay_candidate_fixed40_2026-06-02.json",
    "candidate_gross55": "artifacts/model_experiments/training_candidates/candidate_2026-06-02_config/portfolio_replay_candidate_fixed40_gross55_2026-06-02.json",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build operational rule validation report")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--market-regime-history", default="artifacts/market_regime_history_2026-06-01.json")
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def pct(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{n(value):.2%}"


def regime_map(path: Path) -> dict[str, dict[str, Any]]:
    frame = load_regime_frame(path)
    frame["BIG_BULL"] = frame.apply(is_big_bull, axis=1)
    frame["HIGH_CHOPPY_CONTEXT"] = frame.apply(rolling_high_choppy, axis=1)
    return {
        str(row.trade_date_text): {
            "base_regime": str(row.regime_label),
            "BIG_BULL": bool(row.BIG_BULL),
            "HIGH_CHOPPY_CONTEXT": bool(row.HIGH_CHOPPY_CONTEXT),
        }
        for row in frame.itertuples(index=False)
    }


def compound(values: list[float]) -> float:
    result = 1.0
    for value in values:
        result *= 1 + value
    return result - 1


def grouped_daily(daily: list[dict[str, Any]], regimes: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    buckets: dict[str, list[float]] = {"ALL": []}
    for row in daily:
        date_text = str(row.get("date") or "")
        daily_return = n(row.get("daily_return"))
        info = regimes.get(date_text) or {}
        labels = ["ALL", str(info.get("base_regime") or "UNKNOWN")]
        if info.get("BIG_BULL"):
            labels.append("BIG_BULL")
        if info.get("HIGH_CHOPPY_CONTEXT"):
            labels.append("HIGH_CHOPPY_CONTEXT")
        if not info.get("BIG_BULL") and not info.get("HIGH_CHOPPY_CONTEXT"):
            labels.append("OTHER_FAMILY")
        for label in labels:
            buckets.setdefault(label, []).append(daily_return)
    result: dict[str, dict[str, Any]] = {}
    for label, values in sorted(buckets.items()):
        if not values:
            continue
        result[label] = {
            "daily_count": len(values),
            "compound_return": round(compound(values), 6),
            "avg_daily_return": round(sum(values) / len(values), 6),
            "worst_daily_return": round(min(values), 6),
            "positive_day_rate": round(sum(value > 0 for value in values) / len(values), 6),
        }
    return result


def compact_variant(label: str, path_text: str, regimes: dict[str, dict[str, Any]]) -> dict[str, Any]:
    path = resolve_path(path_text)
    payload = read_json(path)
    summary = payload.get("summary") or {}
    daily = payload.get("daily") or []
    return {
        "label": label,
        "path": repo_path(path),
        "exists": bool(payload),
        "total_return": summary.get("total_return"),
        "max_drawdown": summary.get("max_drawdown"),
        "trade_count": summary.get("trade_count"),
        "win_rate": summary.get("win_rate"),
        "max_gross_exposure": summary.get("max_gross_exposure"),
        "max_group_exposure": summary.get("max_group_exposure"),
        "rolling_20d": rolling_stats(daily, 20),
        "rolling_40d": rolling_stats(daily, 40),
        "by_regime": grouped_daily(daily, regimes),
        "inputs": payload.get("inputs") or {},
    }


def delta(row: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    return {
        "return_delta": round(n(row.get("total_return")) - n(baseline.get("total_return")), 6),
        "drawdown_delta": round(n(row.get("max_drawdown")) - n(baseline.get("max_drawdown")), 6),
        "rolling20_worst_return_delta": round(
            n((row.get("rolling_20d") or {}).get("worst_return"))
            - n((baseline.get("rolling_20d") or {}).get("worst_return")),
            6,
        ),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    regimes = regime_map(resolve_path(args.market_regime_history))
    variants = {label: compact_variant(label, path, regimes) for label, path in VARIANTS.items()}
    baseline = variants["production_fixed40"]
    candidate_baseline = variants["candidate_fixed40"]
    comparisons = {
        "production_sector45": delta(variants["production_sector45"], baseline),
        "production_gross55": delta(variants["production_gross55"], baseline),
        "production_sector45_gross55": delta(variants["production_sector45_gross55"], baseline),
        "production_dynamic_family_exposure": delta(variants["production_dynamic_family_exposure"], baseline),
        "production_sector45_dynamic_family_exposure": delta(variants["production_sector45_dynamic_family_exposure"], baseline),
        "production_top3": delta(variants["production_top3"], baseline),
        "production_top3_sector45": delta(variants["production_top3_sector45"], baseline),
        "candidate_gross55": delta(variants["candidate_gross55"], candidate_baseline),
        "candidate_vs_production": delta(candidate_baseline, baseline),
    }
    sector45 = comparisons["production_sector45"]
    gross55 = comparisons["production_gross55"]
    top3 = comparisons["production_top3"]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK" if all(row["exists"] for row in variants.values()) else "MISSING_INPUT",
        "contract": {
            "research_only": True,
            "model_changes": False,
            "production_ranking_changes": False,
            "promotion_evidence": False,
        },
        "summary": {
            "overall_decision": "VALIDATE_PRODUCTION_RULES_CONTINUE_RESEARCH",
            "default_candidate": "production_fixed40_sector45_monitor",
            "conservative_candidate": "production_gross55_monitor_only",
            "aggressive_candidate": "production_top3_label_only",
            "dynamic_family_exposure": "rejected_for_now",
            "candidate_model_overlay": "rejected_for_now",
            "sector45_passes_tolerance": sector45["return_delta"] >= -0.02 and sector45["drawdown_delta"] >= -0.005,
            "gross55_is_default": gross55["return_delta"] >= -0.08,
            "top3_is_default": top3["drawdown_delta"] >= -0.02,
        },
        "variants": variants,
        "comparisons": comparisons,
        "next_actions": [
            "把 sector45 作為 production 風控 monitor，不直接改 ranking score。",
            "gross55 只作保守模式候選；需要更多弱勢/震盪區間證據，不能在牛市直接改預設。",
            "Top3 只作積極核心觀察標籤，不能縮短每日 Top10 名單。",
            "動態 family 曝險目前淘汰；降低 HIGH_CHOPPY/OTHER 曝險會砍報酬且未改善回撤。",
            "candidate model/overlay 目前不進 production，只保留 research-only。",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    variants = payload["variants"]
    comps = payload["comparisons"]
    lines = [
        "# Operational Rule Validation Report",
        "",
        f"- status: `{payload['status']}`",
        f"- overall_decision: `{payload['summary']['overall_decision']}`",
        f"- default_candidate: `{payload['summary']['default_candidate']}`",
        f"- conservative_candidate: `{payload['summary']['conservative_candidate']}`",
        f"- aggressive_candidate: `{payload['summary']['aggressive_candidate']}`",
        "",
        "## Core Comparison",
        "",
        f"- production fixed40: {pct(variants['production_fixed40'].get('total_return'))}, DD {pct(variants['production_fixed40'].get('max_drawdown'))}",
        f"- production sector45: {pct(variants['production_sector45'].get('total_return'))}, DD {pct(variants['production_sector45'].get('max_drawdown'))}, delta {pct(comps['production_sector45'].get('return_delta'))}",
        f"- production gross55: {pct(variants['production_gross55'].get('total_return'))}, DD {pct(variants['production_gross55'].get('max_drawdown'))}, delta {pct(comps['production_gross55'].get('return_delta'))}",
        f"- production dynamic family exposure: {pct(variants['production_dynamic_family_exposure'].get('total_return'))}, DD {pct(variants['production_dynamic_family_exposure'].get('max_drawdown'))}, delta {pct(comps['production_dynamic_family_exposure'].get('return_delta'))}",
        f"- production top3: {pct(variants['production_top3'].get('total_return'))}, DD {pct(variants['production_top3'].get('max_drawdown'))}, delta {pct(comps['production_top3'].get('return_delta'))}",
        f"- candidate fixed40: {pct(variants['candidate_fixed40'].get('total_return'))}, DD {pct(variants['candidate_fixed40'].get('max_drawdown'))}",
        "",
        "## Regime Snapshot",
        "",
    ]
    for label in ["production_fixed40", "production_sector45", "production_gross55", "production_top3"]:
        regime = variants[label].get("by_regime") or {}
        big_bull = regime.get("BIG_BULL") or {}
        high_choppy = regime.get("HIGH_CHOPPY_CONTEXT") or {}
        lines.append(
            f"- {label}: BIG_BULL {pct(big_bull.get('compound_return'))} ({big_bull.get('daily_count', 0)}d), "
            f"HIGH_CHOPPY_CONTEXT {pct(high_choppy.get('compound_return'))} ({high_choppy.get('daily_count', 0)}d)"
        )
    lines.extend(["", "## Next Actions", ""])
    lines.extend(f"- {item}" for item in payload["next_actions"])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = (
        resolve_path(args.output)
        if args.output
        else PROJECT_ROOT / "artifacts" / "model_experiments" / f"operational_rule_validation_report_{args.date}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output), **payload["summary"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
