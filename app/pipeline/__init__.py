"""Stage-based ETL pipeline package.

使用 lazy export，避免 `validate` 這類只讀檢查被外部抓資料套件 import 擋住。
"""

from __future__ import annotations

from importlib import import_module
from typing import Any


_EXPORTS = {
    "ETLPipeline": "app.pipeline.orchestrator",
    "FetchStage": "app.pipeline.fetch_stage",
    "IndicatorStage": "app.pipeline.indicator_stage",
    "FundamentalStage": "app.pipeline.fundamental_stage",
    "EventStage": "app.pipeline.event_stage",
    "FilterStage": "app.pipeline.filter_stage",
    "ReportStage": "app.pipeline.report_stage",
    "PipelineDataValidator": "app.pipeline.validation",
    "LocalOutputRepair": "app.pipeline.repair",
}


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(f"module 'app.pipeline' has no attribute {name!r}")
    module = import_module(_EXPORTS[name])
    return getattr(module, name)


__all__ = tuple(_EXPORTS)
