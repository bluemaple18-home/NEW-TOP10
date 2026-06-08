#!/usr/bin/env python3
"""彙整 overnight shadow training / replay 結果。"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "overnight-training-summary.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build overnight training summary")
    parser.add_argument("--date", required=True)
    parser.add_argument("--window", default="extended")
    parser.add_argument("--artifact-label", default=None)
    parser.add_argument("--model", default="models/latest_lgbm.pkl")
    parser.add_argument("--model-hash-before", required=True)
    parser.add_argument("--steps-log", default=None)
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


def steps_summary(path: str | None) -> dict[str, Any]:
    if not path:
        return {"provided": False, "total": 0, "failed": 0, "failed_steps": []}
    resolved = resolve_path(path)
    if not resolved.exists():
        return {"provided": True, "exists": False, "total": 0, "failed": 0, "failed_steps": []}
    rows = []
    for line in resolved.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) >= 4:
            rows.append({"step": parts[0], "status": parts[1], "started_at": parts[2], "ended_at": parts[3]})
    failed = [row for row in rows if row["status"] != "OK"]
    return {
        "provided": True,
        "exists": True,
        "total": len(rows),
        "failed": len(failed),
        "failed_steps": failed,
    }


def replay_metrics(path: str) -> dict[str, Any]:
    payload = read_json(path)
    if not payload:
        return {"exists": False}
    summary = payload.get("summary") or {}
    h10 = (summary.get("portfolio_by_horizon") or {}).get("10") or {}
    trade = (summary.get("by_horizon") or {}).get("10") or {}
    return {
        "exists": True,
        "compounded_return": h10.get("total_compounded_return"),
        "avg_portfolio_return": h10.get("avg_portfolio_return"),
        "trade_avg_net_return": trade.get("avg_net_return"),
        "trade_hit_rate": trade.get("hit_rate"),
    }


def portfolio_metrics(path: str) -> dict[str, Any]:
    payload = read_json(path)
    if not payload:
        return {"exists": False}
    summary = payload.get("summary") or {}
    return {
        "exists": True,
        "total_return": summary.get("total_return"),
        "max_drawdown": summary.get("max_drawdown"),
        "max_group_exposure": summary.get("max_group_exposure"),
        "trade_count": summary.get("trade_count"),
    }


def ranking_metrics(path: str) -> dict[str, Any]:
    payload = read_json(path)
    if not payload:
        return {"exists": False}
    summary = payload.get("summary") or {}
    return {
        "exists": True,
        "date_count": summary.get("date_count"),
        "avg_overlap_count": summary.get("avg_overlap_count"),
        "min_overlap_count": summary.get("min_overlap_count"),
    }


def delta(value: Any, baseline: Any) -> float | None:
    if value is None or baseline is None:
        return None
    return float(value) - float(baseline)


def build_candidate(prefix: str, keep: int, baseline: dict[str, Any], date_text: str, artifact_label: str) -> dict[str, Any]:
    candidate_id = f"{prefix}_constrained_k{keep}"
    replay = replay_metrics(f"artifacts/backtest/replay_batch01_{candidate_id}_{artifact_label}_{date_text}.json")
    portfolio_top10 = portfolio_metrics(f"artifacts/backtest/portfolio_batch01_{candidate_id}_{artifact_label}_top10_h10_{date_text}.json")
    ranking = ranking_metrics(f"artifacts/backtest/shadow_rankings_batch01_{prefix}_constrained_k{keep}_{artifact_label}/constrained_shadow_ranking.json")
    return_delta = delta(portfolio_top10.get("total_return"), baseline.get("total_return"))
    drawdown_delta = delta(portfolio_top10.get("max_drawdown"), baseline.get("max_drawdown"))
    decision = "MISSING"
    reason = "artifact missing"
    if replay.get("exists") and portfolio_top10.get("exists") and ranking.get("exists"):
        decision = "MONITOR_ONLY"
        reason = "not better than baseline on return and drawdown"
        if return_delta is not None and drawdown_delta is not None and return_delta >= 0 and drawdown_delta >= 0:
            decision = "READY_FOR_SHADOW_MONITOR"
            reason = "portfolio return is not below baseline and drawdown improved"
    return {
        "candidate_id": candidate_id,
        "ranking": ranking,
        "replay": replay,
        "portfolio_top10_h10": portfolio_top10,
        "portfolio_total_return_delta": return_delta,
        "portfolio_drawdown_delta": drawdown_delta,
        "decision": decision,
        "reason": reason,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    model_path = resolve_path(args.model)
    model_hash_after = sha256(model_path)
    artifact_label = args.artifact_label or args.window
    baseline = portfolio_metrics(f"artifacts/backtest/portfolio_batch01_baseline_{artifact_label}_top10_h10_{args.date}.json")
    baseline_replay = replay_metrics(f"artifacts/backtest/replay_batch01_baseline_{artifact_label}_{args.date}.json")
    candidates = []
    for keep in [6, 7, 8]:
        for prefix in ["feature_group", "sector_context"]:
            candidates.append(build_candidate(prefix, keep, baseline, args.date, artifact_label))
    counts: dict[str, int] = {}
    for item in candidates:
        counts[item["decision"]] = counts.get(item["decision"], 0) + 1
    ready = [item for item in candidates if item["decision"] == "READY_FOR_SHADOW_MONITOR"]
    best = max(
        [item for item in candidates if item["portfolio_top10_h10"].get("total_return") is not None],
        key=lambda item: float(item["portfolio_top10_h10"]["total_return"]),
        default=None,
    )
    errors = []
    if args.model_hash_before != model_hash_after:
        errors.append("models/latest_lgbm.pkl hash changed")
    step_summary = steps_summary(args.steps_log)
    if step_summary.get("failed"):
        errors.append("one or more overnight steps failed")
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "window": args.window,
        "artifact_label": artifact_label,
        "status": "FAILED" if errors else "OK",
        "contract": {
            "research_only": True,
            "does_not_train_model": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_production_ranking": True,
            "promotion_ready": False,
        },
        "steps": step_summary,
        "baseline": {"portfolio_top10_h10": baseline, "replay": baseline_replay},
        "summary": {
            "candidates_tested": len(candidates),
            "decisions": counts,
            "ready_for_shadow_monitor": len(ready),
            "best_candidate": best["candidate_id"] if best else None,
            "best_total_return": (best.get("portfolio_top10_h10") or {}).get("total_return") if best else None,
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
    baseline = payload["baseline"]["portfolio_top10_h10"]
    lines = [
        "# Overnight Training Summary",
        "",
        f"- status: {payload['status']}",
        f"- window: {payload['window']}",
        f"- steps_total: {payload['steps'].get('total')}",
        f"- steps_failed: {payload['steps'].get('failed')}",
        f"- candidates_tested: {payload['summary']['candidates_tested']}",
        f"- ready_for_shadow_monitor: {payload['summary']['ready_for_shadow_monitor']}",
        f"- best_candidate: {payload['summary']['best_candidate']}",
        f"- baseline_return: {pct(baseline.get('total_return'))}",
        f"- baseline_max_drawdown: {pct(baseline.get('max_drawdown'))}",
        f"- models_latest_changed: {payload['guard_status']['models_latest_changed']}",
        f"- promotion_ready: {payload['guard_status']['promotion_ready']}",
        "",
        "| Candidate | Decision | Dates | Avg Overlap | Return | Return Delta | Max DD | DD Delta | Max Group |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in payload["candidates"]:
        portfolio = item["portfolio_top10_h10"]
        ranking = item["ranking"]
        lines.append(
            "| {candidate} | {decision} | {dates} | {overlap} | {ret} | {ret_delta} | {dd} | {dd_delta} | {group} |".format(
                candidate=item["candidate_id"],
                decision=item["decision"],
                dates=ranking.get("date_count"),
                overlap=ranking.get("avg_overlap_count"),
                ret=pct(portfolio.get("total_return")),
                ret_delta=pct(item.get("portfolio_total_return_delta")),
                dd=pct(portfolio.get("max_drawdown")),
                dd_delta=pct(item.get("portfolio_drawdown_delta")),
                group=pct(portfolio.get("max_group_exposure")),
            )
        )
    if payload["errors"]:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {item}" for item in payload["errors"])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = resolve_path(args.output) if args.output else PROJECT_ROOT / "artifacts" / "model_experiments" / f"overnight_training_summary_{args.date}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output), "errors": payload["errors"]}, ensure_ascii=False))
    return 1 if payload["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
