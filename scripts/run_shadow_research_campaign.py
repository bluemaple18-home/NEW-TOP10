#!/usr/bin/env python3
"""以具名 stage 執行 shadow research campaign。

本入口只編排既有 research-only 工具，不訓練模型、不修改 production
ranking，也不允許任何 stage 自動晉升 production。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN_SCHEMA_VERSION = "shadow-research-campaign.v1"
A1_SCHEMA_VERSION = "a1-forward-shadow-monitor.v1"
STRESS_SCHEMA_VERSION = "candidate-stress-matrix.v1"
TRAINING_SCHEMA_VERSION = "overnight-shadow-training-runner.v1"
RISK_SCHEMA_VERSION = "overnight-risk-matrix-summary.v1"
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
    Variant("baseline", "artifacts/backtest/historical_rankings_current_model_half_year_dense_2025-11-17_2026-05-15"),
    Variant("feature_group_production_top7_shadow_fill3", "artifacts/backtest/shadow_rankings_batch01_feature_group_constrained_k7_half_year_dense"),
    Variant("sector_context_production_top7_shadow_fill3", "artifacts/backtest/shadow_rankings_batch01_sector_context_constrained_k7_half_year_dense"),
    Variant("feature_group_production_top9_shadow_fill1", "artifacts/backtest/shadow_rankings_batch01_feature_group_constrained_k9_half_year_dense"),
    Variant("sector_context_production_top9_shadow_fill1", "artifacts/backtest/shadow_rankings_batch01_sector_context_constrained_k9_half_year_dense"),
]

SCENARIOS = [
    Scenario("top10_h10_d1_gc25", 10, 10, 1, 0.25),
    Scenario("top10_h10_d2_gc25", 10, 10, 2, 0.25),
    Scenario("top10_h7_d1_gc25", 10, 7, 1, 0.25),
    Scenario("top10_h7_d2_gc25", 10, 7, 2, 0.25),
    Scenario("top10_h5_d1_gc25", 10, 5, 1, 0.25),
    Scenario("top10_h5_d2_gc25", 10, 5, 2, 0.25),
    Scenario("top10_h5_d1_gc20", 10, 5, 1, 0.20),
    Scenario("top10_h5_d1_gc25_tp18", 10, 5, 1, 0.25, take_profit_pct=0.18),
    Scenario("top10_h5_d1_gc25_sl08", 10, 5, 1, 0.25, stop_loss_pct=0.08),
    Scenario("top5_h10_d1_gc25", 5, 10, 1, 0.25),
    Scenario("top10_h10_d1_gc20", 10, 10, 1, 0.20),
    Scenario("top10_h10_d1_gc25_tp18", 10, 10, 1, 0.25, take_profit_pct=0.18),
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def read_json(path: str | Path) -> dict[str, Any]:
    resolved = resolve_path(path)
    if not resolved.exists():
        return {}
    return json.loads(resolved.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def add_common_stage_args(parser: argparse.ArgumentParser, *, date_required: bool) -> None:
    parser.add_argument("--date", required=date_required, default=None if date_required else date.today().isoformat())


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="run shadow research campaign")
    parser.add_argument("--dry-run", dest="campaign_dry_run", action="store_true")
    parser.add_argument("--output", dest="campaign_output", default=None, help="top-level campaign manifest")
    stages = parser.add_subparsers(dest="stage", required=True)

    a1 = stages.add_parser("a1-forward")
    add_common_stage_args(a1, date_required=False)
    a1.add_argument("--production-dir", default="artifacts")
    a1.add_argument("--features", default="data/clean/features.parquet")
    a1.add_argument("--market-regime-history", default="artifacts/market_regime_history_2026-06-01.json")
    a1.add_argument("--industry-map", default="data/reference/stock_industry_map.csv")
    a1.add_argument("--output", dest="stage_output", default=None)
    a1.add_argument("--reuse-existing", action="store_true", help="只重建 monitor summary，不重跑四個子步驟")

    stress = stages.add_parser("candidate-stress")
    add_common_stage_args(stress, date_required=False)
    stress.add_argument("--features", default="data/clean/features.parquet")
    stress.add_argument("--output", dest="stage_output", default=None)
    stress.add_argument("--dry-run", dest="stage_dry_run", action="store_true")

    training = stages.add_parser("overnight-training")
    add_common_stage_args(training, date_required=True)
    training.add_argument("--label", default="extended")
    training.add_argument("--dates-from-dir", default="artifacts/backtest/historical_rankings_current_model_extended")
    training.add_argument("--market-regime-history", default="artifacts/market_regime_history_2026-06-01.json")
    training.add_argument("--features", default="data/clean/features.parquet")
    training.add_argument("--model-hash-before", required=True)
    training.add_argument("--keeps", default="6,7,8")
    training.add_argument("--output", dest="stage_output", default=None)
    training.add_argument("--steps-log", default=None)

    risk = stages.add_parser("risk-matrix-summary")
    add_common_stage_args(risk, date_required=True)
    risk.add_argument("--label", default="half_year_dense")
    risk.add_argument("--model", default="models/latest_lgbm.pkl")
    risk.add_argument("--model-hash-before", required=True)
    risk.add_argument("--output", dest="stage_output", default=None)
    return parser.parse_args(argv)


def a1_paths(args: argparse.Namespace) -> dict[str, Path]:
    shadow_dir = PROJECT_ROOT / "artifacts" / "backtest" / f"shadow_rankings_a1_sector_context_forward_{args.date}"
    constrained_dir = PROJECT_ROOT / "artifacts" / "backtest" / f"shadow_rankings_a1_sector_context_production_top7_shadow_fill3_forward_{args.date}"
    return {
        "shadow_ranking_dir": shadow_dir,
        "shadow_ranking_summary": shadow_dir / "regime_shadow_ranking.json",
        "constrained_dir": constrained_dir,
        "constrained_summary": constrained_dir / "constrained_shadow_ranking.json",
        "baseline_replay": PROJECT_ROOT / "artifacts" / "backtest" / f"portfolio_a1_baseline_forward_top10_h5_d1_gc25_{args.date}.json",
        "candidate_replay": PROJECT_ROOT / "artifacts" / "backtest" / f"portfolio_a1_sector_context_production_top7_shadow_fill3_forward_top10_h5_d1_gc25_{args.date}.json",
    }


def a1_command_plan(args: argparse.Namespace) -> list[tuple[str, list[str]]]:
    paths = a1_paths(args)
    if args.reuse_existing:
        return []
    return [
        (
            "shadow_ranking",
            [
                sys.executable,
                "scripts/research_regime_shadow_ranking.py",
                "--dates-from-dir",
                args.production_dir,
                "--output-dir",
                repo_path(paths["shadow_ranking_dir"]),
                "--market-regime-history",
                args.market_regime_history,
                "--industry-map",
                args.industry_map,
                "--risk-profile",
                "shadow_regime_guard_balanced",
                "--top-n",
                "10",
                "--max-sector-count",
                "4",
                "--sector-cap-column",
                "industry_name",
            ],
        ),
        (
            "constrained_ranking",
            [
                sys.executable,
                "scripts/build_constrained_shadow_rankings.py",
                "--production-dir",
                args.production_dir,
                "--shadow-dir",
                repo_path(paths["shadow_ranking_dir"]),
                "--output-dir",
                repo_path(paths["constrained_dir"]),
                "--top-n",
                "10",
                "--min-production-count",
                "7",
            ],
        ),
        (
            "baseline_replay",
            [
                sys.executable,
                "scripts/run_portfolio_replay.py",
                "--rankings-dir",
                args.production_dir,
                "--features",
                args.features,
                "--top-n",
                "10",
                "--horizon",
                "5",
                "--entry-delay-trade-days",
                "1",
                "--max-group-exposure",
                "0.25",
                "--output",
                repo_path(paths["baseline_replay"]),
            ],
        ),
        (
            "candidate_replay",
            [
                sys.executable,
                "scripts/run_portfolio_replay.py",
                "--rankings-dir",
                repo_path(paths["constrained_dir"]),
                "--features",
                args.features,
                "--top-n",
                "10",
                "--horizon",
                "5",
                "--entry-delay-trade-days",
                "1",
                "--max-group-exposure",
                "0.25",
                "--output",
                repo_path(paths["candidate_replay"]),
            ],
        ),
    ]


def run_a1_step(name: str, command: list[str]) -> dict[str, Any]:
    started_at = now_utc()
    proc = subprocess.run(command, cwd=PROJECT_ROOT, text=True, capture_output=True)
    return {
        "name": name,
        "status": "OK" if proc.returncode == 0 else "FAILED",
        "returncode": proc.returncode,
        "started_at": started_at,
        "finished_at": now_utc(),
        "command": command,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-4000:],
    }


def build_a1_payload(args: argparse.Namespace, steps: list[dict[str, Any]]) -> dict[str, Any]:
    paths = a1_paths(args)
    shadow_summary = read_json(paths["shadow_ranking_summary"])
    constrained_summary = read_json(paths["constrained_summary"])
    baseline = read_json(paths["baseline_replay"])
    candidate = read_json(paths["candidate_replay"])
    baseline_summary = baseline.get("summary") if isinstance(baseline.get("summary"), dict) else {}
    candidate_summary = candidate.get("summary") if isinstance(candidate.get("summary"), dict) else {}
    candidate_skipped = candidate.get("skipped") if isinstance(candidate.get("skipped"), list) else []
    trade_count = int(candidate_summary.get("trade_count") or 0)
    return {
        "schema_version": A1_SCHEMA_VERSION,
        "generated_at": now_utc(),
        "date": args.date,
        "status": "OK" if all(step["status"] == "OK" for step in steps) else "FAILED",
        "monitor_status": "READY_WITH_MATURE_OUTCOMES" if trade_count > 0 else "PENDING_OUTCOMES",
        "contract": {
            "research_only": True,
            "does_not_train_model": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_production_ranking": True,
            "does_not_change_risk_adjusted_score": True,
            "production_promotion_allowed": False,
            "model_hash_before": MODEL_HASH,
        },
        "lane": {
            "id": "A1",
            "candidate": "sector_context_production_top7_shadow_fill3",
            "scenario": "top10_h5_d1_gc25",
            "entry": "D+1 open",
            "horizon_trade_days": 5,
            "group_cap": 0.25,
            "min_production_count": 7,
            "top_n": 10,
        },
        "inputs": {
            "production_dir": args.production_dir,
            "features": args.features,
            "market_regime_history": args.market_regime_history,
            "industry_map": args.industry_map,
        },
        "artifacts": {key: repo_path(path) for key, path in paths.items()},
        "summary": {
            "shadow_ranking_count": len(shadow_summary.get("outputs") or []),
            "shadow_input_date_count": (shadow_summary.get("inputs") or {}).get("date_count"),
            "constrained_date_count": (constrained_summary.get("summary") or {}).get("date_count"),
            "constrained_avg_overlap_count": (constrained_summary.get("summary") or {}).get("avg_overlap_count"),
            "baseline_trade_count": baseline_summary.get("trade_count"),
            "candidate_trade_count": candidate_summary.get("trade_count"),
            "candidate_skipped_count": candidate_summary.get("skipped_count"),
            "candidate_total_return": candidate_summary.get("total_return"),
            "candidate_max_drawdown": candidate_summary.get("max_drawdown"),
            "pending_reasons": candidate_skipped[:10],
        },
        "steps": steps,
    }


def render_a1_markdown(payload: dict[str, Any]) -> str:
    summary = payload.get("summary", {})
    lines = [
        "# A1 Forward Shadow Monitor",
        "",
        f"- status：`{payload.get('status')}`",
        f"- monitor_status：`{payload.get('monitor_status')}`",
        f"- candidate：`{payload['lane']['candidate']}`",
        f"- scenario：`{payload['lane']['scenario']}`",
        f"- constrained_date_count：`{summary.get('constrained_date_count')}`",
        f"- candidate_trade_count：`{summary.get('candidate_trade_count')}`",
        f"- candidate_skipped_count：`{summary.get('candidate_skipped_count')}`",
        "",
        "## Artifacts",
        "",
    ]
    for key, value in payload.get("artifacts", {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Pending Reasons", "", "| Ranking Date | Reason |", "|---|---|"])
    for row in summary.get("pending_reasons") or []:
        lines.append(f"| {row.get('ranking_date')} | {row.get('reason')} |")
    lines.append("")
    return "\n".join(lines)


def run_a1(args: argparse.Namespace) -> tuple[int, Path, dict[str, Any]]:
    if args.reuse_existing:
        timestamp = now_utc()
        steps = [{"name": "reuse_existing", "status": "OK", "returncode": 0, "started_at": timestamp, "finished_at": now_utc(), "command": [], "stdout": "", "stderr": ""}]
    else:
        steps = [run_a1_step(name, command) for name, command in a1_command_plan(args)]
    payload = build_a1_payload(args, steps)
    output = resolve_path(args.stage_output) if args.stage_output else PROJECT_ROOT / "artifacts" / "model_experiments" / f"a1_forward_shadow_monitor_{args.date}.json"
    write_json(output, payload)
    output.with_suffix(".md").write_text(render_a1_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "monitor_status": payload["monitor_status"], "output": repo_path(output), **payload["summary"]}, ensure_ascii=False))
    return (0 if payload["status"] == "OK" else 1), output, payload


def stress_output_path(variant: Variant, scenario: Scenario, run_date: str) -> Path:
    return PROJECT_ROOT / "artifacts" / "backtest" / f"portfolio_stress_{variant.name}_{scenario.name}_{run_date}.json"


def stress_command(variant: Variant, scenario: Scenario, run_date: str, features: str) -> list[str]:
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
        str(stress_output_path(variant, scenario, run_date)),
    ]
    if scenario.take_profit_pct is not None:
        command.extend(["--take-profit-pct", str(scenario.take_profit_pct)])
    if scenario.stop_loss_pct is not None:
        command.extend(["--stop-loss-pct", str(scenario.stop_loss_pct)])
    return command


def stress_command_plan(args: argparse.Namespace) -> list[tuple[str, list[str]]]:
    return [
        (f"{scenario.name}.{variant.name}", stress_command(variant, scenario, args.date, args.features))
        for scenario in SCENARIOS
        for variant in VARIANTS
    ]


def run_portfolio(variant: Variant, scenario: Scenario, args: argparse.Namespace) -> dict[str, Any]:
    output = stress_output_path(variant, scenario, args.date)
    command = stress_command(variant, scenario, args.date, args.features)
    if not args.stage_dry_run:
        subprocess.run(command, cwd=PROJECT_ROOT, check=True)
    payload = read_json(output)
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    return {"variant": variant.name, "scenario": scenario.name, "output": repo_path(output), "command": command, "summary": summary}


def stress_decision(row: dict[str, Any], baseline: dict[str, Any]) -> str:
    summary = row.get("summary") if isinstance(row.get("summary"), dict) else {}
    base_summary = baseline.get("summary") if isinstance(baseline.get("summary"), dict) else {}
    ret, dd = summary.get("total_return"), summary.get("max_drawdown")
    base_ret, base_dd = base_summary.get("total_return"), base_summary.get("max_drawdown")
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


def build_stress_payload(args: argparse.Namespace) -> dict[str, Any]:
    rows = [run_portfolio(variant, scenario, args) for scenario in SCENARIOS for variant in VARIANTS]
    baselines = {row["scenario"]: row for row in rows if row.get("variant") == "baseline"}
    for row in rows:
        baseline = baselines.get(str(row.get("scenario")), {})
        row["decision"] = "BASELINE" if row.get("variant") == "baseline" else stress_decision(row, baseline)
        summary = row.get("summary") if isinstance(row.get("summary"), dict) else {}
        base_summary = baseline.get("summary") if isinstance(baseline.get("summary"), dict) else {}
        row["delta_vs_baseline"] = {
            "total_return": round(float(summary["total_return"]) - float(base_summary["total_return"]), 6) if summary.get("total_return") is not None and base_summary.get("total_return") is not None else None,
            "max_drawdown": round(float(summary["max_drawdown"]) - float(base_summary["max_drawdown"]), 6) if summary.get("max_drawdown") is not None and base_summary.get("max_drawdown") is not None else None,
        }
    candidate_rows = [row for row in rows if row.get("variant") != "baseline"]
    by_decision = {name: [row for row in candidate_rows if row.get("decision") == name] for name in ("READY_FOR_SHADOW_MONITOR", "RETURN_ONLY_MONITOR", "RISK_REDUCED_MONITOR", "NO_EFFECT_BASELINE_EQUIVALENT")}
    best = sorted(candidate_rows, key=lambda row: (float((row.get("summary") or {}).get("total_return") or -999), float((row.get("summary") or {}).get("max_drawdown") or -999)), reverse=True)[:5]
    variant_summary: dict[str, dict[str, Any]] = {}
    for variant in [item.name for item in VARIANTS if item.name != "baseline"]:
        items = [row for row in candidate_rows if row.get("variant") == variant]
        meaningful = [row for row in items if row.get("decision") != "NO_EFFECT_BASELINE_EQUIVALENT"]
        ready_items = [row for row in items if row.get("decision") == "READY_FOR_SHADOW_MONITOR"]
        return_deltas = [float((row.get("delta_vs_baseline") or {}).get("total_return")) for row in meaningful if (row.get("delta_vs_baseline") or {}).get("total_return") is not None]
        dd_deltas = [float((row.get("delta_vs_baseline") or {}).get("max_drawdown")) for row in meaningful if (row.get("delta_vs_baseline") or {}).get("max_drawdown") is not None]
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
        "schema_version": STRESS_SCHEMA_VERSION,
        "generated_at": now_utc(),
        "date": args.date,
        "contract": {"research_only": True, "does_not_train_model": True, "does_not_write_models_latest_lgbm": True, "does_not_change_production_ranking": True, "does_not_change_risk_adjusted_score": True, "production_promotion_allowed": False, "model_hash_before": MODEL_HASH},
        "inputs": {"features": args.features, "variants": [asdict(variant) for variant in VARIANTS], "scenarios": [asdict(scenario) for scenario in SCENARIOS]},
        "summary": {
            "scenario_count": len(SCENARIOS),
            "variant_count": len(VARIANTS),
            "candidate_rows": len(candidate_rows),
            "ready_for_shadow_monitor": len(by_decision["READY_FOR_SHADOW_MONITOR"]),
            "return_only_monitor": len(by_decision["RETURN_ONLY_MONITOR"]),
            "risk_reduced_monitor": len(by_decision["RISK_REDUCED_MONITOR"]),
            "no_effect_baseline_equivalent": len(by_decision["NO_EFFECT_BASELINE_EQUIVALENT"]),
            "best_candidate": best[0]["variant"] if best else None,
            "best_candidate_scenario": best[0]["scenario"] if best else None,
        },
        "variant_summary": variant_summary,
        "rows": rows,
        "best_rows": best,
    }


def render_stress_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Candidate Stress Matrix",
        "",
        "- status：`OK`",
        f"- date：`{payload['date']}`",
        f"- scenario_count：`{summary['scenario_count']}`",
        f"- candidate_rows：`{summary['candidate_rows']}`",
        f"- ready_for_shadow_monitor：`{summary['ready_for_shadow_monitor']}`",
        f"- return_only_monitor：`{summary['return_only_monitor']}`",
        f"- risk_reduced_monitor：`{summary['risk_reduced_monitor']}`",
        f"- no_effect_baseline_equivalent：`{summary['no_effect_baseline_equivalent']}`",
        "",
        "## Variant Summary",
        "",
        "| Variant | Meaningful Scenarios | Ready | Ready Ratio | Avg Return Δ | Avg DD Δ |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for variant, row in payload.get("variant_summary", {}).items():
        lines.append("| {variant} | {count} | {ready} | {ratio:.2%} | {ret} | {dd} |".format(variant=variant, count=row.get("meaningful_scenario_count"), ready=row.get("ready_for_shadow_monitor"), ratio=float(row.get("ready_ratio") or 0), ret="" if row.get("avg_total_return_delta") is None else f"{float(row['avg_total_return_delta']):.2%}", dd="" if row.get("avg_max_drawdown_delta") is None else f"{float(row['avg_max_drawdown_delta']):.2%}"))
    lines.extend(["", "| Variant | Scenario | Return | Max DD | Return Δ | DD Δ | Decision |", "|---|---|---:|---:|---:|---:|---|"])
    for row in payload["rows"]:
        item, delta = row.get("summary") or {}, row.get("delta_vs_baseline") or {}
        lines.append("| {variant} | {scenario} | {ret:.2%} | {dd:.2%} | {dret} | {ddd} | {decision} |".format(variant=row.get("variant"), scenario=row.get("scenario"), ret=float(item.get("total_return") or 0), dd=float(item.get("max_drawdown") or 0), dret="" if delta.get("total_return") is None else f"{float(delta['total_return']):.2%}", ddd="" if delta.get("max_drawdown") is None else f"{float(delta['max_drawdown']):.2%}", decision=row.get("decision")))
    lines.append("")
    return "\n".join(lines)


def run_stress(args: argparse.Namespace) -> tuple[int, Path, dict[str, Any]]:
    payload = build_stress_payload(args)
    output = resolve_path(args.stage_output) if args.stage_output else PROJECT_ROOT / "artifacts" / "model_experiments" / f"candidate_stress_matrix_{args.date}.json"
    write_json(output, payload)
    output.with_suffix(".md").write_text(render_stress_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": "OK", "output": repo_path(output), **payload["summary"]}, ensure_ascii=False))
    return 0, output, payload


def replay_command(rankings_dir: str, output: str, features: str) -> list[str]:
    return [sys.executable, "scripts/run_backtest_replay.py", "--rankings-dir", rankings_dir, "--features", features, "--output", output]


def portfolio_command(rankings_dir: str, output: str, features: str, top_n: int = 10) -> list[str]:
    return [
        sys.executable,
        "scripts/run_portfolio_replay.py",
        "--rankings-dir",
        rankings_dir,
        "--features",
        features,
        "--horizon",
        "10",
        "--top-n",
        str(top_n),
        "--max-group-exposure",
        "0.35",
        "--output",
        output,
    ]


def shadow_ranking_command(args: argparse.Namespace, output_dir: str, risk_profile: str) -> list[str]:
    return [
        sys.executable,
        "scripts/research_regime_shadow_ranking.py",
        "--dates-from-dir",
        args.dates_from_dir,
        "--output-dir",
        output_dir,
        "--market-regime-history",
        args.market_regime_history,
        "--risk-profile",
        risk_profile,
        "--top-n",
        "10",
        "--max-sector-count",
        "4",
        "--sector-cap-column",
        "industry_name",
    ]


def constrained_command(production_dir: str, shadow_dir: str, output_dir: str, keep: int) -> list[str]:
    return [
        sys.executable,
        "scripts/build_constrained_shadow_rankings.py",
        "--production-dir",
        production_dir,
        "--shadow-dir",
        shadow_dir,
        "--output-dir",
        output_dir,
        "--top-n",
        "10",
        "--min-production-count",
        str(keep),
    ]


def training_steps_log(args: argparse.Namespace) -> Path:
    return resolve_path(args.steps_log or f"artifacts/model_experiments/overnight_training_steps_{args.date}_{args.label}.tsv")


def training_summary_command(args: argparse.Namespace, steps_log: Path) -> list[str]:
    return [
        sys.executable,
        "scripts/build_overnight_training_summary.py",
        "--date",
        args.date,
        "--window",
        args.label,
        "--artifact-label",
        args.label,
        "--model-hash-before",
        args.model_hash_before,
        "--steps-log",
        repo_path(steps_log),
    ]


def training_command_plan(args: argparse.Namespace) -> list[tuple[str, list[str]]]:
    label = args.label
    production_dir = args.dates_from_dir
    feature_shadow = f"artifacts/backtest/shadow_rankings_batch01_feature_group_sector_cap_{label}"
    sector_shadow = f"artifacts/backtest/shadow_rankings_batch01_sector_context_sector_cap_{label}"
    steps: list[tuple[str, list[str]]] = [
        ("baseline.replay", replay_command(production_dir, f"artifacts/backtest/replay_batch01_baseline_{label}_{args.date}.json", args.features)),
        ("baseline.portfolio.top10", portfolio_command(production_dir, f"artifacts/backtest/portfolio_batch01_baseline_{label}_top10_h10_{args.date}.json", args.features)),
        ("feature_group.shadow_ranking", shadow_ranking_command(args, feature_shadow, "baseline")),
        ("sector_context.shadow_ranking", shadow_ranking_command(args, sector_shadow, "shadow_regime_guard_balanced")),
    ]
    for keep in [int(item.strip()) for item in args.keeps.split(",") if item.strip()]:
        for prefix, shadow_dir in (("feature_group", feature_shadow), ("sector_context", sector_shadow)):
            constrained_dir = f"artifacts/backtest/shadow_rankings_batch01_{prefix}_constrained_k{keep}_{label}"
            candidate = f"{prefix}_constrained_k{keep}_{label}"
            steps.extend(
                [
                    (f"{prefix}.constrained.k{keep}", constrained_command(production_dir, shadow_dir, constrained_dir, keep)),
                    (f"{prefix}.replay.k{keep}", replay_command(constrained_dir, f"artifacts/backtest/replay_batch01_{candidate}_{args.date}.json", args.features)),
                    (f"{prefix}.portfolio.k{keep}", portfolio_command(constrained_dir, f"artifacts/backtest/portfolio_batch01_{candidate}_top10_h10_{args.date}.json", args.features)),
                ]
            )
    steps.append(("summary.build", training_summary_command(args, training_steps_log(args))))
    return steps


def run_training_step(name: str, command: list[str]) -> dict[str, Any]:
    started = now_utc()
    completed = subprocess.run(command, cwd=PROJECT_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return {
        "name": name,
        "status": "OK" if completed.returncode == 0 else "FAILED",
        "returncode": completed.returncode,
        "started_at": started,
        "ended_at": now_utc(),
        "command": command,
        "stdout_tail": completed.stdout[-3000:],
        "stderr_tail": completed.stderr[-3000:],
    }


def append_tsv(path: Path, step: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{step['name']}\t{step['status']}\t{step['started_at']}\t{step['ended_at']}\t{step['returncode']}\n")


def run_training(args: argparse.Namespace) -> tuple[int, Path, dict[str, Any]]:
    steps_log = training_steps_log(args)
    if steps_log.exists():
        steps_log.unlink()
    steps: list[dict[str, Any]] = []
    for name, command in training_command_plan(args):
        step = run_training_step(name, command)
        steps.append(step)
        append_tsv(steps_log, step)
    status = "OK" if all(step["status"] == "OK" for step in steps) else "FAILED"
    payload = {
        "schema_version": TRAINING_SCHEMA_VERSION,
        "generated_at": now_utc(),
        "date": args.date,
        "label": args.label,
        "status": status,
        "contract": {"research_only": True, "does_not_train_model": True, "does_not_write_models_latest_lgbm": True, "does_not_change_production_ranking": True},
        "steps_log": repo_path(steps_log),
        "steps": steps,
    }
    output = resolve_path(args.stage_output or f"artifacts/model_experiments/overnight_shadow_training_runner_{args.date}_{args.label}.json")
    write_json(output, payload)
    print(json.dumps({"status": status, "output": repo_path(output), "steps_log": repo_path(steps_log)}, ensure_ascii=False))
    return (0 if status == "OK" else 1), output, payload


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def matrix(path: str) -> dict[str, Any]:
    payload = read_json(path)
    return {"path": path, "exists": bool(payload), "summary": payload.get("summary") or {}, "scenarios": payload.get("scenarios") or []}


def pick_best(rows: list[dict[str, Any]], baseline_return: float | None, baseline_drawdown: float | None) -> dict[str, Any]:
    valid = [row for row in rows if row.get("total_return") is not None and row.get("max_drawdown") is not None]
    if baseline_return is None or baseline_drawdown is None:
        return {}
    passing = [row for row in valid if float(row["total_return"]) >= baseline_return and float(row["max_drawdown"]) >= baseline_drawdown]
    if passing:
        best = max(passing, key=lambda row: float(row.get("score") or -999))
        return {"decision": "READY_FOR_SHADOW_MONITOR", "scenario": best, "reason": "return and drawdown both beat baseline"}
    lower_dd = [row for row in valid if float(row["max_drawdown"]) >= baseline_drawdown]
    if lower_dd:
        best = max(lower_dd, key=lambda row: float(row.get("total_return") or -999))
        return {"decision": "RISK_REDUCED_MONITOR_ONLY", "scenario": best, "reason": "drawdown improved but return is below baseline"}
    best = max(valid, key=lambda row: float(row.get("score") or -999), default={})
    return {"decision": "MONITOR_ONLY", "scenario": best, "reason": "no scenario beats baseline drawdown"}


def risk_candidate(label: str, path: str, baseline: dict[str, Any]) -> dict[str, Any]:
    item = matrix(path)
    baseline_rows = baseline.get("scenarios") or []
    baseline_best = baseline_rows[0] if baseline_rows else {}
    decision = pick_best(item["scenarios"], baseline_best.get("total_return"), baseline_best.get("max_drawdown"))
    return {"candidate_id": label, "matrix": item, "best_vs_baseline": decision}


def build_risk_payload(args: argparse.Namespace) -> dict[str, Any]:
    model_hash_after = sha256(resolve_path(args.model))
    baseline = matrix(f"artifacts/backtest/strategy_matrix_baseline_{args.label}_{args.date}.json")
    candidates = [
        risk_candidate("sector_context_k7", f"artifacts/backtest/strategy_matrix_sector_context_k7_{args.label}_{args.date}.json", baseline),
        risk_candidate("feature_group_k7", f"artifacts/backtest/strategy_matrix_feature_group_k7_{args.label}_{args.date}.json", baseline),
        risk_candidate("feature_group_k8", f"artifacts/backtest/strategy_matrix_feature_group_k8_{args.label}_{args.date}.json", baseline),
    ]
    counts: dict[str, int] = {}
    for item in candidates:
        decision = item["best_vs_baseline"].get("decision", "MISSING")
        counts[decision] = counts.get(decision, 0) + 1
    errors = []
    if args.model_hash_before != model_hash_after:
        errors.append("models/latest_lgbm.pkl hash changed")
    if not baseline["exists"]:
        errors.append("missing baseline matrix")
    return {
        "schema_version": RISK_SCHEMA_VERSION,
        "generated_at": now_utc(),
        "date": args.date,
        "label": args.label,
        "status": "FAILED" if errors else "OK",
        "contract": {"research_only": True, "does_not_train_model": True, "does_not_write_models_latest_lgbm": True, "promotion_ready": False},
        "baseline": baseline,
        "summary": {"candidates_tested": len(candidates), "decisions": counts, "ready_for_shadow_monitor": counts.get("READY_FOR_SHADOW_MONITOR", 0), "risk_reduced_monitor_only": counts.get("RISK_REDUCED_MONITOR_ONLY", 0)},
        "candidates": candidates,
        "guard_status": {"models_latest_changed": args.model_hash_before != model_hash_after, "model_hash_before": args.model_hash_before, "model_hash_after": model_hash_after, "promotion_ready": False},
        "errors": errors,
    }


def pct(value: Any) -> str:
    return "--" if value is None else f"{float(value):.2%}"


def render_risk_markdown(payload: dict[str, Any]) -> str:
    baseline_best = (payload["baseline"].get("scenarios") or [{}])[0]
    lines = [
        "# Overnight Risk Matrix Summary",
        "",
        f"- status: {payload['status']}",
        f"- label: {payload['label']}",
        f"- ready_for_shadow_monitor: {payload['summary']['ready_for_shadow_monitor']}",
        f"- risk_reduced_monitor_only: {payload['summary']['risk_reduced_monitor_only']}",
        f"- baseline_best: {baseline_best.get('scenario_id')}",
        f"- baseline_return: {pct(baseline_best.get('total_return'))}",
        f"- baseline_max_drawdown: {pct(baseline_best.get('max_drawdown'))}",
        f"- models_latest_changed: {payload['guard_status']['models_latest_changed']}",
        f"- promotion_ready: {payload['guard_status']['promotion_ready']}",
        "",
        "| Candidate | Decision | Scenario | Return | Max DD | Win | Reason |",
        "|---|---|---|---:|---:|---:|---|",
    ]
    for item in payload["candidates"]:
        decision = item["best_vs_baseline"]
        scenario = decision.get("scenario") or {}
        lines.append("| {candidate} | {decision} | {scenario_id} | {ret} | {dd} | {win} | {reason} |".format(candidate=item["candidate_id"], decision=decision.get("decision"), scenario_id=scenario.get("scenario_id"), ret=pct(scenario.get("total_return")), dd=pct(scenario.get("max_drawdown")), win=pct(scenario.get("win_rate")), reason=decision.get("reason")))
    lines.append("")
    return "\n".join(lines)


def run_risk(args: argparse.Namespace) -> tuple[int, Path, dict[str, Any]]:
    payload = build_risk_payload(args)
    output = resolve_path(args.stage_output) if args.stage_output else PROJECT_ROOT / "artifacts" / "model_experiments" / f"overnight_risk_matrix_summary_{args.date}_{args.label}.json"
    write_json(output, payload)
    output.with_suffix(".md").write_text(render_risk_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output), "errors": payload["errors"]}, ensure_ascii=False))
    return (1 if payload["errors"] else 0), output, payload


def stage_output_path(args: argparse.Namespace) -> Path:
    if args.stage_output:
        return resolve_path(args.stage_output)
    if args.stage == "a1-forward":
        return PROJECT_ROOT / "artifacts" / "model_experiments" / f"a1_forward_shadow_monitor_{args.date}.json"
    if args.stage == "candidate-stress":
        return PROJECT_ROOT / "artifacts" / "model_experiments" / f"candidate_stress_matrix_{args.date}.json"
    if args.stage == "overnight-training":
        return PROJECT_ROOT / "artifacts" / "model_experiments" / f"overnight_shadow_training_runner_{args.date}_{args.label}.json"
    return PROJECT_ROOT / "artifacts" / "model_experiments" / f"overnight_risk_matrix_summary_{args.date}_{args.label}.json"


def command_plan(args: argparse.Namespace) -> list[tuple[str, list[str]]]:
    if args.stage == "a1-forward":
        return a1_command_plan(args)
    if args.stage == "candidate-stress":
        return stress_command_plan(args)
    if args.stage == "overnight-training":
        return training_command_plan(args)
    return []


def campaign_manifest(args: argparse.Namespace, status: str, history: list[str], returncode: int | None) -> dict[str, Any]:
    plan = command_plan(args)
    return {
        "schema_version": CAMPAIGN_SCHEMA_VERSION,
        "generated_at": now_utc(),
        "dry_run": bool(args.campaign_dry_run),
        "status": status,
        "stages": [
            {
                "name": args.stage,
                "status": status,
                "status_history": history,
                "command": [{"name": name, "argv": command} for name, command in plan],
                "returncode": returncode,
                "artifact_path": repo_path(stage_output_path(args)),
            }
        ],
    }


def manifest_path(args: argparse.Namespace) -> Path | None:
    if args.campaign_output:
        return resolve_path(args.campaign_output)
    if args.campaign_dry_run:
        return None
    return PROJECT_ROOT / "artifacts" / "model_experiments" / f"shadow_research_campaign_{args.date}_{args.stage}.json"


def write_manifest(args: argparse.Namespace, status: str, history: list[str], returncode: int | None) -> None:
    path = manifest_path(args)
    if path is not None:
        write_json(path, campaign_manifest(args, status, history, returncode))


def run_stage(args: argparse.Namespace) -> tuple[int, Path, dict[str, Any]]:
    if args.stage == "a1-forward":
        return run_a1(args)
    if args.stage == "candidate-stress":
        return run_stress(args)
    if args.stage == "overnight-training":
        return run_training(args)
    return run_risk(args)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.campaign_dry_run:
        write_manifest(args, "SKIPPED", ["planned", "SKIPPED"], None)
        return 0

    write_manifest(args, "running", ["planned", "running"], None)
    try:
        returncode, _, _ = run_stage(args)
    except Exception:
        write_manifest(args, "FAILED", ["planned", "running", "FAILED"], 1)
        raise
    status = "OK" if returncode == 0 else "FAILED"
    write_manifest(args, status, ["planned", "running", status], returncode)
    return returncode


if __name__ == "__main__":
    raise SystemExit(main())
