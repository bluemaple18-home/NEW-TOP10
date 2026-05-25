
"""
ETL 階段：風險過濾 (Filter Stage)
套用各類風險過濾器，產出 Universe 股票池
"""
import pandas as pd
from .base import PipelineStage
from app.risk_filter import RiskFilter

class FilterStage(PipelineStage):
    def execute(self, data: pd.DataFrame, context: dict) -> pd.DataFrame:
        risk_filter = RiskFilter(data)
        
        suspended_list = context.get('suspended_list', [])
        universe = risk_filter.apply_all_filters(
            suspended_list=suspended_list,
            min_listing_days=60,
            min_avg_value=10_000_000,
            min_price=10.0
        )
        
        universe_path = context['dirs']['clean'] / "universe.parquet"
        universe.to_parquet(universe_path, index=False)
        self.logger.info(f"已存入 {universe_path}")
        
        context['universe_df'] = universe
        context['stats']['filter'] = risk_filter.get_filter_report().to_dict('records')
        
        return data
