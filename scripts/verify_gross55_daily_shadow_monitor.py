#!/usr/bin/env python3
"""驗證 gross55 每日 shadow monitor 邊界。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_MODEL_SHA256 = "76f530f6491f996f4838500acacbde40a10c90f43116cec0dcc69fb6b4935675"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify gross55 daily shadow monitor")
    parser.add_argument("--artifact", default="artifacts/model_experiments/gross55_daily_shadow_monitor_2026-06-02.json")
    parser.add_argument("--expected-model-sha256", default=EXPECTED_MODEL_SHA256)
    parser.add_argument("--output", default="artifacts/model_experiments/gross55_daily_shadow_monitor_verification_latest.json")
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def model_sha256() -> str:
    digest = hashlib.sha256()
    with (PROJECT_ROOT / "models" / "latest_lgbm.pkl").open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def n(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def main() -> int:
    args = parse_args()
    artifact = resolve_path(args.artifact)
    payload = read_json(artifact)
    contract = payload.get("contract") or {}
    summary = payload.get("summary") or {}
    allocation = payload.get("latest_allocation_shadow") or {}
    allowed_statuses = {"MONITOR_WOULD_REDUCE_TODAY_EXPOSURE", "MONITOR_NO_ENTRY_CHANGE_TODAY"}
    checks = {
        "artifact_exists": bool(payload),
        "status_ok": payload.get("status") == "OK",
        "monitor_status_allowed": payload.get("monitor_status") in allowed_statuses,
        "shadow_only": contract.get("operational_shadow_only") is True,
        "default_not_allowed": contract.get("default_allowed") is False,
        "no_top10_change": contract.get("changes_top10_membership") is False and allocation.get("same_top10") is True,
        "no_score_change": contract.get("changes_risk_adjusted_score") is False,
        "no_ranking_change": contract.get("changes_production_ranking") is False,
        "no_message_change": contract.get("changes_clawd_message") is False,
        "no_model_change": contract.get("changes_model") is False and model_sha256() == args.expected_model_sha256,
        "ranking_exists": allocation.get("exists") is True,
        "gross55_not_above_production": n(summary.get("gross55_shadow_target_gross")) <= n(summary.get("production_target_gross")),
    }
    failed = [key for key, value in checks.items() if not value]
    output = resolve_path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "schema_version": "gross55-daily-shadow-monitor-verification.v1",
                "status": "OK" if not failed else "FAILED",
                "artifact": repo_path(artifact),
                "checks": checks,
                "failed": failed,
            },
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"status": "OK" if not failed else "FAILED", "output": repo_path(output), "failed": failed}, ensure_ascii=False))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
