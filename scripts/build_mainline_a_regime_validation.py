#!/usr/bin/env python3
"""主線 A：production_top7_shadow_fill3 的盤勢分層驗證。

只讀既有 replay / stress artifacts 與 market regime，不訓練模型、不改正式 ranking。
"""

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

from scripts.build_high_choppy_context_overlay import (  # noqa: E402
    load_regime_frame,
    rolling_high_choppy,
    strict_high_choppy,
)
from scripts.research_regime_family_training_candidates import is_big_bull  # noqa: E402


SCHEMA_VERSION = "mainline-a-regime-validation.v1"
MODEL_HASH = "76f530f6491f996f4838500acacbde40a10c90f43116cec0dcc69fb6b4935675"


SCENARIOS = [
    ("top10_h5_d1_gc25", "5D D+1 group-cap 25%"),
    ("top10_h7_d1_gc25", "7D D+1 group-cap 25%"),
    ("top10_h10_d1_gc25_tp18", "10D D+1 TP18 group-cap 25%"),
]

VARIANTS = [
    "baseline",
    "feature_group_production_top7_shadow_fill3",
    "sector_context_production_top7_shadow_fill3",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build mainline A regime validation")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--market-regime-history", default="artifacts/market_regime_history_2026-06-01.json")
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


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def artifact_path(variant: str, scenario: str, run_date: str) -> Path:
    return PROJECT_ROOT / "artifacts" / "backtest" / f"portfolio_stress_{variant}_{scenario}_{run_date}.json"


def build_regime_map(path: Path) -> dict[str, dict[str, Any]]:
    frame = load_regime_frame(path)
    frame["BIG_BULL"] = frame.apply(is_big_bull, axis=1)
    frame["HIGH_CHOPPY_STRICT"] = frame.apply(strict_high_choppy, axis=1)
    frame["HIGH_CHOPPY_CONTEXT"] = frame.apply(rolling_high_choppy, axis=1)
    return {
        str(row.trade_date_text): {
            "base_regime": str(row.regime_label),
            "BIG_BULL": bool(row.BIG_BULL),
            "HIGH_CHOPPY_STRICT": bool(row.HIGH_CHOPPY_STRICT),
            "HIGH_CHOPPY_CONTEXT": bool(row.HIGH_CHOPPY_CONTEXT),
        }
        for row in frame.itertuples(index=False)
    }


def compounded_return(values: list[float]) -> float | None:
    if not values:
        return None
    equity = 1.0
    for value in values:
        equity *= 1.0 + float(value)
    return round(equity - 1.0, 6)


def max_drawdown(values: list[float]) -> float | None:
    if not values:
        return None
    equity = 1.0
    peak = 1.0
    worst = 0.0
    for value in values:
        equity *= 1.0 + float(value)
        peak = max(peak, equity)
        if peak > 0:
            worst = min(worst, equity / peak - 1.0)
    return round(worst, 6)


