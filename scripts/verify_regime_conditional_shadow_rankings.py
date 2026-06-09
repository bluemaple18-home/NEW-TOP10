#!/usr/bin/env python3
"""驗證 regime conditional shadow ranking artifact。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "regime-conditional-shadow-ranking-verification.v1"
REPORT_SCHEMA = "regime-conditional-shadow-ranking.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify regime conditional shadow rankings")
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--output", default="artifacts/model_experiments/regime_conditional_shadow_ranking_verification_latest.json")
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
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    outputs = payload.get("outputs") if isinstance(payload.get("outputs"), list) else []
    output_paths = [resolve_path(item) for item in outputs[:5]]
    checks = [
        {"name": "schema", "ok": payload.get("schema_version") == REPORT_SCHEMA, "value": payload.get("schema_version")},
        {"name": "research_only", "ok": contract.get("research_only") is True, "value": contract},
        {"name": "trains_model_false", "ok": contract.get("trains_model") is False, "value": contract.get("trains_model")},
        {
            "name": "modifies_production_ranking_false",
            "ok": contract.get("modifies_production_ranking") is False,
            "value": contract.get("modifies_production_ranking"),
        },
        {"name": "date_count_positive", "ok": int(summary.get("date_count") or 0) > 0, "value": summary.get("date_count")},
        {
            "name": "shadow_active_family_positive",
            "ok": int(summary.get("shadow_active_family_count") or 0) > 0,
            "value": summary.get("shadow_active_family_count"),
        },
        {
            "name": "production_inactive_family_positive",
            "ok": int(summary.get("production_inactive_family_count") or 0) > 0,
            "value": summary.get("production_inactive_family_count"),
        },
        {
            "name": "rows_match_summary",
            "ok": len(rows) == int(summary.get("date_count") or -1),
            "value": {"rows": len(rows), "summary": summary.get("date_count")},
        },
        {
            "name": "sample_outputs_exist",
            "ok": all(path is not None and path.exists() for path in output_paths),
            "value": [repo_path(path) for path in output_paths],
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
            "date_count": summary.get("date_count"),
            "shadow_active_family_count": summary.get("shadow_active_family_count"),
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
