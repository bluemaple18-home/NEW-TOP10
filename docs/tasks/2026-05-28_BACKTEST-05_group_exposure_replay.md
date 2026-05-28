# BACKTEST-05：Group Exposure Replay Cap

## 五行派工卡

任務ID：BACKTEST-05
卡片類型｜派工對象：Backtest / Risk Control｜Codex
請讀：`scripts/run_portfolio_replay.py`、`scripts/verify_portfolio_replay.py`、`data/reference/stock_industry_map.csv`
任務目的：在 overlap portfolio replay 加入可選同族群曝險上限，驗證動能股 Top10 是否過度集中於同產業/題材
證據路徑：`artifacts/portfolio_replay_verification_latest.json`、`artifacts/backtest/portfolio_replay_YYYY-MM-DD.json`

## 範圍

- 新增 `--max-group-exposure` 作為可選風控；未指定時維持既有 replay 行為。
- 預設從 `data/reference/stock_industry_map.csv` 讀取 `industry_name` 作為 group。
- 進場時限制同 group 新增 notional。
- 收盤後若同 group 因價格 drift 超過 cap，按 group 內市值比例去槓桿。
- daily artifact 輸出 `group_exposures`、`group_deleveraged_notional`、`group_deleverage_count`。
- summary 輸出 `max_group_exposure`。

## 非範圍

- 不把產業/族群接入模型 feature。
- 不改 ranking score。
- 不改每日推薦文案。
- 不做 sector rotation alpha 判斷；這張只驗風控約束。

## 驗收

- synthetic 驗證同 group 曝險不超過 `--max-group-exposure`。
- synthetic 驗證 group exposure contract 寫入 artifact。
- synthetic 驗證 JSON 不輸出 NaN。
- 原本 D+1 open、固定 horizon close、重疊持倉、gross exposure cap、OHLC skip regression 仍通過。
- 小樣本真實 replay 可啟用 `--max-group-exposure` 產生 artifact。
- `py_compile` 與 `git diff --check` 通過。

## Review 重點

- 檢查 group cap 是否只在 replay 研究層生效。
- 檢查 missing group map 時不會讓預設 replay 壞掉。
- 檢查 group cap 是否同時處理進場與 close drift。
- 檢查是否有不小心改到 model / ranking production path。
