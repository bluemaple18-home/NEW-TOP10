#!/usr/bin/env python3
"""彙整 liquidity replay v2 batch，產生風險封頂後的二階候選。

這支腳本只讀研究 artifact，不改 production ranking / model / publish。
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = PROJECT_ROOT / "artifacts" / "research_reviews"
RUN_HISTORY_PATH = PROJECT_ROOT / "artifacts" / "autonomous_research" / "run_history.jsonl"
SCHEMA_VERSION = "liquidity-replay-v2-stage2.v1"
SOURCE_SCHEMA = "liquidity-replay-v2-batch.v1"
PRODUCTION_IMPACT = "NO_PRODUCTION_CHANGE"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build liquidity replay v2 stage2 candidates")
    parser.add_argument("--date", required=True)
    parser.add_argument("--input", default=None)
    parser.add_argument("--output-dir", default=str(INPUT_DIR))
    parser.add_argument("--append-run-history", action="store_true")
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
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def failure_reasons(row: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if safe_float(row.get("return_delta")) < 0.02:
        reasons.append("RETURN_DELTA_BELOW_STAGE2_MIN")
    if safe_float(row.get("drawdown_delta")) < -0.005:
        reasons.append("DRAWDOWN_WORSE_THAN_STAGE2_LIMIT")
    if safe_float(row.get("concentration_delta")) > 0.03:
        reasons.append("CONCENTRATION_WORSE_THAN_STAGE2_LIMIT")
    if safe_float(row.get("turnover_delta")) > 0.05:
        reasons.append("TURNOVER_WORSE_THAN_STAGE2_LIMIT")
    if row.get("decision") != "KEEP_FOR_COMPONENT_FOLLOWUP":
        reasons.append("SOURCE_BATCH_REJECTED")
    return reasons


def stage2_decision(row: dict[str, Any]) -> tuple[str, list[str]]:
    reasons = failure_reasons(row)
    if not reasons:
        return "STAGE2_RISK_CAPPED_CANDIDATE", []
    if row.get("decision") == "KEEP_FOR_COMPONENT_FOLLOWUP" and safe_float(row.get("return_delta")) > 0:
        return "SHADOW_MONITOR_ONLY", reasons
    return "REJECT_FOR_NOW", reasons


def score(row: dict[str, Any]) -> float:
    return round(
        safe_float(row.get("return_delta"))
        + min(0.03, max(-0.05, safe_float(row.get("drawdown_delta"))))
        - max(0.0, safe_float(row.get("concentration_delta")) - 0.03)
        - max(0.0, safe_float(row.get("turnover_delta")) - 0.05),
        6,
    )


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    decision, reasons = stage2_decision(row)
    return {
        "index": row.get("index"),
        "combo_id": row.get("combo_id"),
        "topic_id": row.get("topic_id"),
        "dimensions": row.get("dimensions") if isinstance(row.get("dimensions"), dict) else {},
        "source_decision": row.get("decision"),
        "stage2_decision": decision,
        "failure_reasons": reasons,
        "score": score(row),
        "return_delta": row.get("return_delta"),
        "drawdown_delta": row.get("drawdown_delta"),
        "turnover_delta": row.get("turnover_delta"),
        "concentration_delta": row.get("concentration_delta"),
        "baseline_artifact": ((row.get("baseline") or {}).get("artifact") if isinstance(row.get("baseline"), dict) else None),
        "candidate_artifact": ((row.get("candidate") or {}).get("artifact") if isinstance(row.get("candidate"), dict) else None),
    }


def dimension_summary(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    counter = Counter(str((row.get("dimensions") or {}).get(key)) for row in rows)
    return [{"value": value, "count": count} for value, count in counter.most_common()]


def build_payload(date: str, source_path: Path) -> dict[str, Any]:
    source = read_json(source_path)
    rows = source.get("rows") if isinstance(source.get("rows"), list) else []
    normalized = [normalize_row(row) for row in rows if isinstance(row, dict)]
    candidates = [row for row in normalized if row["stage2_decision"] == "STAGE2_RISK_CAPPED_CANDIDATE"]
    shadow = [row for row in normalized if row["stage2_decision"] == "SHADOW_MONITOR_ONLY"]
    rejected = [row for row in normalized if row["stage2_decision"] == "REJECT_FOR_NOW"]
    candidates = sorted(candidates, key=lambda row: (safe_float(row["score"]), safe_float(row["return_delta"])), reverse=True)
    shadow = sorted(shadow, key=lambda row: (safe_float(row["return_delta"]), safe_float(row["score"])), reverse=True)
    rejected = sorted(rejected, key=lambda row: safe_float(row["score"]), reverse=True)
    failure_counts = Counter(reason for row in normalized for reason in row["failure_reasons"])
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK",
        "review_date": date,
        "production_impact": PRODUCTION_IMPACT,
        "source": {
            "artifact": repo_path(source_path),
            "schema_version": source.get("schema_version"),
            "summary": source.get("summary") if isinstance(source.get("summary"), dict) else {},
        },
        "stage2_gate": {
            "return_delta_min": 0.02,
            "drawdown_delta_min": -0.005,
            "concentration_delta_max": 0.03,
            "turnover_delta_max": 0.05,
        },
        "summary": {
            "source_rows": len(rows),
            "source_effective_count": sum(row.get("decision") == "KEEP_FOR_COMPONENT_FOLLOWUP" for row in rows),
            "stage2_candidate_count": len(candidates),
            "shadow_monitor_count": len(shadow),
            "rejected_count": len(rejected),
            "failure_counts": dict(failure_counts),
            "candidate_entry_filter": dimension_summary(candidates, "entry_filter"),
            "candidate_regime_gate": dimension_summary(candidates, "regime_gate"),
            "candidate_risk_guard": dimension_summary(candidates, "risk_guard"),
            "candidate_group_exposure": dimension_summary(candidates, "group_exposure"),
        },
        "stage2_candidates": candidates,
        "shadow_monitor_only": shadow,
        "rejected": rejected,
        "next_action": "RUN_LONG_WINDOW_REPLAY_FOR_STAGE2_CANDIDATES",
    }


def pct(value: Any) -> str:
    try:
        return f"{float(value):.2%}"
    except (TypeError, ValueError):
        return "--"


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Liquidity Replay V2 Stage2",
        "",
        f"- status: `{payload['status']}`",
        f"- source_rows: `{summary['source_rows']}`",
        f"- source_effective_count: `{summary['source_effective_count']}`",
        f"- stage2_candidate_count: `{summary['stage2_candidate_count']}`",
        f"- shadow_monitor_count: `{summary['shadow_monitor_count']}`",
        f"- rejected_count: `{summary['rejected_count']}`",
        f"- production_impact: `{payload['production_impact']}`",
        "",
        "## Stage2 Candidates",
        "",
        "| index | entry_filter | regime_gate | risk_guard | group | return delta | drawdown delta | concentration delta | score |",
        "| ---: | --- | --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["stage2_candidates"][:30]:
        dim = row["dimensions"]
        lines.append(
            f"| {row['index']} | {dim.get('entry_filter')} | {dim.get('regime_gate')} | {dim.get('risk_guard')} | {dim.get('group_exposure')} | {pct(row.get('return_delta'))} | {pct(row.get('drawdown_delta'))} | {pct(row.get('concentration_delta'))} | {row.get('score')} |"
        )
    lines.extend(
        [
            "",
            "## Failure Attribution",
            "",
        ]
    )
    for reason, count in sorted(summary["failure_counts"].items(), key=lambda item: item[1], reverse=True):
        lines.append(f"- `{reason}`: `{count}`")
    lines.extend(["", "## Production Impact", "", f"`{payload['production_impact']}`", ""])
    return "\n".join(lines)


def run_history_rows(payload: dict[str, Any], artifact_path: Path) -> list[dict[str, Any]]:
    finished_at = str(payload.get("generated_at") or datetime.now(timezone.utc).isoformat())
    rows: list[dict[str, Any]] = []
    for row in [*payload.get("stage2_candidates", []), *payload.get("shadow_monitor_only", []), *payload.get("rejected", [])]:
        stage2_decision = str(row.get("stage2_decision") or "")
        if stage2_decision == "STAGE2_RISK_CAPPED_CANDIDATE":
            insight = "next_stage"
            decision = "CONFIRMED_FOR_NEXT_REPLAY"
        elif stage2_decision == "SHADOW_MONITOR_ONLY":
            insight = "risk_worse_return_positive"
            decision = "MONITOR_ONLY"
        else:
            insight = "rejected"
            decision = "REJECT_FOR_NOW"
        rows.append(
            {
                "schema_version": "research-map-run-history.v2",
                "map_version": "v2",
                "source": "liquidity_replay_v2_stage2",
                "status": "completed",
                "combo_id": row.get("combo_id"),
                "dimensions": row.get("dimensions"),
                "decision": decision,
                "stage2_decision": stage2_decision,
                "insight_level": insight,
                "return_delta": row.get("return_delta"),
                "drawdown_delta": row.get("drawdown_delta"),
                "turnover_delta": row.get("turnover_delta"),
                "concentration_delta": row.get("concentration_delta"),
                "score_delta": row.get("score"),
                "artifact_path": repo_path(artifact_path),
                "finished_at": finished_at,
            }
        )
    return rows


def main() -> int:
    args = parse_args()
    source_path = resolve_path(args.input) or INPUT_DIR / f"liquidity_replay_v2_batch_{args.date}.json"
    output_dir = resolve_path(args.output_dir) or INPUT_DIR
    payload = build_payload(args.date, source_path)
    json_path = output_dir / f"liquidity_replay_v2_stage2_{args.date}.json"
    md_path = output_dir / f"liquidity_replay_v2_stage2_{args.date}.md"
    write_json(json_path, payload)
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    appended = 0
    if args.append_run_history:
        rows = run_history_rows(payload, json_path)
        existing = {
            (str(row.get("source") or ""), str(row.get("combo_id") or ""))
            for row in read_jsonl(RUN_HISTORY_PATH)
        }
        rows = [row for row in rows if (str(row.get("source") or ""), str(row.get("combo_id") or "")) not in existing]
        append_jsonl(RUN_HISTORY_PATH, rows)
        appended = len(rows)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "output": repo_path(json_path),
                "stage2_candidates": payload["summary"]["stage2_candidate_count"],
                "shadow_monitor": payload["summary"]["shadow_monitor_count"],
                "rejected": payload["summary"]["rejected_count"],
                "appended_run_history": appended,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
