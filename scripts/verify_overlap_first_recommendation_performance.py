#!/usr/bin/env python3
"""驗證 overlap-first recommendation performance replay。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "overlap-first-recommendation-performance-verification.v1"
REPORT_SCHEMA = "overlap-first-recommendation-performance.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify overlap-first recommendation performance")
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--output", default="artifacts/model_experiments/overlap_first_recommendation_performance_verification_latest.json")
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


def ranking_count(path: Path | None) -> int:
    if path is None or not path.exists():
        return 0
    return len(list(path.glob("ranking_*.csv")))


def n(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def build_payload(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    inputs = payload.get("inputs") if isinstance(payload.get("inputs"), dict) else {}
    overlap_rankings = payload.get("overlap_rankings") if isinstance(payload.get("overlap_rankings"), dict) else {}
    replays = payload.get("replays") if isinstance(payload.get("replays"), dict) else {}
    comparison = payload.get("comparison") if isinstance(payload.get("comparison"), dict) else {}
    decision = payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    selected_days = int(inputs.get("selected_ranking_days") or 0)
    production_subset = resolve_path(inputs.get("production_subset_rankings_dir"))
    candidate_subset = resolve_path(inputs.get("candidate_subset_rankings_dir"))
    overlap_dir = resolve_path(overlap_rankings.get("dir"))
    replay_daily_counts = {
        key: int((value or {}).get("daily_count") or 0)
        for key, value in replays.items()
        if isinstance(value, dict)
    }
    vs_production = comparison.get("overlap_vs_production") if isinstance(comparison.get("overlap_vs_production"), dict) else {}
    checks = [
        {"name": "schema", "ok": payload.get("schema_version") == REPORT_SCHEMA, "value": payload.get("schema_version")},
        {"name": "status_ok", "ok": payload.get("status") == "OK", "value": payload.get("status")},
        {
            "name": "research_only_contract",
            "ok": contract.get("research_only") is True
            and contract.get("uses_existing_rankings_only") is True
            and contract.get("changes_production_ranking") is False
            and contract.get("changes_clawd_message") is False
            and contract.get("changes_model") is False,
            "value": contract,
        },
        {
            "name": "no_direct_switch",
            "ok": contract.get("production_switch_ready") is False
            and contract.get("promotion_ready") is False
            and decision.get("production_switch_ready") is False
            and decision.get("promotion_ready") is False,
            "value": {"contract": contract, "decision": decision},
        },
        {"name": "selected_days_positive", "ok": selected_days > 0, "value": selected_days},
        {
            "name": "subset_window_aligned",
            "ok": ranking_count(production_subset) == selected_days
            and ranking_count(candidate_subset) == selected_days
            and ranking_count(overlap_dir) == selected_days,
            "value": {
                "selected_days": selected_days,
                "production_subset": ranking_count(production_subset),
                "candidate_subset": ranking_count(candidate_subset),
                "overlap": ranking_count(overlap_dir),
            },
        },
        {
            "name": "all_replay_variants_present",
            "ok": {"production", "candidate", "overlap_first"}.issubset(set(replays)),
            "value": sorted(replays),
        },
        {
            "name": "daily_counts_aligned",
            "ok": len(set(replay_daily_counts.values())) == 1 and all(value > 0 for value in replay_daily_counts.values()),
            "value": replay_daily_counts,
        },
        {
            "name": "decision_matches_delta",
            "ok": (decision.get("status") == "MONITOR_ONLY" and n(vs_production.get("return_delta")) <= 0)
            or n(vs_production.get("return_delta")) > 0,
            "value": {"decision": decision, "overlap_vs_production": vs_production},
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
            "window": payload.get("window"),
            "decision": decision.get("status"),
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
        raise RuntimeError("output resolution failed")
    payload = build_payload(artifact)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output)}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
