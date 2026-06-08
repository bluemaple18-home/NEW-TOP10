#!/usr/bin/env python3
"""彙整 overnight 風控矩陣結果。"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "overnight-risk-matrix-summary.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build overnight risk matrix summary")
    parser.add_argument("--date", required=True)
    parser.add_argument("--label", default="half_year_dense")
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


def matrix(path: str) -> dict[str, Any]:
    payload = read_json(path)
    return {
        "path": path,
        "exists": bool(payload),
        "summary": payload.get("summary") or {},
        "scenarios": payload.get("scenarios") or [],
    }


def pick_best(rows: list[dict[str, Any]], baseline_return: float | None, baseline_drawdown: float | None) -> dict[str, Any]:
    valid = [row for row in rows if row.get("total_return") is not None and row.get("max_drawdown") is not None]
    if baseline_return is None or baseline_drawdown is None:
        return {}
    passing = [
        row
        for row in valid
        if float(row["total_return"]) >= baseline_return and float(row["max_drawdown"]) >= baseline_drawdown
    ]
    if passing:
        best = max(passing, key=lambda row: float(row.get("score") or -999))
        return {"decision": "READY_FOR_SHADOW_MONITOR", "scenario": best, "reason": "return and drawdown both beat baseline"}
    lower_dd = [row for row in valid if float(row["max_drawdown"]) >= baseline_drawdown]
    if lower_dd:
        best = max(lower_dd, key=lambda row: float(row.get("total_return") or -999))
        return {"decision": "RISK_REDUCED_MONITOR_ONLY", "scenario": best, "reason": "drawdown improved but return is below baseline"}
    best = max(valid, key=lambda row: float(row.get("score") or -999), default={})
    return {"decision": "MONITOR_ONLY", "scenario": best, "reason": "no scenario beats baseline drawdown"}


def candidate(label: str, path: str, baseline: dict[str, Any]) -> dict[str, Any]:
    item = matrix(path)
    baseline_rows = baseline.get("scenarios") or []
    baseline_best = baseline_rows[0] if baseline_rows else {}
    baseline_return = baseline_best.get("total_return")
    baseline_drawdown = baseline_best.get("max_drawdown")
    decision = pick_best(item["scenarios"], baseline_return, baseline_drawdown)
    return {
        "candidate_id": label,
        "matrix": item,
        "best_vs_baseline": decision,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    model_hash_after = sha256(resolve_path(args.model))
    baseline = matrix(f"artifacts/backtest/strategy_matrix_baseline_{args.label}_{args.date}.json")
    candidates = [
        candidate(
            "sector_context_k7",
            f"artifacts/backtest/strategy_matrix_sector_context_k7_{args.label}_{args.date}.json",
            baseline,
        ),
        candidate(
            "feature_group_k7",
            f"artifacts/backtest/strategy_matrix_feature_group_k7_{args.label}_{args.date}.json",
            baseline,
        ),
        candidate(
            "feature_group_k8",
            f"artifacts/backtest/strategy_matrix_feature_group_k8_{args.label}_{args.date}.json",
            baseline,
        ),
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
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "label": args.label,
        "status": "FAILED" if errors else "OK",
        "contract": {
            "research_only": True,
            "does_not_train_model": True,
            "does_not_write_models_latest_lgbm": True,
            "promotion_ready": False,
        },
        "baseline": baseline,
        "summary": {
            "candidates_tested": len(candidates),
            "decisions": counts,
            "ready_for_shadow_monitor": counts.get("READY_FOR_SHADOW_MONITOR", 0),
            "risk_reduced_monitor_only": counts.get("RISK_REDUCED_MONITOR_ONLY", 0),
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
    baseline_best = ((payload["baseline"].get("scenarios") or [{}])[0])
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
        lines.append(
            "| {candidate} | {decision} | {scenario_id} | {ret} | {dd} | {win} | {reason} |".format(
                candidate=item["candidate_id"],
                decision=decision.get("decision"),
                scenario_id=scenario.get("scenario_id"),
                ret=pct(scenario.get("total_return")),
                dd=pct(scenario.get("max_drawdown")),
                win=pct(scenario.get("win_rate")),
                reason=decision.get("reason"),
            )
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = resolve_path(args.output) if args.output else PROJECT_ROOT / "artifacts" / "model_experiments" / f"overnight_risk_matrix_summary_{args.date}_{args.label}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output), "errors": payload["errors"]}, ensure_ascii=False))
    return 1 if payload["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
