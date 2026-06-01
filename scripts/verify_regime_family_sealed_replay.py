#!/usr/bin/env python3
"""驗證 regime family sealed replay artifact。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_EXPERIMENTS_DIR = PROJECT_ROOT / "artifacts" / "model_experiments"
CONTRACT_TRUE_FLAGS = {
    "research_only",
    "in_memory_models_only",
    "does_not_write_models_latest_lgbm",
    "does_not_change_risk_adjusted_score",
    "does_not_change_production_ranking",
    "promotion_requires_manual_review",
}
VALID_DECISIONS = {"SEALED_REPLAY_PASS", "MONITOR_ONLY", "REJECTED"}
BASE_REGIME_LABELS = [
    "BROAD_RISK_ON",
    "NARROW_LEADER",
    "CHOPPY_RANGE",
    "RISK_OFF",
    "PANIC_SELLING",
    "EARLY_REVERSAL",
    "MIXED_NEUTRAL",
    "UNKNOWN",
]
REGIME_FAMILY_TAGS = {"HIGH_CHOPPY", "BIG_BULL"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify regime family sealed replay artifact")
    parser.add_argument("--artifact", default=None)
    parser.add_argument("--output", default="artifacts/model_experiments/regime_family_sealed_replay_verification_latest.json")
    return parser.parse_args()


def resolve_path(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def latest_artifact() -> Path | None:
    matches = sorted(MODEL_EXPERIMENTS_DIR.glob("regime_family_sealed_replay_????-??-??.json"))
    return matches[-1] if matches else None


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def check(name: str, ok: bool, value: Any) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "value": value}


def split_chronological(split: dict[str, Any]) -> bool:
    train_end = split.get("train_end_date")
    sealed_start = split.get("sealed_start_date")
    if not train_end or not sealed_start:
        return False
    return str(train_end) < str(sealed_start)


def passed_families_have_no_failures(families: list[dict[str, Any]]) -> bool:
    for family in families:
        if family.get("decision") == "SEALED_REPLAY_PASS" and family.get("failures"):
            return False
    return True


def failed_or_small_families_not_passed(families: list[dict[str, Any]], policy: dict[str, Any]) -> bool:
    min_dates = int(policy.get("min_sealed_family_dates") or 0)
    min_rows = int(policy.get("min_sealed_samples") or 0)
    for family in families:
        selected = (family.get("variants") or {}).get(family.get("selected_candidate_variant"), {})
        if int(selected.get("sealed_family_dates") or 0) < min_dates and family.get("decision") == "SEALED_REPLAY_PASS":
            return False
        if int(selected.get("sealed_rows") or 0) < min_rows and family.get("decision") == "SEALED_REPLAY_PASS":
            return False
    return True


def build_report(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    taxonomy = contract.get("taxonomy") if isinstance(contract.get("taxonomy"), dict) else {}
    policy = payload.get("decision_policy") if isinstance(payload.get("decision_policy"), dict) else {}
    split = payload.get("split") if isinstance(payload.get("split"), dict) else {}
    families = payload.get("families") if isinstance(payload.get("families"), list) else []
    family_ids = {str(row.get("family")) for row in families}
    no_hindsight = contract.get("no_hindsight_policy") if isinstance(contract.get("no_hindsight_policy"), dict) else {}
    checks = [
        check("schema", payload.get("schema_version") == "regime-family-sealed-replay.v1", payload.get("schema_version")),
        check("status", payload.get("status") == "OK", payload.get("status")),
        check("pre_registered", payload.get("pre_registered") is True, payload.get("pre_registered")),
        check("layer_model", payload.get("layer") == "model", payload.get("layer")),
        check("decision_standard", payload.get("decision") in VALID_DECISIONS, payload.get("decision")),
        check("family_decisions_standard", all(row.get("decision") in VALID_DECISIONS for row in families), [row.get("decision") for row in families]),
        check("has_family_results", bool(families), sorted(family_ids)),
        check("no_extra_family_tags", family_ids.issubset(REGIME_FAMILY_TAGS), sorted(family_ids)),
        check("base_regime_labels_fixed", taxonomy.get("base_regime_labels") == BASE_REGIME_LABELS, taxonomy.get("base_regime_labels")),
        check("base_regime_mutually_exclusive", taxonomy.get("base_regime_mutually_exclusive") is True, taxonomy),
        check("families_not_base_regimes", taxonomy.get("family_tags_are_not_base_regimes") is True, taxonomy),
        check("family_tags_not_mutually_exclusive", taxonomy.get("family_tags_are_not_mutually_exclusive") is True, taxonomy),
        check("family_tag_contract_fixed", set(taxonomy.get("regime_family_tags") or []) == REGIME_FAMILY_TAGS, taxonomy.get("regime_family_tags")),
        check("production_promotion_blocked", contract.get("production_promotion_allowed") is False, contract.get("production_promotion_allowed")),
        check("split_chronological", split_chronological(split), split),
        check("passed_families_have_no_failures", passed_families_have_no_failures(families), None),
        check("failed_or_small_families_not_passed", failed_or_small_families_not_passed(families, policy), policy),
        check("fixed_candidate_artifact", no_hindsight.get("uses_fixed_candidate_artifact") is True, no_hindsight),
        check("sealed_split_fixed_before_scoring", no_hindsight.get("sealed_split_fixed_before_scoring") is True, no_hindsight),
        check("no_same_run_filters", no_hindsight.get("diagnostic_failures_cannot_define_same_run_filters") is True, no_hindsight),
        check("passing_gate_not_promotion", no_hindsight.get("passing_this_gate_does_not_allow_production_promotion") is True, no_hindsight),
    ]
    for flag in CONTRACT_TRUE_FLAGS:
        checks.append(check(f"contract.{flag}", contract.get(flag) is True, contract.get(flag)))
    failed = [row for row in checks if not row["ok"]]
    return {
        "schema_version": "regime-family-sealed-replay-verification.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK" if not failed else "FAILED",
        "input": repo_path(path),
        "summary": {
            "check_count": len(checks),
            "failed_count": len(failed),
            "families": sorted(family_ids),
        },
        "checks": checks,
    }


def main() -> int:
    args = parse_args()
    artifact = resolve_path(args.artifact) or latest_artifact()
    if artifact is None:
        raise FileNotFoundError("找不到 regime_family_sealed_replay_YYYY-MM-DD.json")
    report = build_report(artifact)
    output = resolve_path(args.output)
    if output is None:
        raise RuntimeError("output path resolution failed")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"status": report["status"], "output": repo_path(output), **report["summary"]}, ensure_ascii=False))
    return 0 if report["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
