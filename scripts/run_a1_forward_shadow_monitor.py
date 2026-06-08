#!/usr/bin/env python3
"""執行 A1 forward shadow monitor。

A1 固定規格：
- sector_context_production_top7_shadow_fill3
- 5D / D+1 / group cap 25%

本腳本只產研究 artifact，不修改 production ranking、不覆蓋正式模型。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "a1-forward-shadow-monitor.v1"
MODEL_HASH = "76f530f6491f996f4838500acacbde40a10c90f43116cec0dcc69fb6b4935675"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="run A1 forward shadow monitor")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--production-dir", default="artifacts")
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument("--market-regime-history", default="artifacts/market_regime_history_2026-06-01.json")
    parser.add_argument("--industry-map", default="data/reference/stock_industry_map.csv")
    parser.add_argument("--output", default=None)
    parser.add_argument("--reuse-existing", action="store_true", help="只重建 monitor summary，不重跑四個子步驟")
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def run_step(name: str, command: list[str]) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc).isoformat()
    proc = subprocess.run(command, cwd=PROJECT_ROOT, text=True, capture_output=True)
    return {
        "name": name,
        "status": "OK" if proc.returncode == 0 else "FAILED",
        "returncode": proc.returncode,
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "command": command,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-4000:],
    }


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_payload(args: argparse.Namespace, steps: list[dict[str, Any]], paths: dict[str, Path]) -> dict[str, Any]:
    shadow_summary = load_json(paths["shadow_ranking_summary"])
    constrained_summary = load_json(paths["constrained_summary"])
    baseline = load_json(paths["baseline_replay"])
    candidate = load_json(paths["candidate_replay"])
    baseline_summary = baseline.get("summary") if isinstance(baseline.get("summary"), dict) else {}
    candidate_summary = candidate.get("summary") if isinstance(candidate.get("summary"), dict) else {}
    candidate_skipped = candidate.get("skipped") if isinstance(candidate.get("skipped"), list) else []
    trade_count = int(candidate_summary.get("trade_count") or 0)
    status = "READY_WITH_MATURE_OUTCOMES" if trade_count > 0 else "PENDING_OUTCOMES"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK" if all(step["status"] == "OK" for step in steps) else "FAILED",
        "monitor_status": status,
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


def render_markdown(payload: dict[str, Any]) -> str:
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


def main() -> int:
    args = parse_args()
    shadow_dir = PROJECT_ROOT / "artifacts" / "backtest" / f"shadow_rankings_a1_sector_context_forward_{args.date}"
    constrained_dir = PROJECT_ROOT / "artifacts" / "backtest" / f"shadow_rankings_a1_sector_context_production_top7_shadow_fill3_forward_{args.date}"
    baseline_replay = PROJECT_ROOT / "artifacts" / "backtest" / f"portfolio_a1_baseline_forward_top10_h5_d1_gc25_{args.date}.json"
    candidate_replay = PROJECT_ROOT / "artifacts" / "backtest" / f"portfolio_a1_sector_context_production_top7_shadow_fill3_forward_top10_h5_d1_gc25_{args.date}.json"
    paths = {
        "shadow_ranking_dir": shadow_dir,
        "shadow_ranking_summary": shadow_dir / "regime_shadow_ranking.json",
        "constrained_dir": constrained_dir,
        "constrained_summary": constrained_dir / "constrained_shadow_ranking.json",
        "baseline_replay": baseline_replay,
        "candidate_replay": candidate_replay,
    }
    if args.reuse_existing:
        steps = [
            {
                "name": "reuse_existing",
                "status": "OK",
                "returncode": 0,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "command": [],
                "stdout": "",
                "stderr": "",
            }
        ]
    else:
        steps = [
            run_step(
            "shadow_ranking",
            [
                sys.executable,
                "scripts/research_regime_shadow_ranking.py",
                "--dates-from-dir",
                args.production_dir,
                "--output-dir",
                repo_path(shadow_dir),
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
            run_step(
            "constrained_ranking",
            [
                sys.executable,
                "scripts/build_constrained_shadow_rankings.py",
                "--production-dir",
                args.production_dir,
                "--shadow-dir",
                repo_path(shadow_dir),
                "--output-dir",
                repo_path(constrained_dir),
                "--top-n",
                "10",
                "--min-production-count",
                "7",
            ],
            ),
            run_step(
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
                repo_path(baseline_replay),
            ],
            ),
            run_step(
            "candidate_replay",
            [
                sys.executable,
                "scripts/run_portfolio_replay.py",
                "--rankings-dir",
                repo_path(constrained_dir),
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
                repo_path(candidate_replay),
            ],
            ),
        ]
    payload = build_payload(args, steps, paths)
    output = resolve_path(args.output) if args.output else PROJECT_ROOT / "artifacts" / "model_experiments" / f"a1_forward_shadow_monitor_{args.date}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "monitor_status": payload["monitor_status"], "output": repo_path(output), **payload["summary"]}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
