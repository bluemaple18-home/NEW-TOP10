#!/usr/bin/env python3
"""VWAP regime-gated entry quality 診斷。

讀 `research_vwap_entry_quality_replay.py` 的 daily 結果，把單一 policy overlay
組合成「只在指定盤勢啟用」的候選方案。此腳本只做研究彙整，不訓練模型、不改 ranking。
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "vwap-regime-gated-entry-quality.v2"

GATED_PLANS: dict[str, dict[str, str]] = {
    "baseline": {},
    "nl_panic_balanced": {
        "NARROW_LEADER": "balanced_cost_basis",
        "PANIC_SELLING": "balanced_cost_basis",
    },
    "nl_panic_avoid5": {
        "NARROW_LEADER": "avoid_extended_vwap_5d",
        "PANIC_SELLING": "avoid_extended_vwap_5d",
    },
    "panic_only_balanced": {
        "PANIC_SELLING": "balanced_cost_basis",
    },
    "narrow_only_balanced": {
        "NARROW_LEADER": "balanced_cost_basis",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="research VWAP regime-gated entry quality from replay artifact")
    parser.add_argument("--replay", default="artifacts/model_experiments/vwap_entry_quality_replay_top50_2026-07-05.json")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--sealed-start", default="2026-02-06")
    parser.add_argument("--sealed-end", default="2026-05-15")
    parser.add_argument("--min-positive-horizons", type=int, default=3)
    parser.add_argument("--max-turnover-delta", type=float, default=0.02)
    parser.add_argument("--max-drawdown-worsen", type=float, default=0.01)
    parser.add_argument("--max-pre-sealed-worsen", type=float, default=0.0005)
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def resolve_path(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def split_bucket(value: str, sealed_start: str | None, sealed_end: str | None) -> str:
    if not sealed_start or not sealed_end:
        return "unknown"
    date_value = pd.to_datetime(value, errors="coerce")
    start = pd.to_datetime(sealed_start, errors="coerce")
    end = pd.to_datetime(sealed_end, errors="coerce")
    if pd.isna(date_value) or pd.isna(start) or pd.isna(end):
        return "unknown"
    if start <= date_value <= end:
        return "sealed"
    if date_value < start:
        return "pre_sealed"
    return "post_sealed"


def max_drawdown(returns: list[float]) -> float | None:
    if not returns:
        return None
    equity = 1.0
    peak = 1.0
    worst = 0.0
    for value in returns:
        equity *= 1 + value
        peak = max(peak, equity)
        worst = min(worst, equity / peak - 1)
    return round(worst, 6)


def turnover(stock_rows: list[list[str]]) -> float | None:
    previous: set[str] | None = None
    values = []
    for stock_ids in stock_rows:
        current = set(stock_ids)
        if previous is not None:
            values.append(1 - len(previous & current) / max(len(current), 1))
        previous = current
    return round(float(pd.Series(values).mean()), 6) if values else None


def bucket_for_plan(row: dict[str, Any], plan: str) -> dict[str, Any]:
    if plan == "baseline":
        return row["policies"]["baseline"]
    regime = str(row.get("market_regime") or "UNKNOWN")
    policy = GATED_PLANS[plan].get(regime, "baseline")
    return row["policies"][policy]


def summarize_plan(rows: list[dict[str, Any]], plan: str, horizon: int) -> dict[str, Any]:
    buckets = [bucket_for_plan(row, plan) for row in rows if int(row["horizon"]) == horizon]
    returns = [float(bucket["avg_net_return"]) for bucket in buckets if bucket.get("avg_net_return") is not None]
    hit_rates = [float(bucket["hit_rate"]) for bucket in buckets if bucket.get("hit_rate") is not None]
    maes = [float(bucket["avg_mae"]) for bucket in buckets if bucket.get("avg_mae") is not None]
    mfes = [float(bucket["avg_mfe"]) for bucket in buckets if bucket.get("avg_mfe") is not None]
    valid_counts = [int(bucket.get("valid_trade_count") or 0) for bucket in buckets]
    return {
        "date_count": len(returns),
        "avg_net_return": round(float(pd.Series(returns).mean()), 6) if returns else None,
        "hit_rate": round(float(pd.Series(hit_rates).mean()), 6) if hit_rates else None,
        "avg_mae": round(float(pd.Series(maes).mean()), 6) if maes else None,
        "avg_mfe": round(float(pd.Series(mfes).mean()), 6) if mfes else None,
        "max_drawdown": max_drawdown(returns),
        "turnover": turnover([bucket.get("stock_ids", []) for bucket in buckets]),
        "min_valid_trade_count": min(valid_counts) if valid_counts else 0,
    }


def summarize_rows(rows: list[dict[str, Any]], horizons: list[int]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for horizon in horizons:
        baseline = summarize_plan(rows, "baseline", horizon)
        variants = {}
        for plan in GATED_PLANS:
            summary = summarize_plan(rows, plan, horizon)
            return_delta = metric_delta(summary, baseline, "avg_net_return")
            drawdown_delta = metric_delta(summary, baseline, "max_drawdown")
            turnover_delta = metric_delta(summary, baseline, "turnover")
            variants[plan] = {
                **summary,
                "return_delta_vs_baseline": return_delta,
                "drawdown_delta_vs_baseline": drawdown_delta,
                "turnover_delta_vs_baseline": turnover_delta,
            }
        result[str(horizon)] = variants
    return result


def metric_delta(left: dict[str, Any], right: dict[str, Any], key: str) -> float | None:
    if left.get(key) is None or right.get(key) is None:
        return None
    return round(float(left[key]) - float(right[key]), 6)


def summarize_by_split(rows: list[dict[str, Any]], horizons: list[int]) -> dict[str, Any]:
    result = {}
    for split in sorted({str(row.get("split_bucket") or "unknown") for row in rows}):
        subset = [row for row in rows if str(row.get("split_bucket") or "unknown") == split]
        if subset:
            result[split] = {"row_count": len(subset), "summary": summarize_rows(subset, horizons)}
    return result


def summarize_by_regime(rows: list[dict[str, Any]], horizons: list[int]) -> dict[str, Any]:
    result = {}
    for regime in sorted({str(row.get("market_regime") or "UNKNOWN") for row in rows}):
        subset = [row for row in rows if str(row.get("market_regime") or "UNKNOWN") == regime]
        if subset:
            result[regime] = {"row_count": len(subset), "summary": summarize_rows(subset, horizons)}
    return result


def decide(summary: dict[str, Any], split_summary: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    rows = []
    for plan in GATED_PLANS:
        if plan == "baseline":
            continue
        horizon_metrics = [summary[horizon][plan] for horizon in sorted(summary, key=int)]
        positive = [item for item in horizon_metrics if (item.get("return_delta_vs_baseline") or 0) > 0]
        turnover_ok = all((item.get("turnover_delta_vs_baseline") or 0) <= args.max_turnover_delta for item in horizon_metrics)
        drawdown_ok = all((item.get("drawdown_delta_vs_baseline") or 0) >= -args.max_drawdown_worsen for item in horizon_metrics)
        sealed = split_summary.get("sealed", {}).get("summary", {})
        sealed_metrics = [sealed[horizon][plan] for horizon in sorted(sealed, key=int)] if sealed else []
        sealed_positive = [item for item in sealed_metrics if (item.get("return_delta_vs_baseline") or 0) > 0]
        pre_sealed = split_summary.get("pre_sealed", {}).get("summary", {})
        pre_sealed_metrics = [pre_sealed[horizon][plan] for horizon in sorted(pre_sealed, key=int)] if pre_sealed else []
        pre_sealed_deltas = [item.get("return_delta_vs_baseline") or 0 for item in pre_sealed_metrics]
        pre_sealed_min_delta = min(pre_sealed_deltas) if pre_sealed_deltas else None
        pre_sealed_non_worsening = pre_sealed_min_delta is None or pre_sealed_min_delta >= -args.max_pre_sealed_worsen
        rows.append(
            {
                "plan": plan,
                "positive_horizons": len(positive),
                "turnover_ok": turnover_ok,
                "drawdown_ok": drawdown_ok,
                "sealed_positive_horizons": len(sealed_positive),
                "pre_sealed_positive_horizons": sum(1 for value in pre_sealed_deltas if value > 0),
                "pre_sealed_min_delta": round(float(pre_sealed_min_delta), 6) if pre_sealed_min_delta is not None else None,
                "pre_sealed_non_worsening": pre_sealed_non_worsening,
                "avg_return_delta": round(
                    float(pd.Series([item.get("return_delta_vs_baseline") or 0 for item in horizon_metrics]).mean()),
                    6,
                ),
            }
        )
    rows = sorted(
        rows,
        key=lambda row: (
            row["positive_horizons"],
            row["sealed_positive_horizons"],
            row["pre_sealed_non_worsening"],
            row["turnover_ok"],
            row["drawdown_ok"],
            row["avg_return_delta"],
        ),
        reverse=True,
    )
    best = rows[0] if rows else {}
    candidate = bool(
        best
        and best["positive_horizons"] >= args.min_positive_horizons
        and best["turnover_ok"]
        and best["drawdown_ok"]
        and best["sealed_positive_horizons"] >= args.min_positive_horizons
        and best["pre_sealed_non_worsening"]
    )
    return {
        "status": "REGIME_GATED_ENTRY_CANDIDATE" if candidate else "MONITOR_ONLY",
        "best_plan": best,
        "ranked_plans": rows,
        "promotion_ready": False,
        "next_step": "run longer-window replay and production-style portfolio replay" if candidate else "do not promote; keep as monitored research signal",
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    replay_path = resolve_path(args.replay)
    assert replay_path is not None
    replay = json.loads(replay_path.read_text(encoding="utf-8"))
    rows = list(replay.get("daily") or [])
    if not rows:
        raise ValueError(f"replay artifact missing daily rows: {replay_path}")
    for row in rows:
        row["split_bucket"] = split_bucket(str(row.get("ranking_date")), args.sealed_start, args.sealed_end)
    horizons = sorted({int(row["horizon"]) for row in rows})
    summary = summarize_rows(rows, horizons)
    split_summary = summarize_by_split(rows, horizons)
    regime_summary = summarize_by_regime(rows, horizons)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "contract": {
            "research_only": True,
            "reads_replay_artifact": True,
            "does_not_train_model": True,
            "does_not_change_production_ranking": True,
            "production_ready": False,
        },
        "inputs": {
            "replay": repo_path(replay_path),
            "sealed_start": args.sealed_start,
            "sealed_end": args.sealed_end,
            "horizons": horizons,
            "gated_plans": GATED_PLANS,
            "gates": {
                "min_positive_horizons": args.min_positive_horizons,
                "max_turnover_delta": args.max_turnover_delta,
                "max_drawdown_worsen": args.max_drawdown_worsen,
                "max_pre_sealed_worsen": args.max_pre_sealed_worsen,
            },
        },
        "decision": decide(summary, split_summary, args),
        "summary": summary,
        "split_summary": split_summary,
        "regime_summary": regime_summary,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# VWAP Regime-Gated Entry Quality",
        "",
        f"- decision：`{payload['decision']['status']}`",
        f"- best_plan：`{payload['decision']['best_plan']}`",
        f"- next_step：`{payload['decision']['next_step']}`",
        "",
        "## Overall",
        "",
        "| Horizon | Plan | Return | Delta | Drawdown Delta | Turnover Delta | Hit |",
        "|---:|---|---:|---:|---:|---:|---:|",
    ]
    append_summary_table(lines, payload["summary"])
    lines.extend(["", "## Sealed Split", ""])
    for split, split_payload in payload["split_summary"].items():
        lines.extend([f"### {split}", "", "| Horizon | Plan | Return | Delta | Drawdown Delta | Turnover Delta | Hit |", "|---:|---|---:|---:|---:|---:|---:|"])
        append_summary_table(lines, split_payload["summary"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def append_summary_table(lines: list[str], summary: dict[str, Any]) -> None:
    for horizon, variants in summary.items():
        for plan, metrics in variants.items():
            lines.append(
                f"| {horizon} | {plan} | {fmt(metrics.get('avg_net_return'))} | "
                f"{fmt(metrics.get('return_delta_vs_baseline'))} | {fmt(metrics.get('drawdown_delta_vs_baseline'))} | "
                f"{fmt(metrics.get('turnover_delta_vs_baseline'))} | {fmt(metrics.get('hit_rate'))} |"
            )


def fmt(value: Any) -> str:
    if value is None:
        return "--"
    return f"{float(value):.4f}"


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = resolve_path(args.output) or PROJECT_ROOT / "artifacts" / "model_experiments" / f"vwap_regime_gated_entry_quality_{args.date}.json"
    assert output is not None
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": "OK", "output": repo_path(output), "decision": payload["decision"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
