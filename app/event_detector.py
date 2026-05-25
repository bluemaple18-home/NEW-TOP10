"""
事件偵測模組
根據 config/signals.yaml 定義的規則，從技術指標資料中計算事件訊號
"""

import pandas as pd
import numpy as np
import yaml
from pathlib import Path
from typing import Dict, List, Any
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class EventDetector:
    """技術事件偵測器"""
    
    def __init__(self, df: pd.DataFrame, config_path: str = "config/signals.yaml"):
        """
        初始化事件偵測器
        
        Args:
            df: 包含所有技術指標的 DataFrame
            config_path: 訊號設定檔路徑
        """
        self.df = df.copy()
        # 確保依股票和日期排序
        self.df = self.df.sort_values(['stock_id', 'date']).reset_index(drop=True)
        self.config = self._load_config(config_path)
        
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """載入設定檔"""
        path = Path(config_path)
        if not path.exists():
            logger.warning(f"設定檔 {config_path} 不存在，使用預設空設定")
            return {"events": []}
            
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
            
    def detect_all_events(self) -> pd.DataFrame:
        """
        偵測所有定義的事件
        
        Returns:
            包含 date, stock_id 與所有事件(0/1) 的 DataFrame
        """
        logger.info("開始偵測技術事件...")
        
        events_df = self.df[['date', 'stock_id']].copy()
        
        if not self.config.get('events'):
            logger.warning("未定義任何事件")
            return events_df
            
        for event_config in self.config['events']:
            event_name = event_config['name']
            event_type = event_config['type']
            params = event_config.get('params', {})
            
            logger.info(f"計算事件: {event_name} ({event_type})")
            
            try:
                if event_type == 'price_breakout':
                    signal = self._detect_price_breakout(params)
                elif event_type == 'crossover':
                    signal = self._detect_crossover(params)
                elif event_type == 'threshold_cross':
                    signal = self._detect_threshold_cross(params)
                elif event_type == 'pattern':
                    signal = self._detect_pattern(params)
                elif event_type == 'volume':
                    signal = self._detect_volume_event(params)
                else:
                    logger.warning(f"未知的事件類型: {event_type}")
                    signal = pd.Series(0, index=self.df.index)
                
                events_df[event_name] = signal.astype(int)
                
            except Exception as e:
                logger.error(f"計算事件 {event_name} 失敗: {e}")
                events_df[event_name] = 0
                
        logger.info("所有技術事件偵測完成")
        return events_df

    def _detect_price_breakout(self, params: Dict) -> pd.Series:
        """偵測價格突破"""
        period = params.get('period', 20)
        direction = params.get('direction', 'up')
        
        signals = []
        for _, group in self.df.groupby('stock_id'):
            if direction == 'up':
                # 突破近 N 日最高價 (其實是昨天的近N日最高，還是今天的近N日最高？通常突破是指 Close > Max(High of last N days excluding today))
                # 這裡定義為: Close > Rolling Max (shifted 1)
                rolling_max = group['high'].shift(1).rolling(window=period).max()
                signal = (group['close'] > rolling_max).astype(int)
            else:
                # 跌破近 N 日最低價
                rolling_min = group['low'].shift(1).rolling(window=period).min()
                signal = (group['close'] < rolling_min).astype(int)
            signals.append(signal)
            
        return pd.concat(signals).sort_index()

    def _detect_crossover(self, params: Dict) -> pd.Series:
        """偵測交叉 (黃金交叉/死亡交叉)"""
        fast_col = params['fast_ma']
        slow_col = params['slow_ma']
        direction = params.get('direction', 'up')
        
        # 檢查欄位是否存在
        if fast_col not in self.df.columns or slow_col not in self.df.columns:
            logger.warning(f"缺少欄位 {fast_col} 或 {slow_col}，無法計算交叉")
            return pd.Series(0, index=self.df.index)
            
        signals = []
        for _, group in self.df.groupby('stock_id'):
            fast = group[fast_col]
            slow = group[slow_col]
            
            shift_fast = fast.shift(1)
            shift_slow = slow.shift(1)
            
            if direction == 'up':
                # 黃金交叉: 昨天 Fast <= Slow, 今天 Fast > Slow
                signal = ((shift_fast <= shift_slow) & (fast > slow)).astype(int)
            else:
                # 死亡交叉: 昨天 Fast >= Slow, 今天 Fast < Slow
                signal = ((shift_fast >= shift_slow) & (fast < slow)).astype(int)
            
            signals.append(signal)
            
        return pd.concat(signals).sort_index()

    def _detect_threshold_cross(self, params: Dict) -> pd.Series:
        """偵測突破/跌破閾值"""
        target_col = params['target']
        threshold = params['threshold'] # 可以是數值或欄位名稱
        direction = params.get('direction', 'up')
        
        if target_col not in self.df.columns:
            logger.warning(f"缺少欄位 {target_col}")
            return pd.Series(0, index=self.df.index)
            
        target = self.df[target_col]
        
        # 判斷閾值是固定數值還是欄位
        if isinstance(threshold, str) and threshold in self.df.columns:
            thresh_val = self.df[threshold]
        else:
            thresh_val = float(threshold)
            
        signals = []
        for _, group in self.df.groupby('stock_id'):
            tgt = group[target_col]
            if isinstance(thresh_val, pd.Series):
                ths = thresh_val.loc[tgt.index]
            else:
                ths = thresh_val
                
            prev_tgt = tgt.shift(1)
            
            if isinstance(ths, pd.Series):
                prev_ths = ths.shift(1)
            else:
                prev_ths = ths
            
            if direction == 'up':
                # 向上突破: 昨天 <= 閾值, 今天 > 閾值
                signal = ((prev_tgt <= prev_ths) & (tgt > ths)).astype(int)
            else:
                # 向下跌破: 昨天 >= 閾值, 今天 < 閾值
                signal = ((prev_tgt >= prev_ths) & (tgt < ths)).astype(int)
                
            signals.append(signal)

        return pd.concat(signals).sort_index()

    def _detect_pattern(self, params: Dict) -> pd.Series:
        """偵測價格型態"""
        pattern_type = params['pattern_type']
        
        signals = []
        for _, group in self.df.groupby('stock_id'):
            open_p = group['open']
            close_p = group['close']
            high_p = group['high']
            low_p = group['low']
            prev_high = high_p.shift(1)
            prev_close = close_p.shift(1)
            
            if pattern_type == 'gap_up_strong':
                # 跳空上漲且收強: (Close > Open) AND (Open > Prev High)
                # 有些定義是 Low > Prev High (缺口)，這裡依需求: Open > Prev High 且 收紅
                signal = ((close_p > open_p) & (open_p > prev_high)).astype(int)
                
            elif pattern_type == 'long_upper_shadow':
                # 長上影線: (High - Max(Open, Close)) > (Abs(Open - Close) * ratio)
                ratio = params.get('ratio', 2.0)
                body = (close_p - open_p).abs()
                upper_shadow = high_p - pd.concat([open_p, close_p], axis=1).max(axis=1)
                
                # 避免 body 為 0 的情況 (十字線)，這裡允許 body 很小
                # 如果 body 為 0, 只要 upper_shadow > 0 就可能算，但通常要求一定的影線長度
                # 簡單起見: upper_shadow > body * ratio 且 upper_shadow 佔總長一定比例?
                # 依需求單純比較長度
                signal = (upper_shadow > (body * ratio)).astype(int)
            
            else:
                signal = pd.Series(0, index=group.index)
                
            signals.append(signal)
            
        return pd.concat(signals).sort_index()

    def _detect_volume_event(self, params: Dict) -> pd.Series:
        """偵測量能事件"""
        ratio = params.get('ratio', 2.0)
        period = params.get('period', 5)
        
        signals = []
        for _, group in self.df.groupby('stock_id'):
            vol = group['volume']
            avg_vol = vol.rolling(window=period).mean().shift(1) # 使用昨天的 N 日均量還是包含今天的？
            # 爆量通常是指今天量 > 過去 N 日均量 * 倍數 (過去N日通常不含今天，或含今天)
            # 根據 volume_indicators 算法，avg_volume_5d 是包含今天的。
            # 如果要比較「爆發」，通常是跟「過去平均」比。
            # 這裡使用 shift(1) 的 rolling mean 比較合理，或者直接用 volume_ratio_Nd 欄位
            
            # 如果已有 volume_ratio_Nd 欄位且定義為 (vol / avg_vol)，可以直接用
            ratio_col = f'volume_ratio_{period}d'
            if ratio_col in group.columns:
                signal = (group[ratio_col] > ratio).astype(int)
            else:
                # 自己算
                avg_vol_ref = vol.rolling(window=period).mean().shift(1)
                signal = (vol > (avg_vol_ref * ratio)).astype(int)
            
            signals.append(signal)
            
        return pd.concat(signals).sort_index()


if __name__ == "__main__":
    # 測試
    features_path = Path("data/clean/features.parquet")
    if features_path.exists():
        print(f"載入 {features_path}...")
        df = pd.read_parquet(features_path)
        
        detector = EventDetector(df)
        events_df = detector.detect_all_events()
        
        print(f"\n事件偵測完成！")
        print(f"資料筆數: {len(events_df)}")
        print(f"事件欄位: {list(events_df.columns[2:])}")
        
        # 顯示一些統計
        event_cols = events_df.columns[2:]
        summary = events_df[event_cols].sum()
        print("\n事件觸發次數:")
        print(summary)
        
        # 儲存
        output_path = Path("data/clean/events.parquet")
        events_df.to_parquet(output_path, index=False)
        print(f"\n已儲存至 {output_path}")
    else:
        print("features.parquet 不存在")
