"""
視覺化模組
產生訊號預覽圖與各種分析圖表
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import font_manager
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 設定中文字體（避免方框）
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'PingFang TC', 'Microsoft JhengHei', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False


def plot_stock_chart(df: pd.DataFrame, stock_id: str, stock_name: str = None) -> tuple:
    """
    繪製單一股票的 K 線圖 + 技術指標
    
    Args:
        df: 包含 OHLCV 與技術指標的 DataFrame
        stock_id: 股票代碼
        stock_name: 股票名稱（可選）
        
    Returns:
        (fig, axes) tuple
    """
    # 篩選該股票資料
    stock_data = df[df['stock_id'] == stock_id].sort_values('date').tail(120)  # 最近 120 個交易日
    
    if stock_data.empty:
        logger.warning(f"股票 {stock_id} 無資料")
        return None, None
    
    if stock_name is None:
        stock_name = stock_data['stock_name'].iloc[0] if 'stock_name' in stock_data.columns else stock_id
    
    # 建立子圖
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), gridspec_kw={'height_ratios': [3, 1]})
    fig.suptitle(f'{stock_id} {stock_name}', fontsize=14, fontweight='bold')
    
    # === 上圖：K 線 + MA + 布林通道 ===
    
    # K 線顏色
    colors = ['red' if c >= o else 'green' for c, o in zip(stock_data['close'], stock_data['open'])]
    
    # 繪製 K 線
    for idx, row in stock_data.iterrows():
        # 實體
        body_height = abs(row['close'] - row['open'])
        body_bottom = min(row['close'], row['open'])
        color = 'red' if row['close'] >= row['open'] else 'green'
        
        ax1.bar(row['date'], body_height, bottom=body_bottom, width=0.8, color=color, alpha=0.8)
        
        # 影線
        ax1.plot([row['date'], row['date']], [row['low'], row['high']], color='black', linewidth=0.5)
    
    # 繪製 MA
    for ma_period in [5, 10, 20]:
        ma_col = f'ma{ma_period}'
        if ma_col in stock_data.columns:
            ax1.plot(stock_data['date'], stock_data[ma_col], label=f'MA{ma_period}', linewidth=1.5)
    
    # 繪製布林通道
    if 'bb_upper' in stock_data.columns:
        ax1.plot(stock_data['date'], stock_data['bb_upper'], 'b--', label='BB Upper', linewidth=1, alpha=0.6)
        ax1.plot(stock_data['date'], stock_data['bb_middle'], 'b-', label='BB Middle', linewidth=1, alpha=0.6)
        ax1.plot(stock_data['date'], stock_data['bb_lower'], 'b--', label='BB Lower', linewidth=1, alpha=0.6)
        ax1.fill_between(stock_data['date'], stock_data['bb_upper'], stock_data['bb_lower'], alpha=0.1, color='blue')
    
    ax1.set_ylabel('價格 (元)', fontsize=11)
    ax1.legend(loc='upper left', fontsize=9)
    ax1.grid(True, alpha=0.3)
    
    # === 下圖：成交量 ===
    
    # 成交量顏色
    vol_colors = ['red' if c >= o else 'green' for c, o in zip(stock_data['close'], stock_data['open'])]
    ax2.bar(stock_data['date'], stock_data['volume'], color=vol_colors, alpha=0.6, width=0.8)
    
    # 繪製平均量
    if 'avg_volume_20d' in stock_data.columns:
        ax2.plot(stock_data['date'], stock_data['avg_volume_20d'], 'orange', label='20日均量', linewidth=1.5)
    
    ax2.set_xlabel('日期', fontsize=11)
    ax2.set_ylabel('成交量', fontsize=11)
    ax2.legend(loc='upper left', fontsize=9)
    ax2.grid(True, alpha=0.3)
    
    # 格式化 X 軸日期
    for ax in [ax1, ax2]:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        for label in ax.get_xticklabels():
            label.set_rotation(45)
    
    plt.tight_layout()
    
    return fig, (ax1, ax2)


def generate_signals_preview(
    df: pd.DataFrame,
    output_path: str = "artifacts/signals_preview.png",
    num_samples: int = 5,
    seed: int = 42
):
    """
    產生訊號預覽圖（抽樣多檔股票）
    
    Args:
        df: universe DataFrame
        output_path: 輸出路徑
        num_samples: 抽樣股票數
        seed: 隨機種子
    """
    logger.info(f"產生訊號預覽圖（抽樣 {num_samples} 檔）")
    
    # 隨機抽樣
    np.random.seed(seed)
    unique_stocks = df['stock_id'].unique()
    
    if len(unique_stocks) < num_samples:
        logger.warning(f"股票數 ({len(unique_stocks)}) < 抽樣數 ({num_samples})，調整抽樣數")
        num_samples = len(unique_stocks)
    
    sampled_stocks = np.random.choice(unique_stocks, size=num_samples, replace=False)
    
    # 建立大圖
    fig = plt.figure(figsize=(16, 4 * num_samples))
    
    for i, stock_id in enumerate(sampled_stocks):
        stock_data = df[df['stock_id'] == stock_id].sort_values('date').tail(120)
        
        if stock_data.empty:
            continue
        
        stock_name = stock_data['stock_name'].iloc[0] if 'stock_name' in stock_data.columns else stock_id
        
        # 上圖：K 線 + MA + 布林
        ax1 = plt.subplot(num_samples, 2, i*2 + 1)
        
        # K 線
        for idx, row in stock_data.iterrows():
            body_height = abs(row['close'] - row['open'])
            body_bottom = min(row['close'], row['open'])
            color = 'red' if row['close'] >= row['open'] else 'green'
            
            ax1.bar(row['date'], body_height, bottom=body_bottom, width=0.8, color=color, alpha=0.8)
            ax1.plot([row['date'], row['date']], [row['low'], row['high']], color='black', linewidth=0.5)
        
        # MA
        for ma_period, color in [(5, 'orange'), (10, 'blue'), (20, 'purple')]:
            ma_col = f'ma{ma_period}'
            if ma_col in stock_data.columns:
                ax1.plot(stock_data['date'], stock_data[ma_col], color=color, label=f'MA{ma_period}', linewidth=1)
        
        # 布林通道
        if 'bb_upper' in stock_data.columns:
            ax1.plot(stock_data['date'], stock_data['bb_upper'], 'gray', linestyle='--', linewidth=0.8, alpha=0.5)
            ax1.plot(stock_data['date'], stock_data['bb_lower'], 'gray', linestyle='--', linewidth=0.8, alpha=0.5)
            ax1.fill_between(stock_data['date'], stock_data['bb_upper'], stock_data['bb_lower'], alpha=0.05, color='gray')
        
        ax1.set_title(f'{stock_id} {stock_name}', fontsize=10, fontweight='bold')
        ax1.set_ylabel('價格', fontsize=9)
        ax1.legend(loc='upper left', fontsize=7)
        ax1.grid(True, alpha=0.3)
        ax1.tick_params(axis='x', labelsize=7)
        ax1.tick_params(axis='y', labelsize=7)
        
        # 下圖：成交量
        ax2 = plt.subplot(num_samples, 2, i*2 + 2)
        
        vol_colors = ['red' if c >= o else 'green' for c, o in zip(stock_data['close'], stock_data['open'])]
        ax2.bar(stock_data['date'], stock_data['volume'], color=vol_colors, alpha=0.6, width=0.8)
        
        if 'avg_volume_20d' in stock_data.columns:
            ax2.plot(stock_data['date'], stock_data['avg_volume_20d'], 'orange', label='20日均量', linewidth=1)
        
        ax2.set_title('成交量', fontsize=10)
        ax2.set_ylabel('量', fontsize=9)
        ax2.legend(loc='upper left', fontsize=7)
        ax2.grid(True, alpha=0.3)
        ax2.tick_params(axis='x', labelsize=7)
        ax2.tick_params(axis='y', labelsize=7)
    
    plt.tight_layout()
    
    # 儲存
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    logger.info(f"訊號預覽圖已儲存: {output_path}")


if __name__ == "__main__":
    # 測試
    universe_file = Path("data/clean/universe.parquet")
    
    if universe_file.exists():
        df = pd.read_parquet(universe_file)
        print(f"載入 universe: {len(df)} 筆, {df['stock_id'].nunique()} 檔")
        
        generate_signals_preview(
            df=df,
            output_path="artifacts/signals_preview.png",
            num_samples=5
        )
        
        print("視覺化完成！")
    else:
        print(f"請先執行 ETL 流程產生 {universe_file}")
