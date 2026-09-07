"""價格型態訊號層。

這層只負責把 OHLCV 轉成可被模型、排序與 UI 共用的訊號欄位。
"""

from .candlestick import CANDLESTICK_COLUMNS, add_candlestick_patterns
from .price_patterns import PRICE_PATTERN_COLUMNS, add_price_patterns
from .registry import PATTERN_SIGNAL_DEFINITIONS, PatternSignalDefinition
from .specs import (
    DAILY_CLOSE_DATASET_CONTRACT,
    INITIAL_SIGNAL_SPECS,
    SignalCalendarPolicy,
    SignalDirection,
    SignalEligibilityStatus,
    SignalEvaluation,
    SignalEvaluationState,
    SignalObservabilityWarning,
    SignalParityReport,
    SignalParityResult,
    SignalSpec,
    SignalSpecContractError,
    radar_eligible_signal_specs,
    resolve_signal_evaluation,
    validate_signal_parity,
)
from .scanner import (
    SCANNER_CONTRACT_VERSION,
    DailySignalScanHit,
    DailySignalScanReport,
    DailySignalScanStatus,
    DailySignalScanSummary,
    DailySignalScannerError,
    DailySignalScanWarning,
    scan_finalized_daily_signals,
)
from .occurrences import (
    RADAR_PROJECTION_BUILD_VERSION,
    RANKING_IMPACT_NONE,
    SIGNAL_OCCURRENCE_SCHEMA_VERSION,
    SignalOccurrence,
    SignalOccurrenceError,
    build_signal_occurrences,
)
from .radar_projection import (
    DAILY_RADAR_PROJECTION_SCHEMA_VERSION,
    DailyRadarInstrumentItem,
    DailyRadarProjection,
    build_daily_radar_projection,
)
from .td_sequential import TD_COLUMNS, add_td_sequential

__all__ = [
    "CANDLESTICK_COLUMNS",
    "DAILY_CLOSE_DATASET_CONTRACT",
    "INITIAL_SIGNAL_SPECS",
    "PRICE_PATTERN_COLUMNS",
    "PATTERN_SIGNAL_DEFINITIONS",
    "PatternSignalDefinition",
    "DAILY_RADAR_PROJECTION_SCHEMA_VERSION",
    "RADAR_PROJECTION_BUILD_VERSION",
    "RANKING_IMPACT_NONE",
    "SCANNER_CONTRACT_VERSION",
    "SIGNAL_OCCURRENCE_SCHEMA_VERSION",
    "DailyRadarInstrumentItem",
    "DailyRadarProjection",
    "DailySignalScanHit",
    "DailySignalScanReport",
    "DailySignalScanStatus",
    "DailySignalScanSummary",
    "DailySignalScannerError",
    "DailySignalScanWarning",
    "SignalOccurrence",
    "SignalOccurrenceError",
    "SignalCalendarPolicy",
    "SignalDirection",
    "SignalEligibilityStatus",
    "SignalEvaluation",
    "SignalEvaluationState",
    "SignalObservabilityWarning",
    "SignalParityReport",
    "SignalParityResult",
    "SignalSpec",
    "SignalSpecContractError",
    "TD_COLUMNS",
    "add_candlestick_patterns",
    "add_price_patterns",
    "add_td_sequential",
    "build_daily_radar_projection",
    "build_signal_occurrences",
    "radar_eligible_signal_specs",
    "resolve_signal_evaluation",
    "scan_finalized_daily_signals",
    "validate_signal_parity",
]
