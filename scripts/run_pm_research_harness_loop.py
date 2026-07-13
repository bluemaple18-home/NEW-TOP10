#!/usr/bin/env python3
"""PM 核准後自動驅動 research harness，並把下一批決策卡送回 Discord。

本 loop 只做 research-only automation：
- 讀 PM decision state / approved work queue。
- 觸發既有 autonomous research runner。
- 產生下一輪 PM 審核卡。
- 可選擇透過 OpenClaw gateway 送到 review-approval Discord 頻道。

不改 ranking、不訓練模型、不改推播。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_pm_approved_work_queue import build_payload as build_approved_work_queue
from scripts.build_pm_approved_work_queue import repo_path, write_json, write_research_cards


ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
STATE_DIR = ARTIFACTS_DIR / "pm_research_harness"
STATE_PATH = STATE_DIR / "harness_state.json"
SCHEMA_VERSION = "top10-pm-research-harness-loop.v1"
PROJECT_DOMAIN = "TOP10_STOCK"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="run PM-approved research harness loop")
    parser.add_argument("--date", default=None)
    parser.add_argument("--pm-run-dir", action="append", default=[])
    parser.add_argument("--quota", type=int, default=2)
    parser.add_argument("--max-ranking-files", type=int, default=8)
    parser.add_argument("--max-review-cards", type=int, default=8)
    parser.add_argument("--max-continuation-runs", type=int, default=8)
    parser.add_argument("--min-queue-depth", type=int, default=12)
    parser.add_argument("--discovery-max-topics", type=int, default=30)
    parser.add_argument("--config", default="config/automation.yaml")
    parser.add_argument("--state", default=str(STATE_PATH))
    parser.add_argument("--send-cards", action="store_true")
    parser.add_argument("--dry-run-send", action="store_true")
    parser.add_argument("--target", default=None)
    parser.add_argument("--node-bin", default=None)
    parser.add_argument("--openclaw-entry", default=None)
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def local_date(config: dict[str, Any]) -> str:
    timezone_name = str(config.get("timezone") or "Asia/Taipei")
    return datetime.now(ZoneInfo(timezone_name)).date().isoformat()


def read_json(path: Path, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return fallback or {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else (fallback or {})


def read_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {}


def write_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def load_state(path: Path) -> dict[str, Any]:
    state = read_json(path, {})
    return {
        "schema_version": "top10-pm-research-harness-state.v1",
        "loop_enabled": bool(state.get("loop_enabled")),
        "consumed_approvals": list_value(state.get("consumed_approvals")),
        "sent_decision_ids": list_value(state.get("sent_decision_ids")),
        "runs": list_value(state.get("runs")),
        "consecutive_empty_runs": int(state.get("consecutive_empty_runs") or 0),
        "consecutive_no_approval_runs": int(state.get("consecutive_no_approval_runs") or 0),
    }


def list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def discover_pm_run_dirs(args: argparse.Namespace) -> list[Path]:
    if args.pm_run_dir:
        return [resolve_path(path) for path in args.pm_run_dir]
    candidates = []
    for state_path in sorted((ARTIFACTS_DIR / "pm_review_cards").glob("*/pm_decision_state.json")):
        run_dir = state_path.parent
        if "test" in run_dir.name:
            continue
        if not is_top10_stock_run_dir(run_dir):
            continue
        candidates.append(run_dir)
    return candidates


def is_top10_stock_run_dir(run_dir: Path) -> bool:
    cards_payload = read_json(run_dir / "cards.json", {})
    if cards_payload.get("project_domain") != PROJECT_DOMAIN:
        return False
    cards = cards_payload.get("cards") if isinstance(cards_payload.get("cards"), dict) else {}
    if not cards:
        return False
    for card in cards.values():
        if not isinstance(card, dict) or card.get("project_domain") != PROJECT_DOMAIN:
            return False
    return True


def approval_key(item: dict[str, Any]) -> str:
    return f"{item.get('run_dir')}::{item.get('card_id')}"


def approved_work_for_run(run_dir: Path, date_text: str) -> dict[str, Any]:
    payload = build_approved_work_queue(run_dir, date_text)
    output = run_dir / "approved_work_queue.json"
    research_output = ARTIFACTS_DIR / "autonomous_research" / f"research_cards_{date_text}.jsonl"
    write_json(output, payload)
    write_research_cards(research_output, payload, date_text)
    return payload


def collect_pending_approvals(run_dirs: list[Path], state: dict[str, Any], date_text: str) -> tuple[list[dict[str, Any]], list[str]]:
    consumed = {str(item) for item in state.get("consumed_approvals", [])}
    pending = []
    queue_paths = []
    for run_dir in run_dirs:
        if not (run_dir / "pm_decision_state.json").exists():
            continue
        if not is_top10_stock_run_dir(run_dir):
            queue_paths.append(str(run_dir / "approved_work_queue.json"))
            continue
        payload = approved_work_for_run(run_dir, date_text)
        queue_paths.append(str(run_dir / "approved_work_queue.json"))
        for item in payload.get("items", []):
            if not isinstance(item, dict):
                continue
            if not item.get("run_dir") or not item.get("card_id"):
                continue
            key = approval_key(item)
            if key not in consumed and item.get("route") == "research_worker":
                pending.append(item)
    return pending, queue_paths


def python_bin() -> str:
    candidate = PROJECT_ROOT / ".venv" / "bin" / "python"
    return str(candidate) if candidate.exists() else "python3"


def run_checked(command: list[str]) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, cwd=PROJECT_ROOT, text=True, capture_output=True)
    if completed.returncode != 0:
        raise RuntimeError(
            "command failed "
            f"exit_code={completed.returncode}: {' '.join(command)}\n"
            f"stdout={completed.stdout[-1000:]}\nstderr={completed.stderr[-1000:]}"
        )
    return completed


def current_queue_depth() -> int:
    queue = read_json(ARTIFACTS_DIR / "autonomous_research" / "next_action_queue.json", {})
    actions = queue.get("actions") if isinstance(queue.get("actions"), list) else []
    return len([item for item in actions if isinstance(item, dict)])


def top_up_research_queue_from_registry(min_depth: int, max_items: int) -> int:
    """queue 不足時，優先從題目庫補 fresh 題，再用高分 rejected 題作 revisit。"""
    research_dir = ARTIFACTS_DIR / "autonomous_research"
    queue_path = research_dir / "next_action_queue.json"
    registry_path = research_dir / "topic_registry.json"
    topic_bank_path = research_dir / "topic_bank.json"
    queue_payload = read_json(queue_path, {})
    registry_payload = read_json(registry_path, {})
    topic_bank_payload = read_json(topic_bank_path, {})
    actions = queue_payload.get("actions") if isinstance(queue_payload.get("actions"), list) else []
    actions = [item for item in actions if isinstance(item, dict)]
    if len(actions) >= min_depth:
        return 0

    bank_topics = topic_bank_payload.get("topics") if isinstance(topic_bank_payload.get("topics"), list) else []
    registry_topics = registry_payload.get("topics") if isinstance(registry_payload.get("topics"), list) else []
    registry_by_id = {
        str(item.get("topic_id")): item
        for item in registry_topics
        if isinstance(item, dict) and item.get("topic_id")
    }
    topic_rows = bank_topics if bank_topics else registry_topics
    existing_ids = {str(item.get("topic_id") or "") for item in actions}
    needed = max(0, min(max_items, min_depth - len(actions)))
    candidates = []
    for item in topic_rows:
        if not isinstance(item, dict) or not item.get("topic_id"):
            continue
        topic_id = str(item.get("topic_id"))
        if topic_id in existing_ids:
            continue
        registry_row = registry_by_id.get(topic_id, {})
        manager_status = str(registry_row.get("manager_status") or item.get("manager_status") or item.get("status") or "candidate")
        if manager_status not in {"candidate", "confirmed_for_next_replay", "partial_needs_followup", "blocked_missing_evidence", "rejected"}:
            continue
        candidates.append((manager_status, item, registry_row))
    candidates = sorted(
        candidates,
        key=lambda row: (
            1 if row[0] == "rejected" else 0,
            -float(row[1].get("score") or 0),
            str(row[1].get("topic_id")),
        ),
    )
    additions = []
    added_ids = set()
    for manager_status, topic, registry_row in candidates[:needed]:
        is_revisit = manager_status == "rejected"
        topic_id = str(topic.get("topic_id") or "")
        additions.append(
            {
                "topic_id": topic_id,
                "manager_status": manager_status,
                "next_action": "rerun_rejected_with_larger_window_or_risk_check"
                if is_revisit
                else "run_autonomous_research_execute_smoke",
                "score": topic.get("score"),
                "last_decision": registry_row.get("last_decision"),
                "candidate_dir": topic.get("candidate_dir"),
                "queue_reason": "pm_harness_low_water_revisit" if is_revisit else "pm_harness_low_water_topic_bank",
            }
        )
        added_ids.add(topic_id)
    if not additions:
        return 0
    output = {
        "schema_version": "autonomous-research-next-action-queue.v1",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "actions": [*actions, *additions],
    }
    write_state(queue_path, output)
    if bank_topics and added_ids:
        remaining_bank_topics = [
            item
            for item in bank_topics
            if isinstance(item, dict) and str(item.get("topic_id") or "") not in added_ids
        ]
        topic_bank_payload["topics"] = remaining_bank_topics
        topic_bank_payload["topic_count"] = len(remaining_bank_topics)
        topic_bank_payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        write_state(topic_bank_path, topic_bank_payload)
    return len(additions)


def discover_research_topics(date_text: str, max_topics: int, max_ranking_files: int) -> Path:
    stamp = datetime.now(ZoneInfo("Asia/Taipei")).strftime("%Y%m%d_%H%M%S")
    output = ARTIFACTS_DIR / "autonomous_research" / f"pm_research_topic_discovery_{date_text}_{stamp}.json"
    run_checked(
        [
            python_bin(),
            "scripts/run_autonomous_research.py",
            "--date",
            date_text,
            "--max-topics",
            str(max_topics),
            "--max-ranking-files",
            str(max_ranking_files),
            "--output",
            repo_path(output) or str(output),
        ]
    )
    return output


def run_research(date_text: str, quota: int, max_ranking_files: int) -> tuple[Path, str]:
    stamp = datetime.now(ZoneInfo("Asia/Taipei")).strftime("%Y%m%d_%H%M%S")
    output = ARTIFACTS_DIR / "autonomous_research" / f"pm_research_harness_{date_text}_{stamp}.json"
    verification_output = output.with_name(f"{output.stem}_verification.json")
    run_checked(
        [
            python_bin(),
            "scripts/run_autonomous_research.py",
            "--date",
            date_text,
            "--execute",
            "--from-queue",
            "--rerun",
            "--include-rejected",
            "--execute-topic-count",
            str(quota),
            "--max-topics",
            "100",
            "--max-ranking-files",
            str(max_ranking_files),
            "--output",
            repo_path(output) or str(output),
        ]
    )
    run_checked(
        [
            python_bin(),
            "scripts/verify_daily_research_quota.py",
            "--artifact",
            repo_path(output) or str(output),
            "--min-quota",
            str(quota),
            "--output",
            repo_path(verification_output) or str(verification_output),
        ]
    )
    return output, str(read_json(verification_output, {}).get("status") or "BLOCKED")


def build_research_brief(date_text: str) -> Path:
    run_checked([python_bin(), "scripts/build_strategy_archetype_evidence_map.py", "--date", date_text])
    run_checked([python_bin(), "scripts/build_research_decision_brief.py", "--run-date", date_text])
    return ARTIFACTS_DIR / "research_decisions" / f"research_decision_brief_{date_text}.json"


def decision_fingerprint(decision: dict[str, Any]) -> str:
    basis = {
        "id": decision.get("id"),
        "artifact_paths": decision.get("artifact_paths"),
        "metrics": decision.get("metrics"),
        "recommended_option": decision.get("recommended_option"),
    }
    return hashlib.sha256(json.dumps(basis, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:12]


def render_card_markdown(card_id: str, decision: dict[str, Any]) -> str:
    card = decision.get("pm_card") if isinstance(decision.get("pm_card"), dict) else {}
    title = str(card.get("topic_name") or decision.get("title") or card_id)
    evidence = card.get("evidence") if isinstance(card.get("evidence"), list) else []
    lines = [
        f"專案：{PROJECT_DOMAIN}｜台股 TOP10 研究審核",
        "",
        f"{card_id}｜{title}",
        "狀態：待決策",
        "",
        f"處理哪裡：{card.get('system_area') or 'TOP10 research harness'}",
        f"可能提升：{card.get('potential_improvement') or decision.get('recommended_option') or '集中研究資源到下一步驗證。'}",
        f"判斷點：{card.get('decision_point') or decision.get('why_decision_needed') or '是否核准進下一步研究。'}",
        f"下一步 harness：{card.get('next_harness') or decision.get('formal_agent') or 'research_worker'}",
        "",
        "素材/證據：",
    ]
    if evidence:
        for row in evidence[:5]:
            if isinstance(row, dict):
                lines.append(f"- {row.get('item')}: {row.get('relevance') or 'evidence'}")
    else:
        for path in list_value(decision.get("artifact_paths"))[:5]:
            lines.append(f"- {path}: 可追溯 artifact")
    lines.extend(
        [
            "",
            f"決策邊界：{card.get('decision_boundary') or '核准只代表進下一步研究；不代表 production promotion、交易或上線。'}",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def export_pm_review_cards(brief_path: Path, state: dict[str, Any], date_text: str, max_cards: int) -> tuple[Path | None, list[str]]:
    brief = read_json(brief_path, {})
    sent = {str(item) for item in state.get("sent_decision_ids", [])}
    decisions = [item for item in list_value(brief.get("decision_requests")) if isinstance(item, dict)]
    selected = []
    for decision in decisions:
        if not is_top10_stock_decision(decision):
            continue
        decision_id = str(decision.get("id") or "")
        fingerprint = decision_fingerprint(decision)
        key = f"{decision_id}::{fingerprint}"
        if not decision_id or key in sent:
            continue
        selected.append((key, decision))
        if len(selected) >= max_cards:
            break
    if not selected:
        return None, []

    stamp = datetime.now(ZoneInfo("Asia/Taipei")).strftime("%H%M%S")
    run_dir = ARTIFACTS_DIR / "pm_review_cards" / f"{date_text}-research-auto-{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    cards_payload = {
        "schema_version": "top10.pm_review_cards.v1",
        "project_domain": PROJECT_DOMAIN,
        "run_dir": repo_path(run_dir),
        "purpose": "TOP10 股票 research harness 自動產生的下一輪 PM 審核卡。",
        "cards": {},
    }
    sent_keys = []
    token = date_text.replace("-", "")[2:]
    for index, (key, decision) in enumerate(selected, start=1):
        card = decision.get("pm_card") if isinstance(decision.get("pm_card"), dict) else {}
        card_id = f"RH{token}-{stamp}-{index:02d}"
        title = str(card.get("topic_name") or decision.get("title") or card_id)
        next_harness = str(card.get("next_harness") or decision.get("formal_agent") or "research_worker")
        cards_payload["cards"][card_id] = {
            "card_id": card_id,
            "project_domain": PROJECT_DOMAIN,
            "title": title,
            "owner": next_harness,
            "next_harness": next_harness,
            "source_decision_id": decision.get("id"),
        }
        (run_dir / f"{card_id}.md").write_text(render_card_markdown(card_id, decision), encoding="utf-8")
        sent_keys.append(key)
    (run_dir / "cards.json").write_text(
        json.dumps(cards_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return run_dir, sent_keys


def is_top10_stock_decision(decision: dict[str, Any]) -> bool:
    """Discord 送出前的最後 domain guard，避免混入其他專案任務卡。"""
    decision_id = str(decision.get("id") or "")
    allowed_prefixes = (
        "external-review-",
        "performance-review-",
        "research-queue-",
        "model-candidate-",
        "strategy-archetype-",
    )
    if not decision_id.startswith(allowed_prefixes):
        return False

    formal_agent = str(decision.get("formal_agent") or "")
    if formal_agent not in {"research_worker", "disagreement_next_actions"}:
        return False

    text = json.dumps(decision, ensure_ascii=False).lower()
    blocked_terms = [
        "ai vibe radar",
        "ai-vibe-radar",
        "ai-core",
        "skill-intake",
        "skill 系統",
        "agent 工作流",
        "browsermcp",
        "chrome-devtools-mcp-flow",
        "frontend-design-gate",
        "global-memory-system",
        "gemini-researcher",
        "gpt-escalation-reviewer",
    ]
    if any(term in text for term in blocked_terms):
        return False

    allowed_artifact_prefixes = (
        "artifacts/autonomous_research/",
        "artifacts/backtest/",
        "artifacts/daily_performance_review_",
        "artifacts/external_review/",
        "artifacts/model_experiments/",
        "artifacts/research_map/",
        "artifacts/research_council/",
        "local_artifact/",
    )
    artifact_paths = [str(path) for path in list_value(decision.get("artifact_paths")) if path]
    if artifact_paths and not any(path.startswith(allowed_artifact_prefixes) for path in artifact_paths):
        return False

    return True


def gateway_defaults(config: dict[str, Any]) -> tuple[str, str, str]:
    notify = config.get("notify") if isinstance(config.get("notify"), dict) else {}
    node_bin = str(notify.get("clawd_cli_node") or "/opt/homebrew/opt/node/bin/node")
    openclaw_entry = str(Path.home() / "new clawd" / "openclaw.mjs")
    target = str(notify.get("review_approval_clawd_to") or notify.get("ops_clawd_to") or "channel:1519179377336651796")
    return node_bin, openclaw_entry, target


def send_pm_cards(
    *,
    run_dir: Path,
    config: dict[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any]:
    node_default, entry_default, target_default = gateway_defaults(config)
    node_bin = args.node_bin or node_default
    openclaw_entry = args.openclaw_entry or entry_default
    target = args.target or target_default
    params = {
        "run_dir": repo_path(run_dir),
        "target": target,
        "dry_run": bool(args.dry_run_send),
    }
    command = [
        node_bin,
        openclaw_entry,
        "gateway",
        "call",
        "top10.pm_review.send_cards",
        "--json",
        "--timeout",
        "15000",
        "--params",
        json.dumps(params, ensure_ascii=False),
    ]
    completed = subprocess.run(command, cwd=PROJECT_ROOT, text=True, capture_output=True)
    return {
        "command": [*command[:9], "<params>"],
        "exit_code": completed.returncode,
        "stdout": completed.stdout[-8000:],
        "stderr": completed.stderr[-4000:],
        "status": "OK" if completed.returncode == 0 else "FAILED",
    }


def main() -> int:
    args = parse_args()
    config = read_config(resolve_path(args.config))
    date_text = args.date or local_date(config)
    state_path = resolve_path(args.state)
    state = load_state(state_path)
    started_at = datetime.now(timezone.utc).isoformat()
    status_path = resolve_path(args.output) if args.output else STATE_DIR / f"pm_research_harness_loop_{date_text}.json"

    run_dirs = discover_pm_run_dirs(args)
    pending_approvals, queue_paths = collect_pending_approvals(run_dirs, state, date_text)
    if pending_approvals:
        state["loop_enabled"] = True
        state["consecutive_empty_runs"] = 0
        state["consecutive_no_approval_runs"] = 0

    research_artifact = None
    brief_path = None
    card_run_dir = None
    send_result: dict[str, Any] | None = None
    sent_keys: list[str] = []
    topic_runs = 0
    research_quota_state: str | None = None
    queue_depth_before = current_queue_depth()
    discovery_artifact = None
    queue_top_up_count = 0
    queue_top_up_after_run_count = 0
    queue_depth_after_discovery = queue_depth_before
    queue_depth_after_run = queue_depth_after_discovery

    if state["loop_enabled"] and queue_depth_before < args.min_queue_depth:
        discovery_artifact = discover_research_topics(date_text, args.discovery_max_topics, args.max_ranking_files)
        queue_top_up_count = top_up_research_queue_from_registry(args.min_queue_depth, args.discovery_max_topics)
        queue_depth_after_discovery = current_queue_depth()
        queue_depth_after_run = queue_depth_after_discovery

    if state["loop_enabled"]:
        research_artifact, research_quota_state = run_research(date_text, args.quota, args.max_ranking_files)
        research_payload = read_json(research_artifact, {})
        topic_runs = len(list_value(research_payload.get("topic_runs")))
        if topic_runs == 0:
            state["consecutive_empty_runs"] = int(state.get("consecutive_empty_runs") or 0) + 1
        else:
            state["consecutive_empty_runs"] = 0
            if pending_approvals:
                state["consecutive_no_approval_runs"] = 0
            else:
                state["consecutive_no_approval_runs"] = int(state.get("consecutive_no_approval_runs") or 0) + 1
        if research_quota_state == "PARTIAL_NO_MORE_WORK":
            state["loop_enabled"] = False
        if state["consecutive_empty_runs"] >= 2:
            state["loop_enabled"] = False
        if not pending_approvals and state["consecutive_no_approval_runs"] >= max(args.max_continuation_runs, 0):
            state["loop_enabled"] = False
        queue_depth_after_run = current_queue_depth()
        if state["loop_enabled"] and queue_depth_after_run < args.min_queue_depth:
            queue_top_up_after_run_count = top_up_research_queue_from_registry(args.min_queue_depth, args.discovery_max_topics)
            queue_depth_after_run = current_queue_depth()

    if pending_approvals or topic_runs > 0:
        brief_path = build_research_brief(date_text)
        card_run_dir, sent_keys = export_pm_review_cards(brief_path, state, date_text, args.max_review_cards)
        if card_run_dir and args.send_cards:
            send_result = send_pm_cards(run_dir=card_run_dir, config=config, args=args)
            if send_result["status"] != "OK":
                raise RuntimeError(f"failed to send PM review cards: {send_result['stderr'] or send_result['stdout']}")

    effective_send = bool(args.send_cards and send_result and send_result.get("status") == "OK" and not args.dry_run_send)
    consumed = {str(item) for item in state.get("consumed_approvals", [])}
    for item in pending_approvals:
        consumed.add(approval_key(item))
    state["consumed_approvals"] = sorted(consumed)
    if sent_keys and effective_send:
        sent = {str(item) for item in state.get("sent_decision_ids", [])}
        sent.update(sent_keys)
        state["sent_decision_ids"] = sorted(sent)

    run_record = {
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "date": date_text,
        "pending_approval_count": len(pending_approvals),
        "loop_enabled_after": state["loop_enabled"],
        "topic_runs": topic_runs,
        "research_quota_state": research_quota_state,
        "research_artifact": repo_path(research_artifact) if research_artifact else None,
        "topic_discovery_artifact": repo_path(discovery_artifact) if discovery_artifact else None,
        "queue_top_up_count": queue_top_up_count,
        "queue_top_up_after_run_count": queue_top_up_after_run_count,
        "brief": repo_path(brief_path) if brief_path else None,
        "pm_review_run_dir": repo_path(card_run_dir) if card_run_dir else None,
        "send_status": "DRY_RUN" if args.dry_run_send and send_result else send_result.get("status") if send_result else "NOT_SENT",
    }
    state["runs"] = [*list_value(state.get("runs")), run_record][-100:]
    write_state(state_path, state)

    status = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK",
        "date": date_text,
        "state": repo_path(state_path),
        "queue_paths": [repo_path(Path(path)) for path in queue_paths],
        "pending_approval_count": len(pending_approvals),
        "topic_runs": topic_runs,
        "research_quota_state": research_quota_state,
        "research_artifact": repo_path(research_artifact) if research_artifact else None,
        "topic_discovery_artifact": repo_path(discovery_artifact) if discovery_artifact else None,
        "research_decision_brief": repo_path(brief_path) if brief_path else None,
        "pm_review_run_dir": repo_path(card_run_dir) if card_run_dir else None,
        "pm_review_cards_sent": effective_send,
        "pm_review_cards_dry_run": bool(args.dry_run_send and send_result and send_result.get("status") == "OK"),
        "send_result": send_result,
        "loop_enabled_after": state["loop_enabled"],
        "consecutive_empty_runs": state["consecutive_empty_runs"],
        "consecutive_no_approval_runs": state["consecutive_no_approval_runs"],
        "max_continuation_runs": args.max_continuation_runs,
        "queue_depth_before": queue_depth_before,
        "queue_depth_after_discovery": queue_depth_after_discovery,
        "queue_depth_after_run": queue_depth_after_run,
        "queue_top_up_count": queue_top_up_count,
        "queue_top_up_after_run_count": queue_top_up_after_run_count,
        "min_queue_depth": args.min_queue_depth,
        "discovery_max_topics": args.discovery_max_topics,
        "contract": {
            "research_only": True,
            "requires_explicit_pm_approval": True,
            "launchd_explicitly_enables_research": True,
            "dry_run_send_does_not_skip_state_update": True,
            "max_no_approval_continuation_runs": args.max_continuation_runs,
            "auto_discovers_topics_when_queue_low": True,
            "revisits_rejected_topics_when_queue_low": True,
            "changes_ranking": False,
            "changes_model": False,
            "changes_publish": False,
            "discord_review_cards_only": True,
        },
    }
    write_state(status_path, status)
    print(json.dumps({key: status[key] for key in ["status", "topic_runs", "pm_review_run_dir", "pm_review_cards_sent", "loop_enabled_after"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
