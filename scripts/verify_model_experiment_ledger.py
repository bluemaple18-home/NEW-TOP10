#!/usr/bin/env python3
"""驗證 model experiment ledger integrity。

此 verifier 只檢查 ledger 結構與狀態，不重做 sealed OOS、replay 或 promotion gate。
"""

from __future__ import annotations

import argparse
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import model_experiment_ledger as ledger_lib  # noqa: E402


DEFAULT_OUTPUT = PROJECT_ROOT / "artifacts" / "model_experiments" / "model_experiment_ledger_verification_latest.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify model experiment ledger")
    parser.add_argument("--ledger", default=str(ledger_lib.DEFAULT_LEDGER))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--self-test", action="store_true")
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


def build_report(payload: dict[str, Any], input_path: Path | None) -> dict[str, Any]:
    checks = ledger_lib.validate_ledger_payload(payload)
    failed = [item for item in checks if not item["ok"]]
    return {
        "schema_version": "model-experiment-ledger-verification.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK" if not failed else "FAILED",
        "input": repo_path(input_path),
        "scope": {
            "checks_ledger_integrity_only": True,
            "does_not_check_no_hindsight": True,
            "does_not_check_sealed_oos": True,
            "does_not_check_replay": True,
            "does_not_check_rollback": True,
            "does_not_check_production_promotion": True,
        },
        "summary": {
            "check_count": len(checks),
            "failed_count": len(failed),
            "entry_count": len(payload.get("experiments", [])),
        },
        "checks": checks,
    }


def valid_sample() -> dict[str, Any]:
    entry = ledger_lib.make_entry(
        exp_type="feature",
        candidate="candidate_persistence",
        slug="smoke",
        hypothesis="candidate_persistence 會讓 sealed top10 return uplift >= 0.002",
        falsification=["sealed uplift <= 0"],
        baseline="artifacts/model_experiments/model_exp_run_manifest_2026-01-05.json",
        target_metrics=[{"name": "sealed_top10_return_uplift", "threshold": 0.002}],
        risk_metrics=[{"name": "replay_mdd_delta_max", "threshold": 0.01}],
        trigger_date="2026-01-19",
        grace_days=14,
        source_artifacts=["artifacts/model_experiments/model_exp_plan_2026-01-05.json"],
        source_labels=["self-test"],
        created_at="2026-01-05T00:00:00+00:00",
    )
    ledger = ledger_lib.empty_ledger()
    ledger["experiments"] = [entry]
    return ledger


def self_test_cases() -> dict[str, bool]:
    good = valid_sample()
    checks = ledger_lib.validate_ledger_payload(good)
    results: dict[str, bool] = {"accepts_valid_sample": all(item["ok"] for item in checks)}

    cases: dict[str, tuple[dict[str, Any], str]] = {}
    missing_baseline = json.loads(json.dumps(good))
    missing_baseline["experiments"][0]["baseline"] = ""
    cases["rejects_missing_baseline"] = (missing_baseline, ".baseline_nonempty")

    vague = json.loads(json.dumps(good))
    vague["experiments"][0]["hypothesis"] = "looks better"
    cases["rejects_vague_hypothesis"] = (vague, ".hypothesis_quantified")

    missing_policy = json.loads(json.dumps(good))
    missing_policy["experiments"][0]["decision_policy"].pop("pass", None)
    cases["rejects_missing_decision_policy"] = (missing_policy, ".decision_policy_rules")

    absolute_source = json.loads(json.dumps(good))
    absolute_source["experiments"][0]["source_artifacts"] = ["/Users/example/model_exp_plan.json"]
    cases["rejects_absolute_source_artifact"] = (absolute_source, ".source_artifacts_repo_relative")

    passed_without_metrics = json.loads(json.dumps(good))
    passed_without_metrics["experiments"][0]["status"] = "passed"
    passed_without_metrics["experiments"][0]["history"].append({"at": "2026-01-20T00:00:00+00:00", "verdict": "passed", "actual_metrics": {}})
    cases["rejects_passed_without_actual_metrics"] = (passed_without_metrics, ".resolved_has_actual_metrics")

    promotion_ready = json.loads(json.dumps(good))
    promotion_ready["experiments"][0]["promotion_ready"] = True
    cases["rejects_promotion_ready_true"] = (promotion_ready, "forbidden_promotion_outputs_absent")

    duplicate = json.loads(json.dumps(good))
    second = json.loads(json.dumps(good["experiments"][0]))
    second["hypothesis"] = "different hypothesis with AUC >= 0.9"
    duplicate["experiments"].append(second)
    cases["rejects_duplicate_id_collision"] = (duplicate, "id_unique")

    for name, (payload, expected_fragment) in cases.items():
        failed = [item for item in ledger_lib.validate_ledger_payload(payload) if not item["ok"]]
        results[name] = any(expected_fragment in item["name"] for item in failed)
    return results


def run_self_test() -> int:
    checks = self_test_cases()
    status = "OK" if all(checks.values()) else "FAILED"
    report = {
        "schema_version": "model-experiment-ledger-self-test.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "checks": checks,
    }
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if status == "OK" else 1


def main() -> int:
    args = parse_args()
    if args.self_test:
        return run_self_test()

    ledger_path = resolve_path(args.ledger)
    if ledger_path is None:
        raise RuntimeError("ledger path resolution failed")
    payload = ledger_lib.load_ledger(ledger_path)
    report = build_report(payload, ledger_path)
    output = resolve_path(args.output)
    if output is None:
        raise RuntimeError("output path resolution failed")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "output": repo_path(output), **report["summary"]}, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
