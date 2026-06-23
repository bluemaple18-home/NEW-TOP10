#!/usr/bin/env python3
"""彙整 weekend survivor deep replay 檢查。

目前只使用已存在的 representative / stage2 replay 證據做保守 gate；
缺長窗 artifact 時標成 MONITOR_ONLY，不宣稱 promotion。
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from weekend_training_common import (
    PRODUCTION_IMPACT,
    RUN_HISTORY_PATH,
    latest_stage2_path,
    latest_by_combo,
    now_utc,
    read_jsonl,
    representative_paths,
    repo_path,
    resolve_path,
    survivor_paths,
    write_json,
    write_text,
)


SCHEMA_VERSION = "weekend-survivor-deep-replay.v1"
SURVIVOR_SOURCES = {"weekend_representative_replay", "liquidity_replay_v2_stage2"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="run weekend survivor deep replay")
    parser.add_argument("--date", required=True)
    parser.add_argument("--representative", default=None)
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


def source_survivors(date: str, representative_path: Path) -> list[dict[str, Any]]:
    latest_records = latest_by_combo(read_jsonl(RUN_HISTORY_PATH))
    rows = []
    for record in latest_records.values():
        source = str(record.get("source") or "")
        if source not in SURVIVOR_SOURCES:
            continue
        decision = str(record.get("decision") or "")
        insight = str(record.get("insight_level") or "")
        if insight == "next_stage" or decision in {"NEXT_STAGE_CANDIDATE", "CONFIRMED_FOR_NEXT_REPLAY"}:
            rows.append({**record, "source_stage": source})
    if rows:
        return sorted(rows, key=lambda row: str(row.get("combo_id") or ""))

    representative = read_json(representative_path)
    rows = [
        {**row, "source_stage": "weekend_representative_replay"}
        for row in representative.get("rows", [])
        if isinstance(row, dict) and row.get("decision") == "NEXT_STAGE_CANDIDATE"
    ]
    if rows:
        return rows
    stage2 = read_json(latest_stage2_path(date))
    return [
        {**row, "source_stage": "liquidity_replay_v2_stage2"}
        for row in stage2.get("stage2_candidates", [])
        if isinstance(row, dict)
    ]


def check_row(row: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "recent_100": "SOURCE_METRIC_ONLY",
        "recent_6m": "SOURCE_METRIC_ONLY",
        "available_long_window": "NOT_AVAILABLE",
        "BIG_BULL_slice": "NOT_AVAILABLE",
        "HIGH_CHOPPY_CONTEXT_slice": "NOT_AVAILABLE",
        "RISK_OFF_PANIC_slice": "NOT_AVAILABLE",
        "same_exit_ranking_isolation": "NOT_AVAILABLE",
    }
    failure_reasons: list[str] = []
    if safe_float(row.get("return_delta")) < 0.02:
        failure_reasons.append("RETURN_DELTA_BELOW_DEEP_MIN")
    if safe_float(row.get("drawdown_delta")) < -0.005:
        failure_reasons.append("DRAWDOWN_WORSE_THAN_DEEP_LIMIT")
    if safe_float(row.get("concentration_delta")) > 0.03:
        failure_reasons.append("CONCENTRATION_WORSE_THAN_DEEP_LIMIT")
    if checks["available_long_window"] == "NOT_AVAILABLE":
        failure_reasons.append("LONG_WINDOW_REPLAY_NOT_EXECUTED")
    decision = "MONITOR_ONLY" if failure_reasons else "KEEP_FOR_NEXT_RESEARCH"
    if "LONG_WINDOW_REPLAY_NOT_EXECUTED" in failure_reasons:
        decision = "MONITOR_ONLY"
    return {
        "combo_id": row.get("combo_id"),
        "topic_id": row.get("topic_id"),
        "dimensions": row.get("dimensions"),
        "source_stage": row.get("source_stage"),
        "return_delta": row.get("return_delta"),
        "drawdown_delta": row.get("drawdown_delta"),
        "turnover_delta": row.get("turnover_delta"),
        "concentration_delta": row.get("concentration_delta"),
        "checks": checks,
        "decision": decision,
        "failure_reasons": failure_reasons,
        "production_impact": PRODUCTION_IMPACT,
    }


def build_payload(date: str, representative_path: Path) -> dict[str, Any]:
    rows = [check_row(row) for row in source_survivors(date, representative_path)]
    counts = dict(sorted(Counter(str(row["decision"]) for row in rows).items()))
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now_utc(),
        "date": date,
        "status": "OK",
        "production_impact": PRODUCTION_IMPACT,
        "source": {
            "representative_replay": repo_path(representative_path),
            "stage2": repo_path(latest_stage2_path(date)),
            "run_history": repo_path(RUN_HISTORY_PATH),
        },
        "summary": {
            "source_survivor_count": len(rows),
            "keep_for_next_research_count": counts.get("KEEP_FOR_NEXT_RESEARCH", 0),
            "monitor_only_count": counts.get("MONITOR_ONLY", 0),
            "reject_count": counts.get("REJECT", 0),
            "decision_counts": counts,
        },
        "rows": rows,
    }


def pct(value: Any) -> str:
    try:
        return f"{float(value):.2%}"
    except (TypeError, ValueError):
        return "--"


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Weekend Survivor Deep Replay",
        "",
        f"- status: `{payload['status']}`",
        f"- source_survivor_count: `{summary['source_survivor_count']}`",
        f"- keep_for_next_research_count: `{summary['keep_for_next_research_count']}`",
        f"- monitor_only_count: `{summary['monitor_only_count']}`",
        f"- production_impact: `{payload['production_impact']}`",
        "",
        "| combo | return delta | drawdown delta | decision | failure reasons |",
        "| --- | ---: | ---: | --- | --- |",
    ]
    for row in payload["rows"][:50]:
        lines.append(
            f"| `{row.get('combo_id')}` | {pct(row.get('return_delta'))} | {pct(row.get('drawdown_delta'))} | `{row.get('decision')}` | `{', '.join(row.get('failure_reasons') or [])}` |"
        )
    lines.extend(["", "No production ranking, model, or Clawd live push changes.", ""])
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    default_representative, _ = representative_paths(args.date)
    representative_path = resolve_path(args.representative) or default_representative
    payload = build_payload(args.date, representative_path)
    json_path, md_path = survivor_paths(args.date)
    write_json(json_path, payload)
    write_text(md_path, render_markdown(payload))
    print(json.dumps({"status": payload["status"], "output": repo_path(json_path), "survivors": payload["summary"]["source_survivor_count"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
