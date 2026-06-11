#!/usr/bin/env python3
"""檢查 production trail10 shadow 訊號品質。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from build_production_trail10_shadow import build_payload as build_shadow_payload
from build_production_trail10_shadow import ranking_date, ranking_files


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "production-trail10-shadow-review.v1"
ALLOWED_DECISIONS = {"SHADOW_SIGNAL_OK", "SHADOW_SIGNAL_MONITOR", "SHADOW_SIGNAL_BLOCKED"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build production trail10 shadow review")
    parser.add_argument("--date", default=datetime.now().date().isoformat())
    parser.add_argument("--rankings-dir", default="artifacts")
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument("--shadow-dir", default="artifacts/shadow/production_trail10")
    parser.add_argument("--output", default=None)
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


def shadow_args(args: argparse.Namespace, date_text: str) -> SimpleNamespace:
    return SimpleNamespace(
        date=date_text,
        rankings_dir=args.rankings_dir,
        features=args.features,
        top_n=10,
        lookback_ranking_days=45,
        max_holding_days=40,
        min_holding_days=5,
        trail_pct=0.10,
        trail_zone_buffer=0.02,
        output=None,
    )


def load_or_build_shadow(args: argparse.Namespace, date_text: str) -> dict[str, Any]:
    shadow_path = resolve_path(args.shadow_dir) / f"production_trail10_shadow_{date_text}.json"
    if shadow_path.exists():
        return read_json(shadow_path)
    return build_shadow_payload(shadow_args(args, date_text))


def sample_dates(args: argparse.Namespace) -> dict[str, list[str]]:
    rankings_dir = resolve_path(args.rankings_dir)
    if rankings_dir is None or not rankings_dir.exists():
        raise FileNotFoundError(f"找不到 rankings dir：{args.rankings_dir}")
    files = ranking_files(rankings_dir, args.date)
    dates = [ranking_date(path) for path in files]
    return {
        "latest": dates[-1:],
        "recent_5": dates[-5:],
        "recent_20": dates[-20:],
    }


def check_shadow(payload: dict[str, Any]) -> dict[str, Any]:
    positions = payload.get("shadow_positions") if isinstance(payload.get("shadow_positions"), list) else []
    run_date = str(payload.get("run_date"))
    as_of = str((payload.get("inputs") or {}).get("as_of_price_date"))
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    seen: dict[tuple[str, str], str] = {}
    for row in positions:
        status = str(row.get("status"))
        key = (str(row.get("stock_id")), str(row.get("ranking_date")))
        previous = seen.get(key)
        if previous and previous != status:
            issues.append({"type": "mutually_exclusive_status", "stock_id": key[0], "ranking_date": key[1], "statuses": [previous, status]})
        seen[key] = status
        if status == "exit_triggered" and int(row.get("days_held") or 0) < int(row.get("min_holding_days") or 5):
            issues.append({"type": "min_hold_violation", "stock_id": row.get("stock_id"), "days_held": row.get("days_held")})
        if status == "exit_triggered" and (row.get("exit_price") is None or row.get("trail_threshold") is None):
            issues.append({"type": "missing_exit_price_basis", "stock_id": row.get("stock_id")})
        if status == "trail_stop_zone" and (row.get("latest_close") is None or row.get("trail_threshold") is None):
            issues.append({"type": "missing_trail_zone_price_basis", "stock_id": row.get("stock_id")})
        if status == "expired_or_removed" and not row.get("status_reason"):
            warnings.append({"type": "expired_missing_reason", "stock_id": row.get("stock_id")})
    latest_ranking = str((payload.get("inputs") or {}).get("latest_ranking") or "")
    latest_matches_run_date = latest_ranking.endswith(f"ranking_{run_date}.csv")
    if as_of > run_date:
        issues.append({"type": "future_price_data", "run_date": run_date, "as_of_price_date": as_of})
    if not latest_matches_run_date:
        warnings.append({"type": "latest_ranking_not_equal_run_date", "run_date": run_date, "latest_ranking": latest_ranking})
    return {
        "run_date": run_date,
        "as_of_price_date": as_of,
        "latest_ranking_matches_run_date": latest_matches_run_date,
        "status_counts": (payload.get("summary") or {}).get("status_counts", {}),
        "issue_count": len(issues),
        "warning_count": len(warnings),
        "issues": issues,
        "warnings": warnings,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    groups = sample_dates(args)
    reviewed: dict[str, list[dict[str, Any]]] = {}
    all_issues: list[dict[str, Any]] = []
    all_warnings: list[dict[str, Any]] = []
    for label, dates in groups.items():
        reviewed[label] = []
        for date_text in dates:
            row = check_shadow(load_or_build_shadow(args, date_text))
            reviewed[label].append(row)
            all_issues.extend([{**issue, "sample": label, "run_date": date_text} for issue in row["issues"]])
            all_warnings.extend([{**warning, "sample": label, "run_date": date_text} for warning in row["warnings"]])
    if all_issues:
        decision = "SHADOW_SIGNAL_BLOCKED"
    elif all_warnings:
        decision = "SHADOW_SIGNAL_MONITOR"
    else:
        decision = "SHADOW_SIGNAL_OK"
    target_shadow = resolve_path(args.shadow_dir) / f"production_trail10_shadow_{args.date}.json"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_date": args.date,
        "status": "OK",
        "contract": {
            "review_only": True,
            "changes_production_ranking": False,
            "changes_clawd_live_message": False,
            "changes_model": False,
            "live_send": False,
            "uses_future_data_for_exit": False,
        },
        "inputs": {
            "target_shadow": repo_path(target_shadow),
            "rankings_dir": args.rankings_dir,
            "features": args.features,
            "sample_dates": groups,
        },
        "reviewed_samples": reviewed,
        "issue_count": len(all_issues),
        "warning_count": len(all_warnings),
        "issues": all_issues,
        "warnings": all_warnings,
        "decision": decision,
        "blocked_reasons": [issue["type"] for issue in all_issues],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# Production Trail10 Shadow Review - {payload['run_date']}",
        "",
        f"- decision: `{payload['decision']}`",
        f"- issues: `{payload['issue_count']}`",
        f"- warnings: `{payload['warning_count']}`",
        "",
        "## Samples",
        "",
    ]
    for label, rows in payload["reviewed_samples"].items():
        lines.append(f"### {label}")
        for row in rows:
            lines.append(
                f"- `{row['run_date']}` as_of=`{row['as_of_price_date']}` issues=`{row['issue_count']}` warnings=`{row['warning_count']}` counts=`{row['status_counts']}`"
            )
        lines.append("")
    if payload["issues"]:
        lines.extend(["## Issues", ""])
        lines.extend([f"- {item}" for item in payload["issues"]])
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    output = resolve_path(args.output) or PROJECT_ROOT / "artifacts" / "shadow" / "production_trail10" / f"production_trail10_shadow_review_{args.date}.json"
    if output is None:
        raise RuntimeError("output resolution failed")
    payload = build_payload(args)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "decision": payload["decision"], "output": repo_path(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
