#!/usr/bin/env python3
"""驗證 HIGH_CHOPPY context / overlay artifact 的研究邊界。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_EXPERIMENTS_DIR = PROJECT_ROOT / "artifacts" / "model_experiments"
VALID_DECISIONS = {"MONITOR_ONLY", "SOFT_FEATURE_CANDIDATE", "RANKING_OVERLAY_CANDIDATE"}
USAGE_KEYS = {"soft_feature", "stratified_evaluation", "ranking_overlay", "promotion_evidence"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify HIGH_CHOPPY context overlay artifact")
    parser.add_argument("--artifact", default=None)
    parser.add_argument("--output", default="artifacts/model_experiments/high_choppy_context_overlay_verification_latest.json")
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
    matches = sorted(MODEL_EXPERIMENTS_DIR.glob("high_choppy_context_overlay_????-??-??.json"))
    return matches[-1] if matches else None


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def check(name: str, ok: bool, value: Any) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "value": value}


def build_report(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    definition = payload.get("context_definition") if isinstance(payload.get("context_definition"), dict) else {}
    allowed = summary.get("usage_allowed") if isinstance(summary.get("usage_allowed"), dict) else {}
    checks = [
        check("schema", payload.get("schema_version") == "high-choppy-context-overlay.v1", payload.get("schema_version")),
        check("status", payload.get("status") == "OK", payload.get("status")),
        check("decision_standard", payload.get("decision") in VALID_DECISIONS, payload.get("decision")),
        check("definition_pre_registered", definition.get("pre_registered_before_evaluation") is True, definition),
        check("rolling_definition_present", all(definition.get(key) for key in ["high_condition", "choppy_condition", "concentration_condition", "breadth_condition"]), definition),
        check("context_dates_present", isinstance(summary.get("rolling_context_dates"), int), summary.get("rolling_context_dates")),
        check("strict_dates_present", isinstance(summary.get("strict_dates"), int), summary.get("strict_dates")),
        check("new_dates_quality_present", isinstance(summary.get("new_dates_quality"), dict), summary.get("new_dates_quality")),
        check("usage_keys_present", set(allowed) == USAGE_KEYS, sorted(allowed)),
        check("promotion_evidence_blocked", (allowed.get("promotion_evidence") or {}).get("status") == "BLOCKED", allowed.get("promotion_evidence")),
        check("blocks_main_training_false", contract.get("blocks_main_training") is False and summary.get("blocks_main_training") is False, {"contract": contract.get("blocks_main_training"), "summary": summary.get("blocks_main_training")}),
        check("research_only", contract.get("research_only") is True, contract.get("research_only")),
        check("does_not_train_model", contract.get("trains_model") is False, contract.get("trains_model")),
        check("does_not_train_family_specific_model", contract.get("does_not_train_family_specific_model") is True, contract.get("does_not_train_family_specific_model")),
        check("does_not_write_latest_model", contract.get("does_not_write_models_latest_lgbm") is True, contract.get("does_not_write_models_latest_lgbm")),
        check("does_not_change_ranking", contract.get("does_not_change_production_ranking") is True, contract.get("does_not_change_production_ranking")),
        check("does_not_add_base_regime", contract.get("does_not_add_formal_base_regime") is True, contract.get("does_not_add_formal_base_regime")),
        check("production_promotion_blocked", contract.get("production_promotion_allowed") is False, contract.get("production_promotion_allowed")),
    ]
    failed = [row for row in checks if not row["ok"]]
    return {
        "schema_version": "high-choppy-context-overlay-verification.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK" if not failed else "FAILED",
        "input": repo_path(path),
        "summary": {
            "check_count": len(checks),
            "failed_count": len(failed),
            "strict_dates": summary.get("strict_dates"),
            "rolling_context_dates": summary.get("rolling_context_dates"),
            "blocks_main_training": summary.get("blocks_main_training"),
        },
        "checks": checks,
    }


def main() -> int:
    args = parse_args()
    artifact = resolve_path(args.artifact) or latest_artifact()
    if artifact is None:
        raise FileNotFoundError("找不到 high_choppy_context_overlay_YYYY-MM-DD.json")
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
