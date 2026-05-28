# BACKTEST-01：Production Replay 回測第一版

## 五行派工卡

任務ID：BACKTEST-01
卡片類型｜派工對象：Backtest / Production Replay｜Codex
請讀：`scripts/run_backtest_replay.py`、`app/agent_b_ranking.py`、`app/labels.py`、`docs/architecture/MODEL_IMPROVEMENT_LOOP.md`
任務目的：建立 D 日 ranking、D+1 開盤進場的 production replay，先輸出 1D / 3D / 5D / 10D horizon 統計與交易成本後報酬
證據路徑：`artifacts/backtest/replay_YYYY-MM-DD.json`、`artifacts/backtest_replay_verification_latest.json`

## 背景

正規回測不是重新訓練一次看分數，而是模擬使用者每天真的會看到的 ranking artifact，檢查當時選出來的股票在之後 1 / 3 / 5 / 10 個交易日的表現。

## 本卡範圍

- 只讀 `ranking_*.csv` 與 `features.parquet`。
- D 日 ranking，D+1 開盤進場。
- 用 exit day close 出場。
- 納入買賣手續費、證交稅與雙邊滑價。
- 輸出每個 horizon 的平均報酬、勝率、MAE、MFE。

## 非範圍

- 不訓練模型。
- 不重跑 ranking。
- 不做完整 portfolio equity curve。
- 不做資金再平衡。
- 不把結果自動寫回 production score。

## 驗收

- `scripts/verify_backtest_replay.py` 使用 synthetic ranking / OHLC，不讀正式大資料。
- 驗證進場日是 D+1，不是 D 日。
- 驗證成本後報酬有被計算。
- 驗證 horizon summary 產生。
- `py_compile` 通過。

## 後續

完整 portfolio replay 需另開 BACKTEST-03，加入：

- 最大持股數。
- 單檔最大部位。
- 同族群曝險限制。
- equity curve。
- Max Drawdown / Sharpe / Sortino / Profit Factor。
