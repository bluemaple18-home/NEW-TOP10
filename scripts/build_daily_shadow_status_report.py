#!/usr/bin/env python3
"""彙整每日 shadow monitor 狀態。

這份報告只讀既有 shadow artifact，不改 Top10、不改 ranking score、不改模型。
用途是把目前到底有幾條觀測分支、哪條最接近 review、下一步要累積什麼樣本講清楚。
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
SCHEMA_VERSION = "daily-shadow-status-report.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build daily shadow status report")
    parser.add_argument("--date", default=date.today().isoformat())
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
        [
            path
            for path in OUTPUT_DIR.glob(pattern)
            if re.search(r"_\d{4}-\d{2}-\d{2}\.json$", path.name)
        ]
    )
    return files[-1] if files else None


def n(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def gross55_branch() -> dict[str, Any]:
    path = latest("gross55_daily_shadow_monitor_batch_*.json")
    payload = read_json(path)
    summary = payload.get("summary") or {}
    policy = summary.get("sample_policy") or {}
    ranking_days = int(summary.get("ranking_days") or 0)
    matured = int(policy.get("current_matured_1d_days") or 0)
    min_ranking = int(policy.get("min_ranking_days") or 20)
    min_matured = int(policy.get("min_matured_1d_days") or 10)
    return {
        "branch_id": "gross55_exposure_shadow",
        "category": "active_daily_monitor",
        "status": payload.get("monitor_status") or "MISSING",
        "artifact": repo_path(path),
        "what_it_tests": "同樣 Top10，把 portfolio 總曝險影子壓到 55%，觀察是否降低回撤。",
        "current_evidence": {
            "ranking_days": ranking_days,
            "would_reduce_exposure_days": summary.get("would_reduce_exposure_days"),
            "would_reduce_exposure_rate": summary.get("would_reduce_exposure_rate"),
            "avg_gross_target_delta": summary.get("avg_gross_target_delta"),
            "current_matured_1d_days": matured,
        },
        "review_gate": {
            "review_type": "default_profile_review",
            "sample_ready": bool(policy.get("sample_ready_for_default_review")),
            "min_ranking_days": min_ranking,
            "ranking_days_remaining": max(0, min_ranking - ranking_days),
            "min_matured_1d_days": min_matured,
            "matured_1d_days_remaining": max(0, min_matured - matured),
        },
        "next_action": "每日累積 shadow monitor；達樣本門檻後才能 review 是否變成保守曝險 profile。",
        "production_allowed": False,
    }


def capital_entry_branch() -> dict[str, Any]:
    path = latest("capital_entry_quality_daily_shadow_monitor_batch_*.json")
    payload = read_json(path)
    summary = payload.get("summary") or {}
    policy = summary.get("sample_policy") or {}
    ranking_days = int(summary.get("ranking_days") or 0)
    min_ranking = int(policy.get("min_ranking_days") or 20)
    return {
        "branch_id": "capital_entry_quality_shadow",
        "category": "active_daily_monitor",
        "status": payload.get("monitor_status") or "MISSING",
        "artifact": repo_path(path),
        "what_it_tests": "同樣 Top10，影子檢查哪些股票比較像適合今天進場。",
        "current_evidence": {
            "ranking_days": ranking_days,
            "avg_balanced_eligible_count": summary.get("avg_balanced_eligible_count"),
            "avg_conservative_eligible_count": summary.get("avg_conservative_eligible_count"),
            "balanced_has_any_days": summary.get("balanced_has_any_days"),
            "conservative_has_any_days": summary.get("conservative_has_any_days"),
        },
        "review_gate": {
            "review_type": "entry_filter_review",
            "sample_ready": bool(policy.get("sample_ready_for_default_review")),
            "min_ranking_days": min_ranking,
            "ranking_days_remaining": max(0, min_ranking - ranking_days),
            "min_matured_1d_days": None,
            "matured_1d_days_remaining": None,
        },
        "next_action": "繼續每日監控；未做長期 replay / promotion review 前不可改正式入場資格。",
        "production_allowed": False,
    }


def candidate_trail10_branch() -> dict[str, Any]:
    path = latest("candidate_trail10_daily_shadow_monitor_*.json")
    overlap_path = latest("overlap_first_daily_recommendation_shadow_*.json")
    payload = read_json(path)
    overlap_payload = read_json(overlap_path)
    summary = payload.get("summary") or {}
    policy = payload.get("policy") or {}
    overlap_summary = overlap_payload.get("summary") or {}
    return {
        "branch_id": "candidate_trail10_shadow",
        "category": "active_daily_monitor",
        "status": payload.get("monitor_status") or "MISSING",
        "artifact": repo_path(path),
        "what_it_tests": "新 candidate ranking + trail10 出場規則若作為每日觀察系統，今天會選誰、跟正式榜差多少。",
        "current_evidence": {
            "production_ranking_date": summary.get("production_ranking_date"),
            "candidate_ranking_date": summary.get("candidate_ranking_date"),
            "overlap_count": summary.get("overlap_count"),
            "candidate_only_count": summary.get("candidate_only_count"),
            "actionable_count": summary.get("actionable_count"),
            "trailing_stop_pct": policy.get("trailing_stop_pct"),
            "min_event_holding_days": policy.get("min_event_holding_days"),
            "max_holding_days": policy.get("max_holding_days"),
            "overlap_first_artifact": repo_path(overlap_path),
            "overlap_first_status": overlap_payload.get("shadow_status"),
            "overlap_first_overlap_count": overlap_summary.get("overlap_count"),
            "overlap_first_merged_count": overlap_summary.get("merged_count"),
        },
        "review_gate": {
            "review_type": "candidate_ranking_trail10_shadow_review",
            "sample_ready": False,
            "min_ranking_days": 20,
            "ranking_days_remaining": 20,
            "min_matured_1d_days": None,
            "matured_1d_days_remaining": None,
        },
        "next_action": "每天累積 candidate+trail10 shadow artifact；未進 production review 前不可改正式推播。",
        "production_allowed": False,
    }


def research_only_branches() -> list[dict[str, Any]]:
    alpha_path = latest("alpha_candidate_overlay_replay_constrained_blend030_*.json")
    alpha = read_json(alpha_path)
    alpha_summary = alpha.get("summary") or {}
    chip_path = latest("chip_warning_replay_aggregate_*.json")
    chip = read_json(chip_path)
    chip_summary = chip.get("summary") or {}
    chip_readiness_path = latest("chip_flow_readiness_report_*.json")
    chip_readiness = read_json(chip_readiness_path)
    chip_decision = chip_readiness.get("decision") or {}
    chip_composite_path = latest("chip_composite_warning_report_top10_20d_*.json") or latest("chip_composite_warning_report_*.json")
    chip_composite = read_json(chip_composite_path)
    chip_composite_summary = chip_composite.get("summary") or {}
    long_path = latest("operational_long_rule_validation_report_*.json")
    long_report = read_json(long_path)
    long_summary = long_report.get("summary") or {}
    return [
        {
            "branch_id": "alpha_candidate_overlay",
            "category": "research_monitor_only",
            "status": alpha.get("decision") or "MISSING",
            "artifact": repo_path(alpha_path),
            "what_it_tests": "alpha rerank 是否能改善 Top10。",
            "current_evidence": {
                "return_delta": alpha_summary.get("return_delta"),
                "positive_fold_count": alpha_summary.get("positive_fold_count"),
                "avg_overlap_ratio": alpha_summary.get("avg_overlap_ratio"),
            },
            "next_action": "已降級 MONITOR_ONLY；不要再鑽，除非有新特徵或新樣本。",
            "production_allowed": False,
        },
        {
            "branch_id": "sector45_and_rank_bucket",
            "category": "research_monitor_only",
            "status": long_summary.get("sector45_status") or "MISSING",
            "artifact": repo_path(long_path),
            "what_it_tests": "產業集中上限與 rank bucket 是否能改善風險。",
            "current_evidence": {
                "sector45_status": long_summary.get("sector45_status"),
                "top3_status": long_summary.get("top3_status"),
            },
            "next_action": "sector45 / top3 只當分層觀察，不改正式 Top10。",
            "production_allowed": False,
        },
        {
            "branch_id": "chip_warning_only",
            "category": "research_monitor_only",
            "status": chip_decision.get("production_status") or (chip.get("decision") or {}).get("status") or "MISSING",
            "artifact": repo_path(chip_readiness_path or chip_path),
            "what_it_tests": "籌碼 warning 是否能提示風險；目前只保留研究 overlay，不作大盤主判斷、推薦排名或正式提醒。",
            "current_evidence": {
                "target_date_count": chip_summary.get("target_date_count"),
                "deduped_observation_count": chip_summary.get("deduped_observation_count"),
                "aggregate_decision": (chip.get("decision") or {}).get("status"),
                "composite_artifact": repo_path(chip_composite_path),
                "composite_decision": (chip_composite.get("decision") or {}).get("status"),
                "composite_group_counts": chip_composite_summary.get("group_counts"),
                "first_promotable_shape": chip_decision.get("first_promotable_shape"),
            },
            "next_action": "停止推 chip_flow 正式 warning；主線轉測 price/rank/volume/overheat reversal exit signal，chip_flow 只當輔助文字或研究 overlay。",
            "production_allowed": False,
        },
    ]


def closest_branch(branches: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [row for row in branches if row.get("category") == "active_daily_monitor"]
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda row: (
            int((row.get("review_gate") or {}).get("ranking_days_remaining") or 999),
            int((row.get("review_gate") or {}).get("matured_1d_days_remaining") or 999),
        ),
    )


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    branches = [gross55_branch(), capital_entry_branch(), candidate_trail10_branch(), *research_only_branches()]
    active = [row for row in branches if row["category"] == "active_daily_monitor"]
    research = [row for row in branches if row["category"] == "research_monitor_only"]
    closest = closest_branch(branches)
    historical_path = latest("shadow_historical_evidence_*.json")
    historical = read_json(historical_path)
    historical_summary = historical.get("summary") or {}
    historical_waiting_only = historical_summary.get("waiting_only")
    next_operational_step = "繼續 daily shadow monitor；gross55 最接近第一次 review，但還沒達樣本門檻。"
    if historical_waiting_only is False:
        next_operational_step = "不要只等每日樣本；先用歷史證據把 gross55 / capital_entry_quality 送 review 決策，forward monitor 作近期確認。"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK",
        "contract": {
            "report_only": True,
            "changes_production_top10_membership": False,
            "changes_risk_adjusted_score": False,
            "changes_production_ranking": False,
            "changes_clawd_message": False,
            "changes_model": False,
            "enables_auto_retrain": False,
            "default_allowed": False,
        },
        "summary": {
            "active_daily_monitor_count": len(active),
            "research_monitor_only_count": len(research),
            "total_branch_count": len(branches),
            "closest_to_review": closest["branch_id"] if closest else None,
            "closest_review_gate": closest.get("review_gate") if closest else None,
            "historical_evidence_artifact": repo_path(historical_path),
            "historical_waiting_only": historical_waiting_only,
            "historical_supported_branches": historical_summary.get("branches_with_historical_support", []),
            "production_ready_branch_count": 0,
            "next_operational_step": next_operational_step,
            "training_schedule_status": "candidate training/retrain remains manual; daily automation only runs ranking and shadow monitors",
        },
        "branches": branches,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Daily Shadow Status Report",
        "",
        f"- status: `{payload['status']}`",
        f"- active_daily_monitor_count: `{summary['active_daily_monitor_count']}`",
        f"- research_monitor_only_count: `{summary['research_monitor_only_count']}`",
        f"- closest_to_review: `{summary['closest_to_review']}`",
        f"- historical_waiting_only: `{summary.get('historical_waiting_only')}`",
        f"- production_ready_branch_count: `{summary['production_ready_branch_count']}`",
        f"- next_operational_step: {summary['next_operational_step']}",
        f"- training_schedule_status: {summary['training_schedule_status']}",
        "",
        "| Branch | Category | Status | Next Action |",
        "|---|---|---|---|",
    ]
    for row in payload["branches"]:
        lines.append(f"| {row['branch_id']} | {row['category']} | {row['status']} | {row['next_action']} |")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- 不改 Top10。",
            "- 不改 ranking score。",
            "- 不改正式推播。",
            "- 不改模型。",
            "- 不啟用 auto retrain。",
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
        else OUTPUT_DIR / f"daily_shadow_status_{args.date}.json"
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
