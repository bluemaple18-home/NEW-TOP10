"""卡30：檢查舊context輸入的過濾生命週期與排序工作集。"""
import gc
import json
import os
from pathlib import Path
import weakref

import numpy as np
import pandas as pd


def indicator_fixture():
    n = 4 * 90
    row = np.arange(n)
    close = 50 + np.sin(row / 3)
    return pd.DataFrame({
        'stock_id': np.repeat(['A','B','C','D'],90),
        'date': np.tile(pd.date_range('2026-01-01',periods=90),4),
        'open': close - .5, 'high': close + 1, 'low': close - 1,
        'close': close, 'volume': np.full(n,1_000_000.), 'value': close * 1_000_000,
    })


def legacy_indicator_context(frame, context):
    """安排舊context作為Event/Filter輸入，保留已驗清理責任的回歸覆蓋。"""
    from app.indicators import TechnicalIndicators
    from app.volume_indicators import VolumeIndicators
    tech = TechnicalIndicators(frame)
    technical = tech.calculate_all_indicators()
    vol = VolumeIndicators(technical)
    data = vol.calculate_all_volume_indicators()
    context['stats']['indicators'] = {'tech_missing': tech.get_missing_rate().to_dict(),
                                      'vol_missing': vol.get_missing_rate().to_dict()}
    context.update(tech_ind=tech, vol_ind=vol)
    return data


def test_filter_stage_memory_lifecycle_and_workset(monkeypatch, tmp_path):
    """同一產品接縫：多餘存活表與全寬排序均須可觀察地消失。"""
    from app.pipeline.fundamental_stage import FundamentalStage
    from app.pipeline.filter_stage import FilterStage

    context = {'stats':{}, 'dirs':{'clean':tmp_path}}
    data = legacy_indicator_context(indicator_fixture(),context)
    assert context['tech_ind'].df is not None  # 既有回傳後契約
    held = {'tech_df':context['tech_ind'].df, 'vol_df':context['vol_ind'].df,
            **{'pivot_'+k:v for k,v in context['tech_ind'].pivots.items()}}
    refs = {k:weakref.ref(v) for k,v in held.items()}
    held_bytes = {k:int(v.memory_usage(deep=True).sum()) for k,v in held.items()}
    del held
    data = FundamentalStage().execute(data,context)
    sorts = []
    original_sort = pd.DataFrame.sort_values
    def measured_sort(frame, *args, **kwargs):
        sorts.append({'columns':len(frame.columns),'bytes':int(frame.memory_usage(deep=True).sum())})
        return original_sort(frame,*args,**kwargs)
    monkeypatch.setattr(pd.DataFrame,'sort_values',measured_sort)
    written = []
    def parquet(frame,*args,**kwargs):
        gc.collect()
        written.append({'rows':len(frame),'live_holders':[k for k,v in refs.items() if v() is not None]})
    monkeypatch.setattr(pd.DataFrame,'to_parquet',parquet)
    result = FilterStage().execute(data,context)
    assert result is data
    violations = []
    if written[0]['live_holders']:
        violations.append('寫universe時仍持有指標中間表')
    if any(s['columns'] > 3 for s in sorts):
        violations.append('僅判斷最新門檻卻排序全寬特徵表')
    metrics = {'held_df_bytes_before_filter':held_bytes,'sorts':sorts,'write':written,'violations':violations}
    if os.environ.get('R30_METRICS'):
        Path(os.environ['R30_METRICS']).write_text(json.dumps(metrics,ensure_ascii=False,indent=2))
    assert not violations, metrics


# 此oracle鎖住改前的全寬排序語意；其餘未修改的風險規則沿既有類別。
from app.risk_filter import RiskFilter
import pytest


class LegacyRiskFilter(RiskFilter):
    def filter_liquidity(self, min_avg_value=10_000_000, period=20):
        column = f'avg_value_{period}d'
        if column not in self.df:
            return self.df
        initial = self.df.stock_id.nunique()
        latest = self.df.sort_values('date').groupby('stock_id').tail(1)
        valid = latest.loc[latest[column] >= min_avg_value, 'stock_id'].tolist()
        self.df = self.df[self.df.stock_id.isin(valid)]
        remaining = self.df.stock_id.nunique()
        self.filter_stats['liquidity'] = {'min_avg_value':min_avg_value,'period':period,
            'removed_stocks':initial-remaining,'remaining_stocks':remaining}
        return self.df

    def filter_price(self, min_price=10.0):
        initial = self.df.stock_id.nunique()
        latest = self.df.sort_values('date').groupby('stock_id').tail(1)
        valid = latest.loc[latest.close >= min_price, 'stock_id'].tolist()
        self.df = self.df[self.df.stock_id.isin(valid)]
        remaining = self.df.stock_id.nunique()
        self.filter_stats['price'] = {'min_price':min_price,
            'removed_stocks':initial-remaining,'remaining_stocks':remaining}
        return self.df


