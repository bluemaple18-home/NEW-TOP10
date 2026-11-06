import pandas as pd
from FinMind.data import DataLoader
from datetime import datetime, timedelta
from pathlib import Path
import time
import logging

logger = logging.getLogger(__name__)

class FinMindFetcher:
    """FinMind 資料抓取器 - 負責獲取籌碼面與基本面資料"""
    
    def __init__(self, token: str = None):
        """
        Args:
            token: FinMind API Token (若無則使用免費版限制)
        """
        self.api = DataLoader(token=token or "")
        if token:
            logger.info("FinMind 已提供 token；有效性以資料端點回應為準")
        else:
            logger.warning("FinMind 未提供 token，使用未登入額度")

    def get_institutional_investors(self, stock_id: str, start_date: str, end_date: str = None):
        """
        獲取三大法人買買超資料
        """
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")
            
        try:
            df = self.api.taiwan_stock_institutional_investors(
                stock_id=stock_id,
                start_date=start_date,
                end_date=end_date
            )
            
            if df.empty:
                return pd.DataFrame()
                
            # 資料轉換與清洗
            # FinMind 回傳包含 外資、投信、自營商 各自的 buy/sell
            # 我們彙整為總買賣超
            df['date'] = pd.to_datetime(df['date'])
            return df
            
        except Exception as exc:
            logger.warning("FinMind 法人擷取失敗 stock_id=%s error_type=%s", stock_id, type(exc).__name__)
            raise RuntimeError(f"FinMind 法人來源擷取失敗：{stock_id} {start_date}..{end_date}") from exc

    def get_margin_purchase_short_sale(self, stock_id: str, start_date: str, end_date: str = None):
        """
        獲取融資融券資料 (籌碼面的反向指標)
        """
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")
        try:
            df = self.api.taiwan_stock_margin_purchase_short_sale(
                stock_id=stock_id,
                start_date=start_date,
                end_date=end_date
            )
            return df
        except Exception as exc:
            logger.warning("FinMind 融資融券擷取失敗 stock_id=%s error_type=%s", stock_id, type(exc).__name__)
            raise RuntimeError(f"FinMind 融資融券來源擷取失敗：{stock_id} {start_date}..{end_date}") from exc

    def get_daily_short_sale_balances(self, stock_id: str, start_date: str, end_date: str = None):
        """
        獲取信用額度總量管制餘額資料。

        這張表包含「借券賣出」餘額，和融券餘額不同；後續用來衡量
        空方借券賣出是否接近發行股數上限。
        """
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")
        try:
            df = self.api.taiwan_daily_short_sale_balances(
                stock_id=stock_id,
                start_date=start_date,
                end_date=end_date
            )
            return df
        except Exception as exc:
            logger.warning("FinMind 借券餘額擷取失敗 stock_id=%s error_type=%s", stock_id, type(exc).__name__)
            raise RuntimeError(f"FinMind 借券餘額來源擷取失敗：{stock_id} {start_date}..{end_date}") from exc

if __name__ == "__main__":
    fetcher = FinMindFetcher()
    # 測試抓取台積電 (2330) 最近 10 天籌碼
    start = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    df = fetcher.get_institutional_investors("2330", start)
    if not df.empty:
        print(f"✅ 成功抓取 2330 籌碼，最新一筆：\n{df.tail(1)}")
    else:
        print("❌ 抓取結果為空")
