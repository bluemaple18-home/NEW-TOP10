#!/usr/bin/env python3
"""驗證 SHADOW-01 feature experiment artifacts。

此驗證只讀 artifact，確認 shadow contract 與候選清單正確。
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
REQUIRED_CANDIDATES = {
    "candidate_persistence",
    "portfolio_risk_overlay",
    "regime_feature_group_ablation",
}
FORBIDDEN_CANDIDATES = {"market_context", "fundamentals", "chip_flow", "industry_rotation"}
CONTRACT_FLAGS = {
    "shadow_only",
    "reads_existing_artifacts_only",
    "does_not_train_model",
    "does_not_write_models_latest_lgbm",
    "does_not_change_risk_adjusted_score",
    "does_not_change_production_ranking",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify SHADOW-01 feature experiment artifacts")
    parser.add_argument("--artifact", default=None)
    parser.add_argument("--output", default="artifacts/shadow_feature_experiment_verification_latest.json")
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


def latest_index() -> Path | None:
    matches = sorted(
        path for path in ARTIFACTS_DIR.glob("shadow_feature_experiment_????-??-??.json")
        if path.is_file()
    )
    return matches[-1] if matches else None


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def check_contract(payload: dict[str, Any], prefix: str, checks: list[dict[str, Any]]) -> None:
    contract = payload.get("contract", {})
    for flag in CONTRACT_FLAGS:
        checks.append(
            {
                "name": f"{prefix}.{flag}",
                "ok": contract.get(flag) is True,
                "value": contract.get(flag),
            }
        )


def build_report(index_path: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    index = load_json(index_path)
    candidate_ids = {row.get("candidate_id") for row in index.get("candidates", [])}
    checks.extend(
        [
            {"name": "index.schema", "ok": index.get("schema_version") == "shadow-feature-experiment-index.v1", "value": index.get("schema_version")},
            {"name": "index.status", "ok": index.get("status") == "OK", "value": index.get("status")},
            {"name": "index.required_candidates", "ok": REQUIRED_CANDIDATES <= candidate_ids, "value": sorted(candidate_ids)},
            {"name": "index.forbidden_candidates_absent", "ok": not (FORBIDDEN_CANDIDATES & candidate_ids), "value": sorted(FORBIDDEN_CANDIDATES & candidate_ids)},
            {
                "name": "index.production_promotion_blocked",
                "ok": index.get("contract", {}).get("production_promotion_allowed") is False,
                "value": index.get("contract", {}).get("production_promotion_allowed"),
            },
        ]
    )
    check_contract(index, "index.contract", checks)

    for row in index.get("candidates", []):
        path = resolve_path(row.get("artifact"))
        exists = bool(path and path.exists())
        checks.append({"name": f"candidate.{row.get('candidate_id')}.artifact_exists", "ok": exists, "value": repo_path(path)})
        if not exists or path is None:
            continue
        payload = load_json(path)
        checks.extend(
            [
                {
                    "name": f"candidate.{row.get('candidate_id')}.schema",
                    "ok": payload.get("schema_version") == "shadow-feature-experiment.v1",
                    "value": payload.get("schema_version"),
                },
                {
                    "name": f"candidate.{row.get('candidate_id')}.status",
                    "ok": payload.get("status") == "OK",
                    "value": payload.get("status"),
                },
                {
                    "name": f"candidate.{row.get('candidate_id')}.decision",
                    "ok": payload.get("decision") in {"MODEL_EXP_CANDIDATE", "MONITOR_ONLY"},
                    "value": payload.get("decision"),
                },
                {
                    "name": f"candidate.{row.get('candidate_id')}.gate_ready",
                    "ok": payload.get("feature_gate", {}).get("shadow_status") == "READY_FOR_SHADOW",
                    "value": payload.get("feature_gate", {}).get("shadow_status"),
                },
            ]
        )
        check_contract(payload, f"candidate.{row.get('candidate_id')}.contract", checks)

    failed = [item for item in checks if not item["ok"]]
    return {
        "schema_version": "shadow-feature-experiment-verification.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK" if not failed else "FAILED",
        "input": repo_path(index_path),
        "summary": {
            "check_count": len(checks),
            "failed_count": len(failed),
            "candidate_count": len(candidate_ids),
            "candidates": sorted(candidate_ids),
        },
        "checks": checks,
    }


def main() -> int:
    args = parse_args()
    index_path = resolve_path(args.artifact) or latest_index()
    if index_path is None:
        raise FileNotFoundError("找不到 shadow_feature_experiment_YYYY-MM-DD.json")
    report = build_report(index_path)
    output = resolve_path(args.output)
    if output is None:
        raise RuntimeError("output path resolution failed")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"status": report["status"], "output": repo_path(output), **report["summary"]}, ensure_ascii=False))
    return 0 if report["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
