#!/usr/bin/env python3
"""模型實驗 ledger CLI。

Ledger 只保存研究假設的長期狀態，不做模型驗收、不放行正式升版。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER = PROJECT_ROOT / "artifacts" / "model_experiments" / "model_experiment_ledger.json"
SCHEMA_VERSION = "model-experiment-ledger.v1"
LEDGER_ROLE = "state_memory"
VALID_STATUSES = {"pending", "passed", "failed", "partial", "expired", "stale", "superseded"}
VALID_TYPES = {"feature", "label", "horizon", "universe", "overlay", "training_policy"}
RESOLVED_STATUSES = {"passed", "failed", "partial", "expired", "stale", "superseded"}
FORBIDDEN_OUTPUTS = {"PROMOTION_READY", "AUTO_PROMOTE", "MODEL_APPROVED"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="manage model experiment ledger")
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    parser.add_argument("--asof", default=date.today().isoformat())
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add")
    add.add_argument("--type", required=True, choices=sorted(VALID_TYPES))
    add.add_argument("--candidate", required=True)
    add.add_argument("--slug", required=True)
    add.add_argument("--hypothesis", required=True)
    add.add_argument("--falsification", action="append", default=[])
    add.add_argument("--baseline", required=True)
    add.add_argument("--target-metric", action="append", default=[])
    add.add_argument("--risk-metric", action="append", default=[])
    add.add_argument("--trigger-date", required=True)
    add.add_argument("--grace-days", type=int, default=14)
    add.add_argument("--source", action="append", default=[])
    add.add_argument("--source-artifact", action="append", default=[])

    list_cmd = sub.add_parser("list")
    list_cmd.add_argument("--status", choices=sorted(VALID_STATUSES), default=None)

    due = sub.add_parser("due")
    due.add_argument("--grace-days", type=int, default=None)
    due.add_argument("--no-expire", action="store_true")

    resolve = sub.add_parser("resolve")
    resolve.add_argument("--id", required=True)
    resolve.add_argument("--verdict", required=True, choices=sorted({"passed", "failed", "partial", "expired", "stale"}))
    resolve.add_argument("--result-report", default=None)
    resolve.add_argument("--actual-metric", action="append", default=[])
    resolve.add_argument("--reason", default=None)

    reschedule = sub.add_parser("reschedule")
    reschedule.add_argument("--id", required=True)
    reschedule.add_argument("--trigger-date", required=True)
    reschedule.add_argument("--reason", default=None)

    supersede = sub.add_parser("supersede")
    supersede.add_argument("--id", required=True)
    supersede.add_argument("--by-id", required=True)
    supersede.add_argument("--reason", default=None)

    sub.add_parser("stats")
    sub.add_parser("validate")
    return parser.parse_args()


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


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


def is_repo_relative(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    path = Path(value)
    return not path.is_absolute() and "~" not in value and "://" not in value and ".." not in path.parts


def parse_asof(value: str) -> date:
    return date.fromisoformat(value)


def slugify(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower()).strip("-")
    return text or "experiment"


def ledger_id(exp_type: str, candidate: str, slug: str) -> str:
    return f"{exp_type}:{candidate}:{slugify(slug)}"


def normalize_hypothesis(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).lower()


def parse_metric(text: str) -> dict[str, Any]:
    if ":" not in text:
        return {"name": text, "threshold": None}
    name, raw = text.split(":", 1)
    try:
        threshold: float | str | None = float(raw)
    except ValueError:
        threshold = raw
    return {"name": name, "threshold": threshold}


def metrics_from(items: list[str]) -> list[dict[str, Any]]:
    return [parse_metric(item) for item in items]


def default_decision_policy(target_metrics: list[dict[str, Any]], risk_metrics: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "pass": "all target metrics meet threshold and risk metrics are not degraded",
        "fail": "primary target metric fails threshold or any risk metric breaks threshold",
        "partial": "target improves but evidence is incomplete or windows conflict",
        "target_metrics": target_metrics,
        "risk_metrics": risk_metrics,
    }


def empty_ledger() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "ledger_role": LEDGER_ROLE,
        "production_promotion_allowed": False,
        "updated": now_iso(),
        "experiments": [],
    }


def load_ledger(path: Path) -> dict[str, Any]:
    if not path.exists():
        return empty_ledger()
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_ledger(payload: dict[str, Any]) -> dict[str, Any]:
    payload.setdefault("schema_version", SCHEMA_VERSION)
    payload.setdefault("ledger_role", LEDGER_ROLE)
    payload["production_promotion_allowed"] = False
    payload.setdefault("experiments", [])
    payload["experiments"] = sorted(payload["experiments"], key=lambda item: str(item.get("id")))
    payload["updated"] = now_iso()
    return payload


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = normalize_ledger(payload)
    data = json.dumps(normalized, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(data)
        tmp_name = handle.name
    os.replace(tmp_name, path)


def find_entry(ledger: dict[str, Any], exp_id: str) -> dict[str, Any] | None:
    for item in ledger.get("experiments", []):
        if item.get("id") == exp_id:
            return item
    return None


def merge_sources(*groups: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for group in groups:
        for item in group:
            if not item or item in seen:
                continue
            seen.add(item)
            result.append(item)
    return sorted(result)


def make_entry(
    *,
    exp_type: str,
    candidate: str,
    slug: str,
    hypothesis: str,
    falsification: list[str],
    baseline: str,
    target_metrics: list[dict[str, Any]],
    risk_metrics: list[dict[str, Any]],
    trigger_date: str,
    grace_days: int,
    source_artifacts: list[str],
    source_labels: list[str],
    created_at: str | None = None,
) -> dict[str, Any]:
    exp_id = ledger_id(exp_type, candidate, slug)
    timestamp = created_at or now_iso()
    return {
        "id": exp_id,
        "type": exp_type,
        "candidate": candidate,
        "slug": slugify(slug),
        "hypothesis": hypothesis.strip(),
        "falsification": falsification,
        "baseline": baseline,
        "target_metrics": target_metrics,
        "risk_metrics": risk_metrics,
        "decision_policy": default_decision_policy(target_metrics, risk_metrics),
        "evidence_requirements": {
            "sealed_oos": True,
            "production_replay": True,
            "walk_forward": True,
            "portfolio_replay": True,
        },
        "trigger": {"date": trigger_date, "grace_days": grace_days},
        "status": "pending",
        "created": timestamp,
        "updated": timestamp,
        "source_artifacts": merge_sources(source_artifacts),
        "source": sorted(set(source_labels)),
        "history": [
            {
                "at": timestamp,
                "action": "created",
                "status": "pending",
                "source_artifacts": merge_sources(source_artifacts),
            }
        ],
        "production_promotion_allowed": False,
    }


def add_or_update_entry(ledger: dict[str, Any], entry: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    existing = find_entry(ledger, str(entry["id"]))
    if existing is None:
        ledger.setdefault("experiments", []).append(entry)
        return "added", entry
    if normalize_hypothesis(existing.get("hypothesis", "")) != normalize_hypothesis(entry.get("hypothesis", "")):
        return "collision", existing
    if existing.get("status") in RESOLVED_STATUSES and existing.get("status") != "expired":
        return "resolved_exists", existing

    timestamp = now_iso()
    existing["trigger"] = entry["trigger"]
    existing["baseline"] = entry["baseline"]
    existing["target_metrics"] = entry["target_metrics"]
    existing["risk_metrics"] = entry["risk_metrics"]
    existing["decision_policy"] = entry["decision_policy"]
    existing["evidence_requirements"] = entry["evidence_requirements"]
    existing["source_artifacts"] = merge_sources(existing.get("source_artifacts", []), entry.get("source_artifacts", []))
    existing["source"] = sorted(set(existing.get("source", [])) | set(entry.get("source", [])))
    existing["updated"] = timestamp
    existing.setdefault("history", []).append(
        {
            "at": timestamp,
            "action": "updated",
            "status": existing.get("status"),
            "source_artifacts": entry.get("source_artifacts", []),
        }
    )
    return "updated", existing


def resolve_entry(
    ledger: dict[str, Any],
    exp_id: str,
    verdict: str,
    *,
    result_report: str | None,
    actual_metrics: dict[str, Any],
    reason: str | None,
) -> tuple[bool, str]:
    entry = find_entry(ledger, exp_id)
    if entry is None:
        return False, "missing_id"
    timestamp = now_iso()
    entry["status"] = verdict
    entry["updated"] = timestamp
    if result_report:
        entry["source_artifacts"] = merge_sources(entry.get("source_artifacts", []), [result_report])
    entry.setdefault("history", []).append(
        {
            "at": timestamp,
            "action": "resolved",
            "status": verdict,
            "verdict": verdict,
            "result_report": result_report,
            "actual_metrics": actual_metrics,
            "reason": reason,
            "production_promotion_allowed": False,
        }
    )
    return True, "resolved"


def reschedule_entry(ledger: dict[str, Any], exp_id: str, trigger_date: str, reason: str | None) -> tuple[bool, str]:
    entry = find_entry(ledger, exp_id)
    if entry is None:
        return False, "missing_id"
    timestamp = now_iso()
    entry["status"] = "pending"
    entry["trigger"] = {**entry.get("trigger", {}), "date": trigger_date}
    entry["updated"] = timestamp
    entry.setdefault("history", []).append(
        {"at": timestamp, "action": "rescheduled", "status": "pending", "trigger_date": trigger_date, "reason": reason}
    )
    return True, "rescheduled"


def supersede_entry(ledger: dict[str, Any], exp_id: str, by_id: str, reason: str | None) -> tuple[bool, str]:
    entry = find_entry(ledger, exp_id)
    if entry is None:
        return False, "missing_id"
    timestamp = now_iso()
    entry["status"] = "superseded"
    entry["superseded_by"] = by_id
    entry["updated"] = timestamp
    entry.setdefault("history", []).append(
        {"at": timestamp, "action": "superseded", "status": "superseded", "by_id": by_id, "reason": reason}
    )
    return True, "superseded"


def due_entries(ledger: dict[str, Any], asof: date, grace_days: int | None, mark_expired: bool) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    timestamp = now_iso()
    for entry in ledger.get("experiments", []):
        if entry.get("status") != "pending":
            continue
        trigger = entry.get("trigger", {})
        trigger_date = trigger.get("date")
        if not trigger_date:
            continue
        due_date = date.fromisoformat(trigger_date)
        if due_date > asof:
            continue
        days = int(grace_days if grace_days is not None else trigger.get("grace_days", 14))
        expired = asof > due_date + timedelta(days=days)
        if expired and mark_expired:
            entry["status"] = "expired"
            entry["updated"] = timestamp
            entry.setdefault("history", []).append(
                {"at": timestamp, "action": "expired", "status": "expired", "verdict": "expired", "actual_metrics": {}}
            )
        result.append({"id": entry.get("id"), "trigger_date": trigger_date, "expired": expired, "status": entry.get("status")})
    return sorted(result, key=lambda item: str(item.get("id")))


def ledger_stats(ledger: dict[str, Any], asof: str | None = None) -> dict[str, Any]:
    counts = {status: 0 for status in sorted(VALID_STATUSES)}
    by_candidate: dict[str, dict[str, int]] = {}
    for entry in ledger.get("experiments", []):
        status = str(entry.get("status"))
        if status in counts:
            counts[status] += 1
        candidate = str(entry.get("candidate"))
        by_candidate.setdefault(candidate, {key: 0 for key in sorted(VALID_STATUSES)})
        if status in by_candidate[candidate]:
            by_candidate[candidate][status] += 1
    denominator = counts["passed"] + counts["failed"] + counts["partial"]
    hit_rate = None if denominator == 0 else round(counts["passed"] / denominator, 4)
    return {
        "schema_version": "model-experiment-ledger-stats-inline.v1",
        "asof": asof,
        "entry_count": len(ledger.get("experiments", [])),
        "counts": counts,
        "candidate_status_counts": by_candidate,
        "candidate_hit_rate": hit_rate,
    }


def find_forbidden_truths(value: Any, path: str = "$") -> list[str]:
    failures: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in {"promotion_ready", "production_promotion_allowed"} and child is True:
                failures.append(child_path)
            if isinstance(child, str) and child in FORBIDDEN_OUTPUTS:
                failures.append(child_path)
            failures.extend(find_forbidden_truths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            failures.extend(find_forbidden_truths(child, f"{path}[{index}]"))
    return failures


def validate_ledger_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    checks.append({"name": "schema_version", "ok": payload.get("schema_version") == SCHEMA_VERSION, "value": payload.get("schema_version")})
    checks.append({"name": "ledger_role", "ok": payload.get("ledger_role") == LEDGER_ROLE, "value": payload.get("ledger_role")})
    checks.append({"name": "production_promotion_allowed_false", "ok": payload.get("production_promotion_allowed") is False, "value": payload.get("production_promotion_allowed")})
    entries = payload.get("experiments", [])
    ids = [entry.get("id") for entry in entries]
    checks.append({"name": "id_unique", "ok": len(ids) == len(set(ids)), "value": ids})
    forbidden = find_forbidden_truths(payload)
    checks.append({"name": "forbidden_promotion_outputs_absent", "ok": not forbidden, "value": forbidden})

    seen_hypothesis: dict[str, str] = {}
    for index, entry in enumerate(entries):
        prefix = str(entry.get("id") or f"entry_{index}")
        status = entry.get("status")
        source_artifacts = entry.get("source_artifacts", [])
        history = entry.get("history", [])
        policy = entry.get("decision_policy", {})
        hypothesis = str(entry.get("hypothesis") or "")

        checks.extend(
            [
                {"name": f"{prefix}.type_valid", "ok": entry.get("type") in VALID_TYPES, "value": entry.get("type")},
                {"name": f"{prefix}.status_valid", "ok": status in VALID_STATUSES, "value": status},
                {"name": f"{prefix}.baseline_nonempty", "ok": bool(str(entry.get("baseline") or "").strip()), "value": entry.get("baseline")},
                {
                    "name": f"{prefix}.hypothesis_quantified",
                    "ok": bool(re.search(r"(>=|<=|>|<|=|提升|降低|uplift|return|auc|metric|risk|drawdown)", hypothesis, re.I))
                    and len(hypothesis.strip()) >= 16,
                    "value": hypothesis,
                },
                {
                    "name": f"{prefix}.decision_policy_rules",
                    "ok": isinstance(policy, dict) and all(policy.get(key) for key in ["pass", "fail", "partial"]),
                    "value": policy,
                },
                {"name": f"{prefix}.source_artifacts_repo_relative", "ok": all(is_repo_relative(item) for item in source_artifacts), "value": source_artifacts},
                {"name": f"{prefix}.history_nonempty", "ok": isinstance(history, list) and bool(history), "value": history},
                {"name": f"{prefix}.production_promotion_allowed_false", "ok": entry.get("production_promotion_allowed") is False, "value": entry.get("production_promotion_allowed")},
            ]
        )
        if status == "pending":
            trigger = entry.get("trigger", {})
            checks.append({"name": f"{prefix}.pending_has_trigger", "ok": bool(trigger.get("date")), "value": trigger})
        if status in {"passed", "failed", "partial"}:
            verdict_events = [event for event in history if event.get("verdict") == status]
            checks.append({"name": f"{prefix}.resolved_has_history_verdict", "ok": bool(verdict_events), "value": history})
            checks.append(
                {
                    "name": f"{prefix}.resolved_has_actual_metrics",
                    "ok": any(isinstance(event.get("actual_metrics"), dict) and bool(event.get("actual_metrics")) for event in verdict_events),
                    "value": verdict_events,
                }
            )
        if status in {"expired", "stale"}:
            checks.append(
                {
                    "name": f"{prefix}.terminal_has_history_verdict",
                    "ok": any(event.get("verdict") == status or event.get("status") == status for event in history),
                    "value": history,
                }
            )
        normalized = normalize_hypothesis(hypothesis)
        if prefix in seen_hypothesis:
            checks.append({"name": f"{prefix}.duplicate_hypothesis_same", "ok": seen_hypothesis[prefix] == normalized, "value": hypothesis})
        seen_hypothesis[prefix] = normalized
    return checks


def print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False))


def entry_from_args(args: argparse.Namespace) -> dict[str, Any]:
    target_metrics = metrics_from(args.target_metric)
    risk_metrics = metrics_from(args.risk_metric)
    source_artifacts = merge_sources(args.source_artifact, [item for item in args.source if is_repo_relative(item)])
    return make_entry(
        exp_type=args.type,
        candidate=args.candidate,
        slug=args.slug,
        hypothesis=args.hypothesis,
        falsification=args.falsification,
        baseline=args.baseline,
        target_metrics=target_metrics,
        risk_metrics=risk_metrics,
        trigger_date=args.trigger_date,
        grace_days=args.grace_days,
        source_artifacts=source_artifacts,
        source_labels=[item for item in args.source if not is_repo_relative(item)],
    )


def main() -> int:
    args = parse_args()
    ledger_path = resolve_path(args.ledger)
    if ledger_path is None:
        raise RuntimeError("ledger path resolution failed")
    ledger = load_ledger(ledger_path)
    asof = parse_asof(args.asof)
    changed = False
    exit_code = 0

    if args.command == "add":
        result, current = add_or_update_entry(ledger, entry_from_args(args))
        changed = result in {"added", "updated"}
        exit_code = 0 if result in {"added", "updated"} else 2
        print_json({"status": result, "id": current.get("id") if current else None, "ledger": repo_path(ledger_path)})
    elif args.command == "list":
        rows = [
            {"id": item.get("id"), "status": item.get("status"), "candidate": item.get("candidate"), "trigger": item.get("trigger")}
            for item in ledger.get("experiments", [])
            if args.status is None or item.get("status") == args.status
        ]
        print_json({"status": "OK", "entries": rows})
    elif args.command == "due":
        rows = due_entries(ledger, asof, args.grace_days, mark_expired=not args.no_expire)
        changed = any(item.get("status") == "expired" for item in rows) and not args.no_expire
        print_json({"status": "OK", "due": rows, "due_count": len(rows)})
    elif args.command == "resolve":
        metrics = {item["name"]: item.get("threshold") for item in metrics_from(args.actual_metric)}
        report_path = repo_path(resolve_path(args.result_report)) if args.result_report else None
        ok, status = resolve_entry(ledger, args.id, args.verdict, result_report=report_path, actual_metrics=metrics, reason=args.reason)
        changed = ok
        exit_code = 0 if ok else 2
        print_json({"status": status, "id": args.id})
    elif args.command == "reschedule":
        ok, status = reschedule_entry(ledger, args.id, args.trigger_date, args.reason)
        changed = ok
        exit_code = 0 if ok else 2
        print_json({"status": status, "id": args.id})
    elif args.command == "supersede":
        ok, status = supersede_entry(ledger, args.id, args.by_id, args.reason)
        changed = ok
        exit_code = 0 if ok else 2
        print_json({"status": status, "id": args.id, "by_id": args.by_id})
    elif args.command == "stats":
        print_json({"status": "OK", **ledger_stats(ledger, args.asof)})
    elif args.command == "validate":
        checks = validate_ledger_payload(ledger)
        failed = [item for item in checks if not item["ok"]]
        exit_code = 0 if not failed else 1
        print_json({"status": "OK" if not failed else "FAILED", "check_count": len(checks), "failed_count": len(failed), "failed": failed})

    if changed:
        atomic_write_json(ledger_path, ledger)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
