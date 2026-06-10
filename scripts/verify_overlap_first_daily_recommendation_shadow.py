#!/usr/bin/env python3
"""驗證 overlap-first 每日推薦影子稿。"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "overlap-first-daily-recommendation-shadow-verification.v1"
REPORT_SCHEMA = "overlap-first-daily-recommendation-shadow.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify overlap-first daily recommendation shadow")
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--output", default="artifacts/model_experiments/overlap_first_daily_recommendation_shadow_verification_latest.json")
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
    return json.loads(path.read_text(encoding="utf-8"))


def read_ranking_ids(path: Path | None, top_n: int) -> list[str]:
    if path is None or not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [
            str(row.get("stock_id") or "").strip().replace(".0", "").zfill(4)
            for index, row in enumerate(csv.DictReader(handle), start=1)
            if index <= top_n and row.get("stock_id")
        ]


def stock_ids(rows: list[dict[str, Any]]) -> list[str]:
    return [str(row.get("stock_id") or "").zfill(4) for row in rows if row.get("stock_id")]


def no_duplicates(values: list[str]) -> bool:
    return len(values) == len(set(values))


def overlap_prefix_is_clean(rows: list[dict[str, Any]]) -> bool:
    seen_non_overlap = False
    for row in rows:
        bucket = row.get("selection_bucket")
        if bucket != "overlap_high_confidence":
            seen_non_overlap = True
        if seen_non_overlap and bucket == "overlap_high_confidence":
            return False
    return True


def bucket_order_is_clean(rows: list[dict[str, Any]]) -> bool:
    order = {
        "overlap_high_confidence": 0,
        "candidate_trail10_only": 1,
        "production_baseline_only": 2,
        "candidate_no_trail10_only": 3,
    }
    values = [order.get(str(row.get("selection_bucket")), 99) for row in rows]
    return values == sorted(values)


def rank_sequence(rows: list[dict[str, Any]]) -> bool:
    return [row.get("shadow_rank") for row in rows] == list(range(1, len(rows) + 1))


def build_payload(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    inputs = payload.get("inputs") if isinstance(payload.get("inputs"), dict) else {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    rows = payload.get("overlap_first_top10") if isinstance(payload.get("overlap_first_top10"), list) else []
    production_ranking = resolve_path(inputs.get("production_ranking"))
    candidate_monitor_path = resolve_path(inputs.get("candidate_monitor"))
    candidate_monitor = read_json(candidate_monitor_path) if candidate_monitor_path and candidate_monitor_path.exists() else {}
    candidate_rows = candidate_monitor.get("candidate_top10") if isinstance(candidate_monitor.get("candidate_top10"), list) else []
    top_n = int(inputs.get("top_n") or 10)
    allowed_ids = set()
    allowed_ids.update(stock_ids(candidate_rows))
    allowed_ids.update(read_ranking_ids(production_ranking, top_n))

    ids = stock_ids(rows)
    overlap_rows = [row for row in rows if row.get("selection_bucket") == "overlap_high_confidence"]
    checks = [
        {"name": "schema", "ok": payload.get("schema_version") == REPORT_SCHEMA, "value": payload.get("schema_version")},
        {"name": "status_ok", "ok": payload.get("status") == "OK", "value": payload.get("status")},
        {
            "name": "shadow_ready",
            "ok": payload.get("shadow_status") == "READY_FOR_SHADOW_RECOMMENDATION_REVIEW",
            "value": payload.get("shadow_status"),
        },
        {"name": "shadow_only", "ok": contract.get("shadow_only") is True and contract.get("overlap_first") is True, "value": contract},
        {
            "name": "no_production_changes",
            "ok": contract.get("changes_production_top10_membership") is False
            and contract.get("changes_risk_adjusted_score") is False
            and contract.get("changes_production_ranking") is False
            and contract.get("changes_clawd_message") is False
            and contract.get("changes_model") is False,
            "value": contract,
        },
        {
            "name": "no_direct_switch",
            "ok": contract.get("production_switch_ready") is False
            and contract.get("promotion_ready") is False
            and contract.get("default_allowed") is False,
            "value": contract,
        },
        {"name": "production_ranking_exists", "ok": production_ranking is not None and production_ranking.exists(), "value": repo_path(production_ranking)},
        {"name": "candidate_monitor_exists", "ok": candidate_monitor_path is not None and candidate_monitor_path.exists(), "value": repo_path(candidate_monitor_path)},
        {"name": "top10_count", "ok": len(rows) == top_n, "value": len(rows)},
        {"name": "rank_sequence", "ok": rank_sequence(rows), "value": [row.get("shadow_rank") for row in rows]},
        {"name": "no_duplicate_stocks", "ok": no_duplicates(ids), "value": ids},
        {"name": "overlap_prefix", "ok": overlap_prefix_is_clean(rows), "value": [row.get("selection_bucket") for row in rows]},
        {"name": "bucket_order", "ok": bucket_order_is_clean(rows), "value": [row.get("selection_bucket") for row in rows]},
        {
            "name": "overlap_summary_consistent",
            "ok": int(summary.get("overlap_count") or 0) == len(overlap_rows),
            "value": summary,
        },
        {
            "name": "union_only",
            "ok": set(ids).issubset(allowed_ids),
            "value": {"ids": ids, "allowed_count": len(allowed_ids)},
        },
        {
            "name": "candidate_items_have_trail_context",
            "ok": all(
                row.get("selection_bucket") != "candidate_trail10_only"
                or (row.get("candidate") and row.get("has_trail10_plan") is True)
                for row in rows
            ),
            "value": rows[:3],
        },
    ]
    failed = [check for check in checks if not check["ok"]]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK" if not failed else "FAILED",
        "artifact": repo_path(path),
        "summary": {
            "check_count": len(checks),
            "failed_count": len(failed),
            "overlap_count": summary.get("overlap_count"),
            "merged_count": summary.get("merged_count"),
        },
        "checks": checks,
    }


def main() -> int:
    args = parse_args()
    artifact = resolve_path(args.artifact)
    if artifact is None or not artifact.exists():
        raise FileNotFoundError(f"找不到 artifact：{args.artifact}")
    output = resolve_path(args.output)
    if output is None:
        raise RuntimeError("output resolution failed")
    payload = build_payload(artifact)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output)}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
