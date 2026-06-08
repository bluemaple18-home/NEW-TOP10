#!/usr/bin/env python3
"""彙整 constrained shadow ranking 比較結果。"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "constrained-shadow-comparison.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build constrained shadow comparison")
    parser.add_argument("--date", required=True)
    parser.add_argument("--model", default="models/latest_lgbm.pkl")
    parser.add_argument("--model-hash-before", required=True)
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


def read_json(path: str | Path) -> dict[str, Any]:
    resolved = resolve_path(path)
    if not resolved.exists():
        return {}
    return json.loads(resolved.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def replay_metrics(path: str) -> dict[str, Any]:
    summary = read_json(path).get("summary") or {}
    h10 = (summary.get("portfolio_by_horizon") or {}).get("10") or {}
    trade = (summary.get("by_horizon") or {}).get("10") or {}
    return {
        "compounded_return": h10.get("total_compounded_return"),
        "avg_portfolio_return": h10.get("avg_portfolio_return"),
        "trade_avg_net_return": trade.get("avg_net_return"),
    }


def portfolio_metrics(path: str) -> dict[str, Any]:
    summary = read_json(path).get("summary") or {}
    return {
        "total_return": summary.get("total_return"),
        "max_drawdown": summary.get("max_drawdown"),
        "max_group_exposure": summary.get("max_group_exposure"),
    }


def constrained_summary(path: str) -> dict[str, Any]:
    return (read_json(path).get("summary") or {})


def candidate(candidate_id: str, ranking_dir: str, replay_path: str, portfolio_path: str, baseline: dict[str, Any]) -> dict[str, Any]:
    replay = replay_metrics(replay_path)
    portfolio = portfolio_metrics(portfolio_path)
    total_return_delta = None
    drawdown_delta = None
    if portfolio.get("total_return") is not None and baseline["portfolio"].get("total_return") is not None:
        total_return_delta = float(portfolio["total_return"]) - float(baseline["portfolio"]["total_return"])
    if portfolio.get("max_drawdown") is not None and baseline["portfolio"].get("max_drawdown") is not None:
        drawdown_delta = float(portfolio["max_drawdown"]) - float(baseline["portfolio"]["max_drawdown"])
    decision = "MONITOR_ONLY"
    reason = "未同時優於 baseline return 與 drawdown。"
    if total_return_delta is not None and drawdown_delta is not None and total_return_delta >= 0 and drawdown_delta >= 0:
        decision = "READY_FOR_SHADOW_MONITOR"
        reason = "Top10 portfolio return 不低於 baseline，且 max drawdown 改善。"
    return {
        "candidate_id": candidate_id,
        "ranking_dir": ranking_dir,
        "ranking_summary": constrained_summary(f"{ranking_dir}/constrained_shadow_ranking.json"),
        "replay": replay,
        "portfolio": portfolio,
        "portfolio_total_return_delta": total_return_delta,
        "portfolio_drawdown_delta": drawdown_delta,
        "decision": decision,
        "reason": reason,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    model_path = resolve_path(args.model)
    model_hash_after = sha256(model_path)
    baseline = {
        "replay": replay_metrics("artifacts/backtest/replay_batch01_baseline_recent_2026-06-02.json"),
        "portfolio": portfolio_metrics("artifacts/backtest/portfolio_batch01_baseline_top10_h10_2026-06-02.json"),
    }
    candidates = []
    for keep in [3, 5, 7]:
        candidates.append(
            candidate(
                f"feature_group_ablation_by_regime_constrained_k{keep}",
                f"artifacts/backtest/shadow_rankings_batch01_feature_group_constrained_k{keep}",
                f"artifacts/backtest/replay_batch01_feature_group_constrained_k{keep}_2026-06-02.json",
                f"artifacts/backtest/portfolio_batch01_feature_group_constrained_k{keep}_top10_h10_2026-06-02.json",
                baseline,
            )
        )
        candidates.append(
            candidate(
                f"sector_industry_context_constrained_k{keep}",
                f"artifacts/backtest/shadow_rankings_batch01_sector_context_constrained_k{keep}",
                f"artifacts/backtest/replay_batch01_sector_context_constrained_k{keep}_2026-06-02.json",
                f"artifacts/backtest/portfolio_batch01_sector_context_constrained_k{keep}_top10_h10_2026-06-02.json",
                baseline,
            )
        )
    counts: dict[str, int] = {}
    for item in candidates:
        counts[item["decision"]] = counts.get(item["decision"], 0) + 1
    errors = []
    if args.model_hash_before != model_hash_after:
        errors.append("models/latest_lgbm.pkl hash changed")
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "FAILED" if errors else "OK",
        "contract": {
            "research_only": True,
            "does_not_train_model": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_production_ranking": True,
            "promotion_ready": False,
        },
        "baseline": baseline,
        "summary": {
            "candidates_tested": len(candidates),
            "decisions": counts,
            "ready_for_shadow_monitor": counts.get("READY_FOR_SHADOW_MONITOR", 0),
            "best_candidate": max(candidates, key=lambda item: float(item["portfolio"].get("total_return") or -999)).get("candidate_id")
            if candidates
            else None,
        },
        "candidates": candidates,
        "guard_status": {
            "models_latest_changed": args.model_hash_before != model_hash_after,
            "model_hash_before": args.model_hash_before,
            "model_hash_after": model_hash_after,
            "promotion_ready": False,
        },
        "errors": errors,
    }


def pct(value: Any) -> str:
    if value is None:
        return "--"
    return f"{float(value):.2%}"


def render_markdown(payload: dict[str, Any]) -> str:
    baseline = payload["baseline"]["portfolio"]
    lines = [
        "# Constrained Shadow Comparison",
        "",
        f"- status: {payload['status']}",
        f"- candidates_tested: {payload['summary']['candidates_tested']}",
        f"- ready_for_shadow_monitor: {payload['summary']['ready_for_shadow_monitor']}",
        f"- best_candidate: {payload['summary']['best_candidate']}",
        f"- baseline_total_return: {pct(baseline.get('total_return'))}",
        f"- baseline_max_drawdown: {pct(baseline.get('max_drawdown'))}",
        f"- models_latest_changed: {payload['guard_status']['models_latest_changed']}",
        f"- promotion_ready: {payload['guard_status']['promotion_ready']}",
        "",
        "| Candidate | Decision | Avg Overlap | Return | Return Delta | Max DD | Max Group |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for item in payload["candidates"]:
        lines.append(
            "| {candidate} | {decision} | {overlap} | {ret} | {ret_delta} | {dd} | {group} |".format(
                candidate=item["candidate_id"],
                decision=item["decision"],
                overlap=item["ranking_summary"].get("avg_overlap_count"),
                ret=pct(item["portfolio"].get("total_return")),
                ret_delta=pct(item.get("portfolio_total_return_delta")),
                dd=pct(item["portfolio"].get("max_drawdown")),
                group=pct(item["portfolio"].get("max_group_exposure")),
            )
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = resolve_path(args.output) if args.output else PROJECT_ROOT / "artifacts" / "model_experiments" / f"constrained_shadow_comparison_{args.date}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output), "errors": payload["errors"]}, ensure_ascii=False))
    return 1 if payload["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