def risk_fixture(case):
    frame = indicator_fixture()
    frame['close'] = frame.stock_id.map({'A':10.,'B':9.99,'C':np.nan,'D':30.})
    frame['avg_value_20d'] = frame.stock_id.map({'A':10_000_000.,'B':20_000_000.,'C':30_000_000.,'D':9_999_999.})
    # 無關寬欄含nullable與object，回傳schema仍必須完整不變。
    frame['nullable'] = pd.Series(np.arange(len(frame)),dtype='Int64')
    frame['text'] = '保留完整特徵'
    if case == 'duplicates':
        frame = pd.concat([frame,frame.iloc[[89,179,269,359]]])
        frame.iloc[-4:,frame.columns.get_loc('close')] = [9.,11.,20.,30.]
        frame.iloc[-4:,frame.columns.get_loc('avg_value_20d')] = [30_000_000.]*4
    elif case == 'null_keys':
        frame.loc[::13,'date'] = pd.NaT
        frame.loc[::11,'stock_id'] = None
    elif case == 'categorical':
        frame['stock_id'] = pd.Categorical(frame.stock_id,categories=['A','B','C','D','UNUSED'])
    elif case == 'empty':
        frame = frame.iloc[:0]
    elif case == 'missing_liquidity':
        frame = frame.drop(columns='avg_value_20d')
    elif case == 'timezone':
        frame['date'] = frame.date.dt.tz_localize('Asia/Taipei')
    if case != 'ordered':
        frame = frame.sample(frac=1,random_state=30)
        frame.index = pd.Index([7]*len(frame),name='重複索引')
    return frame


@pytest.mark.parametrize('case',['ordered','shuffled','duplicates','null_keys','categorical','empty','missing_liquidity','timezone'])
@pytest.mark.parametrize('method',['filter_liquidity','filter_price','apply_all_filters'])
def test_risk_filter_exact_equivalence(case, method):
    """包含同日tie、NaT、NA股號、重複索引、分類型別與空表的精確回歸。"""
    frame = risk_fixture(case)
    original = frame.copy(deep=True)
    old, new = LegacyRiskFilter(frame), RiskFilter(frame)
    kwargs = {'suspended_list':['B']} if method == 'apply_all_filters' else {}
    expected = getattr(old,method)(**kwargs)
    actual = getattr(new,method)(**kwargs)
    pd.testing.assert_frame_equal(actual,expected,check_exact=True)
    pd.testing.assert_frame_equal(new.get_filter_report(),old.get_filter_report(),check_exact=True)
    assert new.filter_stats == old.filter_stats
    pd.testing.assert_frame_equal(frame,original,check_exact=True)


def test_risk_filter_keeps_input_isolation():
    """初始deep copy契約保留，不能以共用輸入儲存來省記憶體。"""
    frame = risk_fixture('ordered')
    original = frame.copy(deep=True)
    risk = RiskFilter(frame)
    risk.df.loc[0,'close'] = -999
    pd.testing.assert_frame_equal(frame,original,check_exact=True)


def test_event_stage_releases_finished_work_before_copy_and_write(monkeypatch, tmp_path):
    """事件建構前釋放上游；偵測後釋放detector，並驗完整輸出等價。"""
    from app.pipeline.fundamental_stage import FundamentalStage
    from app.pipeline import event_stage
    from app.event_detector import EventDetector

    context = {'stats':{},'dirs':{'clean':tmp_path}}
    data = legacy_indicator_context(indicator_fixture(),context)
    assert context['tech_ind'].df is not None
    refs = {'tech_df':weakref.ref(context['tech_ind'].df),
            'vol_df':weakref.ref(context['vol_ind'].df),
            **{'pivot_'+key:weakref.ref(value) for key,value in context['tech_ind'].pivots.items()}}
    upstream_bytes = int(context['tech_ind'].df.memory_usage(deep=True).sum() +
                         context['vol_ind'].df.memory_usage(deep=True).sum())
    data = FundamentalStage().execute(data,context)
    original = data.copy(deep=True)
    expected = EventDetector(data).detect_all_events()
    observed = {'upstream_bytes_before_event':upstream_bytes,'writes':[]}
    detector_refs = {}

    class ObservedDetector(EventDetector):
        def __init__(self, frame):
            gc.collect()
            observed['live_before_constructor'] = [name for name,ref in refs.items() if ref() is not None]
            super().__init__(frame)
            detector_refs['detector'] = weakref.ref(self)
            detector_refs['df'] = weakref.ref(self.df)
            observed['detector_df_bytes'] = int(self.df.memory_usage(deep=True).sum())

    monkeypatch.setattr(event_stage,'EventDetector',ObservedDetector)
    written = {}
    def parquet(frame,path,*args,**kwargs):
        gc.collect()
        observed['writes'].append({'name':path.name,
            'live_detector':[name for name,ref in detector_refs.items() if ref() is not None],
            'live_upstream':[name for name,ref in refs.items() if ref() is not None]})
        written[path.name] = frame.copy(deep=True)
    monkeypatch.setattr(pd.DataFrame,'to_parquet',parquet)
    actual = event_stage.EventStage().execute(data,context)
    assert actual is data
    pd.testing.assert_frame_equal(data,original,check_exact=True)
    pd.testing.assert_frame_equal(written['features.parquet'],original,check_exact=True)
    pd.testing.assert_frame_equal(written['events.parquet'],expected,check_exact=True)
    pd.testing.assert_frame_equal(context['events_df'],expected,check_exact=True)
    assert context['stats']['events'] == {'count':len(expected.columns)-2}
    violations = []
    if observed['live_before_constructor']:
        violations.append('EventDetector建構前仍持有上游中間表')
    if any(row['live_detector'] or row['live_upstream'] for row in observed['writes']):
        violations.append('寫入前仍持有已完成的detector或上游中間表')
    observed['exact_equivalence'] = True
    observed['violations'] = violations
    if os.environ.get('R30_METRICS'):
        path = Path(os.environ['R30_METRICS']).with_name('event-lifecycle.json')
        path.write_text(json.dumps(observed,ensure_ascii=False,indent=2))
    assert not violations,observed
