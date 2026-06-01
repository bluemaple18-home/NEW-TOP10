#!/usr/bin/env python3
"""產出 model experiment ledger 摘要。

報告只露出治理摘要，不輸出完整 ledger，也不影響 ranking。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import model_experiment_ledger as ledger_lib  # noqa: E402


OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "model_experiments"
SCHEMA_VERSION = "model-experiment-ledger-stats.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build model experiment ledger stats")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--ledger", default=str(ledger_lib.DEFAULT_LEDGER))
    parser.add_argument("--output", default=None)
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


def entry_reason(entry: dict[str, Any]) -> str | None:
    history = entry.get("history", [])
    for event in reversed(history):
        if event.get("reason"):
            return str(event.get("reason"))
        if event.get("verdict"):
            return str(event.get("verdict"))
    return None


def due_soon_entries(entries: list[dict[str, Any]], asof: date) -> list[dict[str, Any]]:
    rows = []
    horizon = asof + timedelta(days=7)
    for entry in entries:
        if entry.get("status") != "pending":
            continue
        trigger_date = entry.get("trigger", {}).get("date")
        if not trigger_date:
            continue
        parsed = date.fromisoformat(trigger_date)
        if parsed <= horizon:
            rows.append(
                {
                    "id": entry.get("id"),
                    "candidate": entry.get("candidate"),
                    "trigger_date": trigger_date,
                    "next_action": "build result report or reschedule before trigger grace expires",
                }
            )
    return sorted(rows, key=lambda item: str(item.get("trigger_date")) + str(item.get("id")))


def recent_failed_partial(entries: list[dict[str, Any]], asof: date) -> list[dict[str, Any]]:
    cutoff = asof - timedelta(days=14)
    rows = []
    for entry in entries:
        if entry.get("status") not in {"failed", "partial"}:
            continue
        updated = str(entry.get("updated", ""))[:10]
        if updated and date.fromisoformat(updated) < cutoff:
            continue
        rows.append(
            {
                "id": entry.get("id"),
                "candidate": entry.get("candidate"),
                "status": entry.get("status"),
                "reason": entry_reason(entry),
            }
        )
    return sorted(rows, key=lambda item: str(item.get("id")))


def repeated_failed_families(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for entry in entries:
        if entry.get("status") == "failed":
            counts[str(entry.get("candidate"))] = counts.get(str(entry.get("candidate")), 0) + 1
    return [{"candidate": candidate, "failed_count": count} for candidate, count in sorted(counts.items()) if count >= 2]


def next_priorities(entries: list[dict[str, Any]], asof: date) -> list[str]:
    due = due_soon_entries(entries, asof)
    if due:
        return [f"resolve_or_reschedule:{item['id']}" for item in due[:5]]
    partial = [entry for entry in entries if entry.get("status") == "partial"]
    if partial:
        return [f"complete_evidence:{entry.get('id')}" for entry in partial[:5]]
    return ["register_next_pre_registered_model_experiment"]


def build_stats(ledger: dict[str, Any], asof_text: str, ledger_path: Path) -> dict[str, Any]:
    asof = date.fromisoformat(asof_text)
    entries = ledger.get("experiments", [])
    base = ledger_lib.ledger_stats(ledger, asof_text)
    expired_count = base["counts"].get("expired", 0)
    blocked_reasons = []
    if expired_count:
        blocked_reasons.append("expired required experiments need follow-through before promotion review")
    if base["counts"].get("partial", 0):
        blocked_reasons.append("partial experiments require more evidence")
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": asof_text,
        "ledger": repo_path(ledger_path),
        "status": "OK",
        "summary": {
            **base,
            "pending_due_soon": due_soon_entries(entries, asof),
            "failed_partial_since_last_run": recent_failed_partial(entries, asof),
            "expired_count": expired_count,
            "repeated_failed_hypothesis_family": repeated_failed_families(entries),
            "next_research_priorities": next_priorities(entries, asof),
            "blocked_promotion_reasons": blocked_reasons,
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Model Experiment Ledger Stats",
        "",
        f"- status：`{payload['status']}`",
        f"- date：`{payload['date']}`",
        f"- entry_count：`{summary['entry_count']}`",
        f"- candidate_hit_rate：`{summary['candidate_hit_rate']}`",
        f"- expired_count：`{summary['expired_count']}`",
        "",
        "## Pending Due Soon",
        "",
    ]
    for item in summary["pending_due_soon"]:
        lines.append(f"- `{item['id']}` due={item['trigger_date']} action={item['next_action']}")
    lines.extend(["", "## Next Research Priorities", ""])
    for item in summary["next_research_priorities"]:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    ledger_path = resolve_path(args.ledger)
    if ledger_path is None:
        raise RuntimeError("ledger path resolution failed")
    ledger = ledger_lib.load_ledger(ledger_path)
    payload = build_stats(ledger, args.date, ledger_path)
    output = resolve_path(args.output) or OUTPUT_DIR / f"model_experiment_ledger_stats_{args.date}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output), **payload["summary"]["counts"]}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
