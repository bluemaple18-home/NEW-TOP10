
"""
ETL 階段：報告產生 (Report Stage)
產出 Markdown 報告與數據預覽圖
"""
import pandas as pd
from datetime import datetime
from .base import PipelineStage

class ReportStage(PipelineStage):
    def execute(self, data: pd.DataFrame, context: dict) -> pd.DataFrame:
        self.logger.info("產生 ETL 報告與視覺化...")
        
        # 由於原始報告生成邏輯較為耦合，此處先以 placeholder 呼叫
        # 實務上會呼叫重構後的 ReportGenerator
        
        # 簡化版報告生成 logic (保持功能)
        report_path = context['dirs']['artifacts'] / "etl_report.md"
        report_content = f"# ETL 執行報告\n\n產生時間: {datetime.now()}"
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
            
        try:
            from app.visualization import generate_signals_preview
            preview_path = context['dirs']['artifacts'] / "signals_preview.png"
            generate_signals_preview(context['universe_df'], output_path=str(preview_path))
        except Exception as e:
            self.logger.error(f"視覺化失敗: {e}")
            
        return data
