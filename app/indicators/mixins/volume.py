
"""
Volume Indicators Mixin
Volume Spike, Institutional Indicators
"""
import pandas as pd
import numpy as np

class VolumeIndicatorsMixin:
    def calculate_volume_spike(self, ma_period: int = 20, multiplier: float = 2.0) -> pd.DataFrame:
        """計算量能突增 - 向量化"""
        self.logger.info("計算量能突增 (Vectorized)")
        
        volume = self.pivots['volume']
        vol_ma = volume.rolling(window=ma_period).mean()
        
        spike = (volume > (vol_ma * multiplier)).astype(int)
        
        self._merge_indicator(spike, 'volume_spike')
        return self.df

    def calculate_institutional_indicators(self, periods: list = [3, 5, 10]) -> pd.DataFrame:
        """
        計算籌碼面指標 (三大法人買賣超) - 向量化
        """
        self.logger.info(f"計算籌碼面指標 (Vectorized): {periods}天回溯")
        
        # 確保有法人資料
        required = ['foreign_buy', 'trust_buy', 'dealer_buy']
        if not all(col in self.pivots for col in required):
            self.logger.warning("缺少法人資料，跳過籌碼指標計算")
            return self.df
            
        f_buy = self.pivots['foreign_buy']
        t_buy = self.pivots['trust_buy']
        d_buy = self.pivots['dealer_buy']
        volume = self.pivots['volume']
        
        # 三大法人合計買賣超
        total_inst_buy = f_buy + t_buy + d_buy
        self._merge_indicator(total_inst_buy, 'inst_buy_total')
        
        for p in periods:
            # 1. 累計買賣超佔成交量比例
            # 回溯期間的總買賣超 / 總成交量
            sum_buy = total_inst_buy.rolling(window=p).sum()
            sum_vol = volume.rolling(window=p).sum()
            inst_buy_ratio = sum_buy / sum_vol
            self._merge_indicator(inst_buy_ratio, f'inst_buy_ratio_{p}d')
            
            # 2. 投信連續買超力道 (投信是台股波段關鍵)
            # 標記當日買超為 1
            is_trust_buy = (t_buy > 0).astype(int)
            # 這裡簡化連續天數計算：回溯期間買超天數
            trust_buy_days = is_trust_buy.rolling(window=p).sum()
            self._merge_indicator(trust_buy_days, f'trust_buy_days_{p}d')
            
        return self.df
