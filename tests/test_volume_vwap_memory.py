"""離線重現 VWAP 寬表放大，並以修補前演算法核對完整輸出。"""

import gc
import json
import resource
import sys
import tracemalloc

import numpy as np
import pandas as pd
import pytest

from app.volume_indicators import VolumeIndicators


class LegacyVolumeIndicators(VolumeIndicators):
    """保留 225a32b 的 VWAP 計算作為數值與記憶體對照。"""

    def calculate_vwap_cost_basis(self, periods=[5, 20]):
        result_dfs = []
        daily_vwap_raw = self._daily_vwap_from_value()
        usable = self._value_volume_unit_usable(daily_vwap_raw)
        self.vwap_diagnostics = {
            **self.vwap_diagnostics,
            "value_volume_unit_usable": usable,
            "daily_vwap_source": "value_div_volume" if usable else "disabled_unit_check_failed",
            "rolling_vwap_source": "sum_close_times_volume_div_sum_volume",
        }
        self.df["daily_vwap"] = daily_vwap_raw if usable else pd.NA
        for _, group in self.df.groupby("stock_id"):
            group = group.sort_values("date").reset_index(drop=True)
            close = pd.to_numeric(group["close"], errors="coerce")
            volume = pd.to_numeric(group["volume"], errors="coerce")
            close_volume = close * volume
            for period in periods:
                volume_sum = volume.rolling(window=period).sum()
                weighted_sum = close_volume.rolling(window=period).sum()
                rolling_vwap = self._safe_ratio(weighted_sum, volume_sum)
                group[f"rolling_vwap_{period}d"] = rolling_vwap
                group[f"close_vs_vwap_{period}d"] = self._safe_ratio(close, rolling_vwap) - 1.0
            if 20 in periods:
                previous_close = close.shift(1)
                previous_vwap20 = group["rolling_vwap_20d"].shift(1)
                current_vwap20 = group["rolling_vwap_20d"]
                valid = previous_close.notna() & previous_vwap20.notna() & close.notna() & current_vwap20.notna()
                reclaim = (previous_close < previous_vwap20) & (close >= current_vwap20)
                loss = (previous_close > previous_vwap20) & (close < current_vwap20)
                group["vwap_reclaim_20d"] = reclaim.where(valid).astype(float)
                group["vwap_loss_20d"] = loss.where(valid).astype(float)
            result_dfs.append(group)
        self.df = pd.concat(result_dfs, ignore_index=True)
        return self.df


def synthetic_frame(stocks=20, days=300, extra_columns=96):
    """寬欄模擬先前階段的技術指標，不讀取市場資料。"""
    n = stocks * days
    row = np.arange(n)
    close = 100.0 + np.sin(row / 3.0) * 10
    volume = (row % 17 + 1).astype(float) * 1000
    return pd.DataFrame({
        "date": np.tile(pd.date_range("2025-01-01", periods=days), stocks),
        "stock_id": np.repeat([f"S{i:04d}" for i in range(stocks)], days),
        "close": close, "volume": volume, "value": close * volume,
        "low": close - 1, "high": close + 1,
        **{f"existing_{i}": close + i for i in range(extra_columns)},
    })


def measured_peak(cls, frame):
    calculator = cls(frame)
    gc.collect()
    tracemalloc.start()
    try:
        calculator.calculate_vwap_cost_basis()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def test_vwap_wide_frame_memory():
    """相同輸入應消除大部分既有欄位的多份複製，非縮短資料窗口。"""
    frame = synthetic_frame()
    before = measured_peak(LegacyVolumeIndicators, frame)
    after = measured_peak(VolumeIndicators, frame)
    print(f"VWAP traced peak bytes: legacy={before}, current={after}")
    assert after < before * 0.65, (before, after)


def test_vwap_object_features_memory():
    """重現 reviewer P1：既有 object 指標不得被重複搬運及回填。"""
    frame = synthetic_frame()
    columns = [column for column in frame if column.startswith("existing_")]
    frame[columns] = frame[columns].astype(object)
    before = measured_peak(LegacyVolumeIndicators, frame)
    after = measured_peak(VolumeIndicators, frame)
    print(f"OBJECT VWAP traced peak bytes: legacy={before}, current={after}")
    assert after < before * 0.65, (before, after)
    pd.testing.assert_frame_equal(
        VolumeIndicators(frame).calculate_vwap_cost_basis(),
        LegacyVolumeIndicators(frame).calculate_vwap_cost_basis(),
        check_exact=True,
    )


