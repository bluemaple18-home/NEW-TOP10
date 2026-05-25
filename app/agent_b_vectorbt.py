import vectorbt as vbt
import pandas as pd
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
from datetime import datetime

class VectorBacktester:
    """基於 vectorbt 的向量化回測引擎"""
    
    def __init__(self, data_dir: str = "data/clean", artifact_dir: str = "artifacts"):
        self.data_dir = Path(data_dir)
        self.artifact_dir = Path(artifact_dir)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        
    def run_vectorized_backtest(self, df: pd.DataFrame, prob_threshold: float = 0.25):
        """
        執行向量化回測
        Args:
            df: 包含預測機率 (model_prob) 與價格的 DataFrame
            prob_threshold: 勝率門檻
        """
        print(f"🚀 啟動 vectorbt 向量化回測 (Threshold: {prob_threshold})...")
        
        # 1. 準備信號
        # 建立買入信號：model_prob > threshold
        entries = df['model_prob'] > prob_threshold
        
        # 建立賣出信號：持有 10 天 (向量化處理)
        # 在 vectorbt 中，可以使用 Portfolio.from_signals 並設定 init_cash 與 fees
        # 持有期賣出通常使用 exit_on_order_duration=10
        
        # 取得收盤價
        close = df.pivot(index='date', columns='stock_id', values='close')
        # 取得買入矩陣 (對齊價格矩陣)
        entry_matrix = df.pivot(index='date', columns='stock_id', values='model_prob') > prob_threshold
        
        # 2. 執行回測
        pf = vbt.Portfolio.from_signals(
            close, 
            entries=entry_matrix,
            exits=None, 
            init_cash=1000000,
            fees=0.001425 + 0.003, 
            cash_sharing=True,
            group_by=False,
            tp_stop=None,
            sl_stop=None,
            freq='1D' # 顯式指定頻率，避免 'B' 引起的錯誤
        )
        
        # 3. 獲取指標
        stats = pf.stats()
        print(f"✅ 回測完成！總報酬率: {stats['Total Return [%]']:.2f}%")
        
        return pf, stats

    def parameter_sweep(self, df: pd.DataFrame, thresholds: list = [0.15, 0.2, 0.25, 0.3]):
        """
        執行多門檻平行掃描
        """
        print(f"🔍 執行參數掃描: {thresholds}...")
        
        close = df.pivot(index='date', columns='stock_id', values='close')
        prob_matrix = df.pivot(index='date', columns='stock_id', values='model_prob')
        
        # 建立多維 entry 矩陣 (使用 vectorbt 的多維數據支援)
        # 這部分是 vectorbt 的核心優勢
        results = []
        for t in thresholds:
            entry_matrix = prob_matrix > t
            pf = vbt.Portfolio.from_signals(close, entries=entry_matrix, init_cash=1000000, fees=0.004)
            ret = pf.total_return().mean()
            results.append({'threshold': t, 'return': ret})
            print(f"  門檻 {t}: 平均報酬 {ret*100:.2f}%")
            
        return pd.DataFrame(results)

if __name__ == "__main__":
    # 測試腳本
    backtester = VectorBacktester()
    # 這裡假設已有預測結果的 df
    print("💡 提示: 需搭配已產出的預測結果 Dataframe 執行回測")
