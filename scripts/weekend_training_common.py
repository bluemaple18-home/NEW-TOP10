#!/usr/bin/env python3
"""Weekend training 共用工具。

這裡只處理 research artifact 的 deterministic 分類、分派與驗證輔助；
不改 production ranking、不訓練模型、不觸碰 Clawd。
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import os
import re
from typing import Any

from research_map_contract import (
    BASE_DIMENSION_KEYS,
    SCENARIO_DIMENSION_GRID,
    V2_DEFAULT_COORDINATES,
    V2_DIMENSION_VALUES,
    apply_run_history,
    build_combo_registry,
    canonicalize_lifecycle_history,
    canonicalize_lifecycle_topics,
    default_v2_dimensions,
    expanded_universe_total,
    latest_by_combo,
    read_jsonl,
    status_from_insight,
    v2_combo_id,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AUTO_DIR = PROJECT_ROOT / "artifacts" / "autonomous_research"
MAP_PATH = PROJECT_ROOT / "artifacts" / "research_map" / "research_fog_map_latest.json"
REVIEWS_DIR = PROJECT_ROOT / "artifacts" / "research_reviews"
WEEKEND_DIR = PROJECT_ROOT / "artifacts" / "weekend_training"
RUN_HISTORY_PATH = AUTO_DIR / "run_history.jsonl"
TOPIC_REGISTRY_PATH = AUTO_DIR / "topic_registry.json"
PRODUCTION_IMPACT = "NO_PRODUCTION_CHANGE"

SUPPORTED_ENTRY_FILTERS = {"TOPIC_DEFAULT", "LOG_GATE", "PERCENTILE_GATE", "LOG_GATE_NON_WORSENING"}
UNSUPPORTED_REGIME_GATES = {"RISK_OFF_ONLY", "PANIC_SELLING_ONLY", "NEUTRAL_ONLY"}
UNSUPPORTED_CATEGORIES = {
    "UNSUPPORTED_RANKING_DIR_MISSING",
    "UNSUPPORTED_ENTRY_FILTER_NOT_AVAILABLE",
    "UNSUPPORTED_TOPIC_NO_CANDIDATE_DIR",
    "UNSUPPORTED_REGIME_SLICE_NO_DATA",
    "UNSUPPORTED_RUNNER_CONTRACT",
    "UNSUPPORTED_OTHER",
}
REPLAY_READY_STATUSES = {"EXECUTED_REPLAY", "NEXT_STAGE_CANDIDATE", "REJECTED", "LOW_INFORMATION"}
REPLAY_RUNNER = "scripts/run_capital_aware_replay.py"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def repo_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def resolve_path(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any], *, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if compact:
        text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    else:
        text = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False)
    path.write_text(text + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_topics() -> list[dict[str, Any]]:
    payload = read_json(TOPIC_REGISTRY_PATH)
    topics = payload.get("topics") if isinstance(payload.get("topics"), list) else []
    return canonicalize_lifecycle_topics(topics)


def load_map() -> dict[str, Any]:
    return read_json(MAP_PATH)


def load_history() -> list[dict[str, Any]]:
    return canonicalize_lifecycle_history(read_jsonl(RUN_HISTORY_PATH))


def all_v2_dimensions(base_dimensions: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    base = {key: str(base_dimensions.get(key) or "") for key in BASE_DIMENSION_KEYS}
    for regime_gate in V2_DIMENSION_VALUES["regime_gate"]:
        for risk_guard in V2_DIMENSION_VALUES["risk_guard"]:
            for entry_filter in V2_DIMENSION_VALUES["entry_filter"]:
                rows.append(
                    {
                        **base,
                        "regime_gate": regime_gate,
                        "risk_guard": risk_guard,
                        "entry_filter": entry_filter,
                    }
                )
    return rows


def gross_values(regime_gate: str, risk_guard: str) -> dict[str, float]:
    values = {
        "big_bull": 0.65,
        "risk_on": 0.65,
        "high_choppy": 0.65,
        "neutral": 0.65,
        "risk_off": 0.65,
    }
    if regime_gate == "BIG_BULL_ONLY":
        values.update({"risk_on": 0.0, "high_choppy": 0.0, "neutral": 0.0, "risk_off": 0.0})
    elif regime_gate == "BIG_BULL_HIGH_CHOPPY":
        values.update({"risk_on": 0.0, "neutral": 0.0, "risk_off": 0.0})
    elif regime_gate == "EXCLUDE_RISK_OFF_PANIC":
        values["risk_off"] = 0.0
    if risk_guard == "RISK_OFF_CASH_RAISE":
        values["risk_off"] = min(values["risk_off"], 0.30)
    elif risk_guard in {"RISK_OFF_DISABLE", "PANIC_DISABLE"}:
        values["risk_off"] = 0.0
    return values


def gross_signature(regime_gate: str, risk_guard: str) -> str:
    values = gross_values(regime_gate, risk_guard)
    return "|".join(f"{key}:{values[key]:.2f}" for key in sorted(values))


def sibling_rankings_dir(candidate_dir: str, entry_filter: str, role: str) -> Path:
    if role == "baseline":
        override = os.environ.get("TOP10_BASELINE_RANKINGS_DIR")
        if override:
            path = Path(override).expanduser()
            return path if path.is_absolute() else PROJECT_ROOT / path
    path = PROJECT_ROOT / candidate_dir
    parent = path.parent
    if role == "baseline":
        return parent / "production"
    if entry_filter == "TOPIC_DEFAULT":
        return path
    if entry_filter == "PERCENTILE_GATE":
        if path.name == "percentile_gate":
            return path
        if (path / "percentile_gate").exists():
            return path / "percentile_gate"
        return parent / "percentile_gate"
    if path.name == "log_gate":
        return path
    if (path / "log_gate").exists():
        return path / "log_gate"
    if any(path.glob("ranking_*.csv")):
        return path
    return parent / "log_gate"


def rankings_dir_family(candidate_dir: str, entry_filter: str) -> str:
    if entry_filter == "TOPIC_DEFAULT":
        return Path(candidate_dir).name or "topic_default"
    if entry_filter == "PERCENTILE_GATE":
        return "percentile_gate"
    return "log_gate"


def unsupported_reason(topic: dict[str, Any], dimensions: dict[str, str]) -> str | None:
    regime_gate = dimensions["regime_gate"]
    entry_filter = dimensions["entry_filter"]
    candidate_dir = str(topic.get("candidate_dir") or "")
    if not candidate_dir:
        return "UNSUPPORTED_TOPIC_NO_CANDIDATE_DIR"
    if regime_gate in UNSUPPORTED_REGIME_GATES:
        return f"UNSUPPORTED_REGIME_GATE:{regime_gate}"
    if entry_filter not in SUPPORTED_ENTRY_FILTERS:
        return f"UNSUPPORTED_ENTRY_FILTER:{entry_filter}"
    baseline = sibling_rankings_dir(candidate_dir, entry_filter, "baseline")
    candidate = sibling_rankings_dir(candidate_dir, entry_filter, "candidate")
    if not baseline.exists():
        return f"MISSING_BASELINE_RANKINGS_DIR:{repo_path(baseline)}"
    if not candidate.exists():
        return f"MISSING_CANDIDATE_RANKINGS_DIR:{repo_path(candidate)}"
    return None


def unsupported_detail(reason: str | None) -> dict[str, Any]:
    """把 unsupported reason 正規化成可彙總、可解除的分類契約。"""

    reason_text = str(reason or "UNSUPPORTED_OTHER")
    if reason_text == "UNSUPPORTED_TOPIC_NO_CANDIDATE_DIR":
        category = "UNSUPPORTED_TOPIC_NO_CANDIDATE_DIR"
        can_be_unblocked = True
        requirement = "補齊 topic_registry.candidate_dir，讓 runner 能定位候選 ranking 目錄。"
    elif reason_text.startswith("UNSUPPORTED_ENTRY_FILTER:"):
        category = "UNSUPPORTED_ENTRY_FILTER_NOT_AVAILABLE"
        can_be_unblocked = True
        requirement = "替 entry_filter 增加 runner adapter，或將該格映射到已支援的 replay gate。"
    elif reason_text.startswith("UNSUPPORTED_REGIME_GATE:"):
        category = "UNSUPPORTED_REGIME_SLICE_NO_DATA"
        can_be_unblocked = True
        requirement = "補齊 regime slice 資料/合約，讓該 regime gate 可被 replay runner 驗證。"
    elif reason_text.startswith("MISSING_BASELINE_RANKINGS_DIR:") or reason_text.startswith("MISSING_CANDIDATE_RANKINGS_DIR:"):
        category = "UNSUPPORTED_RANKING_DIR_MISSING"
        can_be_unblocked = True
        requirement = "產生或接上缺少的 baseline/candidate ranking 目錄。"
    elif reason_text == "NO_SUPPORTED_REPRESENTATIVE":
        category = "UNSUPPORTED_RUNNER_CONTRACT"
        can_be_unblocked = True
        requirement = "補齊 equivalence/representative runner contract，讓該群至少有一個可跑代表格。"
    elif reason_text.startswith("UNSUPPORTED_RUNNER_CONTRACT"):
        category = "UNSUPPORTED_RUNNER_CONTRACT"
        can_be_unblocked = True
        requirement = "補齊 runner contract 或資料轉接層。"
    else:
        category = "UNSUPPORTED_OTHER"
        can_be_unblocked = False
        requirement = "人工檢視 unsupported_reason 後再拆成穩定分類。"
    return {
        "unsupported_reason": reason_text,
        "unsupported_category": category,
        "can_be_unblocked": can_be_unblocked,
        "unblock_requirement": requirement,
    }


def rule_prune_reason(dimensions: dict[str, str]) -> str | None:
    # 第一批 burn-down 不讓高集中度格子進昂貴 replay；這是研究 queue policy，不是 production 判斷。
    if dimensions.get("group_exposure") == "0.55":
        return "RULE_PRUNE_HIGH_GROUP_EXPOSURE_FIRST_PASS"
    if dimensions.get("stop_loss") == "0.08" and dimensions.get("take_profit") == "none":
        return "RULE_PRUNE_TIGHT_STOP_WITHOUT_TAKE_PROFIT"
    return None


def current_status_from_record(record: dict[str, Any] | None) -> str:
    if not record:
        return "PENDING"
    insight = str(record.get("insight_level") or "")
    decision = str(record.get("decision") or "")
    if insight in {"next_stage", "breakthrough"} or decision in {"CONFIRMED_FOR_NEXT_REPLAY", "NEXT_STAGE_CANDIDATE"}:
        return "NEXT_STAGE_CANDIDATE"
    if insight == "rejected" or decision in {"REJECT_FOR_NOW", "REJECTED"}:
        return "REJECTED"
    if insight in {"ordinary", "low_information"}:
        return "LOW_INFORMATION"
    return "EXECUTED_REPLAY"


def current_status_from_base_scenario(scenario: dict[str, Any] | None) -> str:
    if not scenario or scenario.get("status") == "pending":
        return "PENDING"
    status = str(scenario.get("status") or "")
    if status == "rejected":
        return "REJECTED"
    if status in {"next_stage_candidate", "breakthrough_candidate"}:
        return "NEXT_STAGE_CANDIDATE"
    if status == "low_information":
        return "LOW_INFORMATION"
    return "EXECUTED_REPLAY"


def is_default_coordinate(dimensions: dict[str, str]) -> bool:
    return all(str(dimensions.get(key)) == value for key, value in V2_DEFAULT_COORDINATES.items())


def equivalence_key(topic: dict[str, Any], dimensions: dict[str, str]) -> str:
    return "|".join(
        [
            str(topic.get("topic_id") or ""),
            f"horizon={dimensions['horizon']}",
            f"stop_loss={dimensions['stop_loss']}",
            f"take_profit={dimensions['take_profit']}",
            f"group_exposure={dimensions['group_exposure']}",
            f"regime_gate_effective_bucket={gross_signature(dimensions['regime_gate'], dimensions['risk_guard'])}",
            "risk_guard_effective_bucket=gross_signature",
            f"entry_filter={dimensions['entry_filter']}",
            f"rankings_dir_family={rankings_dir_family(str(topic.get('candidate_dir') or ''), dimensions['entry_filter'])}",
        ]
    )


def priority_score(row: dict[str, Any], stage2_combo_ids: set[str]) -> int:
    dim = row.get("dimensions") if isinstance(row.get("dimensions"), dict) else {}
    score = 0
    if row.get("combo_id") in stage2_combo_ids:
        score += 1000
    if str(dim.get("horizon")) == "3":
        score += 80
    if str(dim.get("stop_loss")) == "none":
        score += 50
    if str(dim.get("take_profit")) in {"0.25", "0.15"}:
        score += 40
    if str(dim.get("group_exposure")) == "none":
        score += 30
    elif str(dim.get("group_exposure")) == "0.35":
        score += 15
    if str(dim.get("entry_filter")) in {"LOG_GATE", "LOG_GATE_NON_WORSENING"}:
        score += 20
    if str(dim.get("regime_gate")) in {"ALL", "EXCLUDE_RISK_OFF_PANIC", "BIG_BULL_HIGH_CHOPPY"}:
        score += 10
    return score


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or "") for row in rows).items()))


def inventory_paths(date: str) -> tuple[Path, Path]:
    return WEEKEND_DIR / f"weekend_universe_inventory_{date}.json", WEEKEND_DIR / f"weekend_universe_inventory_{date}.md"


def queue_paths(date: str) -> tuple[Path, Path]:
    return WEEKEND_DIR / f"weekend_frontier_queue_{date}.json", WEEKEND_DIR / f"weekend_frontier_queue_{date}.md"


def representative_paths(date: str) -> tuple[Path, Path]:
    return WEEKEND_DIR / f"weekend_representative_replay_{date}.json", WEEKEND_DIR / f"weekend_representative_replay_{date}.md"


def survivor_paths(date: str) -> tuple[Path, Path]:
    return WEEKEND_DIR / f"weekend_survivor_deep_replay_{date}.json", WEEKEND_DIR / f"weekend_survivor_deep_replay_{date}.md"


def rollup_paths(date: str) -> tuple[Path, Path]:
    return WEEKEND_DIR / f"weekend_training_rollup_{date}.json", WEEKEND_DIR / f"weekend_training_rollup_{date}.md"


def stage2_combo_ids(date: str) -> set[str]:
    payload = read_json(latest_stage2_path(date))
    rows: list[dict[str, Any]] = []
    for key in ["stage2_candidates", "shadow_monitor_only", "rejected"]:
        values = payload.get(key) if isinstance(payload.get(key), list) else []
        rows.extend(row for row in values if isinstance(row, dict))
    return {str(row.get("combo_id") or "") for row in rows if row.get("combo_id")}


def latest_stage2_path(date: str) -> Path:
    dated = REVIEWS_DIR / f"liquidity_replay_v2_stage2_{date}.json"
    if dated.exists():
        return dated
    pattern = re.compile(r"liquidity_replay_v2_stage2_\d{4}-\d{2}-\d{2}\.json$")
    candidates = sorted(path for path in REVIEWS_DIR.glob("liquidity_replay_v2_stage2_*.json") if pattern.match(path.name))
    return candidates[-1] if candidates else dated


def base_scenarios_by_v2_combo(topics: list[dict[str, Any]], history_records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    base_scenarios = apply_run_history(build_combo_registry(topics), history_records)
    return {str(row.get("v2_combo_id") or ""): row for row in base_scenarios if row.get("v2_combo_id")}
