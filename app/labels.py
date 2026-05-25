
import pandas as pd
import numpy as np

class LabelGenerator:
    """
    負責生成模型訓練用的標籤 (Labels)
    核心邏輯：
    1. Signal Day: D
    2. Entry: D+1 開盤價 (Open)
    3. Exit: D+N 收盤價 (Close) (N=horizon)
    4. Return: (Exit - Entry) / Entry
    5. Target: 1 if Return > threshold else 0 (Binary Classification)
    """
    
    def __init__(self, horizon: int = 10, threshold: float = 0.05):
        self.horizon = horizon
        self.threshold = threshold
        
    def generate_labels(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        生成標籤
        
        Args:
            df: 包含 OHLC 資料的 DataFrame (必須包含 stock_id, date, open, close)
            
        Returns:
            df: 包含 entry_price, exit_price, return_5d, target 的 DataFrame
        """
        # 避免修改原始 Frame
        df = df.copy()
        
        # 檢查欄位
        required = {'stock_id', 'date', 'open', 'close'}
        if not required.issubset(df.columns):
            raise ValueError(f"缺少必要欄位，需求: {required}, 實際: {df.columns.tolist()}")
            
        # 排序確保 shift 邏輯正確
        df = df.sort_values(['stock_id', 'date'])
        
        # 1. Entry Price: D+1 Open
        # shift(-1) 取下一列
        df['entry_price'] = df.groupby('stock_id')['open'].shift(-1)
        
        # 2. Exit Price: D+N Close
        # 持有 N 天。
        df['exit_price'] = df.groupby('stock_id')['close'].shift(-self.horizon)
        
        # 3. Calculate Return
        # (賣出 - 買入) / 買入
        df['return_long'] = (df['exit_price'] - df['entry_price']) / df['entry_price']
        # 為了相容性保留 return_5d 的名稱? 或者統一改名?
        # 為了避免 agent_b_modeling 壞掉，這欄位名稱應保持或更新 modeling
        # 我們將其命名為 return_5d (歷史包袱) 或 return_holding?
        # 決定：將欄位改名為 'future_return'，並保留 'return_5d' 作為 alias (若有舊程式依賴)
        df['future_return'] = df['return_long']
        df['return_5d'] = df['return_long'] 
        
        # 4. Generate Target (Binary Classification)
        # 獲利 > threshold 即為 1 (Win)
        valid_label = df['future_return'].notna() & df['entry_price'].notna() & df['exit_price'].notna()
        df['target'] = np.where(valid_label, (df['future_return'] > self.threshold).astype(int), np.nan)
        
        # 補充：Debug 用，紀錄未來收盤
        df['future_close'] = df['exit_price']
        
        # 統計
        valid_count = df['future_return'].notna().sum()
        positive_count = int(df.loc[valid_label, 'target'].sum())
        ratio = positive_count / valid_count if valid_count > 0 else 0
        print(f"✓ 已生成標籤: {valid_count} 筆有效樣本 (Horizon={self.horizon}d, Threshold={self.threshold:.1%})")
        print(f"  - 正樣本數: {positive_count} ({ratio:.1%})")
        
        return df
