#!/usr/bin/env python3
"""驗證 5913 combo effectiveness review artifact。

只檢查研究 review 產物與 production 邊界，不判斷策略是否可上線。
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "research_reviews"
SCHEMA_VERSION = "5913-combo-effectiveness-review-verification.v1"
REVIEW_SCHEMA = "5913-combo-effectiveness-review.v1"
REQUIRED_KEYS = {
    "status",
    "review_date",
    "input_total_combos",
    "input_processed_combos",
    "classification_counts",
    "top_candidates",
    "next_replay_queue",
    "do_not_promote",
    "production_impact",
    "errors",
}
REQUIRED_CLASSIFICATIONS = {
    "KEEP_FOR_NEXT_REPLAY",
    "MONITOR_ONLY",
    "LOW_INFORMATION",
    "REJECTED_OR_DO_NOT_PROMOTE",
}
FORBIDDEN_CHANGED_PREFIXES = (
    "models/latest_lgbm.pkl",
    "artifacts/backtest/historical_rankings_current_model/",
    "artifacts/production/",
    "artifacts/clawd/",
    "data/production/",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify 5913 combo effectiveness review")
    parser.add_argument("--date", required=True)
    parser.add_argument("--json", default=None)
    parser.add_argument("--markdown", default=None)
    parser.add_argument("--output", default=str(OUTPUT_DIR / "5913_combo_effectiveness_review_verification_latest.json"))
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


def git_changed_paths() -> list[str]:
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return []
    paths: list[str] = []
    for line in result.stdout.splitlines():
        text = line[3:].strip()
        if " -> " in text:
            text = text.split(" -> ", 1)[1].strip()
        if text:
            paths.append(text)
    return paths


def build_payload(date: str, json_path: Path, md_path: Path) -> dict[str, Any]:
    review = read_json(json_path) if json_path.exists() else {}
    md_text = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
    classification_counts = review.get("classification_counts") if isinstance(review.get("classification_counts"), dict) else {}
    total_classified = sum(value for value in classification_counts.values() if isinstance(value, int))
    changed_paths = git_changed_paths()
    forbidden_changed = [
        path
        for path in changed_paths
        if any(path == prefix or path.startswith(prefix) for prefix in FORBIDDEN_CHANGED_PREFIXES)
    ]
    generated = review.get("generated_artifacts") if isinstance(review.get("generated_artifacts"), dict) else {}
    checks = [
        {"name": "review_json_exists", "ok": json_path.exists(), "value": repo_path(json_path)},
        {"name": "review_markdown_exists", "ok": md_path.exists(), "value": repo_path(md_path)},
        {"name": "schema", "ok": review.get("schema_version") == REVIEW_SCHEMA, "value": review.get("schema_version")},
        {"name": "required_keys", "ok": REQUIRED_KEYS.issubset(review.keys()), "value": sorted(set(review.keys()) & REQUIRED_KEYS)},
        {"name": "status_ok", "ok": review.get("status") == "OK", "value": review.get("status")},
        {"name": "review_date", "ok": review.get("review_date") == date, "value": review.get("review_date")},
        {"name": "input_total_combos", "ok": review.get("input_total_combos") == 5913, "value": review.get("input_total_combos")},
        {"name": "input_processed_combos", "ok": review.get("input_processed_combos") == 5913, "value": review.get("input_processed_combos")},
        {
            "name": "classification_keys",
            "ok": REQUIRED_CLASSIFICATIONS.issubset(classification_counts.keys()),
            "value": sorted(classification_counts.keys()),
        },
        {
            "name": "classification_counts_align_total",
            "ok": total_classified == review.get("input_processed_combos") == 5913,
            "value": {"total_classified": total_classified, "input_processed_combos": review.get("input_processed_combos")},
        },
        {
            "name": "raw_counts_align_card",
            "ok": review.get("raw_insight_counts") == {
                "effective": 642,
                "follow_up_signal": 563,
                "rejected": 4382,
                "low_information": 326,
            },
            "value": review.get("raw_insight_counts"),
        },
        {
            "name": "replay_queue_present",
            "ok": isinstance(review.get("next_replay_queue"), list) and len(review.get("next_replay_queue")) > 0,
            "value": len(review.get("next_replay_queue") or []),
        },
        {
            "name": "top_candidates_present",
            "ok": isinstance(review.get("top_candidates"), list) and len(review.get("top_candidates")) > 0,
            "value": len(review.get("top_candidates") or []),
        },
        {
            "name": "do_not_promote_present",
            "ok": isinstance(review.get("do_not_promote"), list) and len(review.get("do_not_promote")) > 0,
            "value": len(review.get("do_not_promote") or []),
        },
        {
            "name": "production_impact_no_change",
            "ok": review.get("production_impact") == "NO_PRODUCTION_CHANGE",
            "value": review.get("production_impact"),
        },
        {
            "name": "report_contains_required_sections",
            "ok": all(
                section in md_text
                for section in [
                    "Executive Summary",
                    "Top Useful Findings",
                    "Rejected / Misleading Findings",
                    "Next Replay Queue",
                    "Strategy Component Candidates",
                    "Production Impact",
                    "Open Risks",
                ]
            ),
            "value": "markdown_sections",
        },
        {
            "name": "report_avoids_promotion_ready_token",
            "ok": "PROMOTION_READY" not in md_text,
            "value": "PROMOTION_READY" in md_text,
        },
        {
            "name": "generated_artifacts_limited_to_review",
            "ok": set(generated.values()) == {
                f"artifacts/research_reviews/5913_combo_effectiveness_review_{date}.json",
                f"artifacts/research_reviews/5913_combo_effectiveness_review_{date}.md",
            },
            "value": generated,
        },
        {
            "name": "no_forbidden_production_artifact_changed",
            "ok": not forbidden_changed,
            "value": forbidden_changed,
        },
    ]
    failed = [check for check in checks if not check["ok"]]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK" if not failed else "FAILED",
        "date": date,
        "artifact": {
            "json": repo_path(json_path),
            "markdown": repo_path(md_path),
        },
        "summary": {
            "check_count": len(checks),
            "failed_count": len(failed),
        },
        "checks": checks,
        "errors": failed,
    }


def main() -> int:
    args = parse_args()
    json_path = resolve_path(args.json) or OUTPUT_DIR / f"5913_combo_effectiveness_review_{args.date}.json"
    md_path = resolve_path(args.markdown) or OUTPUT_DIR / f"5913_combo_effectiveness_review_{args.date}.md"
    output_path = resolve_path(args.output) or OUTPUT_DIR / "5913_combo_effectiveness_review_verification_latest.json"
    payload = build_payload(args.date, json_path, md_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "failed_count": payload["summary"]["failed_count"], "output": repo_path(output_path)}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
