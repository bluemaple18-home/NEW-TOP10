#!/usr/bin/env python3
"""驗證 weekend unsupported unlock audit。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build_weekend_unsupported_unlock_audit import SCHEMA_VERSION, audit_paths
from weekend_training_common import PRODUCTION_IMPACT, UNSUPPORTED_CATEGORIES, repo_path, resolve_path, rollup_paths, write_json


VERIFY_SCHEMA_VERSION = "weekend-unsupported-unlock-audit-verification.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify weekend unsupported unlock audit")
    parser.add_argument("--date", required=True)
    parser.add_argument("--artifact", default=None)
    parser.add_argument("--output", default="artifacts/weekend_training/weekend_unsupported_unlock_audit_verification_latest.json")
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_payload(date: str, artifact: Path) -> dict[str, Any]:
    payload = read_json(artifact)
    rollup_path, _ = rollup_paths(date)
    rollup = read_json(rollup_path)
    rollup_summary = rollup.get("summary") if isinstance(rollup.get("summary"), dict) else {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    categories = payload.get("categories") if isinstance(payload.get("categories"), list) else []
    category_counts = rollup_summary.get("unsupported_category_counts") if isinstance(rollup_summary.get("unsupported_category_counts"), dict) else {}
    category_total = sum(int(item.get("count") or 0) for item in categories if isinstance(item, dict))
    category_names = [str(item.get("category")) for item in categories if isinstance(item, dict)]
    missing_decisions = [
        item.get("category")
        for item in categories
        if not isinstance(item, dict) or not item.get("unlock_decision") or not item.get("next_action")
    ]
    unknown_categories = sorted(name for name in category_names if name not in UNSUPPORTED_CATEGORIES)
    checks = [
        {"name": "artifact_exists", "ok": artifact.exists(), "value": repo_path(artifact)},
        {"name": "schema", "ok": payload.get("schema_version") == SCHEMA_VERSION, "value": payload.get("schema_version")},
        {"name": "status_ok", "ok": payload.get("status") == "OK", "value": payload.get("status")},
        {
            "name": "unsupported_count_matches_rollup",
            "ok": int(summary.get("unsupported_count") or 0) == int(rollup_summary.get("unsupported_count") or 0),
            "value": {"audit": summary.get("unsupported_count"), "rollup": rollup_summary.get("unsupported_count")},
        },
        {
            "name": "category_total_matches_unsupported_count",
            "ok": category_total == int(summary.get("unsupported_count") or 0),
            "value": {"category_total": category_total, "unsupported_count": summary.get("unsupported_count")},
        },
        {
            "name": "category_names_match_rollup",
            "ok": sorted(category_names) == sorted(str(key) for key in category_counts),
            "value": {"audit": sorted(category_names), "rollup": sorted(str(key) for key in category_counts)},
        },
        {"name": "categories_known", "ok": not unknown_categories, "value": unknown_categories},
        {"name": "all_categories_have_decision", "ok": not missing_decisions, "value": missing_decisions},
        {"name": "production_impact", "ok": payload.get("production_impact") == PRODUCTION_IMPACT, "value": payload.get("production_impact")},
        {"name": "no_promotion_ready", "ok": "PROMOTION_READY" not in json.dumps(payload, ensure_ascii=False), "value": False},
    ]
    failed = [check for check in checks if not check["ok"]]
    return {
        "schema_version": VERIFY_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": date,
        "status": "OK" if not failed else "FAILED",
        "artifact": repo_path(artifact),
        "summary": {"check_count": len(checks), "failed_count": len(failed)},
        "checks": checks,
        "errors": failed,
    }


def main() -> int:
    args = parse_args()
    default_artifact, _ = audit_paths(args.date)
    artifact = resolve_path(args.artifact) or default_artifact
    output = resolve_path(args.output)
    payload = build_payload(args.date, artifact)
    write_json(output, payload)
    print(json.dumps({"status": payload["status"], "failed_count": payload["summary"]["failed_count"], "output": repo_path(output)}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
