#!/usr/bin/env python3
"""建立策略 archetype 證據地圖。

這份報告把 7 維迷霧組合先整理成 PM 可讀的策略區域，不執行 replay、
不改 ranking，也不宣告 promotion ready。它只回答：現有證據支持哪些
策略區域、缺口在哪裡、下一批研究應該清哪一類。
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
SCHEMA_VERSION = "strategy-archetype-evidence-map.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build strategy archetype evidence map")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--artifacts-dir", default=ARTIFACTS_DIR, type=Path)
    parser.add_argument("--output-json", default=None, type=Path)
    parser.add_argument("--output-md", default=None, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifacts_dir = resolve_path(args.artifacts_dir)
    payload = build_payload(args.date, artifacts_dir)
    output_json = resolve_path(args.output_json) if args.output_json else default_json_path(artifacts_dir, args.date)
    output_md = resolve_path(args.output_md) if args.output_md else default_markdown_path(artifacts_dir, args.date)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output_md.write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "output": repo_path(output_json),
                "archetype_count": len(payload["archetypes"]),
            },
            ensure_ascii=False,
        )
    )
    return 0


def build_payload(run_date: str, artifacts_dir: Path) -> dict[str, Any]:
    fog_map, fog_path = load_json_with_path(artifacts_dir / "research_map" / "research_fog_map_latest.json")
    fog_verification, fog_verification_path = load_json_with_path(
        artifacts_dir / "research_map" / "research_fog_map_verification_latest.json"
    )
    weekend_rollup, weekend_path = load_json_with_path(
        artifacts_dir / "weekend_training" / f"weekend_training_rollup_{run_date}.json"
    )
    campaign, campaign_path = load_json_with_path(
        artifacts_dir / "autonomous_research" / f"research_campaign_progress_{run_date}.json"
    )
    next_queue, next_queue_path = load_json_with_path(artifacts_dir / "autonomous_research" / "next_action_queue.json")
    manager, manager_path = load_json_with_path(artifacts_dir / "autonomous_research" / "manager_summary.json")
    performance, performance_path = load_json_with_path(artifacts_dir / f"daily_performance_review_{run_date}.json")
    decision_quality, decision_quality_path = load_json_with_path(artifacts_dir / f"decision_quality_{run_date}.json")

    followup_signals = extract_followup_signals(campaign)
    next_actions = [item for item in list_value(next_queue.get("actions")) if isinstance(item, dict)]
    queue_by_archetype = classify_records(next_actions)
    followup_by_archetype = classify_records(followup_signals)

    archetypes = [
        build_high_entry_chase_archetype(
            next_actions=queue_by_archetype["high_entry_chase_protection"],
            followup_signals=followup_by_archetype["high_entry_chase_protection"],
            performance=performance,
        ),
        build_selloff_protection_archetype(
            next_actions=queue_by_archetype["selloff_protection"],
            followup_signals=followup_by_archetype["selloff_protection"],
            weekend_rollup=weekend_rollup,
            performance=performance,
        ),
        build_strong_trend_hold_archetype(
            next_actions=queue_by_archetype["strong_trend_hold"],
            followup_signals=followup_by_archetype["strong_trend_hold"],
        ),
        build_concentration_control_archetype(
            next_actions=queue_by_archetype["concentration_control"],
            followup_signals=followup_by_archetype["concentration_control"],
        ),
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_date": run_date,
        "status": "NEEDS_RESEARCH_EXECUTION",
        "market_thesis": {
            "label": "強趨勢 + 高波動 + 科技集中",
            "meaning": "先研究如何保留強趨勢，同時避開追高、急殺與科技集中反噬。",
            "confirmed_by_pm": True,
        },
        "execution_boundary": {
            "research_only": True,
            "does_not_execute_backtests": True,
            "does_not_change_ranking": True,
            "does_not_train_model": True,
            "does_not_publish": True,
            "does_not_mark_promotion_ready": True,
        },
        "global_evidence_state": build_global_state(
            fog_map=fog_map,
            fog_verification=fog_verification,
            weekend_rollup=weekend_rollup,
            campaign=campaign,
            manager=manager,
            next_actions=next_actions,
        ),
        "archetypes": archetypes,
        "recommended_execution_order": [
            "high_entry_chase_protection",
            "selloff_protection",
            "strong_trend_hold",
            "concentration_control",
        ],
        "source_artifacts": [
            repo_path(path)
            for path in [
                fog_path,
                fog_verification_path,
                weekend_path,
                campaign_path,
                next_queue_path,
                manager_path,
                performance_path,
                decision_quality_path,
            ]
            if path
        ],
    }


def build_global_state(
    *,
    fog_map: dict[str, Any],
    fog_verification: dict[str, Any],
    weekend_rollup: dict[str, Any],
    campaign: dict[str, Any],
    manager: dict[str, Any],
    next_actions: list[dict[str, Any]],
) -> dict[str, Any]:
    fog_summary = dict_value(fog_map.get("summary"))
    burn_down = dict_value(fog_map.get("burn_down_progress"))
    weekend_summary = dict_value(weekend_rollup.get("summary"))
    campaign_summary = dict_value(campaign.get("summary"))
    return {
        "fog_map_status": fog_map.get("status"),
        "fog_verification_status": fog_verification.get("status"),
        "base_universe": {
            "processed": fog_summary.get("base_processed") or campaign_summary.get("base_processed"),
            "total": fog_summary.get("base_universe_total") or campaign_summary.get("base_universe_total"),
            "progress_pct": fog_summary.get("base_progress_pct") or campaign_summary.get("base_progress_pct"),
        },
        "expanded_universe": {
            "processed": fog_summary.get("expanded_processed") or campaign_summary.get("expanded_processed"),
            "total": fog_summary.get("expanded_universe_total") or campaign_summary.get("expanded_universe_total"),
            "progress_pct": fog_summary.get("expanded_progress_pct") or campaign_summary.get("expanded_progress_pct"),
        },
        "burn_down_classification": {
            "classified_total": burn_down.get("classified_total") or weekend_summary.get("rollup_classified_total"),
            "full_universe_total": burn_down.get("full_universe_total") or weekend_summary.get("full_universe_total"),
            "classified_progress_pct": burn_down.get("classified_progress_pct"),
            "counts": burn_down.get("counts") or {},
        },
        "unsupported": {
            "count": weekend_summary.get("unsupported_count"),
            "category_counts": weekend_summary.get("unsupported_category_counts") or {},
            "reason_top_counts": weekend_summary.get("unsupported_reason_top_counts") or {},
            "non_unblockable_count": weekend_summary.get("unsupported_non_unblockable_count"),
        },
        "manager": {
            "status": manager.get("status"),
            "status_counts": manager.get("status_counts") or {},
            "next_action_count": manager.get("next_action_count") or len(next_actions),
        },
    }


def build_high_entry_chase_archetype(
    *,
    next_actions: list[dict[str, Any]],
    followup_signals: list[dict[str, Any]],
    performance: dict[str, Any],
) -> dict[str, Any]:
    findings = performance_findings(performance, ["D+1", "D+3", "進場", "回撤", "hit_rate"])
    return archetype(
        archetype_id="high_entry_chase_protection",
        priority=1,
        label="高位防追高型",
        intent="強勢股仍可進 Top10，但要避免追在短線過熱點；排除過熱股後必須由 Top11-20/Top21-30 補位。",
        role="defensive_replacement",
        dimension_signature={
            "entry_filter": ["LOG_GATE", "PERCENTILE_GATE", "LOG_GATE_NON_WORSENING"],
            "horizon": ["3", "5"],
            "stop_loss": ["none", "0.08", "0.12"],
            "group_exposure": ["none", "0.35", "0.55"],
            "regime_gate": ["ALL", "BIG_BULL_HIGH_CHOPPY", "EXCLUDE_RISK_OFF_PANIC"],
            "risk_guard": ["NONE", "RISK_OFF_CASH_RAISE"],
        },
        operating_policy={
            "replacement_pool": ["Top11-20", "Top21-30 fallback"],
            "cash_allowed": False,
            "must_preserve_top10_fill": True,
            "not_allowed": ["少報股票假裝降低風險", "直接改 production ranking"],
        },
        current_evidence={
            "next_action_count": len(next_actions),
            "followup_signal_count": len(followup_signals),
            "performance_findings": findings,
            "evidence_status": "PARTIAL_MECHANISM_EVIDENCE",
        },
        interpretation="這一區目前應優先研究 entry_filter 與短 horizon 的交互作用；重點不是少報，而是換股後是否仍保報酬。",
        next_research=[
            "用 Top11-20、Top21-30 fallback 模擬防追高補位，確認 Top10 fill rate 不下降。",
            "比較 D+1/D+3 avg return、hit rate、bucket drawdown，不允許只靠少交易變好。",
            "將有效組合再推到較長窗口 replay，避免只看 2026-06 局部樣本。",
        ],
        representative_actions=compact_actions(next_actions),
        representative_followups=compact_actions(followup_signals),
    )


def build_selloff_protection_archetype(
    *,
    next_actions: list[dict[str, Any]],
    followup_signals: list[dict[str, Any]],
    weekend_rollup: dict[str, Any],
    performance: dict[str, Any],
) -> dict[str, Any]:
    weekend_summary = dict_value(weekend_rollup.get("summary"))
    findings = performance_findings(performance, ["回撤", "D+1", "D+3", "risk", "bucket"])
    return archetype(
        archetype_id="selloff_protection",
        priority=2,
        label="急殺保護型",
        intent="市場突然 risk-off 或 profit-taking 時，允許降曝險/留現金；這是 risk overlay，不是 ranking 補位。",
        role="risk_overlay",
        dimension_signature={
            "regime_gate": ["EXCLUDE_RISK_OFF_PANIC", "RISK_OFF_ONLY", "PANIC_SELLING_ONLY"],
            "risk_guard": ["RISK_OFF_CASH_RAISE", "RISK_OFF_DISABLE", "PANIC_DISABLE"],
            "stop_loss": ["0.08", "0.12"],
            "horizon": ["3", "5"],
            "entry_filter": ["LOG_GATE", "LOG_GATE_NON_WORSENING"],
            "group_exposure": ["none", "0.35", "0.55"],
        },
        operating_policy={
            "cash_allowed": True,
            "must_label_as": "risk_overlay",
            "not_allowed": ["把降曝險包裝成 ranking 命中率提升", "沒有 regime/breadth 證據就開保護"],
        },
        current_evidence={
            "next_action_count": len(next_actions),
            "followup_signal_count": len(followup_signals),
            "performance_findings": findings,
            "unsupported_regime_slice_no_data": dict_value(weekend_summary.get("unsupported_category_counts")).get(
                "UNSUPPORTED_REGIME_SLICE_NO_DATA"
            ),
            "evidence_status": "NEEDS_TRIGGER_VALIDATION",
        },
        interpretation="這一區不能先問股票怎麼挑；要先判斷 risk_guard 是否真的改善急殺，而不是只是少做交易。",
        next_research=[
            "先用已存在 market_context / decision_quality 標記可用 regime/breadth 訊號，TAIFEX 缺資料不可當主觸發。",
            "對 RISK_OFF_CASH_RAISE / RISK_OFF_DISABLE / PANIC_DISABLE 做同窗口比較，拆出報酬、回撤、曝險下降來源。",
            "regime slice 無資料區先維持 unsupported，不硬跑。",
        ],
        representative_actions=compact_actions(next_actions),
        representative_followups=compact_actions(followup_signals),
    )


def build_strong_trend_hold_archetype(
    *,
    next_actions: list[dict[str, Any]],
    followup_signals: list[dict[str, Any]],
) -> dict[str, Any]:
    return archetype(
        archetype_id="strong_trend_hold",
        priority=3,
        label="強趨勢續抱型",
        intent="AI/半導體主線強時，避免過早停利或過度防守錯殺強股。",
        role="offensive_retention",
        dimension_signature={
            "horizon": ["5", "10"],
            "take_profit": ["none", "0.25"],
            "stop_loss": ["none", "0.08", "0.12"],
            "regime_gate": ["ALL", "BIG_BULL_ONLY", "BIG_BULL_HIGH_CHOPPY"],
            "group_exposure": ["none", "0.55"],
            "entry_filter": ["TOPIC_DEFAULT", "LOG_GATE_NON_WORSENING"],
        },
        operating_policy={
            "cash_allowed": False,
            "must_preserve_upside": True,
            "not_allowed": ["只看短線防守就否決長趨勢"],
        },
        current_evidence={
            "next_action_count": len(next_actions),
            "followup_signal_count": len(followup_signals),
            "evidence_status": "SECOND_PRIORITY",
        },
        interpretation="這一區要等防追高與急殺保護的結論回來後再做，否則容易把追高和續抱混在一起。",
        next_research=[
            "比較 horizon 5/10 與 take_profit none/0.25 的相鄰區域，不看單一 lucky combo。",
            "確認停利是否真的穩定報酬，還是過早賣掉強股。",
        ],
        representative_actions=compact_actions(next_actions),
        representative_followups=compact_actions(followup_signals),
    )


def build_concentration_control_archetype(
    *,
    next_actions: list[dict[str, Any]],
    followup_signals: list[dict[str, Any]],
) -> dict[str, Any]:
    return archetype(
        archetype_id="concentration_control",
        priority=4,
        label="科技集中控制型",
        intent="科技主線很強時，group_exposure 要判斷是在保護 bucket，還是在錯殺強族群。",
        role="portfolio_constraint",
        dimension_signature={
            "group_exposure": ["0.35", "0.55"],
            "regime_gate": ["ALL", "BIG_BULL_HIGH_CHOPPY", "EXCLUDE_RISK_OFF_PANIC"],
            "risk_guard": ["NONE", "RISK_OFF_CASH_RAISE"],
            "horizon": ["3", "5", "10"],
            "entry_filter": ["TOPIC_DEFAULT", "LOG_GATE", "LOG_GATE_NON_WORSENING"],
        },
        operating_policy={
            "cash_allowed": False,
            "must_compare_to_unconstrained": True,
            "not_allowed": ["把 sector cap 的報酬下降忽略，只看 drawdown"],
        },
        current_evidence={
            "next_action_count": len(next_actions),
            "followup_signal_count": len(followup_signals),
            "evidence_status": "SECOND_PRIORITY",
        },
        interpretation="這一區暫列第二順位；它依賴防追高/急殺保護先釐清，否則不知道是集中風險還是進場問題。",
        next_research=[
            "先比 group_exposure none / 0.55 / 0.35 的相鄰區域。",
            "把科技/半導體主線日與非主線日分開，不要用單一平均掩蓋 tradeoff。",
        ],
        representative_actions=compact_actions(next_actions),
        representative_followups=compact_actions(followup_signals),
    )


def archetype(
    *,
    archetype_id: str,
    priority: int,
    label: str,
    intent: str,
    role: str,
    dimension_signature: dict[str, list[str]],
    operating_policy: dict[str, Any],
    current_evidence: dict[str, Any],
    interpretation: str,
    next_research: list[str],
    representative_actions: list[dict[str, Any]],
    representative_followups: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "archetype_id": archetype_id,
        "priority": priority,
        "label": label,
        "intent": intent,
        "role": role,
        "dimension_signature": dimension_signature,
        "operating_policy": operating_policy,
        "current_evidence": current_evidence,
        "interpretation": interpretation,
        "next_research": next_research,
        "representative_actions": representative_actions,
        "representative_followups": representative_followups,
    }


def classify_records(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {
        "high_entry_chase_protection": [],
        "selloff_protection": [],
        "strong_trend_hold": [],
        "concentration_control": [],
    }
    for record in records:
        text = json.dumps(record, ensure_ascii=False).lower()
        dimensions = dict_value(record.get("dimensions"))
        if any(token in text for token in ["entry", "log_gate", "percentile_gate", "entry_filter"]):
            result["high_entry_chase_protection"].append(record)
        if any(token in text for token in ["regime", "risk_guard", "risk_off", "panic", "stop_0.08", "stop_loss"]):
            result["selloff_protection"].append(record)
        if dimensions.get("horizon") in {"5", "10"} or any(token in text for token in ["take_profit", "big_bull"]):
            result["strong_trend_hold"].append(record)
        if any(token in text for token in ["sector", "group_exposure", "gc0p35", "gc0p55"]):
            result["concentration_control"].append(record)
    return result


def extract_followup_signals(campaign: dict[str, Any]) -> list[dict[str, Any]]:
    insights = dict_value(campaign.get("insights"))
    signals = [item for item in list_value(insights.get("followup_signals")) if isinstance(item, dict)]
    return signals


def performance_findings(performance: dict[str, Any], keywords: list[str]) -> list[dict[str, str]]:
    findings = []
    for item in list_value(performance.get("findings")):
        if not isinstance(item, dict):
            continue
        text = json.dumps(item, ensure_ascii=False)
        if any(keyword in text for keyword in keywords):
            findings.append(
                {
                    "severity": str(item.get("severity") or ""),
                    "title": str(item.get("title") or ""),
                    "detail": str(item.get("detail") or ""),
                    "suggested_action": str(item.get("suggested_action") or ""),
                }
            )
    return findings[:6]


def compact_actions(records: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    compact = []
    for item in records[:limit]:
        compact.append(
            {
                "topic_id": item.get("topic_id"),
                "candidate_dir": item.get("candidate_dir"),
                "dimensions": item.get("dimensions") or {},
                "manager_status": item.get("manager_status"),
                "next_action": item.get("next_action"),
                "decision": item.get("decision") or item.get("last_decision"),
                "score": item.get("score"),
                "artifact_path": item.get("artifact_path"),
            }
        )
    return compact


def render_markdown(payload: dict[str, Any]) -> str:
    state = dict_value(payload.get("global_evidence_state"))
    expanded = dict_value(state.get("expanded_universe"))
    unsupported = dict_value(state.get("unsupported"))
    lines = [
        f"# Strategy Archetype Evidence Map｜{payload['run_date']}",
        "",
        "## 核心判斷",
        f"- 盤面語意：{payload['market_thesis']['label']}",
        "- 這份報告只整理策略區域與證據缺口，不改 ranking、不訓練模型、不發佈。",
        f"- expanded replay progress：`{expanded.get('processed')}/{expanded.get('total')}`，約 `{expanded.get('progress_pct')}`。",
        f"- unsupported：`{unsupported.get('count')}`；這是已分類不可跑/不應硬跑區，不是待跑清單。",
        "",
        "## 建議執行順序",
    ]
    for index, archetype_id in enumerate(list_value(payload.get("recommended_execution_order")), start=1):
        label = next(
            (item.get("label") for item in list_value(payload.get("archetypes")) if item.get("archetype_id") == archetype_id),
            archetype_id,
        )
        lines.append(f"{index}. `{archetype_id}`｜{label}")
    lines.append("")
    lines.append("## Strategy Archetypes")
    for item in list_value(payload.get("archetypes")):
        evidence = dict_value(item.get("current_evidence"))
        lines.extend(
            [
                "",
                f"### {item.get('priority')}. {item.get('label')}",
                f"- archetype_id：`{item.get('archetype_id')}`",
                f"- 目的：{item.get('intent')}",
                f"- 角色：`{item.get('role')}`",
                f"- 現有 queue：next_action `{evidence.get('next_action_count')}`；followup `{evidence.get('followup_signal_count')}`",
                f"- 證據狀態：`{evidence.get('evidence_status')}`",
                f"- 解讀：{item.get('interpretation')}",
                "- 下一步：",
            ]
        )
        for step in list_value(item.get("next_research")):
            lines.append(f"  - {step}")
    lines.append("")
    lines.append("## Sources")
    for source in list_value(payload.get("source_artifacts")):
        lines.append(f"- `{source}`")
    return "\n".join(lines).rstrip() + "\n"


def load_json_with_path(path: Path) -> tuple[dict[str, Any], Path | None]:
    if not path.exists():
        return {}, None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}, path


def resolve_path(path: Path) -> Path:
    path = path.expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(path)


def default_json_path(artifacts_dir: Path, run_date: str) -> Path:
    return artifacts_dir / "research_council" / f"strategy_archetype_evidence_map_{run_date}.json"


def default_markdown_path(artifacts_dir: Path, run_date: str) -> Path:
    return artifacts_dir / "research_council" / f"strategy_archetype_evidence_map_{run_date}.md"


def dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


if __name__ == "__main__":
    raise SystemExit(main())
