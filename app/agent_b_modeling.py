
import argparse
import pandas as pd
import numpy as np
import lightgbm as lgb
from pathlib import Path
from datetime import datetime, timedelta
import pickle
from typing import Any
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import TimeSeriesSplit
import optuna
from sklearn.metrics import roc_auc_score, log_loss
from sklearn.isotonic import IsotonicRegression
import shap
import mlflow
import mlflow.lightgbm
import webbrowser
import os
import yaml

# 引入新的標籤生成器
try:
    from labels import LabelGenerator
except ImportError:
    # 若相對路徑匯入失敗，嘗試從 app 匯入
    from app.labels import LabelGenerator

try:
    from app.modeling.feature_contract import (
        FeatureFrameMetadata,
        build_m4_feature_frame,
        candidate_feature_columns,
        load_m4_feature_frame,
    )
    from app.modeling.sealed_oos import SealedOOSConfig, build_sealed_oos_split
except ImportError:
    from modeling.feature_contract import (
        FeatureFrameMetadata,
        build_m4_feature_frame,
        candidate_feature_columns,
        load_m4_feature_frame,
    )
    from modeling.sealed_oos import SealedOOSConfig, build_sealed_oos_split


class LightGBMTrainer:
    """LightGBM 分類模型訓練器 (Advanced 版: Calibration + SHAP)"""
    
    def __init__(self, data_dir: str = "data/clean", model_dir: str = "models", 
                 artifact_dir: str = "artifacts", horizon: int = 10, threshold: float = 0.05):
        """
        初始化訓練器
        Args:
            horizon: 持有天數 (預設 10 天)
            threshold: 獲利門檻 (預設 5%)
        """
        self.data_dir = Path(data_dir)
        self.model_dir = Path(model_dir)
        self.artifact_dir = Path(artifact_dir)
        self.horizon = horizon
        self.threshold = threshold
        self.model = None
        self.calibrator = None  # 機率校準器
        self.best_params = None
        self.feature_metadata: FeatureFrameMetadata | None = None
        self.sealed_oos_metadata: dict[str, Any] | None = None
        self.model_metadata: dict[str, Any] = {}
        self.training_feature_names: list[str] = []
        
        # 建立必要目錄
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
    
    def load_features(self, file_path: str = None) -> pd.DataFrame:
        """載入 M4 合併特徵資料。

        預設讀取 `features.parquet` + `events.parquet` + 本地 fundamentals cache。
        這裡不觸發 Goodinfo 或其他外部抓取。
        """
        if file_path is None:
            features_path = self.data_dir / "features.parquet"
            if features_path.exists():
                df, metadata = load_m4_feature_frame(self.data_dir, Path.cwd())
            else:
                features_path = Path("data/test/features_test.parquet")
                events_path = Path("data/test/events_test.parquet")
                if not features_path.exists():
                    raise FileNotFoundError(f"特徵檔案不存在: {features_path}")
                events = pd.read_parquet(events_path) if events_path.exists() else None
                df, metadata = build_m4_feature_frame(pd.read_parquet(features_path), events)
            self.feature_metadata = metadata
            df.attrs["m4_feature_metadata"] = metadata
        else:
            file_path = Path(file_path)
            if not file_path.exists():
                raise FileNotFoundError(f"特徵檔案不存在: {file_path}")
            features = pd.read_parquet(file_path)
            events_path = file_path.with_name("events.parquet")
            events = pd.read_parquet(events_path) if events_path.exists() else None
            df, metadata = build_m4_feature_frame(features, events)
            self.feature_metadata = metadata
            df.attrs["m4_feature_metadata"] = metadata
        
        # 記憶體優化
        float_cols = df.select_dtypes(include=['float64']).columns
        if len(float_cols) > 0:
            df[float_cols] = df[float_cols].astype('float32')
            
        print(f"✓ 載入特徵資料: {len(df)} 筆, {len(df.columns)} 欄位")
        self._print_feature_contract_summary()
        return df
    
    def generate_labels(self, df: pd.DataFrame) -> pd.DataFrame:
        """使用 LabelGenerator 生成標籤"""
        generator = LabelGenerator(horizon=self.horizon, threshold=self.threshold)
        df = self._with_trade_date(df)
        self._ensure_unique_trade_keys(df, "訓練 features")
        # 標籤邏輯是日頻 D/D+1/D+N，先統一 date 避免 timestamp 影響 shift。
        df['date'] = df['trade_date']
        # 需確保 df 有 open/close 欄位，ETL 產出的 features.parquet 應該有
        if 'open' not in df.columns:
            print("⚠ 警告: 找不到 'open' 欄位，標籤生成可能失敗")
        
        df_labeled = generator.generate_labels(df)
        before = len(df_labeled)
        df_labeled = df_labeled.dropna(subset=['target', 'future_return', 'entry_price', 'exit_price']).copy()
        df_labeled['target'] = df_labeled['target'].astype(int)
        dropped = before - len(df_labeled)
        if dropped:
            print(f"✓ 已排除無未來報酬的尾端樣本: {dropped} 筆")
        df_labeled.attrs["m4_feature_metadata"] = df.attrs.get("m4_feature_metadata", self.feature_metadata)
        return df_labeled
    
    def prepare_train_data(self, df: pd.DataFrame, exclude_cols: list = None, feature_metadata: FeatureFrameMetadata | None = None):
        """準備訓練資料"""
        if 'date' in df.columns:
            df = df.copy()
            df['trade_date'] = pd.to_datetime(df['date']).dt.normalize()
            df = df.sort_values(['trade_date', 'stock_id'] if 'stock_id' in df.columns else ['trade_date']).copy()
        if exclude_cols is None:
            exclude_cols = [
                'symbol', 'stock_id', 'date', 'trade_date', 'target', 'stock_name', 
                'entry_price', 'exit_price', 'return_5d', 'future_close',
                'return_long', 'future_return' # 修正漏網之魚
            ]
        
        y = df['target'] # 0 or 1
        metadata = feature_metadata or df.attrs.get("m4_feature_metadata") or self.feature_metadata

        if metadata is not None:
            potential_features = candidate_feature_columns(df, metadata)
        else:
            # 1. 先排除明確指定的欄位
            potential_features = [col for col in df.columns if col not in exclude_cols]
        X_raw = df[potential_features]
        
        # 2. 強制僅保留數值型別 (int, float, bool)
        # LightGBM 不接受 object / string
        X = X_raw.select_dtypes(include=[np.number, bool])
        
        # 記錄被排除的欄位 (Debug用)
        dropped = set(X_raw.columns) - set(X.columns)
        if dropped:
            print(f"⚠ 自動排除非數值欄位: {dropped}")
            
        feature_cols = X.columns.tolist()
        self.training_feature_names = feature_cols
        self.model_metadata = self._build_model_metadata(feature_cols, metadata)
        self._warn_feature_group_degradation(feature_cols, metadata)
        
        print(f"✓ 準備訓練資料: {len(X)} 筆, {len(feature_cols)} 個特徵")
        return X, y, feature_cols

    def apply_sealed_oos_split(self, df: pd.DataFrame, config: SealedOOSConfig) -> pd.DataFrame:
        """切出封閉 OOS 視窗，只回傳可用於訓練/調參/校準的 development frame。"""
        if not config.enabled:
            self.sealed_oos_metadata = {"enabled": False}
            print("⚠ Sealed OOS 已停用，本次訓練不切封閉測試視窗")
            return df

        split = build_sealed_oos_split(df, config, horizon=self.horizon, threshold=self.threshold)
        self.sealed_oos_metadata = split.metadata
        print(
            "🔒 Sealed OOS 已鎖定: "
            f"train={split.metadata['train_start_date']}~{split.metadata['train_end_date']} "
            f"embargo_days={split.metadata['embargo_trade_days']} "
            f"sealed={split.metadata['sealed_start_date']}~{split.metadata['sealed_end_date']} "
            f"sealed_rows={split.metadata['sealed_rows']}"
        )
        return split.development
    
    def walk_forward_train(self, df: pd.DataFrame, n_splits: int = 5):
        """
        時序滾動驗證
        依據用戶需求：訓練窗口 24-36 個月 (簡化版：使用 TimeSeriesSplit 自動切分)
        """
        print(f"⏳ 開始 Walk-forward Validation (n_splits={n_splits})...")
        
        df = self._with_trade_date(df)
        dates = self._unique_trade_dates(df)
        
        tscv = TimeSeriesSplit(n_splits=n_splits)
        metrics = []
        
        # 準備資料
        X_all, y_all, feature_cols = self.prepare_train_data(df)
        
        for i, (train_idx, val_idx) in enumerate(tscv.split(dates)):
            train_dates = dates[train_idx]
            val_dates = dates[val_idx]
            train_dates = self._purge_train_dates(train_dates, val_dates)
            if len(train_dates) == 0:
                print(f"⚠ Fold {i+1} 訓練資料被 purge 後為空，跳過")
                continue
            
            d_train = df[df['trade_date'].isin(train_dates)]
            d_val = df[df['trade_date'].isin(val_dates)]
            
            # 使用 prepare_train_data 確保欄位一致
            X_train, y_train, _ = self.prepare_train_data(d_train)
            X_val, y_val, _ = self.prepare_train_data(d_val)
            
            params = self.best_params if self.best_params else self._get_default_params()
            
            lgb_train = lgb.Dataset(X_train, label=y_train)
            lgb_val = lgb.Dataset(X_val, label=y_val, reference=lgb_train)
            
            # 訓練分類模型
            model = lgb.train(
                params,
                lgb_train,
                num_boost_round=1000,
                valid_sets=[lgb_train, lgb_val],
                valid_names=['train', 'valid'],
                callbacks=[lgb.early_stopping(50), lgb.log_evaluation(0)]
            )
            
            # 預測機率
            preds_prob = model.predict(X_val)
            
            # 評估指標: AUC & LogLoss
            try:
                auc = roc_auc_score(y_val, preds_prob)
                loss = log_loss(y_val, preds_prob)
            except ValueError:
                auc = 0
                loss = 999
            
            metrics.append({'auc': auc, 'logloss': loss})
            print(f"  Fold {i+1} ({pd.Timestamp(val_dates[0]).date()}~{pd.Timestamp(val_dates[-1]).date()}): AUC={auc:.4f}, LogLoss={loss:.4f}")
            
        avg_auc = np.mean([m['auc'] for m in metrics])
        print(f"✅ 驗證完成. 平均 AUC: {avg_auc:.4f}")
        
        # 最終全量訓練 (含校準拆分)
        self.train_final_model(X_all, y_all, feature_cols)
        return metrics

    def _with_trade_date(self, df: pd.DataFrame) -> pd.DataFrame:
        """建立交易日欄位，所有 walk-forward 切分都以日頻為準。"""
        if 'date' not in df.columns:
            raise ValueError("訓練資料缺少 date 欄位")
        result = df.copy()
        result['date'] = pd.to_datetime(result['date'])
        result['trade_date'] = result['date'].dt.normalize()
        sort_cols = ['trade_date', 'stock_id'] if 'stock_id' in result.columns else ['trade_date']
        return result.sort_values(sort_cols).copy()

    def _unique_trade_dates(self, df: pd.DataFrame) -> np.ndarray:
        """取得排序後的唯一交易日，避免同日不同 timestamp 被拆進不同 fold。"""
        if 'trade_date' not in df.columns:
            df = self._with_trade_date(df)
        return df['trade_date'].drop_duplicates().sort_values().to_numpy()

    def _ensure_unique_trade_keys(self, df: pd.DataFrame, dataset_name: str) -> None:
        """確認日頻模型資料不含同股同交易日多筆資料。"""
        required = {'trade_date', 'stock_id'}
        if df.empty or not required.issubset(df.columns):
            return
        duplicate_mask = df.duplicated(['trade_date', 'stock_id'], keep=False)
        if not duplicate_mask.any():
            return
        sample = (
            df.loc[duplicate_mask, ['trade_date', 'stock_id']]
            .drop_duplicates()
            .head(5)
            .assign(trade_date=lambda x: x['trade_date'].dt.strftime('%Y-%m-%d'))
            .to_dict('records')
        )
        raise ValueError(f"{dataset_name} 含同股同交易日多筆資料，請先聚合成日頻資料: {sample}")

    def _purge_train_dates(self, train_dates, val_dates):
        """排除 train fold 尾端可能引用 validation 價格的日期。"""
        if len(train_dates) == 0 or len(val_dates) == 0:
            return train_dates
        train_dates = train_dates[train_dates < val_dates[0]]
        if len(train_dates) <= self.horizon:
            return train_dates[:0]
        return train_dates[:-self.horizon]

    def _print_feature_contract_summary(self) -> None:
        if self.feature_metadata is None:
            return
        group_sizes = {name: len(group.columns) for name, group in self.feature_metadata.feature_groups.items()}
        print(
            "✓ M4 feature groups: "
            f"{group_sizes}, fundamental_cache_coverage={self.feature_metadata.fundamental_cache_coverage:.1%}"
        )

    def _build_model_metadata(
        self,
        feature_names: list[str],
        metadata: FeatureFrameMetadata | None = None,
    ) -> dict[str, Any]:
        metadata = metadata or self.feature_metadata
        feature_set = set(feature_names)
        result: dict[str, Any] = {
            "horizon": self.horizon,
            "threshold": self.threshold,
            "feature_names": feature_names,
            "feature_count": len(feature_names),
            "feature_groups": {},
            "used_feature_groups": {},
            "notes": [],
        }
        if self.sealed_oos_metadata is not None:
            result["sealed_oos"] = self.sealed_oos_metadata
        if metadata is None:
            result["notes"].append("未提供 M4 feature metadata，使用舊版數值欄位選取。")
            return result
        metadata_dict = metadata.to_dict()
        result["feature_groups"] = metadata_dict["feature_groups"]
        result["fundamental_cache_coverage"] = metadata.fundamental_cache_coverage
        result["notes"].extend(metadata.notes)
        for group_name, group in metadata.feature_groups.items():
            used = [col for col in group.columns if col in feature_set]
            result["used_feature_groups"][group_name] = used
        return result

    def _warn_feature_group_degradation(
        self,
        feature_names: list[str],
        metadata: FeatureFrameMetadata | None = None,
    ) -> None:
        metadata = metadata or self.feature_metadata
        if metadata is None:
            return
        used_groups = self.model_metadata.get("used_feature_groups", {})
        missing_groups = [name for name in ("technical", "event", "fundamental") if not used_groups.get(name)]
        if missing_groups:
            print(f"⚠ M4 feature group 未進入候選特徵: {missing_groups}")
        fundamental_cols = used_groups.get("fundamental", [])
        if not fundamental_cols:
            print(
                "⚠ 基本面 cache 覆蓋率未達模型 gate 或無可用基本面特徵，"
                "本次訓練不使用 fundamental_* 欄位但保留 metadata。"
            )
        else:
            print(f"✓ 基本面特徵已納入候選欄位: {len(fundamental_cols)} 欄")

    def optimize_params(self, X: pd.DataFrame, y: pd.Series, n_trials: int = 20, dates: pd.Series | None = None):
        """Optuna 超參數調優"""
        print(f"⏳ 開始 Optuna 超參數調優 (trials={n_trials})...")
        
        # 啟動 MLflow 實驗
        mlflow.set_experiment("Agent_B_Stock_Prediction")
        
        def objective(trial):
            with mlflow.start_run(nested=True, run_name=f"Trial_{trial.number}"):
                param = {
                    'objective': 'binary',
                    'metric': 'auc',
                    'verbosity': -1,
                    'boosting_type': 'gbdt',
                    'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.1),
                    'num_leaves': trial.suggest_int('num_leaves', 20, 150),
                    'feature_fraction': trial.suggest_float('feature_fraction', 0.5, 1.0),
                    'bagging_fraction': trial.suggest_float('bagging_fraction', 0.5, 1.0),
                    'bagging_freq': trial.suggest_int('bagging_freq', 1, 10),
                    'min_child_samples': trial.suggest_int('min_child_samples', 5, 100),
                    'lambda_l1': trial.suggest_float('lambda_l1', 1e-8, 10.0, log=True),
                    'lambda_l2': trial.suggest_float('lambda_l2', 1e-8, 10.0, log=True),
                    'is_unbalance': True 
                }
                
                # 紀錄參數到 MLflow
                mlflow.log_params(param)
                
                train_size = int(len(X) * 0.8)
                X_t, y_t = X.iloc[:train_size], y.iloc[:train_size]
                X_v, y_v = X.iloc[train_size:], y.iloc[train_size:]
                if dates is not None and not X_t.empty and not X_v.empty:
                    date_series = pd.to_datetime(dates.loc[X.index]).dt.normalize()
                    train_dates = date_series.loc[X_t.index].sort_values().unique()
                    val_dates = date_series.loc[X_v.index].sort_values().unique()
                    purged_dates = set(self._purge_train_dates(train_dates, val_dates))
                    keep_mask = date_series.loc[X_t.index].isin(purged_dates)
                    X_t, y_t = X_t.loc[keep_mask], y_t.loc[keep_mask]
                if X_t.empty or X_v.empty:
                    return 0
                
                dtrain = lgb.Dataset(X_t, label=y_t)
                dval = lgb.Dataset(X_v, label=y_v, reference=dtrain)
                
                model = lgb.train(param, dtrain, num_boost_round=500, 
                                  valid_sets=[dval], callbacks=[lgb.early_stopping(30), lgb.log_evaluation(0)])
                
                preds = model.predict(X_v)
                try:
                    score = roc_auc_score(y_v, preds)
                except:
                    score = 0
                
                # 紀錄結果指標到 MLflow
                mlflow.log_metric("auc", score)
                
                return score # Maximize AUC

        study = optuna.create_study(direction='maximize')
        study.optimize(objective, n_trials=n_trials)
        
        self.best_params = study.best_params
        self.best_params.update({'objective': 'binary', 'metric': 'auc', 'verbosity': -1, 'is_unbalance': True})
        
        print(f"✅ 最佳參數: {self.best_params}")
        return self.best_params

    def train_final_model(self, X: pd.DataFrame, y: pd.Series, feature_names: list):
        """訓練最終模型 + 機率校準 (Probability Calibration)"""
        self.training_feature_names = list(feature_names)
        self.model_metadata = self._build_model_metadata(list(feature_names))
        params = self.best_params if self.best_params else self._get_default_params()
        
        # 拆分 10% 做校準 (依時間序列，取最後 10%)
        # 因為這是 Time Series，不能隨機拆
        calib_size = int(len(X) * 0.1)
        train_size = len(X) - calib_size
        
        X_train = X.iloc[:train_size]
        y_train = y.iloc[:train_size]
        X_calib = X.iloc[train_size:]
        y_calib = y.iloc[train_size:]
        
        print(f"⏳ 訓練最終模型 (Train: {len(X_train)}, Calibration: {len(X_calib)})...")
        
        # 啟動 MLflow 父運行
        with mlflow.start_run(run_name="Final_Model_Training"):
            mlflow.log_params(params)
            mlflow.lightgbm.autolog()
            
            lgb_train = lgb.Dataset(X_train, label=y_train, feature_name=feature_names)
            self.model = lgb.train(params, lgb_train, num_boost_round=500)
            
            # 進行機率校準 (Isotonic Regression)
            print("🔧 執行 Isotonic Probability Calibration...")
            raw_probs = self.model.predict(X_calib)
            self.calibrator = IsotonicRegression(out_of_bounds='clip')
            self.calibrator.fit(raw_probs, y_calib)
            
            # 記錄模型到 MLflow
            mlflow.lightgbm.log_model(self.model, "model")
            print(f"✅ 最終模型已紀錄至 MLflow")
            
        return self.model

    def _get_default_params(self):
        return {
            'objective': 'binary',
            'metric': 'auc',
            'is_unbalance': True,
            'verbose': -1
        }

    def save_model(self, filename: str = "latest_lgbm.pkl"):
        """儲存模型與校準器"""
        if self.model is None: raise ValueError("尚未訓練模型")
        model_path = self.model_dir / filename
        
        # 儲存字典包含模型與校準器
        save_obj = {
            'model': self.model,
            'calibrator': self.calibrator,
            'feature_names': self.model.feature_name(),
            'metadata': self.model_metadata,
        }
        
        with open(model_path, 'wb') as f:
            pickle.dump(save_obj, f)
        print(f"✓ 模型與校準器已儲存至: {model_path}")

    def plot_feature_importance(self, top_n: int = 30):
        """繪製特徵重要性 (Gain)"""
        importance = self.model.feature_importance(importance_type='gain')
        features = self.model.feature_name()
        fi_df = pd.DataFrame({'feature': features, 'importance': importance}).sort_values('importance', ascending=False)
        
        plt.figure(figsize=(12, 10))
        sns.barplot(data=fi_df.head(top_n), x='importance', y='feature', palette='magma')
        plt.title(f'Top {top_n} 模型特徵重要性 (Gain)')
        plt.tight_layout()
        plt.savefig(self.artifact_dir / "feature_importance.png", dpi=150)
        plt.close()
        print(f"✓ 已產出特徵重要性圖表")
        return fi_df
        
    def plot_shap_summary(self, X_sample: pd.DataFrame = None, sample_size: int = 1000):
        """繪製 SHAP Summary Plot (Scikit-Learn Skill Integration)"""
        if self.model is None:
            print("⚠ 模型尚未訓練，無法繪製 SHAP")
            return

        print("⏳ 計算 SHAP values...")
        try:
            # 使用 TreeExplainer (針對 LightGBM 優化)
            explainer = shap.TreeExplainer(self.model)
            
            if X_sample is None:
                # 若未提供，嘗試自動載入一部分資料
                try:
                    df = self.load_features()
                    X, _, _ = self.prepare_train_data(df)
                    # 隨機採樣以加速
                    if len(X) > sample_size:
                        X_sample = X.sample(n=sample_size, random_state=42)
                    else:
                        X_sample = X
                except Exception as e:
                    print(f"⚠ 無法自動載入資料供 SHAP 分析: {e}")
                    return

            shap_values = explainer.shap_values(X_sample)
            
            # LightGBM binary classification returns list of arrays [class0, class1] or just class1 depending on version
            # New LightGBM versions with SHAP might return array. Handle carefully.
            if isinstance(shap_values, list):
                # Binary classification: index 1 is positive class
                shap_vals_target = shap_values[1]
            else:
                shap_vals_target = shap_values

            plt.figure(figsize=(10, 8))
            shap.summary_plot(shap_vals_target, X_sample, show=False)
            plt.title("SHAP Summary Plot (Top Features)")
            plt.tight_layout()
            
            save_path = self.artifact_dir / "shap_summary.png"
            plt.savefig(save_path, dpi=150)
            plt.close()
            print(f"✓ 已產出 SHAP Summary Plot: {save_path}")
            
        except Exception as e:
            print(f"❌ SHAP 分析失敗: {e}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Agent B LightGBM 訓練")
    parser.add_argument("--config", default="config/automation.yaml", help="讀取 retrain / sealed_oos 設定")
    parser.add_argument("--data-dir", default="data/clean")
    parser.add_argument("--model-dir", default="models")
    parser.add_argument("--artifact-dir", default="artifacts")
    parser.add_argument("--horizon", type=int, default=10)
    parser.add_argument("--threshold", type=float, default=0.05)
    parser.add_argument("--optuna-trials", type=int, default=None)
    return parser.parse_args()


