"""模型底座。

這個 package 只描述模型契約與組裝順序，不直接訓練或跑回測。
"""

from .feature_contract import (
    FUNDAMENTAL_FEATURE_COLUMNS,
    FeatureFrameMetadata,
    FeatureGroupMetadata,
    build_m4_feature_frame,
    candidate_feature_columns,
    load_m4_feature_frame,
)
from .contracts import ModelSpec, ModelValidationIssue
from .factor_registry import (
    FACTOR_GROUP_DEFINITIONS,
    FactorDefinition,
    FactorGroupDefinition,
    FactorValidationIssue,
    build_factor_registry,
    build_factor_run_manifest,
    trainable_factor_columns,
    validate_factor_registry,
)
from .registry import MODEL_SPECS, get_model_spec, validate_model_registry
from .sealed_oos import SealedOOSConfig, build_sealed_oos_split, evaluate_sealed_oos_model

__all__ = [
    "FACTOR_GROUP_DEFINITIONS",
    "FUNDAMENTAL_FEATURE_COLUMNS",
    "MODEL_SPECS",
    "FactorDefinition",
    "FeatureFrameMetadata",
    "FeatureGroupMetadata",
    "FactorGroupDefinition",
    "FactorValidationIssue",
    "ModelSpec",
    "ModelValidationIssue",
    "SealedOOSConfig",
    "build_factor_registry",
    "build_factor_run_manifest",
    "build_m4_feature_frame",
    "build_sealed_oos_split",
    "candidate_feature_columns",
    "evaluate_sealed_oos_model",
    "get_model_spec",
    "load_m4_feature_frame",
    "trainable_factor_columns",
    "validate_factor_registry",
    "validate_model_registry",
]
