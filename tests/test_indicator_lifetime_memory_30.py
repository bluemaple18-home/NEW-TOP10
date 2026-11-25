"""卡30第3輪：在量能計算接縫實測舊技術表釋放及完整等價。"""
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


def legacy_indicator_execute(frame, context, technical, volume):
    """鎖住指定patch之前的計算順序與公開回傳、統計語意。"""
    tech = technical(frame)
    data = tech.calculate_all_indicators()
    vol = volume(data)
    data = vol.calculate_all_volume_indicators()
    context['stats']['indicators'] = {
        'tech_missing': tech.get_missing_rate().to_dict(),
        'vol_missing': vol.get_missing_rate().to_dict(),
    }
    return data


def observe_indicators(monkeypatch):
    """只存弱ref與純值，避免觀測本身延長中間表生命。"""
    from app.pipeline import indicator_stage
    technical, volume = indicator_stage.TechnicalIndicators, indicator_stage.VolumeIndicators
    seen = {'refs': {}, 'bytes': {}, 'rhs': {}, 'isolated': False}

    class ObservedTechnical(technical):
        def calculate_all_indicators(self):
            result = super().calculate_all_indicators()
            held = {'tech_ind': self, 'tech_df': result,
                    **{'pivot_' + k: v for k, v in self.pivots.items()}}
            seen['refs'].update({k: weakref.ref(v) for k, v in held.items()})
            seen['bytes'].update({k: int(v.memory_usage(deep=True).sum())
                                  for k, v in held.items() if isinstance(v, pd.DataFrame)})
            return result

    class ObservedVolume(volume):
        def __init__(self, frame):
            super().__init__(frame)
            seen['refs']['vol_ind'] = weakref.ref(self)
            seen['refs']['vol_initial_df'] = weakref.ref(self.df)
            seen['bytes']['vol_initial_df'] = int(self.df.memory_usage(deep=True).sum())
            seen['isolated'] = self.df is not frame and not any(
                np.shares_memory(a.values, b.values)
                for a in frame._mgr.blocks for b in self.df._mgr.blocks)

        def calculate_all_volume_indicators(self):
            gc.collect()
            seen['rhs'] = {k: ref() is not None for k, ref in seen['refs'].items()
                           if k == 'tech_ind' or k == 'tech_df' or k.startswith('pivot_')}
            return super().calculate_all_volume_indicators()

    monkeypatch.setattr(indicator_stage, 'TechnicalIndicators', ObservedTechnical)
    monkeypatch.setattr(indicator_stage, 'VolumeIndicators', ObservedVolume)
    return seen


def test_indicator_rhs_releases_aliases_and_preserves_exact_values(monkeypatch):
    """未修時應因同一多餘持有而紅；修後數值、統計、輸入及弱ref全驗。"""
    from app.pipeline import indicator_stage

    frame = indicator_fixture().sample(frac=1, random_state=30)
    frame.index = [7] * len(frame)
    original = frame.copy(deep=True)
    expected_context, context = {'stats': {}}, {'stats': {}}
    expected = legacy_indicator_execute(frame, expected_context,
                                        indicator_stage.TechnicalIndicators,
                                        indicator_stage.VolumeIndicators)
    seen = observe_indicators(monkeypatch)
    actual = indicator_stage.IndicatorStage().execute(frame, context)
    pd.testing.assert_frame_equal(actual, expected, check_exact=True)
    pd.testing.assert_frame_equal(frame, original, check_exact=True)
    assert context['stats'] == expected_context['stats']
    gc.collect()
    result = {'rhs_live': seen['rhs'], 'volume_ctor_isolated': seen['isolated'],
              'return_live': {k: ref() is not None for k, ref in seen['refs'].items()},
              'context_calculators': sorted(set(context) & {'tech_ind', 'vol_ind'}),
              'exact_output_stats_input': True}
    if os.environ.get('R30_LIFECYCLE'):
        Path(os.environ['R30_LIFECYCLE']).write_text(json.dumps(result, ensure_ascii=False, indent=2))
    assert {'tech_ind', 'tech_df'} <= set(seen['rhs'])
    assert any(k.startswith('pivot_') for k in seen['rhs'])
    assert seen['isolated'], result
    assert not any(seen['rhs'].values()), result
    assert not any(result['return_live'].values()), result
    assert not result['context_calculators'], result
