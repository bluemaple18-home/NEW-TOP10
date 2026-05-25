
"""
Core Technical Indicators Module
Assembles all indicator logic via Mixins.
"""
import pandas as pd
import logging
from .mixins.trend import TrendIndicatorsMixin
from .mixins.momentum import MomentumIndicatorsMixin
from .mixins.volatility import VolatilityIndicatorsMixin
from .mixins.volume import VolumeIndicatorsMixin
from .mixins.pattern import PatternIndicatorsMixin

class TechnicalIndicators(
    TrendIndicatorsMixin,
    MomentumIndicatorsMixin,
    VolatilityIndicatorsMixin,
    VolumeIndicatorsMixin,
    PatternIndicatorsMixin
):
    """技術指標計算器 (向量化版本 - Atomic Refactored)"""
    
    def __init__(self, df: pd.DataFrame):
        """
        初始化技術指標計算器
        
        Args:
            df: 必須包含 date, stock_id, open, high, low, close, volume 欄位
        """
        self.logger = logging.getLogger(__name__)
        
        self.df = df.copy()
        # 確保資料型態正確
        if 'date' in self.df.columns:
            self.df['date'] = pd.to_datetime(self.df['date'])
            self.df = self.df.sort_values(['date', 'stock_id'])
        
        # 準備寬表格 (Wide Format) 用於向量化計算
        # Index: Date, Columns: StockID
        self.logger.info("準備向量化資料結構...")
        self.pivots = {}
        for col in ['open', 'high', 'low', 'close', 'volume', 'foreign_buy', 'trust_buy', 'dealer_buy']:
            if col in self.df.columns:
                self.pivots[col] = self.df.pivot(index='date', columns='stock_id', values=col)

    def _merge_indicator(self, indicator_df: pd.DataFrame, name: str):
        """
        將計算好的寬表格指標合併回原始長表格
        
        Args:
            indicator_df: 寬表格指標 (Index: Date, Columns: StockID)
            name: 指標名稱
        """
        # Melt 回長表格
        melted = indicator_df.melt(ignore_index=False, var_name='stock_id', value_name=name).reset_index()
        
        # 合併回 self.df
        # 注意: 這裡假設 self.df 與 melted 的 keys (date, stock_id) 是完全對齊的
        # 為了效能，我們使用 set_index 後的賦值，避免昂貴的 merge
        if 'date' in self.df.columns and 'stock_id' in self.df.columns:
            self.df = self.df.set_index(['date', 'stock_id'])
            melted = melted.set_index(['date', 'stock_id'])
            self.df[name] = melted[name]
            self.df = self.df.reset_index()
        else:
            # Fallback
            self.df = self.df.merge(melted, on=['date', 'stock_id'], how='left')

    def calculate_all_indicators(self) -> pd.DataFrame:
        """一次計算所有技術指標"""
        self.logger.info("開始計算所有技術指標 (Vectorized)...")
        
        self.calculate_ma()
        self.calculate_ema()
        self.calculate_macd()
        self.calculate_rsi()
        self.calculate_kd()
        self.calculate_bollinger_bands()
        self.calculate_breakout_flag()
        self.calculate_volume_spike()
        self.calculate_position_indicators()
        self.calculate_ma_squeeze()
        self.calculate_bias_ratio()
        self.calculate_revenue_factors()
        self.calculate_institutional_indicators()
        
        # 計算二元事件
        self.calculate_binary_events()
        # 計算價格型態訊號，讓模型、排名與 K 線 UI 共用同一份欄位。
        self.calculate_candlestick_patterns()
        self.calculate_td_sequential()
        self.calculate_price_patterns()
        
        self.logger.info("所有技術指標計算完成！")
        return self.df
    
    def get_missing_rate(self) -> pd.Series:
        """計算各欄位缺值率"""
        missing_rate = (self.df.isnull().sum() / len(self.df) * 100).round(2)
        return missing_rate.sort_values(ascending=False)
