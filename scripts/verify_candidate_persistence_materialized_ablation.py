#!/usr/bin/env python3
"""驗證 candidate persistence materialized ablation artifact。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "model_experiments"
CONTRACT_TRUE_FLAGS = {
    "research_only",
    "uses_prior_only_materialized_features",
    "does_not_train_model",
    "does_not_write_models_latest_lgbm",
    "does_not_change_risk_adjusted_score",
    "does_not_change_production_ranking",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify candidate persistence materialized ablation")
    parser.add_argument("--artifact", default=None)
    parser.add_argument("--output", default="artifacts/model_experiments/candidate_persistence_materialized_ablation_verification_latest.json")
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
    matches = sorted(OUTPUT_DIR.glob("candidate_persistence_materialized_ablation_????-??-??.json"))
    return matches[-1] if matches else None


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_report(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    contract = payload.get("contract", {})
    summary = payload.get("summary", {})
    checks: list[dict[str, Any]] = [
        {"name": "schema", "ok": payload.get("schema_version") == "candidate-persistence-materialized-ablation.v1", "value": payload.get("schema_version")},
        {"name": "status", "ok": payload.get("status") == "OK", "value": payload.get("status")},
        {"name": "has_trades", "ok": int(summary.get("trade_count") or 0) > 0, "value": summary.get("trade_count")},
        {
            "name": "has_horizon_baselines",
            "ok": bool(summary.get("baseline_by_horizon")),
            "value": sorted((summary.get("baseline_by_horizon") or {}).keys()),
        },
        {
            "name": "promotion_blocked",
            "ok": contract.get("production_promotion_allowed") is False,
            "value": contract.get("production_promotion_allowed"),
        },
    ]
    for flag in CONTRACT_TRUE_FLAGS:
        checks.append({"name": f"contract.{flag}", "ok": contract.get(flag) is True, "value": contract.get(flag)})
    failed = [item for item in checks if not item["ok"]]
    return {
        "schema_version": "candidate-persistence-materialized-ablation-verification.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
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
        raise FileNotFoundError("找不到 candidate_persistence_materialized_ablation_YYYY-MM-DD.json")
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
