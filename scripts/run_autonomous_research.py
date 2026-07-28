#!/usr/bin/env python3
"""自動研究發題與安全回測 runner。

此腳本負責做三件事：
1. 從既有 artifacts / ledger / external review 產生研究題目。
2. 選出可用既有 ranking artifacts 回測的題目。
3. 在 --execute 時只呼叫白名單回測腳本，不訓練模型、不改正式 ranking。
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.modeling.sealed_oos import build_regime_episode_split  # noqa: E402
from scripts.fog_daily_source_lineage import build_daily_source_lineage  # noqa: E402


ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
OUTPUT_DIR = ARTIFACTS_DIR / "autonomous_research"
LEDGER_PATH = ARTIFACTS_DIR / "model_experiments" / "model_experiment_ledger.json"
SCHEMA_VERSION = "autonomous-research-run.v1"
MANAGER_SCHEMA_VERSION = "autonomous-research-manager.v1"
TOPIC_BANK_SCHEMA_VERSION = "autonomous-research-topic-bank.v1"
RUNNER_REGISTRY_SCHEMA_VERSION = "autonomous-research-runner-registry.v1"
REGIME_RESEARCH_SCHEMA_VERSION = "closed-regime-research.v1"
BASE_REGIME_LABELS = {
    "BROAD_RISK_ON",
    "NARROW_LEADER",
    "CHOPPY_RANGE",
    "RISK_OFF",
    "PANIC_SELLING",
    "EARLY_REVERSAL",
    "MIXED_NEUTRAL",
    "UNKNOWN",
}
REGIME_FAMILY_TAGS = {"HIGH_CHOPPY", "BIG_BULL"}
FUNNEL_TRANSITIONS = {
    "REGISTERED": {"COARSE_SCREEN", "BLOCKED", "INSUFFICIENT_EVIDENCE"},
    "COARSE_SCREEN": {
        "SAME_REGIME_VALIDATION",
        "REJECTED",
        "NO_STRATEGY",
        "INSUFFICIENT_EVIDENCE",
        "BLOCKED",
    },
    "SAME_REGIME_VALIDATION": {"SEALED_OOS", "REJECTED", "INSUFFICIENT_EVIDENCE", "BLOCKED"},
    "SEALED_OOS": {"FORWARD_SHADOW", "REJECTED", "INSUFFICIENT_EVIDENCE", "BLOCKED"},
    "FORWARD_SHADOW": {"REGIME_POLICY_CANDIDATE", "MONITOR_ONLY", "REJECTED", "BLOCKED"},
}
ALLOWED_RUNNERS = {
    "scripts/run_backtest_strategy_matrix.py",
    "scripts/compare_strategy_matrices.py",
}
RUNNER_SPECS = {
    "strategy_matrix_comparison": {
        "runner": "strategy_matrix_comparison",
        "allowed_scripts": sorted(ALLOWED_RUNNERS),
        "step_count": 3,
        "does_not_fetch_data": True,
        "does_not_train_model": True,
        "does_not_change_production_ranking": True,
        "production_promotion_allowed": False,
        "output_decisions": [
            "CONFIRMED_FOR_NEXT_REPLAY",
            "PARTIAL_SCORE_ONLY",
            "REJECTED_BY_STRATEGY_MATRIX",
            "NO_COMPARISON_EVIDENCE",
            "NO_STRATEGY",
        ],
    }
}
BASELINE_RANKINGS_DIR = "artifacts/backtest/historical_rankings_current_model"
CONTROLLED_RERUN_POLICIES = {
    "confirmed_for_next_replay": {"max_run_count": 2, "cooldown_hours": 24},
    "partial_needs_followup": {"max_run_count": 3, "cooldown_hours": 24},
}
RANKING_FILE_NAME_PATTERN = re.compile(r"ranking_(\d{4}-\d{2}-\d{2})\.csv")


@dataclass(frozen=True)
class ResearchTopic:
    topic_id: str
    title: str
    hypothesis: str
    validation_plan: str
    runner: str
    candidate_dir: str
    baseline_dir: str
    score: float
    reasons: list[str]
    evidence_sources: list[str]
    ranking_file_count: int
    status: str = "candidate"
    validation_profile: str = "standard"
    horizons: str = ""
    stop_loss_pcts: str = ""
    take_profit_pcts: str = ""
    max_group_exposures: str = ""
    regime_identity: dict[str, Any] | None = None
    score_breakdown: dict[str, float] | None = None
    eligible: bool = True
    reason_code: str = "LEGACY_TOPIC"
    selection_rationale: dict[str, Any] | None = None


VALIDATION_PROFILES = [
    {
        "name": "standard",
        "title_suffix": "standard matrix",
        "hypothesis_suffix": "使用標準 horizons / stop-loss / take-profit / group exposure matrix。",
        "score_bonus": 0.0,
        "horizons": "3,5,10",
        "stop_loss_pcts": "none,0.08,0.12",
        "take_profit_pcts": "none,0.15,0.25",
        "max_group_exposures": "none,0.35,0.55",
    },
    {
        "name": "risk_guard",
        "title_suffix": "risk guard matrix",
        "hypothesis_suffix": "加強 stop-loss 與 group exposure 壓力檢查，驗證報酬是否不是靠集中風險撐起來。",
        "score_bonus": 6.0,
        "horizons": "3,5,10",
        "stop_loss_pcts": "0.06,0.08,0.10",
        "take_profit_pcts": "none,0.15,0.25",
        "max_group_exposures": "0.25,0.35,0.45",
    },
    {
        "name": "long_horizon",
        "title_suffix": "long horizon matrix",
        "hypothesis_suffix": "拉長持有 horizon，驗證候選策略是否只在短線噪音有效。",
        "score_bonus": 4.0,
        "horizons": "5,10,20",
        "stop_loss_pcts": "none,0.08,0.12",
        "take_profit_pcts": "none,0.20,0.30",
        "max_group_exposures": "none,0.35,0.55",
    },
    {
        "name": "tight_exit",
        "title_suffix": "tight exit matrix",
        "hypothesis_suffix": "使用較緊停損與較早停利，驗證候選策略是否能降低回撤。",
        "score_bonus": 3.0,
        "horizons": "3,5,10",
        "stop_loss_pcts": "0.05,0.08",
        "take_profit_pcts": "0.10,0.15,0.20",
        "max_group_exposures": "none,0.35",
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="generate autonomous research topics and optionally run safe backtests")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--output", default=None)
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument("--baseline-dir", default=BASELINE_RANKINGS_DIR)
    parser.add_argument("--candidate-dir", default=None, help="指定候選 ranking 目錄；未指定時由 autopilot 自己選")
    parser.add_argument("--topic-index", type=int, default=0)
    parser.add_argument("--max-topics", type=int, default=12)
    parser.add_argument("--min-ranking-files", type=int, default=3)
    parser.add_argument("--max-ranking-files", type=int, default=8)
    parser.add_argument("--horizons", default="3,5,10")
    parser.add_argument("--stop-loss-pcts", default="none,0.08,0.12")
    parser.add_argument("--take-profit-pcts", default="none,0.15,0.25")
    parser.add_argument("--max-group-exposures", default="none,0.35,0.55")
    parser.add_argument("--execute", action="store_true", help="實際執行 baseline/candidate strategy matrix 與 comparison")
    parser.add_argument("--execute-topic-count", type=int, default=1, help="單次 execute 最多執行幾個題目")
    parser.add_argument("--from-queue", action="store_true", help="從 manager queue 選下一批題目，而不是只用 --topic-index")
    parser.add_argument("--rerun", action="store_true", help="相容舊入口；不得繞過 manager 受控重跑政策")
    parser.add_argument("--include-rejected", action="store_true", help="相容舊入口；rejected topic 仍不得重跑")
    parser.add_argument("--no-manager-update", action="store_true", help="只產生本次 run artifact，不更新管理層狀態")
    parser.add_argument("--closed-regime-research", action="store_true", help="啟用 default-off 的 exact-match 封閉盤勢研究契約")
    parser.add_argument("--market-regime-history", default=None, help="含 as_of_date/base_regime/family_tags 的盤勢歷史 artifact")
    parser.add_argument("--research-contract", default="config/regime_research_contract.json")
    parser.add_argument("--coverage-map", default=None, help="既有 exact-match coverage records JSON；未指定視為尚無研究紀錄")
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


def slugify(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower()).strip("-")
    if not text:
        return "research-topic"
    if len(text) <= 90:
        return text
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]
    return f"{text[:80]}-{digest}"


def load_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def canonical_json_hash(value: Any) -> str:
    """產生不受 dict key 順序影響的 SHA-256。"""

    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def canonical_trade_dates(values: Any) -> list[str]:
    if not isinstance(values, list) or not values:
        raise ValueError("sealed trade dates 不可為空")
    dates = [str(item) for item in values]
    if any(not item for item in dates) or len(dates) != len(set(dates)):
        raise ValueError("sealed trade dates 缺失或重複")
    try:
        parsed = [date.fromisoformat(item) for item in dates]
    except ValueError as exc:
        raise ValueError("sealed trade dates 必須是 ISO YYYY-MM-DD") from exc
    if parsed != sorted(parsed):
        raise ValueError("sealed trade dates 必須嚴格遞增")
    return dates


def sealed_dataset_slice_hash(dataset_hash: str, trade_dates: list[str]) -> str:
    return canonical_json_hash({"dataset_hash": dataset_hash, "sealed_trade_dates": trade_dates})


def canonical_regime_identity(value: dict[str, Any]) -> dict[str, Any]:
    base = str(value.get("base_regime") or value.get("regime_label") or "").strip().upper()
    if base not in BASE_REGIME_LABELS:
        raise ValueError(f"未知 base regime：{base or '<empty>'}")
    raw_tags = value.get("family_tags") or []
    if not isinstance(raw_tags, (list, tuple, set)):
        raise ValueError("family_tags 必須是 list/tuple/set")
    tags = sorted({str(item).strip().upper() for item in raw_tags if str(item).strip()})
    unknown = sorted(set(tags) - REGIME_FAMILY_TAGS)
    if unknown:
        raise ValueError(f"未知 family tags：{unknown}")
    return {"base_regime": base, "family_tags": tags}


def regime_identity_id(value: dict[str, Any]) -> str:
    identity = canonical_regime_identity(value)
    return f"{identity['base_regime']}|{'+'.join(identity['family_tags'])}"


def regime_row_identity(row: dict[str, Any]) -> dict[str, Any]:
    tags = row.get("family_tags")
    if tags is None:
        tags = [tag for tag in sorted(REGIME_FAMILY_TAGS) if bool(row.get(f"family_{tag}"))]
    return canonical_regime_identity(
        {
            "base_regime": row.get("base_regime") or row.get("regime_label"),
            "family_tags": tags,
        }
    )


def validate_as_of_regime_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    violations = []
    for index, row in enumerate(rows):
        trade_date = str(row.get("trade_date") or "")
        as_of_date = str(row.get("as_of_date") or "")
        if not trade_date or not as_of_date:
            violations.append({"index": index, "reason_code": "MISSING_AS_OF_DATE"})
        elif as_of_date != trade_date:
            violations.append(
                {
                    "index": index,
                    "reason_code": "AS_OF_DATE_NOT_TRADE_DATE",
                    "trade_date": trade_date,
                    "as_of_date": as_of_date,
                }
            )
    return {"ok": not violations, "violations": violations}


def select_exact_regime_rows(rows: list[dict[str, Any]], target: dict[str, Any]) -> list[dict[str, Any]]:
    """只保留完全相同 identity；transition 與 UNKNOWN 一律 fail closed。"""

    expected = canonical_regime_identity(target)
    selected: list[dict[str, Any]] = []
    for row in rows:
        if bool(row.get("is_transition")):
            continue
        try:
            actual = regime_row_identity(row)
        except ValueError:
            continue
        if actual["base_regime"] == "UNKNOWN":
            continue
        if actual == expected:
            selected.append(row)
    return selected


def current_regime_context(path: Path, as_of_date: str) -> dict[str, Any]:
    payload = load_json(path)
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    as_of_check = validate_as_of_regime_rows(rows)
    if not as_of_check["ok"]:
        raise ValueError(f"market regime history 不符合 as_of 契約：{as_of_check['violations'][:3]}")
    eligible: list[dict[str, Any]] = []
    for row in rows:
        trade_date = str(row.get("trade_date") or "")
        observed_as_of = str(row.get("as_of_date") or "")
        if not trade_date or not observed_as_of:
            continue
        if trade_date <= as_of_date and observed_as_of <= as_of_date:
            eligible.append(row)
    if not eligible:
        raise ValueError("找不到具有 as_of_date 的當前盤勢；封閉研究不得回退到檔名判斷")
    row = sorted(eligible, key=lambda item: (str(item["trade_date"]), str(item["as_of_date"])))[-1]
    identity = regime_row_identity(row)
    if identity["base_regime"] == "UNKNOWN" or bool(row.get("is_transition")):
        raise ValueError("當前盤勢為 UNKNOWN/transition；只能 MONITOR_ONLY，不得執行正式研究")
    return {
        "as_of_date": as_of_date,
        "source_trade_date": str(row["trade_date"]),
        "identity": identity,
        "identity_id": regime_identity_id(identity),
        "source": repo_path(path),
    }


def score_regime_research_topic(
    topic: dict[str, Any],
    *,
    current_regime: dict[str, Any],
    coverage: dict[str, Any],
    information_gain: float,
    product_value: float,
    feasibility: float,
    estimated_compute_cost: float,
) -> dict[str, Any]:
    topic_identity = topic.get("regime_identity")
    if not isinstance(topic_identity, dict):
        return {
            "eligible": False,
            "reason_code": "MISSING_TOPIC_REGIME_IDENTITY",
            "priority": 0.0,
            "score_breakdown": {},
        }
    try:
        current = canonical_regime_identity(current_regime)
        candidate = canonical_regime_identity(topic_identity)
    except ValueError as exc:
        return {"eligible": False, "reason_code": "INVALID_REGIME_IDENTITY", "priority": 0.0, "error": str(exc)}
    if candidate != current:
        return {
            "eligible": False,
            "reason_code": "NON_EXACT_CURRENT_REGIME",
            "priority": 0.0,
            "score_breakdown": {"current_regime_relevance": 0.0},
        }
    cost = float(estimated_compute_cost)
    if cost <= 0:
        return {"eligible": False, "reason_code": "INVALID_COMPUTE_COST", "priority": 0.0, "score_breakdown": {}}
    breakdown = {
        "current_regime_relevance": 1.0,
        "evidence_gap": max(0.0, float(coverage.get("evidence_gap") or 0.0)),
        "expected_information_gain": max(0.0, float(information_gain)),
        "product_value": max(0.0, float(product_value)),
        "feasibility": max(0.0, float(feasibility)),
        "estimated_compute_cost": cost,
    }
    priority = (
        breakdown["current_regime_relevance"]
        * breakdown["evidence_gap"]
        * breakdown["expected_information_gain"]
        * breakdown["product_value"]
        * breakdown["feasibility"]
        / cost
    )
    return {
        "eligible": priority > 0,
        "reason_code": "ELIGIBLE" if priority > 0 else "ZERO_INFORMATION_VALUE",
        "priority": round(priority, 9),
        "score_breakdown": breakdown,
    }


def parameter_combinations(contract: dict[str, Any]) -> list[dict[str, Any]]:
    dimensions = contract.get("parameter_universe", {}).get("dimensions", [])
    executable = [row for row in dimensions if row.get("execution_status") == "EXECUTABLE"]
    names = [str(row["id"]) for row in executable]
    values = [list(row.get("allowed_values") or []) for row in executable]
    combinations: list[dict[str, Any]] = []
    for items in itertools.product(*values):
        params = dict(zip(names, items, strict=True))
        combinations.append(
            {
                "combination_id": canonical_json_hash(params),
                "parameters": params,
            }
        )
    return combinations


def validation_profile_combinations(
    horizons: str,
    stop_loss_pcts: str,
    take_profit_pcts: str,
    max_group_exposures: str,
) -> list[dict[str, Any]]:
    """展開實際送入 matrix 的 profile，作為不可變更的預註冊測試集合。"""

    def optional_floats(value: str) -> list[float | None]:
        values: list[float | None] = []
        for item in str(value).split(","):
            token = item.strip().lower()
            if token:
                values.append(None if token in {"none", "null", "-"} else float(token))
        return values

    return [
        {
            "horizon": horizon,
            "stop_loss_pct": stop_loss_pct,
            "take_profit_pct": take_profit_pct,
            "max_group_exposure": max_group_exposure,
        }
        for horizon, stop_loss_pct, take_profit_pct, max_group_exposure in itertools.product(
            [int(item.strip()) for item in str(horizons).split(",") if item.strip()],
            optional_floats(stop_loss_pcts),
            optional_floats(take_profit_pcts),
            optional_floats(max_group_exposures),
        )
    ]


def parameter_universe_summary(contract: dict[str, Any]) -> dict[str, Any]:
    combinations = parameter_combinations(contract)
    ids = [row["combination_id"] for row in combinations]
    return {
        "inventory_status": contract.get("parameter_universe", {}).get("inventory_status"),
        "declared_complete": bool(contract.get("parameter_universe", {}).get("declared_complete")),
        "executable_dimension_count": len(
            [
                row
                for row in contract.get("parameter_universe", {}).get("dimensions", [])
                if row.get("execution_status") == "EXECUTABLE"
            ]
        ),
        "legal_combination_count": len(combinations),
        "legal_combination_ids": ids,
        "combination_id_hash": canonical_json_hash(ids),
        "parameter_space_hash": canonical_json_hash(contract.get("parameter_universe", {})),
        "blocked_dimensions": contract.get("parameter_universe", {}).get("blocked_dimensions", []),
    }


def _validation_profile_partition_ids(contract: dict[str, Any]) -> dict[str, list[str]]:
    global_ids = set(parameter_universe_summary(contract)["legal_combination_ids"])
    partitions: dict[str, list[str]] = {}
    for profile in VALIDATION_PROFILES:
        combinations = validation_profile_combinations(
            profile["horizons"],
            profile["stop_loss_pcts"],
            profile["take_profit_pcts"],
            profile["max_group_exposures"],
        )
        ids = sorted(canonical_json_hash(combination) for combination in combinations)
        unexpected = sorted(set(ids) - global_ids)
        if unexpected:
            raise ValueError(
                f"validation profile {profile['name']} 包含 contract 外參數組合：{unexpected[:3]}"
            )
        partitions[str(profile["name"])] = ids
    return partitions


def statistical_family_contract(contract: dict[str, Any]) -> dict[str, Any]:
    """由 immutable research contract 推導唯一的統計 family authority。"""

    universe = parameter_universe_summary(contract)
    global_ids = sorted(str(item) for item in universe["legal_combination_ids"])
    global_family_id = canonical_json_hash(global_ids)
    familywise_alpha = float(
        (contract.get("multiple_testing_policy") or {}).get("familywise_alpha") or 0.0
    )
    if not global_ids or familywise_alpha <= 0:
        raise ValueError("research contract 缺少合法 statistical family 或 familywise alpha")
    partitions = _validation_profile_partition_ids(contract)
    return {
        "contract_hash": canonical_json_hash(contract),
        "parameter_space_hash": universe["parameter_space_hash"],
        "global_combination_ids": global_ids,
        "global_combination_ids_hash": universe["combination_id_hash"],
        "global_family_id": global_family_id,
        "global_family_size": len(global_ids),
        "familywise_alpha": familywise_alpha,
        "corrected_alpha": familywise_alpha / len(global_ids),
        "minimum_statistical_unit_count": math.ceil(
            math.log2(len(global_ids) / familywise_alpha)
        ),
        "partition_policy_id": "validation_profile_partition.v1",
        "legal_partitions": partitions,
    }


def validate_statistical_partition(
    *,
    partition_id: str,
    tested_combination_ids: list[str],
    authority: dict[str, Any],
) -> dict[str, Any]:
    """驗證 tested IDs 完整等於 contract 中一個合法 validation profile。"""

    ids = [str(item) for item in tested_combination_ids if str(item)]
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    if duplicates:
        return {
            "ok": False,
            "reason_code": "DUPLICATE_TESTED_COMBINATION_IDS",
            "duplicate_ids": duplicates,
        }
    partitions = authority.get("legal_partitions") or {}
    if partition_id not in partitions:
        return {
            "ok": False,
            "reason_code": "INVALID_PARTITION_ID",
            "legal_partition_ids": sorted(partitions),
        }
    expected = sorted(str(item) for item in partitions[partition_id])
    observed = sorted(ids)
    missing = sorted(set(expected) - set(observed))
    unexpected = sorted(set(observed) - set(expected))
    if observed != expected:
        return {
            "ok": False,
            "reason_code": "PARTITION_TESTED_IDS_MISMATCH",
            "missing_ids": missing,
            "unexpected_ids": unexpected,
        }
    return {
        "ok": True,
        "reason_code": "PARTITION_VALID",
        "partition_id": partition_id,
        "tested_combination_ids": expected,
        "tested_combination_count": len(expected),
        "tested_combination_ids_hash": canonical_json_hash(expected),
    }


def validation_profile_partition_coverage(contract: dict[str, Any]) -> dict[str, Any]:
    """列舉 public validation profiles 對 720-family 的 union 與交集政策。"""

    authority = statistical_family_contract(contract)
    membership: dict[str, list[str]] = {}
    partitions: dict[str, dict[str, Any]] = {}
    for partition_id, ids in authority["legal_partitions"].items():
        duplicate_ids = sorted({item for item in ids if ids.count(item) > 1})
        for combination_id in set(ids):
            membership.setdefault(combination_id, []).append(partition_id)
        partitions[partition_id] = {
            "tested_combination_ids": ids,
            "tested_combination_ids_hash": canonical_json_hash(ids),
            "tested_combination_count": len(ids),
            "duplicate_ids": duplicate_ids,
        }
    covered_ids = sorted(membership)
    missing_ids = sorted(set(authority["global_combination_ids"]) - set(covered_ids))
    overlapping_ids = sorted(
        combination_id
        for combination_id, partition_ids in membership.items()
        if len(partition_ids) > 1
    )
    status = (
        "PARTITION_COVERAGE_COMPLETE"
        if not missing_ids and not any(row["duplicate_ids"] for row in partitions.values())
        else "PARTITION_COVERAGE_INCOMPLETE"
    )
    return {
        "status": status,
        "global_family_size": authority["global_family_size"],
        "covered_unique_count": len(covered_ids),
        "missing_count": len(missing_ids),
        "missing_ids": missing_ids,
        "cross_partition_overlap_count": len(overlapping_ids),
        "cross_partition_overlap_ids": overlapping_ids,
        "policy": {
            "within_partition_duplicates": "forbidden",
            "cross_partition_overlap": (
                "allowed_for_separate_pre_registered_runs_but_counted_once_in_union"
            ),
            "coverage_claim": "complete_only_when_union_equals_global_family",
        },
        "partitions": partitions,
    }


def closed_mode_episode_evidence_status(
    *,
    exact_regime: str,
    available_episode_count: int,
    contract: dict[str, Any],
) -> dict[str, Any]:
    """在不降低 split gate 下回報 closed-mode 可用 episode 缺口。"""

    split_policy = contract.get("split_policy") or {}
    requirements = {
        "development": int(split_policy.get("development_episode_count") or 0),
        "validation": int(split_policy.get("validation_episode_count") or 0),
        "sealed": int(split_policy.get("sealed_episode_count") or 0),
    }
    remaining = max(0, int(available_episode_count))
    gaps: dict[str, int] = {}
    for role in ("development", "validation", "sealed"):
        allocated = min(remaining, requirements[role])
        remaining -= allocated
        gaps[role] = requirements[role] - allocated
    theoretical_minimum = sum(requirements.values())
    sufficient = not any(gaps.values())
    return {
        "decision": "EVIDENCE_READY" if sufficient else "INSUFFICIENT_EVIDENCE",
        "exact_regime": exact_regime,
        "available_episode_count": int(available_episode_count),
        "theoretical_minimum_episode_count": theoretical_minimum,
        "episode_gaps": gaps,
        "embargo_min_trade_days": int(split_policy.get("embargo_min_trade_days") or 0),
        "next_replay_condition": (
            None
            if sufficient
            else f"exact regime 累積至少 {theoretical_minimum} 個角色用 episode，"
            "另須完整 episode 覆蓋 embargo trade days"
        ),
    }


def build_regime_episodes(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    episodes: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for row in sorted(rows, key=lambda item: str(item.get("trade_date") or "")):
        if bool(row.get("is_transition")):
            current = None
            continue
        try:
            identity = regime_row_identity(row)
        except ValueError:
            current = None
            continue
        if identity["base_regime"] == "UNKNOWN":
            current = None
            continue
        identity_id = regime_identity_id(identity)
        trade_date = str(row.get("trade_date") or "")
        if not trade_date:
            current = None
            continue
        if current is None or current["regime_id"] != identity_id:
            current = {
                "regime_id": identity_id,
                "identity": identity,
                "start_date": trade_date,
                "end_date": trade_date,
                "trade_dates": [trade_date],
            }
            episodes.append(current)
        else:
            current["end_date"] = trade_date
            current["trade_dates"].append(trade_date)
    for episode in episodes:
        episode["episode_id"] = canonical_json_hash(
            {
                "regime_id": episode["regime_id"],
                "start_date": episode["start_date"],
                "end_date": episode["end_date"],
                "trade_dates": episode["trade_dates"],
            }
        )
    return episodes


def statistical_lineage_authority(
    *,
    rows: list[dict[str, Any]],
    contract: dict[str, Any],
    regime_id: str,
    horizons: list[int],
) -> dict[str, Any]:
    """由可信 runtime history 與 contract 重建唯一的 episode split lineage。"""

    as_of_check = validate_as_of_regime_rows(rows)
    if not as_of_check["ok"]:
        raise ValueError(
            f"market regime history 不符合 as-of 契約：{as_of_check['violations'][:3]}"
        )
    if not horizons or any(int(item) <= 0 for item in horizons):
        raise ValueError("statistical lineage horizons 必須是正整數")
    episodes = [
        episode
        for episode in build_regime_episodes(rows)
        if episode["regime_id"] == regime_id
    ]
    split_policy = contract.get("split_policy") or {}
    max_horizon = max(int(item) for item in horizons)
    split = build_regime_episode_split(
        episodes,
        horizon=max_horizon,
        min_development_episodes=int(
            split_policy.get("development_episode_count") or 2
        ),
        validation_episodes=int(split_policy.get("validation_episode_count") or 1),
        sealed_episodes=int(split_policy.get("sealed_episode_count") or 1),
        min_embargo_trade_days=int(
            split_policy.get("embargo_min_trade_days") or max_horizon
        ),
    )
    split_artifact = {
        "metadata": split.metadata,
        "development": split.development,
        "validation": split.validation,
        "embargo": split.embargo,
        "sealed": split.sealed,
    }
    split_ids = {
        role: list(split.metadata[f"{role}_episode_ids"])
        for role in ("development", "validation", "embargo", "sealed")
    }
    dataset_hash = canonical_json_hash(rows)
    sealed_trade_dates = canonical_trade_dates(
        [
            str(trade_date)
            for episode in split.sealed
            for trade_date in episode["trade_dates"]
        ]
    )
    return {
        "dataset_hash": dataset_hash,
        "split_id": split.metadata["split_id"],
        "split_artifact_hash": canonical_json_hash(split_artifact),
        "development_episode_ids": split_ids["development"],
        "validation_episode_ids": split_ids["validation"],
        "embargo_episode_ids": split_ids["embargo"],
        "sealed_episode_ids": split_ids["sealed"],
        "episode_split_ids_hash": canonical_json_hash(split_ids),
        "sealed_trade_dates": sealed_trade_dates,
        "sealed_trade_date_hash": canonical_json_hash(sealed_trade_dates),
        "sealed_dataset_slice_hash": sealed_dataset_slice_hash(
            dataset_hash,
            sealed_trade_dates,
        ),
        "split_artifact": split_artifact,
    }


def deterministic_experiment_id(candidate: dict[str, Any]) -> str:
    identity_payload = {
        key: value
        for key, value in candidate.items()
        if key not in {"experiment_id", "registry_record_hash", "registered_at"}
    }
    return f"experiment:{canonical_json_hash(identity_payload).split(':', 1)[1]}"


def build_experiment_pre_registration(values: dict[str, Any]) -> dict[str, Any]:
    candidate = {key: value for key, value in values.items() if key != "experiment_id"}
    candidate.setdefault("state", "REGISTERED")
    if candidate.get("sealed_trade_dates") is not None:
        trade_dates = canonical_trade_dates(candidate["sealed_trade_dates"])
        candidate["sealed_trade_dates"] = trade_dates
        candidate["sealed_trade_date_hash"] = canonical_json_hash(trade_dates)
        if candidate.get("dataset_hash"):
            candidate["sealed_dataset_slice_hash"] = sealed_dataset_slice_hash(
                str(candidate["dataset_hash"]),
                trade_dates,
            )
    return {**candidate, "experiment_id": deterministic_experiment_id(candidate)}


def validate_experiment_registration(candidate: dict[str, Any], registry: list[dict[str, Any]]) -> dict[str, Any]:
    experiment_id = str(candidate.get("experiment_id") or "")
    if not experiment_id:
        return {"ok": False, "reason_code": "MISSING_EXPERIMENT_ID"}
    sources = {str(item) for item in candidate.get("component_source_experiment_ids") or [] if str(item)}
    if sources and (experiment_id in sources or not bool(candidate.get("fresh_composition_experiment"))):
        return {"ok": False, "reason_code": "CROSS_EXPERIMENT_COMPOSITION"}
    prior_by_id = {
        str(row.get("experiment_id")): row
        for row in registry
        if row.get("experiment_id") and row.get("event_type") in {None, "PRE_REGISTRATION"}
    }
    if experiment_id in prior_by_id:
        return {"ok": False, "reason_code": "EXPERIMENT_ID_REUSE"}
    unknown_sources = sorted(sources - set(prior_by_id))
    if unknown_sources:
        return {
            "ok": False,
            "reason_code": "UNKNOWN_COMPONENT_SOURCE",
            "source_experiment_ids": unknown_sources,
        }
    source_hashes = candidate.get("component_source_hashes")
    if sources:
        if not isinstance(source_hashes, dict):
            return {"ok": False, "reason_code": "MISSING_COMPONENT_SOURCE_HASHES"}
        for source_id in sorted(sources):
            expected_hash = str(prior_by_id[source_id].get("registry_record_hash") or "")
            if not expected_hash or str(source_hashes.get(source_id) or "") != expected_hash:
                return {
                    "ok": False,
                    "reason_code": "UNTRACEABLE_COMPONENT_SOURCE",
                    "source_experiment_id": source_id,
                }
    sealed = {str(item) for item in candidate.get("sealed_episode_ids") or [] if str(item)}
    if not sealed:
        return {"ok": False, "reason_code": "MISSING_SEALED_EPISODES"}
    try:
        sealed_dates = canonical_trade_dates(candidate.get("sealed_trade_dates"))
    except ValueError as exc:
        return {"ok": False, "reason_code": "MISSING_CANONICAL_SEALED_DATES", "error": str(exc)}
    sealed_date_hash = canonical_json_hash(sealed_dates)
    if str(candidate.get("sealed_trade_date_hash") or "") != sealed_date_hash:
        return {"ok": False, "reason_code": "SEALED_TRADE_DATE_HASH_MISMATCH"}
    expected_slice_hash = sealed_dataset_slice_hash(str(candidate.get("dataset_hash") or ""), sealed_dates)
    if str(candidate.get("sealed_dataset_slice_hash") or "") != expected_slice_hash:
        return {"ok": False, "reason_code": "SEALED_DATASET_SLICE_HASH_MISMATCH"}
    for row in registry:
        used = {str(item) for item in row.get("sealed_episode_ids") or [] if str(item)}
        overlap = sorted(sealed & used)
        used_dates = {str(item) for item in row.get("sealed_trade_dates") or [] if str(item)}
        overlapping_dates = sorted(set(sealed_dates) & used_dates)
        same_date_hash = bool(row.get("sealed_trade_date_hash")) and row.get("sealed_trade_date_hash") == sealed_date_hash
        same_slice_hash = (
            bool(row.get("sealed_dataset_slice_hash"))
            and row.get("sealed_dataset_slice_hash") == expected_slice_hash
        )
        if overlap or overlapping_dates or same_date_hash or same_slice_hash:
            return {
                "ok": False,
                "reason_code": "SEALED_DATASET_REUSE",
                "source_experiment_id": row.get("experiment_id"),
                "overlapping_episode_ids": overlap,
                "overlapping_trade_dates": overlapping_dates,
            }
    required = {
        "research_question",
        "baseline_id",
        "regime_id",
        "dataset_hash",
        "split_id",
        "parameter_space_hash",
        "metric_policy_hash",
        "sealed_trade_date_hash",
        "sealed_dataset_slice_hash",
    }
    missing = sorted(key for key in required if not candidate.get(key))
    if missing:
        return {"ok": False, "reason_code": "INCOMPLETE_PRE_REGISTRATION", "missing_fields": missing}
    expected_id = deterministic_experiment_id(candidate)
    if experiment_id != expected_id:
        return {
            "ok": False,
            "reason_code": "EXPERIMENT_ID_PAYLOAD_MISMATCH",
            "expected_experiment_id": expected_id,
        }
    return {"ok": True, "reason_code": "REGISTERED", "registry_record_hash": canonical_json_hash(candidate)}


def validate_statistical_family_registration(
    candidate: dict[str, Any],
    *,
    contract: dict[str, Any],
    registry: list[dict[str, Any]],
    expected_regime_id: str | None = None,
    expected_development_episode_ids: list[str] | None = None,
    expected_lineage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """以 trusted contract 與 manager registry 驗證 matrix statistical authority。"""

    authority = statistical_family_contract(contract)
    if str(candidate.get("contract_hash") or "") != authority["contract_hash"]:
        return {"ok": False, "reason_code": "UNKNOWN_CONTRACT"}
    if str(candidate.get("parameter_space_hash") or "") != authority["parameter_space_hash"]:
        return {"ok": False, "reason_code": "PARAMETER_SPACE_HASH_MISMATCH"}
    global_combination_ids = [
        str(item)
        for item in candidate.get("global_combination_ids") or []
        if str(item)
    ]
    if global_combination_ids != authority["global_combination_ids"]:
        return {"ok": False, "reason_code": "GLOBAL_COMBINATION_IDS_MISMATCH"}
    if (
        str(candidate.get("global_combination_ids_hash") or "")
        != authority["global_combination_ids_hash"]
    ):
        return {"ok": False, "reason_code": "GLOBAL_COMBINATION_IDS_HASH_MISMATCH"}
    if (
        str(candidate.get("global_family_id") or "") != authority["global_family_id"]
        or int(candidate.get("global_family_size") or 0) != authority["global_family_size"]
    ):
        return {"ok": False, "reason_code": "GLOBAL_FAMILY_MISMATCH"}
    correction_ids = [
        str(item)
        for item in candidate.get("correction_family_combination_ids") or []
        if str(item)
    ]
    if (
        correction_ids != authority["global_combination_ids"]
        or str(candidate.get("correction_family_id") or "") != authority["global_family_id"]
        or int(candidate.get("correction_family_size") or 0) != authority["global_family_size"]
    ):
        return {"ok": False, "reason_code": "INVALID_CORRECTION_FAMILY"}
    tested_ids = [
        str(item)
        for item in candidate.get("tested_combination_ids") or []
        if str(item)
    ]
    if len(tested_ids) != len(candidate.get("tested_combination_ids") or []):
        return {"ok": False, "reason_code": "MISSING_TESTED_COMBINATION_IDS"}
    if str(candidate.get("tested_combination_ids_hash") or "") != canonical_json_hash(
        sorted(tested_ids)
    ):
        return {"ok": False, "reason_code": "TESTED_COMBINATION_HASH_MISMATCH"}
    partition_policy = candidate.get("partition_policy")
    if not isinstance(partition_policy, dict):
        return {"ok": False, "reason_code": "MISSING_PARTITION_POLICY"}
    if partition_policy.get("policy_id") != authority["partition_policy_id"]:
        return {"ok": False, "reason_code": "INVALID_PARTITION_POLICY"}
    partition = validate_statistical_partition(
        partition_id=str(partition_policy.get("partition_id") or ""),
        tested_combination_ids=tested_ids,
        authority=authority,
    )
    if not partition["ok"]:
        return partition
    if (
        partition_policy.get("correction_scope") != "global_parameter_universe"
        or partition_policy.get("parameter_space_hash") != authority["parameter_space_hash"]
        or int(partition_policy.get("tested_combination_count") or 0)
        != partition["tested_combination_count"]
        or partition_policy.get("tested_combination_ids_hash")
        != partition["tested_combination_ids_hash"]
        or partition_policy.get("correction_family_id") != authority["global_family_id"]
        or int(partition_policy.get("correction_family_size") or 0)
        != authority["global_family_size"]
    ):
        return {"ok": False, "reason_code": "PARTITION_POLICY_FAMILY_MISMATCH"}

    split_ids = {
        role: [str(item) for item in candidate.get(f"{role}_episode_ids") or [] if str(item)]
        for role in ("development", "validation", "embargo", "sealed")
    }
    required_lineage = {
        "regime_id",
        "dataset_hash",
        "split_id",
        "split_artifact_hash",
        "episode_split_ids_hash",
    }
    missing_lineage = sorted(field for field in required_lineage if not candidate.get(field))
    if missing_lineage or not split_ids["development"] or not split_ids["validation"] or not split_ids["sealed"]:
        return {
            "ok": False,
            "reason_code": "INCOMPLETE_STATISTICAL_LINEAGE",
            "missing_fields": missing_lineage,
        }
    all_episode_ids = [item for values in split_ids.values() for item in values]
    if (
        any(len(values) != len(set(values)) for values in split_ids.values())
        or len(all_episode_ids) != len(set(all_episode_ids))
    ):
        return {"ok": False, "reason_code": "EPISODE_SPLIT_ID_REUSE"}
    if candidate.get("episode_split_ids_hash") != canonical_json_hash(split_ids):
        return {"ok": False, "reason_code": "EPISODE_SPLIT_HASH_MISMATCH"}
    if expected_regime_id and candidate.get("regime_id") != expected_regime_id:
        return {"ok": False, "reason_code": "REGIME_IDENTITY_MISMATCH"}
    if expected_lineage is not None:
        scalar_lineage_reason_codes = {
            "dataset_hash": "DATASET_HASH_MISMATCH",
            "split_id": "SPLIT_ID_MISMATCH",
            "split_artifact_hash": "SPLIT_ARTIFACT_HASH_MISMATCH",
        }
        for field, reason_code in scalar_lineage_reason_codes.items():
            if candidate.get(field) != expected_lineage.get(field):
                return {"ok": False, "reason_code": reason_code}
        if candidate.get("sealed_trade_dates") != expected_lineage.get(
            "sealed_trade_dates"
        ):
            return {
                "ok": False,
                "reason_code": "SEALED_TRADE_DATES_MISMATCH",
            }
        sealed_hash_reason_codes = {
            "sealed_trade_date_hash": "SEALED_TRADE_DATE_HASH_MISMATCH",
            "sealed_dataset_slice_hash": "SEALED_DATASET_SLICE_HASH_MISMATCH",
        }
        for field, reason_code in sealed_hash_reason_codes.items():
            if candidate.get(field) != expected_lineage.get(field):
                return {"ok": False, "reason_code": reason_code}
        for role in ("development", "validation", "embargo", "sealed"):
            if split_ids[role] != list(
                expected_lineage.get(f"{role}_episode_ids") or []
            ):
                return {
                    "ok": False,
                    "reason_code": f"{role.upper()}_EPISODE_IDS_MISMATCH",
                }
        if candidate.get("episode_split_ids_hash") != expected_lineage.get(
            "episode_split_ids_hash"
        ):
            return {
                "ok": False,
                "reason_code": "EPISODE_SPLIT_IDS_HASH_MISMATCH",
            }
    if expected_development_episode_ids is not None and sorted(
        expected_development_episode_ids
    ) != sorted(split_ids["development"]):
        return {"ok": False, "reason_code": "DEVELOPMENT_EPISODE_IDS_MISMATCH"}

    artifact = {key: value for key, value in candidate.items() if key != "registry_record_hash"}
    artifact_hash = canonical_json_hash(artifact)
    supplied_record_hash = str(candidate.get("registry_record_hash") or "")
    matching_records = [
        (index, row)
        for index, row in enumerate(registry)
        if row.get("event_type") == "PRE_REGISTRATION"
        and row.get("experiment_id") == candidate.get("experiment_id")
    ]
    if len(matching_records) != 1:
        return {"ok": False, "reason_code": "REGISTRY_MEMBERSHIP_MISMATCH"}
    record_index, record = matching_records[0]
    record_payload = {
        key: value
        for key, value in record.items()
        if key not in {"event_type", "registry_record_hash"}
    }
    if (
        not supplied_record_hash
        or supplied_record_hash != artifact_hash
        or record.get("registry_record_hash") != artifact_hash
        or record_payload != artifact
    ):
        return {"ok": False, "reason_code": "REGISTRY_RECORD_HASH_MISMATCH"}
    registration_check = validate_experiment_registration(artifact, registry[:record_index])
    if not registration_check["ok"]:
        return {
            "ok": False,
            "reason_code": "INVALID_REGISTERED_EXPERIMENT",
            "registration_reason_code": registration_check["reason_code"],
        }
    return {
        "ok": True,
        "reason_code": "STATISTICAL_FAMILY_AUTHORITY_VALID",
        "authority": authority,
        "partition": partition,
        "registry_record_hash": artifact_hash,
    }


def append_experiment_registry(path: Path, candidate: dict[str, Any]) -> dict[str, Any]:
    registry: list[dict[str, Any]] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                registry.append(json.loads(line))
    result = validate_experiment_registration(candidate, registry)
    if not result["ok"]:
        return result
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        **candidate,
        "event_type": "PRE_REGISTRATION",
        "registry_record_hash": result["registry_record_hash"],
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
    return result


def transition_experiment_registry(
    path: Path,
    *,
    experiment_id: str,
    target_state: str,
    evidence_path: str,
) -> dict[str, Any]:
    if not path.exists():
        return {"ok": False, "reason_code": "EXPERIMENT_NOT_REGISTERED"}
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    own_events = [row for row in events if str(row.get("experiment_id") or "") == experiment_id]
    registration = next((row for row in own_events if row.get("event_type") == "PRE_REGISTRATION"), None)
    if registration is None:
        return {"ok": False, "reason_code": "EXPERIMENT_NOT_REGISTERED"}
    current_state = str(own_events[-1].get("target_state") or registration.get("state") or "REGISTERED")
    validation = validate_funnel_transition(current_state, target_state, evidence_path)
    if not validation["ok"]:
        return validation
    previous_hash = str(own_events[-1].get("event_hash") or own_events[-1].get("registry_record_hash") or "")
    event = {
        "event_type": "STATE_TRANSITION",
        "experiment_id": experiment_id,
        "from_state": current_state,
        "target_state": target_state,
        "evidence_path": evidence_path,
        "previous_event_hash": previous_hash,
    }
    event["event_hash"] = canonical_json_hash(event)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
    return {"ok": True, "reason_code": "TRANSITION_RECORDED", **event}


def validate_funnel_transition(current: str, target: str, evidence_path: str | None) -> dict[str, Any]:
    allowed = FUNNEL_TRANSITIONS.get(current, set())
    if target not in allowed:
        return {"ok": False, "reason_code": "ILLEGAL_STATE_TRANSITION", "allowed": sorted(allowed)}
    if not evidence_path:
        return {"ok": False, "reason_code": "MISSING_TRANSITION_EVIDENCE"}
    return {"ok": True, "reason_code": "TRANSITION_ALLOWED"}


def multiple_testing_gate(
    candidates: list[dict[str, Any]],
    *,
    expected_family: dict[str, Any] | None = None,
    familywise_alpha: float = 0.05,
    min_robust_neighbors: int = 2,
) -> dict[str, Any]:
    tested = len(candidates)
    if tested <= 0:
        return {
            "ok": False,
            "reason_code": "INSUFFICIENT_EVIDENCE",
            "evidence_complete": False,
            "eligible_ids": [],
        }
    required_fields = {
        "combination_id",
        "correction_family_id",
        "p_value",
        "robust_neighbor_lineage",
        "robust_neighbor_pass_count",
        "drawdown_within_limit",
        "statistical_unit_policy",
        "statistical_unit_ids",
        "statistical_unit_count",
        "pseudo_replication_detected",
    }
    missing_by_combination: dict[str, list[str]] = {}
    for index, row in enumerate(candidates):
        missing = sorted(
            field
            for field in required_fields
            if field not in row or (field in {"combination_id", "correction_family_id", "p_value"} and row.get(field) is None)
        )
        if missing:
            missing_by_combination[str(row.get("combination_id") or f"row:{index}")] = missing
    combination_ids = [str(row.get("combination_id") or "") for row in candidates]
    correction_family_ids = {str(row.get("correction_family_id") or "") for row in candidates}
    expected_ids = sorted(
        str(item)
        for item in (expected_family or {}).get("tested_combination_ids") or []
        if str(item)
    )
    expected_tested_hash = str((expected_family or {}).get("tested_combination_ids_hash") or "")
    correction_family_combination_ids = sorted(
        str(item)
        for item in (expected_family or {}).get("correction_family_combination_ids") or []
        if str(item)
    )
    expected_family_id = str((expected_family or {}).get("correction_family_id") or "")
    expected_family_size = int((expected_family or {}).get("correction_family_size") or 0)
    partition_policy = (expected_family or {}).get("partition_policy")
    family_validation_reason = "EXPECTED_FAMILY_VALID"
    if expected_family is None:
        family_validation_reason = "MISSING_EXPECTED_PRE_REGISTRATION_FAMILY"
    elif (expected_family or {}).get("registration_valid") is not True:
        family_validation_reason = str(
            (expected_family or {}).get("registration_validation_reason")
            or "INVALID_PRE_REGISTRATION"
        )
    elif sorted(combination_ids) != expected_ids:
        family_validation_reason = "TESTED_COMBINATION_FAMILY_MISMATCH"
    elif expected_tested_hash != canonical_json_hash(expected_ids):
        family_validation_reason = "TESTED_COMBINATION_HASH_MISMATCH"
    elif (
        not expected_family_id
        or expected_family_size != len(correction_family_combination_ids)
        or len(correction_family_combination_ids) != len(set(correction_family_combination_ids))
        or expected_family_id != canonical_json_hash(correction_family_combination_ids)
        or not set(expected_ids).issubset(set(correction_family_combination_ids))
    ):
        family_validation_reason = "INVALID_CORRECTION_FAMILY"
    elif not isinstance(partition_policy, dict):
        family_validation_reason = "MISSING_PARTITION_POLICY"
    elif (
        expected_family_size > len(expected_ids)
        and partition_policy.get("correction_scope") != "global_parameter_universe"
    ):
        family_validation_reason = "INVALID_PARTITION_CORRECTION_SCOPE"
    elif (
        partition_policy.get("tested_combination_ids_hash") != expected_tested_hash
        or partition_policy.get("correction_family_id") != expected_family_id
        or int(partition_policy.get("correction_family_size") or 0) != expected_family_size
    ):
        family_validation_reason = "PARTITION_POLICY_FAMILY_MISMATCH"
    lineage_invalid = any(
        not isinstance(row.get("robust_neighbor_lineage"), list)
        or int(row.get("robust_neighbor_pass_count") or 0) != len(row.get("robust_neighbor_lineage") or [])
        or not set(str(item) for item in row.get("robust_neighbor_lineage") or []).issubset(set(combination_ids))
        for row in candidates
    )
    statistical_unit_invalid = any(
        row.get("statistical_unit_policy") != "independent_regime_episode_cluster.v1"
        or not isinstance(row.get("statistical_unit_ids"), list)
        or int(row.get("statistical_unit_count") or 0) != len(row.get("statistical_unit_ids") or [])
        or int(row.get("statistical_unit_count") or 0) <= 0
        or len(row.get("statistical_unit_ids") or []) != len(set(row.get("statistical_unit_ids") or []))
        for row in candidates
    )
    minimum_statistical_unit_count = int(
        (expected_family or {}).get("minimum_statistical_unit_count") or 0
    )
    insufficient_units_by_combination = {
        str(row.get("combination_id") or f"row:{index}"): {
            "actual": int(row.get("statistical_unit_count") or 0),
            "required": minimum_statistical_unit_count,
            "gap": max(
                0,
                minimum_statistical_unit_count
                - int(row.get("statistical_unit_count") or 0),
            ),
        }
        for index, row in enumerate(candidates)
        if minimum_statistical_unit_count > 0
        and int(row.get("statistical_unit_count") or 0)
        < minimum_statistical_unit_count
    }
    pseudo_replication_detected = any(bool(row.get("pseudo_replication_detected")) for row in candidates)
    if (
        missing_by_combination
        or len(combination_ids) != len(set(combination_ids))
        or family_validation_reason != "EXPECTED_FAMILY_VALID"
        or len(correction_family_ids) != 1
        or "" in correction_family_ids
        or correction_family_ids != {expected_family_id}
        or lineage_invalid
        or statistical_unit_invalid
        or insufficient_units_by_combination
        or pseudo_replication_detected
    ):
        return {
            "ok": False,
            "reason_code": "INSUFFICIENT_EVIDENCE",
            "evidence_complete": False,
            "tested_count": tested,
            "eligible_ids": [],
            "missing_fields_by_combination": missing_by_combination,
            "family_validation_reason": family_validation_reason,
            "correction_family_size": expected_family_size,
            "corrected_alpha": (
                familywise_alpha / expected_family_size
                if expected_family_size > 0
                else None
            ),
            "minimum_statistical_unit_count": minimum_statistical_unit_count,
            "insufficient_units_by_combination": insufficient_units_by_combination,
            "pseudo_replication_detected": pseudo_replication_detected,
        }
    corrected_alpha = familywise_alpha / expected_family_size
    eligible = [
        str(row["combination_id"])
        for row in candidates
        if float(row["p_value"]) <= corrected_alpha
        and int(row.get("robust_neighbor_pass_count") or 0) >= min_robust_neighbors
        and bool(row.get("drawdown_within_limit"))
    ]
    return {
        "ok": bool(eligible),
        "reason_code": "ROBUST_CANDIDATE_AVAILABLE" if eligible else "MULTIPLE_TESTING_OR_ROBUSTNESS_FAILED",
        "evidence_complete": True,
        "tested_count": tested,
        "correction_family_size": expected_family_size,
        "corrected_alpha": corrected_alpha,
        "eligible_ids": sorted(eligible),
        "family_validation_reason": family_validation_reason,
        "pseudo_replication_detected": False,
    }


def research_round_decision(candidate_results: list[dict[str, Any]], *, sufficient_evidence: bool) -> str:
    if not sufficient_evidence:
        return "INSUFFICIENT_EVIDENCE"
    return "REGIME_POLICY_CANDIDATE" if any(bool(row.get("passed")) for row in candidate_results) else "NO_STRATEGY"


def coverage_summary(
    universe: dict[str, Any],
    regime_ids: list[str],
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    legal_count = int(universe.get("legal_combination_count") or 0)
    legal_ids = {str(item) for item in universe.get("legal_combination_ids") or []}
    allowed_statuses = {"PENDING", "REJECTED", "VALIDATING", "INSUFFICIENT_EVIDENCE", "PASSED", "BLOCKED"}
    by_regime: list[dict[str, Any]] = []
    for regime_id in sorted(set(regime_ids)):
        rows = [row for row in records if str(row.get("regime_id")) == regime_id]
        counts = {status: 0 for status in sorted(allowed_statuses)}
        seen: set[str] = set()
        for row in rows:
            combo_id = str(row.get("combination_id") or "")
            status = str(row.get("status") or "")
            if combo_id and combo_id in legal_ids and combo_id not in seen and status in allowed_statuses:
                counts[status] += 1
                seen.add(combo_id)
        processed = sum(counts[status] for status in counts if status != "PENDING")
        pending = max(0, legal_count - len(seen)) + counts["PENDING"]
        by_regime.append(
            {
                "regime_id": regime_id,
                "legal_combination_count": legal_count,
                "processed_count": processed,
                "pending_count": pending,
                "status_counts": counts,
                "coverage_closed": pending == 0,
            }
        )
    payload = {"parameter_space_hash": universe.get("parameter_space_hash"), "regimes": by_regime}
    return {**payload, "coverage_hash": canonical_json_hash(payload)}


def required_universal_regime_policy(contract: dict[str, Any]) -> dict[str, Any]:
    """由 contract taxonomy 推導 universal gate 的完整 exact identity 集合。"""

    taxonomy = contract.get("taxonomy") if isinstance(contract.get("taxonomy"), dict) else {}
    configured = {
        str(item)
        for item in taxonomy.get("required_universal_regime_ids") or []
        if str(item)
    }
    policy = str(taxonomy.get("universal_identity_policy") or "")
    if taxonomy.get("identity_rule") != "exact_base_and_exact_family_tag_set":
        return {"ok": False, "reason_code": "MISSING_REQUIRED_REGIME_POLICY", "required_regime_ids": []}
    if policy == "full_cartesian_product":
        bases = sorted(
            str(item)
            for item in taxonomy.get("base_regimes") or []
            if str(item) and str(item) != "UNKNOWN"
        )
        tags = sorted(str(item) for item in taxonomy.get("family_tags") or [] if str(item))
        derived = {
            regime_identity_id({"base_regime": base, "family_tags": list(tag_subset)})
            for base in bases
            for size in range(len(tags) + 1)
            for tag_subset in itertools.combinations(tags, size)
        }
    elif policy == "explicit_legal_identity_set":
        rules = taxonomy.get("legal_identity_rules")
        legal = taxonomy.get("legal_universal_regime_ids")
        if not rules or not isinstance(legal, list):
            return {"ok": False, "reason_code": "MISSING_REQUIRED_REGIME_POLICY", "required_regime_ids": []}
        derived = {str(item) for item in legal if str(item)}
    else:
        return {"ok": False, "reason_code": "MISSING_REQUIRED_REGIME_POLICY", "required_regime_ids": []}
    if not derived or configured != derived:
        return {
            "ok": False,
            "reason_code": "REQUIRED_REGIME_POLICY_MISMATCH",
            "required_regime_ids": sorted(derived),
            "missing_regime_ids": sorted(derived - configured),
            "unexpected_regime_ids": sorted(configured - derived),
        }
    return {
        "ok": True,
        "reason_code": "REQUIRED_REGIME_POLICY_VALID",
        "required_regime_ids": sorted(derived),
    }


def validate_universal_candidate(
    candidate: dict[str, Any],
    *,
    contract: dict[str, Any],
) -> dict[str, Any]:
    universe = contract.get("parameter_universe") if isinstance(contract.get("parameter_universe"), dict) else {}
    if (
        universe.get("declared_complete") is not True
        or str(universe.get("inventory_status") or "") != "COMPLETE"
        or bool(universe.get("blocked_dimensions"))
    ):
        return {"unlocked": False, "reason_code": "PARAMETER_UNIVERSE_INCOMPLETE"}
    required_policy = required_universal_regime_policy(contract)
    if not required_policy["ok"]:
        return {
            "unlocked": False,
            "reason_code": required_policy["reason_code"],
            "missing_regime_ids": required_policy.get("missing_regime_ids", []),
            "unexpected_regime_ids": required_policy.get("unexpected_regime_ids", []),
        }
    required_fields = {
        "coverage_closed",
        "high_value_regions_remaining",
        "fixed_parameter_hash",
        "fresh_sealed_oos_per_regime",
        "coverage_regime_ids",
        "regime_results",
    }
    missing_fields = sorted(field for field in required_fields if field not in candidate)
    if missing_fields:
        return {
            "unlocked": False,
            "reason_code": "MISSING_UNIVERSAL_FIELDS",
            "missing_fields": missing_fields,
        }
    if not bool(candidate["coverage_closed"]):
        return {"unlocked": False, "reason_code": "COVERAGE_NOT_CLOSED"}
    if int(candidate["high_value_regions_remaining"] or 0) > 0:
        return {"unlocked": False, "reason_code": "HIGH_VALUE_RESEARCH_REMAINS"}
    if not candidate.get("fixed_parameter_hash"):
        return {"unlocked": False, "reason_code": "PARAMETERS_NOT_FROZEN"}
    required_regimes = set(required_policy["required_regime_ids"])
    candidate_required = {str(item) for item in candidate.get("required_regime_ids") or [] if str(item)}
    if candidate_required and candidate_required != required_regimes:
        return {
            "unlocked": False,
            "reason_code": "REQUIRED_REGIME_POLICY_MISMATCH",
            "missing_regime_ids": sorted(required_regimes - candidate_required),
            "unexpected_regime_ids": sorted(candidate_required - required_regimes),
        }
    coverage_regimes = {str(item) for item in candidate["coverage_regime_ids"] or [] if str(item)}
    researched_outside_policy = sorted(coverage_regimes - required_regimes)
    if researched_outside_policy:
        return {
            "unlocked": False,
            "reason_code": "REQUIRED_REGIME_POLICY_MISMATCH",
            "unexpected_regime_ids": researched_outside_policy,
        }
    missing_coverage = sorted(required_regimes - coverage_regimes)
    if missing_coverage:
        return {
            "unlocked": False,
            "reason_code": "MISSING_REQUIRED_REGIMES",
            "missing_regime_ids": missing_coverage,
        }
    results = candidate.get("regime_results") if isinstance(candidate.get("regime_results"), list) else []
    if not results:
        return {"unlocked": False, "reason_code": "MISSING_REGIME_RESULTS"}
    result_ids = [str(row.get("regime_id") or "") for row in results if row.get("regime_id")]
    if len(result_ids) != len(set(result_ids)):
        return {"unlocked": False, "reason_code": "DUPLICATE_REGIME_RESULTS"}
    result_by_regime = {str(row.get("regime_id") or ""): row for row in results if row.get("regime_id")}
    missing_results = sorted(required_regimes - set(result_by_regime))
    if missing_results:
        return {
            "unlocked": False,
            "reason_code": "MISSING_REQUIRED_REGIMES",
            "missing_regime_ids": missing_results,
        }
    if not bool(candidate["fresh_sealed_oos_per_regime"]):
        return {"unlocked": False, "reason_code": "SEALED_OOS_NOT_INDEPENDENT"}
    fixed_parameter_hash = str(candidate["fixed_parameter_hash"])
    sealed_lineages: set[str] = set()
    for regime_id in sorted(required_regimes):
        row = result_by_regime[regime_id]
        if not bool(row.get("sufficient_evidence")):
            return {"unlocked": False, "reason_code": "INSUFFICIENT_REQUIRED_REGIME", "regime_id": regime_id}
        if not bool(row.get("passed")):
            return {"unlocked": False, "reason_code": "WORST_REGIME_FAILED", "regime_id": regime_id}
        if str(row.get("parameter_hash") or "") != fixed_parameter_hash:
            return {"unlocked": False, "reason_code": "FIXED_PARAMETER_HASH_MISMATCH", "regime_id": regime_id}
        sealed_hash = str(row.get("sealed_dataset_slice_hash") or "")
        if not sealed_hash:
            return {"unlocked": False, "reason_code": "MISSING_SEALED_LINEAGE", "regime_id": regime_id}
        if sealed_hash in sealed_lineages:
            return {"unlocked": False, "reason_code": "DUPLICATE_SEALED_LINEAGE", "regime_id": regime_id}
        sealed_lineages.add(sealed_hash)
        if row.get("independent_emergence") is not True:
            return {"unlocked": False, "reason_code": "INDEPENDENT_EMERGENCE_MISSING", "regime_id": regime_id}
        if row.get("transition_forward_shadow_passed") is not True:
            return {"unlocked": False, "reason_code": "TRANSITION_FORWARD_SHADOW_MISSING", "regime_id": regime_id}
    return {"unlocked": True, "reason_code": "UNIVERSAL_CANDIDATE_UNLOCKED"}


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def write_run_artifacts(payload: dict[str, Any], output: Path) -> None:
    write_text_atomic(output, json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False))
    write_text_atomic(output.with_suffix(".md"), render_markdown(payload))


def repo_owned_ranking_date_inventory(path_value: str | Path) -> dict[str, Any]:
    """從 repo 內 ranking 檔名建立可重算的日期 inventory。"""

    path = resolve_path(path_value)
    if path is None:
        return {"ok": False, "reason_code": "MISSING_RANKING_INVENTORY"}
    resolved = path.resolve()
    try:
        resolved.relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        return {"ok": False, "reason_code": "RANKING_INVENTORY_PATH_ESCAPE"}
    if not resolved.is_dir():
        return {"ok": False, "reason_code": "MISSING_RANKING_INVENTORY"}
    files = sorted(resolved.glob("ranking_*.csv"))
    if not files:
        return {"ok": False, "reason_code": "MISSING_RANKING_INVENTORY"}
    ranking_dates: list[str] = []
    for path in files:
        if path.is_symlink() or not path.is_file():
            return {"ok": False, "reason_code": "RANKING_INVENTORY_PATH_ESCAPE"}
        try:
            resolved_entry = path.resolve(strict=True)
            resolved_entry.relative_to(PROJECT_ROOT.resolve())
        except (OSError, RuntimeError, ValueError):
            return {"ok": False, "reason_code": "RANKING_INVENTORY_PATH_ESCAPE"}
        match = RANKING_FILE_NAME_PATTERN.fullmatch(path.name)
        if match is None:
            return {"ok": False, "reason_code": "MALFORMED_RANKING_DATE"}
        value = match.group(1)
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            return {"ok": False, "reason_code": "MALFORMED_RANKING_DATE"}
        if parsed.isoformat() != value:
            return {"ok": False, "reason_code": "MALFORMED_RANKING_DATE"}
        ranking_dates.append(value)
    return {"ok": True, "reason_code": "RANKING_INVENTORY_VALID", "ranking_dates": sorted(set(ranking_dates))}


def canonical_exact_regime_allowed_dates(
    *,
    rows: list[dict[str, Any]],
    contract: dict[str, Any],
    regime_identity: dict[str, Any],
    horizons: str,
    as_of_date: str,
) -> set[str]:
    """以 matrix 共用的 episode split authority 重建可執行 development dates。"""

    run_date = date.fromisoformat(as_of_date)
    lineage = statistical_lineage_authority(
        rows=rows,
        contract=contract,
        regime_id=regime_identity_id(regime_identity),
        horizons=parse_positive_ints(horizons),
    )
    development = lineage["split_artifact"].get("development")
    if not isinstance(development, list):
        raise ValueError("canonical development episode authority 缺失")
    allowed_dates = {
        str(trade_date)
        for episode in development
        if isinstance(episode, dict)
        for trade_date in episode.get("trade_dates", [])
        if date.fromisoformat(str(trade_date)) <= run_date
    }
    if not allowed_dates:
        raise ValueError("canonical exact-regime allowed dates 不可為空")
    return allowed_dates


def exact_regime_topic_ranking_eligibility(
    *,
    candidate_dir: str,
    baseline_dir: str,
    allowed_dates: set[str] | None,
    as_of_date: str,
) -> dict[str, Any]:
    """要求 candidate 與 baseline 都有 canonical exact-regime ranking date。"""

    try:
        run_date = date.fromisoformat(as_of_date)
        canonical_allowed = {
            value
            for value in (allowed_dates or set())
            if date.fromisoformat(value) <= run_date
        }
    except (TypeError, ValueError):
        canonical_allowed = set()
    if not canonical_allowed:
        return {"eligible": False, "reason_code": "MISSING_EXACT_REGIME_AUTHORITY"}
    result: dict[str, Any] = {
        "eligible": True,
        "reason_code": "ELIGIBLE",
        "exact_regime_allowed_date_count": len(canonical_allowed),
    }
    for role, path_value in (("candidate", candidate_dir), ("baseline", baseline_dir)):
        inventory = repo_owned_ranking_date_inventory(path_value)
        if not inventory["ok"]:
            return {
                **result,
                "eligible": False,
                "reason_code": inventory["reason_code"],
                "inventory_role": role,
            }
        ranking_dates = set(inventory["ranking_dates"])
        result[f"{role}_ranking_date_count"] = len(ranking_dates)
        result[f"{role}_exact_date_count"] = len(ranking_dates & canonical_allowed)
        if ranking_dates and all(date.fromisoformat(value) > run_date for value in ranking_dates):
            return {
                **result,
                "eligible": False,
                "reason_code": "FUTURE_ONLY_RANKING_DATE",
                "inventory_role": role,
            }
        if not ranking_dates & canonical_allowed:
            return {
                **result,
                "eligible": False,
                "reason_code": "NO_EXACT_REGIME_RANKING_DATE",
                "inventory_role": role,
            }
    return result


def ranking_dirs(min_ranking_files: int) -> list[dict[str, Any]]:
    roots = [ARTIFACTS_DIR / "backtest", ARTIFACTS_DIR / "research_rankings"]
    by_dir: dict[Path, int] = {}
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("ranking_*.csv"):
            by_dir[path.parent] = by_dir.get(path.parent, 0) + 1
    rows = []
    for path, count in by_dir.items():
        if count < min_ranking_files:
            continue
        rows.append({"path": path, "repo_path": repo_path(path), "count": count, "mtime": path.stat().st_mtime})
    return sorted(rows, key=lambda item: (-int(item["count"]), str(item["repo_path"])))


def latest_external_review_summary() -> tuple[dict[str, Any], str | None]:
    root = ARTIFACTS_DIR / "external_review"
    if not root.exists():
        return {}, None
    matches = sorted(root.rglob("external_review_summary_*.json"))
    if not matches:
        return {}, None
    path = matches[-1]
    return load_json(path), repo_path(path)


def ledger_signals() -> tuple[list[str], list[str]]:
    ledger = load_json(LEDGER_PATH)
    candidates = []
    sources = []
    if ledger:
        sources.append(repo_path(LEDGER_PATH) or str(LEDGER_PATH))
    for entry in ledger.get("experiments", []):
        status = str(entry.get("status") or "")
        if status not in {"pending", "partial", "failed"}:
            continue
        candidate = str(entry.get("candidate") or "").strip()
        if candidate:
            candidates.append(candidate.lower())
    return sorted(set(candidates)), sources


def external_review_signals() -> tuple[list[str], list[str]]:
    summary, source = latest_external_review_summary()
    signals = []
    sources = [source] if source else []
    for item in summary.get("research_hypotheses", []):
        if not isinstance(item, dict):
            continue
        family = str(item.get("candidate_signal_family") or "").strip().lower()
        priority = str(item.get("priority") or "").strip().lower()
        if family:
            signals.append(family)
        if priority == "high":
            signals.append("high_priority_external_review")
    return sorted(set(signals)), [item for item in sources if item]


def is_baseline_like(path_text: str) -> bool:
    lowered = path_text.lower()
    return "historical_rankings_current_model" in lowered or "/current_model" in lowered


def keyword_score(path_text: str) -> tuple[float, list[str]]:
    lowered = path_text.lower()
    score = 0.0
    reasons: list[str] = []
    weights = [
        ("odd_lot", 35, "odd-lot capital realism line"),
        ("candidate", 22, "candidate ranking artifact"),
        ("big_bull", 20, "big bull regime hypothesis"),
        ("liquidity", 18, "liquidity quality hypothesis"),
        ("regime", 16, "regime conditional hypothesis"),
        ("guard", 12, "risk guard variant"),
        ("daily_recommendation", 12, "daily recommendation quality line"),
        ("sector", 10, "sector/theme context"),
        ("feature_group", 8, "feature group shadow ranking"),
        ("smoke", -25, "smoke artifact is lower priority"),
    ]
    for key, weight, reason in weights:
        if key in lowered:
            score += weight
            reasons.append(reason)
    return score, reasons


def signal_bonus(path_text: str, ledger_candidates: list[str], external_signals: list[str]) -> tuple[float, list[str]]:
    lowered = path_text.lower()
    score = 0.0
    reasons: list[str] = []
    for candidate in ledger_candidates:
        normalized = candidate.replace("-", "_")
        if normalized and normalized in lowered:
            score += 14
            reasons.append(f"ledger pending/partial signal matched: {candidate}")
    signal_map = {
        "risk_control": ["guard", "stop", "exit", "trail"],
        "liquidity": ["liquidity"],
        "timing": ["setup", "daily_recommendation", "entry"],
        "theme_momentum": ["sector", "industry", "regime", "big_bull"],
        "relative_strength": ["feature_group", "candidate", "rank"],
    }
    for signal in external_signals:
        for keyword in signal_map.get(signal, []):
            if keyword in lowered:
                score += 8
                reasons.append(f"external review signal matched: {signal}")
                break
        if signal == "high_priority_external_review":
            score += 4
            reasons.append("external review has high-priority hypothesis")
    return score, reasons


def topic_for_dir(
    row: dict[str, Any],
    *,
    baseline_dir: str,
    ledger_candidates: list[str],
    external_signals: list[str],
    evidence_sources: list[str],
    profile: dict[str, Any] | None = None,
    current_regime: dict[str, Any] | None = None,
    coverage: dict[str, Any] | None = None,
    enforce_exact_regime_ranking_dates: bool = False,
    exact_regime_allowed_dates: set[str] | None = None,
    exact_regime_as_of_date: str | None = None,
) -> ResearchTopic | None:
    profile = profile or VALIDATION_PROFILES[0]
    candidate_dir = str(row["repo_path"])
    if not candidate_dir or is_baseline_like(candidate_dir):
        return None
    key_score, key_reasons = keyword_score(candidate_dir)
    sig_score, sig_reasons = signal_bonus(candidate_dir, ledger_candidates, external_signals)
    count = int(row["count"])
    sample_score = min(count, 60) / 3
    score = round(10 + sample_score + key_score + sig_score + float(profile.get("score_bonus") or 0), 3)
    label = candidate_dir
    profile_name = str(profile.get("name") or "standard")
    base_topic_id = f"strategy-matrix:{slugify(candidate_dir)}"
    topic_id = base_topic_id if profile_name == "standard" else f"{base_topic_id}:{slugify(profile_name)}"
    regime_identity = canonical_regime_identity(current_regime) if current_regime else None
    coverage = coverage or {"evidence_gap": 1.0, "pending_count": None, "legal_combination_count": None}
    profile_values = [
        [item for item in str(profile.get(key) or "").split(",") if item.strip()]
        for key in ("horizons", "stop_loss_pcts", "take_profit_pcts", "max_group_exposures")
    ]
    estimated_resolved = 1
    for values in profile_values:
        estimated_resolved *= max(1, len(values))
    priority = (
        score_regime_research_topic(
            {"regime_identity": regime_identity},
            current_regime=regime_identity,
            coverage=coverage,
            information_gain=max(
                0.000001,
                min(
                    1.0,
                    estimated_resolved / max(1, int(coverage.get("legal_combination_count") or estimated_resolved)),
                ),
            ),
            product_value=1.0,
            feasibility=1.0,
            estimated_compute_cost=max(1.0, count / 8),
        )
        if regime_identity
        else None
    )
    ranking_eligibility = (
        exact_regime_topic_ranking_eligibility(
            candidate_dir=candidate_dir,
            baseline_dir=baseline_dir,
            allowed_dates=exact_regime_allowed_dates,
            as_of_date=str(exact_regime_as_of_date or ""),
        )
        if enforce_exact_regime_ranking_dates
        else None
    )
    eligible = bool(priority["eligible"]) if priority else True
    reason_code = str(priority["reason_code"]) if priority else "LEGACY_TOPIC"
    if ranking_eligibility is not None and not ranking_eligibility["eligible"]:
        eligible = False
        reason_code = str(ranking_eligibility["reason_code"])
    return ResearchTopic(
        topic_id=topic_id,
        title=f"回測 ranking variant：{Path(candidate_dir).name}｜{profile.get('title_suffix')}",
        hypothesis=f"{label} 相對 current baseline，在 {profile.get('title_suffix')} 下可提升 best_score，且 max drawdown 不惡化。{profile.get('hypothesis_suffix')}",
        validation_plan="同時跑 current baseline 與 candidate 的 strategy matrix，再用 compare_strategy_matrices 比較 best_score、return、drawdown。",
        runner="strategy_matrix_comparison",
        candidate_dir=candidate_dir,
        baseline_dir=baseline_dir,
        score=float(priority["priority"]) if priority else score,
        reasons=key_reasons + sig_reasons + [f"ranking files: {count}"],
        evidence_sources=evidence_sources + [candidate_dir],
        ranking_file_count=count,
        validation_profile=profile_name,
        horizons=str(profile.get("horizons") or ""),
        stop_loss_pcts=str(profile.get("stop_loss_pcts") or ""),
        take_profit_pcts=str(profile.get("take_profit_pcts") or ""),
        max_group_exposures=str(profile.get("max_group_exposures") or ""),
        regime_identity=regime_identity,
        score_breakdown=priority.get("score_breakdown") if priority else None,
        eligible=eligible,
        reason_code=reason_code,
        selection_rationale=(
            {
                "why_now": f"current exact-match regime is {regime_identity_id(regime_identity)}",
                "coverage_gap": float(coverage.get("evidence_gap") or 0.0),
                "pending_combination_count": coverage.get("pending_count"),
                "estimated_combinations_resolved_on_success_or_failure": estimated_resolved,
                "selection_is_deterministic": True,
                **({"ranking_eligibility": ranking_eligibility} if ranking_eligibility is not None else {}),
            }
            if regime_identity
            else None
        ),
    )


def generate_all_topics(args: argparse.Namespace) -> list[ResearchTopic]:
    ledger_candidates, ledger_sources = ledger_signals()
    external_signals, external_sources = external_review_signals()
    evidence_sources = ledger_sources + external_sources
    current_regime = None
    current_coverage = None
    exact_dates_by_profile: dict[str, set[str] | None] = {}
    if bool(getattr(args, "closed_regime_research", False)):
        history_path = resolve_path(getattr(args, "market_regime_history", None))
        if history_path is None:
            raise ValueError("--closed-regime-research 必須提供 --market-regime-history")
        current_regime = current_regime_context(history_path, str(args.date))["identity"]
        contract_path = resolve_path(getattr(args, "research_contract", None))
        if contract_path is None:
            raise ValueError("closed regime research 缺少 parameter universe contract")
        contract = load_json(contract_path)
        universe = parameter_universe_summary(contract)
        coverage_path = resolve_path(getattr(args, "coverage_map", None))
        coverage_payload = load_json(coverage_path)
        records = coverage_payload.get("records") if isinstance(coverage_payload.get("records"), list) else []
        summary = coverage_summary(universe, [regime_identity_id(current_regime)], records)["regimes"][0]
        current_coverage = {
            "evidence_gap": summary["pending_count"] / max(1, summary["legal_combination_count"]),
            "pending_count": summary["pending_count"],
            "legal_combination_count": summary["legal_combination_count"],
        }
        history_payload = load_json(history_path)
        history_rows = history_payload.get("rows") if isinstance(history_payload.get("rows"), list) else []
        for profile in VALIDATION_PROFILES:
            profile_name = str(profile.get("name") or "standard")
            try:
                exact_dates_by_profile[profile_name] = canonical_exact_regime_allowed_dates(
                    rows=history_rows,
                    contract=contract,
                    regime_identity=current_regime,
                    horizons=str(profile.get("horizons") or ""),
                    as_of_date=str(args.date),
                )
            except (KeyError, TypeError, ValueError):
                exact_dates_by_profile[profile_name] = None
    if args.candidate_dir:
        path = resolve_path(args.candidate_dir)
        count = len(list(path.glob("ranking_*.csv"))) if path else 0
        row = {"repo_path": repo_path(path), "count": count, "mtime": path.stat().st_mtime if path and path.exists() else 0}
        topics = [
            topic_for_dir(
                row,
                baseline_dir=args.baseline_dir,
                ledger_candidates=ledger_candidates,
                external_signals=external_signals,
                evidence_sources=evidence_sources,
                profile=profile,
                current_regime=current_regime,
                coverage=current_coverage,
                enforce_exact_regime_ranking_dates=current_regime is not None,
                exact_regime_allowed_dates=exact_dates_by_profile.get(str(profile.get("name") or "standard")),
                exact_regime_as_of_date=str(args.date),
            )
            for profile in VALIDATION_PROFILES
        ]
        return [topic for topic in topics if topic]
    topics = []
    for row in ranking_dirs(args.min_ranking_files):
        for profile in VALIDATION_PROFILES:
            topic = topic_for_dir(
                row,
                baseline_dir=args.baseline_dir,
                ledger_candidates=ledger_candidates,
                external_signals=external_signals,
                evidence_sources=evidence_sources,
                profile=profile,
                current_regime=current_regime,
                coverage=current_coverage,
                enforce_exact_regime_ranking_dates=current_regime is not None,
                exact_regime_allowed_dates=exact_dates_by_profile.get(str(profile.get("name") or "standard")),
                exact_regime_as_of_date=str(args.date),
            )
            if topic is not None:
                topics.append(topic)
    return sorted(topics, key=lambda item: (-item.score, item.topic_id))


def generate_topics(args: argparse.Namespace) -> list[ResearchTopic]:
    return [topic for topic in generate_all_topics(args) if topic.eligible][: args.max_topics]


def matrix_command(
    args: argparse.Namespace,
    rankings_dir: str,
    output: str,
    topic: ResearchTopic | None = None,
    *,
    allowed_episode_ids: list[str] | None = None,
    pre_registration_path: Path | None = None,
    experiment_registry_path: Path | None = None,
) -> list[str]:
    command = [
        sys.executable,
        "scripts/run_backtest_strategy_matrix.py",
        "--rankings-dir",
        rankings_dir,
        "--features",
        args.features,
        "--max-ranking-files",
        str(args.max_ranking_files),
        "--horizons",
        topic.horizons if topic and topic.horizons else args.horizons,
        "--stop-loss-pcts",
        topic.stop_loss_pcts if topic and topic.stop_loss_pcts else args.stop_loss_pcts,
        "--take-profit-pcts",
        topic.take_profit_pcts if topic and topic.take_profit_pcts else args.take_profit_pcts,
        "--max-group-exposures",
        topic.max_group_exposures if topic and topic.max_group_exposures else args.max_group_exposures,
        "--output",
        output,
    ]
    if bool(getattr(args, "closed_regime_research", False)):
        if topic is None or topic.regime_identity is None or not getattr(args, "market_regime_history", None):
            raise ValueError("closed regime matrix 缺少 regime identity/history")
        if not allowed_episode_ids:
            raise ValueError("closed regime matrix 缺少 immutable development episode IDs")
        if pre_registration_path is None:
            raise ValueError("closed regime matrix 缺少 immutable pre-registration")
        if experiment_registry_path is None:
            raise ValueError("closed regime matrix 缺少 manager experiment registry")
        command.extend(
            [
                "--require-exact-regime",
                "--market-regime-history",
                str(args.market_regime_history),
                "--base-regime",
                str(topic.regime_identity["base_regime"]),
                "--family-tags",
                ",".join(topic.regime_identity["family_tags"]),
                "--allowed-episode-ids",
                ",".join(allowed_episode_ids),
                "--pre-registration",
                repo_path(pre_registration_path) or str(pre_registration_path),
                "--experiment-registry",
                repo_path(experiment_registry_path) or str(experiment_registry_path),
            ]
        )
    return command


def compare_command(baseline_output: str, candidate_output: str, comparison_output: str) -> list[str]:
    return [
        sys.executable,
        "scripts/compare_strategy_matrices.py",
        "--variant",
        f"baseline={baseline_output}",
        "--variant",
        f"candidate={candidate_output}",
        "--output",
        comparison_output,
    ]


def command_allowed(command: list[str]) -> bool:
    if len(command) < 2:
        return False
    script = command[1]
    return script in ALLOWED_RUNNERS


def run_step(name: str, command: list[str]) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    if not command_allowed(command):
        ended = datetime.now(timezone.utc)
        return {
            "name": name,
            "status": "BLOCKED",
            "returncode": None,
            "started_at": started.isoformat(),
            "ended_at": ended.isoformat(),
            "command": command,
            "stdout_tail": "",
            "stderr_tail": "runner is not allowlisted",
        }
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    ended = datetime.now(timezone.utc)
    return {
        "name": name,
        "status": "OK" if completed.returncode == 0 else "FAILED",
        "returncode": completed.returncode,
        "started_at": started.isoformat(),
        "ended_at": ended.isoformat(),
        "command": command,
        "stdout_tail": completed.stdout[-3000:],
        "stderr_tail": completed.stderr[-3000:],
    }


def selected_topic(topics: list[ResearchTopic], index: int) -> ResearchTopic | None:
    if not topics or index < 0 or index >= len(topics):
        return None
    return topics[index]


def load_topic_registry() -> dict[str, dict[str, Any]]:
    path = manager_paths()["registry"]
    return {row.get("topic_id"): row for row in load_list_payload(path, "topics") if row.get("topic_id")}


def load_next_action_queue() -> list[dict[str, Any]]:
    return load_list_payload(manager_paths()["queue"], "actions")


def queued_topic_ids() -> set[str]:
    return {str(item.get("topic_id")) for item in load_next_action_queue() if item.get("topic_id")}


def parse_utc_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def load_last_run_at_by_topic() -> dict[str, str]:
    latest: dict[str, tuple[datetime, str]] = {}
    for row in load_list_payload(manager_paths()["history"], "runs"):
        if row.get("execute") is not True:
            continue
        raw_time = str(row.get("generated_at") or "")
        run_at = parse_utc_timestamp(raw_time)
        if run_at is None:
            continue
        topic_ids = row.get("selected_topic_ids") or []
        if not topic_ids and row.get("selected_topic_id"):
            topic_ids = [row.get("selected_topic_id")]
        for topic_id in topic_ids:
            key = str(topic_id or "")
            if key and (key not in latest or run_at > latest[key][0]):
                latest[key] = (run_at, raw_time)
    return {topic_id: value for topic_id, (_, value) in latest.items()}


def topic_allowed_by_manager(
    topic: ResearchTopic,
    registry: dict[str, dict[str, Any]],
    args: argparse.Namespace,
    *,
    last_run_at_by_topic: dict[str, str] | None = None,
    now: datetime | None = None,
) -> bool:
    if not topic.eligible:
        return False
    current = registry.get(topic.topic_id, {})
    status = str(current.get("manager_status") or "candidate")
    run_count = int(current.get("run_count") or 0)
    if run_count == 0:
        return status in {"candidate", "confirmed_for_next_replay", "partial_needs_followup", "blocked_missing_evidence"}
    policy = CONTROLLED_RERUN_POLICIES.get(status)
    if policy is None or run_count >= policy["max_run_count"]:
        return False
    last_run_at = parse_utc_timestamp(current.get("last_run_at"))
    if last_run_at is None and last_run_at_by_topic is not None:
        last_run_at = parse_utc_timestamp(last_run_at_by_topic.get(topic.topic_id))
    if last_run_at is None:
        return False
    current_time = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return current_time - last_run_at >= timedelta(hours=policy["cooldown_hours"])


def select_topics_for_run(topics: list[ResearchTopic], args: argparse.Namespace) -> list[ResearchTopic]:
    topics = [topic for topic in topics if topic.eligible]
    if not topics:
        return []
    count = max(1, int(args.execute_topic_count or 1))
    registry = load_topic_registry()
    last_run_at_by_topic = load_last_run_at_by_topic()
    if args.from_queue:
        by_topic_id = {topic.topic_id: topic for topic in topics}
        selected: list[ResearchTopic] = []
        seen: set[str] = set()
        for action in load_next_action_queue():
            topic_id = str(action.get("topic_id") or "")
            if not topic_id or topic_id in seen:
                continue
            topic = by_topic_id.get(topic_id)
            if topic is None:
                continue
            if not topic_allowed_by_manager(topic, registry, args, last_run_at_by_topic=last_run_at_by_topic):
                continue
            selected.append(topic)
            seen.add(topic_id)
            if len(selected) >= count:
                break
        return selected
    if count > 1:
        selected = [
            topic
            for topic in topics
            if topic_allowed_by_manager(topic, registry, args, last_run_at_by_topic=last_run_at_by_topic)
        ]
        return selected[:count]
    topic = selected_topic(topics, args.topic_index)
    if topic is None:
        return []
    if args.execute and not topic_allowed_by_manager(topic, registry, args, last_run_at_by_topic=last_run_at_by_topic):
        fallback = [
            item
            for item in topics
            if topic_allowed_by_manager(item, registry, args, last_run_at_by_topic=last_run_at_by_topic)
        ]
        return fallback[:1]
    return [topic]


def topic_to_json(topic: ResearchTopic) -> dict[str, Any]:
    return {
        "topic_id": topic.topic_id,
        "title": topic.title,
        "hypothesis": topic.hypothesis,
        "validation_plan": topic.validation_plan,
        "runner": topic.runner,
        "candidate_dir": topic.candidate_dir,
        "baseline_dir": topic.baseline_dir,
        "score": topic.score,
        "reasons": topic.reasons,
        "evidence_sources": topic.evidence_sources,
        "ranking_file_count": topic.ranking_file_count,
        "status": topic.status,
        "validation_profile": topic.validation_profile,
        "horizons": topic.horizons,
        "stop_loss_pcts": topic.stop_loss_pcts,
        "take_profit_pcts": topic.take_profit_pcts,
        "max_group_exposures": topic.max_group_exposures,
        "regime_identity": topic.regime_identity,
        "score_breakdown": topic.score_breakdown,
        "eligible": topic.eligible,
        "reason_code": topic.reason_code,
        "selection_rationale": topic.selection_rationale,
    }


def topic_from_json(row: dict[str, Any]) -> ResearchTopic | None:
    topic_id = str(row.get("topic_id") or "")
    if not topic_id:
        return None
    return ResearchTopic(
        topic_id=topic_id,
        title=str(row.get("title") or topic_id),
        hypothesis=str(row.get("hypothesis") or ""),
        validation_plan=str(row.get("validation_plan") or ""),
        runner=str(row.get("runner") or "strategy_matrix_comparison"),
        candidate_dir=str(row.get("candidate_dir") or ""),
        baseline_dir=str(row.get("baseline_dir") or BASELINE_RANKINGS_DIR),
        score=float(row.get("score") or 0),
        reasons=[str(item) for item in row.get("reasons", []) if item],
        evidence_sources=[str(item) for item in row.get("evidence_sources", []) if item],
        ranking_file_count=int(row.get("ranking_file_count") or 0),
        status=str(row.get("status") or "candidate"),
        validation_profile=str(row.get("validation_profile") or "standard"),
        horizons=str(row.get("horizons") or ""),
        stop_loss_pcts=str(row.get("stop_loss_pcts") or ""),
        take_profit_pcts=str(row.get("take_profit_pcts") or ""),
        max_group_exposures=str(row.get("max_group_exposures") or ""),
        regime_identity=row.get("regime_identity") if isinstance(row.get("regime_identity"), dict) else None,
        score_breakdown=row.get("score_breakdown") if isinstance(row.get("score_breakdown"), dict) else None,
        eligible=bool(row.get("eligible", True)),
        reason_code=str(row.get("reason_code") or "LEGACY_TOPIC"),
        selection_rationale=row.get("selection_rationale") if isinstance(row.get("selection_rationale"), dict) else None,
    )


def load_active_topic_bank() -> list[ResearchTopic]:
    rows = load_list_payload(manager_paths()["topic_bank"], "topics")
    topics = [topic_from_json(row) for row in rows]
    return [topic for topic in topics if topic is not None and topic.eligible]


def is_active_bank_topic(topic_id: str, registry_rows: dict[str, dict[str, Any]], queued_ids: set[str] | None = None) -> bool:
    if queued_ids and topic_id in queued_ids:
        return False
    current = registry_rows.get(topic_id, {})
    if int(current.get("run_count") or 0) > 0:
        return False
    status = str(current.get("manager_status") or "candidate")
    return status == "candidate"


def write_topic_bank(
    topics: list[ResearchTopic],
    args: argparse.Namespace,
    registry_rows: dict[str, dict[str, Any]] | None = None,
    queued_ids: set[str] | None = None,
) -> Path:
    path = OUTPUT_DIR / "topic_bank.json"
    registry_rows = registry_rows or load_topic_registry()
    active_topics = [
        topic
        for topic in topics
        if topic.eligible and is_active_bank_topic(topic.topic_id, registry_rows, queued_ids)
    ]
    payload = {
        "schema_version": TOPIC_BANK_SCHEMA_VERSION,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "topic_count": len(active_topics),
        "generated_topic_count": len(topics),
        "source": "ranking_artifacts",
        "selection_limit_for_run": args.max_topics,
        "topics": [topic_to_json(topic) for topic in active_topics],
        "contract": {
            "research_only": True,
            "active_bank_excludes_queued_topics": True,
            "active_bank_excludes_completed_topics": True,
            "topic_bank_does_not_promote": True,
            "production_promotion_allowed": False,
        },
    }
    write_text_atomic(path, json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False))
    return path


def outcome_from_comparison(path: Path | None) -> dict[str, Any]:
    payload = load_json(path)
    rows = {row.get("variant"): row for row in payload.get("summary", [])}
    baseline = rows.get("baseline") or {}
    candidate = rows.get("candidate") or {}
    if candidate.get("exact_match_regime_required") and candidate.get("statistical_gate_ok") is not True:
        matrix_path = resolve_path(candidate.get("path"))
        matrix_payload = load_json(matrix_path)
        gate = (matrix_payload.get("summary") or {}).get("statistical_gate") or {}
        if gate.get("reason_code") == "INSUFFICIENT_EVIDENCE":
            return {
                "decision": "INSUFFICIENT_EVIDENCE",
                "score_delta": None,
                "return_delta": None,
                "drawdown_delta": None,
                "baseline": baseline,
                "candidate": candidate,
                "promotion_allowed": False,
                "reason_code": "INSUFFICIENT_EVIDENCE",
            }
        return {
            "decision": "NO_STRATEGY",
            "score_delta": None,
            "return_delta": None,
            "drawdown_delta": None,
            "baseline": baseline,
            "candidate": candidate,
            "promotion_allowed": False,
            "reason_code": "MULTIPLE_TESTING_OR_ROBUSTNESS_FAILED",
        }
    score_delta = delta(candidate.get("best_score"), baseline.get("best_score"))
    return_delta = delta(candidate.get("best_total_return"), baseline.get("best_total_return"))
    drawdown_delta = delta(candidate.get("best_max_drawdown"), baseline.get("best_max_drawdown"))
    if score_delta is None:
        decision = "NO_COMPARISON_EVIDENCE"
    elif score_delta > 0 and (return_delta or 0) >= 0 and (drawdown_delta or 0) >= 0:
        decision = "CONFIRMED_FOR_NEXT_REPLAY"
    elif score_delta > 0:
        decision = "PARTIAL_SCORE_ONLY"
    else:
        decision = "REJECTED_BY_STRATEGY_MATRIX"
    return {
        "decision": decision,
        "score_delta": score_delta,
        "return_delta": return_delta,
        "drawdown_delta": drawdown_delta,
        "baseline": baseline,
        "candidate": candidate,
        "promotion_allowed": False,
    }


def topic_manager_status(topic: dict[str, Any], run_outcome: dict[str, Any] | None = None) -> str:
    if run_outcome:
        decision = run_outcome.get("decision")
        if decision == "CONFIRMED_FOR_NEXT_REPLAY":
            return "confirmed_for_next_replay"
        if decision == "PARTIAL_SCORE_ONLY":
            return "partial_needs_followup"
        if decision == "REJECTED_BY_STRATEGY_MATRIX":
            return "rejected"
        if decision == "NO_COMPARISON_EVIDENCE":
            return "blocked_missing_evidence"
        if decision == "NO_STRATEGY":
            return "no_strategy"
    return str(topic.get("manager_status") or "candidate")


def next_action_for_status(status: str, topic: dict[str, Any]) -> str:
    mapping = {
        "candidate": "run_autonomous_research_execute_smoke",
        "confirmed_for_next_replay": "promote_to_longer_replay_candidate",
        "partial_needs_followup": "rerun_with_larger_window_or_add_risk_check",
        "rejected": "archive_or_wait_for_new_evidence",
        "blocked_missing_evidence": "inspect_runner_outputs_and_missing_artifacts",
        "no_strategy": "wait_for_new_pre_registered_hypothesis",
    }
    return mapping.get(status, f"manual_review:{topic.get('topic_id')}")


def topic_actionable_for_queue(topic: dict[str, Any]) -> bool:
    """判斷 topic 是否仍有可執行的 manager lifecycle；冷卻由選題 gate 負責。"""
    if topic.get("eligible") is not True:
        return False
    status = str(topic.get("manager_status") or "candidate")
    run_count = int(topic.get("run_count") or 0)
    if run_count == 0:
        return status in {"candidate", "confirmed_for_next_replay", "partial_needs_followup", "blocked_missing_evidence"}
    policy = CONTROLLED_RERUN_POLICIES.get(status)
    return policy is not None and run_count < policy["max_run_count"]


def manager_paths() -> dict[str, Path]:
    return {
        "topic_bank": OUTPUT_DIR / "topic_bank.json",
        "registry": OUTPUT_DIR / "topic_registry.json",
        "history": OUTPUT_DIR / "run_history.json",
        "queue": OUTPUT_DIR / "next_action_queue.json",
        "summary": OUTPUT_DIR / "manager_summary.json",
        "runner_registry": OUTPUT_DIR / "runner_registry.json",
    }


def load_list_payload(path: Path, key: str) -> list[dict[str, Any]]:
    payload = load_json(path)
    value = payload.get(key)
    return value if isinstance(value, list) else []


def update_manager(payload: dict[str, Any], run_output: Path) -> dict[str, Any]:
    paths = manager_paths()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    registry_rows = {row.get("topic_id"): row for row in load_list_payload(paths["registry"], "topics") if row.get("topic_id")}
    selected_topics = [item for item in payload.get("selected_topics", []) if item.get("topic_id")]
    selected_ids = {item.get("topic_id") for item in selected_topics}
    topic_runs = payload.get("topic_runs", [])
    outcome_by_topic = {
        run.get("topic", {}).get("topic_id"): run.get("outcome")
        for run in topic_runs
        if run.get("topic", {}).get("topic_id")
    }
    for topic in payload.get("topics", []):
        topic_id = topic.get("topic_id")
        if not topic_id:
            continue
        current = registry_rows.get(topic_id, {})
        run_outcome = outcome_by_topic.get(topic_id) if payload["inputs"].get("execute") else None
        manager_status = topic_manager_status(current or topic, run_outcome)
        registry_rows[topic_id] = {
            **current,
            **topic,
            "manager_status": manager_status,
            "next_action": next_action_for_status(manager_status, topic),
            "last_seen_at": now,
            "last_run_output": repo_path(run_output) if topic_id in selected_ids else current.get("last_run_output"),
            "last_run_at": now
            if topic_id in selected_ids and payload["inputs"].get("execute")
            else current.get("last_run_at"),
            "last_decision": (run_outcome or {}).get("decision") if topic_id in selected_ids else current.get("last_decision"),
            "run_count": int(current.get("run_count") or 0) + (1 if topic_id in selected_ids and payload["inputs"].get("execute") else 0),
        }

    history = load_list_payload(paths["history"], "runs")
    history.append(
        {
            "run_id": f"{payload['date']}:{Path(run_output).stem}",
            "date": payload["date"],
            "generated_at": payload["generated_at"],
            "execute": payload["inputs"].get("execute"),
            "status": payload["status"],
            "selected_topic_id": selected_topics[0].get("topic_id") if selected_topics else None,
            "selected_topic_ids": sorted(selected_ids),
            "decision": (payload.get("outcome") or {}).get("decision"),
            "decisions": [
                {
                    "topic_id": run.get("topic", {}).get("topic_id"),
                    "decision": (run.get("outcome") or {}).get("decision"),
                    "status": run.get("status"),
                }
                for run in topic_runs
            ],
            "output": repo_path(run_output),
            "promotion_allowed": False,
        }
    )
    history = history[-200:]
    topics = sorted(registry_rows.values(), key=lambda item: (-float(item.get("score") or 0), str(item.get("topic_id"))))
    queue = [
        {
            "topic_id": topic.get("topic_id"),
            "manager_status": topic.get("manager_status"),
            "next_action": topic.get("next_action"),
            "score": topic.get("score"),
            "last_decision": topic.get("last_decision"),
            "candidate_dir": topic.get("candidate_dir"),
        }
        for topic in topics
        if topic_actionable_for_queue(topic)
    ][:25]
    queued_ids = {str(item.get("topic_id")) for item in queue if item.get("topic_id")}
    all_topics = [topic for topic in payload.get("all_topics", []) if isinstance(topic, dict)]
    active_bank_topics = [
        topic
        for topic in all_topics
        if topic.get("topic_id")
        and topic.get("eligible") is True
        and is_active_bank_topic(str(topic.get("topic_id")), registry_rows, queued_ids)
    ]
    counts: dict[str, int] = {}
    for topic in topics:
        status = str(topic.get("manager_status") or "candidate")
        counts[status] = counts.get(status, 0) + 1
    summary = {
        "schema_version": MANAGER_SCHEMA_VERSION,
        "updated_at": now,
        "status": "OK",
        "topic_count": len(topics),
        "run_count": len(history),
        "status_counts": counts,
        "next_action_count": len(queue),
        "active_topic_bank_count": len(active_bank_topics),
        "top_next_actions": queue[:5],
        "latest_run": history[-1] if history else None,
        "contract": {
            "research_only": True,
            "manager_does_not_promote": True,
            "production_promotion_allowed": False,
            "controlled_rerun_policies": CONTROLLED_RERUN_POLICIES,
        },
    }
    write_text_atomic(
        paths["registry"],
        json.dumps({"schema_version": "autonomous-research-topic-registry.v1", "updated_at": now, "topics": topics}, ensure_ascii=False, indent=2, allow_nan=False),
    )
    write_text_atomic(
        paths["history"],
        json.dumps({"schema_version": "autonomous-research-run-history.v1", "updated_at": now, "runs": history}, ensure_ascii=False, indent=2, allow_nan=False),
    )
    write_text_atomic(
        paths["queue"],
        json.dumps({"schema_version": "autonomous-research-next-action-queue.v1", "updated_at": now, "actions": queue}, ensure_ascii=False, indent=2, allow_nan=False),
    )
    write_text_atomic(
        paths["topic_bank"],
        json.dumps(
            {
                "schema_version": TOPIC_BANK_SCHEMA_VERSION,
                "updated_at": now,
                "topic_count": len(active_bank_topics),
                "generated_topic_count": len(all_topics),
                "source": "ranking_artifacts",
                "topics": active_bank_topics,
                "contract": {
                    "research_only": True,
                    "active_bank_excludes_queued_topics": True,
                    "active_bank_excludes_completed_topics": True,
                    "topic_bank_does_not_promote": True,
                    "production_promotion_allowed": False,
                },
            },
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
    )
    write_text_atomic(
        paths["runner_registry"],
        json.dumps(
            {
                "schema_version": RUNNER_REGISTRY_SCHEMA_VERSION,
                "updated_at": now,
                "runners": RUNNER_SPECS,
                "allowed_scripts": sorted(ALLOWED_RUNNERS),
                "contract": {
                    "allowlisted_runners_only": True,
                    "production_promotion_allowed": False,
                },
            },
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
    )
    write_text_atomic(paths["summary"], json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False))
    return {
        "status": "OK",
        "topic_registry": repo_path(paths["registry"]),
        "topic_bank": repo_path(paths["topic_bank"]),
        "run_history": repo_path(paths["history"]),
        "next_action_queue": repo_path(paths["queue"]),
        "manager_summary": repo_path(paths["summary"]),
        "runner_registry": repo_path(paths["runner_registry"]),
        "status_counts": counts,
        "next_action_count": len(queue),
        "active_topic_bank_count": len(active_bank_topics),
    }


def delta(left: Any, right: Any) -> float | None:
    try:
        if left is None or right is None:
            return None
        return round(float(left) - float(right), 6)
    except (TypeError, ValueError):
        return None


def prepare_closed_experiment(
    args: argparse.Namespace,
    topic: ResearchTopic,
    run_dir: Path,
) -> dict[str, Any]:
    if topic.regime_identity is None:
        raise ValueError("closed experiment 缺少 exact-match regime identity")
    history_path = resolve_path(getattr(args, "market_regime_history", None))
    contract_path = resolve_path(getattr(args, "research_contract", None))
    if history_path is None or contract_path is None:
        raise ValueError("closed experiment 缺少 market regime history 或 research contract")
    history = load_json(history_path)
    rows = history.get("rows") if isinstance(history.get("rows"), list) else []
    as_of_check = validate_as_of_regime_rows(rows)
    if not as_of_check["ok"]:
        raise ValueError(f"market regime history 不符合 as-of 契約：{as_of_check['violations'][:3]}")
    regime_id = regime_identity_id(topic.regime_identity)
    contract = load_json(contract_path)
    horizons = parse_positive_ints(topic.horizons or args.horizons)
    lineage = statistical_lineage_authority(
        rows=rows,
        contract=contract,
        regime_id=regime_id,
        horizons=horizons,
    )
    split_payload = lineage["split_artifact"]
    split_path = run_dir / f"{slugify(topic.topic_id)}_closed_episode_split.json"
    write_text_atomic(split_path, json.dumps(split_payload, ensure_ascii=False, indent=2, allow_nan=False))
    universe = parameter_universe_summary(contract)
    tested_combinations = validation_profile_combinations(
        topic.horizons or args.horizons,
        topic.stop_loss_pcts or args.stop_loss_pcts,
        topic.take_profit_pcts or args.take_profit_pcts,
        topic.max_group_exposures or args.max_group_exposures,
    )
    tested_combination_ids = sorted(canonical_json_hash(item) for item in tested_combinations)
    legal_combination_ids = sorted(str(item) for item in universe["legal_combination_ids"])
    unexpected_combinations = sorted(set(tested_combination_ids) - set(legal_combination_ids))
    if unexpected_combinations:
        raise ValueError(f"validation profile 包含 contract 外參數組合：{unexpected_combinations[:3]}")
    tested_combination_ids_hash = canonical_json_hash(tested_combination_ids)
    correction_family_id = canonical_json_hash(legal_combination_ids)
    authority = statistical_family_contract(contract)
    partition_check = validate_statistical_partition(
        partition_id=topic.validation_profile,
        tested_combination_ids=tested_combination_ids,
        authority=authority,
    )
    if not partition_check["ok"]:
        raise ValueError(f"validation profile 不是合法 contract partition：{partition_check}")
    partition_policy = {
        "policy_id": "validation_profile_partition.v1",
        "partition_id": topic.validation_profile,
        "correction_scope": "global_parameter_universe",
        "parameter_space_hash": universe["parameter_space_hash"],
        "tested_combination_count": len(tested_combination_ids),
        "tested_combination_ids_hash": tested_combination_ids_hash,
        "correction_family_id": correction_family_id,
        "correction_family_size": len(legal_combination_ids),
    }
    registration = build_experiment_pre_registration(
        {
            "experiment_label": f"{args.date}:{topic.topic_id}",
            "research_question": topic.hypothesis,
            "baseline_id": canonical_json_hash({"baseline_dir": topic.baseline_dir}),
            "regime_id": regime_id,
            "dataset_hash": lineage["dataset_hash"],
            "split_id": lineage["split_id"],
            "split_artifact_hash": lineage["split_artifact_hash"],
            "parameter_space_hash": universe["parameter_space_hash"],
            "contract_hash": authority["contract_hash"],
            "global_combination_ids": authority["global_combination_ids"],
            "global_combination_ids_hash": authority["global_combination_ids_hash"],
            "global_family_id": authority["global_family_id"],
            "global_family_size": authority["global_family_size"],
            "tested_combination_ids": tested_combination_ids,
            "tested_combination_ids_hash": tested_combination_ids_hash,
            "correction_family_combination_ids": legal_combination_ids,
            "correction_family_id": correction_family_id,
            "correction_family_size": len(legal_combination_ids),
            "partition_policy": partition_policy,
            "metric_policy_hash": canonical_json_hash(contract.get("multiple_testing_policy") or {}),
            "development_episode_ids": lineage["development_episode_ids"],
            "validation_episode_ids": lineage["validation_episode_ids"],
            "embargo_episode_ids": lineage["embargo_episode_ids"],
            "sealed_episode_ids": lineage["sealed_episode_ids"],
            "episode_split_ids_hash": lineage["episode_split_ids_hash"],
            "sealed_trade_dates": lineage["sealed_trade_dates"],
        }
    )
    registration_path = run_dir / f"{slugify(topic.topic_id)}_closed_pre_registration.json"
    registry_path = OUTPUT_DIR / "closed_experiment_registry.jsonl"
    registered = append_experiment_registry(registry_path, registration)
    if not registered["ok"]:
        raise RuntimeError(f"closed experiment registration failed: {registered}")
    registration = {
        **registration,
        "registry_record_hash": registered["registry_record_hash"],
    }
    write_text_atomic(
        registration_path,
        json.dumps(registration, ensure_ascii=False, indent=2, allow_nan=False),
    )
    coarse = transition_experiment_registry(
        registry_path,
        experiment_id=registration["experiment_id"],
        target_state="COARSE_SCREEN",
        evidence_path=repo_path(split_path) or str(split_path),
    )
    if not coarse["ok"]:
        raise RuntimeError(f"closed experiment coarse transition failed: {coarse}")
    return {
        "experiment": registration,
        "registry_path": registry_path,
        "split_path": split_path,
        "registration_path": registration_path,
        "development_episode_ids": list(lineage["development_episode_ids"]),
    }


def parse_positive_ints(value: str) -> list[int]:
    values = [int(item.strip()) for item in str(value).split(",") if item.strip()]
    if not values or any(item <= 0 for item in values):
        raise ValueError("closed experiment horizons 必須是正整數")
    return values


def execute_topic(args: argparse.Namespace, topic: ResearchTopic, run_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, str]]:
    if not topic.eligible:
        raise ValueError(f"topic 不符合執行資格：{topic.topic_id} ({topic.reason_code})")
    closed = (
        prepare_closed_experiment(args, topic, run_dir)
        if bool(getattr(args, "closed_regime_research", False))
        else None
    )
    allowed_episode_ids = closed["development_episode_ids"] if closed else None
    slug = slugify(topic.topic_id)
    baseline_output = run_dir / f"{slug}_baseline_strategy_matrix.json"
    candidate_output = run_dir / f"{slug}_candidate_strategy_matrix.json"
    comparison_output = run_dir / f"{slug}_comparison.json"
    commands = [
        (
            "baseline.strategy_matrix",
            matrix_command(
                args,
                topic.baseline_dir,
                repo_path(baseline_output) or str(baseline_output),
                topic,
                allowed_episode_ids=allowed_episode_ids,
                pre_registration_path=closed["registration_path"] if closed else None,
                experiment_registry_path=closed["registry_path"] if closed else None,
            ),
        ),
        (
            "candidate.strategy_matrix",
            matrix_command(
                args,
                topic.candidate_dir,
                repo_path(candidate_output) or str(candidate_output),
                topic,
                allowed_episode_ids=allowed_episode_ids,
                pre_registration_path=closed["registration_path"] if closed else None,
                experiment_registry_path=closed["registry_path"] if closed else None,
            ),
        ),
        (
            "compare.strategy_matrices",
            compare_command(
                repo_path(baseline_output) or str(baseline_output),
                repo_path(candidate_output) or str(candidate_output),
                repo_path(comparison_output) or str(comparison_output),
            ),
        ),
    ]
    steps: list[dict[str, Any]] = []
    failed: str | None = None
    for name, command in commands:
        if failed:
            steps.append(
                {
                    "name": name,
                    "status": "SKIPPED",
                    "returncode": None,
                    "started_at": datetime.now(timezone.utc).isoformat(),
                    "ended_at": datetime.now(timezone.utc).isoformat(),
                    "command": command,
                    "stdout_tail": "",
                    "stderr_tail": "",
                    "skip_reason": f"previous step failed: {failed}",
                }
            )
            continue
        step = run_step(name, command)
        steps.append(step)
        if step["status"] != "OK":
            failed = name
    outcome = outcome_from_comparison(comparison_output if comparison_output.exists() else None)
    outputs = {
        "baseline_strategy_matrix": repo_path(baseline_output) or str(baseline_output),
        "candidate_strategy_matrix": repo_path(candidate_output) or str(candidate_output),
        "comparison": repo_path(comparison_output) or str(comparison_output),
    }
    if closed:
        execution_evidence_path = run_dir / f"{slug}_closed_execution_evidence.json"
        write_text_atomic(
            execution_evidence_path,
            json.dumps(
                {"steps": steps, "outcome": outcome},
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            ),
        )
        if failed or outcome.get("decision") == "NO_COMPARISON_EVIDENCE":
            target_state = "BLOCKED"
        elif outcome.get("decision") == "INSUFFICIENT_EVIDENCE":
            target_state = "INSUFFICIENT_EVIDENCE"
        elif outcome.get("decision") == "NO_STRATEGY":
            target_state = "NO_STRATEGY"
        else:
            target_state = "SAME_REGIME_VALIDATION"
        transition = transition_experiment_registry(
            closed["registry_path"],
            experiment_id=closed["experiment"]["experiment_id"],
            target_state=target_state,
            evidence_path=repo_path(execution_evidence_path) or str(execution_evidence_path),
        )
        if not transition["ok"]:
            raise RuntimeError(f"closed experiment final transition failed: {transition}")
        outputs.update(
            {
                "closed_experiment_registry": repo_path(closed["registry_path"])
                or str(closed["registry_path"]),
                "closed_episode_split": repo_path(closed["split_path"]) or str(closed["split_path"]),
                "closed_pre_registration": repo_path(closed["registration_path"])
                or str(closed["registration_path"]),
                "closed_execution_evidence": repo_path(execution_evidence_path)
                or str(execution_evidence_path),
            }
        )
        outcome = {
            **outcome,
            "closed_experiment_id": closed["experiment"]["experiment_id"],
            "closed_final_state": target_state,
        }
    return steps, outcome, outputs


def build_payload(
    args: argparse.Namespace,
    topics: list[ResearchTopic],
    selected_topics_for_run: list[ResearchTopic],
    topic_runs: list[dict[str, Any]],
    steps: list[dict[str, Any]],
    outcome: dict[str, Any],
    outputs: dict[str, str],
    manager: dict[str, Any] | None = None,
    all_topics: list[ResearchTopic] | None = None,
    source_lineage: dict[str, str] | None = None,
) -> dict[str, Any]:
    selected = selected_topics_for_run[0] if selected_topics_for_run else None
    executed = bool(args.execute and selected_topics_for_run)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK" if (not executed or all(step["status"] == "OK" for step in steps)) else "FAILED",
        "contract": {
            "autonomous_topic_generation": True,
            "research_only": True,
            "allowlisted_runners_only": True,
            "does_not_fetch_data": True,
            "does_not_train_model": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_risk_adjusted_score": True,
            "does_not_change_production_ranking": True,
            "production_promotion_allowed": False,
            "controlled_rerun_policies": CONTROLLED_RERUN_POLICIES,
            "closed_regime_research": bool(getattr(args, "closed_regime_research", False)),
            "exact_match_required": bool(getattr(args, "closed_regime_research", False)),
            "sealed_oos_required_before_policy_candidate": bool(getattr(args, "closed_regime_research", False)),
        },
        "inputs": {
            "execute": args.execute,
            "features": args.features,
            "baseline_dir": args.baseline_dir,
            "candidate_dir": args.candidate_dir,
            "topic_index": args.topic_index,
            "execute_topic_count": args.execute_topic_count,
            "from_queue": args.from_queue,
            "rerun": args.rerun,
            "include_rejected": args.include_rejected,
            "max_ranking_files": args.max_ranking_files,
            "horizons": args.horizons,
            "stop_loss_pcts": args.stop_loss_pcts,
            "take_profit_pcts": args.take_profit_pcts,
            "max_group_exposures": args.max_group_exposures,
            "manager_update": not args.no_manager_update,
            "closed_regime_research": bool(getattr(args, "closed_regime_research", False)),
            "market_regime_history": getattr(args, "market_regime_history", None),
            "research_contract": getattr(args, "research_contract", None),
            "coverage_map": getattr(args, "coverage_map", None),
        },
        "selected_topic": topic_to_json(selected) if selected else None,
        "selected_topics": [topic_to_json(topic) for topic in selected_topics_for_run],
        "topics": [topic_to_json(topic) for topic in topics],
        "all_topics": [topic_to_json(topic) for topic in (all_topics or topics)],
        "topic_runs": topic_runs,
        "steps": steps,
        "outcome": outcome,
        "outputs": outputs,
        "manager": manager or {"status": "PENDING_WRITE"},
    }
    if bool(getattr(args, "closed_regime_research", False)):
        payload["source_lineage"] = source_lineage
    return payload


def render_markdown(payload: dict[str, Any]) -> str:
    selected = payload.get("selected_topic") or {}
    lines = [
        "# Autonomous Research Run",
        "",
        f"- status: `{payload['status']}`",
        f"- execute: `{payload['inputs']['execute']}`",
        f"- selected: `{selected.get('topic_id')}`",
        f"- decision: `{payload.get('outcome', {}).get('decision')}`",
        f"- manager: `{payload.get('manager', {}).get('status')}`",
        f"- production_promotion_allowed: `{payload['contract']['production_promotion_allowed']}`",
        "",
        "## Selected Topic",
        "",
        f"- title: {selected.get('title')}",
        f"- hypothesis: {selected.get('hypothesis')}",
        f"- validation_plan: {selected.get('validation_plan')}",
        "",
        "## Top Topics",
        "",
        "| Rank | Topic | Score | Ranking Files |",
        "|---:|---|---:|---:|",
    ]
    for index, topic in enumerate(payload.get("topics", [])[:10], start=1):
        lines.append(f"| {index} | `{topic['topic_id']}` | {topic['score']} | {topic['ranking_file_count']} |")
    lines.extend(["", "## Steps", "", "| Step | Status |", "|---|---|"])
    for step in payload.get("steps", []):
        lines.append(f"| `{step['name']}` | `{step['status']}` |")
    manager = payload.get("manager") or {}
    lines.extend(["", "## Manager", ""])
    for key in ["topic_registry", "run_history", "next_action_queue", "manager_summary", "runner_registry"]:
        if manager.get(key):
            lines.append(f"- `{key}`: `{manager[key]}`")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    output = resolve_path(args.output) or OUTPUT_DIR / f"autonomous_research_{args.date}.json"
    run_dir = output.parent / f"run_{args.date}_{datetime.now().strftime('%H%M%S')}"
    output.parent.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=True, exist_ok=True)
    source_lineage = (
        build_daily_source_lineage(
            root=PROJECT_ROOT,
            features_path=args.features,
            market_run_date=str(args.date),
        )
        if bool(getattr(args, "closed_regime_research", False))
        else None
    )
    all_topics = generate_all_topics(args)
    topic_bank_path = write_topic_bank(all_topics, args, queued_ids=queued_topic_ids())
    active_topics = load_active_topic_bank()
    topics = all_topics[: args.max_topics] if args.from_queue else active_topics[: args.max_topics]
    selected_topics_for_run = select_topics_for_run(topics, args)
    steps: list[dict[str, Any]] = []
    topic_runs: list[dict[str, Any]] = []
    first_topic = selected_topics_for_run[0] if selected_topics_for_run else None
    outcome = {"decision": "DRY_RUN_TOPIC_SELECTED" if first_topic else "NO_EXECUTABLE_TOPIC", "promotion_allowed": False}
    outputs: dict[str, str] = {"run_dir": repo_path(run_dir) or str(run_dir), "topic_bank": repo_path(topic_bank_path) or str(topic_bank_path)}
    if args.execute and selected_topics_for_run:
        decisions: list[str] = []
        for index, topic in enumerate(selected_topics_for_run, start=1):
            topic_steps, topic_outcome, step_outputs = execute_topic(args, topic, run_dir)
            prefixed_steps = [{**step, "name": f"topic{index}.{step['name']}", "topic_id": topic.topic_id} for step in topic_steps]
            steps.extend(prefixed_steps)
            decisions.append(str(topic_outcome.get("decision")))
            topic_runs.append(
                {
                    "topic": topic_to_json(topic),
                    "status": "OK" if all(step["status"] == "OK" for step in topic_steps) else "FAILED",
                    "outcome": topic_outcome,
                    "steps": topic_steps,
                    "outputs": step_outputs,
                }
            )
            if index == 1:
                outcome = topic_outcome
                outputs.update(step_outputs)
        outcome = {
            **outcome,
            "aggregate": {
                "topic_count": len(selected_topics_for_run),
                "decisions": decisions,
                "all_topic_runs_ok": all(run["status"] == "OK" for run in topic_runs),
            },
            "promotion_allowed": False,
        }
    payload = build_payload(
        args,
        topics,
        selected_topics_for_run,
        topic_runs,
        steps,
        outcome,
        outputs,
        all_topics=all_topics,
        source_lineage=source_lineage,
    )
    write_run_artifacts(payload, output)
    if not args.no_manager_update:
        manager = update_manager(payload, output)
        payload = build_payload(
            args,
            topics,
            selected_topics_for_run,
            topic_runs,
            steps,
            outcome,
            outputs,
            manager=manager,
            all_topics=all_topics,
            source_lineage=source_lineage,
        )
        write_run_artifacts(payload, output)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "output": repo_path(output),
                "selected_topic": (payload.get("selected_topic") or {}).get("topic_id"),
                "decision": payload.get("outcome", {}).get("decision"),
                "execute": args.execute,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
