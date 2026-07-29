"""Research Fog Map 的純資料轉換與 payload 組裝。"""

from __future__ import annotations

import hashlib
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from typing import Any

from app.research.map_contract import (
    apply_run_history,
    build_combo_registry,
    canonicalize_lifecycle_history,
    canonicalize_lifecycle_topics,
    completed_v2_expansion_count,
    dimension_schema_payload,
    expanded_universe_total,
    infer_insight_level,
    latest_by_combo,
    progress_summary,
    status_from_insight,
    v2_combo_id,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

SCHEMA_VERSION = "research-fog-map.v2"
DEFAULT_SCENARIO_COUNT = 81
FAMILY_CENTERS = {
    "ranking_source": (16, 36),
    "entry_setup": (26, 72),
    "exit_rule": (40, 28),
    "capital_sizing": (48, 76),
    "regime": (58, 42),
    "sector_industry": (70, 34),
    "liquidity": (78, 70),
    "warning_message": (88, 52),
}

FAMILY_GROUPS = [
    {
        "id": "ranking_source",
        "label": "排名來源",
        "description": "候選 ranking 來源與資料切片",
    },
    {
        "id": "entry_setup",
        "label": "進場條件",
        "description": "進場條件、setup 假說與候選訊號",
    },
    {
        "id": "exit_rule",
        "label": "出場規則",
        "description": "停損、停利、持有期與出場規則",
    },
    {
        "id": "capital_sizing",
        "label": "資金配置",
        "description": "資金配置、曝險上限與 sizing 相關研究",
    },
    {
        "id": "regime",
        "label": "市場狀態",
        "description": "市場狀態、牛熊區間與 regime guard",
    },
    {
        "id": "sector_industry",
        "label": "產業主題",
        "description": "產業、主題、類股情境與 feature group",
    },
    {
        "id": "liquidity",
        "label": "流動性",
        "description": "流動性、成交品質與可交易性",
    },
    {
        "id": "warning_message",
        "label": "風險警示",
        "description": "外部 review、風險警示與待補證據",
    },
]

STATUS_LEGEND = [
    {
        "id": "pending",
        "label": "未探索",
        "color": "fog_gray",
        "hex": "#7c8797",
        "description": "未探索或仍在 queue 中",
    },
    {
        "id": "low_information",
        "label": "已探索",
        "color": "blue",
        "hex": "#5cc8ff",
        "description": "已探索，但目前只有普通資訊",
    },
    {
        "id": "rejected",
        "label": "已淘汰",
        "color": "red",
        "hex": "#ff5f73",
        "description": "明確淘汰或等待新證據",
    },
    {
        "id": "follow_up_signal",
        "label": "待追蹤",
        "color": "yellow",
        "hex": "#ffd166",
        "description": "有報酬改善但風險升高，需要 follow-up",
    },
    {
        "id": "effective_insight",
        "label": "有效洞察",
        "color": "green",
        "hex": "#73f7a4",
        "description": "有有效 insight，可保留為研究證據",
    },
    {
        "id": "next_stage_candidate",
        "label": "下階候選",
        "color": "purple",
        "hex": "#b28cff",
        "description": "可進下一階段研究",
    },
    {
        "id": "breakthrough_candidate",
        "label": "突破候選",
        "color": "gold",
        "hex": "#ffcc4d",
        "description": "候選主線突破口",
    },
]


def build_burn_down_progress(
    rollup: dict[str, Any],
    *,
    source: str | None,
    expanded_total: int,
    executed_processed: int,
) -> dict[str, Any]:
    summary = rollup.get("summary") if isinstance(rollup.get("summary"), dict) else {}
    count_keys = [
        "executed_replay_count",
        "equivalence_inherited_count",
        "rule_pruned_count",
        "unsupported_count",
        "low_information_count",
        "next_stage_count",
        "rejected_count",
        "representative_replay_pending_count",
    ]
    counts = {key: int(summary.get(key) or 0) for key in count_keys}
    classified_total = int(summary.get("rollup_classified_total") or sum(counts.values()))
    full_total = int(summary.get("full_universe_total") or expanded_total)
    return {
        "schema_version": "research-map-burn-down-progress.v1",
        "source": source,
        "source_date": rollup.get("date"),
        "full_universe_total": full_total,
        "classified_total": classified_total,
        "classified_pending": max(0, full_total - classified_total),
        "classified_progress_pct": round(classified_total / full_total, 6) if full_total else 0.0,
        "executed_progress_count": executed_processed,
        "executed_progress_pct": round(executed_processed / max(1, expanded_total), 6),
        "counts": counts,
        "active_representative_queue_count": int(summary.get("active_representative_queue_count") or 0),
        "deferred_low_priority_count": int(summary.get("deferred_low_priority_count") or 0),
        "unsupported_category_counts": summary.get("unsupported_category_counts") if isinstance(summary.get("unsupported_category_counts"), dict) else {},
        "unsupported_reason_top_counts": summary.get("unsupported_reason_top_counts") if isinstance(summary.get("unsupported_reason_top_counts"), dict) else {},
        "artifact_blocker_count": int(summary.get("artifact_blocker_count") or 0),
        "artifact_blocker_category_counts": summary.get("artifact_blocker_category_counts") if isinstance(summary.get("artifact_blocker_category_counts"), dict) else {},
        "artifact_blocker_reason_top_counts": summary.get("artifact_blocker_reason_top_counts") if isinstance(summary.get("artifact_blocker_reason_top_counts"), dict) else {},
        "artifact_blocker_source": summary.get("artifact_blocker_source"),
        "artifact_blocker_source_status": summary.get("artifact_blocker_source_status"),
        "controlled_grid_drain": rollup.get("controlled_grid_drain") if isinstance(rollup.get("controlled_grid_drain"), dict) else {},
        "baseline_blocker_cleared": summary.get("baseline_blocker_cleared"),
        "controlled_grid_drain_ready": summary.get("controlled_grid_drain_ready"),
        "controlled_grid_drain_status": summary.get("controlled_grid_drain_status"),
    }


def safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def safe_number(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def sanitize_action(value: Any) -> str:
    text = safe_text(value, "manual_review")
    replacements = {
        "promote_to_longer_replay_candidate": "advance_to_longer_replay_candidate",
        "promotion": "advancement",
        "promote": "advance",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text


def clean_repoish_path(value: Any) -> str | None:
    text = safe_text(value).strip()
    if not text:
        return None
    path = Path(text)
    if path.is_absolute():
        try:
            return str(path.resolve().relative_to(PROJECT_ROOT))
        except ValueError:
            return f"external:{path.name}"
    return text


def classify_family(topic: dict[str, Any]) -> str:
    text = " ".join(
        [
            safe_text(topic.get("family")),
            safe_text(topic.get("title")),
            safe_text(topic.get("candidate_dir")),
            " ".join(safe_text(item) for item in topic.get("reasons", []) if item is not None),
        ]
    ).lower()
    # 先判斷較明確的研究主題，避免所有 ranking variant 都被粗略塞進 sector/liquidity。
    if any(key in text for key in ["stop_smoke", " stop", "exit", "take_profit", "drawdown", "horizon"]):
        return "exit_rule"
    if any(key in text for key in ["regime", "bull", "bear"]):
        return "regime"
    if any(key in text for key in ["gross", "capital", "sizing", "exposure", "position", "sector_cap"]):
        return "capital_sizing"
    if any(key in text for key in ["candidate_subset", "overlap_first", "production_subset"]):
        return "ranking_source"
    if any(key in text for key in ["entry", "setup", "candidate_subset"]):
        return "entry_setup"
    if any(key in text for key in ["sector", "industry", "theme", "feature_group"]):
        return "sector_industry"
    if any(key in text for key in ["liquidity", "volume", "turnover"]):
        return "liquidity"
    if any(key in text for key in ["warning", "message", "external review", "blocked"]):
        return "warning_message"
    return "ranking_source"


def classify_status(topic: dict[str, Any], outcome: dict[str, Any] | None) -> dict[str, str]:
    manager_status = safe_text(topic.get("manager_status") or topic.get("status") or "candidate")
    decision = safe_text((outcome or {}).get("decision") or topic.get("last_decision"))
    run_count = int(safe_number(topic.get("run_count"), 0))
    if manager_status == "rejected" or decision == "REJECTED_BY_STRATEGY_MATRIX":
        return {"id": "rejected", "color": "red", "label": "已淘汰"}
    if manager_status == "partial_needs_followup" or decision == "PARTIAL_SCORE_ONLY":
        return {"id": "follow_up_signal", "color": "yellow", "label": "待追蹤"}
    if manager_status == "confirmed_for_next_replay" or decision == "CONFIRMED_FOR_NEXT_REPLAY":
        score_delta = safe_number((outcome or {}).get("score_delta"), 0)
        return (
            {"id": "breakthrough_candidate", "color": "gold", "label": "突破候選"}
            if score_delta >= 0.15
            else {"id": "next_stage_candidate", "color": "purple", "label": "下階候選"}
        )
    if manager_status == "blocked_missing_evidence":
        return {"id": "low_information", "color": "blue", "label": "低資訊量"}
    if run_count > 0:
        return {"id": "low_information", "color": "blue", "label": "低資訊量"}
    return {"id": "pending", "color": "fog_gray", "label": "未探索"}


def node_position(topic_id: str, family_id: str, family_index: int, sibling_index: int, sibling_count: int) -> dict[str, float]:
    digest = hashlib.sha1(topic_id.encode("utf-8")).hexdigest()
    seed = int(digest[:8], 16)
    center_x, center_y = FAMILY_CENTERS.get(family_id, (50, 50))
    ring = math.floor(math.sqrt(sibling_index))
    slots_before = ring * ring
    slot = sibling_index - slots_before
    slots_in_ring = max(1, ring * 2 + 1)
    angle = (2 * math.pi * slot / slots_in_ring) + family_index * 0.42 + (seed % 11) * 0.025
    radius = 3.4 + ring * 4.2
    if sibling_count > 24 and family_id in {"sector_industry", "liquidity"}:
        radius = 3.2 + ring * 3.45
    jitter_x = ((seed % 9) - 4) * 0.24
    jitter_y = (((seed >> 4) % 9) - 4) * 0.24
    x = center_x + math.cos(angle) * radius + jitter_x
    y = center_y + math.sin(angle) * radius + jitter_y
    return {"x": round(max(3, min(97, x)), 2), "y": round(max(9, min(91, y)), 2)}


def outcome_by_topic_id(daily_quota: dict[str, Any]) -> dict[str, dict[str, Any]]:
    outcomes: dict[str, dict[str, Any]] = {}
    for run in daily_quota.get("topic_runs", []) if isinstance(daily_quota.get("topic_runs"), list) else []:
        topic = run.get("topic") if isinstance(run.get("topic"), dict) else {}
        topic_id = topic.get("topic_id")
        outcome = run.get("outcome") if isinstance(run.get("outcome"), dict) else {}
        if topic_id:
            outcomes[str(topic_id)] = outcome
    return outcomes


def scenario_summary(outcome: dict[str, Any] | None) -> dict[str, Any]:
    candidate = (outcome or {}).get("candidate") if isinstance((outcome or {}).get("candidate"), dict) else {}
    baseline = (outcome or {}).get("baseline") if isinstance((outcome or {}).get("baseline"), dict) else {}
    scenario_count = int(safe_number(candidate.get("scenario_count") or baseline.get("scenario_count"), DEFAULT_SCENARIO_COUNT))
    return {
        "scenario_count": scenario_count,
        "candidate_positive_return_count": candidate.get("positive_return_count"),
        "candidate_negative_return_count": candidate.get("negative_return_count"),
        "best_scenario_id": candidate.get("best_scenario_id") or baseline.get("best_scenario_id"),
        "best_horizon": candidate.get("best_horizon") or baseline.get("best_horizon"),
    }


def delta_summary(outcome: dict[str, Any] | None) -> dict[str, Any]:
    outcome = outcome or {}
    return {
        "score_delta": outcome.get("score_delta"),
        "return_delta": outcome.get("return_delta"),
        "drawdown_delta": outcome.get("drawdown_delta"),
    }


def fixture_topics() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    statuses = ["pending", "rejected", "follow_up_signal", "low_information", "pending", "pending", "rejected", "pending"]
    families = [item["id"] for item in FAMILY_GROUPS]
    for index, family in enumerate(families):
        status = statuses[index % len(statuses)]
        rows.append(
            {
                "topic_id": f"fixture-topic-{index + 1:02d}",
                "title": f"範例研究節點 {index + 1}",
                "family": family,
                "manager_status": "candidate",
                "status_override": status,
                "score": 30 + index * 4,
                "candidate_dir": f"fixtures/research/{family}",
                "ranking_file_count": 8 + index,
                "reasons": ["範例 fallback", "來源 artifact 缺失"],
                "run_count": 0 if status == "pending" else 1,
                "last_decision": "FIXTURE",
            }
        )
    return rows


def build_nodes(topics: list[dict[str, Any]], outcomes: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for topic in topics:
        family_id = safe_text(topic.get("family")) if topic.get("family") in {item["id"] for item in FAMILY_GROUPS} else classify_family(topic)
        topic["_map_family"] = family_id
        by_family[family_id].append(topic)

    nodes: list[dict[str, Any]] = []
    family_index = {item["id"]: index for index, item in enumerate(FAMILY_GROUPS)}
    for family in FAMILY_GROUPS:
        family_id = family["id"]
        family_topics = sorted(by_family.get(family_id, []), key=lambda row: (-safe_number(row.get("score")), safe_text(row.get("topic_id"))))
        for sibling_index, topic in enumerate(family_topics):
            topic_id = safe_text(topic.get("topic_id"))
            outcome = outcomes.get(topic_id)
            if topic.get("status_override"):
                status = next(item for item in STATUS_LEGEND if item["id"] == topic["status_override"])
                status_info = {"id": status["id"], "color": status["color"], "label": status["label"]}
            else:
                status_info = classify_status(topic, outcome)
            scenario = scenario_summary(outcome)
            position = node_position(topic_id, family_id, family_index[family_id], sibling_index, len(family_topics))
            nodes.append(
                {
                    "topic_id": topic_id,
                    "lifecycle_topic_id": topic.get("lifecycle_topic_id"),
                    "title": safe_text(topic.get("title"), topic_id),
                    "family": family_id,
                    "family_label": family["label"],
                    "status": status_info["id"],
                    "status_color": status_info["color"],
                    "status_label": status_info["label"],
                    "last_decision": safe_text((outcome or {}).get("decision") or topic.get("last_decision"), "not_run"),
                    "run_count": int(safe_number(topic.get("run_count"), 0)),
                    "candidate_dir": clean_repoish_path(topic.get("candidate_dir")),
                    "next_action": sanitize_action(topic.get("next_action")),
                    "score": safe_number(topic.get("score"), 0),
                    "ranking_file_count": int(safe_number(topic.get("ranking_file_count"), 0)),
                    "reasons": [safe_text(item) for item in topic.get("reasons", [])[:4]],
                    "metrics": delta_summary(outcome),
                    "scenario": scenario,
                    "position": position,
                }
            )
    return nodes


STATUS_PRIORITY = {
    "breakthrough_candidate": 7,
    "next_stage_candidate": 6,
    "effective_insight": 5,
    "follow_up_signal": 4,
    "rejected": 3,
    "low_information": 2,
    "pending": 1,
}


def aggregate_nodes_from_scenarios(nodes: list[dict[str, Any]], scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_topic: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for scenario in scenarios:
        by_topic[safe_text(scenario.get("topic_id"))].append(scenario)
    legend_by_id = {item["id"]: item for item in STATUS_LEGEND}
    for node in nodes:
        rows = by_topic.get(node["topic_id"], [])
        explored = [row for row in rows if row.get("status") != "pending"]
        if rows:
            best = max(rows, key=lambda row: STATUS_PRIORITY.get(safe_text(row.get("status")), 0))
            status_id = safe_text(best.get("status"), "pending")
            status = legend_by_id.get(status_id, legend_by_id["pending"])
            latest = max(explored, key=lambda row: safe_text(row.get("finished_at"))) if explored else None
            node["status"] = status["id"]
            node["status_color"] = status["color"]
            node["status_label"] = status["label"]
            node["run_count"] = len(explored)
            node["last_decision"] = safe_text((latest or {}).get("decision"), "not_run")
            node["metrics"] = {
                "score_delta": (latest or {}).get("score_delta"),
                "return_delta": (latest or {}).get("return_delta"),
                "drawdown_delta": (latest or {}).get("drawdown_delta"),
            }
            node["scenario"] = {
                "scenario_count": len(rows),
                "explored_count": len(explored),
                "artifact_count": sum(1 for row in rows if row.get("artifact_path")),
            }
    return nodes


def summary_from_nodes(nodes: list[dict[str, Any]], progress: dict[str, Any]) -> dict[str, Any]:
    progress_summary = progress.get("summary") if isinstance(progress.get("summary"), dict) else {}
    status_counts = Counter(node["status"] for node in nodes)
    total_topics = int(progress_summary.get("total_topics") or len(nodes))
    processed_topics = int(
        progress_summary.get("processed_topics")
        or sum(1 for node in nodes if node["status"] != "pending")
    )
    pending_topics = int(progress_summary.get("pending_topics") or status_counts.get("pending", 0))
    followup_topics = int(progress_summary.get("followup_signal_topics") or status_counts.get("follow_up_signal", 0))
    rejected_topics = int(progress_summary.get("rejected_topics") or status_counts.get("rejected", 0))
    scenario_universe = total_topics * DEFAULT_SCENARIO_COUNT
    processed_scenarios = processed_topics * DEFAULT_SCENARIO_COUNT
    progress_pct = round(processed_topics / total_topics, 4) if total_topics else 0.0
    return {
        "total_topics": total_topics,
        "processed_topics": processed_topics,
        "pending_topics": pending_topics,
        "followup_signal_topics": followup_topics,
        "rejected_topics": rejected_topics,
        "low_information_topics": status_counts.get("low_information", 0),
        "next_stage_topics": status_counts.get("next_stage_candidate", 0),
        "breakthrough_topics": status_counts.get("breakthrough_candidate", 0),
        "estimated_scenario_universe": scenario_universe,
        "estimated_processed_scenarios": processed_scenarios,
        "scenario_count_per_topic": DEFAULT_SCENARIO_COUNT,
        "progress_pct": progress_pct,
        "progress_bar": progress_summary.get("progress_bar") or progress_bar(processed_topics, total_topics),
    }


def progress_bar(done: int, total: int, width: int = 24) -> str:
    if total <= 0:
        return "." * width
    filled = round(width * done / total)
    return "#" * filled + "." * (width - filled)


def build_family_summary(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_family: dict[str, Counter[str]] = defaultdict(Counter)
    for node in nodes:
        by_family[node["family"]][node["status"]] += 1
    rows = []
    for family in FAMILY_GROUPS:
        counts = by_family.get(family["id"], Counter())
        rows.append(
            {
                **family,
                "total": sum(counts.values()),
                "statuses": dict(sorted(counts.items())),
            }
        )
    return rows


def build_mission_queue(
    nodes: list[dict[str, Any]],
    queue_payload: dict[str, Any],
    progress_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    by_id = {node["topic_id"]: node for node in nodes}
    queue_rows = queue_payload.get("actions") if isinstance(queue_payload.get("actions"), list) else []
    if not queue_rows:
        queue_rows = progress_payload.get("next_batch") if isinstance(progress_payload.get("next_batch"), list) else []
    missions: list[dict[str, Any]] = []
    for row in queue_rows[:12]:
        topic_id = safe_text(row.get("topic_id"))
        node = by_id.get(topic_id)
        family = node.get("family_label") if node else classify_family(row).replace("_", " ").title()
        ranking_files = node.get("ranking_file_count") if node else int(safe_number(row.get("ranking_file_count"), 0))
        status = node.get("status") if node else safe_text(row.get("manager_status") or "pending")
        score = node.get("score") if node else safe_number(row.get("score"), 0)
        if status == "follow_up_signal":
            reason = "已有追蹤訊號；建議放大回測視窗或補風險檢查"
        elif status == "pending":
            reason = "高分但仍未探索；可擴大戰爭迷霧覆蓋"
        elif status == "low_information":
            reason = "證據不足；需補資料後才能分類"
        else:
            reason = "可執行的研究佇列項目"
        missions.append(
            {
                "combo_id": row.get("combo_id"),
                "topic_id": topic_id,
                "family": family,
                "score": score,
                "ranking_file_count": ranking_files,
                "next_action": sanitize_action(row.get("next_action") or (node or {}).get("next_action")),
                "reason": reason,
            }
        )
    return missions


def build_active_expansion_queue(
    topics: list[dict[str, Any]],
    records: list[dict[str, Any]],
    *,
    parent: dict[str, Any],
    parent_evidence: str | None,
) -> list[dict[str, Any]]:
    if parent.get("decision") != "KEEP_SHADOW_MONITOR":
        return []
    comparable = parent.get("comparable_window") if isinstance(parent.get("comparable_window"), dict) else {}
    candidate_dir = safe_text(comparable.get("candidate_rankings_dir"))
    topic = next((row for row in topics if safe_text(row.get("candidate_dir")) == candidate_dir), None)
    if topic is None:
        topic = next((row for row in topics if "liquidity_quality_candidate_universe" in safe_text(row.get("candidate_dir"))), None)
    if topic is None:
        return []

    regime_gates = ["ALL", "BIG_BULL_ONLY", "BIG_BULL_HIGH_CHOPPY", "EXCLUDE_RISK_OFF_PANIC"]
    risk_guards = ["NONE", "RISK_OFF_CASH_RAISE", "RISK_OFF_DISABLE", "PANIC_DISABLE"]
    entry_filters = ["LOG_GATE", "PERCENTILE_GATE", "LOG_GATE_NON_WORSENING"]
    group_exposures = ["none", "0.35", "0.55"]
    queue: list[dict[str, Any]] = []
    latest_records = latest_by_combo(records)
    for group_exposure in group_exposures:
        for regime_gate in regime_gates:
            for risk_guard in risk_guards:
                for entry_filter in entry_filters:
                    dimensions = {
                        "horizon": "3",
                        "stop_loss": "none",
                        "take_profit": "0.25",
                        "group_exposure": group_exposure,
                        "regime_gate": regime_gate,
                        "risk_guard": risk_guard,
                        "entry_filter": entry_filter,
                    }
                    combo = v2_combo_id(topic, dimensions)
                    record = latest_records.get(combo)
                    insight = infer_insight_level(record)
                    status = status_from_insight(insight)
                    queue.append(
                        {
                            "schema_version": "research-map-expansion-queue.v2",
                            "map_version": "v2",
                            "stage": "LIQUIDITY-REPLAY-02",
                            "parent_evidence": parent_evidence,
                            "topic_id": topic.get("topic_id"),
                            "candidate_dir": clean_repoish_path(topic.get("candidate_dir")),
                            "combo_id": combo,
                            "dimensions": dimensions,
                            "status": status["id"] if record else "pending",
                            "reason": "risk-capped liquidity component replay candidate",
                            "status_color": status["color"] if record else "fog_gray",
                            "status_label": status["label"] if record else "未探索",
                            "insight_level": insight if record else "unexplored",
                            "run_status": (record or {}).get("status"),
                            "decision": (record or {}).get("decision"),
                            "return_delta": (record or {}).get("return_delta"),
                            "drawdown_delta": (record or {}).get("drawdown_delta"),
                            "score_delta": (record or {}).get("score_delta"),
                            "artifact_path": (record or {}).get("artifact_path"),
                            "finished_at": (record or {}).get("finished_at"),
                        }
                    )
    return queue


def build_unlit_representative_queue(
    topics: list[dict[str, Any]],
    combos: list[dict[str, Any]],
    records: list[dict[str, Any]],
    *,
    per_topic: int = 24,
) -> list[dict[str, Any]]:
    """挑出完整宇宙中尚未執行的 deterministic 代表格，供前端點擊定位。"""
    latest_records = latest_by_combo(records)
    schema = dimension_schema_payload()
    expansion_values = [
        {
            "regime_gate": regime_gate,
            "risk_guard": risk_guard,
            "entry_filter": entry_filter,
        }
        for regime_gate, risk_guard, entry_filter in product(
            schema["dimension_values"]["regime_gate"],
            schema["dimension_values"]["risk_guard"],
            schema["dimension_values"]["entry_filter"],
        )
        if {
            "regime_gate": regime_gate,
            "risk_guard": risk_guard,
            "entry_filter": entry_filter,
        }
        != schema["default_coordinates"]
    ]
    combos_by_topic: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for combo in combos:
        combos_by_topic[safe_text(combo.get("topic_id"))].append(combo)

    representatives: list[dict[str, Any]] = []
    for topic in topics:
        topic_id = safe_text(topic.get("topic_id"))
        base_rows = combos_by_topic.get(topic_id) or []
        if not base_rows:
            continue
        topic_seed = int(hashlib.sha1(topic_id.encode("utf-8")).hexdigest()[:8], 16)
        picked = 0
        attempts = 0
        candidate_total = len(base_rows) * len(expansion_values)
        while picked < per_topic and attempts < candidate_total:
            base = base_rows[(topic_seed + attempts * 7) % len(base_rows)]
            extra = expansion_values[(topic_seed + attempts * 11) % len(expansion_values)]
            dimensions = {**(base.get("dimensions") or {}), **extra}
            combo = v2_combo_id(topic, dimensions)
            if combo not in latest_records:
                representatives.append(
                    {
                        "schema_version": "research-map-unlit-representative.v1",
                        "map_version": "v2",
                        "stage": "FULL-UNIVERSE-UNLIT-REPRESENTATIVE",
                        "topic_id": topic_id,
                        "candidate_dir": clean_repoish_path(topic.get("candidate_dir")),
                        "combo_id": combo,
                        "dimensions": dimensions,
                        "status": "pending",
                        "reason": "完整宇宙未點亮代表格；等待 runner 產生 run_history 與 artifact",
                        "status_color": "fog_gray",
                        "status_label": "未點亮",
                        "insight_level": "unexplored",
                        "run_status": "not_run",
                        "decision": "not_run",
                        "artifact_path": None,
                        "representative_index": picked + 1,
                    }
                )
                picked += 1
            attempts += 1
    return representatives


def build_payload(
    date: str,
    *,
    progress: dict[str, Any],
    registry: dict[str, Any],
    queue: dict[str, Any],
    history: dict[str, Any],
    history_records: list[dict[str, Any]],
    weekend_rollup: dict[str, Any] | None,
    weekend_rollup_source: str | None,
    active_expansion_parent: dict[str, Any],
    active_expansion_parent_evidence: str | None,
    source_paths: dict[str, str | None],
    generated_at: str | None = None,
) -> dict[str, Any]:
    topics = registry.get("topics") if isinstance(registry.get("topics"), list) else []
    topics = canonicalize_lifecycle_topics(topics)
    history_records = canonicalize_lifecycle_history(history_records)
    source_mode = "live" if topics else "fixture"
    if not topics:
        topics = fixture_topics()
    combos = build_combo_registry(topics)
    scenarios = apply_run_history(combos, history_records)
    nodes = aggregate_nodes_from_scenarios(build_nodes(topics, {}), scenarios)
    combo_summary = progress_summary(scenarios)
    dimension_schema = dimension_schema_payload()
    expanded_total = expanded_universe_total(len(topics))
    expansion_processed = completed_v2_expansion_count(history_records)
    expanded_processed = combo_summary["explored_combos"] + expansion_processed
    expanded_progress_pct = round(expanded_processed / expanded_total, 6) if expanded_total else 0.0
    burn_down_progress = (
        build_burn_down_progress(
            weekend_rollup,
            source=weekend_rollup_source,
            expanded_total=expanded_total,
            executed_processed=expanded_processed,
        )
        if weekend_rollup is not None
        else None
    )
    summary = {
        "total_topics": len(topics),
        "processed_topics": sum(1 for node in nodes if node.get("run_count", 0) > 0),
        "pending_topics": sum(1 for node in nodes if node.get("run_count", 0) == 0),
        "followup_signal_topics": sum(1 for node in nodes if node.get("status") == "follow_up_signal"),
        "rejected_topics": sum(1 for node in nodes if node.get("status") == "rejected"),
        "low_information_topics": sum(1 for node in nodes if node.get("status") == "low_information"),
        "next_stage_topics": sum(1 for node in nodes if node.get("status") == "next_stage_candidate"),
        "breakthrough_topics": sum(1 for node in nodes if node.get("status") == "breakthrough_candidate"),
        "total_combos": combo_summary["total_combos"],
        "processed_combos": combo_summary["explored_combos"],
        "pending_combos": combo_summary["pending_combos"],
        "followup_signal_combos": combo_summary["followup_signal_combos"],
        "rejected_combos": combo_summary["rejected_combos"],
        "effective_insight_combos": combo_summary["effective_insight_combos"],
        "next_stage_combos": combo_summary["next_stage_combos"],
        "breakthrough_combos": combo_summary["breakthrough_combos"],
        "estimated_scenario_universe": combo_summary["total_combos"],
        "estimated_processed_scenarios": combo_summary["explored_combos"],
        "scenario_count_per_topic": DEFAULT_SCENARIO_COUNT,
        "progress_pct": combo_summary["progress_pct"],
        "progress_bar": progress.get("summary", {}).get("progress_bar") or progress_bar(combo_summary["explored_combos"], combo_summary["total_combos"]),
        "status_counts": combo_summary["status_counts"],
        "base_universe_total": combo_summary["total_combos"],
        "base_processed": combo_summary["explored_combos"],
        "base_progress_pct": combo_summary["progress_pct"],
        "expanded_universe_total": expanded_total,
        "expanded_processed": expanded_processed,
        "v2_expansion_processed": expansion_processed,
        "expanded_pending": max(0, expanded_total - expanded_processed),
        "expanded_progress_pct": expanded_progress_pct,
        "burn_down_classified_total": (burn_down_progress or {}).get("classified_total"),
        "burn_down_progress_pct": (burn_down_progress or {}).get("classified_progress_pct"),
        "dimension_schema_version": dimension_schema["version"],
        "dimension_values": dimension_schema["dimension_values"],
        "dimension_defaults": dimension_schema["default_coordinates"],
        "expanded_scenarios_per_topic": dimension_schema["expanded_scenarios_per_topic"],
        "expansion_multiplier": dimension_schema["expansion_multiplier"],
    }
    family_summary = build_family_summary(nodes)
    mission_queue = build_mission_queue(nodes, queue, progress)
    active_expansion_queue = build_active_expansion_queue(
        topics,
        history_records,
        parent=active_expansion_parent,
        parent_evidence=active_expansion_parent_evidence,
    )
    active_unexecuted_count = sum(1 for row in active_expansion_queue if not (row.get("run_status") == "completed" and row.get("artifact_path")))
    unlit_representative_queue = build_unlit_representative_queue(topics, combos, history_records)
    summary["active_expansion_queue_count"] = len(active_expansion_queue)
    summary["active_expansion_processed"] = sum(1 for row in active_expansion_queue if row.get("run_status") == "completed" and row.get("artifact_path"))
    summary["active_expansion_unexecuted"] = active_unexecuted_count
    summary["unlit_representative_count"] = len(unlit_representative_queue)
    summary["active_expansion_stage"] = "LIQUIDITY-REPLAY-02" if active_expansion_queue else None
    fog_sample_count = 60000
    executed_fog_sample_count = min(18000, max(1200, int(expanded_processed / 3))) if expanded_processed else 0
    unexplored_count = max(0, expanded_total - expanded_processed)
    selected = next((node for node in nodes if node["status"] == "follow_up_signal"), nodes[0] if nodes else None)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "date": date,
        "status": "OK" if source_mode == "live" else "FIXTURE",
        "source_mode": source_mode,
        "fixture": source_mode == "fixture",
        "contract": {
            "research_only": True,
            "does_not_execute_backtests": True,
            "does_not_train_model": True,
            "does_not_change_models_latest_lgbm": True,
            "does_not_change_risk_adjusted_score": True,
            "does_not_change_production_ranking": True,
            "progress_from_run_history_jsonl": True,
            "manual_progress_fill_allowed": False,
        },
        "sources": source_paths,
        "summary": summary,
        "burn_down_progress": burn_down_progress,
        "dimension_schema": dimension_schema,
        "full_universe_fog": {
            "schema_version": "research-map-full-universe-fog.v1",
            "full_universe_count": expanded_total,
            "base_scenario_count": combo_summary["total_combos"],
            "processed_count": expanded_processed,
            "unexplored_count": unexplored_count,
            "clickable_unexecuted_queue_count": active_unexecuted_count,
            "clickable_unlit_representative_count": len(unlit_representative_queue),
            "clickable_representative_total": active_unexecuted_count + len(unlit_representative_queue),
            "sample_count": fog_sample_count,
            "executed_sample_count": executed_fog_sample_count,
            "clickable": False,
            "rendering": "classified_dim_fog_executed_lit_density_layer",
            "visual_semantics": {
                "dim_background": "burn-down classified universe; not clickable and not executed progress",
                "lit_density": "executed progress sampled from run_history.jsonl",
                "queue_points": "clickable unexecuted combo proxies from active_expansion_queue; no artifact until runner finishes",
            },
            "seed": f"{date}:{expanded_total}:{len(topics)}",
        },
        "families": family_summary,
        "family_centers": {key: {"x": value[0], "y": value[1]} for key, value in FAMILY_CENTERS.items()},
        "legend": STATUS_LEGEND,
        "nodes": nodes,
        "scenarios": scenarios,
        "mission_queue": mission_queue,
        "active_expansion_queue": active_expansion_queue,
        "unlit_representative_queue": unlit_representative_queue,
        "history": {
            "run_count": len(history.get("runs", [])) if isinstance(history.get("runs"), list) else 0,
            "latest_run": (history.get("runs") or [])[-1] if isinstance(history.get("runs"), list) and history.get("runs") else None,
        },
        "default_selected_topic_id": selected.get("topic_id") if selected else None,
    }
