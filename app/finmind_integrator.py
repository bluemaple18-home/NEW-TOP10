import logging

import pandas as pd

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
        
    def integrate_chip_data(self, df: pd.DataFrame, top_n: int = 200, include_margin: bool = True) -> pd.DataFrame:
        """
        將籌碼資料整合進輸入的 DataFrame。

        注意：缺資料不可直接視為 0。整合後會保留 coverage flag，
        後續 warning / shadow feature 必須搭配 *_available 判斷。

        Args:
            top_n: 僅連動成交值最高的前 N 檔股票 (避免 API 制限)
            include_margin: 是否同時抓取融資融券資料
        """
        if self.fetcher is None:
            logger.warning("FinMind 套件不可用，跳過籌碼資料整合: %s", FINMIND_IMPORT_ERROR)
            return df

        if df.empty:
            return df

        working = df.copy()
        working["date"] = pd.to_datetime(working["date"])
        working["stock_id"] = working["stock_id"].astype(str).str.strip()

        # 依成交金額排序，優先抓取流動性好的股票，控制 API 成本。
        avg_value = df.groupby('stock_id')['volume'].mean() * df.groupby('stock_id')['close'].mean()
        top_stocks = [str(stock_id).strip() for stock_id in avg_value.sort_values(ascending=False).head(top_n).index.tolist()]
        
        logger.info("開始整合籌碼面資料，優先抓取成交額前 %s 名股票", top_n)
        
        start_date = working['date'].min().strftime('%Y-%m-%d')
        end_date = working['date'].max().strftime('%Y-%m-%d')

        institutional = self._load_institutional_frames(top_stocks, start_date, end_date)
        if not institutional.empty:
            working = working.merge(institutional, on=["date", "stock_id"], how="left")
            working["institutional_available"] = working["institutional_available"].fillna(False).astype(bool)
        else:
            logger.warning("未能獲取任何三大法人資料")

        if include_margin:
            margin = self._load_margin_frames(top_stocks, start_date, end_date)
            if not margin.empty:
                working = working.merge(margin, on=["date", "stock_id"], how="left")
                working["margin_available"] = working["margin_available"].fillna(False).astype(bool)
            else:
                logger.warning("未能獲取任何融資融券資料")

        coverage = {}
        if "institutional_available" in working.columns:
            coverage["institutional"] = float(working["institutional_available"].mean())
        if "margin_available" in working.columns:
            coverage["margin"] = float(working["margin_available"].mean())
        logger.info("籌碼面資料整合完成，coverage=%s", coverage)
        return working

    def _load_institutional_frames(self, stock_ids: list[str], start_date: str, end_date: str) -> pd.DataFrame:
        frames: list[pd.DataFrame] = []
        for index, stock_id in enumerate(stock_ids):
            if index % 100 == 0:
                logger.info("三大法人進度: %s/%s", index, len(stock_ids))
            raw = self.fetcher.get_institutional_investors(stock_id, start_date, end_date)
            normalized = self._normalize_institutional(raw, stock_id)
            if not normalized.empty:
                frames.append(normalized)
        if not frames:
            return pd.DataFrame()
        combined = pd.concat(frames, ignore_index=True)
        return combined.drop_duplicates(subset=["date", "stock_id"], keep="last")

    def _normalize_institutional(self, raw: pd.DataFrame, stock_id: str) -> pd.DataFrame:
        if raw.empty:
            return pd.DataFrame()
        required = {"date", "buy", "sell", "name"}
        if not required.issubset(raw.columns):
            logger.warning("三大法人資料欄位不完整 stock_id=%s columns=%s", stock_id, list(raw.columns))
            return pd.DataFrame()

        frame = raw.copy()
        frame["date"] = pd.to_datetime(frame["date"])
        frame["net_buy"] = pd.to_numeric(frame["buy"], errors="coerce").fillna(0) - pd.to_numeric(frame["sell"], errors="coerce").fillna(0)
        pivoted = frame.pivot_table(index="date", columns="name", values="net_buy", aggfunc="sum").reset_index()
        pivoted = pivoted.rename(columns={"Foreign_Investor": "foreign_buy", "Investment_Trust": "trust_buy"})
        dealer_cols = [col for col in pivoted.columns if "Dealer" in str(col)]
        pivoted["dealer_buy"] = pivoted[dealer_cols].sum(axis=1) if dealer_cols else 0
        for col in ["foreign_buy", "trust_buy", "dealer_buy"]:
            if col not in pivoted.columns:
                pivoted[col] = 0
        pivoted["stock_id"] = stock_id
        pivoted["institutional_available"] = True
        return pivoted[["date", "stock_id", "foreign_buy", "trust_buy", "dealer_buy", "institutional_available"]]

    def _load_margin_frames(self, stock_ids: list[str], start_date: str, end_date: str) -> pd.DataFrame:
        frames: list[pd.DataFrame] = []
        for index, stock_id in enumerate(stock_ids):
            if index % 100 == 0:
                logger.info("融資融券進度: %s/%s", index, len(stock_ids))
            raw = self.fetcher.get_margin_purchase_short_sale(stock_id, start_date, end_date)
            normalized = self._normalize_margin(raw, stock_id)
            if not normalized.empty:
                frames.append(normalized)
        if not frames:
            return pd.DataFrame()
        combined = pd.concat(frames, ignore_index=True)
        return combined.drop_duplicates(subset=["date", "stock_id"], keep="last")

    def _normalize_margin(self, raw: pd.DataFrame, stock_id: str) -> pd.DataFrame:
        if raw.empty:
            return pd.DataFrame()
        if "date" not in raw.columns:
            logger.warning("融資融券資料缺少 date stock_id=%s columns=%s", stock_id, list(raw.columns))
            return pd.DataFrame()

        frame = raw.copy()
        frame["date"] = pd.to_datetime(frame["date"])
        output = pd.DataFrame({"date": frame["date"], "stock_id": stock_id})
        source_map = {
            "margin_purchase_buy": "MarginPurchaseBuy",
            "margin_purchase_sell": "MarginPurchaseSell",
            "margin_purchase_cash_repayment": "MarginPurchaseCashRepayment",
            "margin_purchase_today_balance": "MarginPurchaseTodayBalance",
            "margin_purchase_yesterday_balance": "MarginPurchaseYesterdayBalance",
            "short_sale_buy": "ShortSaleBuy",
            "short_sale_sell": "ShortSaleSell",
            "short_sale_cash_repayment": "ShortSaleCashRepayment",
            "short_sale_today_balance": "ShortSaleTodayBalance",
            "short_sale_yesterday_balance": "ShortSaleYesterdayBalance",
        }
        for target, source in source_map.items():
            if source in frame.columns:
                output[target] = pd.to_numeric(frame[source], errors="coerce")
            else:
                output[target] = pd.NA

        output["margin_purchase_balance_change"] = (
            output["margin_purchase_today_balance"] - output["margin_purchase_yesterday_balance"]
        )
        output["short_sale_balance_change"] = output["short_sale_today_balance"] - output["short_sale_yesterday_balance"]
        output["margin_available"] = True
        return output
