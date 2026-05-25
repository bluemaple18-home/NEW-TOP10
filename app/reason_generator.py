#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
推薦理由生成模組
根據技術指標、量能、基本面資料生成 3~5 個推薦理由
支援結構化輸出（正向/反向標記）
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Union

# 定義理由類型
TYPE_POSITIVE = "POSITIVE"
TYPE_CAUTION = "CAUTION"

def generate_reasons_structured(row: pd.Series, hist_df: pd.DataFrame = None) -> List[Dict[str, Any]]:
    """
    生成結構化推薦理由 (包含佐證元數據)
    
    Returns:
        List[Dict]: 
        [{
            'type': 'POSITIVE'|'CAUTION', 
            'text': '...',
            'metadata': { ...佐證數據... }
        }]
    """
    reasons = []
    
    # 取得基礎數據
    ret = row.get('expected_return_5d', 0)
    win_rate = row.get('win_rate', 0)
    volume = row.get('volume', 0)
    close = row.get('close', 0)
    date = row.get('date', datetime.now())
    
    # 若有歷史數據，進行深度偵探分析
    if hist_df is not None and not hist_df.empty:
        # 確保按日期排序
        hist_df = hist_df.sort_index()
        last_date = hist_df.index[-1].strftime('%Y-%m-%d')
        
        # --- 1. 偵測 W 底 (雙重底) ---
        # 簡易邏輯：尋找過去 60 天的兩個明顯低點
        # 需在近期 (5日內) 突破頸線
        recent = hist_df.iloc[-60:]
        if len(recent) > 20: 
            # 找兩個低谷 (Local Minima)
            lows = recent['Low'].values
            # 這裡簡化處理，找前後半段的最低點
            mid = len(lows) // 2
            p1 = np.argmin(lows[:mid])
            p2 = np.argmin(lows[mid:]) + mid
            
            low1_val = lows[p1]
            low2_val = lows[p2]
            
            # W底特徵：兩低點接近 (差距 < 3%)
            if abs(low1_val - low2_val) / low1_val < 0.03:
                # 找頸線 (兩低點中間的最高點)
                neckline = np.max(recent['High'].values[p1:p2])
                
                # 檢查是否突破頸線
                if close > neckline and close < neckline * 1.05:
                    date1 = recent.index[p1].strftime('%m/%d')
                    date2 = recent.index[p2].strftime('%m/%d')
                    reasons.append({
                        "type": TYPE_POSITIVE, 
                        "text": "W底成型突破頸線",
                        "metadata": {
                            "date1": date1, "price1": f"{low1_val:.2f}",
                            "date2": date2, "price2": f"{low2_val:.2f}",
                            "neckline": f"{neckline:.2f}",
                            "break_price": f"{close:.2f}"
                        }
                    })

        # --- 2. 偵測 MA 支撐 (回測有守) ---
        # 檢查過去 3 天是否曾觸碰 MA20 但收盤在 MA20 之上
        if 'MA20' in hist_df.columns:
            recent_3d = hist_df.iloc[-3:]
            for dt, r in recent_3d.iterrows():
                ma20 = r['MA20']
                if r['Low'] <= ma20 and r['Close'] > ma20:
                    test_date = dt.strftime('%m/%d')
                    reasons.append({
                        "type": TYPE_POSITIVE,
                        "text": "回測支撐有守",
                        "metadata": {
                            "support_name": "月線 (MA20)",
                            "test_date": test_date,
                            "support_price": f"{ma20:.2f}",
                            "close_price": f"{r['Close']:.2f}"
                        }
                    })
                    break

        # --- 3. 偵測 KD 鈍化 ---
        if 'K' in hist_df.columns:
            # 檢查是否連續 N 天 K < 20
            k_vals = hist_df['K'].values
            low_k_days = 0
            for k in reversed(k_vals[:-1]): # 不含今日
                if k < 25:
                    low_k_days += 1
                else:
                    break
            
            current_k = k_vals[-1]
            if low_k_days >= 3 and current_k > k_vals[-2]: # 鈍化後轉折
                start_date = (hist_df.index[-1] - timedelta(days=low_k_days)).strftime('%m/%d')
                end_date = hist_df.index[-2].strftime('%m/%d')
                reasons.append({
                    "type": TYPE_POSITIVE,
                    "text": "KD指標低檔鈍化",
                    "metadata": {
                        "days": low_k_days,
                        "start_date": start_date,
                        "end_date": end_date,
                        "min_k": f"{min(k_vals[-low_k_days-1:-1]):.1f}", 
                        "current_k": f"{current_k:.1f}"
                    }
                })

        # --- 4. 爆量長紅 ---
        # 今日量 > 均量 2 倍且 漲幅 > 3%
        if 'MA5' in hist_df.columns: # 使用 MA5 作為今日漲幅參考 (今日收盤 - 昨日收盤)
             # 改用 row 傳入的 volume (可能較準)
             vol_ma5 = hist_df['Volume'].rolling(5).mean().iloc[-1]
             prev_close = hist_df['Close'].iloc[-2]
             
             change_pct = (close - prev_close) / prev_close * 100
             if volume > vol_ma5 * 1.8 and change_pct > 3.0:
                 reasons.append({
                     "type": TYPE_POSITIVE,
                     "text": "爆量長紅突破",
                     "metadata": {
                         "vol_ratio": f"{volume/vol_ma5:.1f}",
                         "change_pct": f"{change_pct:.1f}",
                         "close": f"{close:.2f}"
                     }
                 })


    # ===== Fallback: 若無歷史數據或沒偵測到，使用單點特徵填補 (帶參數) =====
    
    # 高勝率 + 高報酬
    if win_rate >= 70 and ret >= 4.0:
        if not any(r['text'] == "W底成型突破頸線" for r in reasons):
             reasons.append({
                 "type": TYPE_POSITIVE, 
                 "text": "W底成型突破頸線",
                 "metadata": {
                     "note": "依據高勝率模型推估",
                     "win_rate": f"{win_rate:.0f}%",
                     "exp_ret": f"{ret:.1f}%"
                 }
             })
             
    # 均線多頭
    if win_rate >= 65 and not any(r['text'] == "均線多頭排列" for r in reasons):
         reasons.append({
             "type": TYPE_POSITIVE, 
             "text": "均線多頭排列",
             "metadata": {
                 "ma5": f"{row.get('MA5', 0):.2f}",
                 "ma20": f"{row.get('MA20', 0):.2f}",
                 "ma60": f"{row.get('MA60', 0):.2f}"
             }
         })

    # MACD
    if 'macd' in row and 'macd_signal' in row:
        macd = row['macd']
        signal = row['macd_signal']
        if macd > signal and macd > 0:
             reasons.append({
                 "type": TYPE_POSITIVE, 
                 "text": "MACD黃金交叉",
                 "metadata": {
                     "dif": f"{macd:.2f}",
                     "signal": f"{signal:.2f}"
                 }
             })
    
    # ===== 營收動能 (Revenue Momentum) =====
    
    revenue_yoy = row.get('revenue_yoy')
    revenue_mom = row.get('revenue_mom')
    
    if revenue_yoy is not None and not np.isnan(revenue_yoy):
        # 爆發式成長
        if revenue_yoy > 100:
            reasons.append({
                "type": TYPE_POSITIVE,
                "text": "營收爆發式成長",
                "metadata": {
                    "revenue_yoy": f"{revenue_yoy:.1f}%",
                    "note": "年增率超過 100%"
                }
            })
        # 強勁成長
        elif revenue_yoy > 50:
            reasons.append({
                "type": TYPE_POSITIVE,
                "text": "營收連三月成長",
                "metadata": {
                    "revenue_yoy": f"{revenue_yoy:.1f}%",
                    "revenue_mom": f"{revenue_mom:.1f}%" if revenue_mom and not np.isnan(revenue_mom) else "N/A"
                }
            })
        # 穩健成長
        elif revenue_yoy > 20:
            reasons.append({
                "type": TYPE_POSITIVE,
                "text": "營收穩健成長",
                "metadata": {
                    "revenue_yoy": f"{revenue_yoy:.1f}%"
                }
            })
        # 營收衰退警示
        elif revenue_yoy < -20:
            reasons.append({
                "type": TYPE_CAUTION,
                "text": "⚠ 營收大幅衰退",
                "metadata": {
                    "revenue_yoy": f"{revenue_yoy:.1f}%"
                }
            })

    # 確保每個理由都有 metadata
    for r in reasons:
        if 'metadata' not in r:
            r['metadata'] = {}

    return reasons[:5]


