
"""
ETL 階段：基本面與營收整合 (Fundamental Stage)
整合真實營收資料；缺資料時保留缺值，不產生虛擬基本面資料。
"""
import pandas as pd
from .base import PipelineStage
from app.fundamental_data import FundamentalData

class FundamentalStage(PipelineStage):
    def execute(self, data: pd.DataFrame, context: dict) -> pd.DataFrame:
        fundamental = FundamentalData(data)
        orchestrator = context.get('orchestrator')
        
        self.logger.info("整合基本面與營收資料...")
        try:
            if orchestrator is None or not hasattr(orchestrator, "twse"):
                self.logger.warning("找不到營收資料來源，保留營收欄位缺值")
                context['stats']['revenue'] = {
                    'status': 'missing_source',
                    'dummy_used': False,
                }
                return fundamental.merge_revenue_data(pd.DataFrame())

            rev_start = data['date'].min().strftime('%Y-%m-%d')
            rev_end = data['date'].max().strftime('%Y-%m-%d')
            
            revenue_df = orchestrator.twse.fetch_revenue_batch(
                start_date=rev_start,
                end_date=rev_end,
                save_to_disk=True
            )
            
            if not revenue_df.empty:
                data = fundamental.merge_revenue_data(revenue_df)
                self.logger.info(f"✅ 已整合真實營收資料，共 {len(revenue_df)} 筆")
                revenue_coverage = (data['revenue_yoy'].notna().sum() / len(data)) * 100
                context['stats']['revenue'] = {
                    'total_records': len(revenue_df),
                    'coverage_rate': f"{revenue_coverage:.2f}%"
                }
            else:
                self.logger.warning("營收資料為空，保留營收欄位缺值")
                data = fundamental.merge_revenue_data(pd.DataFrame())
                context['stats']['revenue'] = {
                    'status': 'empty',
                    'dummy_used': False,
                    'coverage_rate': '0.00%',
                }
        except Exception as e:
            self.logger.error(f"營收處理失敗: {e}，保留營收欄位缺值")
            data = fundamental.merge_revenue_data(pd.DataFrame())
            context['stats']['revenue'] = {
                'status': 'error',
                'dummy_used': False,
                'error': str(e),
            }
            
        return data
