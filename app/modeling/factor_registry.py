"""M4 因子登錄與洩漏風險檢查。

這層只描述欄位能不能安全進訓練 frame，不決定權重，也不觸發訓練。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

import pandas as pd


SCHEMA_VERSION = "factor-registry.v1"
RUN_MANIFEST_SCHEMA_VERSION = "factor-run-manifest.v1"
TRAINING_BLOCKLIST_PREFIXES = (
    "target",
    "future_",
    "next_",
    "label_",
)
TRAINING_BLOCKLIST_NAMES = {
    "target",
    "entry_price",
    "exit_price",
    "future_close",
    "future_return",
    "return_long",
    "return_5d",
}


@dataclass(frozen=True)
class FactorGroupDefinition:
    group_id: str
    source_layer: str
    owner_model_id: str
    availability_rule: str
    training_allowed: bool
    leakage_guard: str
    description: str


@dataclass(frozen=True)
class FactorDefinition:
    factor_id: str
    group_id: str
    source_layer: str
    owner_model_id: str
    availability_rule: str
    training_allowed: bool
    leakage_guard: str


@dataclass(frozen=True)
class FactorValidationIssue:
    severity: str
    factor_id: str
    message: str


FACTOR_GROUP_DEFINITIONS: dict[str, FactorGroupDefinition] = {
    "technical": FactorGroupDefinition(
        group_id="technical",
        source_layer="daily_ohlcv_indicators",
        owner_model_id="M1_TECHNICAL_FACTORS",
        availability_rule="trade_date_close_only",
        training_allowed=True,
        leakage_guard="不得引用 future_*、target、label 或隔日報酬欄位。",
        description="由當日收盤後已知的 OHLCV 與技術指標計算而來。",
    ),
    "event": FactorGroupDefinition(
        group_id="event",
        source_layer="event_detector",
        owner_model_id="M3_EVENT_SIGNALS",
        availability_rule="trade_date_close_only",
        training_allowed=True,
        leakage_guard="事件欄位必須是 0/1，且只能由當日以前資料觸發。",
        description="由 config/signals.yaml 定義的正負事件訊號。",
    ),
    "pattern": FactorGroupDefinition(
        group_id="pattern",
        source_layer="pattern_signals",
        owner_model_id="M3_EVENT_SIGNALS",
        availability_rule="trade_date_close_only",
        training_allowed=True,
        leakage_guard="型態訊號只可使用當日 K 線與過去窗口。",
        description="K 線型態、TD Sequential 與價格結構訊號。",
    ),
    "fundamental": FactorGroupDefinition(
        group_id="fundamental",
        source_layer="fundamental_cache_asof",
        owner_model_id="M2_FUNDAMENTAL_QUALITY",
        availability_rule="asof_available_from_backward_join",
        training_allowed=True,
        leakage_guard="基本面只能用 available_from 之後的資料，不可用財報年度直接回填。",
        description="由本地基本面 cache 透過 as-of join 接入的財務指標。",
    ),
    "alpha_candidate": FactorGroupDefinition(
        group_id="alpha_candidate",
        source_layer="shadow_alpha_materializer",
        owner_model_id="M1_TECHNICAL_FACTORS",
        availability_rule="shadow_only_same_trade_date_close",
        training_allowed=False,
        leakage_guard="只能寫 artifacts/model_experiments；通過 ablation/replay 前不可進正式訓練或排名。",
        description="由既有日頻欄位推導的 shadow alpha 候選因子。",
    ),
}


def is_training_blocked_column(column: str) -> bool:
    """辨識明顯不能進模型的 target/future 類欄位。"""

    normalized = str(column).strip()
    return normalized in TRAINING_BLOCKLIST_NAMES or normalized.startswith(TRAINING_BLOCKLIST_PREFIXES)


def factor_definition_for_column(column: str, group_id: str) -> FactorDefinition:
    """依 feature group 建立欄位層級 metadata。"""

    group = FACTOR_GROUP_DEFINITIONS[group_id]
    training_allowed = group.training_allowed and not is_training_blocked_column(column)
    leakage_guard = group.leakage_guard
    if not training_allowed:
        leakage_guard = "欄位名稱命中 target/future/label blocklist，禁止進訓練。"
    return FactorDefinition(
        factor_id=str(column),
        group_id=group.group_id,
        source_layer=group.source_layer,
        owner_model_id=group.owner_model_id,
        availability_rule=group.availability_rule,
        training_allowed=training_allowed,
        leakage_guard=leakage_guard,
    )


def build_factor_registry(metadata: Any) -> dict[str, FactorDefinition]:
    """從 FeatureFrameMetadata 產生欄位登錄表。"""

    registry: dict[str, FactorDefinition] = {}
    for group_id, group_metadata in metadata.feature_groups.items():
        if group_id not in FACTOR_GROUP_DEFINITIONS:
            continue
        for column in group_metadata.columns:
            registry[column] = factor_definition_for_column(column, group_id)
    return registry


def trainable_factor_columns(frame: pd.DataFrame, metadata: Any) -> list[str]:
    """回傳通過 metadata 與 dtype 檢查的訓練候選欄位。"""

    registry = build_factor_registry(metadata)
    return [
        column
        for column, definition in registry.items()
        if definition.training_allowed
        and column in frame.columns
        and pd.api.types.is_numeric_dtype(frame[column])
    ]


def validate_factor_registry(frame: pd.DataFrame, metadata: Any) -> list[FactorValidationIssue]:
    """檢查因子登錄是否有未知群組、洩漏欄位或非數值欄位。"""

    issues: list[FactorValidationIssue] = []
    for group_id, group_metadata in metadata.feature_groups.items():
        if group_id not in FACTOR_GROUP_DEFINITIONS:
            issues.append(FactorValidationIssue("ERROR", group_id, "未知 feature group，無法判定時間可用性"))
            continue
        for column in group_metadata.columns:
            definition = factor_definition_for_column(column, group_id)
            if not definition.training_allowed:
                issues.append(FactorValidationIssue("ERROR", column, "欄位命中訓練 blocklist"))
                continue
            if column not in frame.columns:
                issues.append(FactorValidationIssue("ERROR", column, "metadata 欄位不存在於 feature frame"))
                continue
            if not pd.api.types.is_numeric_dtype(frame[column]):
                issues.append(FactorValidationIssue("WARN", column, "欄位不是數值 dtype，不會進 LightGBM 候選特徵"))
    return issues


def build_factor_run_manifest(frame: pd.DataFrame, metadata: Any) -> dict[str, Any]:
    """建立只讀 factor run artifact，用於回測/訓練前追溯因子來源。"""

    registry = build_factor_registry(metadata)
    issues = validate_factor_registry(frame, metadata)
    errors = [issue for issue in issues if issue.severity == "ERROR"]
    trainable = trainable_factor_columns(frame, metadata)
    return {
        "schema_version": RUN_MANIFEST_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK" if not errors else "FAILED",
        "contract": {
            "manifest_only": True,
            "does_not_train_model": True,
            "does_not_change_ranking_weight": True,
            "does_not_change_production_ranking": True,
        },
        "summary": {
            "rows": int(len(frame)),
            "stocks": int(frame["stock_id"].astype(str).nunique()) if "stock_id" in frame.columns else 0,
            "factor_count": len(registry),
            "trainable_factor_count": len(trainable),
            "issue_count": len(issues),
        },
        "groups": {group_id: asdict(definition) for group_id, definition in FACTOR_GROUP_DEFINITIONS.items()},
        "factors": {factor_id: asdict(definition) for factor_id, definition in registry.items()},
        "issues": [asdict(issue) for issue in issues],
    }
