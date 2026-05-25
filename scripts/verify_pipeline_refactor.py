
"""
ETL 管道驗證腳本
測試原子化後的管道是否能正確執行
"""
import logging
from app.pipeline import (
    ETLPipeline, FetchStage, IndicatorStage, 
    FundamentalStage, EventStage, FilterStage, ReportStage
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_pipeline():
    # 建立管道並加入階段 (可以自定義流程)
    pipeline = ETLPipeline(data_dir="data", artifacts_dir="artifacts")
    
    pipeline.add_stage(FetchStage()) \
            .add_stage(IndicatorStage()) \
            .add_stage(FundamentalStage()) \
            .add_stage(EventStage()) \
            .add_stage(FilterStage()) \
            .add_stage(ReportStage())
            
    # 執行一小段時間範圍作為測試
    print("啟動管道測試...")
    # 為了測試，設定極短範圍 (例如最近 14 天)
    from datetime import datetime, timedelta
    end = datetime.now().strftime('%Y-%m-%d')
    start = (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%d')
    
    try:
        pipeline.run(start_date=start, end_date=end)
        print("✅ 管道執行測試成功！")
    except Exception as e:
        print(f"❌ 管道執行測試失敗: {e}")

if __name__ == "__main__":
    test_pipeline()
