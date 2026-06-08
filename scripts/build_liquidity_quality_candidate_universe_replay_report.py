#!/usr/bin/env python3
"""彙整完整候選池流動性 shadow replay。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "liquidity-quality-candidate-universe-replay-report.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build liquidity candidate universe replay report")
    parser.add_argument("--shadow", default="artifacts/liquidity_quality_candidate_universe_shadow_2026-06-03.json")
    parser.add_argument("--production-replay", default="artifacts/backtest/replay_liquidity_candidate_universe_production_2026-06-03.json")
    parser.add_argument("--log-replay", default="artifacts/backtest/replay_liquidity_candidate_universe_log_gate_2026-06-03.json")
    parser.add_argument("--percentile-replay", default="artifacts/backtest/replay_liquidity_candidate_universe_percentile_gate_2026-06-03.json")
    parser.add_argument("--output", default="artifacts/liquidity_quality_candidate_universe_replay_report_2026-06-03.json")
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
    return {
        "path": repo_path(path),
        "trade_count": summary.get("trade_count"),
        "skipped_count": len(payload.get("skipped", [])),
        "by_horizon": summary.get("by_horizon", {}),
        "portfolio_by_horizon": summary.get("portfolio_by_horizon", {}),
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
        "candidate_total_return": cand_ret,
        "baseline_total_return": base_ret,
        "total_return_delta": None if cand_ret is None or base_ret is None else round(cand_ret - base_ret, 6),
        "candidate_max_drawdown": cand_dd,
        "baseline_max_drawdown": base_dd,
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
    horizons = sorted(
        (production.get("portfolio_by_horizon") or {}).keys(),
        key=lambda value: int(value),
    )
    comparisons = {
        "log_gate": [horizon_delta(log_gate, production, horizon) for horizon in horizons],
        "percentile_gate": [horizon_delta(percentile, production, horizon) for horizon in horizons],
    }
    date_count = int((shadow.get("summary") or {}).get("date_count") or 0)
    sample_is_small = date_count < 30
    candidates = classify_candidates(comparisons, shadow)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK",
        "contract": {
            "research_only": True,
            "changes_production_ranking": False,
            "changes_risk_adjusted_score": False,
            "changes_model": False,
            "sample_is_small": sample_is_small,
            "portfolio_replay_boundary": "bucket-only replay; not finite-capital overlapping portfolio",
        },
        "inputs": {
            "shadow": repo_path(shadow_path),
            "production_replay": repo_path(production_path),
            "log_replay": repo_path(log_path),
            "percentile_replay": repo_path(percentile_path),
        },
        "shadow_summary": shadow.get("summary"),
        "replays": {
            "production": production,
            "log_gate": log_gate,
            "percentile_gate": percentile,
        },
        "comparisons_vs_recomputed_production": comparisons,
        "decision": {
            "status": "READY_FOR_CAPITAL_AWARE_REPLAY" if candidates else "MONITOR_ONLY",
            "shadow_candidates": [item["variant"] for item in candidates],
            "candidate_details": candidates,
            "production_ready": False,
            "reason": "完整候選池半年 replay 只能當 ranking 方向證據；bucket-only 複利不是有限本金實盤結果。",
            "next_step": "run capital-aware replay before any production ranking proposal",
        },
    }


def classify_candidates(comparisons: dict[str, list[dict[str, Any]]], shadow: dict[str, Any]) -> list[dict[str, Any]]:
    variants = (shadow.get("summary") or {}).get("variants") or {}
    result: list[dict[str, Any]] = []
    for variant, rows in comparisons.items():
        by_horizon = {str(item["horizon"]): item for item in rows}
        key_rows = [by_horizon.get(key) for key in ("3", "5", "10") if by_horizon.get(key)]
        return_wins = sum(1 for item in key_rows if (item.get("total_return_delta") or 0) > 0)
        drawdown_wins = sum(1 for item in key_rows if (item.get("max_drawdown_delta") or 0) >= 0)
        drift = variants.get(variant, {})
        overlap = n(drift.get("avg_overlap_rate_with_recomputed_production"))
        top1_changes = int(drift.get("top1_change_count") or 0)
        date_count = int((shadow.get("summary") or {}).get("date_count") or 0)
        top1_change_rate = None if date_count <= 0 else round(top1_changes / date_count, 6)
        replay_pass = return_wins >= 2 and drawdown_wins >= 2
        if not replay_pass:
            continue
        status = "PRIMARY_FOLLOWUP_CANDIDATE"
        if overlap is not None and overlap < 0.6:
            status = "AGGRESSIVE_REPLAY_WINNER_REQUIRE_DRIFT_CHECK"
        result.append(
            {
                "variant": variant,
                "status": status,
                "return_win_count_3_5_10d": return_wins,
                "drawdown_win_count_3_5_10d": drawdown_wins,
                "avg_overlap_rate_with_recomputed_production": overlap,
                "top1_change_rate": top1_change_rate,
            }
        )
    return result


def pct(value: Any) -> str:
    try:
        return f"{float(value):.2%}"
    except (TypeError, ValueError):
        return "--"


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Liquidity Quality Candidate Universe Replay Report",
        "",
        f"- status: `{payload['status']}`",
        f"- decision: `{payload['decision']['status']}`",
        f"- production_ready: `{payload['decision']['production_ready']}`",
        f"- sample_is_small: `{payload['contract']['sample_is_small']}`",
        f"- replay_boundary: `{payload['contract']['portfolio_replay_boundary']}`",
        "",
        "## Replay Delta Vs Recomputed Production",
        "",
        "| variant | horizon | candidate return | baseline return | delta | candidate DD | baseline DD | DD delta |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for variant, rows in payload["comparisons_vs_recomputed_production"].items():
        for row in rows:
            lines.append(
                f"| {variant} | {row['horizon']} | {pct(row['candidate_total_return'])} | {pct(row['baseline_total_return'])} | {pct(row['total_return_delta'])} | {pct(row['candidate_max_drawdown'])} | {pct(row['baseline_max_drawdown'])} | {pct(row['max_drawdown_delta'])} |"
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
