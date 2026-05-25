"""型態訊號登錄表。

UI 與報告只讀這裡的說明，避免每個地方各寫一套小白解釋。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PatternSignalDefinition:
    signal_id: str
    label: str
    category: str
    polarity: str
    beginner_note: str
    action_hint: str
    display_priority: int = 10


PATTERN_SIGNAL_DEFINITIONS: dict[str, PatternSignalDefinition] = {
    "candle_doji": PatternSignalDefinition(
        "candle_doji",
        "十字星",
        "candlestick",
        "neutral",
        "多空拉扯接近平衡，常出現在轉折或整理前後。",
        "不要單獨當買賣點，搭配量能、位置與隔日方向確認。",
    ),
    "candle_dragonfly_doji": PatternSignalDefinition(
        "candle_dragonfly_doji",
        "蜻蜓十字",
        "candlestick",
        "bullish",
        "盤中被打低後收回，低檔出現時代表買盤有防守。",
        "觀察是否站回短均線，跌破低點則訊號失效。",
        display_priority=30,
    ),
    "candle_tombstone_doji": PatternSignalDefinition(
        "candle_tombstone_doji",
        "墓碑十字",
        "candlestick",
        "bearish",
        "盤中拉高後被壓回，高檔出現時代表上方賣壓重。",
        "若隔日跌破低點或量縮不再攻高，風險要提高。",
        display_priority=30,
    ),
    "candle_hammer": PatternSignalDefinition(
        "candle_hammer",
        "錘子線",
        "candlestick",
        "bullish",
        "下影線長，代表盤中殺低後有人承接。",
        "低檔搭配放量與隔日紅 K，可信度較高。",
        display_priority=20,
    ),
    "candle_shooting_star": PatternSignalDefinition(
        "candle_shooting_star",
        "流星線",
        "candlestick",
        "bearish",
        "上影線長，代表追價後被賣壓壓回。",
        "高檔出現時先降低追價，觀察是否跌破短線支撐。",
        display_priority=20,
    ),
    "candle_bull_engulfing": PatternSignalDefinition(
        "candle_bull_engulfing",
        "多方吞噬",
        "candlestick",
        "bullish",
        "今日紅 K 包住前一根黑 K，代表買盤反攻。",
        "適合搭配均線翻揚與量能放大確認。",
        display_priority=25,
    ),
    "candle_bear_engulfing": PatternSignalDefinition(
        "candle_bear_engulfing",
        "空方吞噬",
        "candlestick",
        "bearish",
        "今日黑 K 包住前一根紅 K，代表賣壓反攻。",
        "若出現在高檔或壓力區，應提高風險折扣。",
        display_priority=25,
    ),
    "td_buy_setup": PatternSignalDefinition(
        "td_buy_setup",
        "TD 買九",
        "td_sequential",
        "bullish",
        "連續下跌結構走到第九根，代表跌勢可能進入疲乏區。",
        "不是保證反轉，需等止跌或隔日轉強確認。",
    ),
    "td_sell_setup": PatternSignalDefinition(
        "td_sell_setup",
        "TD 賣九",
        "td_sequential",
        "bearish",
        "連續上漲結構走到第九根，代表漲勢可能進入疲乏區。",
        "高檔出現時避免追價，搭配量能與長上影線確認風險。",
    ),
    "pattern_w_bottom": PatternSignalDefinition(
        "pattern_w_bottom",
        "W 底突破",
        "price_structure",
        "bullish",
        "價格兩次守住相近低點，再突破中間頸線。",
        "頸線突破後觀察是否站穩，跌破右腳低點則失效。",
    ),
    "pattern_m_top": PatternSignalDefinition(
        "pattern_m_top",
        "M 頭跌破",
        "price_structure",
        "bearish",
        "價格兩次攻高失敗，再跌破中間頸線。",
        "若反彈站不回頸線，風險通常仍未解除。",
    ),
}
