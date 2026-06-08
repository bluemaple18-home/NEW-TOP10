#!/usr/bin/env python3
"""產出 AUTO-TRAINING-13 sealed split policy 與 ranking-only 決策。"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "big-bull-sealed-split-policy-ranking-only-decision.v1"
VALID_DECISIONS = {
    "RANKING_ONLY_CANDIDATE",
    "MODEL_CANDIDATE_NEEDS_MORE_EVIDENCE",
    "MONITOR_ONLY",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build AUTO-TRAINING-13 decision report")
    parser.add_argument("--date", required=True)
    parser.add_argument("--model", default="models/latest_lgbm.pkl")
    parser.add_argument("--model-hash-before", required=True)
    parser.add_argument("--blocker-resolution", default="artifacts/model_experiments/big_bull_blocker_resolution_2026-06-01.json")
    parser.add_argument("--ranking-extension", default="artifacts/model_experiments/big_bull_ranking_replay_extension_2026-06-01.json")
    parser.add_argument("--sealed-stability", default="artifacts/model_experiments/regime_family_sealed_stability_2026-06-01.json")
    parser.add_argument("--sealed-oos-gate", default="artifacts/sealed_oos_report_auto12_2026-06-01.json")
    parser.add_argument("--promotion-review", default="artifacts/model_experiments/model_promotion_review_big_bull_auto13_2026-06-01.json")
    parser.add_argument("--training-readiness", default="artifacts/training_automation_readiness_2026-06-01.json")
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


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def split_from_checks(checks: list[dict[str, Any]]) -> dict[str, Any]:
    keys = {
        "model.sealed_oos.train_end_date": "train_end_date",
        "model.sealed_oos.sealed_start_date": "sealed_start_date",
        "model.sealed_oos.sealed_end_date": "sealed_end_date",
        "model.sealed_oos.embargo_trade_days": "embargo_trade_days",
        "model.sealed_oos.sealed_trade_days": "sealed_trade_days",
    }
    result: dict[str, Any] = {}
    for check in checks:
        key = keys.get(str(check.get("name")))
        if key:
            result[key] = check.get("actual")
    return result


def split_policy(gate: dict[str, Any]) -> dict[str, Any]:
    checks = gate.get("leakage_checks", [])
    metadata_split = split_from_checks(checks)
    fixed_split = gate.get("split", {})
    mismatches = [
        {
            "name": check.get("name"),
            "actual": check.get("actual"),
            "expected": check.get("expected"),
            "contract": check.get("contract"),
        }
        for check in checks
        if check.get("status") == "FAILED" and str(check.get("name", "")).startswith("model.sealed_oos.")
    ]
    conflict = bool(mismatches)
    return {
        "status": "SPLIT_POLICY_CONFLICT" if conflict else "OK",
        "policy_source": "artifact_policy: run_sealed_oos_gate builds the fixed split from retrain.sealed_oos config, model horizon/threshold, and the labeled trade-date calendar",
        "metadata_split": metadata_split,
        "fixed_split": {
            "schema_version": fixed_split.get("schema_version"),
            "train_start_date": fixed_split.get("train_start_date"),
            "train_end_date": fixed_split.get("train_end_date"),
            "embargo_start_date": fixed_split.get("embargo_start_date"),
            "embargo_end_date": fixed_split.get("embargo_end_date"),
            "sealed_start_date": fixed_split.get("sealed_start_date"),
            "sealed_end_date": fixed_split.get("sealed_end_date"),
            "embargo_trade_days": fixed_split.get("embargo_trade_days"),
            "sealed_trade_days": fixed_split.get("sealed_trade_days"),
            "latest_label_date": fixed_split.get("latest_label_date"),
        },
        "policy_decision": "SPLIT_POLICY_CONFLICT" if conflict else "FIXED_SPLIT_ACCEPTED",
        "mismatches": mismatches,
        "resolution": (
            "model metadata and gate fixed split differ; do not auto-select the better-looking result and do not mutate historical artifacts"
            if conflict
            else "model metadata matches the fixed split"
        ),
        "no_hindsight_confirmation": {
            "split_not_chosen_by_result_quality": True,
            "fixed_split_materialized_in_gate_artifact": bool(fixed_split),
            "sealed_period_not_for_training_tuning_or_calibration": True,
            "conflict_blocks_model_promotion": conflict,
        },
    }


def ranking_evidence(extension: dict[str, Any]) -> dict[str, Any]:
    decision = extension.get("decision", {})
    scores = decision.get("scores", {})
    family = scores.get("family_only", {})
    blended = scores.get("blended_rerank", {})
    entry = (extension.get("entry_day_sensitivity") or {}).get("family_only", {})
    window = (extension.get("replay_window_sensitivity") or {}).get("family_only", {})
    return {
        "auto10_decision": decision.get("decision"),
        "best_candidate": decision.get("best_candidate"),
        "family_only_score": family,
        "blended_rerank_score": blended,
        "entry_day_sensitivity": entry,
        "replay_window_sensitivity": window,
        "high_choppy_soft_feature": extension.get("high_choppy_soft_feature_comparison"),
    }


def decide_family_only(
    *,
    blocker: dict[str, Any],
    extension: dict[str, Any],
    stability: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    evidence = ranking_evidence(extension)
    family = evidence["family_only_score"]
    d1_ok = (family.get("total_return") or 0) > 0 and (family.get("hit_rate") or 0) >= 0.5
    extension_ranking_ok = evidence.get("best_candidate") == "family_only" and evidence.get("auto10_decision") == "RANKING_FOLLOWUP_CANDIDATE"
    stability_blocks_model = stability.get("decision") == "MODEL_PROMOTION_BLOCKED"
    split_conflict = policy.get("policy_decision") == "SPLIT_POLICY_CONFLICT"
    if extension_ranking_ok and d1_ok and stability_blocks_model:
        decision = "RANKING_ONLY_CANDIDATE"
    elif stability_blocks_model or split_conflict:
        decision = "MODEL_CANDIDATE_NEEDS_MORE_EVIDENCE"
    else:
        decision = "MONITOR_ONLY"

    return {
        "decision": decision,
        "ranking_only_allowed": decision == "RANKING_ONLY_CANDIDATE",
        "model_promotion_allowed": False,
        "model_candidate_allowed": False if decision == "RANKING_ONLY_CANDIDATE" else decision == "MODEL_CANDIDATE_NEEDS_MORE_EVIDENCE",
        "shadow_ranking_or_dry_run_only": decision == "RANKING_ONLY_CANDIDATE",
        "cannot_overwrite_model": True,
        "cannot_change_production_score": True,
        "evidence": evidence,
        "blocked_model_reasons": [
            item
            for item in [
                "sealed stability blocks model promotion" if stability_blocks_model else None,
                "sealed split policy conflict blocks model promotion" if split_conflict else None,
                "AUTO12 promotion adapter remains blocked" if blocker.get("promotion_adapter_status") == "BLOCKED" else None,
            ]
            if item
        ],
        "reason": (
            "family_only has positive D+1 ranking replay/portfolio evidence and is AUTO10 best ranking follow-up, "
            "but sealed stability and split policy conflict prohibit model promotion."
        )
        if decision == "RANKING_ONLY_CANDIDATE"
        else "ranking evidence is not enough to justify ranking-only progression",
    }


def readiness_summary(readiness: dict[str, Any]) -> dict[str, Any]:
    body = readiness.get("readiness") if isinstance(readiness.get("readiness"), dict) else readiness
    return {
        "status": readiness.get("status"),
        "training_launch_ready": body.get("training_launch_ready"),
        "promotion_ready": body.get("promotion_ready"),
        "blocked": body.get("blocked", []),
        "promotion_blockers": body.get("promotion_blockers", []),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    paths = {
        "blocker_resolution": resolve_path(args.blocker_resolution),
        "ranking_extension": resolve_path(args.ranking_extension),
        "sealed_stability": resolve_path(args.sealed_stability),
        "sealed_oos_gate": resolve_path(args.sealed_oos_gate),
        "promotion_review": resolve_path(args.promotion_review),
        "training_readiness": resolve_path(args.training_readiness),
    }
    missing = [name for name, path in paths.items() if not path.exists()]
    if missing:
        return {
            "schema_version": SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "date": args.date,
            "status": "BLOCKED",
            "errors": [f"missing required artifact: {name}" for name in missing],
        }

    blocker = read_json(paths["blocker_resolution"])
    extension = read_json(paths["ranking_extension"])
    stability = read_json(paths["sealed_stability"])
    gate = read_json(paths["sealed_oos_gate"])
    promotion = read_json(paths["promotion_review"])
    readiness = readiness_summary(read_json(paths["training_readiness"]))
    policy = split_policy(gate)
    family_decision = decide_family_only(blocker=blocker, extension=extension, stability=stability, policy=policy)
    after_hash = sha256(resolve_path(args.model))
    promotion_ready = bool(readiness.get("promotion_ready")) if readiness.get("promotion_ready") is not None else False
    promotion_adapter_status = promotion.get("status")
    errors = []
    if family_decision["decision"] not in VALID_DECISIONS:
        errors.append(f"invalid family_only decision: {family_decision['decision']}")
    if promotion_ready:
        errors.append("promotion_ready unexpectedly true")
    if after_hash != args.model_hash_before:
        errors.append("models/latest_lgbm.pkl hash changed")
    if promotion_adapter_status != "LEDGER_EVIDENCE_BLOCKED":
        errors.append(f"promotion adapter is not blocked: {promotion_adapter_status}")

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK" if not errors else "BLOCKED",
        "contract": {
            "decision_only": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_production_ranking_score": True,
            "does_not_relax_sealed_stability_gate": True,
            "does_not_select_split_by_result_quality": True,
            "promotion_ready_must_be_false": True,
        },
        "sealed_split_policy_status": policy["status"],
        "policy_source": policy["policy_source"],
        "metadata_split": policy["metadata_split"],
        "fixed_split": policy["fixed_split"],
        "policy_decision": policy["policy_decision"],
        "no_hindsight_confirmation": policy["no_hindsight_confirmation"],
        "big_bull_family_only_decision": family_decision["decision"],
        "ranking_only_allowed": family_decision["ranking_only_allowed"],
        "model_promotion_allowed": family_decision["model_promotion_allowed"],
        "family_only_positioning": family_decision,
        "promotion_adapter_status": promotion_adapter_status,
        "promotion_ready": promotion_ready,
        "models_latest_changed": after_hash != args.model_hash_before,
        "model_hash_before": args.model_hash_before,
        "model_hash_after": after_hash,
        "training_launch_ready": readiness.get("training_launch_ready"),
        "next_card": (
            "AUTO-TRAINING-14_big_bull_ranking_only_shadow_dry_run"
            if family_decision["decision"] == "RANKING_ONLY_CANDIDATE"
            else "AUTO-TRAINING-14_big_bull_more_sealed_replay_evidence"
        ),
        "errors": errors,
        "policy_details": policy,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# AUTO-TRAINING-13 Sealed Split Policy / Ranking-Only Decision",
            "",
            f"- sealed_split_policy_status: {payload.get('sealed_split_policy_status')}",
            f"- policy_source: {payload.get('policy_source')}",
            f"- policy_decision: {payload.get('policy_decision')}",
            f"- big_bull_family_only_decision: {payload.get('big_bull_family_only_decision')}",
            f"- ranking_only_allowed: {payload.get('ranking_only_allowed')}",
            f"- model_promotion_allowed: {payload.get('model_promotion_allowed')}",
            f"- promotion_adapter_status: {payload.get('promotion_adapter_status')}",
            f"- promotion_ready: {payload.get('promotion_ready')}",
            f"- models_latest_changed: {payload.get('models_latest_changed')}",
            f"- next_card: {payload.get('next_card')}",
            "",
            "## Errors",
            "",
            *[f"- {item}" for item in payload.get("errors", [])],
            "",
        ]
    )


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = resolve_path(args.output) if args.output else PROJECT_ROOT / "artifacts" / "model_experiments" / f"big_bull_sealed_split_policy_ranking_only_decision_{args.date}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload.get("status"), "output": repo_path(output), "decision": payload.get("big_bull_family_only_decision")}, ensure_ascii=False, sort_keys=True))
    return 0 if payload.get("status") == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
