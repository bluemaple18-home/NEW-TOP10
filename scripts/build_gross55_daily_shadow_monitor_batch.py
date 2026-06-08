#!/usr/bin/env python3
"""批次彙整 gross55 每日 shadow monitor。

讀取正式 daily ranking artifacts，逐日模擬 gross55 保守總曝險規則會不會降低
當日目標曝險；若提供近期 replay artifact，補上已成熟短期結果。此腳本只產
shadow report，不改 production ranking / message / model。
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


SCHEMA_VERSION = "gross55-daily-shadow-monitor-batch.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build gross55 daily shadow monitor batch")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--rankings-dir", default="artifacts")
    parser.add_argument("--dry-run", default="artifacts/model_experiments/gross55_operational_shadow_dry_run_2026-06-02.json")
    parser.add_argument("--fixed65-replay", default="artifacts/backtest/portfolio_replay_gross55_daily_monitor_fixed65_2026-06-02.json")
    parser.add_argument("--gross55-replay", default="artifacts/backtest/portfolio_replay_gross55_daily_monitor_gross55_2026-06-02.json")
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


def n(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def pct(value: Any) -> str:
    return f"{n(value):.2%}"


def ranking_files(path: Path) -> list[Path]:
    return sorted(path.glob("ranking_*.csv"))


def compact_replay(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    summary = payload.get("summary") or {}
    return {
        "path": repo_path(path),
        "exists": bool(payload),
        "total_return": summary.get("total_return"),
        "max_drawdown": summary.get("max_drawdown"),
        "daily_count": summary.get("daily_count"),
        "trade_count": summary.get("trade_count"),
        "skipped_count": summary.get("skipped_count"),
        "win_rate": summary.get("win_rate"),
        "avg_trade_return": summary.get("avg_trade_return"),
    }


def replay_delta(fixed65: dict[str, Any], gross55: dict[str, Any]) -> dict[str, Any]:
    return {
        "total_return_delta": round(n(gross55.get("total_return")) - n(fixed65.get("total_return")), 6),
        "max_drawdown_delta": round(n(gross55.get("max_drawdown")) - n(fixed65.get("max_drawdown")), 6),
        "win_rate_delta": round(n(gross55.get("win_rate")) - n(fixed65.get("win_rate")), 6),
        "avg_trade_return_delta": round(n(gross55.get("avg_trade_return")) - n(fixed65.get("avg_trade_return")), 6),
    }


def monitor_rows(args: argparse.Namespace) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in ranking_files(resolve_path(args.rankings_dir)):
        allocation = allocation_snapshot(
            path,
            args.top_n,
            args.production_gross_cap,
            args.shadow_gross_cap,
            args.max_position_weight,
        )
        production_gross = n(allocation.get("production_target_gross_from_latest_ranking"))
        shadow_gross = n(allocation.get("gross55_shadow_target_gross_from_latest_ranking"))
        rows.append(
            {
                "ranking_date": allocation.get("ranking_date"),
                "ranking_path": allocation.get("ranking_path"),
                "market_regime": allocation.get("latest_market_regime"),
                "ranking_requested_gross": allocation.get("ranking_requested_gross"),
                "production_target_gross": production_gross,
                "gross55_shadow_target_gross": shadow_gross,
                "gross_target_delta": round(shadow_gross - production_gross, 6),
                "entry_weight_changed": allocation.get("entry_weight_changed_on_latest_ranking"),
                "top1": (allocation.get("items") or [{}])[0],
            }
        )
    return rows


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    changed = [row for row in rows if row.get("entry_weight_changed")]
    deltas = [n(row.get("gross_target_delta")) for row in rows]
    regimes: dict[str, int] = {}
    for row in rows:
        label = str(row.get("market_regime") or "UNKNOWN")
        regimes[label] = regimes.get(label, 0) + 1
    return {
        "ranking_days": len(rows),
        "would_reduce_exposure_days": len(changed),
        "would_reduce_exposure_rate": round(len(changed) / len(rows), 6) if rows else None,
        "avg_gross_target_delta": round(sum(deltas) / len(deltas), 6) if deltas else None,
        "min_gross_target_delta": round(min(deltas), 6) if deltas else None,
        "max_gross_target_delta": round(max(deltas), 6) if deltas else None,
        "regime_counts": dict(sorted(regimes.items())),
    }


def decide(summary: dict[str, Any], dry_run: dict[str, Any], model_hash: str | None, expected_hash: str) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if dry_run.get("shadow_status") != "READY_FOR_OPERATIONAL_SHADOW_MONITOR":
        reasons.append("gross55 operational dry-run is not ready")
    if model_hash != expected_hash:
        reasons.append("model hash changed")
    if int(summary.get("ranking_days") or 0) <= 0:
        reasons.append("no ranking days found")
    if reasons:
        return "BLOCKED", reasons
    if int(summary.get("would_reduce_exposure_days") or 0) <= 0:
        return "MONITOR_ACTIVE_NO_RECENT_EXPOSURE_CHANGE", []
    return "MONITOR_ACTIVE_RECENT_EXPOSURE_REDUCTION", []


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    dry_run_path = resolve_path(args.dry_run)
    dry_run = read_json(dry_run_path)
    model_path = resolve_path(args.model)
    model_hash = sha256(model_path) if model_path.exists() else None
    rows = monitor_rows(args)
    row_summary = summarize_rows(rows)
    fixed65 = compact_replay(resolve_path(args.fixed65_replay))
    gross55 = compact_replay(resolve_path(args.gross55_replay))
    monitor_status, reasons = decide(row_summary, dry_run, model_hash, args.expected_model_sha256)
    min_ranking_days = 20
    min_matured_1d_days = 10
    matured_1d_days = int(gross55.get("daily_count") or 0)
    sample_ready = int(row_summary.get("ranking_days") or 0) >= min_ranking_days and matured_1d_days >= min_matured_1d_days
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
            "rankings_dir": repo_path(resolve_path(args.rankings_dir)),
            "dry_run": repo_path(dry_run_path),
            "fixed65_replay": repo_path(resolve_path(args.fixed65_replay)),
            "gross55_replay": repo_path(resolve_path(args.gross55_replay)),
            "model": repo_path(model_path),
            "actual_model_sha256": model_hash,
            "expected_model_sha256": args.expected_model_sha256,
        },
        "summary": {
            **row_summary,
            "next_gate": "CONTINUE_DAILY_SHADOW_MONITOR_UNTIL_MINIMUM_SAMPLE" if monitor_status != "BLOCKED" else "FIX_BLOCKERS",
            "sample_policy": {
                "min_ranking_days": min_ranking_days,
                "min_matured_1d_days": min_matured_1d_days,
                "current_matured_1d_days": matured_1d_days,
                "sample_ready_for_default_review": sample_ready,
            },
            "minimum_sample_note": "近期正式榜只有少量成熟結果；未達 sample policy 前不能升預設，只能累積 shadow monitor。",
        },
        "recent_1d_replay": {
            "fixed65": fixed65,
            "gross55": gross55,
            "delta": replay_delta(fixed65, gross55),
            "maturity_note": "只包含 features 已成熟的 ranking；最新 ranking 若沒有 D+1 價格會被 skipped。",
        },
        "rows": rows,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    replay = payload["recent_1d_replay"]
    lines = [
        "# Gross55 Daily Shadow Monitor Batch",
        "",
        f"- status: `{payload['status']}`",
        f"- monitor_status: `{payload['monitor_status']}`",
        f"- ranking_days: `{summary.get('ranking_days')}`",
        f"- would_reduce_exposure_days: `{summary.get('would_reduce_exposure_days')}`",
        f"- avg_gross_target_delta: `{pct(summary.get('avg_gross_target_delta'))}`",
        f"- next_gate: `{summary.get('next_gate')}`",
        f"- sample_ready_for_default_review: `{summary.get('sample_policy', {}).get('sample_ready_for_default_review')}`",
        "",
        "## Recent 1D Replay",
        "",
        f"- fixed65: total {pct(replay['fixed65'].get('total_return'))}, DD {pct(replay['fixed65'].get('max_drawdown'))}",
        f"- gross55: total {pct(replay['gross55'].get('total_return'))}, DD {pct(replay['gross55'].get('max_drawdown'))}",
        f"- delta: total {pct(replay['delta'].get('total_return_delta'))}, DD {pct(replay['delta'].get('max_drawdown_delta'))}",
        "",
        "## Daily Rows",
        "",
        "| Date | Regime | Requested | Production | Gross55 | Delta | Changed | Top1 |",
        "|---|---|---:|---:|---:|---:|---|---|",
    ]
    for row in payload["rows"]:
        top1 = row.get("top1") or {}
        lines.append(
            "| {date} | {regime} | {requested} | {production} | {gross55} | {delta} | {changed} | {top1} |".format(
                date=row.get("ranking_date"),
                regime=row.get("market_regime"),
                requested=pct(row.get("ranking_requested_gross")),
                production=pct(row.get("production_target_gross")),
                gross55=pct(row.get("gross55_shadow_target_gross")),
                delta=pct(row.get("gross_target_delta")),
                changed=row.get("entry_weight_changed"),
                top1=f"{top1.get('stock_id', '')} {top1.get('stock_name', '')}".strip(),
            )
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- 不改 Top10 名單。",
            "- 不改正式 ranking CSV。",
            "- 不改 Clawd 訊息。",
            "- 不改模型。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = (
        resolve_path(args.output)
        if args.output
        else PROJECT_ROOT / "artifacts" / "model_experiments" / f"gross55_daily_shadow_monitor_batch_{args.date}.json"
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
                "ranking_days": payload["summary"].get("ranking_days"),
                "would_reduce_exposure_days": payload["summary"].get("would_reduce_exposure_days"),
            },
            ensure_ascii=False,
        )
    )
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
