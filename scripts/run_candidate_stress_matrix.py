#!/usr/bin/env python3
"""批量執行候選 ranking 的 portfolio stress test。

此腳本只呼叫既有 replay 腳本並彙整 artifact，不訓練模型、不改 production ranking。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "candidate-stress-matrix.v1"
MODEL_HASH = "76f530f6491f996f4838500acacbde40a10c90f43116cec0dcc69fb6b4935675"


@dataclass(frozen=True)
class Variant:
    name: str
    rankings_dir: str


@dataclass(frozen=True)
class Scenario:
    name: str
    top_n: int
    horizon: int
    entry_delay: int
    max_group_exposure: float
    take_profit_pct: float | None = None
    stop_loss_pct: float | None = None


VARIANTS = [
    Variant(
        "baseline",
        "artifacts/backtest/historical_rankings_current_model_half_year_dense_2025-11-17_2026-05-15",
    ),
    Variant(
        "feature_group_production_top7_shadow_fill3",
        "artifacts/backtest/shadow_rankings_batch01_feature_group_constrained_k7_half_year_dense",
    ),
    Variant(
        "sector_context_production_top7_shadow_fill3",
        "artifacts/backtest/shadow_rankings_batch01_sector_context_constrained_k7_half_year_dense",
    ),
    Variant(
        "feature_group_production_top9_shadow_fill1",
        "artifacts/backtest/shadow_rankings_batch01_feature_group_constrained_k9_half_year_dense",
    ),
    Variant(
        "sector_context_production_top9_shadow_fill1",
        "artifacts/backtest/shadow_rankings_batch01_sector_context_constrained_k9_half_year_dense",
    ),
]


SCENARIOS = [
    Scenario("top10_h10_d1_gc25", top_n=10, horizon=10, entry_delay=1, max_group_exposure=0.25),
    Scenario("top10_h10_d2_gc25", top_n=10, horizon=10, entry_delay=2, max_group_exposure=0.25),
    Scenario("top10_h7_d1_gc25", top_n=10, horizon=7, entry_delay=1, max_group_exposure=0.25),
    Scenario("top10_h7_d2_gc25", top_n=10, horizon=7, entry_delay=2, max_group_exposure=0.25),
    Scenario("top10_h5_d1_gc25", top_n=10, horizon=5, entry_delay=1, max_group_exposure=0.25),
    Scenario("top10_h5_d2_gc25", top_n=10, horizon=5, entry_delay=2, max_group_exposure=0.25),
    Scenario("top10_h5_d1_gc20", top_n=10, horizon=5, entry_delay=1, max_group_exposure=0.20),
    Scenario("top10_h5_d1_gc25_tp18", top_n=10, horizon=5, entry_delay=1, max_group_exposure=0.25, take_profit_pct=0.18),
    Scenario("top10_h5_d1_gc25_sl08", top_n=10, horizon=5, entry_delay=1, max_group_exposure=0.25, stop_loss_pct=0.08),
    Scenario("top5_h10_d1_gc25", top_n=5, horizon=10, entry_delay=1, max_group_exposure=0.25),
    Scenario("top10_h10_d1_gc20", top_n=10, horizon=10, entry_delay=1, max_group_exposure=0.20),
    Scenario("top10_h10_d1_gc25_tp18", top_n=10, horizon=10, entry_delay=1, max_group_exposure=0.25, take_profit_pct=0.18),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="run candidate portfolio stress matrix")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument("--output", default=None)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def run_portfolio(variant: Variant, scenario: Scenario, run_date: str, features: str, dry_run: bool) -> dict[str, Any]:
    output = PROJECT_ROOT / "artifacts" / "backtest" / (
        f"portfolio_stress_{variant.name}_{scenario.name}_{run_date}.json"
    )
    command = [
        sys.executable,
        "scripts/run_portfolio_replay.py",
        "--rankings-dir",
        variant.rankings_dir,
        "--features",
        features,
        "--top-n",
        str(scenario.top_n),
        "--horizon",
        str(scenario.horizon),
        "--entry-delay-trade-days",
        str(scenario.entry_delay),
        "--max-group-exposure",
        str(scenario.max_group_exposure),
        "--output",
        str(output),
    ]
    if scenario.take_profit_pct is not None:
        command.extend(["--take-profit-pct", str(scenario.take_profit_pct)])
    if scenario.stop_loss_pct is not None:
        command.extend(["--stop-loss-pct", str(scenario.stop_loss_pct)])

    if not dry_run:
        subprocess.run(command, cwd=PROJECT_ROOT, check=True)
    payload = json.loads(output.read_text(encoding="utf-8")) if output.exists() else {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    return {
        "variant": variant.name,
        "scenario": scenario.name,
        "output": repo_path(output),
        "command": command,
        "summary": summary,
    }


def decision_for(row: dict[str, Any], baseline: dict[str, Any]) -> str:
    summary = row.get("summary") if isinstance(row.get("summary"), dict) else {}
    base_summary = baseline.get("summary") if isinstance(baseline.get("summary"), dict) else {}
    ret = summary.get("total_return")
    dd = summary.get("max_drawdown")
    base_ret = base_summary.get("total_return")
    base_dd = base_summary.get("max_drawdown")
    if ret is None or dd is None or base_ret is None or base_dd is None:
        return "INSUFFICIENT_DATA"
    if abs(float(ret) - float(base_ret)) < 1e-9 and abs(float(dd) - float(base_dd)) < 1e-9:
        return "NO_EFFECT_BASELINE_EQUIVALENT"
    if float(ret) >= float(base_ret) and float(dd) >= float(base_dd):
        return "READY_FOR_SHADOW_MONITOR"
    if float(ret) >= float(base_ret):
        return "RETURN_ONLY_MONITOR"
    if float(dd) >= float(base_dd):
        return "RISK_REDUCED_MONITOR"
    return "REJECTED"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for scenario in SCENARIOS:
        for variant in VARIANTS:
            rows.append(run_portfolio(variant, scenario, args.date, args.features, args.dry_run))

    baselines = {
        row["scenario"]: row
        for row in rows
        if row.get("variant") == "baseline"
    }
    for row in rows:
        baseline = baselines.get(str(row.get("scenario")), {})
        row["decision"] = "BASELINE" if row.get("variant") == "baseline" else decision_for(row, baseline)
        summary = row.get("summary") if isinstance(row.get("summary"), dict) else {}
        base_summary = baseline.get("summary") if isinstance(baseline.get("summary"), dict) else {}
        row["delta_vs_baseline"] = {
            "total_return": (
                round(float(summary["total_return"]) - float(base_summary["total_return"]), 6)
                if summary.get("total_return") is not None and base_summary.get("total_return") is not None
                else None
            ),
            "max_drawdown": (
                round(float(summary["max_drawdown"]) - float(base_summary["max_drawdown"]), 6)
                if summary.get("max_drawdown") is not None and base_summary.get("max_drawdown") is not None
                else None
            ),
        }

    candidate_rows = [row for row in rows if row.get("variant") != "baseline"]
    ready = [row for row in candidate_rows if row.get("decision") == "READY_FOR_SHADOW_MONITOR"]
    return_only = [row for row in candidate_rows if row.get("decision") == "RETURN_ONLY_MONITOR"]
    risk_reduced = [row for row in candidate_rows if row.get("decision") == "RISK_REDUCED_MONITOR"]
    no_effect = [row for row in candidate_rows if row.get("decision") == "NO_EFFECT_BASELINE_EQUIVALENT"]
    best = sorted(
        candidate_rows,
        key=lambda row: (
            float((row.get("summary") or {}).get("total_return") or -999),
            float((row.get("summary") or {}).get("max_drawdown") or -999),
        ),
        reverse=True,
    )[:5]
    variant_summary: dict[str, dict[str, Any]] = {}
    for variant in [item.name for item in VARIANTS if item.name != "baseline"]:
        items = [row for row in candidate_rows if row.get("variant") == variant]
        meaningful = [row for row in items if row.get("decision") != "NO_EFFECT_BASELINE_EQUIVALENT"]
        ready_items = [row for row in items if row.get("decision") == "READY_FOR_SHADOW_MONITOR"]
        return_deltas = [
            float((row.get("delta_vs_baseline") or {}).get("total_return"))
            for row in meaningful
            if (row.get("delta_vs_baseline") or {}).get("total_return") is not None
        ]
        dd_deltas = [
            float((row.get("delta_vs_baseline") or {}).get("max_drawdown"))
            for row in meaningful
            if (row.get("delta_vs_baseline") or {}).get("max_drawdown") is not None
        ]
        variant_summary[variant] = {
            "scenario_count": len(items),
            "meaningful_scenario_count": len(meaningful),
            "ready_for_shadow_monitor": len(ready_items),
            "ready_ratio": round(len(ready_items) / len(meaningful), 6) if meaningful else None,
            "avg_total_return_delta": round(sum(return_deltas) / len(return_deltas), 6) if return_deltas else None,
            "avg_max_drawdown_delta": round(sum(dd_deltas) / len(dd_deltas), 6) if dd_deltas else None,
            "ready_scenarios": [str(row.get("scenario")) for row in ready_items],
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
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
            "features": args.features,
            "variants": [variant.__dict__ for variant in VARIANTS],
            "scenarios": [scenario.__dict__ for scenario in SCENARIOS],
        },
        "summary": {
            "scenario_count": len(SCENARIOS),
            "variant_count": len(VARIANTS),
            "candidate_rows": len(candidate_rows),
            "ready_for_shadow_monitor": len(ready),
            "return_only_monitor": len(return_only),
            "risk_reduced_monitor": len(risk_reduced),
            "no_effect_baseline_equivalent": len(no_effect),
            "best_candidate": best[0]["variant"] if best else None,
            "best_candidate_scenario": best[0]["scenario"] if best else None,
        },
        "variant_summary": variant_summary,
        "rows": rows,
        "best_rows": best,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Candidate Stress Matrix",
        "",
        f"- status：`OK`",
        f"- date：`{payload['date']}`",
        f"- scenario_count：`{payload['summary']['scenario_count']}`",
        f"- candidate_rows：`{payload['summary']['candidate_rows']}`",
        f"- ready_for_shadow_monitor：`{payload['summary']['ready_for_shadow_monitor']}`",
        f"- return_only_monitor：`{payload['summary']['return_only_monitor']}`",
        f"- risk_reduced_monitor：`{payload['summary']['risk_reduced_monitor']}`",
        f"- no_effect_baseline_equivalent：`{payload['summary']['no_effect_baseline_equivalent']}`",
        "",
        "## Variant Summary",
        "",
        "| Variant | Meaningful Scenarios | Ready | Ready Ratio | Avg Return Δ | Avg DD Δ |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for variant, row in payload.get("variant_summary", {}).items():
        lines.append(
            "| {variant} | {count} | {ready} | {ratio:.2%} | {ret} | {dd} |".format(
                variant=variant,
                count=row.get("meaningful_scenario_count"),
                ready=row.get("ready_for_shadow_monitor"),
                ratio=float(row.get("ready_ratio") or 0),
                ret="" if row.get("avg_total_return_delta") is None else f"{float(row['avg_total_return_delta']):.2%}",
                dd="" if row.get("avg_max_drawdown_delta") is None else f"{float(row['avg_max_drawdown_delta']):.2%}",
            )
        )
    lines.extend([
        "",
        "| Variant | Scenario | Return | Max DD | Return Δ | DD Δ | Decision |",
        "|---|---|---:|---:|---:|---:|---|",
    ])
    for row in payload["rows"]:
        summary = row.get("summary") or {}
        delta = row.get("delta_vs_baseline") or {}
        lines.append(
            "| {variant} | {scenario} | {ret:.2%} | {dd:.2%} | {dret} | {ddd} | {decision} |".format(
                variant=row.get("variant"),
                scenario=row.get("scenario"),
                ret=float(summary.get("total_return") or 0),
                dd=float(summary.get("max_drawdown") or 0),
                dret="" if delta.get("total_return") is None else f"{float(delta['total_return']):.2%}",
                ddd="" if delta.get("max_drawdown") is None else f"{float(delta['max_drawdown']):.2%}",
                decision=row.get("decision"),
            )
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = resolve_path(args.output) if args.output else PROJECT_ROOT / "artifacts" / "model_experiments" / f"candidate_stress_matrix_{args.date}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": "OK", "output": repo_path(output), **payload["summary"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
