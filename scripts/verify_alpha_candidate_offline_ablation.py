#!/usr/bin/env python3
"""驗證 alpha candidate offline ablation artifact。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "model_experiments"
CONTRACT_TRUE_FLAGS = {
    "research_only",
    "in_memory_models_only",
    "does_not_write_models_latest_lgbm",
    "does_not_write_production_features",
    "does_not_change_risk_adjusted_score",
    "does_not_change_production_ranking",
}
ALLOWED_DECISIONS = {"PROMOTE_TO_NEXT_REPLAY", "MONITOR_ONLY", "REJECTED"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify alpha candidate offline ablation")
    parser.add_argument("--artifact", default=None)
    parser.add_argument("--output", default="artifacts/model_experiments/alpha_candidate_offline_ablation_verification_latest.json")
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
    matches = sorted(OUTPUT_DIR.glob("alpha_candidate_offline_ablation_????-??-??.json"))
    return matches[-1] if matches else None


def as_date(value: Any) -> datetime:
    return datetime.strptime(str(value), "%Y-%m-%d")


def build_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    contract = payload.get("contract", {})
    policy = contract.get("no_hindsight_policy", {}) if isinstance(contract.get("no_hindsight_policy"), dict) else {}
    summary = payload.get("summary", {})
    variants = payload.get("variants", {})
    checks: list[dict[str, Any]] = [
        {"name": "schema", "ok": payload.get("schema_version") == "alpha-candidate-offline-ablation.v1", "value": payload.get("schema_version")},
        {"name": "status", "ok": payload.get("status") == "OK", "value": payload.get("status")},
        {"name": "pre_registered", "ok": payload.get("pre_registered") is True, "value": payload.get("pre_registered")},
        {"name": "decision_known", "ok": payload.get("decision") in ALLOWED_DECISIONS, "value": payload.get("decision")},
        {"name": "has_decision_rationale", "ok": bool(str(payload.get("decision_rationale") or "").strip()), "value": payload.get("decision_rationale")},
        {"name": "has_alpha_features", "ok": int(summary.get("alpha_feature_count") or 0) > 0, "value": summary.get("alpha_features")},
        {"name": "has_baseline_variant", "ok": "baseline_only" in variants, "value": sorted(variants)},
        {"name": "has_plus_variant", "ok": "baseline_plus_alpha" in variants, "value": sorted(variants)},
        {"name": "has_alpha_only_diagnostic", "ok": "alpha_only_diagnostic" in variants, "value": sorted(variants)},
        {
            "name": "baseline_has_folds",
            "ok": int(variants.get("baseline_only", {}).get("fold_count") or 0) > 0,
            "value": variants.get("baseline_only", {}).get("fold_count"),
        },
        {
            "name": "plus_has_folds",
            "ok": int(variants.get("baseline_plus_alpha", {}).get("fold_count") or 0) > 0,
            "value": variants.get("baseline_plus_alpha", {}).get("fold_count"),
        },
        {
            "name": "promotion_blocked",
            "ok": contract.get("production_promotion_allowed") is False,
            "value": contract.get("production_promotion_allowed"),
        },
        {
            "name": "promotion_gate_variant",
            "ok": policy.get("promotion_gate_variant") == "baseline_plus_alpha_vs_baseline_only",
            "value": policy.get("promotion_gate_variant"),
        },
        {
            "name": "alpha_only_diagnostic_only",
            "ok": "alpha_only_diagnostic" in set(policy.get("diagnostic_only_variants") or []),
            "value": policy.get("diagnostic_only_variants"),
        },
        {
            "name": "new_filters_require_next_run",
            "ok": policy.get("new_filters_require_next_walkforward_run") is True,
            "value": policy.get("new_filters_require_next_walkforward_run"),
        },
    ]
    for flag in CONTRACT_TRUE_FLAGS:
        checks.append({"name": f"contract.{flag}", "ok": contract.get(flag) is True, "value": contract.get(flag)})

    for variant_name in ("baseline_only", "baseline_plus_alpha"):
        for row in variants.get(variant_name, {}).get("folds", []):
            if row.get("status") != "OK":
                continue
            train_end = row.get("train_end")
            validation_start = row.get("validation_start")
            ok = bool(train_end and validation_start and as_date(train_end) < as_date(validation_start))
            checks.append(
                {
                    "name": f"{variant_name}.fold_{row.get('fold')}.train_before_validation",
                    "ok": ok,
                    "value": {"train_end": train_end, "validation_start": validation_start},
                }
            )

    failed = [item for item in checks if not item["ok"]]
    return {
        "schema_version": "alpha-candidate-offline-ablation-verification.v1",
        "generated_at": datetime.now().isoformat(),
        "status": "OK" if not failed else "FAILED",
        "input": repo_path(path),
        "summary": {
            "check_count": len(checks),
            "failed_count": len(failed),
        },
        "checks": checks,
    }


def main() -> int:
    args = parse_args()
    artifact = resolve_path(args.artifact) or latest_artifact()
    if artifact is None:
        raise FileNotFoundError("找不到 alpha_candidate_offline_ablation_YYYY-MM-DD.json")
    output = resolve_path(args.output)
    if output is None:
        raise RuntimeError("output path resolution failed")
    if not artifact.exists():
        report = {
            "schema_version": "alpha-candidate-offline-ablation-verification.v1",
            "generated_at": datetime.now().isoformat(),
            "status": "FAILED",
            "input": repo_path(artifact),
            "summary": {"check_count": 1, "failed_count": 1},
            "checks": [{"name": "artifact_exists", "ok": False, "value": repo_path(artifact)}],
        }
    else:
        report = build_report(artifact)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"status": report["status"], "output": repo_path(output), **report["summary"]}, ensure_ascii=False))
    return 0 if report["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
