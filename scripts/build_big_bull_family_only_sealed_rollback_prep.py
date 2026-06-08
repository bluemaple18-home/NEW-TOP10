#!/usr/bin/env python3
"""彙整 AUTO-TRAINING-11 sealed / rollback prep 證據。"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "big-bull-family-only-sealed-rollback-prep.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build AUTO-TRAINING-11 sealed rollback prep report")
    parser.add_argument("--date", required=True)
    parser.add_argument("--model", default="models/latest_lgbm.pkl")
    parser.add_argument("--model-hash-before", required=True)
    parser.add_argument("--extension", default="artifacts/model_experiments/big_bull_ranking_replay_extension_2026-06-01.json")
    parser.add_argument("--high-choppy-context", default="artifacts/model_experiments/high_choppy_context_overlay_2026-06-01.json")
    parser.add_argument("--sealed-stability", default="artifacts/model_experiments/regime_family_sealed_stability_2026-06-01.json")
    parser.add_argument("--sealed-replay", default="artifacts/model_experiments/regime_family_sealed_replay_big_bull_100d_2026-06-01.json")
    parser.add_argument("--sealed-replay-verification", default="artifacts/model_experiments/regime_family_sealed_replay_big_bull_100d_verification_latest.json")
    parser.add_argument("--sealed-oos-gate", default="artifacts/sealed_oos_report_auto11_2026-06-01.json")
    parser.add_argument("--rollback-injection", default="artifacts/retrain_rollback_injection_2026-06-01.json")
    parser.add_argument("--ledger", default="artifacts/model_experiments/model_experiment_ledger.json")
    parser.add_argument("--promotion-review", default="artifacts/model_experiments/model_promotion_review_big_bull_auto11_2026-06-01.json")
    parser.add_argument("--promotion-review-ledger-id", default="artifacts/model_experiments/model_promotion_review_big_bull_ranking_followup_auto11_2026-06-01.json")
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


def ledger_traceability(ledger_path: Path) -> dict[str, Any]:
    ledger = read_json(ledger_path)
    auto10_tokens = {
        "AUTO-TRAINING-10",
        "big_bull_ranking_replay_extension_2026-06-01.json",
        "2026-06-01_AUTO-TRAINING-10_big_bull_ranking_replay_extension.md",
    }
    rows = []
    for entry in ledger.get("experiments", []):
        if str(entry.get("candidate")) != "BIG_BULL":
            continue
        source_text = "\n".join(str(item) for item in entry.get("source_artifacts", []))
        rows.append(
            {
                "ledger_id": entry.get("id"),
                "status": entry.get("status"),
                "links_auto10": any(token in source_text for token in auto10_tokens),
                "source_artifacts": entry.get("source_artifacts", []),
            }
        )
    linked = [row for row in rows if row["links_auto10"]]
    return {
        "status": "OK" if linked else "BLOCKED",
        "candidate": "BIG_BULL",
        "linked_ledger_ids": [row["ledger_id"] for row in linked],
        "big_bull_entries": rows,
        "blocker": None if linked else "BIG_BULL ledger entries do not trace to AUTO-TRAINING-10 artifact",
    }


def sealed_prep(sealed_replay_path: Path, sealed_verification_path: Path, sealed_stability_path: Path, sealed_oos_path: Path) -> dict[str, Any]:
    replay = read_json(sealed_replay_path)
    verification = read_json(sealed_verification_path)
    stability = read_json(sealed_stability_path)
    gate = read_json(sealed_oos_path)
    split = replay.get("split", {})
    return {
        "status": "BLOCKED" if stability.get("decision") == "MODEL_PROMOTION_BLOCKED" or gate.get("status") == "FAILED" else "OK",
        "candidate": "BIG_BULL family_only",
        "baseline": "global_baseline",
        "sealed_window": {
            "start": split.get("sealed_start_date"),
            "end": split.get("sealed_end_date"),
            "trade_days": split.get("sealed_trade_days"),
        },
        "no_hindsight_policy": (replay.get("contract") or {}).get("no_hindsight_policy"),
        "sealed_replay_decision": replay.get("decision"),
        "sealed_stability_decision": stability.get("decision"),
        "ranking_decision": stability.get("ranking_decision"),
        "sealed_verification_status": verification.get("status"),
        "current_model_sealed_oos_gate_status": gate.get("status"),
        "current_model_sealed_oos_failures": gate.get("failures", []),
        "blockers": [
            item
            for item in [
                "regime family sealed stability blocks model promotion"
                if stability.get("decision") == "MODEL_PROMOTION_BLOCKED"
                else None,
                "current model sealed OOS gate failed fixed split metadata check" if gate.get("status") == "FAILED" else None,
            ]
            if item
        ],
    }


def rollback_prep(model_path: Path, before_hash: str, rollback_path: Path, promotion_paths: list[Path], readiness_path: Path) -> dict[str, Any]:
    after_hash = sha256(model_path)
    rollback = read_json(rollback_path)
    promotions = [read_json(path) for path in promotion_paths]
    readiness = read_json(readiness_path)
    readiness_body = readiness.get("readiness") if isinstance(readiness.get("readiness"), dict) else readiness
    promotion_statuses = [payload.get("status") for payload in promotions]
    return {
        "status": "OK" if before_hash == after_hash and rollback.get("status") == "OK" and all(status != "LEDGER_EVIDENCE_OK" for status in promotion_statuses) else "BLOCKED",
        "model_hash_before": before_hash,
        "model_hash_after": after_hash,
        "models_latest_changed": before_hash != after_hash,
        "rollback_injection_status": rollback.get("status"),
        "promotion_adapter_statuses": promotion_statuses,
        "training_readiness_status": readiness.get("status"),
        "training_launch_ready": readiness_body.get("training_launch_ready"),
        "promotion_ready": readiness_body.get("promotion_ready"),
        "blocked": readiness_body.get("blocked", []),
        "promotion_blockers": readiness_body.get("promotion_blockers", []),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    paths = {
        "extension": resolve_path(args.extension),
        "high_choppy_context": resolve_path(args.high_choppy_context),
        "sealed_stability": resolve_path(args.sealed_stability),
        "sealed_replay": resolve_path(args.sealed_replay),
        "sealed_replay_verification": resolve_path(args.sealed_replay_verification),
        "sealed_oos_gate": resolve_path(args.sealed_oos_gate),
        "rollback_injection": resolve_path(args.rollback_injection),
        "ledger": resolve_path(args.ledger),
        "promotion_review": resolve_path(args.promotion_review),
        "promotion_review_ledger_id": resolve_path(args.promotion_review_ledger_id),
        "training_readiness": resolve_path(args.training_readiness),
    }
    required = required_artifacts(paths)
    model_path = resolve_path(args.model)
    if required["status"] != "OK":
        status = "BLOCKED"
        sealed = {}
        rollback = {}
        trace = {}
    else:
        sealed = sealed_prep(paths["sealed_replay"], paths["sealed_replay_verification"], paths["sealed_stability"], paths["sealed_oos_gate"])
        rollback = rollback_prep(
            model_path,
            args.model_hash_before,
            paths["rollback_injection"],
            [paths["promotion_review"], paths["promotion_review_ledger_id"]],
            paths["training_readiness"],
        )
        trace = ledger_traceability(paths["ledger"])
        status = "OK" if sealed["status"] == "OK" and rollback["status"] == "OK" and trace["status"] == "OK" else "BLOCKED"
    next_gate = "READY_FOR_SEALED_OOS_REVIEW" if status == "OK" else "BLOCKED"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": status,
        "candidate": "BIG_BULL family_only",
        "baseline": "global_baseline",
        "comparison_only": "BIG_BULL blended_rerank",
        "excluded": ["blended_score"],
        "high_choppy_policy": "rolling context stratified diagnostic only; not promotion evidence",
        "contract": {
            "prep_only": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_production_ranking_score": True,
            "does_not_enable_auto_retrain_promotion": True,
            "does_not_output_promotion_ready": True,
            "promotion_ready_must_be_false": True,
        },
        "required_artifacts": required,
        "sealed_oos_prep": sealed,
        "rollback_prep": rollback,
        "ledger_traceability": trace,
        "promotion_adapter_status": {
            "status": "BLOCKED" if rollback.get("promotion_adapter_statuses") else "UNKNOWN",
            "statuses": rollback.get("promotion_adapter_statuses"),
        },
        "training_launch_ready": rollback.get("training_launch_ready"),
        "promotion_ready": rollback.get("promotion_ready"),
        "models_latest_changed": rollback.get("models_latest_changed"),
        "next_gate": next_gate,
        "errors": sealed.get("blockers", []) + ([trace.get("blocker")] if trace.get("blocker") else []),
    }


def render_markdown(payload: dict[str, Any]) -> str:
    sealed = payload.get("sealed_oos_prep", {})
    rollback = payload.get("rollback_prep", {})
    trace = payload.get("ledger_traceability", {})
    return "\n".join(
        [
            "# AUTO-TRAINING-11 Sealed / Rollback Prep",
            "",
            f"- status: {payload['status']}",
            f"- candidate: {payload['candidate']}",
            f"- baseline: {payload['baseline']}",
            f"- next_gate: {payload['next_gate']}",
            f"- training_launch_ready: {payload.get('training_launch_ready')}",
            f"- promotion_ready: {payload.get('promotion_ready')}",
            f"- models_latest_changed: {payload.get('models_latest_changed')}",
            "",
            "## Sealed",
            "",
            f"- sealed_window: {sealed.get('sealed_window')}",
            f"- sealed_stability_decision: {sealed.get('sealed_stability_decision')}",
            f"- current_model_sealed_oos_gate_status: {sealed.get('current_model_sealed_oos_gate_status')}",
            f"- current_model_sealed_oos_failures: {sealed.get('current_model_sealed_oos_failures')}",
            "",
            "## Rollback / Promotion Guard",
            "",
            f"- rollback_injection_status: {rollback.get('rollback_injection_status')}",
            f"- promotion_adapter_statuses: {rollback.get('promotion_adapter_statuses')}",
            f"- ledger_traceability: {trace.get('status')} {trace.get('blocker') or ''}",
            "",
        ]
    )


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = resolve_path(args.output) if args.output else PROJECT_ROOT / "artifacts" / "model_experiments" / f"big_bull_family_only_sealed_rollback_prep_{args.date}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output), "next_gate": payload["next_gate"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
