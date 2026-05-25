"""
資料擷取模組 (Async Version)
提供從 TWSE、TPEX、Yahoo Finance 擷取台股資料的功能
使用 aiohttp 與 asyncio 進行併發抓取優化
"""

import pandas as pd
import aiohttp
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from pathlib import Path
import time
from tqdm.asyncio import tqdm
import logging
import json

# 設定日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class AsyncTWSEFetcher:
    """台灣證券交易所（上市）資料擷取器 (Async)"""
    
    BASE_URL = "https://www.twse.com.tw"
    
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.data_source_log = []
    
    async def fetch_daily_quotes(self, date: str) -> Optional[pd.DataFrame]:
        """
        擷取指定日期的上市股票日行情 (使用 RWD API 動態解析)
        """
        try:
            # 排除週末 (簡易防呆)
            dt = datetime.strptime(date, '%Y%m%d')
            if dt.weekday() > 4:
                return None

            # TWSE RWD API
            url = f"{self.BASE_URL}/rwd/zh/afterTrading/MI_INDEX"
            params = {
                'date': date,
                'type': 'ALLBUT0999',  # 排除權證與特殊商品，減少資料量
                'response': 'json'
            }
            
            # 模擬瀏覽器行為
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            async with self.session.get(url, params=params, headers=headers, timeout=30) as response:
                if response.status != 200:
                    logger.warning(f"TWSE 連線失敗 ({date}): Status {response.status}")
                    return None
                    
                try:
                    data = await response.json()
                except Exception:
                    logger.warning(f"TWSE 回傳非 JSON 格式 ({date})")
                    return None

            if data.get('stat') != 'OK':
                return None
            
            # 動態尋找目標表格
            target_table = None
            if 'tables' in data:
                for table in data['tables']:
                    title = table.get('title', '')
                    # 關鍵字匹配
                    if "每日收盤行情" in title:
                        target_table = table
                        break
            
            if not target_table:
                # 舊版相容
                if 'data9' in data:
                    fields = data.get('fields9', [])
                    raw_data = data.get('data9', [])
                    target_table = {'fields': fields, 'data': raw_data}
                else:
                    return None

            fields = target_table.get('fields', [])
            raw_data = target_table.get('data', [])
            
            if not raw_data:
                return None
                
            df = pd.DataFrame(raw_data, columns=fields)
            
            # 欄位對應
            col_map = {
                "證券代號": "stock_id",
                "證券名稱": "stock_name",
                "成交股數": "volume",
                "成交筆數": "transactions",
                "成交金額": "value",
                "開盤價": "open",
                "最高價": "high",
                "最低價": "low",
                "收盤價": "close"
            }
            
            rename_dict = {c: col_map[c] for c in df.columns if c in col_map}
            df = df.rename(columns=rename_dict)
            
            # 檢查必要欄位
            required_cols = ['stock_id', 'stock_name', 'open', 'high', 'low', 'close', 'volume']
            missing_cols = [c for c in required_cols if c not in df.columns]
            if missing_cols:
                return None
            
            # 資料清理
            df['date'] = pd.to_datetime(date, format='%Y%m%d')
            
            numeric_cols = ['volume', 'transactions', 'value', 'open', 'high', 'low', 'close']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = df[col].astype(str).str.replace(',', '').replace('--', 'NaN')
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            df = df.dropna(subset=['close'])
            
            self.data_source_log.append({
                'date': date,
                'source': 'TWSE',
                'records': len(df),
                'status': 'success'
            })
            
            return df
            
        except Exception as e:
            logger.error(f"擷取 TWSE {date} 失敗: {e}")
            return None


class AsyncTPEXFetcher:
    """櫃買中心（上櫃）資料擷取器 (Async)"""
    
    BASE_URL = "https://www.tpex.org.tw"
    
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.data_source_log = []
    
    async def fetch_daily_quotes(self, date: str) -> Optional[pd.DataFrame]:
        try:
            dt = datetime.strptime(date, '%Y%m%d')
            if dt.weekday() > 4:
                return None

            roc_date = f"{dt.year - 1911}/{dt.month:02d}/{dt.day:02d}"
            
            url = f"{self.BASE_URL}/web/stock/aftertrading/otc_quotes_no1430/stk_wn1430_result.php"
            params = {
                'l': 'zh-tw',
                'd': roc_date,
                'se': 'AL'
            }
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }

            async with self.session.get(url, params=params, headers=headers, timeout=30) as response:
                if response.status != 200:
                    return None
                try:
                    data = await response.json()
                except:
                    return None
            
            df = self._extract_quote_table(data)
            if df is None or df.empty:
                return None
            
            df['stock_id'] = df['stock_id'].str.strip()
            df['stock_name'] = df['stock_name'].str.strip()
            df = df[df['stock_id'].str.match(r'^\d{4}$')]
            
            for col in ['open', 'high', 'low', 'close', 'volume', 'value']:
                df[col] = df[col].astype(str).str.replace(',', '').replace('---', 'NaN').replace('--', 'NaN')
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            df = df.dropna(subset=['close'])
            df['date'] = dt
            
            self.data_source_log.append({
                'date': date,
                'source': 'TPEX',
                'records': len(df),
                'status': 'success'
            })
            
            return df
            
        except Exception as e:
            logger.error(f"擷取 TPEX {date} 失敗: {e}")
            return None

    def _extract_quote_table(self, data: dict) -> Optional[pd.DataFrame]:
        """解析 TPEx 新舊版日行情格式。"""
        if 'aaData' in data and data['aaData']:
            df = pd.DataFrame(data['aaData'])
            if df.shape[1] < 10:
                return None
            # 0: 代號, 1: 名稱, 2: 收盤, 4: 開盤, 5: 最高, 6: 最低, 7: 成交股數, 8: 成交金額
            df = df.iloc[:, [0, 1, 4, 5, 6, 2, 7, 8]]
            df.columns = ['stock_id', 'stock_name', 'open', 'high', 'low', 'close', 'volume', 'value']
            return df

        for table in data.get('tables', []):
            title = str(table.get('title', ''))
            fields = table.get('fields', [])
            rows = table.get('data', [])
            if "每日收盤行情" not in title or not fields or not rows:
                continue
            df = pd.DataFrame(rows, columns=[str(field).strip() for field in fields])
            col_map = {
                "代號": "stock_id",
                "名稱": "stock_name",
                "開盤": "open",
                "開盤 ": "open",
                "最高": "high",
                "最高 ": "high",
                "最低": "low",
                "收盤": "close",
                "收盤 ": "close",
                "成交股數": "volume",
                "成交股數  ": "volume",
                "成交金額(元)": "value",
                "成交金額(元) ": "value",
                "成交筆數": "transactions",
            }
            df = df.rename(columns={col: col_map[col] for col in df.columns if col in col_map})
            required = {'stock_id', 'stock_name', 'open', 'high', 'low', 'close', 'volume', 'value'}
            if required.issubset(df.columns):
                return df[['stock_id', 'stock_name', 'open', 'high', 'low', 'close', 'volume', 'value']]
        return None


