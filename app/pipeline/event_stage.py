
"""
ETL 階段：技術事件偵測 (Event Stage)
偵測突破、金叉等技術信號
"""
import pandas as pd
from .base import PipelineStage
from app.event_detector import EventDetector

class EventStage(PipelineStage):
    def execute(self, data: pd.DataFrame, context: dict) -> pd.DataFrame:
        detector = EventDetector(data)
        events_df = detector.detect_all_events()
        
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
