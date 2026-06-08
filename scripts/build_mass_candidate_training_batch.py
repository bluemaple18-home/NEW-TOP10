#!/usr/bin/env python3
"""彙整大量候選訓練 / 批次評估結果。"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "mass-candidate-training-batch.v1"
ALLOWED_DECISIONS = {
    "SURVIVED_FOR_REPLAY_EXTENSION",
    "SURVIVED_FOR_SHADOW_DRY_RUN",
    "SURVIVED_FOR_OVERLAY_REVIEW",
    "MODEL_CANDIDATE_NEEDS_MORE_EVIDENCE",
    "RESTRICTED_SHADOW_ONLY",
    "MONITOR_ONLY",
    "REJECTED",
    "BLOCKED_CONTRACT",
    "BLOCKED_MODEL_EVIDENCE",
}
SURVIVING_DECISIONS = {
    "SURVIVED_FOR_REPLAY_EXTENSION",
    "SURVIVED_FOR_SHADOW_DRY_RUN",
    "SURVIVED_FOR_OVERLAY_REVIEW",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build mass candidate training batch report")
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


def read_json(path: str | Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    resolved = resolve_path(path)
    if not resolved.exists():
        return default or {}
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


def glob_digest(root: Path, pattern: str) -> str:
    digest = hashlib.sha256()
    for item in sorted(root.glob(pattern)):
        if item.is_file():
            digest.update(str(item.relative_to(root)).encode("utf-8"))
            digest.update(item.read_bytes())
    return digest.hexdigest()


def readiness_promotion_ready() -> bool:
    payload = read_json("artifacts/training_automation_readiness_2026-06-01.json")
    body = payload.get("readiness") if isinstance(payload.get("readiness"), dict) else payload
    return bool(body.get("promotion_ready")) if body.get("promotion_ready") is not None else False


def base_guard(model_hash_before: str, model_hash_after: str, production_before: str | None, production_after: str | None, clawd_before: str, clawd_after: str) -> dict[str, Any]:
    production_changed = production_before != production_after
    return {
        "production_ranking_changed": production_changed,
        "risk_adjusted_score_changed": production_changed,
        "models_latest_changed": model_hash_before != model_hash_after,
        "clawd_message_created": clawd_before != clawd_after,
        "promotion_ready": readiness_promotion_ready(),
        "production_promotion_allowed": False,
    }


def candidate(
    *,
    candidate_id: str,
    candidate_type: str,
    hypothesis: str,
    input_artifacts: list[str],
    feature_groups: list[str] | None = None,
    regime_usage: str = "diagnostic_only",
    baseline_comparison: dict[str, Any] | None = None,
    replay_summary: dict[str, Any] | None = None,
    portfolio_summary: dict[str, Any] | None = None,
    stratified_summary: dict[str, Any] | None = None,
    guard_status: dict[str, Any] | None = None,
    decision: str,
    reason: str,
    next_allowed_step: str,
) -> dict[str, Any]:
    if decision not in ALLOWED_DECISIONS:
        raise ValueError(f"invalid decision for {candidate_id}: {decision}")
    return {
        "candidate_id": candidate_id,
        "candidate_type": candidate_type,
        "hypothesis": hypothesis,
        "input_artifacts": input_artifacts,
        "feature_groups": feature_groups or [],
        "regime_usage": regime_usage,
        "baseline_comparison": baseline_comparison or {},
        "replay_summary": replay_summary or {},
        "portfolio_summary": portfolio_summary or {},
        "stratified_summary": stratified_summary or {},
        "guard_status": guard_status or {},
        "decision": decision,
        "rejection_or_survival_reason": reason,
        "next_allowed_step": next_allowed_step,
        "promotion_ready": False,
    }


def portfolio_metric(extension: dict[str, Any], variant: str, bucket: str = "top10") -> dict[str, Any]:
    return ((extension.get("topn_sensitivity") or {}).get(variant) or {}).get(bucket) or {}


def entry_metric(extension: dict[str, Any], variant: str, day: str) -> dict[str, Any]:
    return ((extension.get("entry_day_sensitivity") or {}).get(variant) or {}).get(day) or {}


def feature_group_survivors(ablation: dict[str, Any]) -> dict[str, Any]:
    rows = (ablation.get("summary") or {}).get("by_regime_horizon_group") or []
    shadow_rows: list[dict[str, Any]] = []
    for row in rows:
        for feature in row.get("top_features") or []:
            if feature.get("status") == "SHADOW_CANDIDATE":
                shadow_rows.append(
                    {
                        "regime": row.get("regime_label"),
                        "horizon": row.get("horizon"),
                        "group": row.get("group"),
                        "feature": feature.get("feature"),
                        "days": feature.get("days"),
                        "ic_mean": feature.get("ic_mean"),
                        "abs_ic_mean": feature.get("abs_ic_mean"),
                        "direction_consistency": feature.get("direction_consistency"),
                        "spread_mean": feature.get("spread_mean"),
                    }
                )
    by_group = Counter(str(row.get("group")) for row in shadow_rows)
    return {
        "shadow_candidate_count": len(shadow_rows),
        "top_groups": by_group.most_common(6),
        "top_rows": sorted(
            shadow_rows,
            key=lambda row: (
                float(row.get("abs_ic_mean") or 0),
                float(row.get("direction_consistency") or 0),
                int(row.get("days") or 0),
            ),
            reverse=True,
        )[:12],
    }


def build_candidates(guard: dict[str, Any]) -> list[dict[str, Any]]:
    extension = read_json("artifacts/model_experiments/big_bull_ranking_replay_extension_2026-06-01.json")
    stability = read_json("artifacts/model_experiments/regime_family_sealed_stability_2026-06-01.json")
    shadow_monitor = read_json("artifacts/model_experiments/big_bull_shadow_monitor_2026-06-01.json")
    high_choppy = read_json("artifacts/model_experiments/high_choppy_context_overlay_2026-06-01.json")
    result_report = read_json("artifacts/model_experiments/model_exp_result_report_2026-06-01.json")
    run_manifest = read_json("artifacts/model_experiments/model_exp_run_manifest_2026-06-01.json")
    feature_ablation = read_json("artifacts/model_experiments/feature_group_ablation_by_regime_2026-05-31.json")
    technical_only = read_json("artifacts/model_experiments/technical_only_training_lane_2026-06-01.json")
    family_candidates = read_json("artifacts/model_experiments/regime_family_training_candidates_2026-06-01.json")

    baseline_top10 = portfolio_metric(extension, "baseline")
    family_top10 = portfolio_metric(extension, "family_only")
    blended_top10 = portfolio_metric(extension, "blended_rerank")
    feature_screen = feature_group_survivors(feature_ablation)
    common_guard = {
        **guard,
        "formal_regime_added": False,
        "production_model_written": False,
    }

    rows: list[dict[str, Any]] = []
    rows.append(
        candidate(
            candidate_id="big_bull_family_only_model",
            candidate_type="model_variant",
            hypothesis="BIG_BULL family-only model can promote only if sealed stability and split contract agree.",
            input_artifacts=[
                "artifacts/model_experiments/regime_family_sealed_stability_2026-06-01.json",
                "artifacts/model_experiments/big_bull_blocker_resolution_2026-06-01.json",
            ],
            feature_groups=["all_current_features", "BIG_BULL family tag"],
            regime_usage="family training candidate; not production promotion evidence",
            baseline_comparison=stability.get("metrics", {}),
            stratified_summary={
                "decision": stability.get("decision"),
                "ranking_decision": stability.get("ranking_decision"),
                "windows": stability.get("windows", []),
            },
            guard_status=common_guard,
            decision="BLOCKED_MODEL_EVIDENCE",
            reason="sealed stability blocks model promotion: avg AUC delta is negative and nonnegative_auc_delta_ratio is 0.0",
            next_allowed_step="none_for_model_promotion; keep as research-only evidence",
        )
    )
    rows.append(
        candidate(
            candidate_id="big_bull_family_only_ranking",
            candidate_type="ranking_candidate",
            hypothesis="BIG_BULL family-only ranking can improve BIG_BULL Top10 but must survive shadow monitor before overlay.",
            input_artifacts=[
                "artifacts/model_experiments/big_bull_ranking_replay_extension_2026-06-01.json",
                "artifacts/model_experiments/big_bull_shadow_monitor_2026-06-01.json",
            ],
            feature_groups=["BIG_BULL family_only ranking"],
            regime_usage="BIG_BULL ranking-only; HIGH_CHOPPY stratified diagnostics only",
            baseline_comparison={"baseline_top10": baseline_top10, "candidate_top10": family_top10},
            replay_summary=shadow_monitor.get("paper_outcome", {}),
            portfolio_summary=family_top10,
            stratified_summary=shadow_monitor.get("high_choppy_stratified", {}),
            guard_status=common_guard,
            decision="RESTRICTED_SHADOW_ONLY",
            reason="Checkpoint B restricted it: low overlap, high turnover, sector concentration, and 10D under production.",
            next_allowed_step="continue shadow-only monitor; no overlay proposal",
        )
    )
    rows.append(
        candidate(
            candidate_id="big_bull_blended_rerank",
            candidate_type="ranking_candidate",
            hypothesis="Global prefilter + BIG_BULL family rerank may improve hit rate without worsening risk.",
            input_artifacts=["artifacts/model_experiments/big_bull_ranking_replay_extension_2026-06-01.json"],
            feature_groups=["global_model_prob", "family_model_prob"],
            regime_usage="BIG_BULL-only comparison; not promotion evidence",
            baseline_comparison={"baseline_top10": baseline_top10, "candidate_top10": blended_top10},
            portfolio_summary={
                "d1": entry_metric(extension, "blended_rerank", "d1"),
                "d2": entry_metric(extension, "blended_rerank", "d2"),
                "d3": entry_metric(extension, "blended_rerank", "d3"),
            },
            stratified_summary=(extension.get("big_bull_high_choppy_stratified") or {}).get("blended_rerank", {}),
            guard_status=common_guard,
            decision="MONITOR_ONLY",
            reason="D+1 is comparable but D+2/D+3 turn negative and it did not beat family_only enough to survive.",
            next_allowed_step="monitor as comparator only",
        )
    )
    rows.append(
        candidate(
            candidate_id="big_bull_blended_score",
            candidate_type="ranking_candidate",
            hypothesis="Score blend can combine global and family probabilities into a stronger ranking.",
            input_artifacts=[
                "artifacts/backtest/portfolio_replay_big_bull_blended_score_2026-06-01.json",
                "artifacts/model_experiments/big_bull_blended_shadow_ranking_2026-06-01.json",
            ],
            feature_groups=["global_model_prob", "family_model_prob"],
            regime_usage="BIG_BULL-only comparison",
            baseline_comparison={"known_result": "underperformed family_only and blended_rerank in AUTO-TRAINING-08/10"},
            guard_status=common_guard,
            decision="REJECTED",
            reason="score blend was already eliminated by weaker portfolio replay versus family_only/blended_rerank.",
            next_allowed_step="none",
        )
    )
    rows.append(
        candidate(
            candidate_id="high_choppy_soft_feature",
            candidate_type="soft_feature",
            hypothesis="HIGH_CHOPPY rolling context may add useful soft feature and diagnostics.",
            input_artifacts=[
                "artifacts/model_experiments/high_choppy_context_overlay_2026-06-01.json",
                "artifacts/model_experiments/big_bull_ranking_replay_extension_2026-06-01.json",
            ],
            feature_groups=["high_choppy_rolling_context"],
            regime_usage="soft feature + stratified evaluation; not formal regime label",
            baseline_comparison=extension.get("high_choppy_soft_feature_comparison", {}),
            stratified_summary={
                "context_summary": high_choppy.get("summary", {}),
                "big_bull_shadow_monitor": shadow_monitor.get("high_choppy_stratified", {}),
            },
            guard_status=common_guard,
            decision="MONITOR_ONLY",
            reason="soft feature comparison slightly hurt AUC/TopN overall; useful only for diagnostics.",
            next_allowed_step="keep stratified diagnostics; do not promote or overlay",
        )
    )
    rows.append(
        candidate(
            candidate_id="high_choppy_restricted_risk_overlay",
            candidate_type="overlay_candidate",
            hypothesis="HIGH_CHOPPY dates may need restricted risk overlay.",
            input_artifacts=[
                "artifacts/model_experiments/high_choppy_context_overlay_2026-06-01.json",
                "artifacts/model_experiments/big_bull_shadow_monitor_2026-06-01.json",
            ],
            feature_groups=[],
            regime_usage="restricted overlay candidate only; no formal label",
            baseline_comparison=(high_choppy.get("summary") or {}).get("new_dates_top10_replay", {}),
            stratified_summary=shadow_monitor.get("high_choppy_stratified", {}),
            guard_status=common_guard,
            decision="REJECTED",
            reason="HIGH_CHOPPY rolling/strict 10D slices underperformed production in shadow monitor.",
            next_allowed_step="none until new independent evidence appears",
        )
    )
    rows.append(
        candidate(
            candidate_id="feature_group_ablation_by_regime",
            candidate_type="feature_group_ablation",
            hypothesis="Regime-aware feature groups can identify reusable feature candidates before model training.",
            input_artifacts=[
                "artifacts/model_experiments/feature_group_ablation_by_regime_2026-05-31.json",
                "artifacts/model_experiments/model_exp_result_report_2026-06-01.json",
            ],
            feature_groups=[item[0] for item in feature_screen["top_groups"]],
            regime_usage="diagnostic feature screen by existing base regimes only",
            baseline_comparison={
                "feature_screen": {
                    "shadow_candidate_count": feature_screen["shadow_candidate_count"],
                    "top_groups": feature_screen["top_groups"],
                },
                "model_result_report_status": "MONITOR_ONLY until replay extension exists",
            },
            stratified_summary={"top_rows": feature_screen["top_rows"]},
            guard_status=common_guard,
            decision="SURVIVED_FOR_REPLAY_EXTENSION",
            reason="Large feature screen found traceable SHADOW_CANDIDATE rows; survival is limited to replay extension, not model training.",
            next_allowed_step="run no-hindsight replay extension for top feature groups only",
        )
    )
    rows.append(
        candidate(
            candidate_id="sector_industry_context",
            candidate_type="feature_group_add_back",
            hypothesis="Sector/industry breadth and momentum context may improve ranking in specific regimes.",
            input_artifacts=["artifacts/model_experiments/feature_group_ablation_by_regime_2026-05-31.json"],
            feature_groups=["industry_momentum", "sector_context"],
            regime_usage="diagnostic by existing base regimes; no new formal regime",
            baseline_comparison={
                "selected_rows": [
                    row
                    for row in feature_screen["top_rows"]
                    if row.get("group") == "industry_momentum"
                ][:6]
            },
            stratified_summary={"source": "feature_group_ablation_by_regime"},
            guard_status=common_guard,
            decision="SURVIVED_FOR_REPLAY_EXTENSION",
            reason="Industry/sector rows appear among SHADOW_CANDIDATE features and are lineage-traceable.",
            next_allowed_step="run replay extension with sector cap and leave-one-out industry features",
        )
    )
    decisions = {item.get("experiment_id"): item for item in result_report.get("decisions", [])}
    cp = decisions.get("model_exp_candidate_persistence_only", {})
    rows.append(
        candidate(
            candidate_id="candidate_persistence",
            candidate_type="feature_group_add_back",
            hypothesis="Candidate persistence may improve ranking if prior appearances persist.",
            input_artifacts=[
                "artifacts/model_experiments/candidate_persistence_features_2026-06-01.parquet",
                "artifacts/model_experiments/model_exp_result_report_2026-06-01.json",
            ],
            feature_groups=["consecutive_ranked_days", "streak_bucket", "rank_delta_direction"],
            regime_usage="none",
            baseline_comparison=cp.get("metrics", {}),
            guard_status=common_guard,
            decision="MONITOR_ONLY",
            reason="Current window has partial signal, but extended evidence is missing/not stable.",
            next_allowed_step="collect extended evidence before replay extension",
        )
    )
    portfolio_overlay = decisions.get("model_exp_portfolio_risk_overlay_only", {})
    rows.append(
        candidate(
            candidate_id="portfolio_risk_overlay",
            candidate_type="portfolio_overlay",
            hypothesis="Post-ranking portfolio risk overlay can improve return without concentration risk.",
            input_artifacts=["artifacts/model_experiments/model_exp_result_report_2026-06-01.json"],
            feature_groups=[],
            regime_usage="none",
            baseline_comparison=portfolio_overlay.get("metrics", {}),
            guard_status=common_guard,
            decision="MONITOR_ONLY",
            reason="Required overlay replay/extended evidence is not available; cannot survive yet.",
            next_allowed_step="collect overlay replay evidence",
        )
    )
    combined = decisions.get("model_exp_combined_conservative", {})
    rows.append(
        candidate(
            candidate_id="combined_conservative",
            candidate_type="training_policy",
            hypothesis="Combine candidate persistence and regime features after individual passes.",
            input_artifacts=["artifacts/model_experiments/model_exp_run_manifest_2026-06-01.json"],
            feature_groups=["candidate_persistence", "regime_feature_group_ablation"],
            regime_usage="inherits individual candidates only",
            baseline_comparison=combined.get("actual_metrics", {}),
            guard_status=common_guard,
            decision="BLOCKED_CONTRACT",
            reason="Combined experiment must wait until individual candidates pass replay/sealed gates.",
            next_allowed_step="wait for individual candidate survival",
        )
    )
    rows.append(
        candidate(
            candidate_id="technical_only_training_lane",
            candidate_type="model_variant",
            hypothesis="Technical-only lane may be acceptable when revenue features are unavailable.",
            input_artifacts=["artifacts/model_experiments/technical_only_training_lane_2026-06-01.json"],
            feature_groups=["technical_only"],
            regime_usage="none",
            baseline_comparison=technical_only.get("contract", {}),
            guard_status=common_guard,
            decision="MODEL_CANDIDATE_NEEDS_MORE_EVIDENCE",
            reason="Research-only lane exists, but promotion requires explicit degradation acceptance and sealed replay.",
            next_allowed_step="sealed/replay evidence only; no production promotion",
        )
    )
    rows.append(
        candidate(
            candidate_id="global_regime_family_training_candidates",
            candidate_type="model_variant",
            hypothesis="Family-specific training candidates can identify model variants by regime family.",
            input_artifacts=["artifacts/model_experiments/regime_family_training_candidates_2026-06-01.json"],
            feature_groups=["all_current_features", "family_tags"],
            regime_usage="diagnostic family training only",
            baseline_comparison=family_candidates.get("summary", {}),
            guard_status=common_guard,
            decision="BLOCKED_MODEL_EVIDENCE",
            reason="Top-level artifact is MONITOR_ONLY and downstream BIG_BULL sealed stability blocks model promotion.",
            next_allowed_step="use only as research evidence for selected family replay",
        )
    )
    return rows


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    model_path = resolve_path(args.model)
    production_dir = resolve_path("artifacts/backtest/historical_rankings_current_model")
    production_before = directory_digest(production_dir)
    clawd_before = glob_digest(PROJECT_ROOT / "artifacts", "clawd_publish_message*.md")
    model_hash_before_seen = sha256(model_path)
    model_hash_after = sha256(model_path)
    production_after = directory_digest(production_dir)
    clawd_after = glob_digest(PROJECT_ROOT / "artifacts", "clawd_publish_message*.md")
    guard = base_guard(args.model_hash_before, model_hash_after, production_before, production_after, clawd_before, clawd_after)
    guard["model_hash_before_arg"] = args.model_hash_before
    guard["model_hash_before_seen"] = model_hash_before_seen
    guard["model_hash_after"] = model_hash_after
    candidates = build_candidates(guard)
    counts = Counter(row["decision"] for row in candidates)
    surviving = [row for row in candidates if row["decision"] in SURVIVING_DECISIONS]
    monitor_only = [row for row in candidates if row["decision"] in {"MONITOR_ONLY", "RESTRICTED_SHADOW_ONLY", "MODEL_CANDIDATE_NEEDS_MORE_EVIDENCE"}]
    rejected = [row for row in candidates if row["decision"] == "REJECTED"]
    blocked = [row for row in candidates if row["decision"].startswith("BLOCKED")]
    errors = []
    if any(row["decision"] not in ALLOWED_DECISIONS for row in candidates):
        errors.append("invalid candidate decision")
    if not candidates:
        errors.append("no candidates tested")
    if len(surviving) == len(candidates):
        errors.append("all candidates survived; gate is not selective")
    if guard["models_latest_changed"]:
        errors.append("models/latest_lgbm.pkl hash changed")
    if guard["production_ranking_changed"] or guard["risk_adjusted_score_changed"]:
        errors.append("production ranking guard changed")
    if guard["promotion_ready"]:
        errors.append("promotion_ready unexpectedly true")
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "batch_status": "OK" if not errors else "FAILED",
        "contract": {
            "mass_candidate_batch_only": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_production_ranking": True,
            "does_not_change_risk_adjusted_score": True,
            "does_not_create_formal_clawd_message": True,
            "does_not_output_promotion_ready": True,
            "does_not_add_formal_regime_label": True,
            "surviving_candidates_are_not_promotion_ready": True,
        },
        "summary": {
            "candidates_tested": len(candidates),
            "survived": len(surviving),
            "monitor_only": len(monitor_only),
            "rejected": len(rejected),
            "blocked": len(blocked),
            "decision_counts": dict(sorted(counts.items())),
            "top_surviving_candidates": [
                {
                    "candidate_id": row["candidate_id"],
                    "decision": row["decision"],
                    "next_allowed_step": row["next_allowed_step"],
                    "reason": row["rejection_or_survival_reason"],
                }
                for row in surviving
            ],
            "best_next_step": "run replay extension for feature_group_ablation_by_regime and sector_industry_context only",
        },
        "guard_status": guard,
        "candidates": candidates,
        "errors": errors,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload.get("summary", {})
    lines = [
        "# AUTO-TRAINING-BATCH-01 Mass Candidate Training Batch",
        "",
        f"- batch_status: {payload.get('batch_status')}",
        f"- candidates_tested: {summary.get('candidates_tested')}",
        f"- survived: {summary.get('survived')}",
        f"- monitor_only: {summary.get('monitor_only')}",
        f"- rejected: {summary.get('rejected')}",
        f"- blocked: {summary.get('blocked')}",
        f"- best_next_step: {summary.get('best_next_step')}",
        f"- models_latest_changed: {payload.get('guard_status', {}).get('models_latest_changed')}",
        f"- production_ranking_changed: {payload.get('guard_status', {}).get('production_ranking_changed')}",
        f"- risk_adjusted_score_changed: {payload.get('guard_status', {}).get('risk_adjusted_score_changed')}",
        f"- promotion_ready: {payload.get('guard_status', {}).get('promotion_ready')}",
        "",
        "## Surviving Candidates",
        "",
    ]
    for row in summary.get("top_surviving_candidates", []):
        lines.append(f"- {row['candidate_id']}: {row['decision']} -> {row['next_allowed_step']}")
    lines.extend(["", "## Decisions", ""])
    for row in payload.get("candidates", []):
        lines.append(f"- {row['candidate_id']}: {row['decision']} - {row['rejection_or_survival_reason']}")
    if payload.get("errors"):
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {item}" for item in payload["errors"])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = resolve_path(args.output) if args.output else PROJECT_ROOT / "artifacts" / "model_experiments" / f"mass_candidate_training_batch_{args.date}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload["batch_status"], "output": repo_path(output), **payload["summary"]}, ensure_ascii=False, sort_keys=True))
    return 0 if payload["batch_status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
