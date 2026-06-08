#!/usr/bin/env python3
"""驗證近 7 日 Top10 watchlist 風險提醒 artifact 的邊界。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACT_DIR = PROJECT_ROOT / "artifacts" / "model_experiments"
SCHEMA_VERSION = "recent-top10-watchlist-warning.v1"
ALLOWED_LEVELS = {"WATCH", "WEAKENING", "RISK_ALERT"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify recent Top10 watchlist warning artifact")
    parser.add_argument("--artifact", default=None, help="artifact JSON；未指定時使用最新 recent_top10_watchlist_warning_*.json")
    parser.add_argument("--min-items", type=int, default=10, help="最少 watchlist 股票數")
    parser.add_argument("--expected-days", type=int, default=7, help="預期 ranking window 天數")
    return parser.parse_args()


def resolve_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def latest_artifact() -> Path:
    matches = sorted(DEFAULT_ARTIFACT_DIR.glob("recent_top10_watchlist_warning_????-??-??.json"))
    if not matches:
        raise FileNotFoundError("找不到 recent_top10_watchlist_warning_YYYY-MM-DD.json")
    return matches[-1]


def fail(message: str, checks: list[dict[str, Any]]) -> int:
    print(json.dumps({"status": "FAILED", "message": message, "checks": checks}, ensure_ascii=False, indent=2))
    return 1


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, value: Any = None) -> None:
    checks.append({"name": name, "ok": bool(ok), "value": value})


def item_text(item: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("conclusion", "holder_note"):
        value = item.get(key)
        if value is not None:
            parts.append(str(value))
    parts.extend(str(note) for note in item.get("plain_notes") or [])
    return "\n".join(parts)


def main() -> int:
    args = parse_args()
    artifact_path = resolve_path(args.artifact) if args.artifact else latest_artifact()
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    checks: list[dict[str, Any]] = []

    add_check(checks, "schema_version", payload.get("schema_version") == SCHEMA_VERSION, payload.get("schema_version"))
    add_check(checks, "watchlist_days", payload.get("watchlist_ranking_days") == args.expected_days, payload.get("watchlist_ranking_days"))

    contract = payload.get("contract") or {}
    for key in (
        "research_only",
        "no_personal_holdings",
        "non_personal_warning_only",
        "does_not_send_push",
        "does_not_change_ranking",
        "does_not_change_model",
    ):
        add_check(checks, f"contract.{key}", contract.get(key) is True, contract.get(key))
    add_check(checks, "contract.uses_future_rankings", contract.get("uses_future_rankings") is False, contract.get("uses_future_rankings"))

    items = payload.get("items") or []
    add_check(checks, "items_count", len(items) >= args.min_items, len(items))
    levels = {item.get("warning_level") for item in items}
    add_check(checks, "warning_levels_allowed", levels <= ALLOWED_LEVELS, sorted(levels))

    blocked_terms = tuple(contract.get("blocked_message_terms") or [])
    blocked_hits: list[dict[str, str]] = []
    for item in items:
        text = item_text(item)
        for term in blocked_terms:
            if term and term in text:
                blocked_hits.append({"stock_id": str(item.get("stock_id")), "term": term})
    add_check(checks, "message_has_no_direct_trade_terms", not blocked_hits, blocked_hits[:10])

    malformed_items = [
        item.get("stock_id")
        for item in items
        if not item.get("stock_id")
        or not item.get("conclusion")
        or not isinstance(item.get("plain_notes"), list)
        or "latest_in_top10" not in item
        or "days_seen_in_window" not in item
    ]
    add_check(checks, "items_shape", not malformed_items, malformed_items[:10])

    source_files = ((payload.get("source_artifacts") or {}).get("ranking_files") or [])
    add_check(checks, "source_ranking_files", len(source_files) == args.expected_days, source_files)

    failed = [check for check in checks if not check["ok"]]
    if failed:
        return fail("recent top10 watchlist warning verification failed", checks)

    print(
        json.dumps(
            {
                "status": "OK",
                "artifact": str(artifact_path),
                "items": len(items),
                "levels": sorted(levels),
                "checks": checks,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
