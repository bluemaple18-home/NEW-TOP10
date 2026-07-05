#!/usr/bin/env python3
"""把 PM 已核准卡轉成下一步 harness 可消化的工作佇列。

本腳本只讀 Discord PM decision artifacts，產生工作交接 artifact；
不執行研究、不改 ranking/model/publish。
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
SCHEMA_VERSION = "top10-pm-approved-work-queue.v1"
RESEARCH_CARD_SCHEMA_VERSION = "top10-research-card.v1"
PROJECT_DOMAIN = "TOP10_STOCK"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build PM approved work queue")
    parser.add_argument("--run-dir", required=True, help="repo-relative PM review card run dir")
    parser.add_argument("--date", default=datetime.now().date().isoformat())
    parser.add_argument("--output", default=None)
    parser.add_argument("--research-cards-output", default=None)
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


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def route_for_card(card: dict[str, Any]) -> str:
    harness = str(card.get("next_harness") or card.get("owner") or "")
    if harness == "research_worker":
        return "research_worker"
    if "daily-performance" in harness or "performance-review" in harness:
        return "daily_performance_review"
    if "card-state" in harness or "state-recorder" in harness:
        return "pm_card_state"
    return "manual_followup"


def approved_cards(state: dict[str, Any]) -> list[dict[str, Any]]:
    if state.get("project_domain") != PROJECT_DOMAIN:
        return []
    cards = state.get("cards") if isinstance(state.get("cards"), dict) else {}
    result = []
    for card_id, card in sorted(cards.items()):
        if not isinstance(card, dict) or card.get("decision") != "approve":
            continue
        if card.get("project_domain") != PROJECT_DOMAIN:
            continue
        result.append({"card_id": str(card_id), **card})
    return result


def build_work_item(card: dict[str, Any]) -> dict[str, Any]:
    route = route_for_card(card)
    return {
        "card_id": card["card_id"],
        "title": card.get("title") or card["card_id"],
        "route": route,
        "owner": card.get("owner"),
        "next_harness": card.get("next_harness"),
        "decision": "approve",
        "decided_at": card.get("decided_at"),
        "run_dir": card.get("run_dir"),
        "project_domain": PROJECT_DOMAIN,
        "status": "queued",
        "contract": {
            "approved_for_next_step_only": True,
            "changes_ranking": False,
            "changes_model": False,
            "changes_publish": False,
            "production_promotion_allowed": False,
        },
    }


def research_card_for_item(item: dict[str, Any], date_text: str) -> dict[str, Any]:
    return {
        "schema_version": RESEARCH_CARD_SCHEMA_VERSION,
        "task_id": f"PM-APPROVED-{date_text}-{item['card_id']}",
        "source_pm_card_id": item["card_id"],
        "project_domain": PROJECT_DOMAIN,
        "title": item["title"],
        "hypothesis": f"PM 已核准研究/複核主題：{item['title']}。先建立證據，不直接改 production。",
        "input_refs": [
            item["run_dir"],
            f"{item['run_dir']}/pm_decision_state.json",
            f"{item['run_dir']}/approved_work_queue.json",
        ],
        "blocked_conditions": [
            "缺少 PM approval state",
            "找不到可追溯 evidence artifact",
            "任務需要直接改 ranking/model/publish",
        ],
        "next_harness": item.get("next_harness") or "research_worker",
        "status": "queued",
        "contract": {
            "research_only": True,
            "production_promotion_allowed": False,
        },
    }


def build_payload(run_dir: Path, date_text: str) -> dict[str, Any]:
    state_path = run_dir / "pm_decision_state.json"
    state = read_json(state_path)
    if state.get("project_domain") != PROJECT_DOMAIN:
        return {
            "schema_version": SCHEMA_VERSION,
            "project_domain": PROJECT_DOMAIN,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "date": date_text,
            "run_dir": repo_path(run_dir),
            "source_state": repo_path(state_path),
            "status": "SKIPPED",
            "summary": {
                "approved_count": 0,
                "route_counts": {},
                "research_worker_count": 0,
                "skipped_reason": "project_domain mismatch or missing",
            },
            "items": [],
            "contract": {
                "reads_pm_decision_state": True,
                "queues_next_step_only": True,
                "requires_project_domain": PROJECT_DOMAIN,
                "changes_ranking": False,
                "changes_model": False,
                "changes_publish": False,
            },
        }
    items = [build_work_item(card) for card in approved_cards(state)]
    routes: dict[str, int] = {}
    for item in items:
        route = str(item["route"])
        routes[route] = routes.get(route, 0) + 1
    return {
        "schema_version": SCHEMA_VERSION,
        "project_domain": PROJECT_DOMAIN,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": date_text,
        "run_dir": repo_path(run_dir),
        "source_state": repo_path(state_path),
        "status": "READY" if items else "EMPTY",
        "summary": {
            "approved_count": len(items),
            "route_counts": routes,
            "research_worker_count": routes.get("research_worker", 0),
        },
        "items": items,
        "contract": {
            "reads_pm_decision_state": True,
            "queues_next_step_only": True,
            "requires_project_domain": PROJECT_DOMAIN,
            "changes_ranking": False,
            "changes_model": False,
            "changes_publish": False,
        },
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_research_cards(path: Path, payload: dict[str, Any], date_text: str) -> list[dict[str, Any]]:
    cards = [research_card_for_item(item, date_text) for item in payload["items"] if item.get("route") == "research_worker"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(card, ensure_ascii=False, sort_keys=True) + "\n" for card in cards), encoding="utf-8")
    return cards


def main() -> int:
    args = parse_args()
    run_dir = resolve_path(args.run_dir)
    output = resolve_path(args.output) if args.output else run_dir / "approved_work_queue.json"
    research_output = (
        resolve_path(args.research_cards_output)
        if args.research_cards_output
        else ARTIFACTS_DIR / "autonomous_research" / f"research_cards_{args.date}.jsonl"
    )
    payload = build_payload(run_dir, args.date)
    write_json(output, payload)
    research_cards = write_research_cards(research_output, payload, args.date)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "output": repo_path(output),
                "approved_count": payload["summary"]["approved_count"],
                "research_cards_output": repo_path(research_output),
                "research_card_count": len(research_cards),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
