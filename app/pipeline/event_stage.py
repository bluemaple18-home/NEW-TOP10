
"""
ETL 階段：技術事件偵測 (Event Stage)
偵測突破、金叉等技術信號
"""
import pandas as pd
from .base import PipelineStage
from app.event_detector import EventDetector

class EventStage(PipelineStage):
    def execute(self, data: pd.DataFrame, context: dict) -> pd.DataFrame:
        # 指標與缺值統計已完成；事件與報告只讀特徵表，不再使用計算器。
        # 必須在事件工作表複製前釋放，避免上游中間表跨階段疊加。
        context.pop('tech_ind', None)
        context.pop('vol_ind', None)
        detector = EventDetector(data)
        events_df = detector.detect_all_events()
        # 偵測完成後只需事件結果；寫兩份 parquet 前釋放全寬工作副本。
        del detector
        
        events_path = context['dirs']['clean'] / "events.parquet"
        events_df.to_parquet(events_path, index=False)
        self.logger.info(f"已存入 {events_path}")
        
        context['events_df'] = events_df
        context['stats']['events'] = {
            'count': len(events_df.columns) - 2
        }
        
        # 特徵資料同步儲存
        features_path = context['dirs']['clean'] / "features.parquet"
        data.to_parquet(features_path, index=False)
        self.logger.info(f"已存入 {features_path}")
        
        return data
