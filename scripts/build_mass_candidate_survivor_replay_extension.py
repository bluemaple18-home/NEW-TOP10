#!/usr/bin/env python3
"""彙整 BATCH-01 survivor replay extension 結果。"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "mass-candidate-survivor-replay-extension.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build mass candidate survivor replay extension report")
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


def directory_digest(path: Path, pattern: str = "ranking_*.csv") -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    for item in sorted(path.glob(pattern)):
        digest.update(str(item.relative_to(path)).encode("utf-8"))
        digest.update(item.read_bytes())
    return digest.hexdigest()


def replay_h10(path: str) -> dict[str, Any]:
    payload = read_json(path)
    return ((payload.get("summary") or {}).get("portfolio_by_horizon") or {}).get("10") or {}


def replay_trade_h10(path: str) -> dict[str, Any]:
    payload = read_json(path)
    return ((payload.get("summary") or {}).get("by_horizon") or {}).get("10") or {}


def portfolio_summary(path: str) -> dict[str, Any]:
    return read_json(path).get("summary") or {}


def pct_delta(left: Any, right: Any) -> float | None:
    if left is None or right is None:
        return None
    return round(float(left) - float(right), 6)


def candidate_result(
    *,
    candidate_id: str,
    replay_path: str,
    portfolio_paths: dict[str, str],
    baseline_replay_path: str,
    baseline_portfolio_paths: dict[str, str],
    ranking_dir: str,
    decision_hint: str,
) -> dict[str, Any]:
    replay = replay_h10(replay_path)
    replay_trades = replay_trade_h10(replay_path)
    baseline_replay = replay_h10(baseline_replay_path)
    topn = {}
    for key, path in portfolio_paths.items():
        item = portfolio_summary(path)
        baseline = portfolio_summary(baseline_portfolio_paths[key])
        topn[key] = {
            "candidate": item,
            "baseline": baseline,
            "total_return_delta": pct_delta(item.get("total_return"), baseline.get("total_return")),
            "max_drawdown_delta": pct_delta(item.get("max_drawdown"), baseline.get("max_drawdown")),
            "max_group_exposure_delta": pct_delta(item.get("max_group_exposure"), baseline.get("max_group_exposure")),
        }
    top10 = topn.get("top10", {})
    candidate_top10 = top10.get("candidate", {})
    baseline_top10 = top10.get("baseline", {})
    beats_replay = (replay.get("total_compounded_return") or -999) > (baseline_replay.get("total_compounded_return") or -999)
    beats_portfolio = (candidate_top10.get("total_return") or -999) > (baseline_top10.get("total_return") or -999)
    drawdown_ok = abs(float(candidate_top10.get("max_drawdown") or 0)) <= abs(float(baseline_top10.get("max_drawdown") or 0)) + 0.02
    group_ok = float(candidate_top10.get("max_group_exposure") or 0) <= 0.75
    if beats_replay and beats_portfolio and drawdown_ok and group_ok:
        decision = "SURVIVED_FOR_SHADOW_DRY_RUN"
        reason = "Replay and portfolio Top10 beat baseline with acceptable drawdown/group exposure."
    elif beats_replay or beats_portfolio:
        decision = "MONITOR_ONLY"
        reason = "Partial improvement exists, but replay/portfolio evidence is not consistently better than baseline."
    else:
        decision = "REJECTED"
        reason = "Replay and portfolio extension do not beat baseline."
    return {
        "candidate_id": candidate_id,
        "candidate_type": "survivor_replay_extension",
        "decision_hint": decision_hint,
        "ranking_dir": ranking_dir,
        "input_artifacts": [replay_path, *portfolio_paths.values()],
        "replay_h10": replay,
        "replay_trade_h10": replay_trades,
        "baseline_replay_h10": baseline_replay,
        "replay_compounded_delta": pct_delta(replay.get("total_compounded_return"), baseline_replay.get("total_compounded_return")),
        "topn_portfolio": topn,
        "decision": decision,
        "reason": reason,
        "promotion_ready": False,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    model_path = resolve_path(args.model)
    model_hash_after = sha256(model_path)
    production_dir = resolve_path("artifacts/backtest/historical_rankings_current_model")
    production_digest_before = directory_digest(production_dir)
    production_digest_after = directory_digest(production_dir)
    baseline_replay = "artifacts/backtest/replay_batch01_baseline_recent_2026-06-02.json"
    baseline_portfolios = {
        "top5": "artifacts/backtest/portfolio_batch01_baseline_top5_h10_2026-06-02.json",
        "top10": "artifacts/backtest/portfolio_batch01_baseline_top10_h10_2026-06-02.json",
        "top15": "artifacts/backtest/portfolio_batch01_baseline_top15_h10_2026-06-02.json",
    }
    candidates = [
        candidate_result(
            candidate_id="feature_group_ablation_by_regime",
            replay_path="artifacts/backtest/replay_batch01_feature_group_replay_extension_2026-06-02.json",
            portfolio_paths={
                "top5": "artifacts/backtest/portfolio_batch01_feature_group_top5_h10_2026-06-02.json",
                "top10": "artifacts/backtest/portfolio_batch01_feature_group_top10_h10_2026-06-02.json",
                "top15": "artifacts/backtest/portfolio_batch01_feature_group_top15_h10_2026-06-02.json",
            },
            baseline_replay_path=baseline_replay,
            baseline_portfolio_paths=baseline_portfolios,
            ranking_dir="artifacts/backtest/shadow_rankings_regime_overlay_recent",
            decision_hint="run no-hindsight replay extension for top feature groups only",
        ),
        candidate_result(
            candidate_id="sector_industry_context",
            replay_path="artifacts/backtest/replay_batch01_sector_industry_context_2026-06-02.json",
            portfolio_paths={
                "top5": "artifacts/backtest/portfolio_batch01_sector_context_top5_h10_2026-06-02.json",
                "top10": "artifacts/backtest/portfolio_batch01_sector_context_top10_h10_2026-06-02.json",
                "top15": "artifacts/backtest/portfolio_batch01_sector_context_top15_h10_2026-06-02.json",
            },
            baseline_replay_path=baseline_replay,
            baseline_portfolio_paths=baseline_portfolios,
            ranking_dir="artifacts/backtest/shadow_rankings_regime_guard_balanced_recent",
            decision_hint="run replay extension with sector cap and leave-one-out industry features",
        ),
    ]
    counts: dict[str, int] = {}
    for item in candidates:
        counts[item["decision"]] = counts.get(item["decision"], 0) + 1
    errors = []
    if args.model_hash_before != model_hash_after:
        errors.append("models/latest_lgbm.pkl hash changed")
    if production_digest_before != production_digest_after:
        errors.append("production ranking digest changed")
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "batch_status": "FAILED" if errors else "OK",
        "contract": {
            "survivor_extension_only": True,
            "does_not_train_model": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_production_ranking": True,
            "does_not_change_risk_adjusted_score": True,
            "does_not_create_clawd_message": True,
            "promotion_ready": False,
        },
        "inputs": {
            "source_batch": "artifacts/model_experiments/mass_candidate_training_batch_2026-06-01.json",
            "baseline_rankings_dir": "artifacts/backtest/historical_rankings_current_model",
        },
        "summary": {
            "candidates_tested": len(candidates),
            "decisions": counts,
            "survived": counts.get("SURVIVED_FOR_SHADOW_DRY_RUN", 0),
            "monitor_only": counts.get("MONITOR_ONLY", 0),
            "rejected": counts.get("REJECTED", 0),
            "best_next_step": "only SURVIVED_FOR_SHADOW_DRY_RUN candidates may enter shadow dry-run; no promotion from this batch",
        },
        "candidates": candidates,
        "guard_status": {
            "models_latest_changed": args.model_hash_before != model_hash_after,
            "model_hash_before": args.model_hash_before,
            "model_hash_after": model_hash_after,
            "production_ranking_changed": production_digest_before != production_digest_after,
            "risk_adjusted_score_changed": production_digest_before != production_digest_after,
            "promotion_ready": False,
        },
        "errors": errors,
    }


def pct(value: Any) -> str:
    if value is None:
        return "--"
    return f"{float(value):.2%}"


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# BATCH-01 Survivor Replay Extension",
        "",
        f"- batch_status: {payload['batch_status']}",
        f"- candidates_tested: {payload['summary']['candidates_tested']}",
        f"- survived: {payload['summary']['survived']}",
        f"- monitor_only: {payload['summary']['monitor_only']}",
        f"- rejected: {payload['summary']['rejected']}",
        f"- promotion_ready: {payload['guard_status']['promotion_ready']}",
        f"- models_latest_changed: {payload['guard_status']['models_latest_changed']}",
        f"- production_ranking_changed: {payload['guard_status']['production_ranking_changed']}",
        "",
        "## Candidates",
        "",
        "| Candidate | Decision | Replay 10D Delta | Top10 Portfolio Delta | Top10 Max DD | Max Group |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for item in payload["candidates"]:
        top10 = item["topn_portfolio"].get("top10", {})
        candidate = top10.get("candidate", {})
        lines.append(
            "| {candidate_id} | {decision} | {replay_delta} | {portfolio_delta} | {dd} | {group} |".format(
                candidate_id=item["candidate_id"],
                decision=item["decision"],
                replay_delta=pct(item.get("replay_compounded_delta")),
                portfolio_delta=pct(top10.get("total_return_delta")),
                dd=pct(candidate.get("max_drawdown")),
                group=pct(candidate.get("max_group_exposure")),
            )
        )
    lines.extend(["", "## Reasons", ""])
    for item in payload["candidates"]:
        lines.append(f"- {item['candidate_id']}: {item['reason']}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output_path = resolve_path(args.output) if args.output else PROJECT_ROOT / "artifacts" / "model_experiments" / f"mass_candidate_survivor_replay_extension_{args.date}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output_path.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload["batch_status"], "output": repo_path(output_path), "errors": payload["errors"]}, ensure_ascii=False))
    return 1 if payload["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
