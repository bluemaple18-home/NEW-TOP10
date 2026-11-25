
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
        # 技術指標的缺值統計先轉成純數值；量能計算不會改寫此獨立工作表。
        tech_ind = TechnicalIndicators(data)
        data = tech_ind.calculate_all_indicators()
        tech_missing = tech_ind.get_missing_rate().to_dict()

        # 量能計算器已取得獨立工作表；釋放舊表的計算器及本地別名後才開始計算。
        vol_ind = VolumeIndicators(data)
        del tech_ind, data
        data = vol_ind.calculate_all_volume_indicators()

        context['stats']['indicators'] = {
            'tech_missing': tech_missing,
            'vol_missing': vol_ind.get_missing_rate().to_dict()
        }
        # 下游報告只使用 universe_df，不再把整張中間表存入 context。
        return data
