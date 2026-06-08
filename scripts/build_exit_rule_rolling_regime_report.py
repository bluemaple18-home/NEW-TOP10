#!/usr/bin/env python3
"""整理出場規則 rolling / 盤勢切片報告。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_operational_portfolio_rule_report import n  # noqa: E402
from scripts.build_operational_rule_validation_report import regime_map, resolve_path  # noqa: E402


SCHEMA_VERSION = "exit-rule-rolling-regime-report.v1"

VARIANTS = {
    "h40_fixed65": "artifacts/backtest/portfolio_replay_half_year_dense_h40_fixed65_2026-06-02.json",
    "h40_tp15_fixed65": "artifacts/backtest/portfolio_replay_half_year_dense_h40_tp15_fixed65_2026-06-02.json",
    "h30_tp25_sl10_fixed65": "artifacts/backtest/portfolio_replay_half_year_dense_h30_tp25_sl10_fixed65_2026-06-02.json",
    "h40_tp15_gross55": "artifacts/backtest/portfolio_replay_half_year_dense_h40_tp15_gross55_2026-06-02.json",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build exit rule rolling regime report")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--market-regime-history", default="artifacts/market_regime_history_2026-06-01.json")
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_daily(path_text: str) -> list[dict[str, Any]]:
    return read_json(resolve_path(path_text)).get("daily") or []


def compound(rows: list[dict[str, Any]]) -> float:
    value = 1.0
    for row in rows:
        value *= 1 + n(row.get("daily_return"))
    return value - 1


def max_drawdown(rows: list[dict[str, Any]]) -> float:
    high = None
    worst = 0.0
    for row in rows:
        equity = n(row.get("equity"))
        if equity <= 0:
            continue
        high = equity if high is None else max(high, equity)
        worst = min(worst, equity / high - 1 if high else 0.0)
    return worst


def rolling_rows(rows: list[dict[str, Any]], window: int) -> list[dict[str, Any]]:
    ordered = sorted(rows, key=lambda row: str(row.get("date") or ""))
    result: list[dict[str, Any]] = []
    if len(ordered) < window:
        return result
    for index in range(0, len(ordered) - window + 1):
        sliced = ordered[index : index + window]
        result.append(
            {
                "start_date": sliced[0].get("date"),
                "end_date": sliced[-1].get("date"),
                "return": compound(sliced),
                "max_drawdown": max_drawdown(sliced),
            }
        )
    return result


def rolling_pair(baseline_rows: list[dict[str, Any]], candidate_rows: list[dict[str, Any]], window: int) -> dict[str, Any]:
    baseline = rolling_rows(baseline_rows, window)
    candidate = rolling_rows(candidate_rows, window)
    pairs = list(zip(baseline, candidate, strict=False))
    if not pairs:
        return {"window": window, "count": 0}
    return_deltas = [candidate_row["return"] - baseline_row["return"] for baseline_row, candidate_row in pairs]
    dd_deltas = [candidate_row["max_drawdown"] - baseline_row["max_drawdown"] for baseline_row, candidate_row in pairs]
    return {
        "window": window,
        "count": len(pairs),
        "avg_return_delta": round(sum(return_deltas) / len(return_deltas), 6),
        "worst_return_delta": round(min(return_deltas), 6),
        "best_return_delta": round(max(return_deltas), 6),
        "return_beats_rate": round(sum(item > 0 for item in return_deltas) / len(return_deltas), 6),
        "avg_drawdown_delta": round(sum(dd_deltas) / len(dd_deltas), 6),
        "drawdown_improves_rate": round(sum(item > 0 for item in dd_deltas) / len(dd_deltas), 6),
    }


def labels_for(date_text: str, regimes: dict[str, dict[str, Any]]) -> list[str]:
    info = regimes.get(date_text) or {}
    labels = ["ALL", str(info.get("base_regime") or "UNKNOWN")]
    if info.get("BIG_BULL"):
        labels.append("BIG_BULL")
    if info.get("HIGH_CHOPPY_CONTEXT"):
        labels.append("HIGH_CHOPPY_CONTEXT")
    if not info.get("BIG_BULL") and not info.get("HIGH_CHOPPY_CONTEXT"):
        labels.append("OTHER_FAMILY")
    return labels


def regime_slices(rows: list[dict[str, Any]], regimes: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        date_text = str(row.get("date") or "")
        for label in labels_for(date_text, regimes):
            buckets.setdefault(label, []).append(row)
    return {
        label: {
            "daily_count": len(items),
            "compound_return": round(compound(items), 6),
            "max_drawdown": round(max_drawdown(items), 6),
            "positive_day_rate": round(sum(n(row.get("daily_return")) > 0 for row in items) / len(items), 6) if items else None,
        }
        for label, items in sorted(buckets.items())
        if items
    }


def compact(label: str, path_text: str, regimes: dict[str, dict[str, Any]]) -> dict[str, Any]:
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
        "win_rate": summary.get("win_rate"),
        "trade_count": summary.get("trade_count"),
        "avg_gross_exposure": summary.get("avg_gross_exposure"),
        "by_regime": regime_slices(daily, regimes),
    }


def compare_regime(candidate: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    candidate_regimes = candidate.get("by_regime") or {}
    baseline_regimes = baseline.get("by_regime") or {}
    result = {}
    for label in sorted(set(candidate_regimes) | set(baseline_regimes)):
        cand = candidate_regimes.get(label) or {}
        base = baseline_regimes.get(label) or {}
        result[label] = {
            "daily_count": cand.get("daily_count") or base.get("daily_count"),
            "return_delta": round(n(cand.get("compound_return")) - n(base.get("compound_return")), 6),
            "drawdown_delta": round(n(cand.get("max_drawdown")) - n(base.get("max_drawdown")), 6),
            "positive_day_rate_delta": round(n(cand.get("positive_day_rate")) - n(base.get("positive_day_rate")), 6),
        }
    return result


def choose_contextual_rules(rows: dict[str, dict[str, Any]], regime_comparisons: dict[str, Any]) -> dict[str, Any]:
    baseline = rows["h40_fixed65"]
    tp15 = rows["h40_tp15_fixed65"]
    stop_take = rows["h30_tp25_sl10_fixed65"]
    tp15_regime = regime_comparisons["h40_tp15_fixed65"]
    stop_take_regime = regime_comparisons["h30_tp25_sl10_fixed65"]
    gross_tp15_regime = regime_comparisons["h40_tp15_gross55"]

    def candidate_score(candidate: str, regime_label: str) -> float:
        row = (regime_comparisons.get(candidate) or {}).get(regime_label) or {}
        # 情境路由不是 production 權重；這裡只用透明分數避免手動挑想看的結果。
        # 回撤改善很重要，但不能讓報酬犧牲完全失控。
        return n(row.get("return_delta")) + n(row.get("drawdown_delta")) * 4 + n(row.get("positive_day_rate_delta")) * 0.03

    def best_candidate(regime_label: str, candidates: list[str]) -> str:
        return max(candidates, key=lambda candidate: candidate_score(candidate, regime_label))

    high_choppy_pick = best_candidate(
        "HIGH_CHOPPY_CONTEXT",
        ["h40_tp15_fixed65", "h30_tp25_sl10_fixed65", "h40_tp15_gross55"],
    )
    risk_off_pick = best_candidate(
        "RISK_OFF",
        ["h40_tp15_fixed65", "h30_tp25_sl10_fixed65", "h40_tp15_gross55"],
    )
    return {
        "overall_default": "h40_fixed65",
        "overall_shadow": "h40_tp15_fixed65",
        "defensive_shadow": "h30_tp25_sl10_fixed65",
        "big_bull_preference": (
            "h40_fixed65"
            if n((tp15_regime.get("BIG_BULL") or {}).get("return_delta")) < -0.05
            else "h40_tp15_fixed65"
        ),
        "high_choppy_preference": high_choppy_pick,
        "risk_off_preference": risk_off_pick,
        "context_scores": {
            "HIGH_CHOPPY_CONTEXT": {
                "h40_tp15_fixed65": round(candidate_score("h40_tp15_fixed65", "HIGH_CHOPPY_CONTEXT"), 6),
                "h30_tp25_sl10_fixed65": round(candidate_score("h30_tp25_sl10_fixed65", "HIGH_CHOPPY_CONTEXT"), 6),
                "h40_tp15_gross55": round(candidate_score("h40_tp15_gross55", "HIGH_CHOPPY_CONTEXT"), 6),
            },
            "RISK_OFF": {
                "h40_tp15_fixed65": round(candidate_score("h40_tp15_fixed65", "RISK_OFF"), 6),
                "h30_tp25_sl10_fixed65": round(candidate_score("h30_tp25_sl10_fixed65", "RISK_OFF"), 6),
                "h40_tp15_gross55": round(candidate_score("h40_tp15_gross55", "RISK_OFF"), 6),
            },
        },
        "notes": [
            f"fixed65 total={n(baseline.get('total_return')):.2%}, dd={n(baseline.get('max_drawdown')):.2%}",
            f"tp15 total={n(tp15.get('total_return')):.2%}, dd={n(tp15.get('max_drawdown')):.2%}",
            f"stop_take total={n(stop_take.get('total_return')):.2%}, dd={n(stop_take.get('max_drawdown')):.2%}",
            f"gross_tp15 risk_off_dd_delta={n((gross_tp15_regime.get('RISK_OFF') or {}).get('drawdown_delta')):.2%}",
        ],
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    regimes = regime_map(resolve_path(args.market_regime_history))
    rows = {label: compact(label, path, regimes) for label, path in VARIANTS.items()}
    daily = {label: read_daily(path) for label, path in VARIANTS.items()}
    baseline = rows["h40_fixed65"]
    rolling = {
        label: {
            "20d": rolling_pair(daily["h40_fixed65"], daily[label], 20),
            "40d": rolling_pair(daily["h40_fixed65"], daily[label], 40),
        }
        for label in VARIANTS
        if label != "h40_fixed65"
    }
    regime_comparisons = {
        label: compare_regime(rows[label], baseline)
        for label in VARIANTS
        if label != "h40_fixed65"
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK" if all(row["exists"] for row in rows.values()) else "MISSING_INPUT",
        "contract": {
            "research_only": True,
            "rolling_and_regime_sliced": True,
            "does_not_train_model": True,
            "does_not_change_production_ranking": True,
            "does_not_change_risk_adjusted_score": True,
            "production_default_allowed": False,
        },
        "summary": {
            "decision": "EXIT_RULE_CONTEXTUAL_ROUTING_CANDIDATE",
            "next_gate": "WIRE_CONTEXTUAL_EXIT_RULES_TO_DAILY_SHADOW_MONITOR",
        },
        "contextual_rules": choose_contextual_rules(rows, regime_comparisons),
        "rows": rows,
        "rolling_vs_h40_fixed65": rolling,
        "regime_vs_h40_fixed65": regime_comparisons,
    }


def pct(value: Any) -> str:
    return f"{n(value):.2%}"


def render_markdown(payload: dict[str, Any]) -> str:
    rows = payload["rows"]
    rolling = payload["rolling_vs_h40_fixed65"]
    rules = payload["contextual_rules"]
    lines = [
        "# Exit Rule Rolling / Regime Report",
        "",
        f"- status: `{payload['status']}`",
        f"- decision: `{payload['summary']['decision']}`",
        f"- overall_default: `{rules['overall_default']}`",
        f"- overall_shadow: `{rules['overall_shadow']}`",
        f"- big_bull_preference: `{rules['big_bull_preference']}`",
        f"- high_choppy_preference: `{rules['high_choppy_preference']}`",
        f"- risk_off_preference: `{rules['risk_off_preference']}`",
        "",
        "## Overall",
        "",
        "| Variant | Return | DD | Win | 20D Ret Beat | 20D DD Improve | 40D Ret Beat | 40D DD Improve |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in VARIANTS:
        row = rows[label]
        roll = rolling.get(label) or {}
        lines.append(
            "| {label} | {ret} | {dd} | {win} | {r20} | {d20} | {r40} | {d40} |".format(
                label=label,
                ret=pct(row.get("total_return")),
                dd=pct(row.get("max_drawdown")),
                win=pct(row.get("win_rate")),
                r20=pct((roll.get("20d") or {}).get("return_beats_rate")) if roll else "--",
                d20=pct((roll.get("20d") or {}).get("drawdown_improves_rate")) if roll else "--",
                r40=pct((roll.get("40d") or {}).get("return_beats_rate")) if roll else "--",
                d40=pct((roll.get("40d") or {}).get("drawdown_improves_rate")) if roll else "--",
            )
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = (
        resolve_path(args.output)
        if args.output
        else PROJECT_ROOT / "artifacts" / "model_experiments" / f"exit_rule_rolling_regime_report_{args.date}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output), **payload["summary"]}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
