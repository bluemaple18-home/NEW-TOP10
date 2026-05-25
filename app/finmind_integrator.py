import pandas as pd
import logging
from datetime import datetime, timedelta

try:
    from app.finmind_fetcher import FinMindFetcher
except ImportError as exc:
    FinMindFetcher = None
    FINMIND_IMPORT_ERROR = exc
else:
    FINMIND_IMPORT_ERROR = None

logger = logging.getLogger(__name__)

class FinMindIntegrator:
    """負責將 FinMind 資料與主 Dataframe 進行對齊與合併"""
    
    def __init__(self, token: str = None):
        self.fetcher = FinMindFetcher(token=token) if FinMindFetcher is not None else None
        
    def integrate_chip_data(self, df: pd.DataFrame, top_n: int = 200) -> pd.DataFrame:
        """
        將三大法人籌碼資料整合進輸入的 DataFrame
        Args:
            top_n: 僅連動成交值最高的前 N 檔股票 (避免 API 制限)
        """
        if self.fetcher is None:
            logger.warning("FinMind 套件不可用，跳過籌碼資料整合: %s", FINMIND_IMPORT_ERROR)
            return df

        # 1. 篩選優質股票 (依成交金額排序，優先抓取流動性好的)
        avg_value = df.groupby('stock_id')['volume'].mean() * df.groupby('stock_id')['close'].mean()
        top_stocks = avg_value.sort_values(ascending=False).head(top_n).index.tolist()
        
        logger.info(f"⏳ 開始整合籌碼面資料 (優先抓取成交額前 {top_n} 名股票)...")
        
        start_date = df['date'].min().strftime('%Y-%m-%d')
        end_date = df['date'].max().strftime('%Y-%m-%d')
        
        all_chip_data = []
        
        # 為了效能與 API 限制，僅針對重點股票抓取
        for i, sid in enumerate(top_stocks):
            if i % 100 == 0:
                logger.info(f"  進度: {i}/{len(top_stocks)}")
                
            raw_chip = self.fetcher.get_institutional_investors(sid, start_date, end_date)
            if not raw_chip.empty:
                # 1. 計算淨買賣超
                raw_chip['net_buy'] = raw_chip['buy'] - raw_chip['sell']
                
                # 2. 轉置資料 (Pivot)
                # Index: date, Columns: name, Values: net_buy
                pivoted = raw_chip.pivot_table(index='date', columns='name', values='net_buy', aggfunc='sum').reset_index()
                
                # 3. 欄位對齊與命名
                # FinMind name 可能包含: Foreign_Investor, Investment_Trust, Dealer_Self, Dealer_Hedging
                mapping = {
                    'Foreign_Investor': 'foreign_buy',
                    'Investment_Trust': 'trust_buy'
                }
                # 處理 Dealer (自營商通常拆分為自行買賣與避險)
                dealer_cols = [c for c in pivoted.columns if 'Dealer' in c]
                if dealer_cols:
                    pivoted['dealer_buy'] = pivoted[dealer_cols].sum(axis=1)
                else:
                    pivoted['dealer_buy'] = 0
                
                # 改名
                pivoted = pivoted.rename(columns=mapping)
                
                # 確保必要欄位存在
                for col in ['foreign_buy', 'trust_buy', 'dealer_buy']:
                    if col not in pivoted.columns:
                        pivoted[col] = 0
                
                pivoted['stock_id'] = sid
                all_chip_data.append(pivoted[['date', 'stock_id', 'foreign_buy', 'trust_buy', 'dealer_buy']])
            
        if not all_chip_data:
            logger.warning("⚠️ 未能獲取任何籌碼資料")
            return df
            
        chip_combined = pd.concat(all_chip_data)
        chip_combined['date'] = pd.to_datetime(chip_combined['date'])
        
        # 合併前先去除重複 (如果有)
        chip_combined = chip_combined.drop_duplicates(subset=['date', 'stock_id'])
        
        # 合併回主 DataFrame
        df['date'] = pd.to_datetime(df['date'])
        df_integrated = df.merge(chip_combined, on=['date', 'stock_id'], how='left')
        
        # 填補缺失值 (無資料則視為 0)
        cols_to_fill = ['foreign_buy', 'trust_buy', 'dealer_buy']
        df_integrated[cols_to_fill] = df_integrated[cols_to_fill].fillna(0)
        
        logger.info(f"✅ 籌碼面資料整合完成，覆蓋率: {(df_integrated['foreign_buy'] != 0).sum() / len(df_integrated) * 100:.2f}%")
        return df_integrated
