
"""
ETL 階段：資料擷取 (Fetch Stage)
整合 DataFetcher 與 FinMind 資料
"""
from datetime import datetime, timezone

import pandas as pd
from pathlib import Path
from .base import PipelineStage
from app.data.reference_repository import ReferenceRepository
from app.data_fetcher import DataFetcherOrchestrator
from app.pipeline.daily_close_snapshot import materialize_daily_close_snapshot
from app.pipeline.validation_snapshot import (
    ValidationSnapshotProvider,
    load_validation_snapshot_from_environment,
    require_snapshot_window,
    validation_mode_enabled,
)
try:
    from app.finmind_integrator import FinMindIntegrator
except ImportError:
    from app.finmind_integrator import FinMindIntegrator

class FetchStage(PipelineStage):
    def execute(self, data: pd.DataFrame, context: dict) -> pd.DataFrame:
        self.logger.info(f"擷取資料: {context['start_date']} ~ {context['end_date']}")
        validation_mode = validation_mode_enabled()
        if validation_mode:
            snapshot = load_validation_snapshot_from_environment()
            require_snapshot_window(
                snapshot,
                start_date=context['start_date'],
                end_date=context['end_date'],
            )
            orchestrator = ValidationSnapshotProvider(snapshot.frame)
            context['stats']['validation_snapshot'] = {
                'provider_acquisition': 'snapshot',
                **snapshot.metadata,
            }
            daily_close_source = {
                'provider_identity': f"validation-file@sha256:{snapshot.metadata['sha256']}",
                'adapter_contract': 'validation-snapshot-provider.v1',
                'endpoint_contract': {
                    'transport': 'LOCAL_FILE',
                    'format': Path(snapshot.metadata['path']).suffix.lower().removeprefix('.'),
                    'finalization_authority': 'OFFICIAL_FINALIZED_DAILY_ENDPOINT_V1',
                },
            }
        else:
            orchestrator = DataFetcherOrchestrator(data_dir=str(context['dirs']['raw']))
            daily_close_source = {
                'provider_identity': 'TWSE_MI_INDEX+TPEX_STK_WN1430@official',
                'adapter_contract': 'DataFetcherOrchestrator.fetch_historical_data.v1',
                'endpoint_contract': {
                    'finalization_authority': 'OFFICIAL_FINALIZED_DAILY_ENDPOINT_V1',
                    'TWSE': {
                        'method': 'GET',
                        'url': 'https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX',
                        'query_contract': {
                            'date': 'YYYYMMDD',
                            'response': 'json',
                            'type': 'ALLBUT0999',
                        },
                    },
                    'TPEX': {
                        'method': 'GET',
                        'url': 'https://www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no1430/stk_wn1430_result.php',
                        'query_contract': {'d': 'ROC_YYY/MM/DD', 'l': 'zh-tw', 'se': 'AL'},
                    },
                },
            }

        df = orchestrator.fetch_historical_data(
            start_date=context['start_date'],
            end_date=context['end_date']
        )

        daily_close = materialize_daily_close_snapshot(
            df,
            root=Path(context['dirs']['raw']) / 'daily_close_snapshots',
            source=daily_close_source,
            fetched_at=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            requested_start=context['start_date'],
            requested_end=context['end_date'],
        )
        df = daily_close.frame
        context['stats']['daily_close_snapshot'] = {
            'snapshot_id': daily_close.manifest['snapshot_id'],
            'manifest_path': str(daily_close.manifest_path),
            'records_path': str(daily_close.records_path),
            'records_content_id': daily_close.manifest['identity_payload']['records_content_id'],
            'coverage': daily_close.manifest['identity_payload']['coverage'],
            'resolution_status': daily_close.manifest['identity_payload']['resolution_status'],
        }

        if df.empty:
            raise ValueError("資料擷取失敗，產出為空")

        df = self._filter_tradable_universe(df, context)
        df = self._dedupe_trade_keys(df, context)
            
        # FinMind 同屬 FetchStage provider acquisition；validation 時不得觸發外連。
        if validation_mode:
            context['stats']['finmind'] = {
                'status': 'skipped',
                'reason': 'storage validation snapshot provider is offline',
            }
        else:
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


    def _dedupe_trade_keys(self, df: pd.DataFrame, context: dict) -> pd.DataFrame:
        """確保後續 pivot 前交易日與股票代號唯一。"""
        if df.empty:
            return df

        normalized = df.copy()
        normalized['date'] = pd.to_datetime(normalized['date'])
        normalized['stock_id'] = normalized['stock_id'].astype(str).str.strip()

        duplicate_mask = normalized.duplicated(['date', 'stock_id'], keep=False)
        duplicate_rows = int(duplicate_mask.sum())
        if duplicate_rows == 0:
            context['stats']['trade_key_dedupe'] = {'status': 'ok', 'duplicate_rows': 0}
            return normalized

        before_rows = len(normalized)
        market_priority = {'TWSE': 0, 'TPEX': 1}
        market_values = normalized['market'] if 'market' in normalized.columns else pd.Series(index=normalized.index, dtype='object')
        normalized['_market_priority'] = market_values.map(market_priority).fillna(99)
        normalized = normalized.sort_values(['date', 'stock_id', '_market_priority'])
        deduped = normalized.drop_duplicates(['date', 'stock_id'], keep='first').drop(columns=['_market_priority'])

        sample = (
            normalized.loc[duplicate_mask, ['date', 'stock_id', 'stock_name', 'market']]
            .drop_duplicates()
            .head(10)
            .to_dict(orient='records')
        )
        context['stats']['trade_key_dedupe'] = {
            'status': 'deduped',
            'duplicate_rows': duplicate_rows,
            'before_rows': before_rows,
            'after_rows': len(deduped),
            'sample': sample,
        }
        self.logger.warning(
            'FetchStage 發現同日同股重複資料，已依市場優先序去重: duplicate_rows=%s rows %s -> %s sample=%s',
            duplicate_rows,
            before_rows,
            len(deduped),
            sample,
        )
        return deduped