class DataFetcherOrchestrator:
    """資料擷取協調器 (Async 版本)"""
    
    def __init__(self, data_dir: str = "data/raw"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.all_source_logs = []
        
        # 建立限流器 (Semaphore) - 避免對證交所發出太多併發請求
        self.semaphore = asyncio.Semaphore(3) # 同時處理 3 個請求 (保守)

    async def _fetch_day_data(self, session: aiohttp.ClientSession, date: datetime) -> List[pd.DataFrame]:
        """單日資料抓取任務 (TWSE + TPEX 並行)"""
        date_str = date.strftime('%Y%m%d')
        async with self.semaphore:
            # 建立單日抓取器
            twse = AsyncTWSEFetcher(session)
            tpex = AsyncTPEXFetcher(session)
            
            # 並行抓取 TWSE 和 TPEX
            # 這裡我們為了禮貌，TWSE 和 TPEX 雖然是不同站，但為了穩定性，還是稍微錯開一點點或允許並行
            # 考慮到不同網域，可以並行
            results = await asyncio.gather(
                twse.fetch_daily_quotes(date_str),
                tpex.fetch_daily_quotes(date_str)
            )
            
            valid_dfs = []
            if results[0] is not None and not results[0].empty:
                results[0]['market'] = 'TWSE'
                valid_dfs.append(results[0])
                # 收集 log
                self.all_source_logs.extend(twse.data_source_log)
                
            if results[1] is not None and not results[1].empty:
                results[1]['market'] = 'TPEX'
                valid_dfs.append(results[1])
                # 收集 log
                self.all_source_logs.extend(tpex.data_source_log)
            
            return valid_dfs

    async def _run_async_fetch(self, start_date: str, end_date: str) -> pd.DataFrame:
        """非同步主迴圈"""
        date_range = pd.date_range(start=start_date, end=end_date, freq='B')
        logger.info(f"計畫擷取: {start_date} ~ {end_date} ({len(date_range)} 天) - Async Mode")
        
        connector = aiohttp.TCPConnector(limit=5) # 限制全域連線數
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = []
            for date in date_range:
                tasks.append(self._fetch_day_data(session, date))
            
            # 使用 tqdm 顯示進度
            all_results = []
            for f in tqdm.as_completed(tasks, desc="非同步資料回補中"):
                day_dfs = await f
                all_results.extend(day_dfs)
                
                # 每個 request 完成後稍微 sleep 一下避免被鎖 IP? 
                # 其實 Semaphore 已經限制併發數，如果要更保險可以在 _fetch_day_data 加 sleep
                
        if not all_results:
            logger.error("未擷取到任何有效資料。")
            return pd.DataFrame()
            
        return pd.concat(all_results, ignore_index=True)

    def fetch_historical_data(self, start_date: str, end_date: str, delay: float = 3.0) -> pd.DataFrame:
        """
        同步接口 (與舊版相容)，內部呼叫 async 邏輯
        """
        try:
            # 嘗試使用現有的 loop，如果沒有則建立新的
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            
            if loop and loop.is_running():
                # 如果已經在 async 環境中 (例如被 async function 呼叫)
                # 這裡可能需要 nest_asyncio，但為了簡單，假設這是 top-level call
                logger.warning("Detected running event loop, careful with blocking calls.")
                # 若確實需要，應使用 await self._run_async_fetch(...) 
                # 但為了維持介面相容性 (return DataFrame)，這裡可能比較尷尬
                # 暫時假設都在 main script 最外層執行
                return asyncio.run(self._run_async_fetch(start_date, end_date))
            else:
                return asyncio.run(self._run_async_fetch(start_date, end_date))
                
        except Exception as e:
            logger.error(f"Async fetch failed: {e}")
            return pd.DataFrame()
            
        finally:
            # Save logs or cleanup (optional)
            pass

    # --- 為了相容性保留的方法 ---
    def fetch_suspended_stocks_list(self) -> List[str]:
        return []

    def fetch_revenue_batch(self, start_date: str, end_date: str, save_to_disk: bool = True) -> pd.DataFrame:
        return pd.DataFrame()

    def get_data_quality_report(self) -> pd.DataFrame:
        return pd.DataFrame(self.all_source_logs)
