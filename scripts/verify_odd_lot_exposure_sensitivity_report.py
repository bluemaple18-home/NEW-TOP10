#!/usr/bin/env python3
"""驗證 odd-lot 曝險敏感度報告。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "odd-lot-exposure-sensitivity-report-verification.v1"
REPORT_SCHEMA = "odd-lot-exposure-sensitivity-report.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify odd-lot exposure sensitivity report")
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--output", default="artifacts/model_experiments/odd_lot_exposure_sensitivity_report_verification_latest.json")
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
    capital_levels = set((payload.get("inputs") or {}).get("capital_levels") or [])
    settings = set(((payload.get("inputs") or {}).get("settings") or {}).keys())
    sides = {row.get("side") for row in rows}
    row_keys = {(row.get("side"), row.get("setting"), row.get("capital")) for row in rows}
    checks = [
        {"name": "schema", "ok": payload.get("schema_version") == REPORT_SCHEMA, "value": payload.get("schema_version")},
        {"name": "status_ok", "ok": payload.get("status") == "OK", "value": payload.get("status")},
        {"name": "research_only", "ok": contract.get("research_only") is True, "value": contract},
        {"name": "fixed_capital_odd_lot", "ok": contract.get("fixed_capital_odd_lot") is True, "value": contract},
        {"name": "model_changes_false", "ok": contract.get("model_changes") is False, "value": contract.get("model_changes")},
        {
            "name": "production_ranking_changes_false",
            "ok": contract.get("production_ranking_changes") is False,
            "value": contract.get("production_ranking_changes"),
        },
        {"name": "promotion_ready_false", "ok": contract.get("promotion_ready") is False, "value": contract.get("promotion_ready")},
        {"name": "capital_levels_minimum", "ok": len(capital_levels) >= 3, "value": sorted(capital_levels)},
        {"name": "settings_minimum", "ok": {"g85_pos15", "g75_pos12"} <= settings, "value": sorted(settings)},
        {"name": "sides_present", "ok": {"candidate", "production"} <= sides, "value": sorted(str(item) for item in sides)},
        {
            "name": "rows_complete",
            "ok": len(row_keys) >= len(capital_levels) * len(settings) * 2,
            "value": len(row_keys),
        },
        {"name": "missing_empty", "ok": not payload.get("missing"), "value": payload.get("missing")},
        {
            "name": "decision_safe",
            "ok": (payload.get("decision") or {}).get("promotion_ready") is False,
            "value": payload.get("decision"),
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
            "row_count": len(rows),
            "decision": (payload.get("decision") or {}).get("status"),
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
