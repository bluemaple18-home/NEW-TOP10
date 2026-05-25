
"""
ETL 階段：指標計算 (Indicator Stage)
整合技術指標與量能指標
"""
import pandas as pd
from .base import PipelineStage
from app.indicators import TechnicalIndicators
from app.volume_indicators import VolumeIndicators

class IndicatorStage(PipelineStage):
    def execute(self, data: pd.DataFrame, context: dict) -> pd.DataFrame:
        # 技術指標
        tech_ind = TechnicalIndicators(data)
        data = tech_ind.calculate_all_indicators()
        
        # 量能指標
        vol_ind = VolumeIndicators(data)
        data = vol_ind.calculate_all_volume_indicators()
        
        context['stats']['indicators'] = {
            'tech_missing': tech_ind.get_missing_rate().to_dict(),
            'vol_missing': vol_ind.get_missing_rate().to_dict()
        }
        context['tech_ind'] = tech_ind # 供報告使用
        context['vol_ind'] = vol_ind
        
        return data
