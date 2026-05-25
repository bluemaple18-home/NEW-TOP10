
"""
Pattern Indicators Mixin
Breakout, Position, Revenue Factors, Binary Events
"""
import pandas as pd
import numpy as np
from app.signals import add_candlestick_patterns, add_price_patterns, add_td_sequential

class PatternIndicatorsMixin:
    def calculate_candlestick_patterns(self) -> pd.DataFrame:
        """計算 K 線型態，包含十字星、吞噬、晨星等。"""
        self.logger.info("計算 K 線型態訊號")
        self.df = add_candlestick_patterns(self.df)
        return self.df

    def calculate_td_sequential(self) -> pd.DataFrame:
        """計算 TD Sequential 九轉。"""
        self.logger.info("計算 TD 九轉訊號")
        self.df = add_td_sequential(self.df)
        return self.df

    def calculate_price_patterns(self) -> pd.DataFrame:
        """計算 W 底 / M 頭等大型價格結構。"""
        self.logger.info("計算 W 底 / M 頭價格結構訊號")
        self.df = add_price_patterns(self.df)
        return self.df

    def calculate_breakout_flag(self, lookback_period: int = 60) -> pd.DataFrame:
        """計算前高突破旗標 - 向量化"""
        self.logger.info(f"計算前高突破旗標 (Vectorized, 回溯={lookback_period})")
        
        close = self.pivots['close']
        high = self.pivots['high']
        
        # 過去 N 日最高價 (不含今日) -> shift(1)
        rolling_max = high.shift(1).rolling(window=lookback_period).max()
        
        breakout = (close > rolling_max).astype(int)
        
        self._merge_indicator(breakout, 'breakout_flag')
        
        return self.df
    
    def calculate_position_indicators(self, periods: list = [60, 250]) -> pd.DataFrame:
        """
        計算相對位階指標 (受 StockSniper 啟發)
        """
        self.logger.info(f"計算位階指標 (Vectorized): {periods}天回溯")
        
        close = self.pivots['close']
        high = self.pivots['high']
        low = self.pivots['low']
        
        for period in periods:
            # 計算滾動高低點
            rolling_high = high.rolling(window=period).max()
            rolling_low = low.rolling(window=period).min()
            
            # 距高點百分比 (負數代表低於高點)
            pct_from_high = ((close - rolling_high) / rolling_high) * 100
            self._merge_indicator(pct_from_high, f'pct_from_high_{period}d')
            
            # 距低點百分比 (正數代表高於低點)
            pct_from_low = ((close - rolling_low) / rolling_low) * 100
            self._merge_indicator(pct_from_low, f'pct_from_low_{period}d')
            
            # 相對位置 (0-1之間，0=低點，1=高點)
            range_val = rolling_high - rolling_low
            relative_position = (close - rolling_low) / range_val
            relative_position = relative_position.clip(0, 1)  # 防止除0或異常值
            self._merge_indicator(relative_position, f'relative_position_{period}d')
        
        return self.df

    def calculate_revenue_factors(self) -> pd.DataFrame:
        """
        計算基礎基本面因子
        """
        # 檢查是否有營收資料
        if 'revenue' not in self.pivots:
            # 嘗試從 columns 找
            if 'revenue' in self.df.columns:
                 self.pivots['revenue'] = self.df.pivot(index='date', columns='stock_id', values='revenue')
            else:
                self.logger.warning("無營收資料，跳過基本面因子計算")
                return self.df
                
        self.logger.info("計算基本面因子 (Vectorized)")
        revenue = self.pivots['revenue']
        
        # 營收動能: 近 3 月平均營收 / 近 12 月最大營收
        rev_ma3 = revenue.rolling(window=3).mean()
        rev_max12 = revenue.rolling(window=12).max()
        
        rev_momentum = rev_ma3 / rev_max12
        
        self._merge_indicator(rev_momentum, 'revenue_momentum')
        return self.df
    
    def calculate_binary_events(self) -> pd.DataFrame:
        """計算二元事件特徵 (Binary Events) 供模型與解釋使用"""
        self.logger.info("計算二元事件特徵 (Vectorized)")
        
        # 基本欄位引用
        close = self.pivots['close']
        open_ = self.pivots['open']
        high = self.pivots['high']
        low = self.pivots['low']
        volume = self.pivots['volume']
        
        # 1. 突破近 20 日新高 (break_20d_high)
        rolling_max_20 = high.shift(1).rolling(window=20).max()
        self._merge_indicator((close > rolling_max_20).astype(int), 'break_20d_high')

        # 2. MA5 上穿 MA20 (ma5_cross_ma20_up)
        # 需確保 MA 已計算
        if 'ma5' not in self.pivots or 'ma20' not in self.pivots:
            self.calculate_ma([5, 20])
        ma5 = self.df.pivot(index='date', columns='stock_id', values='ma5')
        ma20 = self.df.pivot(index='date', columns='stock_id', values='ma20')
        
        cross_up = (ma5 > ma20) & (ma5.shift(1) <= ma20.shift(1))
        self._merge_indicator(cross_up.astype(int), 'ma5_cross_ma20_up')
        
        cross_down = (ma5 < ma20) & (ma5.shift(1) >= ma20.shift(1))
        self._merge_indicator(cross_down.astype(int), 'ma5_cross_ma20_down')

        # 3. 收盤站上布林中軌 (close_above_bb_mid)
        mid = ma20
        above_mid = (close > mid) & (close.shift(1) <= mid.shift(1))
        self._merge_indicator(above_mid.astype(int), 'close_above_bb_mid')
        
        below_mid = (close < mid) & (close.shift(1) >= mid.shift(1))
        self._merge_indicator(below_mid.astype(int), 'close_below_bb_mid')

        # 4. MACD 金叉/死叉
        if 'macd' not in self.pivots or 'macd_signal' not in self.pivots:
            self.calculate_macd()
        dif = self.df.pivot(index='date', columns='stock_id', values='macd')
        dem = self.df.pivot(index='date', columns='stock_id', values='macd_signal')
        
        macd_bull = (dif > dem) & (dif.shift(1) <= dem.shift(1))
        macd_bear = (dif < dem) & (dif.shift(1) >= dem.shift(1))
        self._merge_indicator(macd_bull.astype(int), 'macd_bullish_cross')
        self._merge_indicator(macd_bear.astype(int), 'macd_bearish_cross')

        # 5. RSI 反彈 (rsi_rebound_from_40)
        if 'rsi' not in self.pivots:
            self.calculate_rsi()
        rsi = self.df.pivot(index='date', columns='stock_id', values='rsi')
        
        rsi_rebound = (rsi > 40) & (rsi.shift(1) <= 40)
        self._merge_indicator(rsi_rebound.astype(int), 'rsi_rebound_from_40')
        
        rsi_weak = (rsi < 50) & (rsi.shift(1) >= 50)
        self._merge_indicator(rsi_weak.astype(int), 'rsi_break_below_50')

        # 6. 量能突增 (volume_spike) > 20日均量 1.5倍
        vol_ma20 = volume.rolling(window=20).mean()
        vol_spike = (volume > (vol_ma20 * 1.5)).astype(int)
        self._merge_indicator(vol_spike, 'volume_spike_1.5x') 

        # 7. 跳空強勢 (gap_up_close_strong)
        gap_up = (open_ > high.shift(1)) & (close > open_)
        self._merge_indicator(gap_up.astype(int), 'gap_up_close_strong')

        # 8. 長上影線 (long_upper_shadow)
        body = (close - open_).abs()
        upper_shadow = high - np.maximum(close, open_)
        long_shadow = (upper_shadow > body * 2) & (upper_shadow > close * 0.005)
        self._merge_indicator(long_shadow.astype(int), 'long_upper_shadow')
        
        return self.df
