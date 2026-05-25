"""
基本面資料整合模組
整合月營收、EPS、ROE 等基本面資料
"""

import pandas as pd
import numpy as np
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class FundamentalData:
    """基本面資料整合器"""
    
    def __init__(self, df: pd.DataFrame):
        """
        初始化基本面資料整合器
        
        Args:
            df: 技術指標資料 DataFrame
        """
        self.df = df.copy()
    
    def merge_revenue_data(self, revenue_df: pd.DataFrame) -> pd.DataFrame:
        """
        合併月營收資料
        
        Args:
            revenue_df: 月營收 DataFrame，包含 stock_id, year, month, revenue_yoy, revenue_mom
            
        Returns:
            合併後的 DataFrame
        """
        logger.info("合併月營收資料")
        
        if revenue_df is None or revenue_df.empty:
            logger.warning("月營收資料為空，跳過合併")
            self.df['revenue_yoy'] = np.nan
            self.df['revenue_mom'] = np.nan
            return self.df
        
        # 從 date 欄位提取年月
        self.df['year'] = self.df['date'].dt.year
        self.df['month'] = self.df['date'].dt.month
        
        # 合併
        self.df = self.df.merge(
            revenue_df[['stock_id', 'year', 'month', 'revenue_yoy', 'revenue_mom']],
            on=['stock_id', 'year', 'month'],
            how='left'
        )
        
        logger.info("月營收資料合併完成")
        return self.df
    
    def merge_financial_ratios(self, financial_df: pd.DataFrame) -> pd.DataFrame:
        """
        合併財務比率資料（EPS、ROE、毛利率、殖利率）
        
        Args:
            financial_df: 財務比率 DataFrame，包含 stock_id, year, quarter, eps_4q, roe, gross_margin, dividend_yield
            
        Returns:
            合併後的 DataFrame
        """
        logger.info("合併財務比率資料")
        
        if financial_df is None or financial_df.empty:
            logger.warning("財務比率資料為空，跳過合併")
            self.df['eps_4q'] = np.nan
            self.df['roe'] = np.nan
            self.df['gross_margin'] = np.nan
            self.df['dividend_yield'] = np.nan
            return self.df
        
        # 從 date 欄位提取年季
        self.df['year'] = self.df['date'].dt.year
        self.df['quarter'] = self.df['date'].dt.quarter
        
        # 合併
        self.df = self.df.merge(
            financial_df[['stock_id', 'year', 'quarter', 'eps_4q', 'roe', 'gross_margin', 'dividend_yield']],
            on=['stock_id', 'year', 'quarter'],
            how='left'
        )
        
        # 移除暫存欄位
        self.df = self.df.drop(columns=['quarter'], errors='ignore')
        
        logger.info("財務比率資料合併完成")
        return self.df
    
    def create_dummy_fundamental_data(self) -> pd.DataFrame:
        """
        建立虛擬基本面資料（用於測試或當無真實資料時）
        
        Returns:
            包含虛擬基本面資料的 DataFrame
        """
        logger.warning("使用虛擬基本面資料（僅供測試）")
        
        # 產生隨機但合理的虛擬資料
        np.random.seed(42)
        
        self.df['revenue_yoy'] = np.random.uniform(-20, 50, len(self.df))  # -20% ~ 50%
        self.df['revenue_mom'] = np.random.uniform(-30, 30, len(self.df))  # -30% ~ 30%
        self.df['eps_4q'] = np.random.uniform(0, 10, len(self.df))         # 0 ~ 10 元
        self.df['roe'] = np.random.uniform(0, 30, len(self.df))            # 0% ~ 30%
        self.df['gross_margin'] = np.random.uniform(5, 60, len(self.df))   # 5% ~ 60%
        self.df['dividend_yield'] = np.random.uniform(0, 8, len(self.df))  # 0% ~ 8%
        
        # 部分資料設為缺值（模擬真實情況）
        for col in ['revenue_yoy', 'revenue_mom', 'eps_4q', 'roe', 'gross_margin', 'dividend_yield']:
            mask = np.random.random(len(self.df)) < 0.1  # 10% 缺值率
            self.df.loc[mask, col] = np.nan
        
        logger.info("虛擬基本面資料建立完成")
        return self.df
    
    def fetch_revenue_data(self, stock_ids: list = None, months: int = 12) -> pd.DataFrame:
        """
        抓取真實月營收資料（使用台灣證交所 OpenAPI）
        
        Args:
            stock_ids: 股票代號列表（若為 None 則使用 self.df 中的所有股票）
            months: 回溯月數
            
        Returns:
            包含 stock_id, year, month, revenue_yoy, revenue_mom 的 DataFrame
        """
        import requests
        from datetime import datetime, timedelta
        import time
        
        logger.info(f"開始抓取月營收資料（回溯 {months} 個月）")
        
        if stock_ids is None:
            stock_ids = self.df['stock_id'].unique().tolist()
        
        # 使用證交所 OpenAPI
        api_url = "https://openapi.twse.com.tw/v1/opendata/t187ap05_P"
        
        try:
            logger.info("從證交所 OpenAPI 下載營收資料...")
            response = requests.get(api_url, timeout=30)
            response.raise_for_status()
            
            data_json = response.json()
            df_all = pd.DataFrame(data_json)
            
            if df_all.empty:
                logger.warning("API 回傳空資料")
                return pd.DataFrame()
            
            # 欄位對應（根據實際 API 回傳格式調整）
            # 假設API回傳欄位: '公司代號', '資料年月', '去年同期增減(%)', '上月比較增減(%)'
            df_all['stock_id'] = df_all['公司代號'].astype(str).str.strip()
            
            # 解析年月 (通常格式: '11301' -> 2024年1月)
            df_all['年月'] = df_all['資料年月'].astype(str)
            df_all['year'] = (df_all['年月'].str[:3].astype(int) + 1911)
            df_all['month'] = df_all['年月'].str[3:5].astype(int)
            
            # 清理營收成長率數值
            df_all['revenue_yoy'] = pd.to_numeric(df_all['去年同期增減(%)'].replace('-', np.nan), errors='coerce')
            df_all['revenue_mom'] = pd.to_numeric(df_all['上月比較增減(%)'].replace('-', np.nan), errors='coerce')
            
            # 篩選需要的股票與月份
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30 * months)
            
            mask = (
                (df_all['stock_id'].isin(stock_ids)) &
                (df_all['year'] >= start_date.year) &
                (df_all['year'] <= end_date.year)
            )
            
            result = df_all[mask][['stock_id', 'year', 'month', 'revenue_yoy', 'revenue_mom']].copy()
            
            logger.info(f"月營收資料抓取完成，共 {len(result)} 筆")
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API 請求失敗: {e}")
            logger.warning("將使用虛擬營收資料")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"資料解析失敗: {e}")
            logger.warning("將使用虛擬營收資料")
            return pd.DataFrame()
    
    def get_data(self) -> pd.DataFrame:
        """取得處理後的資料"""
        return self.df


if __name__ == "__main__":
    # 測試範例
    test_file = Path("data/clean/features_with_all_indicators.parquet")
    
    if test_file.exists():
        print(f"載入測試資料: {test_file}")
        df = pd.read_parquet(test_file)
        
        # 使用虛擬基本面資料測試
        fundamental = FundamentalData(df)
        result = fundamental.create_dummy_fundamental_data()
        
        print(f"\n新增基本面欄位:")
        fundamental_cols = ['revenue_yoy', 'revenue_mom', 'eps_4q', 'roe', 'gross_margin', 'dividend_yield']
        print(fundamental_cols)
        
        print(f"\n基本面資料統計:")
        print(result[fundamental_cols].describe())
        
        # 儲存
        output_path = Path("data/clean") / "features_with_fundamental.parquet"
        result.to_parquet(output_path, index=False)
        print(f"\n結果已儲存至: {output_path}")
    else:
        print(f"請先執行 volume_indicators.py 產生 {test_file}")
