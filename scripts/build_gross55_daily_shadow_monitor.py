#!/usr/bin/env python3
"""產出 gross55 每日營運 shadow monitor。

用途：每日正式 ranking 產生後，檢查 gross55 保守曝險規則若啟用會如何影響
當日 Top10 的目標總曝險。此腳本不改 ranking、不改 Clawd 訊息，只產監控 artifact。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_gross55_operational_shadow_dry_run import (  # noqa: E402
    EXPECTED_MODEL_SHA256,
    allocation_snapshot,
    repo_path,
    resolve_path,
    sha256,
)


SCHEMA_VERSION = "gross55-daily-shadow-monitor.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build gross55 daily shadow monitor")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--ranking", default=None, help="指定 ranking CSV；未指定時使用 artifacts/ranking_<date>.csv，找不到則取最新 artifacts/ranking_*.csv")
    parser.add_argument("--dry-run", default="artifacts/model_experiments/gross55_operational_shadow_dry_run_2026-06-02.json")
    parser.add_argument("--model", default="models/latest_lgbm.pkl")
    parser.add_argument("--expected-model-sha256", default=EXPECTED_MODEL_SHA256)
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--production-gross-cap", type=float, default=0.65)
    parser.add_argument("--shadow-gross-cap", type=float, default=0.55)
    parser.add_argument("--max-position-weight", type=float, default=0.2)
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def ranking_path(args: argparse.Namespace) -> Path | None:
    if args.ranking:
        path = resolve_path(args.ranking)
        return path if path.exists() else None
    dated = PROJECT_ROOT / "artifacts" / f"ranking_{args.date}.csv"
    if dated.exists():
        return dated
    files = sorted((PROJECT_ROOT / "artifacts").glob("ranking_*.csv"))
    return files[-1] if files else None


def n(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def decide(allocation: dict[str, Any], dry_run: dict[str, Any], model_hash: str | None, expected_hash: str) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if dry_run.get("shadow_status") != "READY_FOR_OPERATIONAL_SHADOW_MONITOR":
        reasons.append("gross55 operational dry-run is not ready for shadow monitor")
    if model_hash != expected_hash:
        reasons.append("model hash changed")
    if not allocation.get("exists"):
        reasons.append("ranking file missing")
    if reasons:
        return "BLOCKED", reasons
    if allocation.get("entry_weight_changed_on_latest_ranking"):
        return "MONITOR_WOULD_REDUCE_TODAY_EXPOSURE", []
    return "MONITOR_NO_ENTRY_CHANGE_TODAY", []


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    dry_run_path = resolve_path(args.dry_run)
    dry_run = read_json(dry_run_path)
    selected_ranking = ranking_path(args)
    model_path = resolve_path(args.model)
    model_hash = sha256(model_path) if model_path.exists() else None
    allocation = allocation_snapshot(
        selected_ranking,
        args.top_n,
        args.production_gross_cap,
        args.shadow_gross_cap,
        args.max_position_weight,
    )
    monitor_status, reasons = decide(allocation, dry_run, model_hash, args.expected_model_sha256)
    gross_delta = round(
        n(allocation.get("gross55_shadow_target_gross_from_latest_ranking"))
        - n(allocation.get("production_target_gross_from_latest_ranking")),
        6,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK" if monitor_status != "BLOCKED" else "BLOCKED",
        "monitor_status": monitor_status,
        "blocked_reasons": reasons,
        "contract": {
            "operational_shadow_only": True,
            "changes_top10_membership": False,
            "changes_risk_adjusted_score": False,
            "changes_production_ranking": False,
            "changes_clawd_message": False,
            "changes_model": False,
            "default_allowed": False,
        },
        "inputs": {
            "ranking": repo_path(selected_ranking) if selected_ranking else None,
            "dry_run": repo_path(dry_run_path),
            "model": repo_path(model_path),
            "actual_model_sha256": model_hash,
            "expected_model_sha256": args.expected_model_sha256,
            "production_gross_cap": args.production_gross_cap,
            "shadow_gross_cap": args.shadow_gross_cap,
        },
        "summary": {
            "ranking_date": allocation.get("ranking_date"),
            "latest_market_regime": allocation.get("latest_market_regime"),
            "entry_weight_changed_today": allocation.get("entry_weight_changed_on_latest_ranking"),
            "ranking_requested_gross": allocation.get("ranking_requested_gross"),
            "production_target_gross": allocation.get("production_target_gross_from_latest_ranking"),
            "gross55_shadow_target_gross": allocation.get("gross55_shadow_target_gross_from_latest_ranking"),
            "gross_target_delta": gross_delta,
            "operator_note": "只做影子監控；若 gross_target_delta 為負，代表今天 gross55 會降低曝險，但不改 Top10 名單。",
        },
        "latest_allocation_shadow": allocation,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Gross55 Daily Shadow Monitor",
        "",
        f"- status: `{payload['status']}`",
        f"- monitor_status: `{payload['monitor_status']}`",
        f"- ranking_date: `{summary.get('ranking_date')}`",
        f"- latest_market_regime: `{summary.get('latest_market_regime')}`",
        f"- entry_weight_changed_today: `{summary.get('entry_weight_changed_today')}`",
        f"- ranking_requested_gross: `{n(summary.get('ranking_requested_gross')):.2%}`",
        f"- production_target_gross: `{n(summary.get('production_target_gross')):.2%}`",
        f"- gross55_shadow_target_gross: `{n(summary.get('gross55_shadow_target_gross')):.2%}`",
        f"- gross_target_delta: `{n(summary.get('gross_target_delta')):.2%}`",
        "",
        "## Boundary",
        "",
        "- 不改 Top10 名單。",
        "- 不改正式 ranking CSV。",
        "- 不改 Clawd 訊息。",
        "- 不改模型。",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = (
        resolve_path(args.output)
        if args.output
        else PROJECT_ROOT / "artifacts" / "model_experiments" / f"gross55_daily_shadow_monitor_{args.date}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "monitor_status": payload["monitor_status"],
                "output": repo_path(output),
                "ranking_date": payload["summary"].get("ranking_date"),
                "gross_target_delta": payload["summary"].get("gross_target_delta"),
            },
            ensure_ascii=False,
        )
    )
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
