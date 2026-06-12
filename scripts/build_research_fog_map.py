#!/usr/bin/env python3
"""建立 autonomous research 的遊戲化戰爭迷霧靜態地圖。

這個腳本只整理研究進度與可視化資料，不執行回測、不訓練模型、不改正式 ranking。
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_map_contract import (
    apply_run_history,
    build_combo_registry,
    dimension_schema_payload,
    expanded_universe_total,
    progress_summary,
    read_jsonl,
    v2_combo_id,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = PROJECT_ROOT / "artifacts" / "autonomous_research"
OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "research_map"
SCHEMA_VERSION = "research-fog-map.v1"
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build autonomous research fog-of-war dashboard")
    parser.add_argument("--date", default=datetime.now(timezone.utc).date().isoformat())
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
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
        return None


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


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


def build_active_expansion_queue(topics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    parent_path = PROJECT_ROOT / "artifacts" / "research_reviews" / "liquidity_quality_strict_replay_2026-06-12.json"
    parent = read_json(parent_path)
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
                    queue.append(
                        {
                            "schema_version": "research-map-expansion-queue.v2",
                            "map_version": "v2",
                            "stage": "LIQUIDITY-REPLAY-02",
                            "parent_evidence": repo_path(parent_path),
                            "topic_id": topic.get("topic_id"),
                            "candidate_dir": clean_repoish_path(topic.get("candidate_dir")),
                            "combo_id": v2_combo_id(topic, dimensions),
                            "dimensions": dimensions,
                            "status": "pending",
                            "reason": "risk-capped liquidity component replay candidate",
                        }
                    )
    return queue


def build_payload(date: str) -> dict[str, Any]:
    progress = read_json(SOURCE_DIR / f"research_campaign_progress_{date}.json")
    registry = read_json(SOURCE_DIR / "topic_registry.json")
    queue = read_json(SOURCE_DIR / "next_action_queue.json")
    history = read_json(SOURCE_DIR / "run_history.json")
    history_jsonl_path = SOURCE_DIR / "run_history.jsonl"

    topics = registry.get("topics") if isinstance(registry.get("topics"), list) else []
    source_mode = "live" if topics else "fixture"
    if not topics:
        topics = fixture_topics()
    combos = build_combo_registry(topics)
    history_records = read_jsonl(history_jsonl_path)
    scenarios = apply_run_history(combos, history_records)
    nodes = aggregate_nodes_from_scenarios(build_nodes(topics, {}), scenarios)
    combo_summary = progress_summary(scenarios)
    dimension_schema = dimension_schema_payload()
    expanded_total = expanded_universe_total(len(topics))
    expanded_processed = combo_summary["explored_combos"]
    expanded_progress_pct = round(expanded_processed / expanded_total, 6) if expanded_total else 0.0
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
        "expanded_pending": max(0, expanded_total - expanded_processed),
        "expanded_progress_pct": expanded_progress_pct,
        "dimension_schema_version": dimension_schema["version"],
        "dimension_values": dimension_schema["dimension_values"],
        "dimension_defaults": dimension_schema["default_coordinates"],
        "expanded_scenarios_per_topic": dimension_schema["expanded_scenarios_per_topic"],
        "expansion_multiplier": dimension_schema["expansion_multiplier"],
    }
    family_summary = build_family_summary(nodes)
    mission_queue = build_mission_queue(nodes, queue, progress)
    active_expansion_queue = build_active_expansion_queue(topics)
    summary["active_expansion_queue_count"] = len(active_expansion_queue)
    summary["active_expansion_stage"] = "LIQUIDITY-REPLAY-02" if active_expansion_queue else None
    selected = next((node for node in nodes if node["status"] == "follow_up_signal"), nodes[0] if nodes else None)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
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
        "sources": {
            "progress": repo_path(SOURCE_DIR / f"research_campaign_progress_{date}.json")
            if (SOURCE_DIR / f"research_campaign_progress_{date}.json").exists()
            else None,
            "topic_registry": repo_path(SOURCE_DIR / "topic_registry.json") if (SOURCE_DIR / "topic_registry.json").exists() else None,
            "run_history": repo_path(SOURCE_DIR / "run_history.json") if (SOURCE_DIR / "run_history.json").exists() else None,
            "run_history_jsonl": repo_path(history_jsonl_path) if history_jsonl_path.exists() else None,
            "next_action_queue": repo_path(SOURCE_DIR / "next_action_queue.json") if (SOURCE_DIR / "next_action_queue.json").exists() else None,
        },
        "summary": summary,
        "dimension_schema": dimension_schema,
        "families": family_summary,
        "family_centers": {key: {"x": value[0], "y": value[1]} for key, value in FAMILY_CENTERS.items()},
        "legend": STATUS_LEGEND,
        "nodes": nodes,
        "scenarios": scenarios,
        "mission_queue": mission_queue,
        "active_expansion_queue": active_expansion_queue,
        "history": {
            "run_count": len(history.get("runs", [])) if isinstance(history.get("runs"), list) else 0,
            "latest_run": (history.get("runs") or [])[-1] if isinstance(history.get("runs"), list) and history.get("runs") else None,
        },
        "default_selected_topic_id": selected.get("topic_id") if selected else None,
    }


def render_metric_card(label: str, key: str, suffix: str = "") -> str:
    return f"""
          <article class="metric-card">
            <span>{html.escape(label)}</span>
            <strong data-summary="{html.escape(key)}">0{html.escape(suffix)}</strong>
          </article>"""


def render_html(payload: dict[str, Any]) -> str:
    payload_json = (
        json.dumps(payload, ensure_ascii=False, allow_nan=False)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )
    fixture_banner = (
        '<div class="fixture-banner">範例模式：找不到來源研究 artifact，目前數字只供示意。</div>'
        if payload.get("fixture")
        else ""
    )
    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>研究戰爭迷霧地圖</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #09111f;
      --panel: rgba(16, 27, 45, 0.86);
      --panel-strong: rgba(20, 35, 58, 0.96);
      --line: rgba(142, 176, 216, 0.22);
      --text: #e9f2ff;
      --muted: #8fa4be;
      --cyan: #5cc8ff;
      --red: #ff5f73;
      --yellow: #ffd166;
      --green: #73f7a4;
      --purple: #b28cff;
      --gold: #ffcc4d;
      --fog: #7c8797;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at 28% 30%, rgba(92, 200, 255, 0.18), transparent 22%),
        radial-gradient(circle at 72% 18%, rgba(255, 209, 102, 0.11), transparent 20%),
        radial-gradient(circle at 78% 76%, rgba(178, 140, 255, 0.16), transparent 28%),
        linear-gradient(135deg, #050b15 0%, #091525 45%, #141827 100%);
      color: var(--text);
      letter-spacing: 0;
    }}
    body::before {{
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background-image:
        radial-gradient(circle, rgba(255,255,255,0.7) 0 1px, transparent 1.2px),
        linear-gradient(rgba(92,200,255,0.05) 1px, transparent 1px),
        linear-gradient(90deg, rgba(92,200,255,0.05) 1px, transparent 1px);
      background-size: 78px 78px, 64px 64px, 64px 64px;
      opacity: 0.34;
      mask-image: linear-gradient(to bottom, black, transparent 92%);
    }}
    .app-shell {{
      position: relative;
      width: min(1540px, calc(100vw - 28px));
      margin: 0 auto;
      padding: 22px 0 26px;
    }}
    header {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 18px;
      align-items: end;
      padding: 0 2px 16px;
    }}
    h1 {{
      margin: 0;
      font-size: clamp(28px, 4vw, 54px);
      line-height: 0.96;
      font-weight: 780;
      letter-spacing: 0;
    }}
    .subtitle {{
      margin: 10px 0 0;
      color: var(--muted);
      max-width: 780px;
      line-height: 1.55;
      font-size: 15px;
    }}
    .source-chip {{
      border: 1px solid var(--line);
      background: rgba(13, 23, 38, 0.78);
      padding: 10px 12px;
      border-radius: 8px;
      color: var(--muted);
      font-size: 12px;
      text-align: right;
      min-width: 220px;
    }}
    .source-chip strong {{
      display: block;
      color: var(--text);
      font-size: 14px;
      margin-top: 4px;
    }}
    .fixture-banner {{
      border: 1px solid rgba(255, 209, 102, 0.42);
      background: rgba(255, 209, 102, 0.12);
      color: #ffe3a3;
      border-radius: 8px;
      padding: 10px 12px;
      margin-bottom: 14px;
      font-size: 13px;
    }}
    .dashboard-grid {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) 360px;
      gap: 16px;
      align-items: start;
    }}
    .left-rail {{
      display: grid;
      gap: 14px;
    }}
    .hud {{
      border: 1px solid var(--line);
      background: linear-gradient(135deg, rgba(18, 32, 54, 0.92), rgba(8, 17, 31, 0.76));
      border-radius: 8px;
      padding: 14px;
      backdrop-filter: blur(14px);
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(6, minmax(118px, 1fr));
      gap: 10px;
    }}
    .metric-card {{
      min-height: 76px;
      border: 1px solid rgba(142,176,216,0.18);
      background: rgba(8, 17, 31, 0.62);
      border-radius: 8px;
      padding: 12px;
    }}
    .metric-card span {{
      display: block;
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      line-height: 1.25;
    }}
    .metric-card strong {{
      display: block;
      margin-top: 8px;
      font-size: 24px;
      line-height: 1;
    }}
    .progress-wrap {{
      margin-top: 12px;
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 12px;
      align-items: center;
    }}
    .progress-track {{
      height: 14px;
      border-radius: 999px;
      background: rgba(124, 135, 151, 0.2);
      border: 1px solid rgba(142,176,216,0.2);
      overflow: hidden;
    }}
    .progress-fill {{
      height: 100%;
      width: 0%;
      background: linear-gradient(90deg, var(--cyan), var(--green), var(--gold));
      box-shadow: 0 0 24px rgba(92, 200, 255, 0.5);
    }}
    .progress-label {{
      color: var(--muted);
      font-variant-numeric: tabular-nums;
      font-size: 13px;
    }}
    .map-panel {{
      position: relative;
      min-height: 720px;
      border: 1px solid var(--line);
      background:
        radial-gradient(circle at 52% 50%, rgba(92, 200, 255, 0.16), transparent 16%),
        radial-gradient(circle at 73% 32%, rgba(255, 95, 115, 0.12), transparent 18%),
        radial-gradient(circle at 22% 68%, rgba(178, 140, 255, 0.1), transparent 20%),
        conic-gradient(from 210deg at 52% 51%, rgba(92,200,255,0.05), rgba(255,209,102,0.08), rgba(178,140,255,0.05), rgba(92,200,255,0.05)),
        rgba(8, 16, 30, 0.72);
      border-radius: 8px;
      overflow: hidden;
      cursor: grab;
      touch-action: none;
    }}
    .map-panel.is-dragging {{
      cursor: grabbing;
    }}
    .map-panel.is-point-hover {{
      cursor: pointer;
    }}
    .map-panel.is-point-hover .scenario-canvas {{
      cursor: pointer;
    }}
    .map-panel::before {{
      content: "";
      position: absolute;
      inset: 34px;
      border: 1px solid rgba(92, 200, 255, 0.12);
      border-radius: 50%;
      box-shadow:
        0 0 0 82px rgba(92, 200, 255, 0.025),
        0 0 0 164px rgba(178, 140, 255, 0.018),
        inset 0 0 80px rgba(92, 200, 255, 0.05);
      pointer-events: none;
    }}
    .map-panel::after {{
      content: "";
      position: absolute;
      inset: 0;
      background-image:
        linear-gradient(rgba(92, 200, 255, 0.035) 1px, transparent 1px),
        linear-gradient(90deg, rgba(92, 200, 255, 0.035) 1px, transparent 1px);
      background-size: 88px 88px;
      mask-image: radial-gradient(circle at 52% 50%, black 0 58%, transparent 88%);
      pointer-events: none;
    }}
    .family-bands {{
      position: absolute;
      inset: 0;
      display: block;
      pointer-events: none;
      z-index: 2;
      transform-origin: center;
      transform: translateZ(0);
      transition: none;
      will-change: transform;
    }}
    .map-panel.is-dragging .family-bands,
    .map-panel.is-dragging .starmap {{
      transition: none;
    }}
    .family-band {{
      position: absolute;
      transform: translate(-50%, -50%);
      border: 1px solid rgba(142,176,216,0.16);
      background: rgba(8,17,31,0.62);
      border-radius: 8px;
      padding: 7px 9px;
      color: rgba(233,242,255,0.7);
      font-size: 10px;
      text-transform: uppercase;
      line-height: 1.25;
      white-space: nowrap;
      box-shadow: 0 0 22px rgba(92,200,255,0.07);
    }}
    .starmap {{
      position: absolute;
      inset: 0;
      z-index: 3;
      transform-origin: center;
      transform: translateZ(0);
      transition: none;
      will-change: transform;
      contain: layout paint style;
    }}
    .scenario-canvas {{
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      z-index: 3;
      pointer-events: auto;
    }}
    .star-links {{
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      overflow: visible;
      pointer-events: none;
      z-index: 4;
    }}
    .star-link {{
      stroke: rgba(92, 200, 255, 0.2);
      stroke-width: 0.34;
      vector-effect: non-scaling-stroke;
    }}
    .star-link.is-hot {{
      stroke: rgba(255, 209, 102, 0.48);
      stroke-width: 0.78;
    }}
    .map-core {{
      position: absolute;
      left: 52%;
      top: 51%;
      transform: translate(-50%, -50%);
      width: 132px;
      height: 132px;
      border-radius: 50%;
      border: 1px solid rgba(92, 200, 255, 0.28);
      background:
        radial-gradient(circle, rgba(92, 200, 255, 0.22), transparent 38%),
        rgba(8, 17, 31, 0.32);
      box-shadow: 0 0 42px rgba(92, 200, 255, 0.18), inset 0 0 28px rgba(255, 209, 102, 0.06);
      pointer-events: none;
      z-index: 5;
    }}
    .map-core span {{
      position: absolute;
      inset: 38px 18px auto;
      color: rgba(233,242,255,0.76);
      font-size: 10px;
      text-align: center;
      text-transform: uppercase;
      line-height: 1.25;
    }}
    .node {{
      --node-color: var(--fog);
      position: absolute;
      width: 14px;
      height: 14px;
      transform: translate(-50%, -50%);
      border: 0;
      border-radius: 50%;
      background: var(--node-color);
      box-shadow: 0 0 16px color-mix(in srgb, var(--node-color), transparent 25%);
      cursor: pointer;
      transition: transform 140ms ease, box-shadow 140ms ease, outline-color 140ms ease;
      z-index: 4;
    }}
    .node::after {{
      content: "";
      position: absolute;
      inset: -6px;
      border-radius: 50%;
      border: 1px solid color-mix(in srgb, var(--node-color), transparent 48%);
      opacity: 0.7;
      pointer-events: none;
    }}
    .node:hover,
    .node.is-selected {{
      transform: translate(-50%, -50%) scale(1.18);
      outline: 2px solid rgba(255,255,255,0.72);
      outline-offset: 6px;
      z-index: 7;
    }}
    .node[data-color="fog_gray"] {{ --node-color: #8fa0b6; opacity: calc(var(--o, 0.44) * 0.46); }}
    .node[data-color="blue"] {{ --node-color: #67d4ff; opacity: calc(var(--o, 0.44) * 0.66); }}
    .node[data-color="red"] {{ --node-color: #ff6e82; opacity: calc(var(--o, 0.44) * 0.58); }}
    .node[data-color="yellow"] {{ --node-color: #ffd66e; opacity: calc(var(--o, 0.44) * 0.68); }}
    .node[data-color="green"] {{ --node-color: var(--green); opacity: calc(var(--o, 0.44) * 0.66); }}
    .node[data-color="purple"] {{ --node-color: var(--purple); opacity: calc(var(--o, 0.44) * 0.66); }}
    .node[data-color="gold"] {{ --node-color: #ffd15c; opacity: calc(var(--o, 0.44) * 0.72); }}
    .map-footer {{
      position: absolute;
      left: 14px;
      right: 14px;
      bottom: 12px;
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 12px;
      align-items: end;
      color: var(--muted);
      font-size: 12px;
      pointer-events: none;
      z-index: 5;
    }}
    .family-summary {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 8px;
    }}
    .family-pill {{
      border: 1px solid rgba(142,176,216,0.16);
      background: rgba(8,17,31,0.72);
      border-radius: 8px;
      padding: 8px;
      min-height: 48px;
    }}
    .family-pill strong {{
      display: block;
      color: var(--text);
      font-size: 12px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    aside {{
      display: grid;
      gap: 14px;
    }}
    .panel {{
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 8px;
      padding: 14px;
      backdrop-filter: blur(14px);
    }}
    .panel h2 {{
      margin: 0 0 12px;
      font-size: 15px;
      letter-spacing: 0;
    }}
    .inspector-title {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: start;
    }}
    .status-dot {{
      display: inline-flex;
      width: 12px;
      height: 12px;
      border-radius: 50%;
      background: var(--fog);
      box-shadow: 0 0 14px currentColor;
      flex: 0 0 auto;
      margin-top: 3px;
    }}
    .kv {{
      display: grid;
      grid-template-columns: 118px minmax(0, 1fr);
      gap: 8px;
      padding: 7px 0;
      border-bottom: 1px solid rgba(142,176,216,0.12);
      font-size: 12px;
      line-height: 1.35;
    }}
    .kv span:first-child {{
      color: var(--muted);
    }}
    .kv span:last-child {{
      overflow-wrap: anywhere;
    }}
    .mission-list {{
      display: grid;
      gap: 8px;
      max-height: 390px;
      overflow: auto;
      padding-right: 3px;
    }}
    .mission {{
      border: 1px solid rgba(142,176,216,0.16);
      background: rgba(8,17,31,0.58);
      border-radius: 8px;
      padding: 10px;
      cursor: pointer;
      text-align: left;
    }}
    .mission strong {{
      display: block;
      font-size: 12px;
      overflow-wrap: anywhere;
    }}
    .mission small {{
      display: block;
      color: var(--muted);
      margin-top: 5px;
      line-height: 1.35;
    }}
    .legend-grid {{
      display: grid;
      gap: 7px;
    }}
    .legend-item {{
      display: grid;
      grid-template-columns: 16px minmax(0, 1fr);
      gap: 8px;
      align-items: start;
      font-size: 12px;
      color: var(--muted);
    }}
    .legend-swatch {{
      width: 12px;
      height: 12px;
      border-radius: 50%;
      margin-top: 2px;
      background: var(--fog);
      box-shadow: 0 0 12px currentColor;
    }}
    .legend-item strong {{
      color: var(--text);
      display: block;
      margin-bottom: 2px;
    }}
    @media (max-width: 1180px) {{
      .dashboard-grid {{ grid-template-columns: 1fr; }}
      aside {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .metrics {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
    }}
    @media (max-width: 760px) {{
      .app-shell {{ width: min(100vw - 18px, 760px); padding-top: 14px; }}
      header {{ grid-template-columns: 1fr; }}
      .source-chip {{ text-align: left; min-width: 0; }}
      .metrics {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .map-panel {{ min-height: 560px; }}
      .family-band {{ font-size: 8px; padding: 5px 6px; max-width: 88px; white-space: normal; text-align: center; }}
      .map-core {{ width: 92px; height: 92px; }}
      .map-core span {{ inset: 28px 10px auto; font-size: 8px; }}
      .map-footer {{ grid-template-columns: 1fr; }}
      .family-summary {{ display: none; }}
      aside {{ grid-template-columns: 1fr; }}
      .kv {{ grid-template-columns: 96px minmax(0, 1fr); }}
    }}
    .command-shell {{
      width: min(1920px, calc(100vw - 18px));
      min-height: 100vh;
      margin: 0 auto;
      padding: 10px;
      display: grid;
      grid-template-rows: 104px minmax(590px, 1fr) 232px;
      gap: 10px;
    }}
    .command-top {{
      display: grid;
      grid-template-columns: 500px 260px 250px 240px minmax(320px, 1fr) 190px;
      gap: 12px;
    }}
    .command-card {{
      position: relative;
      border: 1px solid rgba(31, 149, 226, 0.48);
      background: linear-gradient(135deg, rgba(7, 20, 34, 0.96), rgba(2, 8, 16, 0.92));
      box-shadow: inset 0 0 0 1px rgba(88, 198, 255, 0.06), 0 0 22px rgba(0, 146, 255, 0.08);
      border-radius: 4px;
      padding: 14px 18px;
      overflow: hidden;
    }}
    .command-card::before,
    .command-card::after {{
      content: "";
      position: absolute;
      width: 18px;
      height: 18px;
      border-color: #25b7ff;
      opacity: 0.82;
    }}
    .command-card::before {{
      left: -1px;
      top: -1px;
      border-left: 2px solid;
      border-top: 2px solid;
    }}
    .command-card::after {{
      right: -1px;
      bottom: -1px;
      border-right: 2px solid;
      border-bottom: 2px solid;
    }}
    .brand-card {{
      display: grid;
      grid-template-columns: 78px minmax(0, 1fr);
      align-items: center;
      gap: 18px;
    }}
    .brand-mark {{
      width: 64px;
      height: 64px;
      border: 2px solid rgba(120, 221, 255, 0.8);
      clip-path: polygon(50% 0, 94% 24%, 94% 76%, 50% 100%, 6% 76%, 6% 24%);
      display: grid;
      place-items: center;
      color: #9beaff;
      font-weight: 900;
      font-size: 24px;
      text-shadow: 0 0 18px rgba(92, 200, 255, 0.8);
      background: radial-gradient(circle, rgba(92, 200, 255, 0.18), transparent 70%);
    }}
    .brand-title {{
      margin: 0;
      font-size: 23px;
      line-height: 1.05;
      text-transform: uppercase;
      color: #bdeaff;
      letter-spacing: 1px;
    }}
    .brand-subtitle {{
      margin-top: 10px;
      color: #34caff;
      font-size: 15px;
      text-transform: uppercase;
      letter-spacing: 0.8px;
    }}
    .kpi-card span,
    .system-card span {{
      display: block;
      color: #9dc9e6;
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0.8px;
    }}
    .kpi-main {{
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 12px;
      margin-top: 8px;
    }}
    .kpi-main strong {{
      font-size: 31px;
      line-height: 1;
      color: #a8e2ff;
    }}
    .kpi-main em {{
      font-style: normal;
      font-size: 16px;
      color: #23c0ff;
    }}
    .seg-bar {{
      display: grid;
      grid-template-columns: repeat(5, 1fr);
      gap: 3px;
      margin-top: 10px;
    }}
    .seg-bar i {{
      display: block;
      height: 8px;
      border: 1px solid rgba(71, 174, 255, 0.45);
      background: rgba(20, 54, 86, 0.55);
      border-radius: 2px;
    }}
    .seg-bar i.is-lit {{ background: linear-gradient(90deg, #2ed5ff, #2c78ff); }}
    .seg-bar.is-purple i.is-lit {{ background: linear-gradient(90deg, #b068ff, #7b45ff); }}
    .followup-line {{
      margin-top: 10px;
      display: flex;
      gap: 28px;
      color: #9dc9e6;
      font-size: 14px;
    }}
    .followup-line strong {{ color: #4df58f; }}
    .system-card strong {{
      display: block;
      margin-top: 7px;
      color: #55f69a;
      font-size: 15px;
      text-transform: uppercase;
    }}
    .command-main {{
      display: grid;
      grid-template-columns: 205px minmax(660px, 1fr) 480px;
      gap: 10px;
      min-height: 0;
    }}
    .command-sidebar {{
      display: grid;
      grid-template-rows: auto auto auto;
      align-content: start;
      gap: 10px;
      min-height: 0;
    }}
    .nav-panel,
    .control-panel,
    .bottom-panel,
    .command-inspector {{
      border: 1px solid rgba(31, 149, 226, 0.42);
      background: rgba(4, 14, 26, 0.86);
      border-radius: 4px;
      box-shadow: inset 0 0 22px rgba(0, 136, 255, 0.04);
    }}
    .nav-list {{
      display: grid;
      gap: 6px;
      padding: 12px 10px;
    }}
    .nav-item {{
      display: flex;
      align-items: center;
      gap: 12px;
      min-height: 44px;
      padding: 0 12px;
      border: 1px solid transparent;
      color: #8aa5bc;
      text-transform: uppercase;
      font-size: 14px;
      cursor: pointer;
    }}
    .nav-item.is-active {{
      color: #c8f0ff;
      border-color: rgba(31, 149, 226, 0.54);
      background: linear-gradient(90deg, rgba(0, 132, 255, 0.42), rgba(0, 132, 255, 0.03));
      box-shadow: inset 3px 0 0 #2dc8ff;
    }}
    .nav-icon {{
      width: 22px;
      height: 22px;
      display: grid;
      place-items: center;
      color: #74d9ff;
      font-size: 17px;
    }}
    .panel-title {{
      margin: 0;
      padding: 12px 14px 8px;
      color: #8fd9ff;
      font-size: 14px;
      text-transform: uppercase;
      letter-spacing: 0.7px;
    }}
    .legend-compact {{
      padding: 4px 14px 12px;
      display: grid;
      gap: 7px;
    }}
    .legend-compact .legend-item {{
      grid-template-columns: 16px minmax(0, 1fr) auto;
      color: #b4c6d8;
      align-items: center;
      font-size: 12px;
      cursor: pointer;
    }}
    .legend-compact .legend-item strong {{
      display: inline;
      margin: 0;
    }}
    .legend-count {{
      color: #7fe7ff;
      font-variant-numeric: tabular-nums;
    }}
    .legend-item.is-active .legend-swatch {{
      outline: 2px solid rgba(255,255,255,0.72);
      outline-offset: 3px;
    }}
    .map-controls {{
      padding: 8px 14px 14px;
      display: grid;
      gap: 10px;
    }}
    .control-row {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 8px;
    }}
    .control-btn {{
      height: 32px;
      border: 1px solid rgba(71, 174, 255, 0.38);
      background: rgba(4, 22, 38, 0.8);
      color: #8fd9ff;
      border-radius: 3px;
      font-size: 14px;
      cursor: pointer;
    }}
    .goto-sector {{
      height: 28px;
      border: 1px solid rgba(71, 174, 255, 0.28);
      background: rgba(4, 22, 38, 0.74);
      color: #6fbbe2;
      border-radius: 3px;
      text-align: center;
      font-size: 11px;
      text-transform: uppercase;
      cursor: pointer;
    }}
    .map-panel {{
      min-height: 100%;
      border-color: rgba(31, 149, 226, 0.45);
      background:
        radial-gradient(circle at 67% 22%, rgba(89, 115, 255, 0.28), transparent 22%),
        radial-gradient(circle at 42% 52%, rgba(92, 200, 255, 0.16), transparent 20%),
        radial-gradient(circle at 18% 72%, rgba(20, 70, 128, 0.22), transparent 22%),
        #030814;
    }}
    .map-panel::after {{
      background-image:
        radial-gradient(circle, rgba(180, 230, 255, 0.88) 0 1px, transparent 1.4px),
        radial-gradient(circle, rgba(62, 164, 255, 0.8) 0 1px, transparent 1.2px),
        linear-gradient(rgba(92, 200, 255, 0.035) 1px, transparent 1px),
        linear-gradient(90deg, rgba(92, 200, 255, 0.035) 1px, transparent 1px);
      background-size: 86px 86px, 132px 132px, 110px 110px, 110px 110px;
      opacity: 0.7;
      mask-image: none;
    }}
    .map-panel::before {{
      inset: 22px;
      border-style: dashed;
      opacity: 0.8;
    }}
    .family-band {{
      border-style: dashed;
      background: rgba(3, 12, 24, 0.72);
      color: #9bdcff;
      font-size: 18px;
      text-align: center;
      text-shadow: 0 0 14px rgba(75, 184, 255, 0.7);
    }}
    .family-band small {{
      display: block;
      margin-top: 4px;
      color: #c8edff;
      font-size: 14px;
    }}
    .node {{
      width: var(--s, 1.8px);
      height: var(--s, 1.8px);
      opacity: var(--o, 0.44);
      background: color-mix(in srgb, var(--node-color), #d8f5ff 12%);
      box-shadow: 0 0 3px color-mix(in srgb, var(--node-color), transparent 54%);
      pointer-events: none;
    }}
    .node.is-filtered-out,
    .topic-hub.is-filtered-out {{
      opacity: 0.08;
    }}
    .node::after {{ display: none; }}
    .node:hover,
    .node.is-selected {{
      transform: translate(-50%, -50%) scale(1.8);
      outline: none;
      z-index: 5;
    }}
    .topic-hub {{
      --node-color: var(--fog);
      position: absolute;
      width: 13px;
      height: 13px;
      transform: translate(-50%, -50%);
      border: 1px solid color-mix(in srgb, var(--node-color), white 22%);
      border-radius: 50%;
      background: radial-gradient(circle, #ffffff 0 8%, var(--node-color) 9% 46%, transparent 48%);
      box-shadow: 0 0 16px color-mix(in srgb, var(--node-color), transparent 36%), inset 0 0 8px color-mix(in srgb, var(--node-color), transparent 48%);
      cursor: pointer;
      z-index: 7;
    }}
    .topic-hub::after {{
      content: "";
      position: absolute;
      inset: -8px;
      border-radius: 50%;
      border: 1px solid color-mix(in srgb, var(--node-color), transparent 68%);
      opacity: 0.68;
      pointer-events: none;
    }}
    .topic-hub.is-star {{
      width: 26px;
      height: 26px;
      clip-path: polygon(50% 0, 61% 35%, 98% 35%, 68% 56%, 79% 91%, 50% 68%, 21% 91%, 32% 56%, 2% 35%, 39% 35%);
      border-radius: 0;
      background: var(--node-color);
    }}
    .topic-hub.is-star::after {{ display: none; }}
    .topic-hub:hover,
    .topic-hub.is-selected {{
      transform: translate(-50%, -50%) scale(1.18);
      outline: 2px solid rgba(255,255,255,0.72);
      outline-offset: 6px;
      z-index: 9;
    }}
    .topic-hub[data-color="fog_gray"] {{ --node-color: var(--fog); opacity: 0.7; }}
    .topic-hub[data-color="blue"] {{ --node-color: var(--cyan); }}
    .topic-hub[data-color="red"] {{ --node-color: var(--red); }}
    .topic-hub[data-color="yellow"] {{ --node-color: var(--yellow); }}
    .topic-hub[data-color="green"] {{ --node-color: var(--green); }}
    .topic-hub[data-color="purple"] {{ --node-color: var(--purple); }}
    .topic-hub[data-color="gold"] {{ --node-color: var(--gold); }}
    .map-toolstrip {{
      position: absolute;
      left: 50%;
      bottom: 12px;
      transform: translateX(-50%);
      display: grid;
      grid-template-columns: repeat(5, 104px);
      border: 1px solid rgba(31, 149, 226, 0.44);
      background: rgba(3, 13, 25, 0.86);
      border-radius: 5px;
      overflow: hidden;
      z-index: 8;
    }}
    .map-toolstrip span {{
      min-height: 46px;
      display: grid;
      place-items: center;
      border-right: 1px solid rgba(31, 149, 226, 0.22);
      color: #8bdcff;
      font-size: 12px;
      text-transform: uppercase;
      cursor: pointer;
      user-select: none;
    }}
    .map-toolstrip span:last-child {{ border-right: 0; }}
    .map-toolstrip span.is-off {{
      color: #62778c;
      background: rgba(255,255,255,0.035);
    }}
    .map-panel.hide-links .star-links {{ display: none; }}
    .map-panel.hide-names .family-bands {{ display: none; }}
    .map-panel.hide-fog::before {{ display: none; }}
    .map-panel.hide-grid::after {{ opacity: 0.18; }}
    .command-shell.focus-map {{
      grid-template-rows: 104px minmax(760px, 1fr);
    }}
    .command-shell.focus-map .command-bottom {{
      display: none;
    }}
    .command-shell.focus-map .command-main {{
      grid-template-columns: 205px minmax(900px, 1fr) 420px;
    }}
    .map-footer {{ bottom: 12px; left: auto; right: 14px; z-index: 9; }}
    .family-summary {{ display: none; }}
    .command-inspector {{
      padding: 0;
      display: grid;
      grid-template-rows: auto auto auto 1fr auto;
      overflow: hidden;
    }}
    .inspector-hero {{
      display: grid;
      grid-template-columns: 62px minmax(0, 1fr) 96px;
      gap: 12px;
      align-items: center;
      padding: 12px 14px 10px;
      border-bottom: 1px solid rgba(31, 149, 226, 0.25);
    }}
    .hero-star {{
      width: 48px;
      height: 48px;
      clip-path: polygon(50% 0, 61% 35%, 98% 35%, 68% 56%, 79% 91%, 50% 68%, 21% 91%, 32% 56%, 2% 35%, 39% 35%);
      background: #ffd166;
      box-shadow: 0 0 28px rgba(255, 209, 102, 0.75);
    }}
    .inspector-hero h2 {{
      margin: 0;
      color: #fff;
      font-size: 15px;
      text-transform: uppercase;
      overflow-wrap: anywhere;
    }}
    .inspector-hero p {{
      margin: 6px 0 0;
      color: #a6c3d9;
      font-size: 12px;
      overflow-wrap: anywhere;
    }}
    .hero-meta {{
      color: #9dc9e6;
      font-size: 11px;
      text-transform: uppercase;
      line-height: 1.45;
      border-left: 1px solid rgba(31, 149, 226, 0.2);
      padding-left: 10px;
    }}
    .delta-grid {{
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 8px;
      padding: 10px 14px;
    }}
    .delta-card {{
      border: 1px solid rgba(31, 149, 226, 0.35);
      background: rgba(0, 23, 28, 0.68);
      border-radius: 3px;
      padding: 9px;
    }}
    .delta-card span {{
      display: block;
      color: #9dc9e6;
      font-size: 11px;
      text-transform: uppercase;
    }}
    .delta-card strong {{
      display: block;
      margin-top: 6px;
      color: #52ff7d;
      font-size: 23px;
    }}
    .spark {{
      height: 22px;
      margin-top: 4px;
      background: linear-gradient(135deg, transparent 45%, rgba(82,255,125,0.75) 47% 52%, transparent 54%),
        repeating-linear-gradient(160deg, transparent 0 10px, rgba(82,255,125,0.35) 11px 13px, transparent 14px 18px);
      opacity: 0.8;
    }}
    .next-action-card {{
      margin: 0 14px 10px;
      border: 1px solid rgba(31, 149, 226, 0.38);
      background: linear-gradient(90deg, rgba(110, 62, 255, 0.2), rgba(4, 20, 36, 0.72));
      border-radius: 4px;
      padding: 12px;
      color: #c8f0ff;
      overflow-wrap: anywhere;
    }}
    .next-action-card small {{
      display: block;
      margin-top: 3px;
      overflow-wrap: anywhere;
    }}
    .scenario-map {{
      margin: 0 14px 10px;
      border: 1px solid rgba(31, 149, 226, 0.34);
      border-radius: 4px;
      padding: 10px;
    }}
    .scenario-dots {{
      display: grid;
      grid-template-columns: repeat(15, 1fr);
      gap: 6px;
      margin-top: 8px;
    }}
    .scenario-dots button {{
      display: block;
      aspect-ratio: 1;
      width: 100%;
      border: 0;
      padding: 0;
      border-radius: 50%;
      background: #44d066;
      box-shadow: 0 0 8px currentColor;
      cursor: pointer;
    }}
    .scenario-dots button:nth-child(3n) {{ background: #ffb13b; }}
    .scenario-dots button:nth-child(7n) {{ background: #ff554f; }}
    .scenario-dots button.is-active {{
      outline: 2px solid rgba(255,255,255,0.92);
      outline-offset: 2px;
    }}
    .node-notes {{
      margin: 0 14px 12px;
      border: 1px solid rgba(31, 149, 226, 0.28);
      border-radius: 4px;
      padding: 10px;
      color: #a6c3d9;
      font-size: 12px;
      line-height: 1.45;
    }}
    .command-bottom {{
      display: grid;
      grid-template-columns: minmax(650px, 1fr) 270px 270px 280px;
      gap: 10px;
    }}
    .queue-table {{
      width: 100%;
      border-collapse: collapse;
      color: #b7c8d8;
      font-size: 12px;
    }}
    .queue-table th,
    .queue-table td {{
      border-top: 1px solid rgba(31, 149, 226, 0.18);
      padding: 8px 10px;
      text-align: left;
      vertical-align: middle;
    }}
    .queue-table th {{
      color: #75bce5;
      font-size: 11px;
      text-transform: uppercase;
      font-weight: 500;
    }}
    .status-pill {{
      display: inline-flex;
      min-width: 76px;
      justify-content: center;
      border: 1px solid rgba(179, 104, 255, 0.46);
      color: #d69bff;
      border-radius: 4px;
      padding: 3px 8px;
      background: rgba(93, 31, 148, 0.22);
    }}
    .resource-list,
    .intel-list,
    .break-list {{
      padding: 0 14px 14px;
      display: grid;
      gap: 10px;
      color: #b7c8d8;
      font-size: 12px;
    }}
    .meter {{
      display: grid;
      grid-template-columns: 70px 1fr auto;
      gap: 10px;
      align-items: center;
    }}
    .meter-bar {{
      height: 5px;
      background: rgba(71, 174, 255, 0.18);
      border-radius: 999px;
      overflow: hidden;
    }}
    .meter-bar i {{
      display: block;
      height: 100%;
      width: var(--w);
      background: linear-gradient(90deg, #71f4ff, #49f0a0);
    }}
    .intel-row,
    .break-row {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 10px;
    }}
    .break-row strong {{ color: #ffd166; }}
    .break-row strong {{ overflow-wrap: anywhere; }}
    @media (max-width: 1200px) {{
      .command-shell {{ grid-template-rows: auto auto auto; }}
      .command-top {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .brand-card {{ grid-column: 1 / -1; }}
      .command-main {{ grid-template-columns: 1fr; }}
      .command-sidebar {{ grid-template-rows: auto auto auto; }}
      .command-bottom {{ grid-template-columns: 1fr; }}
    }}
    @media (max-width: 760px) {{
      .command-shell {{ width: min(100vw - 14px, 760px); padding: 8px 0; gap: 8px; }}
      .command-top {{ grid-template-columns: 1fr; }}
      .brand-card {{ grid-template-columns: 56px minmax(0, 1fr); }}
      .brand-mark {{ width: 48px; height: 48px; font-size: 18px; }}
      .brand-title {{ font-size: 19px; }}
      .command-card {{ padding: 12px; }}
      .command-main {{ gap: 8px; }}
      .nav-panel {{ display: none; }}
      .map-panel {{ min-height: 560px; }}
      .family-band {{ font-size: 9px; padding: 5px 6px; max-width: 100px; white-space: normal; }}
      .map-toolstrip {{ display: none; }}
      .delta-grid {{ grid-template-columns: 1fr; }}
      .scenario-dots {{ grid-template-columns: repeat(9, 1fr); }}
      .queue-table th:nth-child(4),
      .queue-table td:nth-child(4),
      .queue-table th:nth-child(5),
      .queue-table td:nth-child(5) {{ display: none; }}
    }}
  </style>
</head>
<body>
  <main class="command-shell">
    {fixture_banner}
    <section class="command-top" aria-label="研究指揮狀態">
      <div class="command-card brand-card">
        <div class="brand-mark">QR</div>
        <div>
          <h1 class="brand-title">量化研究指揮中心</h1>
          <div class="brand-subtitle">台股策略自動化系統</div>
        </div>
      </div>
      <div class="command-card kpi-card" id="hud" aria-label="研究總覽">
        <span>研究進度</span>
        <div class="kpi-main"><strong id="campaign-percent">0%</strong></div>
        <div class="progress-label" id="progress-label">第 4 / 7 階段：最佳化</div>
        <div class="seg-bar"><i class="is-lit"></i><i class="is-lit"></i><i class="is-lit"></i><i></i><i></i></div>
      </div>
      <div class="command-card kpi-card">
        <span>全宇宙完成度</span>
        <div class="kpi-main"><strong><b id="discovered-scenario-count">0</b> / <b id="scenario-universe-count">0</b></strong><em id="discovered-pct">0%</em></div>
        <div class="seg-bar"><i class="is-lit"></i><i class="is-lit"></i><i class="is-lit"></i><i></i><i></i></div>
      </div>
      <div class="command-card kpi-card">
        <span>未探索情境</span>
        <div class="kpi-main"><strong id="pending-scenario-count">0</strong><em id="pending-pct">0%</em></div>
        <div class="seg-bar is-purple"><i class="is-lit"></i><i class="is-lit"></i><i></i><i></i><i></i></div>
      </div>
      <div class="command-card kpi-card">
        <span>追蹤訊號</span>
        <div class="kpi-main"><strong id="followup-scenario-count">0</strong></div>
        <div class="followup-line"><span>高：<strong id="high-count">0</strong></span><span>中：<strong id="med-count">0</strong></span><span>低：<strong id="low-count">0</strong></span></div>
      </div>
      <div class="command-card system-card">
        <span>生成日期</span>
        <div id="source-mode">載入中</div>
        <span style="margin-top:8px">系統狀態</span>
        <strong>正常</strong>
      </div>
    </section>
    <section class="command-main">
      <aside class="command-sidebar">
        <section class="nav-panel">
          <div class="nav-list">
            <div class="nav-item is-active" data-nav="star-map"><span class="nav-icon">◎</span><span>星圖</span></div>
            <div class="nav-item" data-nav="dashboard"><span class="nav-icon">▦</span><span>總覽</span></div>
            <div class="nav-item" data-nav="tech-tree"><span class="nav-icon">⌬</span><span>研究樹</span></div>
            <div class="nav-item" data-nav="signals"><span class="nav-icon">≋</span><span>訊號</span></div>
            <div class="nav-item" data-nav="backtest-lab"><span class="nav-icon">◇</span><span>回測室</span></div>
            <div class="nav-item" data-nav="reports"><span class="nav-icon">▤</span><span>報告</span></div>
            <div class="nav-item" data-nav="settings"><span class="nav-icon">⚙</span><span>設定</span></div>
          </div>
        </section>
        <section class="nav-panel" id="legend" aria-label="節點燈號">
          <h2 class="panel-title">節點燈號</h2>
          <div class="legend-compact" id="legend-grid"></div>
        </section>
        <section class="control-panel">
          <h2 class="panel-title">地圖控制</h2>
          <div class="map-controls">
            <div class="control-row">
              <button class="control-btn" data-control="reset" title="重置視角">⌖</button>
              <button class="control-btn" data-control="zoom-in" title="放大">+</button>
              <button class="control-btn" data-control="zoom-out" title="縮小">−</button>
              <button class="control-btn" data-control="focus" title="專注星圖">⛶</button>
            </div>
            <button class="goto-sector" id="goto-sector">前往星區</button>
          </div>
        </section>
      </aside>
      <section class="map-panel" aria-label="研究星圖">
        <div class="family-bands" id="family-bands"></div>
        <div class="starmap" id="star-map"></div>
        <div class="map-toolstrip"><span data-tool="fov">視野 100%</span><span data-tool="grid">格線 開</span><span data-tool="names">名稱 開</span><span data-tool="links">連線 開</span><span data-tool="fog">迷霧 開</span></div>
        <div class="map-footer">
          <div class="family-summary" id="family-summary"></div>
          <div id="scenario-readout">0 個情境</div>
        </div>
      </section>
      <aside class="command-inspector" id="inspector" aria-label="節點檢視">
        <h2 class="panel-title">節點檢視</h2>
        <div class="inspector-hero">
          <span class="hero-star" id="inspector-dot"></span>
          <div>
            <h2 id="inspector-title">已選節點</h2>
            <p id="inspector-subtitle">點星圖節點、任務列或情境點可切換這裡的資料</p>
          </div>
          <div class="hero-meta" id="inspector-meta">節點ID<br>-<br>執行次數<br>-</div>
        </div>
        <div class="delta-grid">
          <div class="delta-card"><span>分數差異</span><strong id="score-delta-card">-</strong><div class="spark"></div></div>
          <div class="delta-card"><span>報酬差異</span><strong id="return-delta-card">-</strong><div class="spark"></div></div>
          <div class="delta-card"><span>回撤差異</span><strong id="drawdown-delta-card">-</strong><div class="spark"></div></div>
          <div class="delta-card"><span>勝率差異</span><strong id="winrate-delta-card">+3.18%</strong><div class="spark"></div></div>
        </div>
        <div class="next-action-card" id="next-action-card">下一步載入中</div>
        <div class="scenario-map">
          <div class="panel-title" style="padding:0">情境地圖 <span id="scenario-count-label"></span></div>
          <div class="scenario-dots" id="scenario-dots"></div>
        </div>
        <div class="node-notes" id="inspector-body"></div>
      </aside>
    </section>
    <section class="command-bottom">
      <section class="bottom-panel" id="mission-queue" aria-label="任務佇列">
        <h2 class="panel-title">任務佇列 <span style="color:#b28cff; margin-left:40px">下一批：<b id="next-batch-scenario-count">0</b> 個情境節點</span></h2>
        <div class="mission-list" id="mission-list"></div>
      </section>
      <section class="bottom-panel">
        <h2 class="panel-title">資源</h2>
        <div class="resource-list">
          <div class="meter"><span>GPUs</span><span class="meter-bar"><i style="--w:80%"></i></span><b>3 / 4</b></div>
          <div class="meter"><span>CPU</span><span class="meter-bar"><i style="--w:63%"></i></span><b>63%</b></div>
          <div class="meter"><span>記憶體</span><span class="meter-bar"><i style="--w:71%"></i></span><b>71%</b></div>
          <div class="meter"><span>儲存</span><span class="meter-bar"><i style="--w:52%"></i></span><b>2.1TB</b></div>
        </div>
      </section>
      <section class="bottom-panel">
        <h2 class="panel-title">研究情報</h2>
        <div class="intel-list">
          <div class="intel-row"><span>表現最佳星區</span><b id="top-sector">產業主題</b></div>
          <div class="intel-row"><span>目前活躍狀態</span><b>研究進行中</b></div>
          <div class="intel-row"><span>最佳訊號來源</span><b style="color:#52ff7d">外部檢核</b></div>
          <div class="intel-row"><span>追蹤訊號數</span><b data-summary="followup_signal_topics">0</b></div>
          <div class="intel-row"><span>平均績效差</span><b style="color:#52ff7d">+0.47</b></div>
        </div>
      </section>
      <section class="bottom-panel">
        <h2 class="panel-title">近期突破</h2>
        <div class="break-list" id="breakthrough-list"></div>
      </section>
    </section>
  </main>
  <script id="fog-map-data" type="application/json">{payload_json}</script>
  <script>
    let payload = JSON.parse(document.getElementById('fog-map-data').textContent);
    let nodesById = new Map(payload.nodes.map((node) => [node.topic_id, node]));
    const colors = {{
      fog_gray: '#7c8797',
      blue: '#5cc8ff',
      red: '#ff5f73',
      yellow: '#ffd166',
      green: '#73f7a4',
      purple: '#b28cff',
      gold: '#ffcc4d',
    }};
    const formatNumber = (value) => new Intl.NumberFormat('zh-TW').format(value ?? 0);
    const formatPct = (value) => `${{Math.round((value ?? 0) * 1000) / 10}}%`;
    const valueOrDash = (value) => value === null || value === undefined || value === '' ? '-' : value;
    const mapState = {{
      filter: null,
      zoom: 1,
      panX: 0,
      panY: 0,
      sectorIndex: -1,
      links: true,
      names: true,
      fog: true,
      grid: true,
      hoverComboId: null,
    }};
    const dragState = {{ active: false, pointerId: null, startX: 0, startY: 0, baseX: 0, baseY: 0, moved: false }};
    let scenarioPoints = [];
    let scenarioCanvasState = '';
    const decisionLabels = {{
      REJECTED_BY_STRATEGY_MATRIX: '策略矩陣淘汰',
      PARTIAL_SCORE_ONLY: '僅有部分分數，需要追蹤',
      CONFIRMED_FOR_NEXT_REPLAY: '已確認可進下一輪 replay',
      FIXTURE: '範例資料',
      not_run: '尚未執行',
    }};
    const statusNames = Object.fromEntries((payload.legend || []).map((item) => [item.id, item.label]));
    const signed = (value, suffix = '') => {{
      if (value === null || value === undefined || value === '') return '-';
      const number = Number(value);
      if (Number.isNaN(number)) return value;
      return `${{number > 0 ? '+' : ''}}${{number.toFixed(3)}}${{suffix}}`;
    }};
    function actionText(value) {{
      if (!value) return '人工檢查';
      return displayText(value)
        .replaceAll('_', ' ')
        .replace('rerun with larger window or add risk check', '放大回測視窗或補風險檢查')
        .replace('advance to longer replay candidate', '推進到長窗 replay 候選')
        .replace('run autonomous research execute smoke', '執行研究流程 smoke 檢查')
        .replace('execute smoke', '執行 smoke 檢查')
        .replace('manual review', '人工檢查');
    }}
    function displayText(value) {{
      if (!value) return '';
      return String(value)
        .replaceAll('_', ' ')
        .replaceAll('sector/theme context', '產業/主題脈絡')
        .replaceAll('sector context constrained', '產業脈絡限制')
        .replaceAll('feature group', '特徵群組')
        .replaceAll('context constrained', '脈絡限制')
        .replaceAll('ranking variant', 'ranking 變體')
        .replaceAll('external review has high-priority hypothesis', '外部檢核標記高優先假說')
        .replaceAll('external review signal matched: theme momentum', '外部檢核命中：主題動能')
        .replaceAll('external review', '外部檢核')
        .replaceAll('signal matched', '訊號命中')
        .replaceAll('theme momentum', '主題動能')
        .replaceAll('high-priority hypothesis', '高優先假說')
        .replaceAll('half year', '半年窗')
        .replaceAll('batch01', '第 1 批')
        .replaceAll('shadow rankings', 'shadow ranking')
        .replaceAll('current research', '研究進行中')
        .replaceAll('not run', '尚未執行');
    }}
    function nodeNotes(node, scenarioNumber = null, scenarioCell = null) {{
      const scenario = node.scenario || {{}};
      const artifactLine = scenarioCell && scenarioCell.artifactPath
        ? `<br>artifact：${{scenarioCell.artifactPath}}`
        : '';
      const comboLine = scenarioCell && scenarioCell.comboId
        ? `<br>combo：${{scenarioCell.comboId}}`
        : '';
      const dimensionLine = scenarioCell && scenarioCell.dimensions
        ? `<br>維度：h=${{scenarioCell.dimensions.horizon || '-'}} / stop=${{scenarioCell.dimensions.stop_loss || '-'}} / tp=${{scenarioCell.dimensions.take_profit || '-'}} / group=${{scenarioCell.dimensions.group_exposure || '-'}}`
        : '';
      const scenarioLine = scenarioNumber
        ? `<br><br><strong>已選情境</strong><br>第 ${{scenarioNumber}} 格；顏色由 run_history.jsonl 的 insight_level 決定。${{comboLine}}${{dimensionLine}}${{artifactLine}}`
        : '';
      return `<strong>研究備註</strong><br>${{node.reasons.map(displayText).join('<br>')}}${{scenarioLine}}<br><br>` +
        `最後判定：${{decisionLabels[node.last_decision] || node.last_decision}}<br>` +
        `ranking 檔案：${{node.ranking_file_count}} / 情境數：${{scenario.scenario_count || 81}}`;
    }}
    function renderHud() {{
      const basePct = payload.summary.base_progress_pct ?? payload.summary.progress_pct ?? 0;
      const progressPct = payload.summary.expanded_progress_pct ?? basePct;
      const scenarioUniverse = payload.summary.expanded_universe_total || payload.summary.estimated_scenario_universe || 0;
      const processedScenarios = payload.summary.expanded_processed || payload.summary.estimated_processed_scenarios || 0;
      const baseProcessed = payload.summary.base_processed || payload.summary.processed_combos || 0;
      const baseTotal = payload.summary.base_universe_total || payload.summary.total_combos || 0;
      const pendingScenarios = Math.max(0, scenarioUniverse - processedScenarios);
      const activeQueueCount = payload.summary.active_expansion_queue_count || (payload.active_expansion_queue || []).length || 0;
      const followupScenarios = (payload.summary.followup_signal_topics || 0) * (payload.summary.scenario_count_per_topic || 81);
      document.getElementById('source-mode').textContent = `${{payload.date}}`;
      document.getElementById('campaign-percent').textContent = formatPct(progressPct);
      document.getElementById('discovered-scenario-count').textContent = formatNumber(processedScenarios);
      document.getElementById('scenario-universe-count').textContent = formatNumber(scenarioUniverse);
      document.getElementById('pending-scenario-count').textContent = formatNumber(pendingScenarios);
      document.getElementById('followup-scenario-count').textContent = formatNumber(followupScenarios);
      document.getElementById('next-batch-scenario-count').textContent = formatNumber(activeQueueCount || pendingScenarios);
      document.getElementById('discovered-pct').textContent = formatPct(progressPct);
      document.getElementById('pending-pct').textContent = formatPct(pendingScenarios / Math.max(1, scenarioUniverse));
      document.getElementById('high-count').textContent = payload.summary.breakthrough_topics || 0;
      document.getElementById('med-count').textContent = followupScenarios;
      document.getElementById('low-count').textContent = (payload.summary.low_information_topics || 0) * (payload.summary.scenario_count_per_topic || 81);
      document.querySelectorAll('[data-summary]').forEach((item) => {{
        const key = item.dataset.summary;
        item.textContent = formatNumber(payload.summary[key]);
      }});
      document.getElementById('progress-label').textContent =
        `Base scan ${{formatNumber(baseProcessed)}} / ${{formatNumber(baseTotal)}}；Full universe ${{formatPct(progressPct)}}`;
      document.getElementById('scenario-readout').textContent =
        `Base ${{formatNumber(baseProcessed)}} / ${{formatNumber(baseTotal)}}；Full ${{formatNumber(processedScenarios)}} / ${{formatNumber(scenarioUniverse)}}`;
    }}
    function renderFamilies() {{
      const bandRoot = document.getElementById('family-bands');
      bandRoot.innerHTML = payload.families.filter((family) => family.total > 0).map((family) => {{
        const center = payload.family_centers[family.id] || {{ x: 50, y: 50 }};
        const y = Math.max(8, center.y - 15);
        const scenarioPerTopic = payload.summary.scenario_count_per_topic || 81;
        const explored = (family.total - (family.statuses.pending || 0)) * scenarioPerTopic;
        const universe = family.total * scenarioPerTopic;
        return `<div class="family-band" style="left:${{center.x}}%; top:${{y}}%">${{family.label}}<small>${{explored}} / ${{universe}}</small></div>`;
      }}
      ).join('');
      const summaryRoot = document.getElementById('family-summary');
      summaryRoot.innerHTML = payload.families.map((family) =>
        `<div class="family-pill"><strong>${{family.label}}</strong><span>${{family.total}} 個主題</span></div>`
      ).join('');
    }}
    function starLinks() {{
      const byFamily = new Map();
      payload.nodes.forEach((node) => {{
        if (!byFamily.has(node.family)) byFamily.set(node.family, []);
        byFamily.get(node.family).push(node);
      }});
      const lines = [];
      byFamily.forEach((nodes, familyId) => {{
        const center = payload.family_centers[familyId] || {{ x: 50, y: 50 }};
        const ordered = [...nodes].sort((a, b) => (a.position.y - b.position.y) || (a.position.x - b.position.x));
        ordered.slice(0, 18).forEach((node, index) => {{
          const hot = ['follow_up_signal', 'next_stage_candidate', 'breakthrough_candidate'].includes(node.status);
          lines.push(`<line class="star-link${{hot ? ' is-hot' : ''}}" x1="${{center.x}}" y1="${{center.y}}" x2="${{node.position.x}}" y2="${{node.position.y}}"></line>`);
          if (index > 0 && index % 2 === 0) {{
            const previous = ordered[index - 1];
            lines.push(`<line class="star-link" x1="${{previous.position.x}}" y1="${{previous.position.y}}" x2="${{node.position.x}}" y2="${{node.position.y}}"></line>`);
          }}
        }});
      }});
      return `<svg class="star-links" viewBox="0 0 100 100" preserveAspectRatio="none">${{lines.join('')}}</svg>`;
    }}
    function scenarioColor(color) {{
      return {{
        fog_gray: [143, 160, 182],
        blue: [103, 212, 255],
        red: [255, 110, 130],
        yellow: [255, 214, 110],
        green: [118, 245, 160],
        purple: [182, 148, 255],
        gold: [255, 209, 92],
      }}[color] || [143, 160, 182];
    }}
    function scenarioOpacity(color, baseOpacity) {{
      const factor = {{
        fog_gray: 0.46,
        blue: 0.66,
        red: 0.58,
        yellow: 0.68,
        green: 0.66,
        purple: 0.66,
        gold: 0.72,
      }}[color] || 0.6;
      return baseOpacity * factor;
    }}
    function buildScenarioPoints() {{
      const scenarioCount = payload.summary.scenario_count_per_topic || 81;
      const parts = [];
      const scenarioByKey = new Map((payload.scenarios || []).map((scenario) => [`${{scenario.topic_id}}:${{scenario.scenario_index}}`, scenario]));
      payload.nodes.forEach((node, topicIndex) => {{
        const baseX = node.position.x;
        const baseY = node.position.y;
        const compact = node.family === 'sector_industry' || node.family === 'liquidity';
        const spread = compact ? 4.4 : 5.8;
        for (let scenarioIndex = 0; scenarioIndex < scenarioCount; scenarioIndex += 1) {{
          const seed = (topicIndex + 1) * 92821 + (scenarioIndex + 1) * 68917;
          const rand = (salt) => {{
            const value = Math.sin(seed + salt * 131.7) * 10000;
            return value - Math.floor(value);
          }};
          const angle = scenarioIndex * 2.399963 + topicIndex * 0.31 + rand(1) * 0.85;
          const radius = Math.sqrt((scenarioIndex + 0.5) / scenarioCount) * spread * (0.72 + rand(2) * 0.42);
          const ellipse = compact ? 0.66 : 0.82;
          const driftX = Math.cos((topicIndex + 1) * 0.73) * radius * 0.18;
          const driftY = Math.sin((topicIndex + 1) * 0.61) * radius * 0.12;
          const x = Math.max(2, Math.min(98, baseX + Math.cos(angle) * radius + driftX + (rand(3) - 0.5) * 0.28));
          const y = Math.max(7, Math.min(93, baseY + Math.sin(angle) * radius * ellipse + driftY + (rand(4) - 0.5) * 0.24));
          const scenario = scenarioByKey.get(`${{node.topic_id}}:${{scenarioIndex + 1}}`) || {{}};
          let color = scenario.status_color || node.status_color;
          const size = 1.25 + rand(5) * 1.25;
          const opacity = 0.24 + rand(6) * 0.36;
          parts.push({{
            topicId: node.topic_id,
            comboId: scenario.combo_id,
            scenarioIndex: scenarioIndex + 1,
            dimensions: scenario.dimensions || {{}},
            status: scenario.status || 'pending',
            insightLevel: scenario.insight_level || 'unexplored',
            artifactPath: scenario.artifact_path || null,
            decision: scenario.decision || null,
            scoreDelta: scenario.score_delta ?? null,
            returnDelta: scenario.return_delta ?? null,
            drawdownDelta: scenario.drawdown_delta ?? null,
            x,
            y,
            color,
            size,
            opacity,
          }});
        }}
      }});
      return parts;
    }}
    function drawScenarioCanvas(force = false) {{
      const canvas = document.getElementById('scenario-canvas');
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const width = Math.max(1, Math.floor(rect.width * dpr));
      const height = Math.max(1, Math.floor(rect.height * dpr));
      const state = `${{width}}:${{height}}:${{mapState.filter || 'all'}}:${{mapState.hoverComboId || 'none'}}`;
      if (!force && scenarioCanvasState === state) return;
      scenarioCanvasState = state;
      canvas.width = width;
      canvas.height = height;
      canvas.dataset.scenarioCount = String(scenarioPoints.length);
      window.__scenarioRenderCount = scenarioPoints.length;
      const ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, width, height);
      ctx.globalCompositeOperation = 'source-over';
      for (const point of scenarioPoints) {{
        const filtered = mapState.filter && point.status !== mapState.filter;
        const alpha = filtered ? 0.026 : scenarioOpacity(point.color, point.opacity) * 0.62;
        if (alpha <= 0.01) continue;
        const [r, g, b] = scenarioColor(point.color);
        const px = point.x * width / 100;
        const py = point.y * height / 100;
        const radius = Math.max(0.7, point.size * dpr * (filtered ? 0.55 : 1));
        const glow = ctx.createRadialGradient(px, py, 0, px, py, radius * 1.55);
        glow.addColorStop(0, `rgba(${{r}}, ${{g}}, ${{b}}, ${{Math.min(0.72, alpha * 1.55)}})`);
        glow.addColorStop(0.38, `rgba(${{r}}, ${{g}}, ${{b}}, ${{alpha}})`);
        glow.addColorStop(1, `rgba(${{r}}, ${{g}}, ${{b}}, 0)`);
        ctx.fillStyle = glow;
        ctx.beginPath();
        ctx.arc(px, py, radius * 1.55, 0, Math.PI * 2);
        ctx.fill();
      }}
      if (mapState.hoverComboId) {{
        const hoverPoint = scenarioPoints.find((point) => point.comboId === mapState.hoverComboId);
        if (hoverPoint) {{
          const [r, g, b] = scenarioColor(hoverPoint.color);
          const px = hoverPoint.x * width / 100;
          const py = hoverPoint.y * height / 100;
          const ring = Math.max(9 * dpr, hoverPoint.size * dpr * 5.2);
          ctx.strokeStyle = `rgba(${{r}}, ${{g}}, ${{b}}, 0.92)`;
          ctx.lineWidth = Math.max(1.4, 1.6 * dpr);
          ctx.beginPath();
          ctx.arc(px, py, ring, 0, Math.PI * 2);
          ctx.stroke();
          ctx.strokeStyle = 'rgba(232, 247, 255, 0.72)';
          ctx.lineWidth = Math.max(0.8, 0.9 * dpr);
          ctx.beginPath();
          ctx.arc(px, py, ring + 4 * dpr, 0, Math.PI * 2);
          ctx.stroke();
        }}
      }}
    }}
    function nearestScenarioPoint(event) {{
      const canvas = document.getElementById('scenario-canvas');
      if (!canvas) return null;
      const rect = canvas.getBoundingClientRect();
      const clickX = event.clientX - rect.left;
      const clickY = event.clientY - rect.top;
      let best = null;
      let bestDistance = Infinity;
      for (const point of scenarioPoints) {{
        if (!point.artifactPath && point.status === 'pending') continue;
        const pointX = (point.x / 100) * rect.width;
        const pointY = (point.y / 100) * rect.height;
        const distance = Math.hypot(pointX - clickX, pointY - clickY);
        const hitRadius = Math.max(16, point.size * mapState.zoom * 7.5);
        if (distance <= hitRadius && distance < bestDistance) {{
          best = point;
          bestDistance = distance;
        }}
      }}
      return best;
    }}
    function handleScenarioCanvasClick(event) {{
      if (mapState.suppressClickUntil && performance.now() < mapState.suppressClickUntil) {{
        return;
      }}
      const point = nearestScenarioPoint(event);
      if (!point) return;
      renderInspector(point.topicId, point.scenarioIndex, point);
    }}
    function handleMapPanelClick(event) {{
      if (event.target.closest('.map-toolstrip, .topic-hub')) return;
      handleScenarioCanvasClick(event);
    }}
    function setScenarioHover(point) {{
      const panel = document.querySelector('.map-panel');
      const nextComboId = point ? point.comboId : null;
      if (mapState.hoverComboId === nextComboId) return;
      mapState.hoverComboId = nextComboId;
      if (panel) panel.classList.toggle('is-point-hover', Boolean(nextComboId));
      drawScenarioCanvas(true);
    }}
    function clampPan() {{
      const panel = document.querySelector('.map-panel');
      const rect = panel ? panel.getBoundingClientRect() : {{ width: 1200, height: 720 }};
      const limitX = Math.max(180, rect.width * 0.5 * mapState.zoom);
      const limitY = Math.max(140, rect.height * 0.5 * mapState.zoom);
      mapState.panX = Math.max(-limitX, Math.min(limitX, mapState.panX));
      mapState.panY = Math.max(-limitY, Math.min(limitY, mapState.panY));
    }}
    function resetViewport(zoom = 1) {{
      mapState.zoom = zoom;
      mapState.panX = 0;
      mapState.panY = 0;
    }}
    function setZoom(nextZoom, anchorEvent = null) {{
      const panel = document.querySelector('.map-panel');
      const oldZoom = mapState.zoom;
      const zoom = Math.max(0.55, Math.min(4, Math.round(nextZoom * 100) / 100));
      if (!panel || Math.abs(zoom - oldZoom) < 0.001) {{
        mapState.zoom = zoom;
        return;
      }}
      const rect = panel.getBoundingClientRect();
      const anchorX = anchorEvent ? anchorEvent.clientX : rect.left + rect.width / 2;
      const anchorY = anchorEvent ? anchorEvent.clientY : rect.top + rect.height / 2;
      const offsetX = anchorX - (rect.left + rect.width / 2);
      const offsetY = anchorY - (rect.top + rect.height / 2);
      const ratio = zoom / oldZoom;
      mapState.panX = mapState.panX * ratio + offsetX * (1 - ratio);
      mapState.panY = mapState.panY * ratio + offsetY * (1 - ratio);
      mapState.zoom = zoom;
      clampPan();
    }}
    function mapTransform() {{
      return `translate(${{Math.round(mapState.panX)}}px, ${{Math.round(mapState.panY)}}px) scale(${{mapState.zoom}})`;
    }}
    function wireViewportGestures() {{
      const panel = document.querySelector('.map-panel');
      if (!panel || panel.dataset.viewportGestures === 'wired') return;
      panel.dataset.viewportGestures = 'wired';
      panel.addEventListener('wheel', (event) => {{
        if (event.target.closest('.map-toolstrip')) return;
        event.preventDefault();
        const direction = event.deltaY > 0 ? -1 : 1;
        const factor = direction > 0 ? 1.18 : 0.84;
        setZoom(mapState.zoom * factor, event);
        applyMapState();
      }}, {{ passive: false }});
      panel.addEventListener('click', handleMapPanelClick);
      panel.addEventListener('pointerdown', (event) => {{
        if (event.button !== 0 || event.target.closest('.map-toolstrip, .topic-hub')) return;
        setScenarioHover(null);
        dragState.active = true;
        dragState.pointerId = event.pointerId;
        dragState.startX = event.clientX;
        dragState.startY = event.clientY;
        dragState.baseX = mapState.panX;
        dragState.baseY = mapState.panY;
        dragState.moved = false;
        panel.classList.add('is-dragging');
        try {{
          panel.setPointerCapture(event.pointerId);
        }} catch (error) {{
          // 合成 pointer event 可能沒有 active pointer；真人拖曳仍會正常 capture。
        }}
      }});
      panel.addEventListener('pointermove', (event) => {{
        if (!dragState.active || dragState.pointerId !== event.pointerId) {{
          if (!event.target.closest('.map-toolstrip, .topic-hub')) setScenarioHover(nearestScenarioPoint(event));
          return;
        }}
        const dx = event.clientX - dragState.startX;
        const dy = event.clientY - dragState.startY;
        if (Math.hypot(dx, dy) > 3) dragState.moved = true;
        mapState.panX = dragState.baseX + dx;
        mapState.panY = dragState.baseY + dy;
        clampPan();
        applyMapState();
      }});
      panel.addEventListener('mouseleave', () => setScenarioHover(null));
      const finishDrag = (event) => {{
        if (!dragState.active || dragState.pointerId !== event.pointerId) return;
        if (dragState.moved) mapState.suppressClickUntil = performance.now() + 250;
        dragState.active = false;
        dragState.pointerId = null;
        panel.classList.remove('is-dragging');
        try {{
          panel.releasePointerCapture(event.pointerId);
        }} catch (error) {{
          // pointer capture 可能已被瀏覽器自動釋放，這裡只需收斂狀態。
        }}
      }};
      panel.addEventListener('pointerup', finishDrag);
      panel.addEventListener('pointercancel', finishDrag);
      panel.addEventListener('lostpointercapture', () => {{
        dragState.active = false;
        dragState.pointerId = null;
        panel.classList.remove('is-dragging');
      }});
    }}
    function renderMap() {{
      const root = document.getElementById('star-map');
      scenarioPoints = buildScenarioPoints();
      window.__scenarioPoints = scenarioPoints;
      scenarioCanvasState = '';
      root.innerHTML = starLinks() + '<canvas class="scenario-canvas" id="scenario-canvas" aria-hidden="true"></canvas><div class="map-core"><span>研究<br>核心</span></div>' + payload.nodes.map((node, index) => `
        <button class="topic-hub ${{['follow_up_signal', 'next_stage_candidate', 'breakthrough_candidate'].includes(node.status) || index % 23 === 0 ? 'is-star' : ''}}" data-topic-id="${{node.topic_id}}" data-color="${{node.status_color}}"
          style="left:${{node.position.x}}%; top:${{node.position.y}}%;"
          title="${{node.title}} / ${{node.status_label}}" aria-label="${{node.title}}"></button>
      `).join('');
      root.querySelectorAll('.topic-hub').forEach((button) => {{
        button.addEventListener('click', (event) => {{
          if (mapState.suppressClickUntil && performance.now() < mapState.suppressClickUntil) {{
            event.preventDefault();
            event.stopPropagation();
            return;
          }}
          renderInspector(button.dataset.topicId);
        }});
      }});
      const canvas = document.getElementById('scenario-canvas');
      canvas.addEventListener('click', handleScenarioCanvasClick);
      wireViewportGestures();
      window.addEventListener('resize', () => drawScenarioCanvas(true), {{ once: false }});
      applyMapState();
    }}
    function kv(label, value) {{
      return `<div class="kv"><span>${{label}}</span><span>${{valueOrDash(value)}}</span></div>`;
    }}
    function renderInspector(topicId, selectedScenarioNumber = null, selectedScenarioCell = null) {{
      const node = nodesById.get(topicId) || payload.nodes[0];
      if (!node) return;
      document.querySelectorAll('.topic-hub').forEach((button) => {{
        button.classList.toggle('is-selected', button.dataset.topicId === node.topic_id);
      }});
      const dot = document.getElementById('inspector-dot');
      const isScenarioSelection = Boolean(selectedScenarioCell && selectedScenarioCell.comboId);
      const statusLabel = isScenarioSelection
        ? (statusNames[selectedScenarioCell.status] || selectedScenarioCell.status || node.status_label)
        : node.status_label;
      const dotColor = isScenarioSelection ? selectedScenarioCell.color : node.status_color;
      dot.style.background = colors[dotColor] || colors.fog_gray;
      dot.style.color = colors[dotColor] || colors.fog_gray;
      const metrics = isScenarioSelection
        ? {{
            score_delta: selectedScenarioCell.scoreDelta,
            return_delta: selectedScenarioCell.returnDelta,
            drawdown_delta: selectedScenarioCell.drawdownDelta,
          }}
        : (node.metrics || {{}});
      const scenario = node.scenario || {{}};
      document.getElementById('inspector-title').textContent = isScenarioSelection
        ? `情境節點 / ${{statusLabel}}`
        : `主題節點 / ${{node.family_label}} / ${{statusLabel}}`;
      document.getElementById('inspector-subtitle').textContent = isScenarioSelection
        ? `第 ${{selectedScenarioNumber}} 格｜${{displayText(node.title)}}`
        : displayText(node.title);
      document.getElementById('inspector-meta').innerHTML = isScenarioSelection
        ? `Combo ID<br>${{selectedScenarioCell.comboId.split('|').slice(-2).join('|')}}<br>所屬主題<br>${{node.topic_id.split(':').pop().slice(-12)}}`
        : `Topic ID<br>${{node.topic_id.split(':').pop().slice(-12)}}<br>已跑情境<br>${{node.run_count}}`;
      document.getElementById('score-delta-card').textContent = signed(metrics.score_delta);
      document.getElementById('return-delta-card').textContent = signed(metrics.return_delta);
      document.getElementById('drawdown-delta-card').textContent = signed(metrics.drawdown_delta);
      document.getElementById('next-action-card').innerHTML = isScenarioSelection
        ? `<strong>情境 artifact</strong><br>${{selectedScenarioCell.artifactPath || '無'}}<br><small>判定：${{decisionLabels[selectedScenarioCell.decision] || selectedScenarioCell.decision || '尚未執行'}}</small>`
        : `<strong>下一步</strong><br>${{actionText(node.next_action)}}<br><small>候選目錄：${{node.candidate_dir || '無'}}</small>`;
      document.getElementById('scenario-count-label').textContent = `（${{scenario.scenario_count || 81}} 個情境）`;
      const dots = Array.from({{ length: 81 }}, (_, index) => `<button type="button" data-scenario="${{index + 1}}" title="情境 ${{index + 1}}"></button>`).join('');
      const scenarioDots = document.getElementById('scenario-dots');
      scenarioDots.innerHTML = dots;
      scenarioDots.querySelectorAll('button').forEach((button) => {{
        button.classList.toggle('is-active', Number(button.dataset.scenario) === Number(selectedScenarioNumber));
        button.addEventListener('click', () => {{
          scenarioDots.querySelectorAll('button').forEach((item) => item.classList.remove('is-active'));
          button.classList.add('is-active');
          const scenarioNumber = Number(button.dataset.scenario);
          const scenarioCell = scenarioPoints.find((point) => point.topicId === node.topic_id && point.scenarioIndex === scenarioNumber);
          renderInspector(node.topic_id, scenarioNumber, scenarioCell);
        }});
      }});
      document.getElementById('inspector-body').innerHTML = nodeNotes(node, selectedScenarioNumber, selectedScenarioCell);
    }}
    function renderMissionQueue() {{
      const root = document.getElementById('mission-list');
      root.innerHTML = `<table class="queue-table"><thead><tr><th>優先</th><th>節點ID</th><th>星區</th><th>原因</th><th>資源</th><th>狀態</th></tr></thead><tbody>` +
        payload.mission_queue.slice(0, 5).map((mission, index) => `
          <tr class="mission" data-topic-id="${{mission.topic_id}}">
            <td>${{index + 1}}</td>
            <td>${{mission.topic_id.split(':').pop().slice(0, 24)}}</td>
            <td>${{mission.family}}</td>
            <td>${{mission.reason}}</td>
            <td>GPU-0${{(index % 3) + 1}}</td>
            <td><span class="status-pill">已排隊</span></td>
          </tr>
        `).join('') + `</tbody></table>`;
      root.querySelectorAll('.mission').forEach((button) => {{
        button.addEventListener('click', () => renderInspector(button.dataset.topicId));
      }});
    }}
    function renderLegend() {{
      const counts = payload.summary.status_counts || {{}};
      const legendNames = {{
        pending: '未探索（迷霧）',
        low_information: '已探索',
        rejected: '已淘汰',
        follow_up_signal: '高風險洞察',
        effective_insight: '有效洞察',
        next_stage_candidate: '下階候選',
        breakthrough_candidate: '突破候選',
      }};
      document.getElementById('legend-grid').innerHTML = payload.legend.map((item) => `
        <div class="legend-item" data-status="${{item.id}}">
          <span class="legend-swatch" style="background:${{item.hex}}; color:${{item.hex}}"></span>
          <span><strong>${{legendNames[item.id] || item.label}}</strong></span>
          <b class="legend-count">${{formatNumber(counts[item.id] || 0)}}</b>
        </div>
      `).join('');
      document.querySelectorAll('#legend-grid .legend-item').forEach((item) => {{
        item.addEventListener('click', () => {{
          mapState.filter = mapState.filter === item.dataset.status ? null : item.dataset.status;
          applyMapState();
        }});
      }});
    }}
    function renderBreakthroughs() {{
      const hot = payload.nodes.filter((node) => ['follow_up_signal', 'next_stage_candidate', 'breakthrough_candidate'].includes(node.status)).slice(0, 4);
      document.getElementById('breakthrough-list').innerHTML = (hot.length ? hot : payload.nodes.slice(0, 3)).map((node) =>
        `<div class="break-row"><strong>${{displayText(node.title).slice(0, 24)}}</strong><span>${{payload.date}}</span></div>`
      ).join('');
    }}
    function applyMapState() {{
      const root = document.getElementById('star-map');
      const familyBands = document.getElementById('family-bands');
      const panel = document.querySelector('.map-panel');
      const shell = document.querySelector('.command-shell');
      const transform = mapTransform();
      root.style.transform = transform;
      if (familyBands) familyBands.style.transform = transform;
      panel.classList.toggle('hide-links', !mapState.links);
      panel.classList.toggle('hide-names', !mapState.names);
      panel.classList.toggle('hide-fog', !mapState.fog);
      panel.classList.toggle('hide-grid', !mapState.grid);
      shell.classList.toggle('focus-map', mapState.focus === true);
      document.querySelectorAll('.topic-hub').forEach((item) => {{
        const topic = nodesById.get(item.dataset.topicId);
        const hidden = mapState.filter && topic && topic.status !== mapState.filter;
        item.classList.toggle('is-filtered-out', Boolean(hidden));
      }});
      drawScenarioCanvas();
      document.querySelectorAll('#legend-grid .legend-item').forEach((item) => {{
        item.classList.toggle('is-active', mapState.filter === item.dataset.status);
      }});
      document.querySelector('[data-tool="fov"]').textContent = `視野 ${{Math.round(mapState.zoom * 100)}}%`;
      document.querySelector('[data-tool="grid"]').textContent = `格線 ${{mapState.grid ? '開' : '關'}}`;
      document.querySelector('[data-tool="names"]').textContent = `名稱 ${{mapState.names ? '開' : '關'}}`;
      document.querySelector('[data-tool="links"]').textContent = `連線 ${{mapState.links ? '開' : '關'}}`;
      document.querySelector('[data-tool="fog"]').textContent = `迷霧 ${{mapState.fog ? '開' : '關'}}`;
      document.querySelectorAll('.map-toolstrip span').forEach((item) => {{
        const key = item.dataset.tool;
        item.classList.toggle('is-off', key !== 'fov' && mapState[key] === false);
      }});
    }}
    function focusFamily(index) {{
      const family = payload.families[index % payload.families.length];
      const node = payload.nodes.find((item) => item.family === family.id) || payload.nodes[0];
      if (node) renderInspector(node.topic_id);
      mapState.filter = null;
      document.getElementById('goto-sector').textContent = family.label;
      applyMapState();
    }}
    function downloadReport() {{
      const blob = new Blob([JSON.stringify(payload, null, 2)], {{ type: 'application/json' }});
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `research_fog_map_${{payload.date}}.json`;
      anchor.click();
      URL.revokeObjectURL(url);
    }}
    function wireControls() {{
      document.querySelectorAll('.nav-item').forEach((item) => {{
        item.addEventListener('click', () => {{
          document.querySelectorAll('.nav-item').forEach((nav) => nav.classList.remove('is-active'));
          item.classList.add('is-active');
          const mode = item.dataset.nav;
          if (mode === 'star-map') {{ mapState.filter = null; resetViewport(1); mapState.focus = false; }}
          if (mode === 'dashboard') {{ mapState.filter = null; resetViewport(0.92); }}
          if (mode === 'tech-tree') {{ mapState.links = true; mapState.names = true; resetViewport(1.08); }}
          if (mode === 'signals') {{ mapState.filter = 'follow_up_signal'; }}
          if (mode === 'backtest-lab') {{ resetViewport(1.15); renderInspector(payload.default_selected_topic_id); }}
          if (mode === 'reports') downloadReport();
          if (mode === 'settings') {{ mapState.fog = !mapState.fog; }}
          applyMapState();
        }});
      }});
      document.querySelectorAll('.control-btn').forEach((button) => {{
        button.addEventListener('click', () => {{
          const action = button.dataset.control;
          if (action === 'reset') {{ resetViewport(1); mapState.filter = null; mapState.focus = false; }}
          if (action === 'zoom-in') setZoom(mapState.zoom * 1.28);
          if (action === 'zoom-out') setZoom(mapState.zoom / 1.28);
          if (action === 'focus') mapState.focus = !mapState.focus;
          applyMapState();
        }});
      }});
      document.getElementById('goto-sector').addEventListener('click', () => {{
        mapState.sectorIndex = (mapState.sectorIndex + 1) % payload.families.length;
        focusFamily(mapState.sectorIndex);
      }});
      document.querySelectorAll('.map-toolstrip span').forEach((item) => {{
        item.addEventListener('click', () => {{
          const tool = item.dataset.tool;
          if (tool === 'fov') {{
            if (mapState.zoom >= 3.5) resetViewport(1);
            else setZoom(mapState.zoom * 1.55);
          }}
          if (tool !== 'fov') mapState[tool] = !mapState[tool];
          applyMapState();
        }});
      }});
    }}
    async function loadLatestPayload() {{
      try {{
        const response = await fetch(`research_fog_map_latest.json?ts=${{Date.now()}}`, {{ cache: 'no-store' }});
        if (response.ok) payload = await response.json();
      }} catch (error) {{
        console.warn('使用 embedded fallback payload', error);
      }}
      nodesById = new Map(payload.nodes.map((node) => [node.topic_id, node]));
      renderHud();
      renderFamilies();
      renderMap();
      renderMissionQueue();
      renderLegend();
      renderBreakthroughs();
      renderInspector(payload.default_selected_topic_id || (payload.nodes[0] && payload.nodes[0].topic_id));
      wireControls();
    }}
    loadLatestPayload();
  </script>
</body>
</html>
"""


def main() -> int:
    args = parse_args()
    output_dir = resolve_path(args.output_dir)
    if output_dir is None:
        raise RuntimeError("output directory resolution failed")
    payload = build_payload(args.date)
    json_path = output_dir / f"research_fog_map_{args.date}.json"
    latest_json_path = output_dir / "research_fog_map_latest.json"
    html_path = output_dir / "index.html"
    write_json(json_path, payload)
    write_json(latest_json_path, payload)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(render_html(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "source_mode": payload["source_mode"],
                "html": repo_path(html_path),
                "payload": repo_path(json_path),
                "latest": repo_path(latest_json_path),
                "total_topics": payload["summary"]["total_topics"],
                "processed_combos": payload["summary"]["processed_combos"],
                "expanded_universe_total": payload["summary"]["expanded_universe_total"],
                "expanded_processed": payload["summary"]["expanded_processed"],
                "expanded_progress_pct": payload["summary"]["expanded_progress_pct"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
