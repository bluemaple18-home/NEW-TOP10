
"""
ETL 管道調度器 (Orchestrator)
採用組合模式 (Composition) 驅動原子化的管道階段
"""
import pandas as pd
from pathlib import Path
import logging
from datetime import datetime, timedelta
import inspect
import os
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]

class ETLPipeline:
    """整合所有原子化階段的 ETL 流程調度器"""
    
    def __init__(self, data_dir: str = "data", artifacts_dir: str = "artifacts"):
        self.data_dir = Path(data_dir)
        self.raw_dir = self.data_dir / "raw"
        self.clean_dir = self.data_dir / "clean"
        self.artifacts_dir = Path(artifacts_dir)
        self._guard_verify_production_write()
        
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

    def _guard_verify_production_write(self):
        """禁止 verify 腳本把測試輸出寫進正式 data/clean。"""
        if os.environ.get("TOP10_ALLOW_VERIFY_PRODUCTION_WRITE") == "1":
            return

        if self.data_dir.resolve() != (PROJECT_ROOT / "data").resolve():
            return

        argv_name = Path(sys.argv[0]).name
        stack_names = {Path(frame.filename).name for frame in inspect.stack(context=0)}
        if not (argv_name.startswith("verify_") or any(name.startswith("verify_") for name in stack_names)):
            return

        raise RuntimeError(
            "verify scripts must not write production data_dir='data'; "
            "use tempfile.TemporaryDirectory(), data/test, or set TOP10_ALLOW_VERIFY_PRODUCTION_WRITE=1 explicitly"
        )

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