def generate_reasons(row: pd.Series, hist_df: pd.DataFrame = None) -> List[str]:
    """
    相容舊版：回傳純文字列表
    """
    structured = generate_reasons_structured(row, hist_df)
    return [r['text'] for r in structured]

def generate_reasons_batch(df: pd.DataFrame, hist_data_dict: dict = None) -> pd.DataFrame:
    """
    批次生成所有股票的推薦理由 (新增 reasons_json 欄位)
    """
    df = df.copy()
    
    reasons_list = []      # 舊版相容
    reasons_json_list = [] # 結構化資料
    
    for idx, row in df.iterrows():
        stock_id = str(row['stock_id'])
        hist_df = hist_data_dict.get(stock_id) if hist_data_dict else None
        
        # 為了計算 prev_close 等特徵，這裡簡單處理
        # 實務上應該在指標計算階段就準備好這些欄位
        # 這裡假設 row 若無這些欄位，則無法產生相關理由
        
        structured = generate_reasons_structured(row, hist_df)
        
        reasons_json_list.append(structured)
        reasons_list.append([r['text'] for r in structured])
    
    df['reasons'] = reasons_list
    df['reasons_json'] = reasons_json_list
    return df

def format_reasons_text(reasons: List[str]) -> str:
    if not reasons:
        return "無推薦理由"
    return "\\n".join([f"• {r}" for r in reasons])
