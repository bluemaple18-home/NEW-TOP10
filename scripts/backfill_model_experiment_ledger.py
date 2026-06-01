#!/usr/bin/env python3
"""從既有 model experiment artifacts 回填 ledger。

Backfill 不修改舊 artifact、不重跑模型；缺 verdict 的歷史資料標成 stale 或 partial。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import model_experiment_ledger as ledger_lib  # noqa: E402


MODEL_EXPERIMENTS_DIR = PROJECT_ROOT / "artifacts" / "model_experiments"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
SCHEMA_VERSION = "model-experiment-ledger-backfill.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="backfill model experiment ledger")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--ledger", default=str(ledger_lib.DEFAULT_LEDGER))
    parser.add_argument("--dry-run", action="store_true")
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


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def plan_files() -> list[Path]:
    return sorted(MODEL_EXPERIMENTS_DIR.glob("model_exp_plan_????-??-??.json"))


def report_files() -> list[Path]:
    return sorted(MODEL_EXPERIMENTS_DIR.glob("model_exp_result_report_????-??-??.json"))


def infer_date(path: Path) -> str:
    for part in path.stem.split("_"):
        if len(part) == 10 and part[4] == "-" and part[7] == "-":
            return part
    return date.today().isoformat()


def entry_from_plan_experiment(experiment: dict[str, Any], plan_path: Path) -> dict[str, Any] | None:
    ledger = experiment.get("ledger", {})
    if not ledger:
        return None
    run_date = infer_date(plan_path)
    return ledger_lib.make_entry(
        exp_type=str(ledger.get("type")),
        candidate=str(ledger.get("candidate")),
        slug=str(ledger.get("slug")),
        hypothesis=str(ledger.get("hypothesis")),
        falsification=[str(item) for item in ledger.get("falsification", [])],
        baseline=str(ledger.get("baseline") or f"artifacts/model_experiments/model_exp_run_manifest_{run_date}.json"),
        target_metrics=list(ledger.get("target_metrics", [])),
        risk_metrics=list(ledger.get("risk_metrics", [])),
        trigger_date=str(ledger.get("trigger", {}).get("date") or run_date),
        grace_days=int(ledger.get("trigger", {}).get("grace_days") or 14),
        source_artifacts=[repo_path(plan_path) or ""],
        source_labels=["backfill"],
    )


def apply_report_verdicts(ledger: dict[str, Any], report_path: Path) -> list[dict[str, Any]]:
    report = load_json(report_path)
    updates = []
    for decision in report.get("decisions", []):
        ledger_id = decision.get("ledger_id")
        if not ledger_id:
            updates.append({"status": "manual_review_required", "experiment_id": decision.get("experiment_id")})
            continue
        verdict = decision.get("verdict")
        if verdict in {"passed", "failed", "partial", "expired", "stale"}:
            ok, status = ledger_lib.resolve_entry(
                ledger,
                str(ledger_id),
                str(verdict),
                result_report=repo_path(report_path),
                actual_metrics=decision.get("actual_metrics") or {"status": decision.get("status")},
                reason=str(decision.get("next_action")),
            )
            updates.append({"status": status, "ledger_id": ledger_id, "ok": ok})
        else:
            updates.append({"status": "skipped_no_verdict", "ledger_id": ledger_id})
    return updates


def mark_unresolved_backfill(ledger: dict[str, Any], backfilled_ids: set[str]) -> None:
    for entry in ledger.get("experiments", []):
        if entry.get("id") not in backfilled_ids:
            continue
        if entry.get("status") != "pending":
            continue
        entry["status"] = "stale"
        entry["updated"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        entry.setdefault("history", []).append(
            {
                "at": entry["updated"],
                "action": "backfill_stale",
                "status": "stale",
                "verdict": "stale",
                "actual_metrics": {"source": "backfill_missing_result_report"},
            }
        )


def build_backfill(args: argparse.Namespace, ledger_path: Path) -> dict[str, Any]:
    ledger = ledger_lib.load_ledger(ledger_path)
    added = 0
    updated = 0
    skipped_existing = 0
    collisions: list[str] = []
    manual_review: list[dict[str, Any]] = []
    added_ids: set[str] = set()

    for plan_path in plan_files():
        plan = load_json(plan_path)
        for experiment in plan.get("experiments", []):
            entry = entry_from_plan_experiment(experiment, plan_path)
            if entry is None:
                manual_review.append({"artifact": repo_path(plan_path), "experiment_id": experiment.get("experiment_id"), "reason": "missing ledger contract"})
                continue
            result, _current = ledger_lib.add_or_update_entry(ledger, entry)
            if result == "added":
                added += 1
                added_ids.add(str(entry.get("id")))
            elif result == "updated":
                updated += 1
            elif result == "resolved_exists":
                skipped_existing += 1
            else:
                collisions.append(str(entry.get("id")))

    report_updates = []
    for report_path in report_files():
        report_updates.extend(apply_report_verdicts(ledger, report_path))
    manual_review.extend(item for item in report_updates if item.get("status") in {"manual_review_required", "missing_id"})
    mark_unresolved_backfill(ledger, added_ids)
    checks = ledger_lib.validate_ledger_payload(ledger)
    failed = [item for item in checks if not item["ok"]]
    if not args.dry_run and not failed and not collisions:
        ledger_lib.atomic_write_json(ledger_path, ledger)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK" if not failed and not collisions else "FAILED",
        "dry_run": bool(args.dry_run),
        "ledger": repo_path(ledger_path),
        "summary": {
            "added": added,
            "updated": updated,
            "skipped_existing": skipped_existing,
            "collision_count": len(collisions),
            "manual_review_count": len(manual_review),
            "report_update_count": len(report_updates),
            "entry_count_after": len(ledger.get("experiments", [])),
        },
        "collisions": collisions,
        "manual_review": manual_review[:50],
        "failed_checks": [item["name"] for item in failed[:20]],
    }


def sample_entry(slug: str, source_label: str) -> dict[str, Any]:
    return ledger_lib.make_entry(
        exp_type="feature",
        candidate="candidate_persistence",
        slug=slug,
        hypothesis=f"{slug} 會讓 sealed top10 return uplift >= 0.002",
        falsification=["sealed uplift <= 0"],
        baseline="artifacts/model_experiments/model_exp_run_manifest_2026-01-05.json",
        target_metrics=[{"name": "sealed_top10_return_uplift", "threshold": 0.002}],
        risk_metrics=[{"name": "replay_mdd_delta_max", "threshold": 0.01}],
        trigger_date="2026-01-19",
        grace_days=14,
        source_artifacts=["artifacts/model_experiments/model_exp_plan_2026-01-05.json"],
        source_labels=[source_label],
        created_at="2026-01-05T00:00:00+00:00",
    )


def self_test_cases() -> dict[str, bool]:
    active = sample_entry("active-pending", "model_research_flow")
    backfilled = sample_entry("backfilled-pending", "backfill")
    ledger = ledger_lib.empty_ledger()
    ledger["experiments"] = [active, backfilled]

    mark_unresolved_backfill(ledger, {str(backfilled["id"])})
    by_id = {entry["id"]: entry for entry in ledger["experiments"]}
    active_history_actions = [event.get("action") for event in by_id[active["id"]].get("history", [])]
    backfilled_history_actions = [event.get("action") for event in by_id[backfilled["id"]].get("history", [])]
    return {
        "preserves_pre_existing_pending_entry": by_id[active["id"]]["status"] == "pending",
        "does_not_append_stale_history_to_active_pending": "backfill_stale" not in active_history_actions,
        "marks_only_current_backfill_pending_entry_stale": by_id[backfilled["id"]]["status"] == "stale"
        and "backfill_stale" in backfilled_history_actions,
    }


def run_self_test() -> int:
    checks = self_test_cases()
    status = "OK" if all(checks.values()) else "FAILED"
    print(json.dumps({"schema_version": f"{SCHEMA_VERSION}-self-test", "status": status, "checks": checks}, ensure_ascii=False, sort_keys=True))
    return 0 if status == "OK" else 1


def main() -> int:
    args = parse_args()
    if args.self_test:
        return run_self_test()
    ledger_path = resolve_path(args.ledger)
    if ledger_path is None:
        raise RuntimeError("ledger path resolution failed")
    payload = build_backfill(args, ledger_path)
    output = resolve_path(args.output) or MODEL_EXPERIMENTS_DIR / f"model_experiment_ledger_backfill_{args.date}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output), **payload["summary"]}, ensure_ascii=False, sort_keys=True))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
