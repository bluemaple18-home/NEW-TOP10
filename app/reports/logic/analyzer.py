
"""
報告生成器邏輯層：股票分析器
負責訊號分析、風險評估與交易計畫生成
"""
import pandas as pd
import numpy as np
from datetime import datetime

try:
    from app.trading import TradePlanService
except ImportError:
    from trading import TradePlanService

class StockAnalyzer:
    def __init__(self):
        self.trade_plan_service = TradePlanService()

    def prepare_report_data(self, ranked_df: pd.DataFrame, features_df: pd.DataFrame) -> dict:
        recommendations = []
        target_stocks = ranked_df.head(5)
        
        for _, row in target_stocks.iterrows():
            stock_id = str(row['stock_id'])
            stock_data = features_df[features_df['stock_id'] == stock_id].copy()
            if stock_data.empty: continue
            
            latest = stock_data.iloc[-1]
            p_win = float(row.get('model_prob', 0))
            
            triggers = self._analyze_triggers(stock_data, latest, row)
            risks = self._analyze_risks(stock_data, latest)
            verdict = self._get_verdict(p_win, risks)
            
            recommendations.append({
                'stock': f"{stock_id} {row.get('stock_name', '')}",
                'date': datetime.now().strftime('%Y-%m-%d'),
                'decision': {
                    'verdict': verdict,
                    'reason_1': triggers[0]['plain_text'] if triggers else "技術面平穩",
                    'reason_2': triggers[1]['plain_text'] if len(triggers) > 1 else ""
                },
                'trade_plan': self._generate_trade_plan(latest, p_win=p_win),
                'metrics': {
                    'p_win_5d': round(p_win * 100, 1),
                    'expected_r5': round((p_win - 0.5) * 10, 2),
                    'confidence': "高" if p_win >= 0.75 else "中" if p_win >= 0.6 else "低"
                },
                'triggers': triggers,
                'risks': risks,
                'snapshot': self._generate_snapshot(stock_data, latest),
                'notes': "注意大盤波動，建議分批佈局"
            })
            
        return {
            'report_date': datetime.now().strftime('%Y-%m-%d'),
            'total_stocks': len(target_stocks),
            'recommendations': recommendations
        }

    def _get_verdict(self, p_win, risks):
        if p_win < 0.6: return "避免"
        return "買入" if p_win >= 0.75 and not risks else "觀察"

    def _generate_trade_plan(self, latest, p_win=None):
        return self.trade_plan_service.build(latest, p_win=p_win).to_report_dict()

    def _analyze_triggers(self, df, latest, row_ranking):
        # 移自原 report_generator.py
        triggers = []
        close = latest['close']
        if len(df) >= 20:
            high_20 = df['high'].shift(1).tail(20).max()
            if close > high_20:
                triggers.append({"type":"技術","name":"線型：突破近 20 日高","evidence":f"收盤 {close} > 20日高點 {high_20:.1f}","plain_text":"慣性改變，股價創波段新高。"})
        # ... (其餘邏輯比照辦理，此處縮減以符合展示)
        return triggers

    def _analyze_risks(self, df, latest):
        risks = []
        rsi = latest.get('rsi', 50)
        if rsi > 75: risks.append(f"RSI 過熱 ({rsi:.1f} > 75)")
        return risks

    def _generate_snapshot(self, df, latest):
        # 比照原邏輯，封裝為快照資料
        return { 'close': latest['close'], 'rsi': round(latest.get('rsi', 0) or 0, 1) } # 簡化版
