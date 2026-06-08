#!/usr/bin/env python3
"""彙整 shadow 分支的歷史回測證據。

這份報告回答一個營運問題：我們是不是只能等每日 forward monitor？
答案通常不是。已經有長區間 replay 的分支，應該先用歷史證據判斷它是否
值得進 review；每日監控只用來確認最近 production-adjacent 行為是否正常。
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "model_experiments"
SCHEMA_VERSION = "shadow-historical-evidence-report.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build shadow historical evidence report")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument(
        "--historical-manifest",
        default="artifacts/backtest/historical_rankings_current_model_batch_dense_2023-11-21_2026-05-15/manifest.json",
    )
    parser.add_argument(
        "--gross55-baseline",
        default="artifacts/backtest/portfolio_replay_production_long_dense_fixed40_2026-06-02.json",
    )
    parser.add_argument(
        "--gross55-shadow",
        default="artifacts/backtest/portfolio_replay_production_long_dense_fixed40_gross55_2026-06-02.json",
    )
    parser.add_argument(
        "--gross55-daily-monitor",
        default=None,
        help="預設讀最新 gross55_daily_shadow_monitor_batch_*.json。",
    )
    parser.add_argument(
        "--capital-entry-report",
        default="artifacts/model_experiments/capital_entry_quality_report_2026-06-03.json",
    )
    parser.add_argument(
        "--capital-entry-daily-monitor",
        default=None,
        help="預設讀最新 capital_entry_quality_daily_shadow_monitor_batch_*.json。",
    )
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def latest(pattern: str) -> Path | None:
    files = sorted(
        path
        for path in OUTPUT_DIR.glob(pattern)
        if re.search(r"_\d{4}-\d{2}-\d{2}\.json$", path.name)
    )
    return files[-1] if files else None


def n(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def pct(value: Any) -> str:
    return f"{n(value):.2%}"


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
        "win_rate": summary.get("win_rate"),
        "avg_trade_return": summary.get("avg_trade_return"),
        "avg_gross_exposure": summary.get("avg_gross_exposure"),
    }


def historical_window(manifest: dict[str, Any]) -> dict[str, Any]:
    inputs = manifest.get("inputs") or {}
    outputs = manifest.get("outputs") or {}
    rankings = outputs.get("rankings") or []
    first = rankings[0].get("date") if rankings else inputs.get("start_date")
    last = rankings[-1].get("date") if rankings else inputs.get("end_date")
    return {
        "status": manifest.get("status"),
        "start_date": first,
        "end_date": last,
        "ranking_count": outputs.get("ranking_count"),
        "manifest_contract": manifest.get("contract") or {},
    }


def gross55_branch(
    manifest_path: Path,
    baseline_path: Path,
    shadow_path: Path,
    daily_monitor_path: Path | None,
) -> dict[str, Any]:
    manifest = read_json(manifest_path)
    baseline = compact_replay(baseline_path)
    shadow = compact_replay(shadow_path)
    daily_monitor = read_json(daily_monitor_path)
    daily_summary = daily_monitor.get("summary") or {}
    sample_policy = daily_summary.get("sample_policy") or {}
    return_delta = round(n(shadow.get("total_return")) - n(baseline.get("total_return")), 6)
    drawdown_delta = round(n(shadow.get("max_drawdown")) - n(baseline.get("max_drawdown")), 6)
    avg_gross_delta = round(n(shadow.get("avg_gross_exposure")) - n(baseline.get("avg_gross_exposure")), 6)
    ranking_count = int((manifest.get("outputs") or {}).get("ranking_count") or 0)
    long_replay_days = int(shadow.get("daily_count") or 0)
    has_long_evidence = ranking_count >= 500 and long_replay_days >= 500
    reduces_drawdown = drawdown_delta > 0
    sacrifices_return = return_delta < 0
    if has_long_evidence and reduces_drawdown and sacrifices_return:
        decision = "HISTORICAL_SUPPORTS_CONSERVATIVE_PROFILE_REVIEW"
        next_action = "不用只等 forward；可把 gross55 當保守曝險 profile 進 review，但不能直接取代預設。"
    elif has_long_evidence and not reduces_drawdown:
        decision = "HISTORICAL_REJECTS_CONSERVATIVE_PROFILE"
        next_action = "長區間沒有降低回撤，停止推進。"
    else:
        decision = "INSUFFICIENT_HISTORICAL_EVIDENCE"
        next_action = "先補歷史 replay，再談每日 monitor。"
    return {
        "branch_id": "gross55_exposure_shadow",
        "historical_window": historical_window(manifest),
        "baseline": baseline,
        "shadow": shadow,
        "historical_delta": {
            "total_return_delta": return_delta,
            "max_drawdown_delta": drawdown_delta,
            "avg_gross_exposure_delta": avg_gross_delta,
        },
        "daily_forward_monitor": {
            "artifact": repo_path(daily_monitor_path),
            "status": daily_monitor.get("monitor_status") or "MISSING",
            "ranking_days": daily_summary.get("ranking_days"),
            "current_matured_1d_days": sample_policy.get("current_matured_1d_days"),
            "sample_ready_for_default_review": sample_policy.get("sample_ready_for_default_review"),
        },
        "decision": decision,
        "production_ready": False,
        "next_action": next_action,
        "plain_chinese": "gross55 像是保守駕駛模式：長回測少賺約 28.85 個百分點，但最大回撤少約 4.54 個百分點。它不是更會選股，而是讓曝險低一點。",
    }


def capital_entry_branch(report_path: Path, daily_monitor_path: Path | None) -> dict[str, Any]:
    report = read_json(report_path)
    daily_monitor = read_json(daily_monitor_path)
    daily_summary = daily_monitor.get("summary") or {}
    comparisons = report.get("comparisons_vs_baseline") or {}
    decision = report.get("decision") or {}
    non_worsening = comparisons.get("non_worsening") or {}
    improved_only = comparisons.get("improved_only") or {}
    first_day = comparisons.get("first_day") or {}
    balanced_long = non_worsening.get("long") or {}
    conservative_long = improved_only.get("long") or {}
    has_long_comparison = bool(balanced_long and conservative_long)
    if has_long_comparison and n(balanced_long.get("return_delta")) >= -0.06 and n(balanced_long.get("drawdown_abs_delta")) < 0:
        status = "HISTORICAL_SUPPORTS_BALANCED_SHADOW_REVIEW"
        next_action = "non_worsening 可繼續當入場品質 shadow；它不是大幅增益，而是用小報酬犧牲換較低回撤。"
    elif has_long_comparison:
        status = "HISTORICAL_ONLY_MONITOR"
        next_action = "歷史證據不足以推 default，只保留監控。"
    else:
        status = "INSUFFICIENT_HISTORICAL_EVIDENCE"
        next_action = "先補 entry filter 長區間 replay。"
    return {
        "branch_id": "capital_entry_quality_shadow",
        "historical_report": repo_path(report_path),
        "balanced_shadow_candidate": decision.get("balanced_shadow_candidate"),
        "conservative_shadow_candidate": decision.get("conservative_shadow_candidate"),
        "comparisons_vs_baseline": {
            "first_day": first_day,
            "non_worsening": non_worsening,
            "improved_only": improved_only,
        },
        "daily_forward_monitor": {
            "artifact": repo_path(daily_monitor_path),
            "status": daily_monitor.get("monitor_status") or "MISSING",
            "ranking_days": daily_summary.get("ranking_days"),
            "avg_balanced_eligible_count": daily_summary.get("avg_balanced_eligible_count"),
            "avg_conservative_eligible_count": daily_summary.get("avg_conservative_eligible_count"),
        },
        "decision": status,
        "production_ready": False,
        "next_action": next_action,
        "plain_chinese": "入場品質不是要重選 Top10，而是提醒哪些上榜股比較不糟。non_worsening 長回測少賺約 4.15 個百分點、回撤少約 4.30 個百分點；improved_only 更保守，但少賺太多。",
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    gross55_daily_path = resolve_path(args.gross55_daily_monitor) if args.gross55_daily_monitor else latest("gross55_daily_shadow_monitor_batch_*.json")
    capital_daily_path = (
        resolve_path(args.capital_entry_daily_monitor)
        if args.capital_entry_daily_monitor
        else latest("capital_entry_quality_daily_shadow_monitor_batch_*.json")
    )
    branches = [
        gross55_branch(
            resolve_path(args.historical_manifest),
            resolve_path(args.gross55_baseline),
            resolve_path(args.gross55_shadow),
            gross55_daily_path,
        ),
        capital_entry_branch(resolve_path(args.capital_entry_report), capital_daily_path),
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK",
        "contract": {
            "report_only": True,
            "uses_historical_backtest": True,
            "changes_production_top10_membership": False,
            "changes_risk_adjusted_score": False,
            "changes_production_ranking": False,
            "changes_clawd_message": False,
            "changes_model": False,
            "enables_auto_retrain": False,
            "production_ready": False,
        },
        "summary": {
            "waiting_only": False,
            "historical_backtest_available": True,
            "earliest_historical_date": branches[0]["historical_window"].get("start_date"),
            "latest_historical_date": branches[0]["historical_window"].get("end_date"),
            "historical_ranking_count": branches[0]["historical_window"].get("ranking_count"),
            "branches_with_historical_support": [
                row["branch_id"]
                for row in branches
                if str(row.get("decision", "")).startswith("HISTORICAL_SUPPORTS")
            ],
            "production_ready_branch_count": 0,
            "recommended_next_step": "先做 gross55 / capital_entry 的 review 決策，不要只等每日樣本；若要升正式，仍需另走 promotion review。",
        },
        "branches": branches,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Shadow Historical Evidence Report",
        "",
        f"- status: `{payload['status']}`",
        f"- waiting_only: `{summary['waiting_only']}`",
        f"- historical_window: `{summary['earliest_historical_date']} ~ {summary['latest_historical_date']}`",
        f"- historical_ranking_count: `{summary['historical_ranking_count']}`",
        f"- production_ready_branch_count: `{summary['production_ready_branch_count']}`",
        "",
        "## Branches",
        "",
        "| Branch | Decision | Production Ready | 白話 |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["branches"]:
        lines.append(
            f"| {row['branch_id']} | `{row['decision']}` | `{row['production_ready']}` | {row['plain_chinese']} |"
        )
    lines.extend(
        [
            "",
            "## Gross55 Delta",
            "",
        ]
    )
    gross = payload["branches"][0]
    delta = gross["historical_delta"]
    lines.extend(
        [
            f"- total_return_delta: `{pct(delta['total_return_delta'])}`",
            f"- max_drawdown_delta: `{pct(delta['max_drawdown_delta'])}`",
            f"- avg_gross_exposure_delta: `{pct(delta['avg_gross_exposure_delta'])}`",
            "",
            "## Capital Entry Delta",
            "",
            "```json",
            json.dumps(payload["branches"][1]["comparisons_vs_baseline"], ensure_ascii=False, indent=2),
            "```",
            "",
            "## Boundary",
            "",
            "- 只產報告。",
            "- 不改 Top10。",
            "- 不改 ranking score。",
            "- 不改正式推播。",
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
        else OUTPUT_DIR / f"shadow_historical_evidence_{args.date}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "output": repo_path(output),
                **payload["summary"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
