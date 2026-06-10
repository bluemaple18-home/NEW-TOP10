#!/usr/bin/env python3
"""建立策略零件庫第一版。

這份 registry 只整理既有 artifact / reference 的狀態，不重新回測、不改正式 ranking。
目的：把策略拆成可重用零件，避免每次實驗都變成孤島。
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "strategy-component-registry.v1"

STATUS_REUSABLE = "REUSABLE_CANDIDATE"
STATUS_CONDITIONAL = "CONDITIONAL_CANDIDATE"
STATUS_DIAGNOSTIC = "DIAGNOSTIC_ONLY"
STATUS_REJECTED = "REJECTED"
STATUS_DATA_UNAVAILABLE = "DATA_UNAVAILABLE"
STATUS_REFERENCE = "REFERENCE_AVAILABLE"
STATUS_MESSAGE = "MESSAGE_AVAILABLE"
STATUS_NEEDS_TEST = "NEEDS_TEST"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build strategy component registry")
    parser.add_argument("--date", default=date.today().isoformat())
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


def read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv_shape(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {"exists": False}
    frame = pd.read_csv(path, dtype={"stock_id": str})
    result: dict[str, Any] = {
        "exists": True,
        "path": repo_path(path),
        "rows": len(frame),
        "columns": list(frame.columns),
    }
    if "stock_id" in frame.columns:
        result["stock_count"] = int(frame["stock_id"].astype(str).str.zfill(4).nunique())
    if "industry_name" in frame.columns:
        result["industry_count"] = int(frame["industry_name"].dropna().nunique())
    if "sector_name" in frame.columns:
        result["sector_count"] = int(frame["sector_name"].dropna().nunique())
    return result


def feature_coverage() -> dict[str, Any]:
    path = PROJECT_ROOT / "data" / "clean" / "features.parquet"
    if not path.exists():
        return {"exists": False, "path": repo_path(path)}
    frame = pd.read_parquet(path)
    result = {
        "exists": True,
        "path": repo_path(path),
        "rows": len(frame),
        "stock_count": int(frame["stock_id"].astype(str).str.zfill(4).nunique()) if "stock_id" in frame.columns else None,
        "start_date": str(pd.to_datetime(frame["date"]).min().date()) if "date" in frame.columns else None,
        "end_date": str(pd.to_datetime(frame["date"]).max().date()) if "date" in frame.columns else None,
        "coverage": {},
    }
    for column in ["revenue_yoy", "revenue_mom"]:
        if column in frame.columns:
            result["coverage"][column] = {
                "non_null": int(frame[column].notna().sum()),
                "ratio": round(float(frame[column].notna().mean()), 6),
            }
    return result


def artifact(path_text: str) -> tuple[Path, dict[str, Any]]:
    path = PROJECT_ROOT / path_text
    return path, read_json(path)


def n(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def component(
    component_id: str,
    category: str,
    status: str,
    description: str,
    evidence: list[str],
    where_it_helps: list[str] | None = None,
    where_it_hurts: list[str] | None = None,
    allowed_next_use: list[str] | None = None,
    blocked_uses: list[str] | None = None,
    metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "component_id": component_id,
        "category": category,
        "status": status,
        "description": description,
        "evidence": evidence,
        "where_it_helps": where_it_helps or [],
        "where_it_hurts": where_it_hurts or [],
        "allowed_next_use": allowed_next_use or [],
        "blocked_uses": blocked_uses or [],
        "metrics": metrics or {},
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    long_path, long_report = artifact("artifacts/model_experiments/long_candidate_validation_report_2026-06-10.json")
    retention_path, retention = artifact("artifacts/model_experiments/candidate_trail10_retention_diagnostics_2026-06-10.json")
    overlap_100_path, overlap_100 = artifact("artifacts/model_experiments/overlap_first_recommendation_performance_recent_100_2026-06-10.json")
    overlap_6m_path, overlap_6m = artifact("artifacts/model_experiments/overlap_first_recommendation_performance_recent_6m_2026-06-10.json")
    chip_path, chip = artifact("artifacts/model_experiments/chip_flow_readiness_report_2026-06-08.json")
    chip_agg_path, chip_agg = artifact("artifacts/model_experiments/chip_warning_replay_aggregate_2026-06-08.json")

    industry_path = PROJECT_ROOT / "data" / "reference" / "stock_industry_map.csv"
    concept_path = PROJECT_ROOT / "data" / "reference" / "stock_concept_membership.csv"
    notification_path = PROJECT_ROOT / "config" / "notification_industry_buckets.csv"
    regime_long_path = PROJECT_ROOT / "artifacts" / "model_experiments" / "market_regime_history_2023-11-21_2026-05-15.json"
    regime_recent_path = PROJECT_ROOT / "artifacts" / "market_regime_history_2026-06-01.json"
    market_context_path = PROJECT_ROOT / "artifacts" / "market_context_2026-06-09.json"

    retention_summary = retention.get("summary") or {}
    retention_decision = retention.get("decision") or {}
    long_decision = long_report.get("decision") or {}
    overlap_100_comp = (overlap_100.get("comparison") or {}).get("overlap_vs_production") or {}
    overlap_6m_comp = (overlap_6m.get("comparison") or {}).get("overlap_vs_production") or {}
    chip_decision = chip.get("decision") or {}
    chip_agg_decision = chip_agg.get("decision") or {}
    features = feature_coverage()
    revenue_coverage = features.get("coverage", {})

    components = [
        component(
            "candidate_ranking",
            "ranking_source",
            STATUS_CONDITIONAL,
            "current_baseline_candidate_2026-06-08 ranking source。長區間有效，但 2026 近期輸 production。",
            [repo_path(long_path), repo_path(retention_path)],
            where_it_helps=["2025_H1", "2025_H2", "long_window"],
            where_it_hurts=["recent_100", "recent_6m", "2026_YTD_to_0515"],
            allowed_next_use=["conditional_switch_research", "daily_shadow_monitor"],
            blocked_uses=["immediate_production_switch", "unconditional_publish_replacement"],
            metrics={
                "long_return_delta": retention_summary.get("long_return_delta"),
                "long_drawdown_delta": retention_summary.get("long_drawdown_delta"),
                "recent_100_return_delta": retention_summary.get("recent_100_return_delta"),
                "recent_6m_return_delta": retention_summary.get("recent_6m_return_delta"),
            },
        ),
        component(
            "trail10",
            "exit_rule",
            STATUS_REUSABLE,
            "持有滿 5 個交易日後，以高點回落 10% 作移動停利/轉弱線。",
            [repo_path(long_path), repo_path(retention_path)],
            where_it_helps=["candidate_long_window", "drawdown_reduction_vs_production_peer"],
            allowed_next_use=["candidate_trail10_shadow", "conditional_switch_research", "page_explanation"],
            blocked_uses=["personal_position_sell_alert_without_user_holdings"],
            metrics={
                "candidate_long_total_return": retention_summary.get("long_candidate_total_return"),
                "production_long_total_return": retention_summary.get("long_production_total_return"),
                "selected_exit_rule": long_decision.get("selected_exit_rule"),
            },
        ),
        component(
            "overlap_first",
            "ranking_transform",
            STATUS_REJECTED,
            "production Top10 與 candidate Top10 重複者優先的混合排序。",
            [repo_path(overlap_100_path), repo_path(overlap_6m_path)],
            where_it_hurts=["recent_100", "recent_6m"],
            allowed_next_use=["diagnostic_overlap_label_only"],
            blocked_uses=["ranking_replacement", "publish_order_replacement"],
            metrics={
                "recent_100_return_delta": overlap_100_comp.get("return_delta"),
                "recent_100_drawdown_delta": overlap_100_comp.get("drawdown_delta"),
                "recent_6m_return_delta": overlap_6m_comp.get("return_delta"),
                "recent_6m_drawdown_delta": overlap_6m_comp.get("drawdown_delta"),
            },
        ),
        component(
            "chip_flow",
            "risk_overlay",
            STATUS_DIAGNOSTIC,
            "外資、投信、融資融券等籌碼資料；目前只能當診斷或輔助文字，不當正式排名或大盤主判斷。",
            [repo_path(chip_path), repo_path(chip_agg_path)],
            allowed_next_use=["diagnostic_label", "research_overlay"],
            blocked_uses=["production_ranking_score", "primary_market_direction", "standalone_warning_channel"],
            metrics={
                "readiness_status": chip_decision.get("status"),
                "production_status": chip_decision.get("production_status"),
                "aggregate_status": chip_agg_decision.get("status"),
            },
        ),
        component(
            "fundamental_revenue",
            "feature_group",
            STATUS_DATA_UNAVAILABLE,
            "月營收 YoY / MoM 欄位存在，但目前 features coverage 為 0，不能進模型或 ranking。",
            [repo_path(PROJECT_ROOT / "data" / "clean" / "features.parquet")],
            allowed_next_use=["ui_metadata_after_coverage_fix", "future_shadow_feature_after_data_contract"],
            blocked_uses=["model_training_feature", "ranking_score", "promotion_evidence"],
            metrics={
                "revenue_yoy": revenue_coverage.get("revenue_yoy"),
                "revenue_mom": revenue_coverage.get("revenue_mom"),
            },
        ),
        component(
            "industry_map",
            "data_source",
            STATUS_REFERENCE,
            "本地全股票產業 / sector / theme_tags 對照。",
            [repo_path(industry_path)],
            allowed_next_use=["message_annotation", "sector_exposure_analysis", "component_registry_input"],
            blocked_uses=["standalone_alpha_without_replay"],
            metrics=read_csv_shape(industry_path),
        ),
        component(
            "concept_membership",
            "data_source",
            STATUS_REFERENCE,
            "本地股票概念 membership 與 taxonomy。",
            [repo_path(concept_path)],
            allowed_next_use=["message_annotation", "theme_flow_analysis", "component_registry_input"],
            blocked_uses=["standalone_alpha_without_replay"],
            metrics=read_csv_shape(concept_path),
        ),
        component(
            "notification_bucket",
            "message_rule",
            STATUS_MESSAGE,
            "把細產業聚合成小白看得懂的推播資金主題。",
            [repo_path(notification_path)],
            allowed_next_use=["clawd_market_summary", "sector_flow_message"],
            blocked_uses=["model_feature", "ranking_score"],
            metrics=read_csv_shape(notification_path),
        ),
        component(
            "market_regime_history",
            "regime_gate",
            STATUS_NEEDS_TEST,
            "既有 base regime 與 BIG_BULL / HIGH_CHOPPY family 可用於條件式切換研究。",
            [repo_path(regime_long_path), repo_path(regime_recent_path)],
            allowed_next_use=["candidate_trail10_conditional_switch_research", "regime_breakdown"],
            blocked_uses=["new_regime_preset_without_contract"],
            metrics={
                "long_history": (read_json(regime_long_path).get("summary") or {}),
                "recent_history": (read_json(regime_recent_path).get("summary") or {}),
            },
        ),
        component(
            "market_context",
            "data_source",
            STATUS_DIAGNOSTIC,
            "每日大盤上下文 artifact；可供推播摘要，但 6/9 外部 source 有 UNKNOWN / missing。",
            [repo_path(market_context_path)],
            allowed_next_use=["daily_message_market_summary", "diagnostic_context"],
            blocked_uses=["hard_gate_until_source_status_ok"],
            metrics={
                "latest": read_json(market_context_path).get("summary") or {},
                "source_status": read_json(market_context_path).get("source_status") or {},
            },
        ),
    ]

    status_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    for row in components:
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
        category_counts[row["category"]] = category_counts.get(row["category"], 0) + 1

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK",
        "contract": {
            "registry_only": True,
            "uses_existing_artifacts_only": True,
            "changes_production_ranking": False,
            "changes_clawd_message": False,
            "changes_model": False,
            "production_switch_ready": False,
            "promotion_ready": False,
        },
        "summary": {
            "component_count": len(components),
            "status_counts": status_counts,
            "category_counts": category_counts,
            "next_mainline": "conditional_switch_research_for_candidate_trail10",
        },
        "components": components,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Strategy Component Registry",
        "",
        f"- status: `{payload['status']}`",
        f"- component_count: `{payload['summary']['component_count']}`",
        f"- next_mainline: `{payload['summary']['next_mainline']}`",
        "",
        "| Component | Category | Status | Allowed Next Use | Blocked Uses |",
        "|---|---|---|---|---|",
    ]
    for row in payload["components"]:
        lines.append(
            "| {component_id} | {category} | {status} | {allowed} | {blocked} |".format(
                component_id=row["component_id"],
                category=row["category"],
                status=row["status"],
                allowed=", ".join(row["allowed_next_use"]),
                blocked=", ".join(row["blocked_uses"]),
            )
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- 不改正式 ranking。",
            "- 不改推播。",
            "- 不改模型。",
            "- reference available 不等於 alpha validated。",
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
        else PROJECT_ROOT / "artifacts" / "model_experiments" / f"strategy_component_registry_{args.date}.json"
    )
    if output is None:
        raise RuntimeError("output resolution failed")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "output": repo_path(output),
                "component_count": payload["summary"]["component_count"],
                "status_counts": payload["summary"]["status_counts"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
