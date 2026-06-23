#!/usr/bin/env python3
"""執行 research map v2 liquidity replay component batch。

只讀 active_expansion_queue 與既有 ranking/features，輸出研究 artifact；
不改 production ranking、不訓練模型、不寫推播。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FOG_MAP_PATH = PROJECT_ROOT / "artifacts" / "research_map" / "research_fog_map_latest.json"
RUN_HISTORY_PATH = PROJECT_ROOT / "artifacts" / "autonomous_research" / "run_history.jsonl"
OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "research_reviews"
SCHEMA_VERSION = "liquidity-replay-v2-batch.v1"
PRODUCTION_IMPACT = "NO_PRODUCTION_CHANGE"
STAGE = "LIQUIDITY-REPLAY-02"
REQUIRED_DIMENSIONS = {"horizon", "stop_loss", "take_profit", "group_exposure", "regime_gate", "risk_guard", "entry_filter"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="run liquidity replay v2 batch")
    parser.add_argument("--date", required=True)
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--append-run-history", action="store_true")
    parser.add_argument("--rerun", action="store_true")
    parser.add_argument("--force-append", action="store_true")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
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


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")


def active_queue() -> list[dict[str, Any]]:
    payload = read_json(FOG_MAP_PATH)
    queue = payload.get("active_expansion_queue") if isinstance(payload.get("active_expansion_queue"), list) else []
    return [item for item in queue if isinstance(item, dict) and item.get("stage") == STAGE]


def selected_queue(queue: list[dict[str, Any]], start_index: int, limit: int) -> list[tuple[int, dict[str, Any]]]:
    end = start_index + max(0, limit)
    return list(enumerate(queue[start_index:end], start=start_index))


def safe_slug(value: str, max_len: int = 180) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in value)
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_")[:max_len] or "scenario"


def scenario_output_path(run_dir: Path, index: int, row: dict[str, Any], role: str) -> Path:
    combo_id = str(row.get("combo_id") or "combo")
    digest = hashlib.sha1(combo_id.encode("utf-8")).hexdigest()[:12]
    return run_dir / f"{index:03d}_{safe_slug(combo_id, max_len=120)}_{digest}_{role}.json"


def sibling_rankings_dir(candidate_dir: str, entry_filter: str, role: str) -> str:
    if role == "baseline":
        override = os.environ.get("TOP10_BASELINE_RANKINGS_DIR")
        if override:
            return override
    path = Path(candidate_dir)
    parent = path.parent
    if role == "baseline":
        return str(parent / "production")
    if entry_filter == "TOPIC_DEFAULT":
        return str(path)
    if entry_filter == "PERCENTILE_GATE":
        if path.name == "percentile_gate":
            return str(path)
        if (PROJECT_ROOT / path / "percentile_gate").exists():
            return str(path / "percentile_gate")
        return str(parent / "percentile_gate")
    if path.name == "log_gate":
        return str(path)
    if (PROJECT_ROOT / path / "log_gate").exists():
        return str(path / "log_gate")
    if any((PROJECT_ROOT / path).glob("ranking_*.csv")):
        return str(path)
    return str(parent / "log_gate")


def entry_filter_value(entry_filter: str) -> str:
    if entry_filter == "LOG_GATE_NON_WORSENING":
        return "non_worsening"
    return "all"


def max_group_pct(value: str) -> float:
    return 0.30 if value in {"", "none", "None", "null"} else float(value)


def gross_values(regime_gate: str, risk_guard: str) -> dict[str, float]:
    values = {
        "big_bull": 0.65,
        "risk_on": 0.65,
        "high_choppy": 0.65,
        "neutral": 0.65,
        "risk_off": 0.65,
    }
    if regime_gate == "BIG_BULL_ONLY":
        values.update({"risk_on": 0.0, "high_choppy": 0.0, "neutral": 0.0, "risk_off": 0.0})
    elif regime_gate == "BIG_BULL_HIGH_CHOPPY":
        values.update({"risk_on": 0.0, "neutral": 0.0, "risk_off": 0.0})
    elif regime_gate == "EXCLUDE_RISK_OFF_PANIC":
        values["risk_off"] = 0.0

    if risk_guard == "RISK_OFF_CASH_RAISE":
        values["risk_off"] = min(values["risk_off"], 0.30)
    elif risk_guard in {"RISK_OFF_DISABLE", "PANIC_DISABLE"}:
        values["risk_off"] = 0.0
    return values


def build_command(row: dict[str, Any], role: str, output_path: Path) -> list[str]:
    dimensions = row.get("dimensions") if isinstance(row.get("dimensions"), dict) else {}
    entry_filter = str(dimensions.get("entry_filter") or "LOG_GATE")
    gross = gross_values(str(dimensions.get("regime_gate") or "ALL"), str(dimensions.get("risk_guard") or "NONE"))
    command = [
        ".venv/bin/python",
        "scripts/run_capital_aware_replay.py",
        "--rankings-dir",
        sibling_rankings_dir(str(row.get("candidate_dir") or ""), entry_filter, role),
        "--scenario",
        "tp15_partial_runner",
        "--gross-policy",
        "regime",
        "--horizon",
        str(dimensions.get("horizon") or "3"),
        "--entry-filter",
        "all" if role == "baseline" else entry_filter_value(entry_filter),
        "--max-group-pct",
        str(max_group_pct(str(dimensions.get("group_exposure") or "none"))),
        "--big-bull-gross",
        str(gross["big_bull"]),
        "--risk-on-gross",
        str(gross["risk_on"]),
        "--high-choppy-gross",
        str(gross["high_choppy"]),
        "--neutral-gross",
        str(gross["neutral"]),
        "--risk-off-gross",
        str(gross["risk_off"]),
        "--output",
        str(output_path),
    ]
    take_profit = str(dimensions.get("take_profit") or "none")
    if take_profit not in {"none", "None", "null", ""}:
        command.extend(["--tp-pct", take_profit, "--min-holding-days", "1"])
    stop_loss = str(dimensions.get("stop_loss") or "none")
    if stop_loss not in {"none", "None", "null", ""}:
        command.extend(["--stop-loss-source", "pct", "--stop-loss-pct", stop_loss])
    return command


def portable_args(command_args: list[str]) -> list[str]:
    portable: list[str] = []
    for item in command_args:
        path = Path(item)
        if path.is_absolute():
            portable.append(repo_path(path) or item)
        else:
            portable.append(item)
    return portable


def run_or_load(command: list[str], output_path: Path, *, rerun: bool) -> tuple[dict[str, Any], str]:
    if output_path.exists() and not rerun:
        return read_json(output_path), "reused"
    result = subprocess.run(command, cwd=PROJECT_ROOT, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        return {
            "status": "FAILED",
            "returncode": result.returncode,
            "stdout": result.stdout[-2000:],
            "stderr": result.stderr[-2000:],
        }, "failed"
    return read_json(output_path), "ran"


def max_group_exposure(run: dict[str, Any]) -> float:
    values: list[float] = []
    for row in run.get("daily", []):
        exposures = row.get("group_exposures") if isinstance(row, dict) else {}
        if isinstance(exposures, dict) and exposures:
            values.append(max(float(value or 0) for value in exposures.values()))
    return round(max(values), 6) if values else 0.0


def turnover_events_per_day(run: dict[str, Any]) -> float:
    daily = run.get("daily") if isinstance(run.get("daily"), list) else []
    if not daily:
        return 0.0
    events = sum(int(row.get("entries") or 0) + int(row.get("exits") or 0) + int(row.get("partial_exits") or 0) for row in daily if isinstance(row, dict))
    return round(events / len(daily), 6)


def summary(run: dict[str, Any], artifact: Path) -> dict[str, Any]:
    data = run.get("summary") if isinstance(run.get("summary"), dict) else {}
    return {
        "artifact": repo_path(artifact),
        "total_return": data.get("total_return"),
        "max_drawdown": data.get("max_drawdown"),
        "win_rate": data.get("win_rate"),
        "trade_count": data.get("trade_count"),
        "daily_count": data.get("daily_count"),
        "turnover_events_per_day": turnover_events_per_day(run),
        "max_group_exposure": max_group_exposure(run),
        "avg_gross_exposure": data.get("avg_gross_exposure"),
        "max_gross_exposure": data.get("max_gross_exposure"),
        "skip_reason_counts": data.get("skip_reason_counts") or {},
    }


def f(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def classify(return_delta: float, drawdown_delta: float, turnover_delta: float, concentration_delta: float) -> tuple[str, str]:
    if return_delta > 0 and drawdown_delta >= -0.005 and turnover_delta <= 0.05 and concentration_delta <= 0.05:
        return "KEEP_FOR_COMPONENT_FOLLOWUP", "effective"
    if return_delta > 0 and drawdown_delta >= -0.02:
        return "KEEP_FOR_COMPONENT_FOLLOWUP", "effective"
    return "REJECT_FOR_NOW", "rejected"


def process_row(index: int, row: dict[str, Any], run_dir: Path, rerun: bool) -> dict[str, Any]:
    baseline_path = scenario_output_path(run_dir, index, row, "baseline")
    candidate_path = scenario_output_path(run_dir, index, row, "candidate")
    baseline_command = build_command(row, "baseline", baseline_path)
    candidate_command = build_command(row, "candidate", candidate_path)
    baseline_payload, baseline_status = run_or_load(baseline_command, baseline_path, rerun=rerun)
    candidate_payload, candidate_status = run_or_load(candidate_command, candidate_path, rerun=rerun)
    if baseline_payload.get("status") == "FAILED" or candidate_payload.get("status") == "FAILED":
        return {
            "index": index,
            "combo_id": row.get("combo_id"),
            "topic_id": row.get("topic_id"),
            "dimensions": row.get("dimensions"),
            "status": "failed",
            "production_impact": PRODUCTION_IMPACT,
            "baseline_status": baseline_status,
            "candidate_status": candidate_status,
            "errors": {"baseline": baseline_payload if baseline_payload.get("status") == "FAILED" else {}, "candidate": candidate_payload if candidate_payload.get("status") == "FAILED" else {}},
        }
    baseline = summary(baseline_payload, baseline_path)
    candidate = summary(candidate_payload, candidate_path)
    return_delta = round(f(candidate.get("total_return")) - f(baseline.get("total_return")), 6)
    drawdown_delta = round(f(candidate.get("max_drawdown")) - f(baseline.get("max_drawdown")), 6)
    turnover_delta = round(f(candidate.get("turnover_events_per_day")) - f(baseline.get("turnover_events_per_day")), 6)
    concentration_delta = round(f(candidate.get("max_group_exposure")) - f(baseline.get("max_group_exposure")), 6)
    decision, insight_level = classify(return_delta, drawdown_delta, turnover_delta, concentration_delta)
    return {
        "index": index,
        "combo_id": row.get("combo_id"),
        "topic_id": row.get("topic_id"),
        "dimensions": row.get("dimensions"),
        "status": "completed",
        "decision": decision,
        "insight_level": insight_level,
        "production_impact": PRODUCTION_IMPACT,
        "baseline": baseline,
        "candidate": candidate,
        "return_delta": return_delta,
        "drawdown_delta": drawdown_delta,
        "turnover_delta": turnover_delta,
        "concentration_delta": concentration_delta,
        "baseline_status": baseline_status,
        "candidate_status": candidate_status,
        "invocation": {
            "runner": "scripts/run_capital_aware_replay.py",
            "baseline_args": portable_args(baseline_command[2:]),
            "candidate_args": portable_args(candidate_command[2:]),
        },
    }


def run_history_row(row: dict[str, Any], artifact_path: str, finished_at: str) -> dict[str, Any]:
    return {
        "schema_version": "research-map-run-history.v2",
        "map_version": "v2",
        "source": "liquidity_replay_v2_batch",
        "status": row.get("status"),
        "combo_id": row.get("combo_id"),
        "dimensions": row.get("dimensions"),
        "decision": row.get("decision"),
        "insight_level": row.get("insight_level"),
        "return_delta": row.get("return_delta"),
        "drawdown_delta": row.get("drawdown_delta"),
        "turnover_delta": row.get("turnover_delta"),
        "concentration_delta": row.get("concentration_delta"),
        "artifact_path": artifact_path,
        "finished_at": finished_at,
    }


def append_missing_history(rows: list[dict[str, Any]], artifact_path: str, finished_at: str, force_append: bool) -> int:
    existing = read_jsonl(RUN_HISTORY_PATH)
    existing_keys = {str(row.get("combo_id")) for row in existing if row.get("source") == "liquidity_replay_v2_batch"}
    payload = []
    for row in rows:
        if row.get("status") != "completed":
            continue
        combo_id = str(row.get("combo_id") or "")
        if not force_append and combo_id in existing_keys:
            continue
        payload.append(run_history_row(row, artifact_path, finished_at))
    append_jsonl(RUN_HISTORY_PATH, payload)
    return len(payload)


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    queue = active_queue()
    output_dir = resolve_path(args.output_dir)
    run_dir = output_dir / f"liquidity_replay_v2_batch_{args.date}"
    rows = [process_row(index, row, run_dir, args.rerun) for index, row in selected_queue(queue, args.start_index, args.limit)]
    counts = Counter(str(row.get("insight_level") or "blocked") for row in rows)
    finished_at = datetime.now(timezone.utc).isoformat()
    artifact_path = f"artifacts/research_reviews/liquidity_replay_v2_batch_{args.date}.json"
    appended_count = append_missing_history(rows, artifact_path, finished_at, args.force_append) if args.append_run_history else 0
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": finished_at,
        "status": "OK" if all(row.get("status") == "completed" for row in rows) else "PARTIAL",
        "review_date": args.date,
        "production_impact": PRODUCTION_IMPACT,
        "source": {
            "research_map": repo_path(FOG_MAP_PATH),
            "active_stage": STAGE,
            "run_history": repo_path(RUN_HISTORY_PATH),
            "source_queue": "active_expansion_queue",
        },
        "summary": {
            "active_queue_count": len(queue),
            "start_index": args.start_index,
            "limit": args.limit,
            "selected_count": len(rows),
            "completed_count": sum(row.get("status") == "completed" for row in rows),
            "failed_count": sum(row.get("status") == "failed" for row in rows),
            "effective_count": counts.get("effective", 0),
            "rejected_count": counts.get("rejected", 0),
            "appended_run_history_count": appended_count,
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
    lines = [
        "# Liquidity Replay V2 Batch",
        "",
        f"- status: `{payload['status']}`",
        f"- active_queue_count: `{payload['summary']['active_queue_count']}`",
        f"- selected_count: `{payload['summary']['selected_count']}`",
        f"- completed_count: `{payload['summary']['completed_count']}`",
        f"- effective_count: `{payload['summary']['effective_count']}`",
        f"- rejected_count: `{payload['summary']['rejected_count']}`",
        f"- production_impact: `{payload['production_impact']}`",
        "",
        "| index | entry_filter | regime_gate | risk_guard | group | return delta | drawdown delta | decision |",
        "| ---: | --- | --- | --- | --- | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        dim = row.get("dimensions") or {}
        lines.append(
            f"| {row.get('index')} | {dim.get('entry_filter')} | {dim.get('regime_gate')} | {dim.get('risk_guard')} | {dim.get('group_exposure')} | {pct(row.get('return_delta'))} | {pct(row.get('drawdown_delta'))} | `{row.get('decision')}` |"
        )
    lines.extend(["", "## Production Impact", "", f"`{payload['production_impact']}`", "", "No production ranking, model, risk_adjusted_score, or Clawd live push changes.", ""])
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    output_dir = resolve_path(args.output_dir)
    payload = build_payload(args)
    json_path = output_dir / f"liquidity_replay_v2_batch_{args.date}.json"
    md_path = output_dir / f"liquidity_replay_v2_batch_{args.date}.md"
    write_json(json_path, payload)
    write_text(md_path, render_markdown(payload))
    print(json.dumps({"status": payload["status"], "output": repo_path(json_path), "completed": payload["summary"]["completed_count"], "appended": payload["summary"]["appended_run_history_count"]}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
