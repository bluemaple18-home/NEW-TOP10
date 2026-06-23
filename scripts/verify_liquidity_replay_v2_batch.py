#!/usr/bin/env python3
"""驗證 liquidity replay v2 batch artifact 與星圖回寫契約。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FOG_MAP_PATH = PROJECT_ROOT / "artifacts" / "research_map" / "research_fog_map_latest.json"
RUN_HISTORY_PATH = PROJECT_ROOT / "artifacts" / "autonomous_research" / "run_history.jsonl"
OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "research_reviews"
SCHEMA_VERSION = "liquidity-replay-v2-batch-verification.v1"
BATCH_SCHEMA = "liquidity-replay-v2-batch.v1"
STAGE = "LIQUIDITY-REPLAY-02"
REQUIRED_DIMENSIONS = {"horizon", "stop_loss", "take_profit", "group_exposure", "regime_gate", "risk_guard", "entry_filter"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify liquidity replay v2 batch")
    parser.add_argument("--date", required=True)
    parser.add_argument("--artifact", default=None)
    parser.add_argument("--output", default=str(OUTPUT_DIR / "liquidity_replay_v2_batch_verification_latest.json"))
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
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def active_queue() -> list[dict[str, Any]]:
    payload = read_json(FOG_MAP_PATH)
    queue = payload.get("active_expansion_queue") if isinstance(payload.get("active_expansion_queue"), list) else []
    return [item for item in queue if isinstance(item, dict) and item.get("stage") == STAGE]


def rows_have_dimensions(rows: list[dict[str, Any]]) -> bool:
    for row in rows:
        dimensions = row.get("dimensions") if isinstance(row.get("dimensions"), dict) else {}
        if not REQUIRED_DIMENSIONS.issubset(dimensions):
            return False
    return True


def completed_have_artifacts(rows: list[dict[str, Any]]) -> bool:
    for row in rows:
        if row.get("status") != "completed":
            continue
        for side in ["baseline", "candidate"]:
            artifact = ((row.get(side) or {}).get("artifact")) if isinstance(row.get(side), dict) else None
            if not artifact or not resolve_path(str(artifact)).exists():
                return False
    return True


def completed_have_deltas(rows: list[dict[str, Any]]) -> bool:
    return all(row.get("return_delta") is not None and row.get("drawdown_delta") is not None for row in rows if row.get("status") == "completed")


def run_history_alignment(rows: list[dict[str, Any]]) -> dict[str, Any]:
    history = read_jsonl(RUN_HISTORY_PATH)
    by_combo = {str(row.get("combo_id")): row for row in history if row.get("source") == "liquidity_replay_v2_batch"}
    missing = []
    mismatched = []
    for row in rows:
        if row.get("status") != "completed":
            continue
        combo_id = str(row.get("combo_id") or "")
        history_row = by_combo.get(combo_id)
        if not history_row:
            missing.append(combo_id)
            continue
        if history_row.get("combo_id") != row.get("combo_id"):
            mismatched.append(combo_id)
    return {"missing": missing, "mismatched": mismatched, "history_count": len(by_combo)}


def build_payload(date: str, artifact_path: Path) -> dict[str, Any]:
    batch = read_json(artifact_path)
    md_path = artifact_path.with_suffix(".md")
    md_text = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
    queue = active_queue()
    rows = batch.get("rows") if isinstance(batch.get("rows"), list) else []
    alignment = run_history_alignment(rows)
    checks = [
        {"name": "artifact_exists", "ok": artifact_path.exists(), "value": repo_path(artifact_path)},
        {"name": "markdown_exists", "ok": md_path.exists(), "value": repo_path(md_path)},
        {"name": "schema", "ok": batch.get("schema_version") == BATCH_SCHEMA, "value": batch.get("schema_version")},
        {"name": "batch_source_active_queue", "ok": (batch.get("source") or {}).get("source_queue") == "active_expansion_queue" and (batch.get("source") or {}).get("active_stage") == STAGE, "value": batch.get("source")},
        {"name": "active_queue_count", "ok": len(queue) > 0, "value": len(queue)},
        {"name": "scenario_count_lte_active_queue", "ok": len(rows) <= len(queue), "value": {"rows": len(rows), "queue": len(queue)}},
        {"name": "rows_have_v2_dimensions", "ok": rows_have_dimensions(rows), "value": len(rows)},
        {"name": "completed_have_artifacts", "ok": completed_have_artifacts(rows), "value": len(rows)},
        {"name": "completed_have_deltas", "ok": completed_have_deltas(rows), "value": len(rows)},
        {"name": "run_history_combo_alignment", "ok": not alignment["missing"] and not alignment["mismatched"], "value": alignment},
        {"name": "production_impact", "ok": batch.get("production_impact") == "NO_PRODUCTION_CHANGE", "value": batch.get("production_impact")},
        {"name": "report_avoids_promotion_ready_token", "ok": "PROMOTION_READY" not in md_text, "value": "PROMOTION_READY" in md_text},
    ]
    failed = [check for check in checks if not check["ok"]]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK" if not failed else "FAILED",
        "date": date,
        "artifact": {"json": repo_path(artifact_path), "markdown": repo_path(md_path)},
        "summary": {"check_count": len(checks), "failed_count": len(failed)},
        "checks": checks,
        "errors": failed,
    }


def main() -> int:
    args = parse_args()
    artifact = resolve_path(args.artifact) or OUTPUT_DIR / f"liquidity_replay_v2_batch_{args.date}.json"
    output = resolve_path(args.output) or OUTPUT_DIR / "liquidity_replay_v2_batch_verification_latest.json"
    payload = build_payload(args.date, artifact)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "failed_count": payload["summary"]["failed_count"], "output": repo_path(output)}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
