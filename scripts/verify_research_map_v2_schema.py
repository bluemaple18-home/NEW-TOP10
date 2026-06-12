#!/usr/bin/env python3
"""驗證 research map v2 世界觀 schema。

這支 verifier 不判斷策略好壞，只檢查地圖是否誠實呈現：
- base scan 與 full universe 分開
- v1 5913 已探索情境已 migrate 到 v2 default coordinates
- expanded universe count 沒被包裝成 100%
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_map_contract import (
    V2_DEFAULT_COORDINATES,
    V2_DIMENSION_SCHEMA_VERSION,
    dimension_schema_payload,
    expanded_universe_total,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "research_map"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify research map v2 schema")
    parser.add_argument("--payload", default=str(OUTPUT_DIR / "research_fog_map_latest.json"))
    parser.add_argument("--output", default=str(OUTPUT_DIR / "research_map_v2_schema_verification_latest.json"))
    return parser.parse_args()


def resolve_path(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    path = Path(value)
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


def main() -> int:
    args = parse_args()
    payload_path = resolve_path(args.payload)
    output_path = resolve_path(args.output)
    if payload_path is None or output_path is None:
        raise RuntimeError("path resolution failed")
    payload = read_json(payload_path)
    report = build_report(payload, payload_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": report["status"],
                "output": repo_path(output_path),
                "failed_count": report["summary"]["failed_count"],
                "expanded_universe_total": report["summary"].get("expanded_universe_total"),
                "expanded_processed": report["summary"].get("expanded_processed"),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "OK" else 1


def build_report(payload: dict[str, Any], payload_path: Path) -> dict[str, Any]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    scenarios = payload.get("scenarios") if isinstance(payload.get("scenarios"), list) else []
    schema = payload.get("dimension_schema") if isinstance(payload.get("dimension_schema"), dict) else {}
    expected_schema = dimension_schema_payload()
    topic_count = int(summary.get("total_topics") or 0)
    expected_expanded_total = expanded_universe_total(topic_count)
    migrated = [
        row
        for row in scenarios
        if isinstance(row.get("v2_dimensions"), dict)
        and all(row["v2_dimensions"].get(key) == value for key, value in V2_DEFAULT_COORDINATES.items())
    ]
    active_queue = payload.get("active_expansion_queue") if isinstance(payload.get("active_expansion_queue"), list) else []
    checks = [
        {"name": "payload_exists", "ok": payload_path.exists(), "value": repo_path(payload_path)},
        {
            "name": "schema_version",
            "ok": summary.get("dimension_schema_version") == V2_DIMENSION_SCHEMA_VERSION
            and schema.get("version") == V2_DIMENSION_SCHEMA_VERSION,
            "value": {"summary": summary.get("dimension_schema_version"), "schema": schema.get("version")},
        },
        {
            "name": "dimension_values_match_contract",
            "ok": schema.get("dimension_values") == expected_schema["dimension_values"]
            and summary.get("dimension_values") == expected_schema["dimension_values"],
            "value": schema.get("dimension_values"),
        },
        {
            "name": "base_scan_count",
            "ok": summary.get("base_universe_total") == 5913
            and summary.get("base_processed") == 5913
            and len(scenarios) == 5913,
            "value": {
                "base_universe_total": summary.get("base_universe_total"),
                "base_processed": summary.get("base_processed"),
                "scenario_rows": len(scenarios),
            },
        },
        {
            "name": "expanded_universe_count",
            "ok": summary.get("expanded_universe_total") == expected_expanded_total == 662256,
            "value": {
                "actual": summary.get("expanded_universe_total"),
                "expected": expected_expanded_total,
            },
        },
        {
            "name": "expanded_progress_is_early_stage",
            "ok": summary.get("expanded_processed") == 5913
            and float(summary.get("expanded_progress_pct") or 0) < 0.02
            and float(summary.get("base_progress_pct") or 0) == 1.0,
            "value": {
                "expanded_processed": summary.get("expanded_processed"),
                "expanded_progress_pct": summary.get("expanded_progress_pct"),
                "base_progress_pct": summary.get("base_progress_pct"),
            },
        },
        {
            "name": "v1_rows_migrated_to_v2_default_coordinates",
            "ok": len(migrated) == 5913,
            "value": {"migrated_rows": len(migrated), "defaults": V2_DEFAULT_COORDINATES},
        },
        {
            "name": "active_queue_uses_v2_coordinates_if_present",
            "ok": all(
                isinstance(row.get("dimensions"), dict)
                and {"regime_gate", "risk_guard", "entry_filter"}.issubset(set(row["dimensions"]))
                for row in active_queue
            ),
            "value": {"active_queue_count": len(active_queue)},
        },
        {
            "name": "production_boundary",
            "ok": (payload.get("contract") or {}).get("does_not_change_production_ranking") is True
            and (payload.get("contract") or {}).get("does_not_train_model") is True
            and (payload.get("contract") or {}).get("does_not_change_models_latest_lgbm") is True,
            "value": payload.get("contract"),
        },
    ]
    failed = [check for check in checks if not check["ok"]]
    return {
        "schema_version": "research-map-v2-schema-verification.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK" if not failed else "FAILED",
        "artifact": repo_path(payload_path),
        "summary": {
            "failed_count": len(failed),
            "base_universe_total": summary.get("base_universe_total"),
            "base_processed": summary.get("base_processed"),
            "expanded_universe_total": summary.get("expanded_universe_total"),
            "expanded_processed": summary.get("expanded_processed"),
            "expanded_progress_pct": summary.get("expanded_progress_pct"),
            "active_queue_count": len(active_queue),
            "v1_migration_count": len(migrated),
        },
        "checks": checks,
    }


if __name__ == "__main__":
    raise SystemExit(main())

