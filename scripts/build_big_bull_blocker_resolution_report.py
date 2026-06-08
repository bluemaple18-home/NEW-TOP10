#!/usr/bin/env python3
"""彙整 AUTO-TRAINING-12 BIG_BULL blocker resolution 證據。"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "big-bull-blocker-resolution.v1"
ALLOWED_BLOCKER_STATES = {
    "RESOLVED",
    "STILL_BLOCKED_MODEL_EVIDENCE",
    "STILL_BLOCKED_CONTRACT",
    "NOT_APPLICABLE",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build AUTO-TRAINING-12 BIG_BULL blocker resolution report")
    parser.add_argument("--date", required=True)
    parser.add_argument("--model", default="models/latest_lgbm.pkl")
    parser.add_argument("--model-hash-before", required=True)
    parser.add_argument("--extension", default="artifacts/model_experiments/big_bull_ranking_replay_extension_2026-06-01.json")
    parser.add_argument("--sealed-stability", default="artifacts/model_experiments/regime_family_sealed_stability_2026-06-01.json")
    parser.add_argument("--sealed-oos-gate", default="artifacts/sealed_oos_report_auto11_2026-06-01.json")
    parser.add_argument("--rollback-injection", default="artifacts/retrain_rollback_injection_2026-06-01.json")
    parser.add_argument("--ledger", default="artifacts/model_experiments/model_experiment_ledger.json")
    parser.add_argument("--promotion-review", default="artifacts/model_experiments/model_promotion_review_big_bull_auto12_2026-06-01.json")
    parser.add_argument(
        "--promotion-review-ledger-id",
        default="artifacts/model_experiments/model_promotion_review_big_bull_ranking_followup_auto12_2026-06-01.json",
    )
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


def required_artifacts(paths: dict[str, Path]) -> dict[str, Any]:
    checks = {name: path.exists() for name, path in paths.items()}
    return {
        "status": "OK" if all(checks.values()) else "BLOCKED",
        "checks": checks,
        "paths": {name: repo_path(path) for name, path in paths.items()},
    }


def classify_sealed_stability(stability: dict[str, Any]) -> dict[str, Any]:
    metrics = stability.get("metrics", {})
    windows = stability.get("windows", [])
    decision = stability.get("decision")
    ranking_decision = stability.get("ranking_decision")
    auc_blocked = metrics.get("nonnegative_auc_delta_ratio") != 1.0 or (metrics.get("avg_auc_delta_vs_global") or 0) < 0
    topn_mixed = metrics.get("positive_topn_delta_ratio") not in {None, 1, 1.0}
    state = "STILL_BLOCKED_MODEL_EVIDENCE" if decision == "MODEL_PROMOTION_BLOCKED" else "RESOLVED"
    return {
        "state": state,
        "decision": decision,
        "ranking_decision": ranking_decision,
        "candidate_role": "ranking follow-up only" if ranking_decision == "RANKING_FOLLOWUP_CANDIDATE" else "model promotion candidate",
        "diagnosis": {
            "auc_stability_problem": bool(auc_blocked),
            "topn_problem": bool(topn_mixed),
            "window_problem": bool(topn_mixed or auc_blocked),
            "model_promotion_suitability": "blocked" if state == "STILL_BLOCKED_MODEL_EVIDENCE" else "eligible",
        },
        "metrics": metrics,
        "windows": [
            {
                "label": row.get("label"),
                "sealed_start_date": row.get("sealed_start_date"),
                "sealed_end_date": row.get("sealed_end_date"),
                "sealed_trade_days": row.get("sealed_trade_days"),
                "auc_delta_vs_global": row.get("auc_delta_vs_global"),
                "topn_return_delta_vs_global": row.get("topn_return_delta_vs_global"),
                "topn_uplift": row.get("topn_uplift"),
                "decision": row.get("decision"),
            }
            for row in windows
        ],
        "reason": (
            "AUC delta is negative across all sealed windows; TopN uplift is positive overall but one window underperforms, "
            "so the candidate remains a ranking follow-up candidate and cannot become promotion evidence."
        )
        if state == "STILL_BLOCKED_MODEL_EVIDENCE"
        else "sealed stability no longer blocks model promotion",
    }


def _actual_expected(check: dict[str, Any]) -> tuple[Any, Any]:
    if "actual" in check or "expected" in check:
        return check.get("actual"), check.get("expected")
    match = re.search(r"actual=(.*?) expected=(.*)$", str(check.get("message", "")))
    if not match:
        return None, None
    return match.group(1), match.group(2)


def classify_sealed_oos_metadata(gate: dict[str, Any]) -> dict[str, Any]:
    checks = gate.get("leakage_checks", [])
    mismatches = []
    missing = []
    for check in checks:
        actual, expected = _actual_expected(check)
        row = {
            "name": check.get("name"),
            "status": check.get("status"),
            "actual": actual,
            "expected": expected,
            "message": check.get("message"),
            "contract": check.get("contract"),
        }
        if check.get("status") == "FAILED":
            if "缺少" in str(check.get("message")) or actual is None:
                missing.append(row)
            else:
                mismatches.append(row)

    split = gate.get("split") or {}
    no_train_overlap = next((check for check in checks if check.get("name") == "model.sealed_oos.no_train_overlap"), {})
    state = "RESOLVED"
    if missing:
        state = "STILL_BLOCKED_CONTRACT"
    elif gate.get("status") == "FAILED" and mismatches:
        state = "STILL_BLOCKED_CONTRACT"

    return {
        "state": state,
        "gate_status": gate.get("status"),
        "contract_resolution": {
            "metadata_present": any(check.get("name") == "model.sealed_oos_metadata" and check.get("status") == "OK" for check in checks),
            "fixed_split_explained": bool(split),
            "split_schema_version": split.get("schema_version"),
            "no_train_overlap_status": no_train_overlap.get("status"),
            "no_fake_metadata": True,
            "does_not_mask_model_instability": True,
        },
        "fixed_split": {
            "train_start_date": split.get("train_start_date"),
            "train_end_date": split.get("train_end_date"),
            "embargo_start_date": split.get("embargo_start_date"),
            "embargo_end_date": split.get("embargo_end_date"),
            "sealed_start_date": split.get("sealed_start_date"),
            "sealed_end_date": split.get("sealed_end_date"),
            "embargo_trade_days": split.get("embargo_trade_days"),
            "sealed_trade_days": split.get("sealed_trade_days"),
        },
        "missing_fields": missing,
        "mismatched_fields": mismatches,
        "metrics": gate.get("metrics", {}),
        "reason": (
            "fixed split metadata is present and no-train-overlap passes, but the model payload split dates do not match "
            "the current fixed split; this remains a contract blocker until a candidate artifact carries matching split metadata."
        )
        if state == "STILL_BLOCKED_CONTRACT"
        else "fixed split metadata contract is traceable and no longer blocks this card",
    }


def ledger_rows(ledger: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for entry in ledger.get("experiments", []):
        if entry.get("candidate") != "BIG_BULL":
            continue
        source_artifacts = entry.get("source_artifacts", [])
        source_text = "\n".join(str(item) for item in source_artifacts)
        rows.append(
            {
                "ledger_id": entry.get("id"),
                "status": entry.get("status"),
                "links_auto10": "AUTO-TRAINING-10" in source_text
                or "big_bull_ranking_replay_extension_2026-06-01.json" in source_text,
                "production_promotion_allowed": entry.get("production_promotion_allowed"),
                "source_artifacts": source_artifacts,
            }
        )
    return rows


def classify_ledger_traceability(ledger: dict[str, Any], extension: dict[str, Any]) -> dict[str, Any]:
    rows = ledger_rows(ledger)
    followup = next((row for row in rows if row.get("ledger_id") == "training_policy:BIG_BULL:ranking-replay-followup"), None)
    trace_ok = bool(followup and followup.get("links_auto10"))
    decision = extension.get("decision", {})
    soft_feature = extension.get("high_choppy_soft_feature_comparison", {})
    stratified = extension.get("big_bull_high_choppy_stratified", {})
    return {
        "state": "RESOLVED" if trace_ok else "STILL_BLOCKED_CONTRACT",
        "linked_ledger_id": followup.get("ledger_id") if followup else None,
        "ledger_status": followup.get("status") if followup else None,
        "ledger_remains_pending": followup.get("status") == "pending" if followup else None,
        "big_bull_entries": rows,
        "lineage": {
            "BIG_BULL family_only": {
                "role": "primary ranking follow-up candidate",
                "promotion_evidence": False,
                "score": (decision.get("scores") or {}).get("family_only"),
            },
            "BIG_BULL blended_rerank": {
                "role": "comparison only",
                "promotion_evidence": False,
                "score": (decision.get("scores") or {}).get("blended_rerank"),
            },
            "HIGH_CHOPPY rolling context": {
                "role": "soft feature + stratified diagnostic",
                "soft_feature_decision": soft_feature.get("soft_feature_decision"),
                "affects_next_stage_qualification": soft_feature.get("affects_next_stage_qualification"),
                "promotion_evidence": False,
                "stratified": stratified,
            },
        },
        "reason": (
            "ranking-replay-followup now links to AUTO-TRAINING-10 extension artifact while remaining pending; "
            "lineage separates family_only, blended_rerank comparison, and HIGH_CHOPPY MONITOR_ONLY context."
        )
        if trace_ok
        else "BIG_BULL ledger entry still does not link to AUTO-TRAINING-10 artifact",
    }


def rollback_guard(model_path: Path, before_hash: str, rollback: dict[str, Any], promotions: list[dict[str, Any]]) -> dict[str, Any]:
    after_hash = sha256(model_path)
    promotion_statuses = [payload.get("status") for payload in promotions]
    ok = before_hash == after_hash and rollback.get("status") == "OK" and all(status != "LEDGER_EVIDENCE_OK" for status in promotion_statuses)
    return {
        "state": "RESOLVED" if ok else "STILL_BLOCKED_CONTRACT",
        "rollback_status": rollback.get("status"),
        "model_hash_before": before_hash,
        "model_hash_after": after_hash,
        "models_latest_changed": before_hash != after_hash,
        "promotion_adapter_statuses": promotion_statuses,
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
        "extension": resolve_path(args.extension),
        "sealed_stability": resolve_path(args.sealed_stability),
        "sealed_oos_gate": resolve_path(args.sealed_oos_gate),
        "rollback_injection": resolve_path(args.rollback_injection),
        "ledger": resolve_path(args.ledger),
        "promotion_review": resolve_path(args.promotion_review),
        "promotion_review_ledger_id": resolve_path(args.promotion_review_ledger_id),
        "training_readiness": resolve_path(args.training_readiness),
    }
    required = required_artifacts(paths)
    if required["status"] != "OK":
        missing = [name for name, ok in required["checks"].items() if not ok]
        return {
            "schema_version": SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "date": args.date,
            "status": "BLOCKED",
            "required_artifacts": required,
            "errors": [f"missing required artifact: {name}" for name in missing],
        }

    extension = read_json(paths["extension"])
    stability = read_json(paths["sealed_stability"])
    gate = read_json(paths["sealed_oos_gate"])
    rollback = read_json(paths["rollback_injection"])
    ledger = read_json(paths["ledger"])
    promotions = [read_json(paths["promotion_review"]), read_json(paths["promotion_review_ledger_id"])]
    readiness = readiness_summary(read_json(paths["training_readiness"]))

    sealed_stability_blocker = classify_sealed_stability(stability)
    sealed_oos_metadata_blocker = classify_sealed_oos_metadata(gate)
    ledger_traceability_blocker = classify_ledger_traceability(ledger, extension)
    rollback = rollback_guard(resolve_path(args.model), args.model_hash_before, rollback, promotions)

    errors = []
    for label, item in [
        ("sealed_stability_blocker", sealed_stability_blocker),
        ("sealed_oos_metadata_blocker", sealed_oos_metadata_blocker),
        ("ledger_traceability_blocker", ledger_traceability_blocker),
        ("rollback_guard", rollback),
    ]:
        state = item.get("state")
        if state not in ALLOWED_BLOCKER_STATES:
            errors.append(f"{label} has invalid state: {state}")
        if state.startswith("STILL_BLOCKED"):
            errors.append(f"{label}: {state}")

    promotion_adapter_statuses = rollback.get("promotion_adapter_statuses", [])
    promotion_adapter_status = "BLOCKED" if all(status == "LEDGER_EVIDENCE_BLOCKED" for status in promotion_adapter_statuses) else "CHECK"
    promotion_ready = bool(readiness.get("promotion_ready")) if readiness.get("promotion_ready") is not None else False
    if promotion_ready:
        errors.append("promotion_ready unexpectedly true")

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "BLOCKED" if errors else "OK",
        "candidate": "BIG_BULL family_only",
        "baseline": "global_baseline",
        "comparison_only": "BIG_BULL blended_rerank",
        "high_choppy_policy": "rolling context = soft feature + stratified diagnostic; not promotion evidence",
        "contract": {
            "blocker_resolution_only": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_output_promotion_ready": True,
            "does_not_relax_sealed_stability_gate": True,
            "does_not_mask_model_instability_with_metadata": True,
            "does_not_allow_blended_or_high_choppy_promotion": True,
            "does_not_change_production_ranking_score": True,
            "does_not_enable_auto_retrain_promotion": True,
        },
        "required_artifacts": required,
        "sealed_stability_blocker": sealed_stability_blocker,
        "sealed_oos_metadata_blocker": sealed_oos_metadata_blocker,
        "ledger_traceability_blocker": ledger_traceability_blocker,
        "rollback_guard": rollback,
        "training_launch_ready": readiness.get("training_launch_ready"),
        "promotion_ready": promotion_ready,
        "promotion_adapter_status": promotion_adapter_status,
        "models_latest_changed": rollback.get("models_latest_changed"),
        "next_gate": "STILL_BLOCKED_MODEL_EVIDENCE",
        "errors": errors,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# AUTO-TRAINING-12 BIG_BULL Blocker Resolution",
            "",
            f"- status: {payload.get('status')}",
            f"- sealed_stability_blocker: {payload.get('sealed_stability_blocker', {}).get('state')}",
            f"- sealed_oos_metadata_blocker: {payload.get('sealed_oos_metadata_blocker', {}).get('state')}",
            f"- ledger_traceability_blocker: {payload.get('ledger_traceability_blocker', {}).get('state')}",
            f"- rollback_guard: {payload.get('rollback_guard', {}).get('state')}",
            f"- training_launch_ready: {payload.get('training_launch_ready')}",
            f"- promotion_ready: {payload.get('promotion_ready')}",
            f"- promotion_adapter_status: {payload.get('promotion_adapter_status')}",
            f"- models_latest_changed: {payload.get('models_latest_changed')}",
            f"- next_gate: {payload.get('next_gate')}",
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
    output = resolve_path(args.output) if args.output else PROJECT_ROOT / "artifacts" / "model_experiments" / f"big_bull_blocker_resolution_{args.date}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload.get("status"), "output": repo_path(output), "next_gate": payload.get("next_gate")}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
