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
from .registry import MODEL_SPECS, get_model_spec, validate_model_registry
from .sealed_oos import SealedOOSConfig, build_sealed_oos_split, evaluate_sealed_oos_model

__all__ = [
    "FUNDAMENTAL_FEATURE_COLUMNS",
    "MODEL_SPECS",
    "FeatureFrameMetadata",
    "FeatureGroupMetadata",
    "ModelSpec",
    "ModelValidationIssue",
    "SealedOOSConfig",
    "build_m4_feature_frame",
    "build_sealed_oos_split",
    "candidate_feature_columns",
    "evaluate_sealed_oos_model",
    "get_model_spec",
    "load_m4_feature_frame",
    "validate_model_registry",
]
