# BACKTEST-03：Portfolio Bucket Replay 第一版

## 五行派工卡

任務ID：BACKTEST-03
卡片類型｜派工對象：Backtest / Portfolio Replay｜Codex
請讀：`scripts/run_backtest_replay.py`、`docs/tasks/2026-05-28_BACKTEST-01_production_replay.md`、`docs/architecture/MODEL_IMPROVEMENT_LOOP.md`
任務目的：在 D+1 horizon replay 上加入 portfolio bucket 權重、現金、總曝險、equity curve 與 max drawdown 第一版
證據路徑：`artifacts/backtest/replay_YYYY-MM-DD.json`、`artifacts/backtest_replay_verification_latest.json`

## 範圍

- 使用 ranking 內 `suggested_weight`、`max_position_weight`、`gross_exposure`。
- 套用 CLI `--max-position-weight` 上限。
- 每個 ranking date 形成一個 portfolio bucket。
- 對每個 horizon 產生：
  - portfolio return
  - invested weight
  - cash weight
  - equity curve
  - max drawdown

## 非範圍

- 不做跨 ranking date 的重疊持倉再平衡。
- 不做每日逐筆成交撮合。
- 不接模型訓練。
- 不改 production ranking score。

## 驗收

- synthetic replay 驗證 D+1 進場仍成立。
- 驗證 OHLC 缺值會 skip，不輸出 JSON NaN。
- 驗證單檔權重 cap 生效。
- 驗證 portfolio summary 與 equity curve 存在。
- `py_compile` 與 `git diff --check` 通過。

## 後續

下一版才做完整持倉簿：

- 每日重疊持倉。
- 停損/停利事件驅動出場。
- 同族群曝險限制。
- 交易稅費逐筆記帳。
