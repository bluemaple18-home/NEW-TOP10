"""價格型態訊號層。

這層只負責把 OHLCV 轉成可被模型、排序與 UI 共用的訊號欄位。
"""

from .candlestick import CANDLESTICK_COLUMNS, add_candlestick_patterns
from .price_patterns import PRICE_PATTERN_COLUMNS, add_price_patterns
from .registry import PATTERN_SIGNAL_DEFINITIONS, PatternSignalDefinition
from .td_sequential import TD_COLUMNS, add_td_sequential

__all__ = [
    "CANDLESTICK_COLUMNS",
    "PRICE_PATTERN_COLUMNS",
    "PATTERN_SIGNAL_DEFINITIONS",
    "PatternSignalDefinition",
    "TD_COLUMNS",
    "add_candlestick_patterns",
    "add_price_patterns",
    "add_td_sequential",
]