def daily_by_regime(payload: dict[str, Any], regime_map: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    groups = {
        "ALL": [],
        "BIG_BULL": [],
        "HIGH_CHOPPY_CONTEXT": [],
        "BIG_BULL_AND_HIGH_CHOPPY_CONTEXT": [],
        "OTHER": [],
    }
    for row in payload.get("daily", []) if isinstance(payload.get("daily"), list) else []:
        date_text = str(row.get("date"))
        daily_return = row.get("daily_return")
        if daily_return is None:
            continue
        info = regime_map.get(date_text, {})
        is_big = bool(info.get("BIG_BULL"))
        is_high = bool(info.get("HIGH_CHOPPY_CONTEXT"))
        groups["ALL"].append(float(daily_return))
        if is_big:
            groups["BIG_BULL"].append(float(daily_return))
        if is_high:
            groups["HIGH_CHOPPY_CONTEXT"].append(float(daily_return))
        if is_big and is_high:
            groups["BIG_BULL_AND_HIGH_CHOPPY_CONTEXT"].append(float(daily_return))
        if not is_big and not is_high:
            groups["OTHER"].append(float(daily_return))
    result = {}
    for name, values in groups.items():
        result[name] = {
            "daily_count": len(values),
            "avg_daily_return": round(sum(values) / len(values), 6) if values else None,
            "total_return": compounded_return(values),
            "max_drawdown": max_drawdown(values),
            "positive_day_rate": round(sum(1 for value in values if value > 0) / len(values), 6) if values else None,
        }
    return result


def compare(candidate: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    rows = {}
    for regime, metrics in candidate.items():
        base = baseline.get(regime, {})
        ret = metrics.get("total_return")
        base_ret = base.get("total_return")
        dd = metrics.get("max_drawdown")
        base_dd = base.get("max_drawdown")
        rows[regime] = {
            "candidate": metrics,
            "baseline": base,
            "delta_total_return": round(float(ret) - float(base_ret), 6) if ret is not None and base_ret is not None else None,
            "delta_max_drawdown": round(float(dd) - float(base_dd), 6) if dd is not None and base_dd is not None else None,
            "decision": decision(metrics, base),
        }
    return rows


def decision(metrics: dict[str, Any], baseline: dict[str, Any]) -> str:
    if metrics.get("daily_count", 0) < 5:
        return "INSUFFICIENT_DAYS"
    ret = metrics.get("total_return")
    base_ret = baseline.get("total_return")
    dd = metrics.get("max_drawdown")
    base_dd = baseline.get("max_drawdown")
    if ret is None or base_ret is None or dd is None or base_dd is None:
        return "INSUFFICIENT_DATA"
    if float(ret) > float(base_ret) and float(dd) >= float(base_dd):
        return "READY_FOR_FORWARD_SHADOW"
    if float(ret) > float(base_ret):
        return "RETURN_ONLY_MONITOR"
    if float(dd) >= float(base_dd):
        return "RISK_REDUCED_MONITOR"
    return "REJECTED"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    regime_path = resolve_path(args.market_regime_history)
    regime_map = build_regime_map(regime_path)
    scenario_results: dict[str, Any] = {}
    for scenario, label in SCENARIOS:
        per_variant: dict[str, Any] = {}
        for variant in VARIANTS:
            path = artifact_path(variant, scenario, args.date)
            if not path.exists():
                per_variant[variant] = {"status": "MISSING", "path": repo_path(path)}
                continue
            payload = load_json(path)
            per_variant[variant] = {
                "status": "OK",
                "path": repo_path(path),
                "summary": payload.get("summary", {}),
                "by_regime_context": daily_by_regime(payload, regime_map),
            }
        baseline = per_variant.get("baseline", {}).get("by_regime_context", {})
        comparisons = {
            variant: compare(item.get("by_regime_context", {}), baseline)
            for variant, item in per_variant.items()
            if variant != "baseline" and item.get("status") == "OK"
        }
        scenario_results[scenario] = {
            "label": label,
            "variants": per_variant,
            "comparisons": comparisons,
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK",
        "contract": {
            "research_only": True,
            "does_not_train_model": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_production_ranking": True,
            "does_not_change_risk_adjusted_score": True,
            "production_promotion_allowed": False,
            "model_hash_before": MODEL_HASH,
        },
        "inputs": {
            "market_regime_history": repo_path(regime_path),
            "scenarios": [{"id": item[0], "label": item[1]} for item in SCENARIOS],
            "variants": VARIANTS,
        },
        "summary": summarize(scenario_results),
        "scenarios": scenario_results,
    }


def summarize(scenarios: dict[str, Any]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    ready_rows = []
    for scenario, payload in scenarios.items():
        for variant, comparisons in payload.get("comparisons", {}).items():
            for regime, row in comparisons.items():
                decision_value = str(row.get("decision"))
                counts[decision_value] = counts.get(decision_value, 0) + 1
                if decision_value == "READY_FOR_FORWARD_SHADOW":
                    ready_rows.append({"scenario": scenario, "variant": variant, "regime_context": regime})
    return {
        "decision_counts": counts,
        "ready_count": len(ready_rows),
        "ready_rows": ready_rows,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Mainline A Regime Validation",
        "",
        f"- status：`{payload['status']}`",
        f"- production_promotion_allowed：`{payload['contract']['production_promotion_allowed']}`",
        f"- ready_count：`{payload['summary']['ready_count']}`",
        f"- decision_counts：`{payload['summary']['decision_counts']}`",
        "",
    ]
    for scenario, scenario_payload in payload.get("scenarios", {}).items():
        lines.extend([f"## {scenario}", "", "| Variant | Regime Context | Days | Return Δ | DD Δ | Decision |", "|---|---|---:|---:|---:|---|"])
        for variant, comparisons in scenario_payload.get("comparisons", {}).items():
            for regime, row in comparisons.items():
                candidate = row.get("candidate", {})
                lines.append(
                    "| {variant} | {regime} | {days} | {ret} | {dd} | {decision} |".format(
                        variant=variant,
                        regime=regime,
                        days=candidate.get("daily_count"),
                        ret="" if row.get("delta_total_return") is None else f"{float(row['delta_total_return']):.2%}",
                        dd="" if row.get("delta_max_drawdown") is None else f"{float(row['delta_max_drawdown']):.2%}",
                        decision=row.get("decision"),
                    )
                )
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = resolve_path(args.output) if args.output else PROJECT_ROOT / "artifacts" / "model_experiments" / f"mainline_a_regime_validation_{args.date}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": "OK", "output": repo_path(output), **payload["summary"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
