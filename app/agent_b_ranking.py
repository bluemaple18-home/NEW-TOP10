
import pandas as pd
import numpy as np
import lightgbm as lgb
import yaml
import json
import os
from pathlib import Path
from datetime import datetime, timezone
import pickle
import logging
import shap

# 新增：報告生成器
try:
    from report_generator import StockReportGenerator
except ImportError:
    from app.report_generator import StockReportGenerator

try:
    from app.trading import (
        MarketRegimeService,
        PortfolioPolicy,
        PortfolioRiskOverlay,
        PortfolioRiskOverlayConfig,
        RankingPolicy,
        TradePlanService,
    )
except ImportError:
    from trading import (
        MarketRegimeService,
        PortfolioPolicy,
        PortfolioRiskOverlay,
        PortfolioRiskOverlayConfig,
        RankingPolicy,
        TradePlanService,
    )

try:
    from app.modeling.feature_contract import load_m4_feature_frame
except ImportError:
    from modeling.feature_contract import load_m4_feature_frame

# 設定日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class StockRanker:
    """股票排名器 (Advanced版)：融合校準後的模型機率、規則分數與 SHAP 解釋"""
    
    # 技術指標中英對照表
    SIGNAL_TRANSLATIONS = {
        'break_20d_high': '突破20日新高',
        'rebound_ma20': '月線支撐反彈',
        'close_above_bb_mid': '站上布林中軌',
        'macd_bullish_cross': 'MACD黃金交叉',
        'gap_up_close_strong': '跳空強勢收紅',
        'volume_spike': '成交量暴增',
        'lose_20d_low': '跌破20日低點',
        'ma5_cross_ma20_up': '5日線突破月線',
        'ma5_cross_ma20_down': '5日線跌破月線',
        'rsi_oversold_bounce': 'RSI超賣反彈',
        'rsi_rebound_from_40': 'RSI 40 反彈',
        'rsi_break_below_50': 'RSI 跌破50',
        'kd_golden_cross': 'KD黃金交叉',
        'break_60d_high': '突破60日新高',
        'volume_ma_breakout': '量能突破均量',
        'bullish_engulfing': '多頭吞噬K線',
        'hammer': '錘子線型態',
        'morning_star': '晨星反轉',
        'macd_bearish_cross': 'MACD死亡交叉',
        'long_upper_shadow': '長上影線',
        'close_below_bb_mid': '跌破布林中軌',
        'candle_doji': '十字星',
        'candle_dragonfly_doji': '蜻蜓十字',
        'candle_tombstone_doji': '墓碑十字',
        'candle_hammer': '錘子線',
        'candle_shooting_star': '流星線',
        'candle_bull_engulfing': '多方吞噬',
        'candle_bear_engulfing': '空方吞噬',
        'candle_morning_star': '晨星反轉',
        'candle_evening_star': '黃昏星反轉',
        'candle_3white': '紅三兵',
        'candle_3black': '黑三兵',
        'td_buy_setup': 'TD買九',
        'td_sell_setup': 'TD賣九',
        'pattern_w_bottom': 'W底突破',
        'pattern_m_top': 'M頭跌破',
    }
    
    def __init__(
        self,
        data_dir: str = "data/clean",
        model_dir: str = "models",
        artifact_dir: str = "artifacts",
        config_path: str = "config/signals.yaml",
        generate_report: bool = True,
        explain_top_n: int = 20,
    ):
        """
        初始化排名器
        """
        self.data_dir = Path(data_dir)
        self.model_dir = Path(model_dir)
        self.artifact_dir = Path(artifact_dir)
        self.config_path = Path(config_path)
        self.generate_report = generate_report
        self.explain_top_n = explain_top_n
        self.model = None
        self.calibrator = None
        self.market_regime_service = MarketRegimeService()
        self.trade_plan_service = TradePlanService()
        
        # 載入設定
        self.config = self._load_config()
        self.portfolio_overlay = PortfolioRiskOverlay(
            PortfolioRiskOverlayConfig.from_mapping(self.config.get("portfolio_risk_overlay"))
        )
        self.ranking_policy = RankingPolicy(self.trade_plan_service, portfolio_overlay=self.portfolio_overlay)
        self.portfolio_policy = PortfolioPolicy(portfolio_overlay=self.portfolio_overlay)
        self.weights = self.config['scoring']['weights']
        # Alpha: 模型分數權重 (預設 0.5)
        self.alpha = self.config['scoring'].get('alpha', 0.5)
        self.top_n = 10
        self.production_overlay_config = self.config.get("production_ranking_overlay") or {}
        
        # 建立必要目錄
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_config(self):
        """載入訊號設定"""
        if not self.config_path.exists():
            logger.warning(f"設定檔 {self.config_path} 不存在，使用預設值")
            return {
                'scoring': {
                    'weights': {
                         'rebound_ma20': 1.0,
                         'break_20d_high': 1.5
                    },
                    'alpha': 0.5
                }
            }
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def _ensure_unique_trade_keys(self, df: pd.DataFrame, dataset_name: str) -> None:
        """確認日頻資料不含同股同交易日多筆資料。"""
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

    def _project_root(self) -> Path:
        """依 data_dir 推估專案根目錄，讓 ranking 與 M4 訓練讀同一份 fundamentals cache。"""
        if self.data_dir.name == "clean" and self.data_dir.parent.name == "data":
            return self.data_dir.parent.parent
        if self.data_dir.name == "data":
            return self.data_dir.parent
        return Path.cwd()

    def load_model(self, filename: str = "latest_lgbm.pkl"):
        """載入模型 (支援 Old Booster or New Dict)"""
        model_path = self.model_dir / filename
        if not model_path.exists():
            raise FileNotFoundError(f"找不到模型檔案: {model_path}")
            
        with open(model_path, 'rb') as f:
            obj = pickle.load(f)
            
        if isinstance(obj, dict):
            self.model = obj['model']
            self.calibrator = obj.get('calibrator')
            logger.info(f"✓ 已載入模型與校準器: {filename}")
        else:
            self.model = obj
            self.calibrator = None
            logger.info(f"✓ 已載入舊版模型 (無校準): {filename}")

    def load_daily_data(self, date: str = None) -> tuple:
        """載入當日資料"""
        features_path = self.data_dir / "features.parquet"
        universe_path = self.data_dir / "universe.parquet"
        
        if not features_path.exists():
             raise FileNotFoundError("找不到特徵檔案 (features.parquet)")
        
        features, feature_metadata = load_m4_feature_frame(
            data_dir=self.data_dir,
            project_root=self._project_root(),
            config_path=self.config_path,
        )
        features.attrs["m4_feature_metadata"] = feature_metadata
        self._ensure_unique_trade_keys(features, "m4_feature_frame")
        
        if universe_path.exists():
            universe = pd.read_parquet(universe_path)
            if universe.empty:
                logger.warning("universe.parquet 是空的，使用 features 所有股票")
                universe = pd.DataFrame({'stock_id': features['stock_id'].unique()})
            else:
                universe['stock_id'] = universe['stock_id'].astype(str).str.strip()
        else:
            universe = pd.DataFrame({'stock_id': features['stock_id'].unique()})

        if date:
            requested_day = pd.to_datetime(date).normalize()
            if not (features['trade_date'] == requested_day).any():
                raise ValueError(f"找不到指定交易日資料: {date}")
            target_trade_date = requested_day
        else:
            target_trade_date = features['trade_date'].max()
            
        logger.info(f"載入交易日: {target_trade_date.date()}")
        
        # 優化：只保留最近 90 天以加速 Rolling 計算
        start_date = target_trade_date - pd.Timedelta(days=90)
        features = features[features['trade_date'] >= start_date].copy()
        
        # 預計算：壓力線 (近20日高點，不含今日)
        features['ref_high_20d'] = features.groupby('stock_id')['high'].transform(lambda x: x.shift(1).rolling(20).max())
        features['ref_high_60d'] = features.groupby('stock_id')['high'].transform(lambda x: x.shift(1).rolling(60).max())
        
        daily_features = features[features['trade_date'] == target_trade_date].copy()
        
        if 'date' in universe.columns:
            universe['date'] = pd.to_datetime(universe['date'])
            universe['trade_date'] = universe['date'].dt.normalize()
            self._ensure_unique_trade_keys(universe, "universe.parquet")
            daily_universe = universe[universe['trade_date'] == target_trade_date].copy()
        else:
            daily_universe = universe

        valid_stocks = daily_universe['stock_id'].unique()
        df = daily_features[daily_features['stock_id'].isin(valid_stocks)].copy()
        
        # 確保 float32 (LightGBM 需求)
        float_cols = df.select_dtypes(include=['float64']).columns
        if len(float_cols) > 0:
            df[float_cols] = df[float_cols].astype('float32')
            
        return df, features # Return both daily and history

    def calculate_scores(self, df: pd.DataFrame) -> pd.DataFrame:
        """計算總分 (含校準機率)"""
        df = df.copy()
        
        # 1. 模型預測分數 (Win Prob)
        if self.model:
            model_features = self.model.feature_name()
            missing_features = [f for f in model_features if f not in df.columns]
            missing_contract_features = [
                f for f in missing_features
                if f.startswith(("event_", "fundamental_", "candle_", "td_", "pattern_"))
            ]
            if missing_contract_features:
                raise ValueError(f"M4 推論資料缺少訓練契約欄位: {missing_contract_features[:10]}")
            for f in missing_features:
                logger.warning("模型需要欄位 %s，但 ranking frame 不存在，暫以 0 補齊", f)
                df[f] = 0
            
            X = df[model_features].apply(pd.to_numeric, errors='coerce')
            # Predict Raw
            raw_prob = self.model.predict(X)
            df['raw_prob'] = raw_prob
            
            # Calibrate if available
            if self.calibrator:
                # IsotonicRegression.predict expects 1D array
                df['model_prob'] = self.calibrator.predict(raw_prob)
            else:
                df['model_prob'] = raw_prob
        else:
            df['model_prob'] = 0.5 
            df['raw_prob'] = 0.5
            
        # 2. 規則分數 (Rule Score)
        df['rule_score'] = 0.0
        df['reasons'] = "" # Rule-based reasons
        df['positive_signals'] = ""
        df['risk_signals'] = ""
        
        for signal, weight in self.weights.items():
            event_signal_col = f"event_{signal}"
            signal_col = event_signal_col if event_signal_col in df.columns else signal
            if signal_col in df.columns:
                val = pd.to_numeric(df[signal_col], errors='coerce').fillna(0).astype(float)
                triggered = val > 0
                df.loc[triggered, 'rule_score'] += weight
                
                reason_mask = triggered
                # 使用中文翻譯（如有）
                display_name = self.SIGNAL_TRANSLATIONS.get(signal, signal)
                tag = f"{display_name}(+{weight}) " if weight > 0 else f"{display_name}({weight}) "
                
                if reason_mask.any():
                    if 'raw_signals' not in df.columns:
                        df['raw_signals'] = ""
                    df.loc[reason_mask, 'raw_signals'] = df.loc[reason_mask, 'raw_signals'] + tag
                    target_col = 'positive_signals' if weight > 0 else 'risk_signals'
                    df.loc[reason_mask, target_col] = df.loc[reason_mask, target_col] + display_name + "|"
        
        # 組裝完整模板
        # 需要計算：止損(MA20 or Low*0.95)、目標(Close*1.1)
        # 格式：
        # **🎯 操作策略**
        # • 進場：{Close}
        # • 止損：{Stop_Loss} ({Note})
        # • 目標：{Target} (+10%)
        #
        # **💡 關鍵理由**
        # • {Reason 1}
        # • {Reason 2}
        
        reasons_formatted = []
        for idx, row in df.iterrows():
            close = row.get('close', 0)
            ma20 = row.get('ma20', 0)
            
            # 策略計算
            if ma20 > 0 and close > ma20:
                stop_loss = ma20 * 0.98 # 月線下方一點點
                stop_note = "月線支撐"
            else:
                stop_loss = close * 0.95
                stop_note = "回檔5%"
                
            target_price = close * 1.1 # 預設 10% 獲利
            
            positive_sigs = [sig for sig in str(row.get('positive_signals', '')).split('|') if sig]
            risk_sigs = [sig for sig in str(row.get('risk_signals', '')).split('|') if sig]
            
            # 組合模板
            tpl = f"""**🎯 操作策略**  
• 進場：{close:.1f}  
• 止損：{stop_loss:.1f} ({stop_note})  
• 目標：{target_price:.1f} (+10%)  

**💡 關鍵理由**  
"""
            if positive_sigs:
                # 豐富化理由 (加入具體數值)
                enriched_sigs = []
                for s in positive_sigs[:3]:
                    if '突破20日' in s:
                        prior_high = row.get('ref_high_20d', 0)
                        if prior_high > 0:
                            s = f"{s} (壓力{prior_high:.1f})"
                    if '突破60日' in s:
                        prior_high = row.get('ref_high_60d', 0)
                        if prior_high > 0:
                            s = f"{s} (壓力{prior_high:.1f})"
                    if '月線支撐' in s:
                        s = f"{s} (MA20:{ma20:.1f})"
                    if '黃金交叉' in s:
                        # 標註日期 (當日)
                        date_str = row['date'].strftime('%m/%d') if 'date' in row else ""
                        s = f"{s} ({date_str})"
                    enriched_sigs.append(s)
                    
                tpl += "  \n".join([f"• {s}" for s in enriched_sigs])
            else:
                tpl += "• 綜合技術指標轉強"

            if risk_sigs:
                tpl += "\n\n**⚠ 風險提醒**  \n"
                tpl += "  \n".join([f"• {s}" for s in risk_sigs[:2]])
                
            reasons_formatted.append(tpl)
            
        df['reasons'] = reasons_formatted
        
        # 3. 規則分數正規化
        max_score = df['rule_score'].max()
        min_score = df['rule_score'].min()
        if max_score > min_score:
            df['rule_score_norm'] = (df['rule_score'] - min_score) / (max_score - min_score)
        else:
            df['rule_score_norm'] = 0.5
            
        # 4. 融合 (改用 raw_prob 以保留 AI 排序能力)
        df['final_score'] = self.alpha * df['raw_prob'] + (1 - self.alpha) * df['rule_score_norm']
        return df.sort_values('final_score', ascending=False)
        
    def _enrich_with_shap(self, df: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
        """為 Top N 股票增加 SHAP AI 解釋"""
        if self.model is None: return df
        
        # 只取前 N 名做解釋 (加速)
        top_df = df.head(top_n).copy()
        
        try:
            model_features = self.model.feature_name()
            X_top = top_df[model_features]
            
            # 建立 Explainer (TreeExplainer)
            explainer = shap.TreeExplainer(self.model)
            shap_values = explainer.shap_values(X_top)
            
            # shap_values 可能是 list (Binary case sometimes returns [neg, pos])
            if isinstance(shap_values, list):
                shap_values = shap_values[1] # 取 Positive class contribution
                
            # 為每一列生成 "AI Reason"
            ai_reasons = []
            for i in range(len(top_df)):
                # 找出貢獻最大的前 3 個特徵
                vals = shap_values[i]
                # sort indices
                top_indices = np.argsort(np.abs(vals))[-3:][::-1] # absolute value biggest 3
                
                reason_parts = []
                for idx in top_indices:
                    feat_name = model_features[idx]
                    contrib = vals[idx]
                    # 只顯示有意義的貢獻 (> 0.01 或 < -0.01 margin)
                    if abs(contrib) > 0.01:
                        sign = "+" if contrib > 0 else ""
                        reason_parts.append(f"{feat_name}({sign}{contrib:.2f})")
                
                if reason_parts:
                    ai_reasons.append(" | AI: " + " ".join(reason_parts))
                else:
                    ai_reasons.append("")
            
            top_df['reasons'] = top_df['reasons'] + pd.Series(ai_reasons, index=top_df.index)
            
            # 更新回原始 DF
            df.loc[top_df.index, 'reasons'] = top_df['reasons']
            
        except Exception as e:
            logger.warning(f"SHAP 解釋生成失敗: {e}")

        return df

    def _production_overlay_enabled(self) -> bool:
        """判斷正式 ranking 是否啟用 K overlay。"""
        env_value = os.environ.get("TOP10_PRODUCTION_RANKING_OVERLAY")
        enabled = self.production_overlay_config.get("enabled") is True
        approved = self.production_overlay_config.get("promotion_review_approved") is True
        if env_value is not None:
            env_enabled = env_value.strip().lower() in {"1", "true", "yes", "on"}
            if env_enabled and not approved:
                logger.warning("production ranking overlay requested but promotion_review_approved=false; keeping overlay disabled")
            return env_enabled and enabled and approved
        return enabled and approved

    def _production_overlay_keep_count(self) -> int:
        keep = int(self.production_overlay_config.get("keep_production_count", 9))
        return max(1, min(self.top_n, keep))

    def _comparison_keep_counts(self) -> list[int]:
        configured = self.production_overlay_config.get("comparison_keep_counts", [8])
        result = []
        for item in configured:
            try:
                keep = int(item)
            except (TypeError, ValueError):
                continue
            if 1 <= keep <= self.top_n and keep not in result:
                result.append(keep)
        return result

    def _latest_market_regime_history_path(self) -> Path | None:
        artifacts_dir = self.artifact_dir if self.artifact_dir.name == "artifacts" else self._project_root() / "artifacts"
        matches = sorted(artifacts_dir.glob("market_regime_history_????-??-??.json"))
        return matches[-1] if matches else None

    def _detailed_market_regime_label(self, date_text: str) -> tuple[str, Path | None]:
        """讀取 research detailed regime；缺資料時回 UNKNOWN，但不阻塞 ranking。"""
        path = self._latest_market_regime_history_path()
        if path is None or not path.exists():
            return "UNKNOWN", path
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - regime history 是輔助訊號，失敗不可中斷正式排名。
            logger.warning("讀取 market regime history 失敗: %s", exc)
            return "UNKNOWN", path
        for row in payload.get("rows", []):
            if str(row.get("trade_date")) == date_text and row.get("regime_label"):
                return str(row["regime_label"]), path
        return "UNKNOWN", path

    def _percentile(self, series: pd.Series, ascending: bool = True) -> pd.Series:
        values = pd.to_numeric(series, errors="coerce")
        return values.rank(pct=True, ascending=ascending).fillna(0.5).clip(0, 1)

    def _industry_factor_columns(self, history_df: pd.DataFrame, target_date: str) -> pd.DataFrame:
        """產生同產業/同族群 leave-one-out 強度，供 K overlay 排序使用。"""
        industry_path = self._project_root() / "data" / "reference" / "stock_industry_map.csv"
        if history_df.empty or not industry_path.exists():
            return pd.DataFrame(columns=["stock_id"])

        history = history_df.copy()
        history["stock_id"] = history["stock_id"].astype(str).str.strip().str.zfill(4)
        date_col = "trade_date" if "trade_date" in history.columns else "date"
        history[date_col] = pd.to_datetime(history[date_col], errors="coerce").dt.normalize()
        industry = pd.read_csv(industry_path, dtype={"stock_id": str})
        industry["stock_id"] = industry["stock_id"].astype(str).str.strip().str.zfill(4)
        keep = [col for col in ["stock_id", "sector_name", "industry_name"] if col in industry.columns]
        if "stock_id" not in keep:
            return pd.DataFrame(columns=["stock_id"])
        history = history.merge(industry[keep].drop_duplicates("stock_id"), on="stock_id", how="left")
        history["sector_name"] = history.get("sector_name", "unknown").fillna("unknown")
        history["industry_name"] = history.get("industry_name", "unknown").fillna("unknown")
        history["_daily_return"] = history.groupby("stock_id", sort=False)["close"].pct_change()
        if "ma20" in history.columns:
            close = pd.to_numeric(history["close"], errors="coerce")
            ma20 = pd.to_numeric(history["ma20"], errors="coerce")
            history["_above_ma20"] = (close > ma20).astype(float)
        else:
            history["_above_ma20"] = np.nan

        for group_col in ["sector_name", "industry_name"]:
            prefix = "sector" if group_col == "sector_name" else "industry"
            for value_col, suffix in [("_daily_return", "return_1d_loo"), ("_above_ma20", "breadth_ma20_loo")]:
                values = pd.to_numeric(history[value_col], errors="coerce")
                grouped = history.assign(_value=values).groupby([date_col, group_col], dropna=False)["_value"]
                sums = grouped.transform("sum")
                counts = grouped.transform("count")
                peers = counts - 1
                history[f"{prefix}_{suffix}"] = (sums - values) / peers.where(peers > 0)

        target_day = pd.to_datetime(target_date).normalize()
        daily = history[history[date_col] == target_day].copy()
        keep_cols = [
            "stock_id",
            "sector_return_1d_loo",
            "sector_breadth_ma20_loo",
            "industry_return_1d_loo",
            "industry_breadth_ma20_loo",
        ]
        return daily[[col for col in keep_cols if col in daily.columns]].drop_duplicates("stock_id")

    def _feature_group_shadow_score(self, ranked_df: pd.DataFrame, history_df: pd.DataFrame, target_date: str, regime_label: str) -> pd.DataFrame:
        """依 feature-group 研究結果產生 shadow score，不覆蓋正式模型分數。"""
        df = ranked_df.copy()
        factors = self._industry_factor_columns(history_df, target_date)
        if not factors.empty:
            df["stock_id"] = df["stock_id"].astype(str).str.strip().str.zfill(4)
            df = df.merge(factors, on="stock_id", how="left")

        prediction = pd.to_numeric(df.get("prediction_score", df.get("model_prob", 0.5)), errors="coerce").fillna(0.5)
        quality = pd.to_numeric(df.get("quality_score", 0.5), errors="coerce").fillna(0.5)
        risk = pd.to_numeric(df.get("risk_penalty", 0.0), errors="coerce").fillna(0.0)
        base = prediction + quality - risk
        volume_rank = self._percentile(df.get("avg_volume_20d", pd.Series(index=df.index, dtype=float)))
        value_rank = self._percentile(df.get("avg_value_20d", pd.Series(index=df.index, dtype=float)))
        volume_heat = (volume_rank + value_rank) / 2
        industry_strength = self._percentile(df.get("industry_breadth_ma20_loo", pd.Series(index=df.index, dtype=float)))
        sector_strength = self._percentile(df.get("sector_return_1d_loo", pd.Series(index=df.index, dtype=float)))
        trend_extension = self._percentile(df.get("pct_from_low_60d", pd.Series(index=df.index, dtype=float)))
        bb_width = self._percentile(df.get("bb_width", pd.Series(index=df.index, dtype=float)))

        if regime_label == "NARROW_LEADER":
            score = base + 0.32 * industry_strength + 0.24 * sector_strength + 0.18 * volume_heat
        elif regime_label == "EARLY_REVERSAL":
            score = base + 0.32 * sector_strength + 0.22 * industry_strength + 0.18 * volume_heat
        elif regime_label == "MIXED_NEUTRAL":
            score = base - 0.30 * volume_heat + 0.18 * industry_strength - 0.12 * trend_extension
        elif regime_label == "RISK_OFF":
            score = base + 0.25 * (1 - trend_extension) + 0.20 * (1 - bb_width) + 0.14 * industry_strength
        elif regime_label == "PANIC_SELLING":
            score = base + 0.28 * volume_heat + 0.20 * (1 - bb_width) + 0.16 * sector_strength
        else:
            score = base + 0.10 * industry_strength

        df["shadow_market_regime"] = regime_label
        df["shadow_score"] = score.clip(lower=0)
        return df.sort_values("shadow_score", ascending=False)

    def _overlay_topn(self, baseline_top: pd.DataFrame, shadow_ranked: pd.DataFrame, keep_count: int) -> pd.DataFrame:
        """保留 production 前 K 檔，再由 shadow score 補滿 TopN。"""
        selected = []
        selected_ids: set[str] = set()
        baseline = baseline_top.copy().reset_index(drop=True)
        shadow = shadow_ranked.copy()
        baseline["stock_id"] = baseline["stock_id"].astype(str).str.strip().str.zfill(4)
        shadow["stock_id"] = shadow["stock_id"].astype(str).str.strip().str.zfill(4)

        for idx, (_, row) in enumerate(baseline.head(keep_count).iterrows(), start=1):
            item = row.copy()
            item["baseline_rank"] = idx
            item["production_overlay_source"] = "production_keep"
            selected.append(item)
            selected_ids.add(str(item["stock_id"]))

        for _, row in shadow.iterrows():
            stock_id = str(row["stock_id"])
            if stock_id in selected_ids:
                continue
            item = row.copy()
            baseline_match = baseline.index[baseline["stock_id"] == stock_id]
            item["baseline_rank"] = int(baseline_match[0] + 1) if len(baseline_match) else None
            item["production_overlay_source"] = "shadow_fill"
            selected.append(item)
            selected_ids.add(stock_id)
            if len(selected) >= self.top_n:
                break

        if len(selected) < self.top_n:
            for idx, (_, row) in enumerate(baseline.iterrows(), start=1):
                stock_id = str(row["stock_id"])
                if stock_id in selected_ids:
                    continue
                item = row.copy()
                item["baseline_rank"] = idx
                item["production_overlay_source"] = "production_backfill"
                selected.append(item)
                selected_ids.add(stock_id)
                if len(selected) >= self.top_n:
                    break

        result = pd.DataFrame(selected).head(self.top_n).reset_index(drop=True)
        result["rank"] = range(1, len(result) + 1)
        result["production_overlay_keep_count"] = keep_count
        return result

    def _comparison_payload(
        self,
        date_text: str,
        baseline_top: pd.DataFrame,
        final_top: pd.DataFrame,
        comparisons: dict[str, pd.DataFrame],
        detailed_regime: str,
        regime_source: Path | None,
    ) -> dict:
        baseline_ids = [str(value).zfill(4) for value in baseline_top["stock_id"].tolist()]
        final_ids = [str(value).zfill(4) for value in final_top["stock_id"].tolist()]

        def rows(frame: pd.DataFrame) -> list[dict]:
            keep_cols = ["rank", "stock_id", "stock_name", "risk_adjusted_score", "shadow_score", "production_overlay_source"]
            output = []
            for row in frame[[col for col in keep_cols if col in frame.columns]].to_dict("records"):
                normalized = {}
                for key, value in row.items():
                    if pd.isna(value):
                        normalized[key] = None
                    elif isinstance(value, float):
                        normalized[key] = round(value, 6)
                    else:
                        normalized[key] = value
                output.append(normalized)
            return output

        comparison_payload = {}
        for label, frame in comparisons.items():
            ids = [str(value).zfill(4) for value in frame["stock_id"].tolist()]
            comparison_payload[label] = {
                "top10": rows(frame),
                "added_vs_baseline": [stock_id for stock_id in ids if stock_id not in baseline_ids],
                "removed_vs_baseline": [stock_id for stock_id in baseline_ids if stock_id not in ids],
                "overlap_count": len(set(ids) & set(baseline_ids)),
            }

        return {
            "schema_version": "production-ranking-overlay.v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "ranking_date": date_text,
            "contract": {
                "production_overlay_enabled": True,
                "official_ranking_variant": f"k{self._production_overlay_keep_count()}",
                "baseline_preserved": True,
                "model_changed": False,
                "retrain": False,
                "push_changed": False,
            },
            "inputs": {
                "detailed_market_regime": detailed_regime,
                "market_regime_source": str(regime_source) if regime_source else None,
            },
            "official": {
                "added_vs_baseline": [stock_id for stock_id in final_ids if stock_id not in baseline_ids],
                "removed_vs_baseline": [stock_id for stock_id in baseline_ids if stock_id not in final_ids],
                "overlap_count": len(set(final_ids) & set(baseline_ids)),
                "top10": rows(final_top),
            },
            "comparisons": comparison_payload,
        }

    def run_ranking(self, date: str = None):
        """執行排名主流程"""
        try:
            # Load Data
            df, history_df = self.load_daily_data(date)
            if df.empty:
                raise ValueError("無資料可排名")
            
            # Calc Scores
            rank_df = self.calculate_scores(df)
            market_regime = self.market_regime_service.evaluate(history_df, target_date=df['date'].max() if 'date' in df else None)
            logger.info(
                "市場狀態: %s (risk_multiplier=%.2f, breadth_ma20=%s)",
                market_regime.label,
                market_regime.risk_multiplier,
                f"{market_regime.breadth_ma20:.2%}" if market_regime.breadth_ma20 is not None else "N/A",
            )
            rank_df = self.ranking_policy.apply(rank_df, market_regime)
            
            # Enrich with SHAP (Before saving Top 10)
            if self.explain_top_n > 0:
                rank_df = self._enrich_with_shap(rank_df, top_n=self.explain_top_n)
            
            # Select Top 10
            baseline_top10 = rank_df.head(10).copy()
            baseline_top10 = self.portfolio_policy.apply(baseline_top10, market_regime)
            overlay_comparisons: dict[str, pd.DataFrame] = {}
            overlay_payload = None
            
            # Enrich with Stock Names (using local mapping)
            if 'stock_name' not in baseline_top10.columns or baseline_top10['stock_name'].isnull().any():
                logger.info("正在添加股票名稱...")
                try:
                    from app.stock_names import get_stock_name
                except ImportError:
                    from stock_names import get_stock_name
                
                names = []
                for _, row in baseline_top10.iterrows():
                    sid = str(row['stock_id'])
                    names.append(get_stock_name(sid))
                
                baseline_top10['stock_name'] = names
                # Update rank_df as well for completeness if needed (optional)

            # Save
            top10 = baseline_top10.copy()
            today_str = pd.Timestamp(baseline_top10['trade_date'].max()).strftime('%Y-%m-%d') if 'trade_date' in baseline_top10.columns else datetime.now().strftime('%Y-%m-%d')
            path = self.artifact_dir / f"ranking_{today_str}.csv"

            if self._production_overlay_enabled():
                baseline_path = self.artifact_dir / f"baseline_ranking_{today_str}.csv"
                comparison_path = self.artifact_dir / f"ranking_comparison_{today_str}.json"
                detailed_regime, regime_source = self._detailed_market_regime_label(today_str)
                shadow_ranked = self._feature_group_shadow_score(rank_df, history_df, today_str, detailed_regime)
                keep_count = self._production_overlay_keep_count()
                top10 = self._overlay_topn(baseline_top10, shadow_ranked, keep_count=keep_count)
                top10 = self.portfolio_policy.apply(top10, market_regime)
                if 'stock_name' not in top10.columns or top10['stock_name'].isnull().any():
                    try:
                        from app.stock_names import get_stock_name
                    except ImportError:
                        from stock_names import get_stock_name
                    top10['stock_name'] = [
                        name if pd.notna(name) and str(name).strip() else get_stock_name(str(stock_id))
                        for name, stock_id in zip(top10.get('stock_name', []), top10['stock_id'])
                    ]
                for comparison_keep in self._comparison_keep_counts():
                    comparison = self._overlay_topn(baseline_top10, shadow_ranked, keep_count=comparison_keep)
                    comparison = self.portfolio_policy.apply(comparison, market_regime)
                    overlay_comparisons[f"k{comparison_keep}"] = comparison
                overlay_payload = self._comparison_payload(
                    today_str,
                    baseline_top=baseline_top10,
                    final_top=top10,
                    comparisons=overlay_comparisons,
                    detailed_regime=detailed_regime,
                    regime_source=regime_source,
                )
            
            out_cols = [
                'stock_id', 'stock_name', 'close', 'risk_adjusted_score', 'final_score',
                'model_prob', 'rule_score', 'prediction_score', 'setup_score',
                'quality_score', 'risk_penalty', 'suggested_weight', 'max_position_weight',
                'gross_exposure', 'allocated_exposure', 'cash_weight', 'exposure_note', 'risk_reward',
                'market_regime', 'shadow_market_regime', 'shadow_score', 'baseline_rank',
                'production_overlay_source', 'production_overlay_keep_count', 'rank', 'reasons'
            ]
            # Ensure cols exist
            out_cols = [c for c in out_cols if c in top10.columns]
            
            if overlay_payload is not None:
                baseline_out_cols = [c for c in out_cols if c in baseline_top10.columns]
                baseline_top10[baseline_out_cols].to_csv(baseline_path, index=False, encoding='utf-8-sig')
                for label, comparison in overlay_comparisons.items():
                    comparison_out_cols = [c for c in out_cols if c in comparison.columns]
                    comparison.to_csv(self.artifact_dir / f"ranking_comparison_{label}_{today_str}.csv", index=False, encoding='utf-8-sig')
                comparison_path.write_text(json.dumps(overlay_payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
            top10[out_cols].to_csv(path, index=False, encoding='utf-8-sig')
            
            print(f"\n🏆 Top 10 選股結果 (含 AI 解釋) ({today_str}):")
            print(top10[out_cols].to_string(index=False))
            print(f"\n檔案已儲存: {path}")
            
            # 新增：生成結構化分析報告
            if self.generate_report:
                try:
                    print("\n📝 生成結構化分析報告...")
                    report_gen = StockReportGenerator(artifacts_dir=str(self.artifact_dir))
                    report_gen.generate_report(ranked_df=rank_df, features_df=history_df)
                except Exception as report_err:
                    logger.warning(f"報告生成失敗（不影響主流程）: {report_err}")
            return path
            
        except Exception as e:
            logger.error(f"排名執行失敗: {e}")
            import traceback
            traceback.print_exc()
            raise

if __name__ == "__main__":
    ranker = StockRanker()
    try:
        ranker.load_model()
    except Exception as e:
        print(f"注意: {e}")
        
    ranker.run_ranking()
    raise SystemExit(0)
