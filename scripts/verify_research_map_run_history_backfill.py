#!/usr/bin/env python3
"""驗證 research map run_history backfill。

只檢查格式、來源、combo_id 是否在 registry 內，不判斷策略好壞。
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_map_contract import build_combo_registry, read_jsonl


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AUTO_DIR = PROJECT_ROOT / "artifacts" / "autonomous_research"
OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "research_map"
BACKFILL_SOURCES = {
    "research_map_legacy_strategy_matrix_backfill",
    "research_map_legacy_topic_registry_backfill",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify research map backfill rows")
    parser.add_argument("--history", default=str(AUTO_DIR / "run_history.jsonl"))
    parser.add_argument("--output", default=str(OUTPUT_DIR / "research_map_backfill_verification_latest.json"))
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
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_report(history_path: Path) -> dict[str, Any]:
    registry = read_json(AUTO_DIR / "topic_registry.json")
    topics = registry.get("topics") if isinstance(registry.get("topics"), list) else []
    valid_combo_ids = {row["combo_id"] for row in build_combo_registry(topics)}
    rows = read_jsonl(history_path)
    backfill_rows = [row for row in rows if row.get("source") in BACKFILL_SOURCES]
    source_counts = Counter(str(row.get("source")) for row in backfill_rows)
    evidence_counts = Counter(str(row.get("evidence_level")) for row in backfill_rows)
    invalid_combo_ids = [row.get("combo_id") for row in backfill_rows if row.get("combo_id") not in valid_combo_ids]
    missing_artifact_path = [row.get("combo_id") for row in backfill_rows if not row.get("artifact_path")]
    bad_dimensions = [
        row.get("combo_id")
        for row in backfill_rows
        if not isinstance(row.get("dimensions"), dict)
        or set(row["dimensions"]) != {"horizon", "stop_loss", "take_profit", "group_exposure"}
    ]
    unknown_evidence = [
        row.get("combo_id")
        for row in backfill_rows
        if row.get("evidence_level") not in {"scenario_exact", "topic_level"}
    ]
    checks = [
        {"name": "history_exists", "ok": history_path.exists(), "value": repo_path(history_path)},
        {"name": "registry_topics_present", "ok": len(topics) > 0, "value": len(topics)},
        {"name": "backfill_rows_present", "ok": len(backfill_rows) > 0, "value": len(backfill_rows)},
        {"name": "scenario_exact_present", "ok": source_counts.get("research_map_legacy_strategy_matrix_backfill", 0) > 0, "value": dict(source_counts)},
        {"name": "combo_ids_valid", "ok": not invalid_combo_ids, "value": invalid_combo_ids[:10]},
        {"name": "artifact_paths_present", "ok": not missing_artifact_path, "value": missing_artifact_path[:10]},
        {"name": "dimensions_valid", "ok": not bad_dimensions, "value": bad_dimensions[:10]},
        {"name": "evidence_levels_valid", "ok": not unknown_evidence, "value": unknown_evidence[:10]},
    ]
    failed = [check for check in checks if not check["ok"]]
    return {
        "schema_version": "research-map-backfill-verification.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK" if not failed else "FAILED",
        "summary": {
            "total_rows": len(rows),
            "backfill_rows": len(backfill_rows),
            "source_counts": dict(sorted(source_counts.items())),
            "evidence_counts": dict(sorted(evidence_counts.items())),
            "failed_count": len(failed),
        },
        "checks": checks,
    }


def main() -> int:
    args = parse_args()
    history_path = resolve_path(args.history)
    output_path = resolve_path(args.output)
    if history_path is None or output_path is None:
        raise RuntimeError("path resolution failed")
    report = build_report(history_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": report["status"],
                "output": repo_path(output_path),
                **report["summary"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
