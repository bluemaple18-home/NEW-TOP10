#!/usr/bin/env python3
"""彙整流動性品質 shadow replay 結果。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "liquidity-quality-shadow-replay-report.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build liquidity quality shadow replay report")
    parser.add_argument("--shadow", default="artifacts/liquidity_quality_shadow_2026-06-03.json")
    parser.add_argument("--production-replay", default="artifacts/backtest/replay_liquidity_shadow_production_2026-06-03.json")
    parser.add_argument("--log-replay", default="artifacts/backtest/replay_liquidity_shadow_log_gate_2026-06-03.json")
    parser.add_argument("--percentile-replay", default="artifacts/backtest/replay_liquidity_shadow_percentile_gate_2026-06-03.json")
    parser.add_argument("--output", default="artifacts/liquidity_quality_shadow_replay_report_2026-06-03.json")
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"artifact 不存在：{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def n(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def replay_summary(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    summary = payload.get("summary", {})
    portfolio = summary.get("portfolio_by_horizon", {})
    return {
        "path": repo_path(path),
        "trade_count": summary.get("trade_count"),
        "skipped_count": len(payload.get("skipped", [])),
        "portfolio_by_horizon": portfolio,
    }


def horizon_delta(candidate: dict[str, Any], baseline: dict[str, Any], horizon: str) -> dict[str, Any]:
    cand = (candidate.get("portfolio_by_horizon") or {}).get(horizon, {})
    base = (baseline.get("portfolio_by_horizon") or {}).get(horizon, {})
    cand_ret = n(cand.get("total_compounded_return"))
    base_ret = n(base.get("total_compounded_return"))
    cand_dd = n(cand.get("max_drawdown"))
    base_dd = n(base.get("max_drawdown"))
    return {
        "horizon": int(horizon),
        "total_return_delta": None if cand_ret is None or base_ret is None else round(cand_ret - base_ret, 6),
        "max_drawdown_delta": None if cand_dd is None or base_dd is None else round(cand_dd - base_dd, 6),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    shadow_path = resolve_path(args.shadow)
    production_path = resolve_path(args.production_replay)
    log_path = resolve_path(args.log_replay)
    percentile_path = resolve_path(args.percentile_replay)
    shadow = read_json(shadow_path)
    production = replay_summary(production_path)
    log_gate = replay_summary(log_path)
    percentile = replay_summary(percentile_path)
    comparisons = {
        "log_gate": [horizon_delta(log_gate, production, horizon) for horizon in ["1", "3", "5"]],
        "percentile_gate": [horizon_delta(percentile, production, horizon) for horizon in ["1", "3", "5"]],
    }
    top10_overlap = {
        variant: (shadow.get("summary", {}).get("variants", {}).get(variant, {}) or {}).get("avg_overlap_rate_with_production")
        for variant in ["percentile_gate", "log_gate"]
    }
    top1_changes = {
        variant: (shadow.get("summary", {}).get("variants", {}).get(variant, {}) or {}).get("top1_change_count")
        for variant in ["percentile_gate", "log_gate"]
    }
    no_membership_change = all(float(value or 0) >= 1.0 for value in top10_overlap.values())
    replay_same = all(
        all((item.get("total_return_delta") in {0, 0.0} and item.get("max_drawdown_delta") in {0, 0.0}) for item in rows)
        for rows in comparisons.values()
    )
    decision_status = "NO_PORTFOLIO_EFFECT_IN_CURRENT_WINDOW" if no_membership_change and replay_same else "REPLAY_EXTENSION_NEEDED"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK",
        "contract": {
            "research_only": True,
            "changes_production_ranking": False,
            "changes_risk_adjusted_score": False,
            "changes_model": False,
        },
        "inputs": {
            "shadow": repo_path(shadow_path),
            "production_replay": repo_path(production_path),
            "log_replay": repo_path(log_path),
            "percentile_replay": repo_path(percentile_path),
        },
        "summary": {
            "top10_overlap": top10_overlap,
            "top1_changes": top1_changes,
            "no_membership_change": no_membership_change,
            "replay_same": replay_same,
        },
        "replays": {
            "production": production,
            "log_gate": log_gate,
            "percentile_gate": percentile,
        },
        "comparisons_vs_production": comparisons,
        "decision": {
            "status": decision_status,
            "production_ready": False,
            "reason": "目前樣本中 Top10 成員完全相同，只改排序；Top10 portfolio replay 無差異，不能當 production evidence。",
            "next_step": "需要用更大的候選池或重跑 scoring candidate universe，確認 liquidity score 是否會改變 Top10 成員。",
        },
    }


def pct(value: Any) -> str:
    try:
        return f"{float(value):.2%}"
    except (TypeError, ValueError):
        return "--"


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Liquidity Quality Shadow Replay Report",
        "",
        f"- status: `{payload['status']}`",
        f"- decision: `{payload['decision']['status']}`",
        f"- production_ready: `{payload['decision']['production_ready']}`",
        f"- no_membership_change: `{payload['summary']['no_membership_change']}`",
        f"- replay_same: `{payload['summary']['replay_same']}`",
        "",
        "## Top10 Change",
        "",
        json.dumps(payload["summary"], ensure_ascii=False, indent=2),
        "",
        "## Replay Delta Vs Production",
        "",
        json.dumps(payload["comparisons_vs_production"], ensure_ascii=False, indent=2),
        "",
        "## Decision",
        "",
        json.dumps(payload["decision"], ensure_ascii=False, indent=2),
        "",
    ]
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
