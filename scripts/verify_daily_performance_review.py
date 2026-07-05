#!/usr/bin/env python3
"""驗證每日報牌績效復盤評論 artifact 邊界。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
SCHEMA_VERSION = "daily-performance-review.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify daily performance review")
    parser.add_argument("--artifact", default=None)
    parser.add_argument("--date", default=None)
    parser.add_argument("--output", default="artifacts/daily_performance_review_verification_latest.json")
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def artifact_path(args: argparse.Namespace) -> Path | None:
    if args.artifact:
        return resolve_path(args.artifact)
    if args.date:
        return ARTIFACTS_DIR / f"daily_performance_review_{args.date}.json"
    files = sorted(ARTIFACTS_DIR.glob("daily_performance_review_????-??-??.json"))
    return files[-1] if files else None


def main() -> int:
    args = parse_args()
    artifact = artifact_path(args)
    payload = read_json(artifact)
    contract = payload.get("contract") or {}
    summary = payload.get("summary") or {}
    checks = {
        "artifact_exists": bool(payload),
        "schema_ok": payload.get("schema_version") == SCHEMA_VERSION,
        "status_known": payload.get("status") in {"OK", "WATCH", "NEEDS_REVIEW"},
        "review_only": contract.get("review_commentary_only") is True,
        "reads_inputs": contract.get("reads_daily_performance") is True and contract.get("reads_decision_quality") is True,
        "no_ranking_change": contract.get("changes_production_ranking") is False,
        "no_model_change": contract.get("changes_model") is False,
        "no_message_change": contract.get("changes_clawd_message") is False,
        "research_candidates_only": contract.get("creates_research_candidates_only") is True,
        "no_live_send": contract.get("live_send") is False,
        "summary_present": bool(summary.get("operator_summary")),
        "findings_list": isinstance(payload.get("findings"), list),
        "research_cards_list": isinstance(payload.get("research_cards"), list),
    }
    failed = [key for key, value in checks.items() if not value]
    output = resolve_path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "schema_version": "daily-performance-review-verification.v1",
                "status": "OK" if not failed else "FAILED",
                "artifact": repo_path(artifact),
                "checks": checks,
                "failed": failed,
                "summary": {
                    "review_status": payload.get("status"),
                    "finding_count": summary.get("finding_count"),
                    "research_card_count": summary.get("research_card_count"),
                },
            },
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "OK" if not failed else "FAILED", "output": repo_path(output), "failed": failed}, ensure_ascii=False))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
