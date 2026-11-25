"""卡30 Repair 2：建構暫存、排序、事件及輸入隔離精確回歸。"""
import gc
import json
import logging
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.event_detector import EventDetector


class LegacyEventDetector(EventDetector):
    """只保留原建構 oracle；不改或替換產品模組及其餘原型。"""
    def __init__(self, df, config_path='config/signals.yaml'):
        self.df = df.copy()
        self.df = self.df.sort_values(['stock_id', 'date']).reset_index(drop=True)
        self.config = self._load_config(config_path)


def fixture(case):
    n = 120
    row = np.arange(n)
    close = 50 + np.sin(row / 3) * 10
    frame = pd.DataFrame({
        'stock_id': np.repeat(['A', 'B', 'C'], 40),
        'date': np.tile(pd.date_range('2026-01-01', periods=40), 3),
        'open': close - 1, 'high': close + 2, 'low': close - 2,
        'close': close, 'volume': (row % 9 + 1) * 100000.,
        'ma5': close + np.sin(row), 'ma20': close,
        'bb_middle': np.full(n, 50.), 'macd': np.sin(row),
        'macd_signal': np.cos(row), 'rsi': 50 + np.sin(row) * 30,
        'volume_ratio_5d': (row % 5).astype(float),
        'nullable': pd.array(row, dtype='Int64'), 'text': '保留資料',
    })
    if case == 'ties':
        frame = pd.concat([frame, frame.iloc[[1, 2, 40]]])
        frame.iloc[-3:, frame.columns.get_loc('close')] = [1., 100., 200.]
    elif case == 'nulls':
        frame.loc[::11, 'date'] = pd.NaT
        frame.loc[::13, 'stock_id'] = None
        frame.loc[::7, 'close'] = np.nan
        frame.loc[::9, 'nullable'] = pd.NA
    elif case == 'categorical':
        frame['stock_id'] = pd.Categorical(frame.stock_id, categories=['C', 'B', 'A', 'UNUSED'], ordered=True)
    elif case == 'timezone':
        frame['date'] = frame.date.dt.tz_localize('Asia/Taipei')
    elif case == 'empty':
        frame = frame.iloc[:0]
    elif case == 'identical':
        frame['stock_id'] = 'A'
        frame['date'] = pd.Timestamp('2026-01-01')
    if case not in ('ordered', 'identical'):
        frame = frame.sample(frac=1, random_state=30)
        frame.index = pd.Index([7] * len(frame), name='重複索引')
    return frame


def exact(left, right):
    pd.testing.assert_frame_equal(left, right, check_exact=True)


def mutate(frame):
    """寫入數值、object、extension、日期及股號；空表則驗新增欄隔離。"""
    if len(frame):
        for col, value in [('close', -999.), ('text', '變更'), ('nullable', -99),
                           ('date', pd.NaT), ('stock_id', 'B')]:
            frame.iloc[0, frame.columns.get_loc(col)] = value
    frame['新增欄'] = 1


@pytest.mark.parametrize('cow', [False, True])
@pytest.mark.parametrize('case', ['ordered', 'shuffled', 'ties', 'nulls', 'categorical', 'timezone', 'empty', 'identical'])
def test_constructor_data_events_and_bidirectional_isolation(case, cow, caplog):
    """同輸入新舊排序、全部事件、schema、索引與雙向改值均須精確一致。"""
    with pd.option_context('mode.copy_on_write', cow):
        frame = fixture(case)
        before = frame.copy(deep=True)
        old, new = LegacyEventDetector(frame), EventDetector(frame)
        exact(new.df, old.df)
        assert new.config == old.config
        expected = old.detect_all_events()
        actual = new.detect_all_events()
        exact(actual, expected)
        exact(new.df, old.df)
        exact(frame, before)
        if case in ('ordered', 'shuffled', 'ties', 'timezone', 'identical'):
            assert not [r for r in caplog.records if r.levelno >= logging.ERROR]
            assert actual.iloc[:, 2:].to_numpy().sum() > 0
        # detector 改值不回寫輸入。
        mutate(new.df)
        exact(frame, before)
        # 另一個未改值 detector 不受輸入寫入影響。
        new = EventDetector(frame)
        detector_before = new.df.copy(deep=True)
        mutate(frame)
        exact(new.df, detector_before)


def test_constructor_bounds_overlapping_wide_tables(monkeypatch):
    """微型可重現配置接縫：建構期間不應同時持有輸入以外的多張寬表。"""
    with pd.option_context('mode.copy_on_write', False):
        frame = fixture('shuffled')
        columns = tuple(frame.columns)
        observations = []
        # 包住配置接縫，在回傳前觀察仍存活的寬表；不保留額外強引用。
        def observe():
            observations.append(sum(1 for value in gc.get_objects()
                if isinstance(value, pd.DataFrame) and tuple(value.columns) == columns
                and len(value) == len(frame)))
        for name in ('copy', 'sort_values', 'reset_index'):
            original = getattr(pd.DataFrame, name)
            def wrap(self, *args, _original=original, **kwargs):
                result = _original(self, *args, **kwargs)
                observe()
                return result
            monkeypatch.setattr(pd.DataFrame, name, wrap)
        detector = EventDetector(frame)
        peak = max(observations)
        metrics = {'peak_live_wide_tables': peak, 'max_allowed_including_input': 2,
                   'rows': len(frame), 'cols': len(frame.columns)}
        if os.environ.get('R30_METRICS'):
            Path(os.environ['R30_METRICS']).with_name('constructor-allocation.json').write_text(
                json.dumps(metrics, ensure_ascii=False, indent=2) + '\n')
        assert detector.df is not frame
        assert peak <= 2, metrics


def test_harness_imports_current_components_without_baseline():
    """檢查實際 module/class/function 身分，不能只憑路徑或 SHA 宣稱受測。"""
    import inspect
    from app.pipeline import event_stage, filter_stage
    from app.risk_filter import RiskFilter
    from app.pipeline.indicator_stage import IndicatorStage
    from app.pipeline.fundamental_stage import FundamentalStage
    root = Path(__file__).resolve().parents[1]
    assert event_stage.EventDetector is EventDetector
    assert filter_stage.RiskFilter is RiskFilter
    classes = [EventDetector, event_stage.EventStage, filter_stage.FilterStage,
               RiskFilter, IndicatorStage, FundamentalStage]
    identities = {}
    for cls in classes:
        filename = Path(inspect.getfile(cls)).resolve()
        assert filename.is_relative_to(root / 'app')
        methods = {name: method.__code__.co_filename for name, method in cls.__dict__.items()
                   if inspect.isfunction(method)}
        assert all(Path(path).resolve() == filename for path in methods.values())
        identities[cls.__name__] = {'module': cls.__module__, 'path': str(filename), 'methods': methods}
    if os.environ.get('R30_METRICS'):
        Path(os.environ['R30_METRICS']).with_name('runtime-components.json').write_text(
            json.dumps(identities, ensure_ascii=False, indent=2) + '\n')
