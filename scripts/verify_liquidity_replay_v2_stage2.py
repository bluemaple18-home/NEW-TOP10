#!/usr/bin/env python3
"""驗證 liquidity replay v2 stage2 artifact。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "research_reviews"
SCHEMA_VERSION = "liquidity-replay-v2-stage2-verification.v1"
STAGE2_SCHEMA = "liquidity-replay-v2-stage2.v1"
SOURCE_SCHEMA = "liquidity-replay-v2-batch.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify liquidity replay v2 stage2")
    parser.add_argument("--date", required=True)
    parser.add_argument("--artifact", default=None)
    parser.add_argument("--output", default=str(OUTPUT_DIR / "liquidity_replay_v2_stage2_verification_latest.json"))
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


def safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def candidate_passes_gate(row: dict[str, Any], gate: dict[str, Any]) -> bool:
    return (
        safe_float(row.get("return_delta")) >= safe_float(gate.get("return_delta_min"))
        and safe_float(row.get("drawdown_delta")) >= safe_float(gate.get("drawdown_delta_min"))
        and safe_float(row.get("concentration_delta")) <= safe_float(gate.get("concentration_delta_max"))
        and safe_float(row.get("turnover_delta")) <= safe_float(gate.get("turnover_delta_max"))
    )


def all_rows_have_failure_reasons(rows: list[dict[str, Any]]) -> bool:
    return all(isinstance(row.get("failure_reasons"), list) and row.get("failure_reasons") for row in rows)


def build_payload(date: str, artifact: Path) -> dict[str, Any]:
    payload = read_json(artifact)
    md_path = artifact.with_suffix(".md")
    md_text = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
    gate = payload.get("stage2_gate") if isinstance(payload.get("stage2_gate"), dict) else {}
    candidates = payload.get("stage2_candidates") if isinstance(payload.get("stage2_candidates"), list) else []
    shadow = payload.get("shadow_monitor_only") if isinstance(payload.get("shadow_monitor_only"), list) else []
    rejected = payload.get("rejected") if isinstance(payload.get("rejected"), list) else []
    checks = [
        {"name": "artifact_exists", "ok": artifact.exists(), "value": repo_path(artifact)},
        {"name": "markdown_exists", "ok": md_path.exists(), "value": repo_path(md_path)},
        {"name": "schema", "ok": payload.get("schema_version") == STAGE2_SCHEMA, "value": payload.get("schema_version")},
        {"name": "date", "ok": payload.get("review_date") == date, "value": payload.get("review_date")},
        {"name": "source_schema", "ok": source.get("schema_version") == SOURCE_SCHEMA, "value": source.get("schema_version")},
        {
            "name": "source_batch_complete",
            "ok": (source.get("summary") or {}).get("completed_count") == 144 and (source.get("summary") or {}).get("failed_count") == 0,
            "value": source.get("summary"),
        },
        {
            "name": "counts_add_up",
            "ok": summary.get("source_rows") == len(candidates) + len(shadow) + len(rejected),
            "value": {
                "source_rows": summary.get("source_rows"),
                "candidate": len(candidates),
                "shadow": len(shadow),
                "rejected": len(rejected),
            },
        },
        {
            "name": "stage2_candidates_pass_gate",
            "ok": bool(candidates) and all(candidate_passes_gate(row, gate) for row in candidates),
            "value": len(candidates),
        },
        {
            "name": "monitor_and_rejected_have_failure_reasons",
            "ok": all_rows_have_failure_reasons(shadow + rejected),
            "value": {"shadow": len(shadow), "rejected": len(rejected)},
        },
        {"name": "production_impact", "ok": payload.get("production_impact") == "NO_PRODUCTION_CHANGE", "value": payload.get("production_impact")},
        {"name": "report_avoids_promotion_ready_token", "ok": "PROMOTION_READY" not in md_text, "value": "PROMOTION_READY" in md_text},
    ]
    failed = [check for check in checks if not check["ok"]]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK" if not failed else "FAILED",
        "date": date,
        "artifact": {"json": repo_path(artifact), "markdown": repo_path(md_path)},
        "summary": {"check_count": len(checks), "failed_count": len(failed)},
        "checks": checks,
        "errors": failed,
    }


def main() -> int:
    args = parse_args()
    artifact = resolve_path(args.artifact) or OUTPUT_DIR / f"liquidity_replay_v2_stage2_{args.date}.json"
    output = resolve_path(args.output) or OUTPUT_DIR / "liquidity_replay_v2_stage2_verification_latest.json"
    payload = build_payload(args.date, artifact)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "failed_count": payload["summary"]["failed_count"], "output": repo_path(output)}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
