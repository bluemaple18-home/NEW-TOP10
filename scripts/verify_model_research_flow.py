#!/usr/bin/env python3
"""驗證 model research flow 失敗時不會產出下游 plan。"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import run_model_research_flow as flow  # noqa: E402


ARTIFACT_PATH = PROJECT_ROOT / "artifacts" / "model_research_flow_verification_latest.json"


def fake_step_result(name: str, command: list[str]) -> dict[str, Any]:
    return {
        "name": name,
        "status": "FAILED" if name == "shadow_feature.verify" else "OK",
        "returncode": 1 if name == "shadow_feature.verify" else 0,
        "started_at": "2026-01-05T00:00:00+00:00",
        "ended_at": "2026-01-05T00:00:00+00:00",
        "command": command,
        "stdout_tail": "",
        "stderr_tail": "injected failure" if name == "shadow_feature.verify" else "",
    }


def verify_fail_fast() -> dict[str, bool]:
    original_run_step = flow.run_step
    executed: list[str] = []

    def fake_run_step(name: str, command: list[str]) -> dict[str, Any]:
        executed.append(name)
        return fake_step_result(name, command)

    flow.run_step = fake_run_step
    try:
        steps = flow.run_flow(flow.flow_steps("2026-01-05"))
    finally:
        flow.run_step = original_run_step

    by_name = {step["name"]: step for step in steps}
    manifest = flow.build_manifest("2026-01-05", steps)
    return {
        "shadow_verify_failed": by_name["shadow_feature.verify"]["status"] == "FAILED",
        "plan_build_skipped": by_name["model_exp_plan.build"]["status"] == "SKIPPED",
        "plan_verify_skipped": by_name["model_exp_plan.verify"]["status"] == "SKIPPED",
        "downstream_not_executed": "model_exp_plan.build" not in executed and "model_exp_plan.verify" not in executed,
        "manifest_failed": manifest["status"] == "FAILED",
        "skip_reason_points_to_failure": by_name["model_exp_plan.build"].get("skip_reason") == "previous step failed: shadow_feature.verify",
    }


def verify_manifest_write() -> dict[str, bool]:
    with tempfile.TemporaryDirectory(prefix="top10-model-research-flow-") as tmp:
        output = Path(tmp) / "model_research_flow.json"
        steps = [
            fake_step_result("feature_gate.build", ["ok"]),
            fake_step_result("shadow_feature.verify", ["fail"]),
            flow.skipped_step("model_exp_plan.build", ["must-not-run"], "previous step failed: shadow_feature.verify"),
        ]
        manifest = flow.build_manifest("2026-01-05", steps)
        output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        payload = json.loads(output.read_text(encoding="utf-8"))
    return {
        "manifest_json_written": payload["schema_version"] == flow.SCHEMA_VERSION,
        "skipped_status_serialized": payload["steps"][-1]["status"] == "SKIPPED",
    }


def main() -> int:
    checks = {**verify_fail_fast(), **verify_manifest_write()}
    status = "OK" if all(checks.values()) else "FAILED"
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(
        json.dumps(
            {
                "schema_version": "model-research-flow-verification.v1",
                "status": status,
                "checks": checks,
                "note": "uses monkeypatched run_step; does not execute downstream build commands",
            },
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    if status == "OK":
        print(f"MODEL_RESEARCH_FLOW_OK output={ARTIFACT_PATH}")
        return 0
    print(f"MODEL_RESEARCH_FLOW_FAILED output={ARTIFACT_PATH}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
