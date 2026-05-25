
"""
ETL 階段：資料擷取 (Fetch Stage)
整合 DataFetcher 與 FinMind 資料
"""
import pandas as pd
from pathlib import Path
from .base import PipelineStage
from app.data.reference_repository import ReferenceRepository
from app.data_fetcher import DataFetcherOrchestrator
try:
    from app.finmind_integrator import FinMindIntegrator
except ImportError:
    from app.finmind_integrator import FinMindIntegrator

class FetchStage(PipelineStage):
    def execute(self, data: pd.DataFrame, context: dict) -> pd.DataFrame:
        orchestrator = DataFetcherOrchestrator(data_dir=str(context['dirs']['raw']))
        
        self.logger.info(f"擷取資料: {context['start_date']} ~ {context['end_date']}")
        df = orchestrator.fetch_historical_data(
            start_date=context['start_date'],
            end_date=context['end_date']
        )
        
        if df.empty:
            raise ValueError("資料擷取失敗，產出為空")

        df = self._filter_tradable_universe(df, context)
            
        # 整合 FinMind 籌碼；缺套件或 API 失敗時不可阻斷價格資料重建。
        try:
            finmind = FinMindIntegrator()
            df = finmind.integrate_chip_data(df)
        except Exception as exc:
            self.logger.warning("FinMind 籌碼整合失敗，略過此資料源: %s", exc)
            context['stats']['finmind'] = {'status': 'skipped', 'error': str(exc)}
        
        context['stats']['data_fetching'] = {
            'total_records': len(df),
            'unique_stocks': df['stock_id'].nunique()
        }
        context['suspended_list'] = orchestrator.fetch_suspended_stocks_list()
        context['orchestrator'] = orchestrator # 傳遞給後續需要調取資料的階段
        
        return df

    def _filter_tradable_universe(self, df: pd.DataFrame, context: dict) -> pd.DataFrame:
        repository = ReferenceRepository(Path.cwd())
        universe = repository.tradable_universe(active_only=True, include_etfs=False)
        if not universe.available:
            self.logger.warning("tradable_universe.csv 不可用，略過股票池過濾")
            context['stats']['tradable_universe_filter'] = {'status': 'skipped'}
            return df

        allowed = {item.stock_id for item in universe.items}
        before_rows = len(df)
        before_stocks = df['stock_id'].astype(str).str.strip().nunique()
        filtered = df.copy()
        filtered['stock_id'] = filtered['stock_id'].astype(str).str.strip()
        filtered = filtered[filtered['stock_id'].isin(allowed)].copy()
        context['stats']['tradable_universe_filter'] = {
            'status': 'ok',
            'allowed_stocks': len(allowed),
            'before_rows': before_rows,
            'after_rows': len(filtered),
            'before_stocks': int(before_stocks),
            'after_stocks': int(filtered['stock_id'].nunique()) if not filtered.empty else 0,
        }
        self.logger.info(
            "套用 tradable universe filter: rows %s -> %s, stocks %s -> %s",
            before_rows,
            len(filtered),
            before_stocks,
            filtered['stock_id'].nunique() if not filtered.empty else 0,
        )
        if filtered.empty:
            raise ValueError("套用 tradable universe 後資料為空")
        return filtered
