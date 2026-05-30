#!/usr/bin/env python3
"""驗證 MODEL-EXP-01 run manifest。

此驗證確保執行前 manifest 沒有允許正式模型寫入或 blocked candidate 跳級。
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_EXPERIMENTS_DIR = PROJECT_ROOT / "artifacts" / "model_experiments"
CONTRACT_TRUE_FLAGS = {
    "manifest_only",
    "does_not_train_model",
    "does_not_write_models_latest_lgbm",
    "does_not_change_risk_adjusted_score",
    "does_not_change_production_ranking",
}
ALLOWED_STATUSES = {
    "READY_FOR_OVERLAY_REPLAY",
    "READY_FOR_FEATURE_ABLATION",
    "BLOCKED_MISSING_MATERIALIZER",
    "WAIT_FOR_INDIVIDUAL_PASS",
    "BLOCKED_BY_PLAN_STATUS",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify MODEL-EXP-01 run manifest")
    parser.add_argument("--artifact", default=None)
    parser.add_argument("--output", default="artifacts/model_experiments/model_exp_run_manifest_verification_latest.json")
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


def latest_manifest() -> Path | None:
    matches = sorted(MODEL_EXPERIMENTS_DIR.glob("model_exp_run_manifest_????-??-??.json"))
    return matches[-1] if matches else None


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_report(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    checks: list[dict[str, Any]] = []
    contract = payload.get("contract", {})
    runs = payload.get("runs", [])
    statuses = {run.get("execution_status") for run in runs}
    ready_lightgbm = [
        run
        for run in runs
        if run.get("execution_status") == "READY_FOR_FEATURE_ABLATION"
    ]

    checks.extend(
        [
            {"name": "schema", "ok": payload.get("schema_version") == "model-experiment-run-manifest.v1", "value": payload.get("schema_version")},
            {"name": "status_known", "ok": payload.get("status") in {"READY", "READY_WITH_BLOCKERS", "BLOCKED"}, "value": payload.get("status")},
            {"name": "run_statuses_known", "ok": statuses <= ALLOWED_STATUSES, "value": sorted(str(item) for item in statuses)},
            {
                "name": "production_promotion_blocked",
                "ok": contract.get("production_promotion_allowed") is False,
                "value": contract.get("production_promotion_allowed"),
            },
            {
                "name": "candidate_persistence_not_executable_without_materializer",
                "ok": any(
                    run.get("experiment_id") == "model_exp_candidate_persistence_only"
                    and run.get("execution_status") == "BLOCKED_MISSING_MATERIALIZER"
                    for run in runs
                ),
                "value": [
                    {
                        "experiment_id": run.get("experiment_id"),
                        "execution_status": run.get("execution_status"),
                    }
                    for run in runs
                    if run.get("experiment_id") == "model_exp_candidate_persistence_only"
                ],
            },
            {
                "name": "at_most_one_first_pass_feature_ablation_ready",
                "ok": len(ready_lightgbm) <= 1,
                "value": [run.get("experiment_id") for run in ready_lightgbm],
            },
        ]
    )
    for flag in CONTRACT_TRUE_FLAGS:
        checks.append({"name": f"contract.{flag}", "ok": contract.get(flag) is True, "value": contract.get(flag)})

    for run in runs:
        exp_id = run.get("experiment_id")
        checks.extend(
            [
                {"name": f"{exp_id}.has_reason", "ok": bool(run.get("reason")), "value": run.get("reason")},
                {
                    "name": f"{exp_id}.commands_do_not_target_models_latest",
                    "ok": "models/latest_lgbm.pkl" not in "\n".join(run.get("safe_commands", [])),
                    "value": run.get("safe_commands", []),
                },
            ]
        )

    failed = [item for item in checks if not item["ok"]]
    return {
        "schema_version": "model-experiment-run-manifest-verification.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK" if not failed else "FAILED",
        "input": repo_path(path),
        "summary": {
            "check_count": len(checks),
            "failed_count": len(failed),
            "run_count": len(runs),
        },
        "checks": checks,
    }


def main() -> int:
    args = parse_args()
    artifact = resolve_path(args.artifact) or latest_manifest()
    if artifact is None:
        raise FileNotFoundError("找不到 artifacts/model_experiments/model_exp_run_manifest_YYYY-MM-DD.json")
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
