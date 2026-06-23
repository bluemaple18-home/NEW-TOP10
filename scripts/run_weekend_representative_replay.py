#!/usr/bin/env python3
"""執行 weekend frontier queue 的 representative replay。"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from run_liquidity_replay_v2_batch import append_jsonl, process_row, read_jsonl
from weekend_training_common import (
    PRODUCTION_IMPACT,
    RUN_HISTORY_PATH,
    WEEKEND_DIR,
    now_utc,
    queue_paths,
    repo_path,
    representative_paths,
    resolve_path,
    write_json,
    write_text,
)


SCHEMA_VERSION = "weekend-representative-replay.v1"
SOURCE = "weekend_representative_replay"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="run weekend representative replay")
    parser.add_argument("--date", required=True)
    parser.add_argument("--queue", default=None)
    parser.add_argument("--batch-size", type=int, required=True)
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--append-run-history", action="store_true")
    parser.add_argument("--rerun", action="store_true")
    parser.add_argument("--force-append", action="store_true")
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def weekend_decision(row: dict[str, Any]) -> tuple[str, str, list[str]]:
    candidate = row.get("candidate") if isinstance(row.get("candidate"), dict) else {}
    daily_count = int(candidate.get("daily_count") or 0)
    trade_count = int(candidate.get("trade_count") or 0)
    return_delta = safe_float(row.get("return_delta"))
    drawdown_delta = safe_float(row.get("drawdown_delta"))
    turnover_delta = safe_float(row.get("turnover_delta"))
    concentration_delta = safe_float(row.get("concentration_delta"))
    reasons: list[str] = []
    if daily_count < 80:
        reasons.append("DAILY_COUNT_BELOW_80")
    if trade_count <= 0:
        reasons.append("TRADE_COUNT_TOO_LOW")
    if reasons:
        return "LOW_INFORMATION", "ordinary", reasons
    if return_delta >= 0.02 and drawdown_delta >= -0.005 and concentration_delta <= 0.03 and turnover_delta <= 0.05:
        return "NEXT_STAGE_CANDIDATE", "next_stage", []
    if return_delta > 0:
        if drawdown_delta < -0.005:
            reasons.append("DRAWDOWN_WORSE_THAN_LIMIT")
        if concentration_delta > 0.03:
            reasons.append("CONCENTRATION_WORSE_THAN_LIMIT")
        if turnover_delta > 0.05:
            reasons.append("TURNOVER_WORSE_THAN_LIMIT")
        return "MONITOR_ONLY", "risk_worse_return_positive", reasons
    reasons.append("RETURN_DELTA_NON_POSITIVE")
    return "REJECTED", "rejected", reasons


def selected_queue_rows(queue_path: Path, start_index: int, batch_size: int) -> list[tuple[int, dict[str, Any]]]:
    payload = read_json(queue_path)
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    rows = [
        row
        for row in items
        if row.get("queue_type") == "REPRESENTATIVE_REPLAY" and row.get("current_status") == "PENDING"
    ]
    rows = sorted(rows, key=lambda row: (-int(row.get("priority_score") or 0), str(row.get("combo_id") or "")))
    end = start_index + max(0, batch_size)
    return list(enumerate(rows[start_index:end], start=start_index))


def normalize_result(index: int, row: dict[str, Any], run_dir: Path, rerun: bool) -> dict[str, Any]:
    result = process_row(index, row, run_dir, rerun)
    if result.get("status") != "completed":
        result["decision"] = "RUNNER_FAILED"
        result["insight_level"] = "ordinary"
        result["failure_reasons"] = ["RUNNER_FAILED"]
        return result
    decision, insight, reasons = weekend_decision(result)
    result["source_decision"] = result.get("decision")
    result["decision"] = decision
    result["insight_level"] = insight
    result["failure_reasons"] = reasons
    return result


def run_history_row(row: dict[str, Any], artifact_path: Path, finished_at: str) -> dict[str, Any]:
    return {
        "schema_version": "research-map-run-history.v2",
        "map_version": "v2",
        "source": SOURCE,
        "status": row.get("status"),
        "combo_id": row.get("combo_id"),
        "dimensions": row.get("dimensions"),
        "decision": row.get("decision"),
        "insight_level": row.get("insight_level"),
        "return_delta": row.get("return_delta"),
        "drawdown_delta": row.get("drawdown_delta"),
        "turnover_delta": row.get("turnover_delta"),
        "concentration_delta": row.get("concentration_delta"),
        "failure_reasons": row.get("failure_reasons"),
        "artifact_path": repo_path(artifact_path),
        "finished_at": finished_at,
    }


def append_history(rows: list[dict[str, Any]], artifact_path: Path, finished_at: str, force_append: bool) -> int:
    existing = {
        (str(row.get("source") or ""), str(row.get("combo_id") or ""))
        for row in read_jsonl(RUN_HISTORY_PATH)
    }
    payload: list[dict[str, Any]] = []
    for row in rows:
        if row.get("status") != "completed":
            continue
        key = (SOURCE, str(row.get("combo_id") or ""))
        if not force_append and key in existing:
            continue
        payload.append(run_history_row(row, artifact_path, finished_at))
    append_jsonl(RUN_HISTORY_PATH, payload)
    return len(payload)


def build_payload(args: argparse.Namespace, queue_path: Path) -> dict[str, Any]:
    run_dir = WEEKEND_DIR / f"replay_runs_{args.date}"
    selected = selected_queue_rows(queue_path, args.start_index, args.batch_size)
    rows = [normalize_result(index, row, run_dir, args.rerun) for index, row in selected]
    finished_at = now_utc()
    json_path, _ = representative_paths(args.date)
    appended = append_history(rows, json_path, finished_at, args.force_append) if args.append_run_history else 0
    counts = dict(sorted(Counter(str(row.get("decision") or "UNKNOWN") for row in rows).items()))
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": finished_at,
        "date": args.date,
        "status": "OK" if all(row.get("status") == "completed" for row in rows) else "PARTIAL",
        "production_impact": PRODUCTION_IMPACT,
        "source": {"queue": repo_path(queue_path), "runner": "scripts/run_capital_aware_replay.py"},
        "summary": {
            "start_index": args.start_index,
            "batch_size": args.batch_size,
            "selected_count": len(rows),
            "completed_count": sum(row.get("status") == "completed" for row in rows),
            "failed_count": sum(row.get("status") != "completed" for row in rows),
            "decision_counts": counts,
            "appended_run_history_count": appended,
        },
        "rows": rows,
        "errors": [row for row in rows if row.get("status") != "completed"],
    }


def pct(value: Any) -> str:
    try:
        return f"{float(value):.2%}"
    except (TypeError, ValueError):
        return "--"


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Weekend Representative Replay",
        "",
        f"- status: `{payload['status']}`",
        f"- selected_count: `{summary['selected_count']}`",
        f"- completed_count: `{summary['completed_count']}`",
        f"- appended_run_history_count: `{summary['appended_run_history_count']}`",
        f"- production_impact: `{payload['production_impact']}`",
        "",
        "| index | return delta | drawdown delta | turnover delta | concentration delta | decision |",
        "| ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row.get('index')} | {pct(row.get('return_delta'))} | {pct(row.get('drawdown_delta'))} | {pct(row.get('turnover_delta'))} | {pct(row.get('concentration_delta'))} | `{row.get('decision')}` |"
        )
    lines.extend(["", "No production ranking, model, or Clawd live push changes.", ""])
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    default_queue, _ = queue_paths(args.date)
    queue_path = resolve_path(args.queue) or default_queue
    payload = build_payload(args, queue_path)
    json_path, md_path = representative_paths(args.date)
    write_json(json_path, payload)
    write_text(md_path, render_markdown(payload))
    print(json.dumps({"status": payload["status"], "output": repo_path(json_path), "completed": payload["summary"]["completed_count"], "appended": payload["summary"]["appended_run_history_count"]}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
