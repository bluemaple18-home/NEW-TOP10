
"""
ETL 管道調度器 (Orchestrator)
採用組合模式 (Composition) 驅動原子化的管道階段
"""
import pandas as pd
from pathlib import Path
import logging
from datetime import datetime, timedelta

class ETLPipeline:
    """整合所有原子化階段的 ETL 流程調度器"""
    
    def __init__(self, data_dir: str = "data", artifacts_dir: str = "artifacts"):
        self.data_dir = Path(data_dir)
        self.raw_dir = self.data_dir / "raw"
        self.clean_dir = self.data_dir / "clean"
        self.artifacts_dir = Path(artifacts_dir)
        
        # 建立目錄
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.clean_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger = logging.getLogger(self.__class__.__name__)
        self.context = {
            'stats': {},
            'dirs': {
                'raw': self.raw_dir,
                'clean': self.clean_dir,
                'artifacts': self.artifacts_dir
            }
        }
        self.stages = []

    def add_stage(self, stage):
        """新增一個處理階段"""
        self.stages.append(stage)
        return self

    def run(self, start_date=None, end_date=None):
        """執行完整管道"""
        self.logger.info("=" * 80)
        self.logger.info("開始執行原子化 ETL 管道")
        self.logger.info("=" * 80)
        
        # 初始化時間範圍
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=3*365)).strftime('%Y-%m-%d')
            
        self.context['start_date'] = start_date
        self.context['end_date'] = end_date
        
        df = pd.DataFrame()
        
        for stage in self.stages:
            self.logger.info(f"\n執行階段: {stage.__class__.__name__}")
            df = stage.execute(df, self.context)
            
        self.logger.info("\n" + "=" * 80)
        self.logger.info("ETL 管道執行完成！")
        self.logger.info("=" * 80)
        return df
