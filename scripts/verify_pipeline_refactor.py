
"""
ETL 管道驗證腳本
測試原子化後的管道是否能正確執行
"""
import logging
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.pipeline import (
    ETLPipeline, FetchStage, IndicatorStage, 
    FundamentalStage, EventStage, FilterStage, ReportStage
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def verify_universe_artifact(universe_path: Path) -> None:
    if not universe_path.exists():
        raise AssertionError(f"missing universe artifact: {universe_path}")

    universe = pd.read_parquet(universe_path)
    if universe.empty:
        raise AssertionError(f"universe artifact is empty: {universe_path}")
    if "stock_id" not in universe.columns:
        raise AssertionError("universe artifact missing stock_id column")

    stock_count = universe["stock_id"].astype(str).str.strip().replace("", pd.NA).dropna().nunique()
    if stock_count <= 0:
        raise AssertionError("universe artifact has zero valid stocks")
    if "date" not in universe.columns:
        raise AssertionError("universe artifact missing date column")

    latest_date = pd.to_datetime(universe["date"], errors="coerce").max()
    if pd.isna(latest_date):
        raise AssertionError("universe artifact has no valid latest date")

    print(f"✅ universe artifact OK：rows={len(universe)} stocks={stock_count} latest_date={latest_date.date()}")


def test_pipeline():
    # 使用暫存目錄，避免驗證腳本覆寫正式 data/clean。
    with tempfile.TemporaryDirectory(prefix="new-top10-pipeline-verify-") as tmp_dir:
        workspace = Path(tmp_dir)
        pipeline = ETLPipeline(data_dir=str(workspace / "data"), artifacts_dir=str(workspace / "artifacts"))

        pipeline.add_stage(FetchStage()) \
                .add_stage(IndicatorStage()) \
                .add_stage(FundamentalStage()) \
                .add_stage(EventStage()) \
                .add_stage(FilterStage()) \
                .add_stage(ReportStage())

        print("啟動管道測試...")
        # 至少保留 90 天資料，避免短窗口讓所有股票被「上市未滿 60 日」規則誤濾掉。
        end = datetime.now().strftime('%Y-%m-%d')
        start = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')

        pipeline.run(start_date=start, end_date=end)
        universe_path = workspace / "data" / "clean" / "universe.parquet"
        verify_universe_artifact(universe_path)
        print("✅ 管道執行測試成功！")

if __name__ == "__main__":
    test_pipeline()
