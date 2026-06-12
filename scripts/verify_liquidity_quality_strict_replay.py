#!/usr/bin/env python3
"""驗證 liquidity quality strict replay review artifact。"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "research_reviews"
SCHEMA_VERSION = "liquidity-quality-strict-replay-verification.v1"
REVIEW_SCHEMA = "liquidity-quality-strict-replay.v1"
ALLOWED_DECISIONS = {
    "PROMOTE_TO_STRATEGY_COMPONENT_REPLAY",
    "KEEP_SHADOW_MONITOR",
    "REJECT_FOR_NOW",
    "INCONCLUSIVE_MORE_DATA_REQUIRED",
}
REQUIRED_KEYS = {
    "status",
    "review_date",
    "production_impact",
    "candidate_family",
    "input_review_artifact",
    "comparable_window",
    "baseline",
    "candidate",
    "same_exit_comparison",
    "same_capital_comparison",
    "regime_slices",
    "failure_attribution",
    "decision",
    "next_action",
    "errors",
}
FORBIDDEN_CHANGED_PREFIXES = (
    "models/latest_lgbm.pkl",
    "artifacts/backtest/historical_rankings_current_model/",
    "artifacts/production/",
    "artifacts/clawd/",
    "data/production/",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify liquidity quality strict replay")
    parser.add_argument("--date", required=True)
    parser.add_argument("--json", default=None)
    parser.add_argument("--markdown", default=None)
    parser.add_argument("--output", default=str(OUTPUT_DIR / "liquidity_quality_strict_replay_verification_latest.json"))
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
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def changed_paths() -> tuple[list[str], dict[str, Any]]:
    command = ["git", "status", "--short"]
    try:
        result = subprocess.run(command, cwd=PROJECT_ROOT, check=False, capture_output=True, text=True)
    except OSError as exc:
        return [], {"command": command, "ok": False, "error": str(exc)}
    git_status = {
        "command": command,
        "ok": result.returncode == 0,
        "exit_code": result.returncode,
        "stderr": result.stderr.strip(),
    }
    if result.returncode != 0:
        return [], git_status
    paths: list[str] = []
    for line in result.stdout.splitlines():
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip()
        if path:
            paths.append(path)
    git_status["changed_count"] = len(paths)
    return paths, git_status


def has_metric(row: dict[str, Any], key: str) -> bool:
    return key in row and row.get(key) is not None


def has_risk_metrics(row: dict[str, Any]) -> bool:
    return all(has_metric(row, key) for key in ["return", "max_drawdown"]) and isinstance(row.get("turnover"), dict) and isinstance(row.get("concentration"), dict)


def build_payload(date: str, json_path: Path, md_path: Path) -> dict[str, Any]:
    review = read_json(json_path)
    md_text = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
    comparable = review.get("comparable_window") if isinstance(review.get("comparable_window"), dict) else {}
    failure = review.get("failure_attribution") if isinstance(review.get("failure_attribution"), dict) else {}
    primary_reasons = failure.get("primary_reasons") if isinstance(failure.get("primary_reasons"), list) else []
    success = failure.get("success_attribution") if isinstance(failure.get("success_attribution"), dict) else {}
    changed, git_status = changed_paths()
    forbidden = [path for path in changed if any(path == prefix or path.startswith(prefix) for prefix in FORBIDDEN_CHANGED_PREFIXES)]
    checks = [
        {"name": "json_exists", "ok": json_path.exists(), "value": repo_path(json_path)},
        {"name": "markdown_exists", "ok": md_path.exists(), "value": repo_path(md_path)},
        {"name": "schema", "ok": review.get("schema_version") == REVIEW_SCHEMA, "value": review.get("schema_version")},
        {"name": "required_keys", "ok": REQUIRED_KEYS.issubset(review.keys()), "value": sorted(set(review.keys()) & REQUIRED_KEYS)},
        {"name": "status_ok", "ok": review.get("status") == "OK", "value": review.get("status")},
        {"name": "review_date", "ok": review.get("review_date") == date, "value": review.get("review_date")},
        {"name": "production_impact", "ok": review.get("production_impact") == "NO_PRODUCTION_CHANGE", "value": review.get("production_impact")},
        {"name": "decision_allowed", "ok": review.get("decision") in ALLOWED_DECISIONS, "value": review.get("decision")},
        {"name": "failure_or_success_attribution_present", "ok": bool(primary_reasons) or bool(success), "value": {"primary_reasons": len(primary_reasons), "success": bool(success)}},
        {"name": "comparable_date_count_positive", "ok": int(comparable.get("comparable_date_count") or 0) > 0, "value": comparable.get("comparable_date_count")},
        {"name": "baseline_metrics", "ok": has_risk_metrics(review.get("baseline") or {}), "value": sorted(review.get("baseline", {}).keys()) if isinstance(review.get("baseline"), dict) else None},
        {"name": "candidate_metrics", "ok": has_risk_metrics(review.get("candidate") or {}), "value": sorted(review.get("candidate", {}).keys()) if isinstance(review.get("candidate"), dict) else None},
        {"name": "same_exit_present", "ok": isinstance(review.get("same_exit_comparison"), list) and len(review.get("same_exit_comparison")) > 0, "value": len(review.get("same_exit_comparison") or [])},
        {"name": "same_capital_present", "ok": isinstance(review.get("same_capital_comparison"), list) and len(review.get("same_capital_comparison")) > 0, "value": len(review.get("same_capital_comparison") or [])},
        {"name": "regime_slices_present", "ok": isinstance(review.get("regime_slices"), dict) and len(review.get("regime_slices")) > 0, "value": list((review.get("regime_slices") or {}).keys())},
        {"name": "report_sections_present", "ok": all(section in md_text for section in ["Executive Summary", "What Was Tested", "Headline Result", "Failure Attribution", "Regime Breakdown", "Risk Breakdown", "Next Action", "Production Impact"]), "value": "markdown_sections"},
        {"name": "report_avoids_promotion_ready_token", "ok": "PROMOTION_READY" not in md_text, "value": "PROMOTION_READY" in md_text},
        {"name": "git_status_available", "ok": git_status.get("ok") is True, "value": git_status},
        {"name": "no_forbidden_production_artifact_changed", "ok": git_status.get("ok") is True and not forbidden, "value": forbidden},
    ]
    failed = [check for check in checks if not check["ok"]]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK" if not failed else "FAILED",
        "date": date,
        "artifact": {"json": repo_path(json_path), "markdown": repo_path(md_path)},
        "summary": {"check_count": len(checks), "failed_count": len(failed)},
        "checks": checks,
        "errors": failed,
    }


def main() -> int:
    args = parse_args()
    json_path = resolve_path(args.json) or OUTPUT_DIR / f"liquidity_quality_strict_replay_{args.date}.json"
    md_path = resolve_path(args.markdown) or OUTPUT_DIR / f"liquidity_quality_strict_replay_{args.date}.md"
    output = resolve_path(args.output) or OUTPUT_DIR / "liquidity_quality_strict_replay_verification_latest.json"
    payload = build_payload(args.date, json_path, md_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "failed_count": payload["summary"]["failed_count"], "output": repo_path(output)}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
