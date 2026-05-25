"""
量能指標計算模組
計算成交量相關的技術指標
"""

import pandas as pd
import numpy as np
from ta.volume import OnBalanceVolumeIndicator
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class VolumeIndicators:
    """量能指標計算器"""
    
    def __init__(self, df: pd.DataFrame):
        """
        初始化量能指標計算器
        
        Args:
            df: 必須包含 date, stock_id, close, volume 欄位
        """
        self.df = df.copy()
        self.df = self.df.sort_values(['stock_id', 'date']).reset_index(drop=True)
    
    def calculate_avg_volume(self, periods: list = [5, 10, 20]) -> pd.DataFrame:
        """
        計算平均成交量
        
        Args:
            periods: 週期列表
            
        Returns:
            新增平均成交量欄位的 DataFrame
        """
        logger.info(f"計算平均成交量: {periods}")
        
        result_dfs = []
        
        for stock_id, group in self.df.groupby('stock_id'):
            group = group.sort_values('date').reset_index(drop=True)
            
            for period in periods:
                group[f'avg_volume_{period}d'] = group['volume'].rolling(window=period).mean()
            
            result_dfs.append(group)
        
        self.df = pd.concat(result_dfs, ignore_index=True)
        logger.info("平均成交量計算完成")
        return self.df
    
    def calculate_volume_ratio(self, periods: list = [5, 10, 20]) -> pd.DataFrame:
        """
        計算量比（當日量 / N 日平均量）
        
        Args:
            periods: 週期列表
            
        Returns:
            新增量比欄位的 DataFrame
        """
        logger.info(f"計算量比: {periods}")
        
        # 先確保已計算平均成交量
        if f'avg_volume_{periods[0]}d' not in self.df.columns:
            self.calculate_avg_volume(periods)
        
        for period in periods:
            avg_col = f'avg_volume_{period}d'
            ratio_col = f'volume_ratio_{period}d'
            
            self.df[ratio_col] = (self.df['volume'] / self.df[avg_col]).round(2)
            
            # 處理除以零的情況
            self.df[ratio_col] = self.df[ratio_col].replace([np.inf, -np.inf], np.nan)
        
        logger.info("量比計算完成")
        return self.df
    
    def calculate_obv(self) -> pd.DataFrame:
        """
        計算 OBV（能量潮指標）
        
        Returns:
            新增 OBV 欄位的 DataFrame
        """
        logger.info("計算 OBV 指標")
        
        result_dfs = []
        
        for stock_id, group in self.df.groupby('stock_id'):
            group = group.sort_values('date').reset_index(drop=True)
            
            obv_indicator = OnBalanceVolumeIndicator(
                close=group['close'],
                volume=group['volume']
            )
            
            group['obv'] = obv_indicator.on_balance_volume()
            
            result_dfs.append(group)
        
        self.df = pd.concat(result_dfs, ignore_index=True)
        logger.info("OBV 指標計算完成")
        return self.df
    
    def calculate_avg_trading_value(self, period: int = 20) -> pd.DataFrame:
        """
        計算日均成交值（價 × 量）
        
        Args:
            period: 計算週期（預設 20 日）
            
        Returns:
            新增日均成交值欄位的 DataFrame
        """
        logger.info(f"計算 {period} 日日均成交值")
        
        result_dfs = []
        
        for stock_id, group in self.df.groupby('stock_id'):
            group = group.sort_values('date').reset_index(drop=True)
            
            # 計算每日成交值（收盤價 × 成交量）
            group['daily_value'] = group['close'] * group['volume']
            
            # 計算 N 日平均成交值
            group[f'avg_value_{period}d'] = group['daily_value'].rolling(window=period).mean()
            
            # 移除暫存欄位
            group = group.drop(columns=['daily_value'])
            
            result_dfs.append(group)
        
        self.df = pd.concat(result_dfs, ignore_index=True)
        logger.info("日均成交值計算完成")
        return self.df
    
    def calculate_all_volume_indicators(self) -> pd.DataFrame:
        """
        一次計算所有量能指標
        
        Returns:
            包含所有量能指標的 DataFrame
        """
        logger.info("開始計算所有量能指標...")
        
        self.calculate_avg_volume(periods=[5, 10, 20])
        self.calculate_volume_ratio(periods=[5, 10, 20])
        self.calculate_obv()
        self.calculate_avg_trading_value(period=20)
        
        logger.info("所有量能指標計算完成！")
        return self.df
    
    def get_missing_rate(self) -> pd.Series:
        """
        計算各欄位缺值率
        
        Returns:
            缺值率 Series
        """
        missing_rate = (self.df.isnull().sum() / len(self.df) * 100).round(2)
        return missing_rate.sort_values(ascending=False)


if __name__ == "__main__":
    # 測試範例
    from pathlib import Path
    
    test_file = Path("data/clean/features_with_indicators.parquet")
    
    if test_file.exists():
        print(f"載入測試資料: {test_file}")
        
        df = pd.read_parquet(test_file)
        print(f"原始資料: {len(df)} 筆")
        
        # 計算量能指標
        vol_ind = VolumeIndicators(df)
        result = vol_ind.calculate_all_volume_indicators()
        
        print(f"\n新增欄位:")
        new_cols = [col for col in result.columns if 'volume' in col.lower() or 'obv' in col.lower() or 'value' in col.lower()]
        print(new_cols)
        
        print(f"\n缺值率:")
        print(vol_ind.get_missing_rate().head(10))
        
        # 儲存結果
        output_path = Path("data/clean") / "features_with_all_indicators.parquet"
        result.to_parquet(output_path, index=False)
        print(f"\n結果已儲存至: {output_path}")
    else:
        print(f"請先執行 indicators.py 產生 {test_file}")
