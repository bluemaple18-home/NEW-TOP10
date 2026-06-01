#!/usr/bin/env python3
"""建立 model promotion ledger evidence adapter artifact。

此腳本只回答候選模型是否有可追溯 ledger evidence，不取代正式升版 gate。
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import model_experiment_ledger as ledger_lib  # noqa: E402


OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "model_experiments"
SCHEMA_VERSION = "model-promotion-review-ledger-evidence.v1"
ALLOWED_OUTPUTS = {"MISSING_LEDGER_EVIDENCE", "LEDGER_EVIDENCE_BLOCKED", "LEDGER_EVIDENCE_OK"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build model promotion ledger evidence review")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--ledger", default=str(ledger_lib.DEFAULT_LEDGER))
    parser.add_argument("--ledger-id", default=None)
    parser.add_argument("--candidate", default=None)
    parser.add_argument("--manual-override-reason", default=None)
    parser.add_argument("--output", default=None)
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


def candidate_entries(ledger: dict[str, Any], ledger_id: str | None, candidate: str | None) -> list[dict[str, Any]]:
    entries = ledger.get("experiments", [])
    if ledger_id:
        return [entry for entry in entries if entry.get("id") == ledger_id]
    if candidate:
        return [entry for entry in entries if entry.get("candidate") == candidate]
    return []


def traceable(entry: dict[str, Any]) -> bool:
    artifacts = entry.get("source_artifacts", [])
    has_result = any("model_exp_result_report_" in item for item in artifacts)
    has_plan_or_manifest = any("model_exp_run_manifest_" in item or "model_exp_plan_" in item for item in artifacts)
    return has_result and has_plan_or_manifest


def build_review(args: argparse.Namespace, ledger_path: Path) -> dict[str, Any]:
    ledger = ledger_lib.load_ledger(ledger_path)
    checks = ledger_lib.validate_ledger_payload(ledger)
    failed_checks = [item for item in checks if not item["ok"]]
    entries = candidate_entries(ledger, args.ledger_id, args.candidate)
    blockers: list[str] = []
    status = "LEDGER_EVIDENCE_OK"

    if not args.ledger_id and not args.candidate:
        status = "MISSING_LEDGER_EVIDENCE"
        blockers.append("candidate selector required: provide --ledger-id or --candidate")
    if not entries:
        status = "MISSING_LEDGER_EVIDENCE"
        blockers.append("candidate ledger entry not found")
    if failed_checks:
        status = "LEDGER_EVIDENCE_BLOCKED"
        blockers.append("ledger integrity verification failed")
    expired_required = [entry.get("id") for entry in ledger.get("experiments", []) if entry.get("status") == "expired"]
    if expired_required:
        status = "LEDGER_EVIDENCE_BLOCKED"
        blockers.append("expired required experiments exist")

    evidence_rows = []
    for entry in entries:
        entry_blockers = []
        if entry.get("status") != "passed" and not args.manual_override_reason:
            entry_blockers.append("ledger status is not passed and no manual override reason was supplied")
        if not traceable(entry):
            entry_blockers.append("source artifacts do not trace to both result report and plan/run manifest")
        if entry_blockers:
            status = "LEDGER_EVIDENCE_BLOCKED" if status != "MISSING_LEDGER_EVIDENCE" else status
            blockers.extend(entry_blockers)
        evidence_rows.append(
            {
                "ledger_id": entry.get("id"),
                "candidate": entry.get("candidate"),
                "ledger_status": entry.get("status"),
                "source_artifacts": entry.get("source_artifacts", []),
                "traceable": traceable(entry),
                "blockers": entry_blockers,
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": status,
        "allowed_outputs": sorted(ALLOWED_OUTPUTS),
        "contract": {
            "ledger_evidence_adapter_only": True,
            "does_not_replace_sealed_oos": True,
            "does_not_replace_replay": True,
            "does_not_replace_rollback": True,
            "does_not_replace_model_group_acceptance": True,
            "does_not_replace_human_review": True,
            "does_not_output_promotion_ready": True,
            "production_promotion_allowed": False,
        },
        "inputs": {
            "ledger": repo_path(ledger_path),
            "ledger_id": args.ledger_id,
            "candidate": args.candidate,
        },
        "summary": {
            "evidence_count": len(evidence_rows),
            "blockers": sorted(set(blockers)),
            "expired_required_experiments": expired_required,
            "ledger_failed_checks": [item["name"] for item in failed_checks[:10]],
        },
        "evidence": evidence_rows,
        "manual_override_reason": args.manual_override_reason,
    }


def main() -> int:
    args = parse_args()
    if args.self_test:
        return run_self_test()
    ledger_path = resolve_path(args.ledger)
    if ledger_path is None:
        raise RuntimeError("ledger path resolution failed")
    payload = build_review(args, ledger_path)
    output = resolve_path(args.output) or OUTPUT_DIR / f"model_promotion_review_{args.date}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if "PROMOTION_READY" in text or "AUTO_PROMOTE" in text or "MODEL_APPROVED" in text:
        raise RuntimeError("forbidden promotion output detected")
    output.write_text(text, encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output), **payload["summary"]}, ensure_ascii=False, sort_keys=True))
    return 0 if payload["status"] in ALLOWED_OUTPUTS else 1


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Model Promotion Ledger Evidence",
        "",
        f"- status：`{payload['status']}`",
        f"- evidence_count：`{payload['summary']['evidence_count']}`",
        f"- production_promotion_allowed：`{payload['contract']['production_promotion_allowed']}`",
        "",
        "## Blockers",
        "",
    ]
    for item in payload["summary"]["blockers"]:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def sample_entry(*, status: str = "passed", traceable_sources: bool = True) -> dict[str, Any]:
    entry = ledger_lib.make_entry(
        exp_type="feature",
        candidate="candidate_persistence",
        slug="promotion-smoke",
        hypothesis="candidate_persistence 會讓 sealed top10 return uplift >= 0.002",
        falsification=["sealed uplift <= 0"],
        baseline="artifacts/model_experiments/model_exp_run_manifest_2026-01-05.json",
        target_metrics=[{"name": "sealed_top10_return_uplift", "threshold": 0.002}],
        risk_metrics=[{"name": "replay_mdd_delta_max", "threshold": 0.01}],
        trigger_date="2026-01-19",
        grace_days=14,
        source_artifacts=[
            "artifacts/model_experiments/model_exp_plan_2026-01-05.json",
            "artifacts/model_experiments/model_exp_result_report_2026-01-05.json",
        ]
        if traceable_sources
        else ["artifacts/model_experiments/model_exp_result_report_2026-01-05.json"],
        source_labels=["self-test"],
        created_at="2026-01-05T00:00:00+00:00",
    )
    if status == "passed":
        entry["status"] = "passed"
        entry["history"].append(
            {
                "at": "2026-01-20T00:00:00+00:00",
                "action": "resolved",
                "status": "passed",
                "verdict": "passed",
                "actual_metrics": {"sealed_top10_return_uplift": 0.003},
                "production_promotion_allowed": False,
            }
        )
    return entry


def sample_ledger(entry: dict[str, Any]) -> dict[str, Any]:
    ledger = ledger_lib.empty_ledger()
    ledger["experiments"] = [entry]
    return ledger


def self_test_cases() -> dict[str, bool]:
    with tempfile.TemporaryDirectory(prefix="top10-promotion-review-") as tmp:
        ledger_path = Path(tmp) / "ledger.json"

        passed_entry = sample_entry(status="passed", traceable_sources=True)
        ledger_lib.atomic_write_json(ledger_path, sample_ledger(passed_entry))
        missing_selector = build_review(
            argparse.Namespace(
                date="2026-01-05",
                ledger=str(ledger_path),
                ledger_id=None,
                candidate=None,
                manual_override_reason=None,
                output=None,
                self_test=True,
            ),
            ledger_path,
        )

        untraceable_entry = sample_entry(status="pending", traceable_sources=False)
        ledger_lib.atomic_write_json(ledger_path, sample_ledger(untraceable_entry))
        manual_override_untraceable = build_review(
            argparse.Namespace(
                date="2026-01-05",
                ledger=str(ledger_path),
                ledger_id=untraceable_entry["id"],
                candidate=None,
                manual_override_reason="human accepted pending metrics",
                output=None,
                self_test=True,
            ),
            ledger_path,
        )

    return {
        "default_with_passed_entry_requires_candidate_selector": missing_selector["status"] == "MISSING_LEDGER_EVIDENCE"
        and "candidate selector required: provide --ledger-id or --candidate" in missing_selector["summary"]["blockers"],
        "manual_override_does_not_clear_traceability_blocker": manual_override_untraceable["status"] == "LEDGER_EVIDENCE_BLOCKED"
        and "source artifacts do not trace to both result report and plan/run manifest" in manual_override_untraceable["summary"]["blockers"],
    }


def run_self_test() -> int:
    checks = self_test_cases()
    status = "OK" if all(checks.values()) else "FAILED"
    print(json.dumps({"schema_version": f"{SCHEMA_VERSION}-self-test", "status": status, "checks": checks}, ensure_ascii=False, sort_keys=True))
    return 0 if status == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
