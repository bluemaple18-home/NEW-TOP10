#!/usr/bin/env python3
"""驗證 PM approved work queue 只做下一步交接，不越過 production 邊界。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify PM approved work queue")
    parser.add_argument("--queue", required=True)
    parser.add_argument("--research-cards", required=True)
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            payload = json.loads(line)
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def is_repo_relative(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    return not value.startswith("/") and ".." not in Path(value).parts


def main() -> int:
    args = parse_args()
    queue_path = resolve_path(args.queue)
    research_cards_path = resolve_path(args.research_cards)
    queue = read_json(queue_path)
    cards = read_jsonl(research_cards_path)
    items = queue.get("items") if isinstance(queue.get("items"), list) else []
    research_items = [item for item in items if isinstance(item, dict) and item.get("route") == "research_worker"]

    checks = {
        "queue_schema": queue.get("schema_version") == "top10-pm-approved-work-queue.v1",
        "source_state_repo_relative": is_repo_relative(queue.get("source_state")),
        "all_items_approved": all(item.get("decision") == "approve" for item in items if isinstance(item, dict)),
        "all_items_queued": all(item.get("status") == "queued" for item in items if isinstance(item, dict)),
        "production_blocked": all(
            (item.get("contract") or {}).get("changes_ranking") is False
            and (item.get("contract") or {}).get("changes_model") is False
            and (item.get("contract") or {}).get("changes_publish") is False
            for item in items
            if isinstance(item, dict)
        ),
        "research_card_count_matches_route": len(cards) == len(research_items),
        "research_cards_have_required_fields": all(
            card.get("task_id")
            and card.get("hypothesis")
            and isinstance(card.get("input_refs"), list)
            and isinstance(card.get("blocked_conditions"), list)
            and (card.get("contract") or {}).get("research_only") is True
            for card in cards
        ),
    }
    ok = all(checks.values())
    result = {
        "status": "OK" if ok else "FAILED",
        "checks": checks,
        "queue": str(queue_path.relative_to(PROJECT_ROOT)) if queue_path.is_relative_to(PROJECT_ROOT) else str(queue_path),
        "research_cards": str(research_cards_path.relative_to(PROJECT_ROOT))
        if research_cards_path.is_relative_to(PROJECT_ROOT)
        else str(research_cards_path),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
