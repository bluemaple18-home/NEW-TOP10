# BACKTEST-09：Strategy Matrix Backtest

## 五行派工卡

任務ID：BACKTEST-09
卡片類型｜派工對象：Backtest / Strategy Matrix｜Codex
請讀：`scripts/run_backtest_strategy_matrix.py`、`scripts/run_portfolio_replay.py`、`docs/tasks/2026-05-28_BACKTEST-08_acceptance_report.md`
任務目的：用既有 ranking / features 跑多組 horizon、停損、停利、同族群曝險 cap 的 portfolio replay 矩陣，找出策略穩定度而不是單一回測漂亮結果
證據路徑：`artifacts/backtest/strategy_matrix_YYYY-MM-DD.json`、`artifacts/backtest_strategy_matrix_verification_latest.json`

## 範圍

- 只讀既有 `ranking_*.csv` 與 `data/clean/features.parquet`。
- 比較多組：
  - `horizon`
  - `stop_loss_pct`
  - `take_profit_pct`
  - `max_group_exposure`
- 對每個 scenario 輸出：
  - total return
  - max drawdown
  - win rate
  - avg trade return
  - exit reason counts
  - score
- 預設使用 `--max-ranking-files` 控制本機負載。

## 非範圍

- 不重訓模型。
- 不重跑 ETL。
- 不重跑 ranking。
- 不調整 production score。
- 不直接宣告最佳策略可上線。

## 驗收

- synthetic matrix 驗證 scenario count、排序、event exits、group cap scenario 存在。
- 真實小樣本 matrix 可產生 JSON / Markdown。
- JSON 不含 NaN。
- `py_compile` 與 `git diff --check` 通過。

## Review 重點

- 檢查 strategy score 是否只作研究排序，不是 production decision。
- 檢查矩陣是否避免 lookahead，仍沿用 D+1 open / OHLC replay contract。
- 檢查是否沒有模型、RankingPolicy、agent_b_ranking 寫入路徑。
- 檢查本機預設是否有限制 max ranking files，避免高負載。
