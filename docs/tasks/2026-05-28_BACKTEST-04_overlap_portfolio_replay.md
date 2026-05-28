# BACKTEST-04：Overlap Portfolio Replay

## 五行派工卡

任務ID：BACKTEST-04
卡片類型｜派工對象：Backtest / Portfolio Replay｜Codex
請讀：`scripts/run_portfolio_replay.py`、`scripts/run_backtest_replay.py`、`docs/tasks/2026-05-28_BACKTEST-03_portfolio_bucket_replay.md`
任務目的：把 portfolio replay 從單日 bucket 升級成真實重疊持倉簿，支援 D+1 open 進場、固定 horizon close 出場、現金與總曝險上限
證據路徑：`artifacts/backtest/portfolio_replay_YYYY-MM-DD.json`、`artifacts/portfolio_replay_verification_latest.json`

## 範圍

- 只讀既有 ranking artifacts 與 clean features parquet。
- 使用 ranking date 作為 D 日訊號，下一個市場交易日開盤進場。
- 每筆部位持有固定市場 bar 數，最後一根 close 出場。
- 不同 ranking date 的部位可以重疊存在。
- 新增部位受現金與 `max_gross_exposure` 約束。
- 逐日輸出 cash、equity、gross exposure、positions、entries、exits。

## 非範圍

- 不訓練模型。
- 不重跑 ranking。
- 不改 production ranking score。
- 不做停損 / 停利事件出場。
- 不做同族群曝險限制；此項留給下一張風控卡。

## 驗收

- synthetic 驗證 D+1 open 進場，不允許同日進場。
- synthetic 驗證不同 ranking date 的持倉會重疊。
- synthetic 驗證缺 OHLC 會 skip，且 JSON 不輸出 NaN。
- synthetic 驗證總曝險不超過設定上限。
- 小樣本 smoke 可用真實 ranking/features 產出 replay artifact。
- `py_compile` 與 `git diff --check` 通過。

## Review 重點

- 檢查是否有 lookahead：ranking D 日只影響 D+1 之後。
- 檢查 cash / exposure scaling 是否會讓部位超買。
- 檢查 daily equity 是否在出場後更新。
- 確認腳本仍是研究 artifact，不是模型 feature 或 production ranking input。
