#!/usr/bin/env python3
"""驗證每日報牌後驗績效 ledger 的 read-only 與可監控契約。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
SCHEMA_VERSION = "daily-recommendation-performance.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify daily recommendation performance ledger")
    parser.add_argument("--artifact", default=None)
    parser.add_argument("--date", default=None)
    parser.add_argument("--output", default="artifacts/daily_recommendation_performance_verification_latest.json")
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


def latest_artifact() -> Path | None:
    files = sorted(ARTIFACTS_DIR.glob("daily_recommendation_performance_????-??-??.json"))
    return files[-1] if files else None


def artifact_path(args: argparse.Namespace) -> Path | None:
    if args.artifact:
        return resolve_path(args.artifact)
    if args.date:
        return ARTIFACTS_DIR / f"daily_recommendation_performance_{args.date}.json"
    return latest_artifact()


def main() -> int:
    args = parse_args()
    artifact = artifact_path(args)
    payload = read_json(artifact)
    contract = payload.get("contract") or {}
    summary = payload.get("summary") or {}
    inputs = payload.get("inputs") or {}
    horizons = {str(value) for value in inputs.get("horizons", [])}
    total_rows = int(summary.get("trade_count") or 0) + int(summary.get("pending_count") or 0) + int(summary.get("skipped_count") or 0)
    checks = {
        "artifact_exists": bool(payload),
        "schema_ok": payload.get("schema_version") == SCHEMA_VERSION,
        "status_ok": payload.get("status") == "OK",
        "review_only": contract.get("performance_review_only") is True,
        "reads_existing_inputs": contract.get("reads_existing_ranking_artifacts") is True
        and contract.get("reads_existing_features_ohlc") is True,
        "no_ranking_change": contract.get("changes_production_ranking") is False,
        "no_score_change": contract.get("changes_risk_adjusted_score") is False,
        "no_model_change": contract.get("changes_model") is False,
        "no_message_change": contract.get("changes_clawd_message") is False,
        "no_live_send": contract.get("live_send") is False,
        "not_promotion_ready": contract.get("promotion_ready") is False,
        "expected_horizons": {"1", "3", "5", "10"}.issubset(horizons),
        "has_monitorable_rows": total_rows > 0,
        "ranking_files_declared": bool(inputs.get("ranking_files")),
    }
    failed = [key for key, value in checks.items() if not value]
    output = resolve_path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "schema_version": "daily-recommendation-performance-verification.v1",
                "status": "OK" if not failed else "FAILED",
                "artifact": repo_path(artifact),
                "checks": checks,
                "failed": failed,
                "summary": {
                    "as_of_date": payload.get("as_of_date"),
                    "trade_count": summary.get("trade_count"),
                    "pending_count": summary.get("pending_count"),
                    "skipped_count": summary.get("skipped_count"),
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
