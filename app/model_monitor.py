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
import pickle
import warnings
warnings.filterwarnings('ignore')

try:
    from app.modeling.feature_contract import load_m4_feature_frame
except ImportError:
    try:
        from modeling.feature_contract import load_m4_feature_frame
    except ImportError:
        load_m4_feature_frame = None

class ModelMonitor:
    """模型漂移監控器"""
    
    def __init__(self, data_dir: str = "data/clean", 
                 baseline_path: str = "models/baseline_stats.json",
                 model_path: str = "models/latest_lgbm.pkl",
                 project_root: str | Path | None = None,
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
        self.model_path = Path(model_path)
        self.project_root = Path(project_root) if project_root is not None else Path.cwd()
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
        df, numeric_cols, frame_meta = self._load_monitor_frame()
        date_col = 'trade_date' if 'trade_date' in df.columns else 'date'
        train_end = self._model_train_end_date()
        baseline_source_rows = len(df)
        if train_end is not None and date_col in df.columns:
            trade_dates = pd.to_datetime(df[date_col], errors='coerce').dt.normalize()
            df = df[trade_dates <= train_end].copy()
            print(f"   - 依模型 sealed_oos train_end_date 建立 baseline: <= {train_end.date()}")
        
        # 計算統計量 (mean, std, min, max, quantiles)
        baseline_stats = {}
        skipped_empty_model_features = []
        for col in numeric_cols:
            data = df[col].dropna()
            if len(data) > 0:
                sample_size = min(1000, len(data))
                sample_index = np.linspace(0, len(data) - 1, sample_size, dtype=int)
                distribution_sample = data.iloc[sample_index]
                baseline_stats[col] = {
                    'mean': float(data.mean()),
                    'std': float(data.std()),
                    'min': float(data.min()),
                    'max': float(data.max()),
                    'q25': float(data.quantile(0.25)),
                    'q50': float(data.quantile(0.50)),
                    'q75': float(data.quantile(0.75)),
                    'distribution': distribution_sample.values.tolist()
                }
            elif col in set(frame_meta.get('model_feature_names') or []):
                skipped_empty_model_features.append(col)
        
        # 儲存
        latest_date = pd.to_datetime(df[date_col]).max().date().isoformat() if date_col in df.columns else None
        baseline_stats['metadata'] = {
            'schema_version': 'model-baseline-stats.v1',
            'created_at': datetime.now().isoformat(),
            'total_samples': len(df),
            'source_samples_before_training_window_filter': baseline_source_rows,
            'features_count': len(baseline_stats),
            'latest_date': latest_date,
            'source': frame_meta['source'],
            'model_path': str(self.model_path),
            'model_sha256': frame_meta.get('model_sha256'),
            'model_train_end_date': train_end.date().isoformat() if train_end is not None else None,
            'model_feature_count': len(frame_meta.get('model_feature_names') or []),
            'missing_model_features': frame_meta.get('missing_model_features', []),
            'skipped_empty_model_features': skipped_empty_model_features,
            'monitored_model_feature_count': len(
                [
                    feature
                    for feature in frame_meta.get('model_feature_names') or []
                    if feature in baseline_stats
                ]
            ),
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
        df, _, frame_meta = self._load_monitor_frame()
        date_col = 'trade_date' if 'trade_date' in df.columns else 'date'
        df[date_col] = pd.to_datetime(df[date_col])
        df = df.sort_values(date_col)
        
        # 篩選最近 N 天
        cutoff_date = df[date_col].max() - pd.Timedelta(days=days)
        recent_df = df[df[date_col] > cutoff_date]
        
        print(f"   - 基準資料: {baseline_stats['metadata']['total_samples']} 筆")
        print(f"   - 最近資料: {len(recent_df)} 筆 ({cutoff_date.date()} ~ {df[date_col].max().date()})")
        
        # 計算 PSI
        psi_results = {}
        numeric_cols = [k for k in baseline_stats.keys() if k != 'metadata']
        missing_recent_features = []
        
        for col in numeric_cols:
            if col not in recent_df.columns:
                missing_recent_features.append(col)
                continue
                
            baseline_dist = pd.Series(baseline_stats[col]['distribution'])
            recent_dist = recent_df[col].dropna()
            
            psi = self.calculate_psi(baseline_dist, recent_dist)
            psi_results[col] = psi
        if not psi_results:
            return {
                'status': 'no_features',
                'action': '⚠️ 無可比較特徵，請刷新 baseline 或檢查資料契約',
                'avg_psi': None,
                'warning_features': 0,
                'critical_features': 0,
                'top_drift_features': [],
                'missing_recent_features': missing_recent_features,
                'timestamp': datetime.now().isoformat(),
            }
        
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
            'features_checked': len(psi_results),
            'missing_recent_features': missing_recent_features,
            'baseline_metadata': baseline_stats.get('metadata', {}),
            'frame_source': frame_meta['source'],
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

    def _load_monitor_frame(self) -> tuple[pd.DataFrame, list[str], dict]:
        features_path = self.data_dir / "features.parquet"
        if not features_path.exists():
            raise FileNotFoundError(f"找不到特徵檔案: {features_path}")

        model_feature_names = self._model_feature_names()
        df = None
        source = "features.parquet"
        if model_feature_names and load_m4_feature_frame is not None:
            try:
                df, _ = load_m4_feature_frame(self.data_dir, self.project_root)
                source = "m4_feature_frame"
            except Exception as exc:
                print(f"⚠ 無法載入 M4 feature frame，改用原始 features.parquet: {exc}")
        if df is None:
            df = pd.read_parquet(features_path)

        numeric_cols = df.select_dtypes(include=[np.number, bool]).columns.tolist()
        exclude = ['stock_id', 'date', 'trade_date', 'target', 'return_5d', 'future_return', 'return_long']
        numeric_cols = [col for col in numeric_cols if col not in exclude]
        missing_model_features = []
        if model_feature_names:
            feature_set = set(numeric_cols)
            selected = [col for col in model_feature_names if col in feature_set]
            missing_model_features = [col for col in model_feature_names if col not in feature_set]
            if selected:
                numeric_cols = selected

        return df, numeric_cols, {
            'source': source,
            'model_feature_names': model_feature_names,
            'model_sha256': self._sha256(self.model_path) if self.model_path.exists() else None,
            'missing_model_features': missing_model_features,
        }

    def _model_feature_names(self) -> list[str]:
        metadata = self._model_metadata()
        feature_names = metadata.get('feature_names') if isinstance(metadata.get('feature_names'), list) else None
        if feature_names:
            return [str(name) for name in feature_names]
        payload = self._model_payload()
        if isinstance(payload, dict):
            model = payload.get('model')
            if hasattr(model, 'feature_name'):
                return [str(name) for name in model.feature_name()]
        if hasattr(payload, 'feature_name'):
            return [str(name) for name in payload.feature_name()]
        return []

    def _model_train_end_date(self) -> pd.Timestamp | None:
        metadata = self._model_metadata()
        sealed = metadata.get('sealed_oos') if isinstance(metadata.get('sealed_oos'), dict) else {}
        train_end = sealed.get('train_end_date') if sealed else None
        if not train_end:
            return None
        parsed = pd.to_datetime(train_end, errors='coerce')
        if pd.isna(parsed):
            return None
        return pd.Timestamp(parsed).normalize()

    def _model_metadata(self) -> dict:
        payload = self._model_payload()
        if isinstance(payload, dict):
            metadata = payload.get('metadata')
            if isinstance(metadata, dict):
                result = dict(metadata)
                if payload.get('feature_names') and 'feature_names' not in result:
                    result['feature_names'] = payload.get('feature_names')
                return result
        return {}

    def _model_payload(self):
        if not self.model_path.exists():
            return None
        try:
            with self.model_path.open('rb') as handle:
                return pickle.load(handle)
        except Exception:
            return None

    def _sha256(self, path: Path) -> str:
        import hashlib

        digest = hashlib.sha256()
        with path.open('rb') as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b''):
                digest.update(chunk)
        return digest.hexdigest()


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
