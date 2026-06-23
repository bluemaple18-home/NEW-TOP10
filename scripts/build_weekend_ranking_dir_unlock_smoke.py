#!/usr/bin/env python3
"""檢查 ranking dir missing 是否能低風險解鎖。

這支只讀 inventory，抽樣/彙總缺的 ranking dir，不產生 ranking、不跑 replay。
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from weekend_training_common import PRODUCTION_IMPACT, inventory_paths, now_utc, repo_path, write_json, write_text


SCHEMA_VERSION = "weekend-ranking-dir-unlock-smoke.v1"
WEEKEND_DIR = Path(__file__).resolve().parents[1] / "artifacts" / "weekend_training"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build ranking dir unlock smoke")
    parser.add_argument("--date", required=True)
    parser.add_argument("--sample-size", type=int, default=20)
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def smoke_paths(date: str) -> tuple[Path, Path]:
    stem = f"weekend_ranking_dir_unlock_smoke_{date}"
    return WEEKEND_DIR / f"{stem}.json", WEEKEND_DIR / f"{stem}.md"


def missing_path_from_reason(reason: str) -> str | None:
    if ":" not in reason:
        return None
    prefix, value = reason.split(":", 1)
    if prefix not in {"MISSING_BASELINE_RANKINGS_DIR", "MISSING_CANDIDATE_RANKINGS_DIR"}:
        return None
    return value


def build_payload(date: str, sample_size: int) -> dict[str, Any]:
    inventory_path, _ = inventory_paths(date)
    inventory = read_json(inventory_path)
    records = inventory.get("records") if isinstance(inventory.get("records"), list) else []
    rows = [
        row
        for row in records
        if isinstance(row, dict)
        and row.get("burn_down_status") == "UNSUPPORTED_INPUT"
        and row.get("unsupported_category") == "UNSUPPORTED_RANKING_DIR_MISSING"
    ]
    by_reason = Counter(str(row.get("unsupported_reason") or "") for row in rows)
    by_candidate_dir = Counter(str(row.get("candidate_dir") or "") for row in rows)
    by_entry_filter = Counter(str((row.get("dimensions") or {}).get("entry_filter") or "") for row in rows)
    topic_counts: dict[str, int] = defaultdict(int)
    path_counts: Counter[str] = Counter()
    for row in rows:
        topic_counts[str(row.get("topic_id") or "")] += 1
        missing_path = missing_path_from_reason(str(row.get("unsupported_reason") or ""))
        if missing_path:
            path_counts[missing_path] += 1
    sample = []
    for row in rows[: max(sample_size, 0)]:
        sample.append(
            {
                "combo_id": row.get("combo_id"),
                "topic_id": row.get("topic_id"),
                "candidate_dir": row.get("candidate_dir"),
                "dimensions": row.get("dimensions"),
                "unsupported_reason": row.get("unsupported_reason"),
            }
        )
    can_expand_without_new_artifacts = False
    decision = "SMOKE_DONE_ARTIFACT_REQUIRED"
    reason = "缺的是 baseline/candidate ranking 目錄本身；目前只能定位缺口，不能把缺口自動視為可跑。"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now_utc(),
        "date": date,
        "status": "OK",
        "production_impact": PRODUCTION_IMPACT,
        "source": {"inventory": repo_path(inventory_path)},
        "summary": {
            "ranking_dir_missing_count": len(rows),
            "unique_missing_reasons": len(by_reason),
            "unique_missing_paths": len(path_counts),
            "unique_topics": len(topic_counts),
            "entry_filter_counts": dict(sorted(by_entry_filter.items())),
            "top_missing_reasons": dict(by_reason.most_common(10)),
            "top_missing_paths": dict(path_counts.most_common(10)),
            "top_candidate_dirs": dict(by_candidate_dir.most_common(10)),
            "can_expand_without_new_artifacts": can_expand_without_new_artifacts,
            "decision": decision,
            "reason": reason,
            "next_action": "補一張 ranking artifact source audit：確認是否要產生 artifacts/backtest/production，或把 topic 指到既有 production baseline。",
        },
        "sample": sample,
        "contract": {
            "research_only": True,
            "does_not_execute_replay": True,
            "does_not_create_ranking_dirs": True,
            "does_not_change_production_ranking": True,
        },
        "errors": [],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Weekend Ranking Dir Unlock Smoke",
        "",
        f"- status: `{payload['status']}`",
        f"- ranking_dir_missing_count: `{summary['ranking_dir_missing_count']}`",
        f"- unique_missing_paths: `{summary['unique_missing_paths']}`",
        f"- unique_topics: `{summary['unique_topics']}`",
        f"- decision: `{summary['decision']}`",
        f"- can_expand_without_new_artifacts: `{summary['can_expand_without_new_artifacts']}`",
        f"- reason: {summary['reason']}",
        f"- next_action: {summary['next_action']}",
        "",
        "## Entry Filters",
        "",
    ]
    for key, value in summary["entry_filter_counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Top Missing Paths", ""])
    for key, value in summary["top_missing_paths"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "No production ranking, model, or Clawd changes.", ""])
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args.date, args.sample_size)
    json_path, md_path = smoke_paths(args.date)
    write_json(json_path, payload)
    write_text(md_path, render_markdown(payload))
    print(json.dumps({"status": payload["status"], "output": repo_path(json_path), "decision": payload["summary"]["decision"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
