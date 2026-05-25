
"""
Trend Indicators Mixin
MA, EMA, MA Squeeze, Bias Ratio
"""
import pandas as pd
import numpy as np

class TrendIndicatorsMixin:
    def calculate_ma(self, periods: list = [5, 10, 20, 60]) -> pd.DataFrame:
        """計算移動平均線 (MA) - 向量化"""
        self.logger.info(f"計算移動平均線 (Vectorized): {periods}")
        
        close = self.pivots['close']
        
        for period in periods:
            # 直接對整個寬表格做 rolling mean
            ma = close.rolling(window=period).mean()
            self._merge_indicator(ma, f'ma{period}')
            
        return self.df
    
    def calculate_ema(self, periods: list = [12, 26]) -> pd.DataFrame:
        """計算指數移動平均線 (EMA) - 向量化"""
        self.logger.info(f"計算指數移動平均線 (Vectorized): {periods}")
        
        close = self.pivots['close']
        
        for period in periods:
            ema = close.ewm(span=period, adjust=False).mean()
            self._merge_indicator(ema, f'ema{period}')
            
        return self.df

    def calculate_ma_squeeze(self, periods: list = [5, 10, 20, 60]) -> pd.DataFrame:
        """計算均線糾結指標 (各均線間的最大差距)"""
        self.logger.info(f"計算均線糾結指標 (Vectorized): {periods}")
        
        ma_cols = [f'ma{p}' for p in periods]
        # 確保這些 MA 已經計算過
        for col in ma_cols:
            if col not in self.df.columns:
                self.calculate_ma([int(col[2:])])
        
        # 提取這些 MA 欄位並轉為寬表格
        ma_pivots = [self.df.pivot(index='date', columns='stock_id', values=col) for col in ma_cols]
        
        # 計算最大值與最小值之差 / 平均值
        ma_stack = np.stack(ma_pivots)
        ma_max = np.max(ma_stack, axis=0)
        ma_min = np.min(ma_stack, axis=0)
        ma_avg = np.mean(ma_stack, axis=0)
        
        squeeze = (ma_max - ma_min) / ma_avg
        self._merge_indicator(pd.DataFrame(squeeze, index=ma_pivots[0].index, columns=ma_pivots[0].columns), 'ma_squeeze')
        
        return self.df

    def calculate_bias_ratio(self, periods: list = [5, 10, 20, 60]) -> pd.DataFrame:
        """計算乖離率 (Bias Ratio)"""
        self.logger.info(f"計算乖離率 (Vectorized): {periods}")
        
        close = self.pivots['close']
        for period in periods:
            ma_col = f'ma{period}'
            if ma_col not in self.df.columns:
                self.calculate_ma([period])
            
            ma = self.df.pivot(index='date', columns='stock_id', values=ma_col)
            bias = (close - ma) / ma
            self._merge_indicator(bias, f'bias_{period}')
            
        return self.df