@pytest.mark.parametrize("case", ["normal", "missing_value", "wrong_units", "invalid", "nullable", "duplicate_dates", "null_stock", "object_nulls", "extra_object_nulls", "mixed_objects", "one_stock", "short_history"])
@pytest.mark.parametrize("periods", [[5, 20], [3], [20, 5], []])
def test_vwap_exact_equivalence(case, periods):
    frame = synthetic_frame(stocks=3, days=43, extra_columns=2)
    frame["label"] = pd.Series(["甲", None, "乙"] * 43, dtype="string")
    frame["flag"] = pd.Series([True, False, None] * 43, dtype="boolean")
    if case == "missing_value":
        frame = frame.drop(columns="value")
    elif case == "wrong_units":
        frame["value"] *= 1000
    elif case == "invalid":
        frame.loc[[3, 5, 8], "volume"] = [0, -1, np.nan]
        frame.loc[[1, 22], "close"] = [np.nan, np.inf]
        frame["value"] = frame["value"].astype(object)
        frame.loc[9, "value"] = "bad"
    elif case == "nullable":
        frame[["close", "volume", "value"]] = frame[["close", "volume", "value"]].astype("Float64")
        frame.loc[4, "close"] = pd.NA
    elif case == "duplicate_dates":
        frame.loc[:30, "date"] = frame.loc[0, "date"]
    elif case == "null_stock":
        frame.loc[1, "stock_id"] = None
    elif case == "object_nulls":
        frame["empty_object"] = None
        frame["close"] = frame["close"].astype(object)
        frame.loc[:42, "close"] = None
    elif case == "extra_object_nulls":
        frame["empty_object"] = None
        frame["mixed_object"] = "甲"
        frame.loc[:42, "mixed_object"] = pd.NA
    elif case == "mixed_objects":
        frame["existing_0"] = frame["existing_0"].astype(object)
        frame["existing_1"] = pd.Series(["甲", 2, False] * 43, dtype=object)
    elif case == "one_stock":
        frame = frame.iloc[:43].drop(columns="value")
    elif case == "short_history":
        frame = frame.iloc[:2]
    frame = frame.sample(frac=1, random_state=9)
    frame.index = [7] * len(frame)
    original = frame.copy(deep=True)
    old, new = LegacyVolumeIndicators(frame), VolumeIndicators(frame)
    expected = old.calculate_vwap_cost_basis(periods)
    actual = new.calculate_vwap_cost_basis(periods)
    pd.testing.assert_frame_equal(actual, expected, check_exact=True)
    assert new.vwap_diagnostics == old.vwap_diagnostics
    pd.testing.assert_frame_equal(frame, original, check_exact=True)
    pd.testing.assert_frame_equal(new.calculate_vwap_cost_basis(periods), old.calculate_vwap_cost_basis(periods), check_exact=True)


def test_all_volume_indicators_exact_equivalence():
    frame = synthetic_frame(stocks=3, days=43, extra_columns=2)
    old, new = LegacyVolumeIndicators(frame), VolumeIndicators(frame)
    pd.testing.assert_frame_equal(new.calculate_all_volume_indicators(), old.calculate_all_volume_indicators(), check_exact=True)
    assert new.vwap_diagnostics == old.vwap_diagnostics


def test_indicator_stage_exact_equivalence(monkeypatch):
    """僅跑指標接縫；不啟動 ETL、provider 或任何輸出階段。"""
    from app.pipeline import indicator_stage

    frame = synthetic_frame(stocks=3, days=43, extra_columns=2)
    frame["open"] = frame["close"] - 0.5
    original = frame.copy(deep=True)
    old_context, new_context = {"stats": {}}, {"stats": {}}
    monkeypatch.setattr(indicator_stage, "VolumeIndicators", LegacyVolumeIndicators)
    expected = indicator_stage.IndicatorStage().execute(frame, old_context)
    monkeypatch.setattr(indicator_stage, "VolumeIndicators", VolumeIndicators)
    actual = indicator_stage.IndicatorStage().execute(frame, new_context)
    pd.testing.assert_frame_equal(actual, expected, check_exact=True)
    assert new_context["stats"] == old_context["stats"]
    pd.testing.assert_frame_equal(new_context["tech_ind"].df, old_context["tech_ind"].df, check_exact=True)
    pd.testing.assert_frame_equal(frame, original, check_exact=True)


if __name__ == "__main__":
    # 每次以全新程序執行，RSS 為整個程序的高水位；配置峰值僅涵蓋 VWAP。
    cls = {"legacy": LegacyVolumeIndicators, "current": VolumeIndicators}[sys.argv[1]]
    frame = synthetic_frame(stocks=100)
    if len(sys.argv) > 2 and sys.argv[2] == "object":
        columns = [column for column in frame if column.startswith("existing_")]
        frame[columns] = frame[columns].astype(object)
    peak = measured_peak(cls, frame)
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    print(json.dumps({"implementation": sys.argv[1], "rows": len(frame), "columns": len(frame.columns),
                      "traced_peak_bytes": peak, "process_peak_rss_bytes": rss if sys.platform == "darwin" else rss * 1024}))
