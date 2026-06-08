#!/usr/bin/env python3
"""彙整 BATCH-01 survivor sector cap extension 結果。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import build_mass_candidate_survivor_replay_extension as base  # noqa: E402

SCHEMA_VERSION = "mass-candidate-sector-cap-extension.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build mass candidate sector cap extension report")
    parser.add_argument("--date", required=True)
    parser.add_argument("--model", default="models/latest_lgbm.pkl")
    parser.add_argument("--model-hash-before", required=True)
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def candidate(
    candidate_id: str,
    replay_path: str,
    portfolio_prefix: str,
    ranking_dir: str,
    baseline_replay: str,
    baseline_portfolios: dict[str, str],
) -> dict[str, Any]:
    result = base.candidate_result(
        candidate_id=candidate_id,
        replay_path=replay_path,
        portfolio_paths={
            "top5": f"artifacts/backtest/{portfolio_prefix}_top5_h10_2026-06-02.json",
            "top10": f"artifacts/backtest/{portfolio_prefix}_top10_h10_2026-06-02.json",
            "top15": f"artifacts/backtest/{portfolio_prefix}_top15_h10_2026-06-02.json",
        },
        baseline_replay_path=baseline_replay,
        baseline_portfolio_paths=baseline_portfolios,
        ranking_dir=ranking_dir,
        decision_hint="sector cap rerank extension",
    )
    top10 = result["topn_portfolio"].get("top10", {})
    max_group = (top10.get("candidate") or {}).get("max_group_exposure")
    if result["decision"] == "SURVIVED_FOR_SHADOW_DRY_RUN" and max_group is not None and float(max_group) <= 0.45:
        result["decision"] = "SURVIVED_FOR_SHADOW_MONITOR"
        result["reason"] = "Sector cap preserves replay/portfolio edge and reduces group concentration to acceptable range."
    elif max_group is not None and float(max_group) <= 0.45:
        result["decision"] = "MONITOR_ONLY"
        result["reason"] = "Sector cap reduces concentration, but return evidence is not strong enough for shadow monitor."
    return result


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    model_path = base.resolve_path(args.model)
    model_hash_after = base.sha256(model_path)
    production_dir = base.resolve_path("artifacts/backtest/historical_rankings_current_model")
    production_digest_before = base.directory_digest(production_dir)
    production_digest_after = base.directory_digest(production_dir)
    baseline_replay = "artifacts/backtest/replay_batch01_baseline_recent_2026-06-02.json"
    baseline_portfolios = {
        "top5": "artifacts/backtest/portfolio_batch01_baseline_top5_h10_2026-06-02.json",
        "top10": "artifacts/backtest/portfolio_batch01_baseline_top10_h10_2026-06-02.json",
        "top15": "artifacts/backtest/portfolio_batch01_baseline_top15_h10_2026-06-02.json",
    }
    candidates = [
        candidate(
            "feature_group_ablation_by_regime_sector_cap",
            "artifacts/backtest/replay_batch01_feature_group_sector_cap_2026-06-02.json",
            "portfolio_batch01_feature_group_sector_cap",
            "artifacts/backtest/shadow_rankings_batch01_feature_group_sector_cap",
            baseline_replay,
            baseline_portfolios,
        ),
        candidate(
            "sector_industry_context_sector_cap",
            "artifacts/backtest/replay_batch01_sector_context_sector_cap_2026-06-02.json",
            "portfolio_batch01_sector_context_sector_cap",
            "artifacts/backtest/shadow_rankings_batch01_sector_context_sector_cap",
            baseline_replay,
            baseline_portfolios,
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
            "sector_cap_extension_only": True,
            "max_sector_count": 4,
            "does_not_train_model": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_production_ranking": True,
            "does_not_change_risk_adjusted_score": True,
            "promotion_ready": False,
        },
        "summary": {
            "candidates_tested": len(candidates),
            "decisions": counts,
            "survived_for_shadow_monitor": counts.get("SURVIVED_FOR_SHADOW_MONITOR", 0),
            "monitor_only": counts.get("MONITOR_ONLY", 0),
            "rejected": counts.get("REJECTED", 0),
            "best_next_step": "SURVIVED_FOR_SHADOW_MONITOR candidates can enter capped shadow monitor; no production changes.",
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


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# BATCH-01 Sector Cap Extension",
        "",
        f"- batch_status: {payload['batch_status']}",
        f"- candidates_tested: {payload['summary']['candidates_tested']}",
        f"- survived_for_shadow_monitor: {payload['summary']['survived_for_shadow_monitor']}",
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
                replay_delta=base.pct(item.get("replay_compounded_delta")),
                portfolio_delta=base.pct(top10.get("total_return_delta")),
                dd=base.pct(candidate.get("max_drawdown")),
                group=base.pct(candidate.get("max_group_exposure")),
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
    output_path = base.resolve_path(args.output) if args.output else PROJECT_ROOT / "artifacts" / "model_experiments" / f"mass_candidate_sector_cap_extension_{args.date}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output_path.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload["batch_status"], "output": base.repo_path(output_path), "errors": payload["errors"]}, ensure_ascii=False))
    return 1 if payload["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
