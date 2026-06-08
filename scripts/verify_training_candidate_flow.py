#!/usr/bin/env python3
"""驗證安全訓練候選流程 artifact。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_EXPERIMENTS_DIR = PROJECT_ROOT / "artifacts" / "model_experiments"
SCHEMA_VERSION = "training-candidate-flow-verification.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify safe training candidate flow")
    parser.add_argument("--artifact", default=None)
    parser.add_argument("--output", default="artifacts/model_experiments/training_candidate_flow_verification_latest.json")
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


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def latest_artifact() -> Path | None:
    matches = sorted(MODEL_EXPERIMENTS_DIR.glob("training_candidates/*/training_candidate_flow.json"))
    return matches[-1] if matches else None


def model_exists(payload: dict[str, Any]) -> bool:
    model_path = resolve_path((payload.get("candidate") or {}).get("model"))
    return bool(model_path and model_path.exists())


def build_payload(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    guards = payload.get("guards") if isinstance(payload.get("guards"), dict) else {}
    candidate = payload.get("candidate") if isinstance(payload.get("candidate"), dict) else {}
    steps = payload.get("steps") if isinstance(payload.get("steps"), list) else []
    checks = [
        {"name": "schema", "ok": payload.get("schema_version") == "training-candidate-flow.v1", "value": payload.get("schema_version")},
        {"name": "status_ok", "ok": payload.get("status") == "OK", "value": payload.get("status")},
        {"name": "candidate_training_only", "ok": contract.get("candidate_training_only") is True, "value": contract.get("candidate_training_only")},
        {"name": "production_promotion_blocked", "ok": contract.get("production_promotion_allowed") is False, "value": contract.get("production_promotion_allowed")},
        {"name": "models_latest_unchanged", "ok": guards.get("models_latest_changed") is False, "value": guards.get("models_latest_changed")},
        {"name": "promotion_ready_false", "ok": guards.get("promotion_ready") is False, "value": guards.get("promotion_ready")},
        {"name": "candidate_model_exists", "ok": model_exists(payload), "value": candidate.get("model")},
        {"name": "candidate_model_hash_present", "ok": bool(candidate.get("model_sha256")), "value": candidate.get("model_sha256")},
        {"name": "sealed_oos_ok", "ok": candidate.get("sealed_oos_status") == "OK", "value": candidate.get("sealed_oos_status")},
        {"name": "steps_all_ok", "ok": all(step.get("status") == "OK" for step in steps), "value": [(step.get("name"), step.get("status")) for step in steps]},
        {"name": "errors_empty", "ok": not payload.get("errors"), "value": payload.get("errors")},
    ]
    failed = [check for check in checks if not check["ok"]]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK" if not failed else "FAILED",
        "input": repo_path(path),
        "summary": {"check_count": len(checks), "failed_count": len(failed)},
        "checks": checks,
    }


def main() -> int:
    args = parse_args()
    artifact = resolve_path(args.artifact) or latest_artifact()
    if artifact is None:
        raise FileNotFoundError("找不到 training_candidates/*/training_candidate_flow.json")
    report = build_payload(artifact)
    output = resolve_path(args.output)
    if output is None:
        raise RuntimeError("output path resolution failed")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"status": report["status"], "output": repo_path(output), **report["summary"]}, ensure_ascii=False))
    return 0 if report["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
