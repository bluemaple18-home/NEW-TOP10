#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PSI (Population Stability Index) 漂移監控模組
功能: 偵測特徵分佈變化，並在必要時觸發重訓警告
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import json
import warnings
warnings.filterwarnings('ignore')

class ModelMonitor:
    """模型漂移監控器"""
    
    def __init__(self, data_dir: str = "data/clean", 
                 baseline_path: str = "models/baseline_stats.json",
                 psi_warning: float = 0.25,
                 psi_critical: float = 0.5):
        """
        Args:
            baseline_path: 基準統計資料路徑 (訓練集分佈)
            psi_warning: PSI 警告閾值
            psi_critical: PSI 嚴重閾值
        """
        self.data_dir = Path(data_dir)
        self.baseline_path = Path(baseline_path)
        self.psi_warning = psi_warning
        self.psi_critical = psi_critical
        
    def calculate_psi(self, expected: pd.Series, actual: pd.Series, bins: int = 10) -> float:
        """
        計算 PSI (Population Stability Index)
        
        Args:
            expected: 基準分佈 (訓練集)
            actual: 實際分佈 (最近資料)
            bins: 分桶數量
            
        Returns:
            psi_value: PSI 數值
        """
        # 移除 NaN
        expected = expected.dropna()
        actual = actual.dropna()
        
        if len(expected) == 0 or len(actual) == 0:
            return 0.0
            
        # 計算分位數邊界 (基於 expected)
        try:
            breakpoints = np.percentile(expected, np.linspace(0, 100, bins + 1))
            breakpoints = np.unique(breakpoints)  # 去重
        except:
            return 0.0
            
        # 計算各區間的百分比
        expected_percents = np.histogram(expected, bins=breakpoints)[0] / len(expected)
        actual_percents = np.histogram(actual, bins=breakpoints)[0] / len(actual)
        
        # PSI 計算
        psi_value = 0
        for exp, act in zip(expected_percents, actual_percents):
            # 避免除以零
            if exp == 0:
                exp = 0.0001
            if act == 0:
                act = 0.0001
            psi_value += (act - exp) * np.log(act / exp)
            
        return psi_value
    
    def save_baseline(self):
        """儲存訓練集特徵分佈作為基準"""
        print("📊 儲存訓練集基準統計...")
        
        features_path = self.data_dir / "features.parquet"
        if not features_path.exists():
            print("❌ 找不到特徵檔案")
            return
            
        df = pd.read_parquet(features_path)
        
        # 只保留數值特徵
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        # 排除 ID 與標籤
        exclude = ['stock_id', 'date', 'target', 'return_5d', 'future_return', 'return_long']
        numeric_cols = [c for c in numeric_cols if c not in exclude]
        
        # 計算統計量 (mean, std, min, max, quantiles)
        baseline_stats = {}
        for col in numeric_cols:
            data = df[col].dropna()
            if len(data) > 0:
                baseline_stats[col] = {
                    'mean': float(data.mean()),
                    'std': float(data.std()),
                    'min': float(data.min()),
                    'max': float(data.max()),
                    'q25': float(data.quantile(0.25)),
                    'q50': float(data.quantile(0.50)),
                    'q75': float(data.quantile(0.75)),
                    'distribution': data.values.tolist()[:1000]  # 保留部分樣本
                }
        
        # 儲存
        baseline_stats['metadata'] = {
            'created_at': datetime.now().isoformat(),
            'total_samples': len(df),
            'features_count': len(baseline_stats) - 1
        }
        
        with open(self.baseline_path, 'w') as f:
            json.dump(baseline_stats, f, indent=2)
            
        print(f"✅ 基準統計已儲存: {self.baseline_path}")
        print(f"   - 樣本數: {len(df)}")
        print(f"   - 特徵數: {len(baseline_stats) - 1}")
    
    def check_drift(self, days: int = 30) -> dict:
        """
        檢查最近 N 天的資料是否漂移
        
        Args:
            days: 檢查最近幾天的資料
            
        Returns:
            drift_report: 漂移報告
        """
        print(f"\n📊 檢查最近 {days} 天的資料漂移...")
        
        # 載入基準
        if not self.baseline_path.exists():
            print("⚠️ 未找到基準統計，請先執行 save_baseline()")
            return {'status': 'no_baseline'}
            
        with open(self.baseline_path, 'r') as f:
            baseline_stats = json.load(f)
            
        # 載入最近資料
        features_path = self.data_dir / "features.parquet"
        df = pd.read_parquet(features_path)
        df = df.sort_values('date')
        
        # 篩選最近 N 天
        cutoff_date = df['date'].max() - pd.Timedelta(days=days)
        recent_df = df[df['date'] > cutoff_date]
        
        print(f"   - 基準資料: {baseline_stats['metadata']['total_samples']} 筆")
        print(f"   - 最近資料: {len(recent_df)} 筆 ({cutoff_date.date()} ~ {df['date'].max().date()})")
        
        # 計算 PSI
        psi_results = {}
        numeric_cols = [k for k in baseline_stats.keys() if k != 'metadata']
        
        for col in numeric_cols:
            if col not in recent_df.columns:
                continue
                
            baseline_dist = pd.Series(baseline_stats[col]['distribution'])
            recent_dist = recent_df[col].dropna()
            
            psi = self.calculate_psi(baseline_dist, recent_dist)
            psi_results[col] = psi
        
        # 找出高 PSI 的特徵
        high_psi = {k: v for k, v in psi_results.items() if v > self.psi_warning}
        critical_psi = {k: v for k, v in psi_results.items() if v > self.psi_critical}
        
        # 整體 PSI (平均)
        avg_psi = np.mean(list(psi_results.values()))
        
        # 判定結果
        if avg_psi > self.psi_critical:
            status = 'CRITICAL'
            action = '🚨 建議立即重訓模型'
        elif avg_psi > self.psi_warning:
            status = 'WARNING'
            action = '⚠️ 建議近期重訓模型'
        else:
            status = 'OK'
            action = '✅ 模型狀態良好'
        
        # 產生報告
        drift_report = {
            'status': status,
            'action': action,
            'avg_psi': avg_psi,
            'warning_features': len(high_psi),
            'critical_features': len(critical_psi),
            'top_drift_features': sorted(psi_results.items(), key=lambda x: x[1], reverse=True)[:5],
            'timestamp': datetime.now().isoformat()
        }
        
        # 顯示結果
        print(f"\n{'='*50}")
        print(f"📈 PSI 漂移監控報告")
        print(f"{'='*50}")
        print(f"整體 PSI: {avg_psi:.4f}")
        print(f"狀態: {status}")
        print(f"{action}")
        print(f"\n⚠️ 警告特徵數: {len(high_psi)} (PSI > {self.psi_warning})")
        print(f"🚨 嚴重特徵數: {len(critical_psi)} (PSI > {self.psi_critical})")
        
        if high_psi:
            print(f"\nTop 5 漂移特徵:")
            for feat, psi in drift_report['top_drift_features']:
                print(f"  - {feat}: {psi:.4f}")
        
        print(f"{'='*50}\n")
        
        return drift_report


if __name__ == "__main__":
    monitor = ModelMonitor()
    
    # 若無基準，先建立
    if not monitor.baseline_path.exists():
        print("🔧 首次執行，建立基準統計...")
        monitor.save_baseline()
    
    # 執行漂移檢查
    report = monitor.check_drift(days=30)
    
    # 儲存報告
    report_path = Path("artifacts/psi_report.json")
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"📄 報告已儲存: {report_path}")
