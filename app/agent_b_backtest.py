#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agent B - 回測模擬模組 (Simulation Backtest)
負責模擬過去一段時間的每日選股，並計算策略績效
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import warnings
from tqdm import tqdm
import matplotlib.pyplot as plt

# 引用 StockRanker
try:
    from app.agent_b_ranking import StockRanker
except ImportError:
    from agent_b_ranking import StockRanker

warnings.filterwarnings('ignore')

class BacktestSimulator:
    """回測模擬器"""
    
    def __init__(self, data_dir: str = "data/clean", artifact_dir: str = "artifacts",
                 transaction_cost: float = 0.003, initial_capital: float = 1_000_000):
        self.data_dir = Path(data_dir)
        self.artifact_dir = Path(artifact_dir)
        self.transaction_cost = transaction_cost
        self.initial_capital = initial_capital
        
        # 初始化 Ranker (共用)
        self.ranker = StockRanker(data_dir=data_dir, artifact_dir=artifact_dir)
        try:
            self.ranker.load_model()
        except Exception:
            print("⚠ 警告: 無法載入模型，將僅使用規則評分進行回測")
            
        # 載入價格資料 (Cache)
        self.features = self.ranker.load_daily_data(date=None) # 此處 load_daily_data 在 ranking.py 若無參數會載入 default
        # 為了回測，我們需要完整的 df
        # 直接讀取 parquet 比較快
        if (self.data_dir / "features.parquet").exists():
            self.features = pd.read_parquet(self.data_dir / "features.parquet")
            self.features['date'] = pd.to_datetime(self.features['date'])
        else:
            raise FileNotFoundError("特徵資料不存在")

    def run_simulation(self, months: int = 12, prob_threshold: float = 0.5):
        """
        執行模擬回測
        Args:
            months: 回測過去幾個月
            prob_threshold: 機率門檻 (只選信心 > threshold 的股票)
        """
        print(f"⏳ 開始模擬回測 (過去 {months} 個月, Threshold={prob_threshold})...")
        
        # 1. 決定日期範圍
        end_date = self.features['date'].max()
        start_date = end_date - pd.DateOffset(months=months)
        
        # 找出所有交易日
        all_dates = sorted(self.features['date'].unique())
        target_dates = [d for d in all_dates if d >= start_date]
        
        results = []
        equity_curve = [self.initial_capital]
        capital = self.initial_capital
        
        print(f"📅 回測區間: {target_dates[0].date()} ~ {target_dates[-1].date()} (共 {len(target_dates)} 交易日)")
        
        # 2. 逐日模擬
        for date in tqdm(target_dates):
            date_str = date.strftime('%Y-%m-%d')
            
            # 取得當日排名 (使用 Ranker)
            daily_df = self.features[self.features['date'] == date].copy()
            if daily_df.empty: continue
            
            # 呼叫 ranker 邏輯 (不存檔)
            try:
                ranked_df = self.ranker.calculate_scores(daily_df)
                # 篩選 Buy 及 Top N
                # 嚴格篩選: model_prob > threshold 且 final_score 前 10
                qualified = ranked_df[ranked_df['model_prob'] >= prob_threshold]
                
                # 若合格者不足，寧缺勿濫 (High Precision Strategy)
                top10 = qualified.sort_values('final_score', ascending=False).head(10)
                
            except Exception as e:
                # print(f"Error on {date_str}: {e}")
                continue
                
            # 3. 計算報酬 (模擬持有)
            daily_returns = []
            
            for _, row in top10.iterrows():
                stock_id = row['stock_id']
                stock_data = self.features[
                    (self.features['stock_id'] == stock_id) & 
                    (self.features['date'] >= date)
                ].sort_values('date')
                
                if len(stock_data) < 2: 
                    continue
                    
                entry_price = stock_data.iloc[1]['open']
                if pd.isna(entry_price): continue
                
                hold_days = 10
                exit_idx = min(1 + hold_days, len(stock_data) - 1)
                exit_price = stock_data.iloc[exit_idx]['close']
                
                ret = (exit_price - entry_price) / entry_price - self.transaction_cost
                daily_returns.append(ret)
            
            if daily_returns:
                avg_ret = np.mean(daily_returns)
            else:
                avg_ret = 0
                
            results.append({
                'date': date,
                'avg_return_5d': avg_ret,
                'win_rate': np.mean([r > 0 for r in daily_returns]) if daily_returns else 0,
                'selections': len(daily_returns)
            })
            
        results_df = pd.DataFrame(results)
        
        if results_df.empty:
            print("❌ 回測無結果 (可能門檻過高)")
            return results_df
            
        # 統計
        avg_ret_per_trade = results_df[results_df['selections'] > 0]['avg_return_5d'].mean()
        # 加權勝率 (以交易日有出手的才算? 或是以總筆數?)
        # 這裡用總筆數更準確
        # 但為了簡單，先把每日平均勝率再平均
        win_rate = results_df[results_df['selections'] > 0]['win_rate'].mean()
        total_days_traded = (results_df['selections'] > 0).sum()
        total_trades = results_df['selections'].sum()
        
        self._generate_report(results_df, avg_ret_per_trade, win_rate, total_trades, prob_threshold)
        
        return results_df

    def _generate_report(self, df: pd.DataFrame, avg_ret: float, win_rate: float, trades: int, threshold: float):
        """產生 Markdown 與圖表"""
        df['cum_ret'] = (1 + df['avg_return_5d']).cumprod()
        
        plt.figure(figsize=(12, 6))
        plt.plot(df['date'], df['cum_ret'], label=f'Threshold > {threshold}')
        plt.title(f'Agent B Strategy (Threshold={threshold})')
        plt.grid(True)
        plt.legend()
        plt.savefig(self.artifact_dir / f"backtest_curve_{threshold}.png")
        
        report = f"""# Agent B 回測報告 (Threshold={threshold})

**回測期間**: {df['date'].min().date()} ~ {df['date'].max().date()}
**交易成本**: {self.transaction_cost*100}%
**機率門檻**: {threshold}

## 核心績效
- **總交易筆數**: {trades} 筆 (平均每日 {trades/len(df):.1f} 檔)
- **有交易天數**: {(df['selections']>0).sum()} / {len(df)} 天
- **平均每次報酬 (5日)**: {avg_ret*100:.3f}%
- **平均勝率**: {win_rate*100:.2f}%

詳見 `backtest_curve_{threshold}.png`。
"""
        with open(self.artifact_dir / f"backtest_report_{threshold}.md", "w") as f:
            f.write(report)
            
        print("\n" + "-"*40)
        print(f"門檻 {threshold}: 勝率 {win_rate*100:.1f}%, 報酬 {avg_ret*100:.2f}%")
        print("-"*40)

if __name__ == "__main__":
    simulator = BacktestSimulator()
    
    # 測試不同門檻 (建議門檻: 0.25 ~ 0.3)
    # 說明: 由於 Isotonic Calibration 在保守市況下會壓縮機率，0.25 約等同於相對高信心
    print("🔍 執行回測模擬...")
    simulator.run_simulation(months=12, prob_threshold=0.25)
