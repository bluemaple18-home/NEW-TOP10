#!/usr/bin/env python3
"""自動研究發題與安全回測 runner。

此腳本負責做三件事：
1. 從既有 artifacts / ledger / external review 產生研究題目。
2. 選出可用既有 ranking artifacts 回測的題目。
3. 在 --execute 時只呼叫白名單回測腳本，不訓練模型、不改正式 ranking。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
OUTPUT_DIR = ARTIFACTS_DIR / "autonomous_research"
LEDGER_PATH = ARTIFACTS_DIR / "model_experiments" / "model_experiment_ledger.json"
SCHEMA_VERSION = "autonomous-research-run.v1"
MANAGER_SCHEMA_VERSION = "autonomous-research-manager.v1"
RUNNER_REGISTRY_SCHEMA_VERSION = "autonomous-research-runner-registry.v1"
ALLOWED_RUNNERS = {
    "scripts/run_backtest_strategy_matrix.py",
    "scripts/compare_strategy_matrices.py",
}
RUNNER_SPECS = {
    "strategy_matrix_comparison": {
        "runner": "strategy_matrix_comparison",
        "allowed_scripts": sorted(ALLOWED_RUNNERS),
        "step_count": 3,
        "does_not_fetch_data": True,
        "does_not_train_model": True,
        "does_not_change_production_ranking": True,
        "production_promotion_allowed": False,
        "output_decisions": [
            "CONFIRMED_FOR_NEXT_REPLAY",
            "PARTIAL_SCORE_ONLY",
            "REJECTED_BY_STRATEGY_MATRIX",
            "NO_COMPARISON_EVIDENCE",
        ],
    }
}
BASELINE_RANKINGS_DIR = "artifacts/backtest/historical_rankings_current_model"


@dataclass(frozen=True)
class ResearchTopic:
    topic_id: str
    title: str
    hypothesis: str
    validation_plan: str
    runner: str
    candidate_dir: str
    baseline_dir: str
    score: float
    reasons: list[str]
    evidence_sources: list[str]
    ranking_file_count: int
    status: str = "candidate"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="generate autonomous research topics and optionally run safe backtests")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--output", default=None)
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument("--baseline-dir", default=BASELINE_RANKINGS_DIR)
    parser.add_argument("--candidate-dir", default=None, help="指定候選 ranking 目錄；未指定時由 autopilot 自己選")
    parser.add_argument("--topic-index", type=int, default=0)
    parser.add_argument("--max-topics", type=int, default=12)
    parser.add_argument("--min-ranking-files", type=int, default=3)
    parser.add_argument("--max-ranking-files", type=int, default=8)
    parser.add_argument("--horizons", default="3,5,10")
    parser.add_argument("--stop-loss-pcts", default="none,0.08,0.12")
    parser.add_argument("--take-profit-pcts", default="none,0.15,0.25")
    parser.add_argument("--max-group-exposures", default="none,0.35,0.55")
    parser.add_argument("--execute", action="store_true", help="實際執行 baseline/candidate strategy matrix 與 comparison")
    parser.add_argument("--execute-topic-count", type=int, default=1, help="單次 execute 最多執行幾個題目")
    parser.add_argument("--from-queue", action="store_true", help="從 manager queue 選下一批題目，而不是只用 --topic-index")
    parser.add_argument("--rerun", action="store_true", help="允許重跑已執行過的同題目")
    parser.add_argument("--include-rejected", action="store_true", help="佇列選題時允許 rejected topic 重新進入")
    parser.add_argument("--no-manager-update", action="store_true", help="只產生本次 run artifact，不更新管理層狀態")
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


def slugify(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower()).strip("-")
    if not text:
        return "research-topic"
    if len(text) <= 90:
        return text
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]
    return f"{text[:80]}-{digest}"


def load_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def write_run_artifacts(payload: dict[str, Any], output: Path) -> None:
    write_text_atomic(output, json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False))
    write_text_atomic(output.with_suffix(".md"), render_markdown(payload))


def ranking_dirs(min_ranking_files: int) -> list[dict[str, Any]]:
    roots = [ARTIFACTS_DIR / "backtest", ARTIFACTS_DIR / "research_rankings"]
    by_dir: dict[Path, int] = {}
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("ranking_*.csv"):
            by_dir[path.parent] = by_dir.get(path.parent, 0) + 1
    rows = []
    for path, count in by_dir.items():
        if count < min_ranking_files:
            continue
        rows.append({"path": path, "repo_path": repo_path(path), "count": count, "mtime": path.stat().st_mtime})
    return sorted(rows, key=lambda item: (-int(item["count"]), str(item["repo_path"])))


def latest_external_review_summary() -> tuple[dict[str, Any], str | None]:
    root = ARTIFACTS_DIR / "external_review"
    if not root.exists():
        return {}, None
    matches = sorted(root.rglob("external_review_summary_*.json"))
    if not matches:
        return {}, None
    path = matches[-1]
    return load_json(path), repo_path(path)


def ledger_signals() -> tuple[list[str], list[str]]:
    ledger = load_json(LEDGER_PATH)
    candidates = []
    sources = []
    if ledger:
        sources.append(repo_path(LEDGER_PATH) or str(LEDGER_PATH))
    for entry in ledger.get("experiments", []):
        status = str(entry.get("status") or "")
        if status not in {"pending", "partial", "failed"}:
            continue
        candidate = str(entry.get("candidate") or "").strip()
        if candidate:
            candidates.append(candidate.lower())
    return sorted(set(candidates)), sources


def external_review_signals() -> tuple[list[str], list[str]]:
    summary, source = latest_external_review_summary()
    signals = []
    sources = [source] if source else []
    for item in summary.get("research_hypotheses", []):
        if not isinstance(item, dict):
            continue
        family = str(item.get("candidate_signal_family") or "").strip().lower()
        priority = str(item.get("priority") or "").strip().lower()
        if family:
            signals.append(family)
        if priority == "high":
            signals.append("high_priority_external_review")
    return sorted(set(signals)), [item for item in sources if item]


def is_baseline_like(path_text: str) -> bool:
    lowered = path_text.lower()
    return "historical_rankings_current_model" in lowered or "/current_model" in lowered


def keyword_score(path_text: str) -> tuple[float, list[str]]:
    lowered = path_text.lower()
    score = 0.0
    reasons: list[str] = []
    weights = [
        ("odd_lot", 35, "odd-lot capital realism line"),
        ("candidate", 22, "candidate ranking artifact"),
        ("big_bull", 20, "big bull regime hypothesis"),
        ("liquidity", 18, "liquidity quality hypothesis"),
        ("regime", 16, "regime conditional hypothesis"),
        ("guard", 12, "risk guard variant"),
        ("daily_recommendation", 12, "daily recommendation quality line"),
        ("sector", 10, "sector/theme context"),
        ("feature_group", 8, "feature group shadow ranking"),
        ("smoke", -25, "smoke artifact is lower priority"),
    ]
    for key, weight, reason in weights:
        if key in lowered:
            score += weight
            reasons.append(reason)
    return score, reasons


def signal_bonus(path_text: str, ledger_candidates: list[str], external_signals: list[str]) -> tuple[float, list[str]]:
    lowered = path_text.lower()
    score = 0.0
    reasons: list[str] = []
    for candidate in ledger_candidates:
        normalized = candidate.replace("-", "_")
        if normalized and normalized in lowered:
            score += 14
            reasons.append(f"ledger pending/partial signal matched: {candidate}")
    signal_map = {
        "risk_control": ["guard", "stop", "exit", "trail"],
        "liquidity": ["liquidity"],
        "timing": ["setup", "daily_recommendation", "entry"],
        "theme_momentum": ["sector", "industry", "regime", "big_bull"],
        "relative_strength": ["feature_group", "candidate", "rank"],
    }
    for signal in external_signals:
        for keyword in signal_map.get(signal, []):
            if keyword in lowered:
                score += 8
                reasons.append(f"external review signal matched: {signal}")
                break
        if signal == "high_priority_external_review":
            score += 4
            reasons.append("external review has high-priority hypothesis")
    return score, reasons


def topic_for_dir(
    row: dict[str, Any],
    *,
    baseline_dir: str,
    ledger_candidates: list[str],
    external_signals: list[str],
    evidence_sources: list[str],
) -> ResearchTopic | None:
    candidate_dir = str(row["repo_path"])
    if not candidate_dir or is_baseline_like(candidate_dir):
        return None
    key_score, key_reasons = keyword_score(candidate_dir)
    sig_score, sig_reasons = signal_bonus(candidate_dir, ledger_candidates, external_signals)
    count = int(row["count"])
    sample_score = min(count, 60) / 3
    score = round(10 + sample_score + key_score + sig_score, 3)
    label = candidate_dir
    topic_id = f"strategy-matrix:{slugify(candidate_dir)}"
    return ResearchTopic(
        topic_id=topic_id,
        title=f"回測 ranking variant：{Path(candidate_dir).name}",
        hypothesis=f"{label} 相對 current baseline，在相同 strategy matrix 參數下可提升 best_score，且 max drawdown 不惡化。",
        validation_plan="同時跑 current baseline 與 candidate 的 strategy matrix，再用 compare_strategy_matrices 比較 best_score、return、drawdown。",
        runner="strategy_matrix_comparison",
        candidate_dir=candidate_dir,
        baseline_dir=baseline_dir,
        score=score,
        reasons=key_reasons + sig_reasons + [f"ranking files: {count}"],
        evidence_sources=evidence_sources + [candidate_dir],
        ranking_file_count=count,
    )


def generate_topics(args: argparse.Namespace) -> list[ResearchTopic]:
    ledger_candidates, ledger_sources = ledger_signals()
    external_signals, external_sources = external_review_signals()
    evidence_sources = ledger_sources + external_sources
    if args.candidate_dir:
        path = resolve_path(args.candidate_dir)
        count = len(list(path.glob("ranking_*.csv"))) if path else 0
        row = {"repo_path": repo_path(path), "count": count, "mtime": path.stat().st_mtime if path and path.exists() else 0}
        topic = topic_for_dir(
            row,
            baseline_dir=args.baseline_dir,
            ledger_candidates=ledger_candidates,
            external_signals=external_signals,
            evidence_sources=evidence_sources,
        )
        return [topic] if topic else []
    topics = []
    for row in ranking_dirs(args.min_ranking_files):
        topic = topic_for_dir(
            row,
            baseline_dir=args.baseline_dir,
            ledger_candidates=ledger_candidates,
            external_signals=external_signals,
            evidence_sources=evidence_sources,
        )
        if topic is not None:
            topics.append(topic)
    return sorted(topics, key=lambda item: (-item.score, item.topic_id))[: args.max_topics]


def matrix_command(args: argparse.Namespace, rankings_dir: str, output: str) -> list[str]:
    return [
        sys.executable,
        "scripts/run_backtest_strategy_matrix.py",
        "--rankings-dir",
        rankings_dir,
        "--features",
        args.features,
        "--max-ranking-files",
        str(args.max_ranking_files),
        "--horizons",
        args.horizons,
        "--stop-loss-pcts",
        args.stop_loss_pcts,
        "--take-profit-pcts",
        args.take_profit_pcts,
        "--max-group-exposures",
        args.max_group_exposures,
        "--output",
        output,
    ]


def compare_command(baseline_output: str, candidate_output: str, comparison_output: str) -> list[str]:
    return [
        sys.executable,
        "scripts/compare_strategy_matrices.py",
        "--variant",
        f"baseline={baseline_output}",
        "--variant",
        f"candidate={candidate_output}",
        "--output",
        comparison_output,
    ]


def command_allowed(command: list[str]) -> bool:
    if len(command) < 2:
        return False
    script = command[1]
    return script in ALLOWED_RUNNERS


def run_step(name: str, command: list[str]) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    if not command_allowed(command):
        ended = datetime.now(timezone.utc)
        return {
            "name": name,
            "status": "BLOCKED",
            "returncode": None,
            "started_at": started.isoformat(),
            "ended_at": ended.isoformat(),
            "command": command,
            "stdout_tail": "",
            "stderr_tail": "runner is not allowlisted",
        }
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    ended = datetime.now(timezone.utc)
    return {
        "name": name,
        "status": "OK" if completed.returncode == 0 else "FAILED",
        "returncode": completed.returncode,
        "started_at": started.isoformat(),
        "ended_at": ended.isoformat(),
        "command": command,
        "stdout_tail": completed.stdout[-3000:],
        "stderr_tail": completed.stderr[-3000:],
    }


def selected_topic(topics: list[ResearchTopic], index: int) -> ResearchTopic | None:
    if not topics or index < 0 or index >= len(topics):
        return None
    return topics[index]


def load_topic_registry() -> dict[str, dict[str, Any]]:
    path = manager_paths()["registry"]
    return {row.get("topic_id"): row for row in load_list_payload(path, "topics") if row.get("topic_id")}


def load_next_action_queue() -> list[dict[str, Any]]:
    return load_list_payload(manager_paths()["queue"], "actions")


def topic_allowed_by_manager(topic: ResearchTopic, registry: dict[str, dict[str, Any]], args: argparse.Namespace) -> bool:
    current = registry.get(topic.topic_id, {})
    status = str(current.get("manager_status") or "candidate")
    if status == "rejected" and not args.include_rejected:
        return False
    if int(current.get("run_count") or 0) > 0 and not args.rerun:
        return False
    return status in {"candidate", "confirmed_for_next_replay", "partial_needs_followup", "blocked_missing_evidence", "rejected"}


def select_topics_for_run(topics: list[ResearchTopic], args: argparse.Namespace) -> list[ResearchTopic]:
    if not topics:
        return []
    count = max(1, int(args.execute_topic_count or 1))
    registry = load_topic_registry()
    if args.from_queue:
        by_topic_id = {topic.topic_id: topic for topic in topics}
        selected: list[ResearchTopic] = []
        seen: set[str] = set()
        for action in load_next_action_queue():
            topic_id = str(action.get("topic_id") or "")
            if not topic_id or topic_id in seen:
                continue
            topic = by_topic_id.get(topic_id)
            if topic is None:
                continue
            if not topic_allowed_by_manager(topic, registry, args):
                continue
            selected.append(topic)
            seen.add(topic_id)
            if len(selected) >= count:
                break
        return selected
    if count > 1:
        selected = [topic for topic in topics if topic_allowed_by_manager(topic, registry, args)]
        return selected[:count]
    topic = selected_topic(topics, args.topic_index)
    if topic is None:
        return []
    if args.execute and not args.rerun and not topic_allowed_by_manager(topic, registry, args):
        fallback = [item for item in topics if topic_allowed_by_manager(item, registry, args)]
        return fallback[:1]
    return [topic]


def topic_to_json(topic: ResearchTopic) -> dict[str, Any]:
    return {
        "topic_id": topic.topic_id,
        "title": topic.title,
        "hypothesis": topic.hypothesis,
        "validation_plan": topic.validation_plan,
        "runner": topic.runner,
        "candidate_dir": topic.candidate_dir,
        "baseline_dir": topic.baseline_dir,
        "score": topic.score,
        "reasons": topic.reasons,
        "evidence_sources": topic.evidence_sources,
        "ranking_file_count": topic.ranking_file_count,
        "status": topic.status,
    }


def outcome_from_comparison(path: Path | None) -> dict[str, Any]:
    payload = load_json(path)
    rows = {row.get("variant"): row for row in payload.get("summary", [])}
    baseline = rows.get("baseline") or {}
    candidate = rows.get("candidate") or {}
    score_delta = delta(candidate.get("best_score"), baseline.get("best_score"))
    return_delta = delta(candidate.get("best_total_return"), baseline.get("best_total_return"))
    drawdown_delta = delta(candidate.get("best_max_drawdown"), baseline.get("best_max_drawdown"))
    if score_delta is None:
        decision = "NO_COMPARISON_EVIDENCE"
    elif score_delta > 0 and (return_delta or 0) >= 0 and (drawdown_delta or 0) >= 0:
        decision = "CONFIRMED_FOR_NEXT_REPLAY"
    elif score_delta > 0:
        decision = "PARTIAL_SCORE_ONLY"
    else:
        decision = "REJECTED_BY_STRATEGY_MATRIX"
    return {
        "decision": decision,
        "score_delta": score_delta,
        "return_delta": return_delta,
        "drawdown_delta": drawdown_delta,
        "baseline": baseline,
        "candidate": candidate,
        "promotion_allowed": False,
    }


def topic_manager_status(topic: dict[str, Any], run_outcome: dict[str, Any] | None = None) -> str:
    if run_outcome:
        decision = run_outcome.get("decision")
        if decision == "CONFIRMED_FOR_NEXT_REPLAY":
            return "confirmed_for_next_replay"
        if decision == "PARTIAL_SCORE_ONLY":
            return "partial_needs_followup"
        if decision == "REJECTED_BY_STRATEGY_MATRIX":
            return "rejected"
        if decision == "NO_COMPARISON_EVIDENCE":
            return "blocked_missing_evidence"
    return str(topic.get("manager_status") or "candidate")


def next_action_for_status(status: str, topic: dict[str, Any]) -> str:
    mapping = {
        "candidate": "run_autonomous_research_execute_smoke",
        "confirmed_for_next_replay": "promote_to_longer_replay_candidate",
        "partial_needs_followup": "rerun_with_larger_window_or_add_risk_check",
        "rejected": "archive_or_wait_for_new_evidence",
        "blocked_missing_evidence": "inspect_runner_outputs_and_missing_artifacts",
    }
    return mapping.get(status, f"manual_review:{topic.get('topic_id')}")


def manager_paths() -> dict[str, Path]:
    return {
        "registry": OUTPUT_DIR / "topic_registry.json",
        "history": OUTPUT_DIR / "run_history.json",
        "queue": OUTPUT_DIR / "next_action_queue.json",
        "summary": OUTPUT_DIR / "manager_summary.json",
        "runner_registry": OUTPUT_DIR / "runner_registry.json",
    }


def load_list_payload(path: Path, key: str) -> list[dict[str, Any]]:
    payload = load_json(path)
    value = payload.get(key)
    return value if isinstance(value, list) else []


def update_manager(payload: dict[str, Any], run_output: Path) -> dict[str, Any]:
    paths = manager_paths()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    registry_rows = {row.get("topic_id"): row for row in load_list_payload(paths["registry"], "topics") if row.get("topic_id")}
    selected_topics = [item for item in payload.get("selected_topics", []) if item.get("topic_id")]
    selected_ids = {item.get("topic_id") for item in selected_topics}
    topic_runs = payload.get("topic_runs", [])
    outcome_by_topic = {
        run.get("topic", {}).get("topic_id"): run.get("outcome")
        for run in topic_runs
        if run.get("topic", {}).get("topic_id")
    }
    for topic in payload.get("topics", []):
        topic_id = topic.get("topic_id")
        if not topic_id:
            continue
        current = registry_rows.get(topic_id, {})
        run_outcome = outcome_by_topic.get(topic_id) if payload["inputs"].get("execute") else None
        manager_status = topic_manager_status(current or topic, run_outcome)
        registry_rows[topic_id] = {
            **current,
            **topic,
            "manager_status": manager_status,
            "next_action": next_action_for_status(manager_status, topic),
            "last_seen_at": now,
            "last_run_output": repo_path(run_output) if topic_id in selected_ids else current.get("last_run_output"),
            "last_decision": (run_outcome or {}).get("decision") if topic_id in selected_ids else current.get("last_decision"),
            "run_count": int(current.get("run_count") or 0) + (1 if topic_id in selected_ids and payload["inputs"].get("execute") else 0),
        }

    history = load_list_payload(paths["history"], "runs")
    history.append(
        {
            "run_id": f"{payload['date']}:{Path(run_output).stem}",
            "date": payload["date"],
            "generated_at": payload["generated_at"],
            "execute": payload["inputs"].get("execute"),
            "status": payload["status"],
            "selected_topic_id": selected_topics[0].get("topic_id") if selected_topics else None,
            "selected_topic_ids": sorted(selected_ids),
            "decision": (payload.get("outcome") or {}).get("decision"),
            "decisions": [
                {
                    "topic_id": run.get("topic", {}).get("topic_id"),
                    "decision": (run.get("outcome") or {}).get("decision"),
                    "status": run.get("status"),
                }
                for run in topic_runs
            ],
            "output": repo_path(run_output),
            "promotion_allowed": False,
        }
    )
    history = history[-200:]
    topics = sorted(registry_rows.values(), key=lambda item: (-float(item.get("score") or 0), str(item.get("topic_id"))))
    actionable_statuses = {"candidate", "confirmed_for_next_replay", "partial_needs_followup", "blocked_missing_evidence"}
    queue = [
        {
            "topic_id": topic.get("topic_id"),
            "manager_status": topic.get("manager_status"),
            "next_action": topic.get("next_action"),
            "score": topic.get("score"),
            "last_decision": topic.get("last_decision"),
            "candidate_dir": topic.get("candidate_dir"),
        }
        for topic in topics
        if topic.get("manager_status") in actionable_statuses
    ][:25]
    counts: dict[str, int] = {}
    for topic in topics:
        status = str(topic.get("manager_status") or "candidate")
        counts[status] = counts.get(status, 0) + 1
    summary = {
        "schema_version": MANAGER_SCHEMA_VERSION,
        "updated_at": now,
        "status": "OK",
        "topic_count": len(topics),
        "run_count": len(history),
        "status_counts": counts,
        "next_action_count": len(queue),
        "top_next_actions": queue[:5],
        "latest_run": history[-1] if history else None,
        "contract": {
            "research_only": True,
            "manager_does_not_promote": True,
            "production_promotion_allowed": False,
        },
    }
    write_text_atomic(
        paths["registry"],
        json.dumps({"schema_version": "autonomous-research-topic-registry.v1", "updated_at": now, "topics": topics}, ensure_ascii=False, indent=2, allow_nan=False),
    )
    write_text_atomic(
        paths["history"],
        json.dumps({"schema_version": "autonomous-research-run-history.v1", "updated_at": now, "runs": history}, ensure_ascii=False, indent=2, allow_nan=False),
    )
    write_text_atomic(
        paths["queue"],
        json.dumps({"schema_version": "autonomous-research-next-action-queue.v1", "updated_at": now, "actions": queue}, ensure_ascii=False, indent=2, allow_nan=False),
    )
    write_text_atomic(
        paths["runner_registry"],
        json.dumps(
            {
                "schema_version": RUNNER_REGISTRY_SCHEMA_VERSION,
                "updated_at": now,
                "runners": RUNNER_SPECS,
                "allowed_scripts": sorted(ALLOWED_RUNNERS),
                "contract": {
                    "allowlisted_runners_only": True,
                    "production_promotion_allowed": False,
                },
            },
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
    )
    write_text_atomic(paths["summary"], json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False))
    return {
        "status": "OK",
        "topic_registry": repo_path(paths["registry"]),
        "run_history": repo_path(paths["history"]),
        "next_action_queue": repo_path(paths["queue"]),
        "manager_summary": repo_path(paths["summary"]),
        "runner_registry": repo_path(paths["runner_registry"]),
        "status_counts": counts,
        "next_action_count": len(queue),
    }


def delta(left: Any, right: Any) -> float | None:
    try:
        if left is None or right is None:
            return None
        return round(float(left) - float(right), 6)
    except (TypeError, ValueError):
        return None


def execute_topic(args: argparse.Namespace, topic: ResearchTopic, run_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, str]]:
    slug = slugify(topic.topic_id)
    baseline_output = run_dir / f"{slug}_baseline_strategy_matrix.json"
    candidate_output = run_dir / f"{slug}_candidate_strategy_matrix.json"
    comparison_output = run_dir / f"{slug}_comparison.json"
    commands = [
        ("baseline.strategy_matrix", matrix_command(args, topic.baseline_dir, repo_path(baseline_output) or str(baseline_output))),
        ("candidate.strategy_matrix", matrix_command(args, topic.candidate_dir, repo_path(candidate_output) or str(candidate_output))),
        (
            "compare.strategy_matrices",
            compare_command(
                repo_path(baseline_output) or str(baseline_output),
                repo_path(candidate_output) or str(candidate_output),
                repo_path(comparison_output) or str(comparison_output),
            ),
        ),
    ]
    steps: list[dict[str, Any]] = []
    failed: str | None = None
    for name, command in commands:
        if failed:
            steps.append(
                {
                    "name": name,
                    "status": "SKIPPED",
                    "returncode": None,
                    "started_at": datetime.now(timezone.utc).isoformat(),
                    "ended_at": datetime.now(timezone.utc).isoformat(),
                    "command": command,
                    "stdout_tail": "",
                    "stderr_tail": "",
                    "skip_reason": f"previous step failed: {failed}",
                }
            )
            continue
        step = run_step(name, command)
        steps.append(step)
        if step["status"] != "OK":
            failed = name
    outcome = outcome_from_comparison(comparison_output if comparison_output.exists() else None)
    outputs = {
        "baseline_strategy_matrix": repo_path(baseline_output) or str(baseline_output),
        "candidate_strategy_matrix": repo_path(candidate_output) or str(candidate_output),
        "comparison": repo_path(comparison_output) or str(comparison_output),
    }
    return steps, outcome, outputs


def build_payload(
    args: argparse.Namespace,
    topics: list[ResearchTopic],
    selected_topics_for_run: list[ResearchTopic],
    topic_runs: list[dict[str, Any]],
    steps: list[dict[str, Any]],
    outcome: dict[str, Any],
    outputs: dict[str, str],
    manager: dict[str, Any] | None = None,
) -> dict[str, Any]:
    selected = selected_topics_for_run[0] if selected_topics_for_run else None
    executed = bool(args.execute and selected_topics_for_run)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK" if (not executed or all(step["status"] == "OK" for step in steps)) else "FAILED",
        "contract": {
            "autonomous_topic_generation": True,
            "research_only": True,
            "allowlisted_runners_only": True,
            "does_not_fetch_data": True,
            "does_not_train_model": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_risk_adjusted_score": True,
            "does_not_change_production_ranking": True,
            "production_promotion_allowed": False,
        },
        "inputs": {
            "execute": args.execute,
            "features": args.features,
            "baseline_dir": args.baseline_dir,
            "candidate_dir": args.candidate_dir,
            "topic_index": args.topic_index,
            "execute_topic_count": args.execute_topic_count,
            "from_queue": args.from_queue,
            "rerun": args.rerun,
            "include_rejected": args.include_rejected,
            "max_ranking_files": args.max_ranking_files,
            "horizons": args.horizons,
            "stop_loss_pcts": args.stop_loss_pcts,
            "take_profit_pcts": args.take_profit_pcts,
            "max_group_exposures": args.max_group_exposures,
            "manager_update": not args.no_manager_update,
        },
        "selected_topic": topic_to_json(selected) if selected else None,
        "selected_topics": [topic_to_json(topic) for topic in selected_topics_for_run],
        "topics": [topic_to_json(topic) for topic in topics],
        "topic_runs": topic_runs,
        "steps": steps,
        "outcome": outcome,
        "outputs": outputs,
        "manager": manager or {"status": "PENDING_WRITE"},
    }


def render_markdown(payload: dict[str, Any]) -> str:
    selected = payload.get("selected_topic") or {}
    lines = [
        "# Autonomous Research Run",
        "",
        f"- status: `{payload['status']}`",
        f"- execute: `{payload['inputs']['execute']}`",
        f"- selected: `{selected.get('topic_id')}`",
        f"- decision: `{payload.get('outcome', {}).get('decision')}`",
        f"- manager: `{payload.get('manager', {}).get('status')}`",
        f"- production_promotion_allowed: `{payload['contract']['production_promotion_allowed']}`",
        "",
        "## Selected Topic",
        "",
        f"- title: {selected.get('title')}",
        f"- hypothesis: {selected.get('hypothesis')}",
        f"- validation_plan: {selected.get('validation_plan')}",
        "",
        "## Top Topics",
        "",
        "| Rank | Topic | Score | Ranking Files |",
        "|---:|---|---:|---:|",
    ]
    for index, topic in enumerate(payload.get("topics", [])[:10], start=1):
        lines.append(f"| {index} | `{topic['topic_id']}` | {topic['score']} | {topic['ranking_file_count']} |")
    lines.extend(["", "## Steps", "", "| Step | Status |", "|---|---|"])
    for step in payload.get("steps", []):
        lines.append(f"| `{step['name']}` | `{step['status']}` |")
    manager = payload.get("manager") or {}
    lines.extend(["", "## Manager", ""])
    for key in ["topic_registry", "run_history", "next_action_queue", "manager_summary", "runner_registry"]:
        if manager.get(key):
            lines.append(f"- `{key}`: `{manager[key]}`")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    output = resolve_path(args.output) or OUTPUT_DIR / f"autonomous_research_{args.date}.json"
    run_dir = output.parent / f"run_{args.date}_{datetime.now().strftime('%H%M%S')}"
    output.parent.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=True, exist_ok=True)
    topics = generate_topics(args)
    selected_topics_for_run = select_topics_for_run(topics, args)
    steps: list[dict[str, Any]] = []
    topic_runs: list[dict[str, Any]] = []
    first_topic = selected_topics_for_run[0] if selected_topics_for_run else None
    outcome = {"decision": "DRY_RUN_TOPIC_SELECTED" if first_topic else "NO_EXECUTABLE_TOPIC", "promotion_allowed": False}
    outputs: dict[str, str] = {"run_dir": repo_path(run_dir) or str(run_dir)}
    if args.execute and selected_topics_for_run:
        decisions: list[str] = []
        for index, topic in enumerate(selected_topics_for_run, start=1):
            topic_steps, topic_outcome, step_outputs = execute_topic(args, topic, run_dir)
            prefixed_steps = [{**step, "name": f"topic{index}.{step['name']}", "topic_id": topic.topic_id} for step in topic_steps]
            steps.extend(prefixed_steps)
            decisions.append(str(topic_outcome.get("decision")))
            topic_runs.append(
                {
                    "topic": topic_to_json(topic),
                    "status": "OK" if all(step["status"] == "OK" for step in topic_steps) else "FAILED",
                    "outcome": topic_outcome,
                    "steps": topic_steps,
                    "outputs": step_outputs,
                }
            )
            if index == 1:
                outcome = topic_outcome
                outputs.update(step_outputs)
        outcome = {
            **outcome,
            "aggregate": {
                "topic_count": len(selected_topics_for_run),
                "decisions": decisions,
                "all_topic_runs_ok": all(run["status"] == "OK" for run in topic_runs),
            },
            "promotion_allowed": False,
        }
    payload = build_payload(args, topics, selected_topics_for_run, topic_runs, steps, outcome, outputs)
    write_run_artifacts(payload, output)
    if not args.no_manager_update:
        manager = update_manager(payload, output)
        payload = build_payload(args, topics, selected_topics_for_run, topic_runs, steps, outcome, outputs, manager=manager)
        write_run_artifacts(payload, output)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "output": repo_path(output),
                "selected_topic": (payload.get("selected_topic") or {}).get("topic_id"),
                "decision": payload.get("outcome", {}).get("decision"),
                "execute": args.execute,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