def _load_retrain_config(config_path: str | Path) -> dict[str, Any]:
    path = Path(config_path)
    if not path.exists():
        return {}
    config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    retrain = config.get("retrain") if isinstance(config.get("retrain"), dict) else {}
    return retrain


def main():
    args = parse_args()
    retrain_config = _load_retrain_config(args.config)
    optuna_trials = args.optuna_trials
    if optuna_trials is None:
        optuna_trials = int(retrain_config.get("optuna_trials", 20))
    sealed_config = SealedOOSConfig.from_mapping(
        retrain_config.get("sealed_oos") if isinstance(retrain_config.get("sealed_oos"), dict) else {},
        horizon=args.horizon,
    )

    print("🚀 Agent B 模型優化訓練啟動 (Mini版 - Classification)...")
    trainer = LightGBMTrainer(
        data_dir=args.data_dir,
        model_dir=args.model_dir,
        artifact_dir=args.artifact_dir,
        horizon=args.horizon,
        threshold=args.threshold,
    )
    
    try:
        # 1. 準備資料
        df = trainer.load_features()
        # 使用 LabelGenerator 生成 D+1 標籤
        df = trainer.generate_labels(df)
        df_train = trainer.apply_sealed_oos_split(df, sealed_config)
        
        # 2. 自動調優；sealed / embargo 已從 df_train 排除
        X, y, feature_cols = trainer.prepare_train_data(df_train)
        trainer.optimize_params(X, y, n_trials=optuna_trials, dates=df_train['date'])
        
        # 3. 時序滾動驗證與最終訓練；最終模型也只吃 development frame
        trainer.walk_forward_train(df_train)
        
        # 4. 儲存與產出分析
        trainer.save_model()
        trainer.plot_feature_importance()
        
        print("\n✨ 模型優化流程已圓滿完成！")
        
    except Exception as e:
        print(f"\n❌ 流程中斷: {e}")
        import traceback; traceback.print_exc()
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
