
"""
Volatility Indicators Mixin
Bollinger Bands
"""
import pandas as pd
import numpy as np

class VolatilityIndicatorsMixin:
    def calculate_bollinger_bands(self, period: int = 20, std_dev: float = 2.0) -> pd.DataFrame:
        """計算布林通道 - 向量化"""
        self.logger.info(f"計算布林通道 (Vectorized, 週期={period})")
        
        close = self.pivots['close']
        
        ma = close.rolling(window=period).mean()
        std = close.rolling(window=period).std()
        
        upper = ma + (std * std_dev)
        lower = ma - (std * std_dev)
        width = (upper - lower) / ma
        
        self._merge_indicator(upper, 'bb_upper')
        self._merge_indicator(ma, 'bb_middle')
        self._merge_indicator(lower, 'bb_lower')
        self._merge_indicator(width, 'bb_width')
        
        return self.df
