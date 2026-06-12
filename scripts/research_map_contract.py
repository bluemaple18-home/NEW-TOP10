#!/usr/bin/env python3
"""Research map artifact contract helpers.

這裡只定義地圖連動契約：固定 combo id、JSONL run history、燈號分類。
不執行回測、不訓練模型、不改 production ranking。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCENARIO_DIMENSION_GRID = [
    {
        "horizon": horizon,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "group_exposure": group_exposure,
    }
    for horizon in ["3", "5", "10"]
    for stop_loss in ["none", "0.08", "0.12"]
    for take_profit in ["none", "0.15", "0.25"]
    for group_exposure in ["none", "0.35", "0.55"]
]

BASE_DIMENSION_KEYS = ("horizon", "stop_loss", "take_profit", "group_exposure")
V2_DIMENSION_SCHEMA_VERSION = "research-map-dimensions.v2"
V2_DEFAULT_COORDINATES = {
    "regime_gate": "ALL",
    "risk_guard": "NONE",
    "entry_filter": "TOPIC_DEFAULT",
}
V2_DIMENSION_VALUES = {
    "regime_gate": [
        "ALL",
        "BIG_BULL_ONLY",
        "BIG_BULL_HIGH_CHOPPY",
        "EXCLUDE_RISK_OFF_PANIC",
        "RISK_OFF_ONLY",
        "PANIC_SELLING_ONLY",
        "NEUTRAL_ONLY",
    ],
    "risk_guard": [
        "NONE",
        "RISK_OFF_CASH_RAISE",
        "RISK_OFF_DISABLE",
        "PANIC_DISABLE",
    ],
    "entry_filter": [
        "TOPIC_DEFAULT",
        "LOG_GATE",
        "PERCENTILE_GATE",
        "LOG_GATE_NON_WORSENING",
    ],
}

INSIGHT_TO_STATUS = {
    "unexplored": ("pending", "fog_gray", "未探索"),
    "ordinary": ("low_information", "blue", "已探索"),
    "rejected": ("rejected", "red", "已淘汰"),
    "risk_worse_return_positive": ("follow_up_signal", "yellow", "待追蹤"),
    "effective": ("effective_insight", "green", "有效洞察"),
    "next_stage": ("next_stage_candidate", "purple", "下階候選"),
    "breakthrough": ("breakthrough_candidate", "gold", "突破候選"),
}


def base_scenarios_per_topic() -> int:
    return len(SCENARIO_DIMENSION_GRID)


def expansion_multiplier() -> int:
    multiplier = 1
    for values in V2_DIMENSION_VALUES.values():
        multiplier *= len(values)
    return multiplier


def expanded_scenarios_per_topic() -> int:
    return base_scenarios_per_topic() * expansion_multiplier()


def expanded_universe_total(topic_count: int) -> int:
    return topic_count * expanded_scenarios_per_topic()


def default_v2_dimensions(dimensions: dict[str, Any]) -> dict[str, str]:
    base = {key: str(dimensions.get(key) or "") for key in BASE_DIMENSION_KEYS}
    expanded = {key: str(dimensions.get(key) or default) for key, default in V2_DEFAULT_COORDINATES.items()}
    return {**base, **expanded}


def v2_combo_id(topic: dict[str, Any], dimensions: dict[str, Any]) -> str:
    expanded = default_v2_dimensions(dimensions)
    topic_key = stable_topic_key(topic)
    return "|".join(
        [
            topic_key,
            f"horizon_{expanded['horizon']}",
            f"stop_{expanded['stop_loss']}",
            f"take_profit_{expanded['take_profit']}",
            f"group_exposure_{expanded['group_exposure']}",
            f"regime_gate_{expanded['regime_gate']}",
            f"risk_guard_{expanded['risk_guard']}",
            f"entry_filter_{expanded['entry_filter']}",
        ]
    )


def dimension_schema_payload() -> dict[str, Any]:
    return {
        "version": V2_DIMENSION_SCHEMA_VERSION,
        "base_dimensions": list(BASE_DIMENSION_KEYS),
        "expanded_dimensions": [*BASE_DIMENSION_KEYS, *V2_DIMENSION_VALUES.keys()],
        "dimension_values": V2_DIMENSION_VALUES,
        "default_coordinates": V2_DEFAULT_COORDINATES,
        "base_scenarios_per_topic": base_scenarios_per_topic(),
        "expanded_scenarios_per_topic": expanded_scenarios_per_topic(),
        "expansion_multiplier": expansion_multiplier(),
    }


def stable_topic_key(topic: dict[str, Any]) -> str:
    topic_id = str(topic.get("topic_id") or "").strip()
    if ":" in topic_id:
        return topic_id.split(":", 1)[1]
    return topic_id or str(topic.get("candidate_dir") or "unknown").replace("/", "-")


def combo_id(topic: dict[str, Any], dimensions: dict[str, str]) -> str:
    topic_key = stable_topic_key(topic)
    return "|".join(
        [
            topic_key,
            f"horizon_{dimensions['horizon']}",
            f"stop_{dimensions['stop_loss']}",
            f"take_profit_{dimensions['take_profit']}",
            f"group_exposure_{dimensions['group_exposure']}",
        ]
    )


def build_combo_registry(topics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    combos: list[dict[str, Any]] = []
    for topic in topics:
        for index, dimensions in enumerate(SCENARIO_DIMENSION_GRID, start=1):
            combos.append(
                {
                    "combo_id": combo_id(topic, dimensions),
                    "topic_id": topic.get("topic_id"),
                    "scenario_index": index,
                    "dimensions": dimensions,
                    "candidate_dir": topic.get("candidate_dir"),
                }
            )
    return combos


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        text = line.strip()
        if not text:
            continue
        try:
            row = json.loads(text)
        except json.JSONDecodeError:
            rows.append({"combo_id": f"invalid-line-{line_number}", "status": "INVALID_JSON", "line_number": line_number})
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]], *, replace_smoke: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = read_jsonl(path)
    if replace_smoke:
        existing = [row for row in existing if row.get("source") != "research_map_linkage_smoke"]
    payload = existing + rows
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False) for row in payload) + "\n", encoding="utf-8")


def latest_by_combo(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        combo = str(row.get("combo_id") or "")
        if not combo:
            continue
        current = latest.get(combo)
        current_time = str((current or {}).get("finished_at") or "")
        row_time = str(row.get("finished_at") or "")
        if current is None or row_time >= current_time:
            latest[combo] = row
    return latest


def infer_insight_level(record: dict[str, Any] | None) -> str:
    if not record:
        return "unexplored"
    explicit = str(record.get("insight_level") or "").strip()
    if explicit in INSIGHT_TO_STATUS:
        return explicit
    decision = str(record.get("decision") or "")
    return_delta = record.get("return_delta")
    drawdown_delta = record.get("drawdown_delta")
    score_delta = record.get("score_delta")
    if decision == "REJECTED_BY_STRATEGY_MATRIX":
        return "rejected"
    if decision == "PARTIAL_SCORE_ONLY":
        return "risk_worse_return_positive"
    try:
        if float(return_delta or 0) > 0 and float(drawdown_delta or 0) < 0:
            return "risk_worse_return_positive"
        if float(score_delta or 0) >= 0.15:
            return "breakthrough"
        if float(score_delta or 0) > 0:
            return "effective"
    except (TypeError, ValueError):
        pass
    if decision == "CONFIRMED_FOR_NEXT_REPLAY":
        return "next_stage"
    return "ordinary"


def status_from_insight(insight_level: str) -> dict[str, str]:
    status_id, color, label = INSIGHT_TO_STATUS.get(insight_level, INSIGHT_TO_STATUS["ordinary"])
    return {"id": status_id, "color": color, "label": label}


def apply_run_history(combos: list[dict[str, Any]], records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest = latest_by_combo(records)
    scenarios: list[dict[str, Any]] = []
    for combo in combos:
        record = latest.get(str(combo.get("combo_id")))
        insight = infer_insight_level(record)
        status = status_from_insight(insight)
        scenarios.append(
            {
                **combo,
                "map_version": "v2",
                "base_combo_id": combo.get("combo_id"),
                "v2_combo_id": v2_combo_id({"topic_id": combo.get("topic_id"), "candidate_dir": combo.get("candidate_dir")}, combo.get("dimensions") or {}),
                "v2_dimensions": default_v2_dimensions(combo.get("dimensions") or {}),
                "dimension_schema_version": V2_DIMENSION_SCHEMA_VERSION,
                "status": status["id"],
                "status_color": status["color"],
                "status_label": status["label"],
                "insight_level": insight,
                "run_status": (record or {}).get("status"),
                "decision": (record or {}).get("decision"),
                "return_delta": (record or {}).get("return_delta"),
                "drawdown_delta": (record or {}).get("drawdown_delta"),
                "score_delta": (record or {}).get("score_delta"),
                "artifact_path": (record or {}).get("artifact_path"),
                "finished_at": (record or {}).get("finished_at"),
                "has_artifact": bool((record or {}).get("artifact_path")),
            }
        )
    return scenarios


def progress_summary(scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for scenario in scenarios:
        status = str(scenario.get("status") or "pending")
        counts[status] = counts.get(status, 0) + 1
    total = len(scenarios)
    pending = counts.get("pending", 0)
    explored = total - pending
    return {
        "total_combos": total,
        "explored_combos": explored,
        "pending_combos": pending,
        "followup_signal_combos": counts.get("follow_up_signal", 0),
        "rejected_combos": counts.get("rejected", 0),
        "low_information_combos": counts.get("low_information", 0),
        "effective_insight_combos": counts.get("effective_insight", 0),
        "next_stage_combos": counts.get("next_stage_candidate", 0),
        "breakthrough_combos": counts.get("breakthrough_candidate", 0),
        "progress_pct": round(explored / total, 4) if total else 0.0,
        "status_counts": dict(sorted(counts.items())),
    }


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()
