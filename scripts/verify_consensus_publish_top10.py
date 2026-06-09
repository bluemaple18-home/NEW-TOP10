#!/usr/bin/env python3
"""驗證 consensus-first 推播 Top10 artifact。"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "consensus-publish-top10-verification.v1"
REPORT_SCHEMA = "consensus-publish-top10.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="驗證共識推播 Top10 artifact")
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--output", default="artifacts/model_experiments/consensus_publish_top10_verification_latest.json")
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


def read_publish_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def overlap_first(sources: list[str]) -> bool:
    seen_non_overlap = False
    for source in sources:
        if source != "overlap":
            seen_non_overlap = True
        elif seen_non_overlap:
            return False
    return True


def build_payload(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    outputs = payload.get("outputs") if isinstance(payload.get("outputs"), dict) else {}
    publish_path = resolve_path(outputs.get("publish_ranking"))
    publish_rows = payload.get("publish_top10") if isinstance(payload.get("publish_top10"), list) else []
    csv_rows = read_publish_rows(publish_path) if publish_path and publish_path.exists() else []
    sources = [str(row.get("publish_source") or "") for row in csv_rows]
    overlap_rows = [row for row in csv_rows if row.get("publish_source") == "overlap"]
    comparison = payload.get("comparison") if isinstance(payload.get("comparison"), dict) else {}
    checks = [
        {"name": "schema", "ok": payload.get("schema_version") == REPORT_SCHEMA, "value": payload.get("schema_version")},
        {"name": "status_ok", "ok": payload.get("status") == "OK", "value": payload.get("status")},
        {"name": "adapter_contract", "ok": contract.get("research_to_publish_adapter") is True, "value": contract},
        {"name": "model_changes_false", "ok": contract.get("model_changes") is False, "value": contract.get("model_changes")},
        {
            "name": "production_ranking_changes_false",
            "ok": contract.get("production_ranking_changes") is False,
            "value": contract.get("production_ranking_changes"),
        },
        {"name": "clawd_not_sent", "ok": contract.get("clawd_send_attempted") is False, "value": contract.get("clawd_send_attempted")},
        {"name": "promotion_ready_false", "ok": contract.get("promotion_ready") is False, "value": contract.get("promotion_ready")},
        {"name": "publish_ranking_exists", "ok": publish_path is not None and publish_path.exists(), "value": repo_path(publish_path)},
        {"name": "publish_top10_count", "ok": len(publish_rows) == 10 and len(sources) == 10, "value": {"json": len(publish_rows), "csv": len(sources)}},
        {"name": "overlap_first", "ok": overlap_first(sources), "value": sources},
        {
            "name": "overlap_uses_production_row_body",
            "ok": all(row.get("publish_row_source") == "production" for row in overlap_rows),
            "value": overlap_rows[:3],
        },
        {
            "name": "overlap_candidate_comparison_fields",
            "ok": all("candidate_risk_adjusted_score" in row and "candidate_reasons" in row for row in overlap_rows),
            "value": overlap_rows[:3],
        },
        {
            "name": "source_counts_consistent",
            "ok": sum((comparison.get("publish_source_counts") or {}).values()) == len(publish_rows),
            "value": comparison.get("publish_source_counts"),
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
            "overlap_count": comparison.get("overlap_count"),
            "publish_source_counts": comparison.get("publish_source_counts"),
            "publish_ranking": repo_path(publish_path),
        },
        "checks": checks,
    }


def main() -> int:
    args = parse_args()
    artifact = resolve_path(args.artifact)
    if artifact is None or not artifact.exists():
        raise FileNotFoundError(f"找不到 artifact：{args.artifact}")
    output = resolve_path(args.output)
    if output is None:
        raise RuntimeError("output 路徑解析失敗")
    payload = build_payload(artifact)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output)}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
