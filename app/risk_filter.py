"""
風險過濾模組
實作多層風險過濾機制
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class RiskFilter:
    """風險過濾器"""
    
    def __init__(self, df: pd.DataFrame):
        """
        初始化風險過濾器
        
        Args:
            df: 包含完整特徵的 DataFrame
        """
        self.df = df.copy()
        self.filter_stats = {}  # 記錄每個過濾階段的統計
        
        # 記錄初始狀態
        self.filter_stats['initial'] = {
            'total_records': len(self.df),
            'unique_stocks': self.df['stock_id'].nunique()
        }
    
    def filter_suspended_stocks(self, suspended_list: list) -> pd.DataFrame:
        """
        過濾處置股與全額交割股
        
        Args:
            suspended_list: 處置股票代碼清單
            
        Returns:
            過濾後的 DataFrame
        """
        logger.info("過濾處置股與全額交割股")
        
        initial_count = len(self.df)
        initial_stocks = self.df['stock_id'].nunique()
        
        # 移除處置股
        self.df = self.df[~self.df['stock_id'].isin(suspended_list)]
        
        removed_count = initial_count - len(self.df)
        removed_stocks = initial_stocks - self.df['stock_id'].nunique()
        
        self.filter_stats['suspended'] = {
            'removed_records': removed_count,
            'removed_stocks': removed_stocks,
            'remaining_records': len(self.df),
            'remaining_stocks': self.df['stock_id'].nunique()
        }
        
        logger.info(f"移除 {removed_stocks} 檔處置股，剩餘 {self.df['stock_id'].nunique()} 檔")
        return self.df
    
    def filter_listing_days(self, min_days: int = 60, reference_date: str = None) -> pd.DataFrame:
        """
        過濾上市未滿指定天數的股票
        
        Args:
            min_days: 最少上市天數（預設 60）
            reference_date: 參考日期（預設為資料中最新日期）
            
        Returns:
            過濾後的 DataFrame
        """
        logger.info(f"過濾上市未滿 {min_days} 日的股票")
        
        initial_stocks = self.df['stock_id'].nunique()
        
        if reference_date is None:
            reference_date = self.df['date'].max()
        else:
            reference_date = pd.to_datetime(reference_date)
        
        # 計算每檔股票的最早交易日
        first_trading_date = self.df.groupby('stock_id')['date'].min()
        
        # 計算上市天數
        listing_days = (reference_date - first_trading_date).dt.days
        
        # 找出上市滿 min_days 的股票
        valid_stocks = listing_days[listing_days >= min_days].index.tolist()
        
        # 過濾
        self.df = self.df[self.df['stock_id'].isin(valid_stocks)]
        
        removed_stocks = initial_stocks - self.df['stock_id'].nunique()
        
        self.filter_stats['listing_days'] = {
            'min_days': min_days,
            'removed_stocks': removed_stocks,
            'remaining_stocks': self.df['stock_id'].nunique()
        }
        
        logger.info(f"移除 {removed_stocks} 檔上市未滿 {min_days} 日股票，剩餘 {self.df['stock_id'].nunique()} 檔")
        return self.df
    
    def filter_liquidity(self, min_avg_value: float = 10_000_000, period: int = 20) -> pd.DataFrame:
        """
        過濾近 N 日日均成交值低於門檻的股票
        
        Args:
            min_avg_value: 最低日均成交值（預設 1000 萬）
            period: 計算期間（預設 20 日）
            
        Returns:
            過濾後的 DataFrame
        """
        logger.info(f"過濾近 {period} 日日均成交值 < {min_avg_value:,.0f} 的股票")
        
        initial_stocks = self.df['stock_id'].nunique()
        
        avg_value_col = f'avg_value_{period}d'
        
        if avg_value_col not in self.df.columns:
            logger.warning(f"找不到 {avg_value_col} 欄位，跳過流動性過濾")
            return self.df
        
        # 取得每檔股票最新的日均成交值
        latest_data = self.df.sort_values('date').groupby('stock_id').tail(1)
        valid_stocks = latest_data[latest_data[avg_value_col] >= min_avg_value]['stock_id'].tolist()
        
        # 過濾
        self.df = self.df[self.df['stock_id'].isin(valid_stocks)]
        
        removed_stocks = initial_stocks - self.df['stock_id'].nunique()
        
        self.filter_stats['liquidity'] = {
            'min_avg_value': min_avg_value,
            'period': period,
            'removed_stocks': removed_stocks,
            'remaining_stocks': self.df['stock_id'].nunique()
        }
        
        logger.info(f"移除 {removed_stocks} 檔低流動性股票，剩餘 {self.df['stock_id'].nunique()} 檔")
        return self.df
    
    def filter_price(self, min_price: float = 10.0) -> pd.DataFrame:
        """
        過濾股價低於門檻的股票
        
        Args:
            min_price: 最低股價（預設 10 元）
            
        Returns:
            過濾後的 DataFrame
        """
        logger.info(f"過濾股價 < {min_price} 元的股票")
        
        initial_stocks = self.df['stock_id'].nunique()
        
        # 取得每檔股票最新的股價
        latest_data = self.df.sort_values('date').groupby('stock_id').tail(1)
        valid_stocks = latest_data[latest_data['close'] >= min_price]['stock_id'].tolist()
        
        # 過濾
        self.df = self.df[self.df['stock_id'].isin(valid_stocks)]
        
        removed_stocks = initial_stocks - self.df['stock_id'].nunique()
        
        self.filter_stats['price'] = {
            'min_price': min_price,
            'removed_stocks': removed_stocks,
            'remaining_stocks': self.df['stock_id'].nunique()
        }
        
        logger.info(f"移除 {removed_stocks} 檔低價股，剩餘 {self.df['stock_id'].nunique()} 檔")
        return self.df
    
    def apply_all_filters(
        self,
        suspended_list: list = None,
        min_listing_days: int = 60,
        min_avg_value: float = 10_000_000,
        min_price: float = 10.0
    ) -> pd.DataFrame:
        """
        套用所有風險過濾條件
        
        Args:
            suspended_list: 處置股清單
            min_listing_days: 最少上市天數
            min_avg_value: 最低日均成交值
            min_price: 最低股價
            
        Returns:
            過濾後的 DataFrame（universe）
        """
        logger.info("開始套用所有風險過濾條件...")
        
        # 1. 處置股過濾
        if suspended_list:
            self.filter_suspended_stocks(suspended_list)
        
        # 2. 上市天數過濾
        self.filter_listing_days(min_days=min_listing_days)
        
        # 3. 流動性過濾
        self.filter_liquidity(min_avg_value=min_avg_value)
        
        # 4. 價格過濾
        self.filter_price(min_price=min_price)
        
        logger.info(f"風險過濾完成！最終股票池: {self.df['stock_id'].nunique()} 檔")
        return self.df
    
    def get_filter_report(self) -> pd.DataFrame:
        """
        產生過濾統計報告
        
        Returns:
            過濾統計 DataFrame
        """
        report_data = []
        
        for stage, stats in self.filter_stats.items():
            report_data.append({
                'stage': stage,
                **stats
            })
        
        return pd.DataFrame(report_data)
    
    def get_data(self) -> pd.DataFrame:
        """取得過濾後的資料"""
        return self.df


if __name__ == "__main__":
    # 測試範例
    test_file = Path("data/clean/features_with_fundamental.parquet")
    
    if test_file.exists():
        print(f"載入測試資料: {test_file}")
        df = pd.read_parquet(test_file)
        
        print(f"原始資料: {len(df)} 筆, {df['stock_id'].nunique()} 檔股票")
        
        # 載入處置股清單（如果存在）
        suspended_file = Path("data/raw/suspended_stocks.txt")
        suspended_list = []
        if suspended_file.exists():
            with open(suspended_file, 'r') as f:
                suspended_list = [line.strip() for line in f.readlines()]
            print(f"處置股清單: {len(suspended_list)} 檔")
        
        # 套用風險過濾
        risk_filter = RiskFilter(df)
        universe = risk_filter.apply_all_filters(
            suspended_list=suspended_list,
            min_listing_days=60,
            min_avg_value=10_000_000,
            min_price=10.0
        )
        
        print(f"\n過濾後資料: {len(universe)} 筆, {universe['stock_id'].nunique()} 檔股票")
        
        # 過濾統計報告
        print("\n過濾統計:")
        report = risk_filter.get_filter_report()
        print(report)
        
        # 儲存 universe
        output_path = Path("data/clean") / "universe.parquet"
        universe.to_parquet(output_path, index=False)
        print(f"\n股票池已儲存至: {output_path}")
    else:
        print(f"請先執行 fundamental_data.py 產生 {test_file}")
