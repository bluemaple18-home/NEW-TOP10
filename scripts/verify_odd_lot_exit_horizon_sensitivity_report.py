#!/usr/bin/env python3
"""驗證零股出場策略持有上限敏感度報告。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "odd-lot-exit-horizon-sensitivity-report-verification.v1"
REPORT_SCHEMA = "odd-lot-exit-horizon-sensitivity-report.v1"
REQUIRED_HORIZONS = {20, 40, 60}
REQUIRED_KINDS = {"candidate_baseline", "candidate_exit", "production_exit"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify odd-lot exit horizon sensitivity report")
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--output", default="artifacts/model_experiments/odd_lot_exit_horizon_sensitivity_report_verification_latest.json")
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


def build_payload(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    horizons = {int(row.get("horizon")) for row in rows if row.get("horizon") is not None}
    kinds = {row.get("kind") for row in rows}
    decision = payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    checks = [
        {"name": "schema", "ok": payload.get("schema_version") == REPORT_SCHEMA, "value": payload.get("schema_version")},
        {"name": "status_ok", "ok": payload.get("status") == "OK", "value": payload.get("status")},
        {"name": "research_only", "ok": contract.get("research_only") is True, "value": contract},
        {"name": "model_changes_false", "ok": contract.get("model_changes") is False, "value": contract.get("model_changes")},
        {
            "name": "production_ranking_changes_false",
            "ok": contract.get("production_ranking_changes") is False,
            "value": contract.get("production_ranking_changes"),
        },
        {"name": "promotion_ready_false", "ok": contract.get("promotion_ready") is False, "value": contract.get("promotion_ready")},
        {"name": "horizons_present", "ok": REQUIRED_HORIZONS <= horizons, "value": sorted(horizons)},
        {"name": "kinds_present", "ok": REQUIRED_KINDS <= kinds, "value": sorted(str(item) for item in kinds)},
        {"name": "missing_empty", "ok": not payload.get("missing"), "value": payload.get("missing")},
        {"name": "decision_safe", "ok": decision.get("promotion_ready") is False, "value": decision},
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
            "row_count": len(rows),
            "decision": decision.get("status"),
            "selected_horizon": decision.get("selected_horizon"),
        },
        "checks": checks,
    }


def main() -> int:
    args = parse_args()
    artifact = resolve_path(args.artifact)
    if artifact is None or not artifact.exists():
        raise FileNotFoundError(f"artifact not found: {args.artifact}")
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
