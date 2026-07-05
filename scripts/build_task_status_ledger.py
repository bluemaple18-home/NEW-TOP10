#!/usr/bin/env python3
"""建立 docs/tasks 與研究證據的狀態 ledger。

這支腳本只整理狀態，不執行研究、不改 production ranking/model/publish。
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
TASKS_DIR = PROJECT_ROOT / "docs" / "tasks"
SCHEMA_VERSION = "top10-task-status-ledger.v1"

STATUS_ORDER = {
    "active_pending_replay": 0,
    "active_followup": 1,
    "evidence_ready": 2,
    "approved_or_closed": 3,
    "monitor_only": 4,
    "research_only_or_blocked": 5,
    "historical_or_archived": 6,
    "unknown": 7,
}

KEYWORD_ALIASES = {
    "AUTO-TRAINING": ["auto_training", "big_bull", "training_candidate", "regime_family"],
    "BORROW-SQUEEZE": ["borrow_squeeze"],
    "CAPITAL-REALISM": ["capital_realism", "capital_entry", "gross55", "sizing_policy"],
    "CHIP-FLOW": ["chip_flow", "chip_warning"],
    "DAILY-RECOMMENDATION-QUALITY": ["daily_recommendation_quality"],
    "EXIT-SIGNAL": ["exit_signal"],
    "GUARDED-TOP10-REPLAY": ["guarded_top10", "backtest_guarded"],
    "LIQUIDITY-REPLAY": ["liquidity_replay", "liquidity_quality"],
    "LONG-CANDIDATE-VALIDATION": ["long_candidate"],
    "MARKET-DEFENSE": ["market_defense"],
    "POST-DAILY-EXTERNAL-REVIEW": ["external_review"],
    "PRODUCTION-TACTICS": ["production_tactics", "trail10"],
    "RANKING-QUALITY": ["ranking_quality", "liquidity_quality", "daily_recommendation"],
    "RESEARCH-MAP": ["research_fog_map", "research_map"],
    "RESEARCH-MAP-V2": ["research_fog_map", "research_map"],
    "SHADOW-ROLLOUT": ["shadow_rollout", "candidate_trail10", "overlap_first"],
    "STRATEGY-COMPOSE": ["strategy_composition"],
    "WEEKEND-TRAINING": ["weekend_training", "weekend_frontier", "weekend_representative"],
}

EXPLICIT_EVIDENCE = {
    "BORROW-SQUEEZE-02": [
        "artifacts/model_experiments/borrow_squeeze_replay_2026-06-22.json",
        "artifacts/model_experiments/borrow_squeeze_replay_2026-06-22.md",
    ],
    "MARKET-DEFENSE-01": [
        "artifacts/model_experiments/market_defense_guard_replay_2026-06-29.json",
        "artifacts/model_experiments/market_defense_guard_replay_2026-06-29.md",
    ],
    "WEEKEND-TRAINING-21": [
        "artifacts/weekend_training/weekend_training_rollup_2026-06-29.md",
        "artifacts/weekend_training/weekend_training_rollup_2026-06-29.json",
    ],
}


@dataclass(frozen=True)
class TaskCard:
    path: Path
    task_date: str
    task_id: str
    title: str
    body: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build TOP10 task status ledger.")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--tasks-dir", default=TASKS_DIR, type=Path)
    parser.add_argument("--artifacts-dir", default=ARTIFACTS_DIR, type=Path)
    parser.add_argument("--output", default=None)
    parser.add_argument("--markdown-output", default=None)
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(path)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def canonical_task_id(rest: str) -> str:
    """從檔名主體取出派工卡代號，避免把描述文字誤算進 task_id。"""
    parts = rest.split("_")
    task_id = parts[0]
    if len(parts) > 1 and "BATCH" in task_id and re.fullmatch(r"\d+[A-Z]?", parts[1]):
        return f"{task_id}_{parts[1]}"
    return task_id


def parse_task(path: Path) -> TaskCard:
    body = read_text(path)
    name = path.name
    match = re.match(r"(?P<date>\d{4}-\d{2}-\d{2})_(?P<rest>.+)\.md$", name)
    if not match:
        raise ValueError(f"unexpected task filename: {name}")
    rest = match.group("rest")
    task_id = canonical_task_id(rest)
    heading = next((line.lstrip("# ").strip() for line in body.splitlines() if line.startswith("#")), task_id)
    return TaskCard(path=path, task_date=match.group("date"), task_id=task_id, title=heading, body=body)


def artifact_candidates(artifacts_dir: Path) -> list[Path]:
    if not artifacts_dir.exists():
        return []
    allowed_suffixes = {".json", ".md", ".jsonl", ".csv"}
    skip_parts = {"__pycache__", "run_outputs"}
    paths: list[Path] = []
    for path in artifacts_dir.rglob("*"):
        if not path.is_file() or path.suffix not in allowed_suffixes:
            continue
        if any(part in skip_parts for part in path.parts):
            continue
        paths.append(path)
    return paths


def family(task_id: str) -> str:
    parts = task_id.split("-")
    if len(parts) >= 2 and parts[1].isalpha():
        return "-".join(parts[:2])
    if len(parts) >= 2:
        return "-".join(parts[:2])
    return task_id


def evidence_for_task(task: TaskCard, artifacts: list[Path]) -> list[str]:
    explicit = [PROJECT_ROOT / path for path in EXPLICIT_EVIDENCE.get(task.task_id, [])]
    found = [repo_path(path) for path in explicit if path.exists()]
    if found:
        return [path for path in found if path]

    aliases = KEYWORD_ALIASES.get(family(task.task_id), [])
    if not aliases:
        return []
    result: list[str] = []
    for path in artifacts:
        text = repo_path(path) or ""
        normalized = text.lower().replace("-", "_")
        if any(alias in normalized for alias in aliases):
            result.append(text)
        if len(result) >= 8:
            break
    return result


def current_harness_run(artifacts_dir: Path, run_date: str) -> dict[str, Any]:
    run_id_path = artifacts_dir / "harness_status" / run_date / "latest_run_id.txt"
    if not run_id_path.exists():
        return {}
    run_id = run_id_path.read_text(encoding="utf-8").strip()
    rollup_path = artifacts_dir / "harness_status" / run_date / run_id / "rollup.json"
    event_path = artifacts_dir / "harness_status" / run_date / run_id / "events" / "research_worker.json"
    payload: dict[str, Any] = {"run_id": run_id, "rollup": repo_path(rollup_path)}
    if event_path.exists():
        event = json.loads(event_path.read_text(encoding="utf-8"))
        payload["research_worker_status"] = event.get("status")
        payload["research_worker_metrics"] = event.get("metrics") or {}
    return payload


def manager_snapshot(artifacts_dir: Path) -> dict[str, Any]:
    path = artifacts_dir / "autonomous_research" / "manager_summary.json"
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        "status": payload.get("status"),
        "topic_count": payload.get("topic_count"),
        "run_count": payload.get("run_count"),
        "next_action_count": payload.get("next_action_count"),
        "latest_run": payload.get("latest_run") or {},
        "status_counts": payload.get("status_counts") or {},
    }


def status_for_task(task: TaskCard, evidence: list[str], run_date: str) -> tuple[str, str, str | None]:
    body = task.body
    if task.task_id == "MARKET-DEFENSE-01":
        if evidence:
            return "evidence_ready", "大盤防守 replay artifact 已存在。", None
        return (
            "active_pending_replay",
            "最新 PM 問題卡，尚未產出 market_defense_guard_replay evidence。",
            "建立 market defense replay harness，先跑日線壓力/廣度/回撤版本。",
        )
    if evidence:
        return "evidence_ready", "已找到對應 evidence artifact。", None
    if "狀態：`APPROVED`" in body or "狀態：MAINLINE_SUMMARY_READY" in body:
        return "approved_or_closed", "卡片本身已有 review/closure 結論。", None
    if "ACTIVE_DAILY_MONITOR" in body:
        return "monitor_only", "已收斂為 daily shadow monitor，不是待跑 replay。", None
    if "RESEARCH_ONLY" in body or "BLOCKED" in body:
        return "research_only_or_blocked", "卡片標示為 research-only 或 blocked。", None
    if task.task_date < "2026-06-21":
        return "historical_or_archived", "早於最新主線窗口；需由 closure/rollup 重新拉回才算 active。", None
    return "unknown", "未找到直接 evidence，也不在明確 active 規則內。", "人工確認是否仍需排入 queue。"


def build_payload(tasks_dir: Path, artifacts_dir: Path, run_date: str) -> dict[str, Any]:
    tasks = [parse_task(path) for path in sorted(tasks_dir.glob("2026-06-*.md"))]
    artifacts = artifact_candidates(artifacts_dir)
    rows: list[dict[str, Any]] = []
    for task in tasks:
        evidence = evidence_for_task(task, artifacts)
        status, status_reason, next_action = status_for_task(task, evidence, run_date)
        rows.append(
            {
                "task_id": task.task_id,
                "task_date": task.task_date,
                "title": task.title,
                "path": repo_path(task.path),
                "status": status,
                "status_reason": status_reason,
                "evidence_artifacts": evidence,
                "next_action": next_action,
            }
        )
    rows.sort(key=lambda row: (STATUS_ORDER.get(str(row["status"]), 99), row["task_date"], row["task_id"]))
    status_counts: dict[str, int] = {}
    for row in rows:
        key = str(row["status"])
        status_counts[key] = status_counts.get(key, 0) + 1
    active_rows = [row for row in rows if row["status"] in {"active_pending_replay", "active_followup", "unknown"}]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_date": run_date,
        "status": "NEEDS_ACTION" if active_rows else "OK",
        "summary": {
            "task_count": len(rows),
            "status_counts": status_counts,
            "active_attention_count": len(active_rows),
            "evidence_ready_count": status_counts.get("evidence_ready", 0),
        },
        "manager_snapshot": manager_snapshot(artifacts_dir),
        "harness_snapshot": current_harness_run(artifacts_dir, run_date),
        "active_attention": active_rows,
        "tasks": rows,
        "contract": {
            "research_only": True,
            "does_not_execute_replay": True,
            "does_not_train_model": True,
            "does_not_change_production_ranking": True,
            "does_not_send_push": True,
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Task Status Ledger",
        "",
        f"- run_date: `{payload['run_date']}`",
        f"- status: `{payload['status']}`",
        f"- task_count: `{summary['task_count']}`",
        f"- active_attention_count: `{summary['active_attention_count']}`",
        "",
        "## Status Counts",
        "",
        "| status | count |",
        "|---|---:|",
    ]
    for status, count in sorted(summary["status_counts"].items(), key=lambda item: STATUS_ORDER.get(item[0], 99)):
        lines.append(f"| `{status}` | {count} |")
    lines.extend(["", "## Active Attention", "", "| task_id | status | next_action | evidence |", "|---|---|---|---|"])
    for row in payload["active_attention"]:
        evidence = "<br>".join(f"`{path}`" for path in row["evidence_artifacts"]) or "-"
        next_action = row["next_action"] or row["status_reason"]
        lines.append(f"| `{row['task_id']}` | `{row['status']}` | {next_action} | {evidence} |")
    lines.extend(["", "## Recent Evidence Rows", "", "| task_id | status | evidence |", "|---|---|---|"])
    evidence_rows = [row for row in payload["tasks"] if row["evidence_artifacts"]][:20]
    for row in evidence_rows:
        evidence = "<br>".join(f"`{path}`" for path in row["evidence_artifacts"][:3])
        lines.append(f"| `{row['task_id']}` | `{row['status']}` | {evidence} |")
    lines.extend(
        [
            "",
            "## Contract",
            "",
            "- research_only: `true`",
            "- does_not_execute_replay: `true`",
            "- does_not_change_production_ranking: `true`",
            "- does_not_send_push: `true`",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    tasks_dir = resolve_path(args.tasks_dir)
    artifacts_dir = resolve_path(args.artifacts_dir)
    payload = build_payload(tasks_dir, artifacts_dir, args.date)
    output = resolve_path(args.output) if args.output else artifacts_dir / "task_status" / f"task_status_ledger_{args.date}.json"
    markdown_output = (
        resolve_path(args.markdown_output)
        if args.markdown_output
        else artifacts_dir / "task_status" / f"task_status_ledger_{args.date}.md"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.write_text(render_markdown(payload), encoding="utf-8")
    latest_json = output.parent / "task_status_ledger_latest.json"
    latest_md = output.parent / "task_status_ledger_latest.md"
    latest_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    latest_md.write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "output": repo_path(output),
                "markdown_output": repo_path(markdown_output),
                "active_attention_count": payload["summary"]["active_attention_count"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
