
"""
Momentum Indicators Mixin
MACD, RSI, KD
"""
import pandas as pd
import numpy as np

class MomentumIndicatorsMixin:
    def calculate_macd(self, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
        """計算 MACD 指標 - 向量化"""
        self.logger.info("計算 MACD 指標 (Vectorized)")
        
        close = self.pivots['close']
        
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        
        dif = ema_fast - ema_slow
        dem = dif.ewm(span=signal, adjust=False).mean()
        osc = dif - dem
        
        self._merge_indicator(dif, 'macd')
        self._merge_indicator(dem, 'macd_signal')
        self._merge_indicator(osc, 'macd_hist')
        
        return self.df
    
    def calculate_rsi(self, period: int = 14) -> pd.DataFrame:
        """計算 RSI 指標 (Wilder's Smoothing) - 向量化"""
        self.logger.info(f"計算 RSI 指標 (Vectorized, 週期={period})")
        
        close = self.pivots['close']
        delta = close.diff()
        
        # 分離漲跌
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        
        # Wilder's Smoothing
        # First value is SMA, subsequent are (prev * (n-1) + curr) / n
        # This is equivalent to ewm(alpha=1/n, adjust=False)
        avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        self._merge_indicator(rsi, 'rsi')
        
        return self.df
    
    def calculate_kd(self, k_period: int = 9, d_period: int = 3, smooth_k: int = 3) -> pd.DataFrame:
        """計算 KD 指標 - 向量化"""
        self.logger.info("計算 KD 指標 (Vectorized)")
        
        close = self.pivots['close']
        high = self.pivots['high']
        low = self.pivots['low']
        
        # RSV
        low_min = low.rolling(window=k_period).min()
        high_max = high.rolling(window=k_period).max()
        rsv = 100 * (close - low_min) / (high_max - low_min)
        
        # K = 2/3 * Prev_K + 1/3 * RSV
        k = rsv.ewm(alpha=1/3, adjust=False).mean()
        d = k.ewm(alpha=1/3, adjust=False).mean()
        
        self._merge_indicator(k, 'k')
        self._merge_indicator(d, 'd')
        
        return self.df
