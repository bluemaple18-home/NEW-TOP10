# PERSIST-01：入榜天數與排名變化

## 五行派工卡

任務ID：PERSIST-01
卡片類型｜派工對象：Decision Artifact / Candidate Persistence｜Codex
請讀：`scripts/build_candidate_persistence.py`、`scripts/generate_daily_report.py`、`scripts/run_automation.py`
任務目的：新增入榜天數、首次入榜日、連續入榜天數、排名變化；先作為決策輔助，不進模型分數
證據路徑：`artifacts/candidate_persistence_YYYY-MM-DD.json`、`artifacts/candidate_persistence_verification_latest.json`

## 背景

動能策略的假設是：若推薦有效，且基本面、技術面、籌碼面沒有崩壞，候選不應只入榜一天就消失。

但「入榜越久越好」不是鐵律。它可能代表：

- 第 1 天：剛突破，尚未確認。
- 第 2-5 天：動能延續。
- 太久：過熱或追高風險。

因此本卡只做 annotation，不進正式模型。

## 實作

- 新增 `scripts/build_candidate_persistence.py`。
- `run_automation daily` 在 ranking 後、daily report 前產生 persistence artifact。
- `generate_daily_report.py` 若找到 persistence artifact，Top10 表格顯示入榜天數與排名變化。

## 契約

- 只讀 `ranking_*.csv`。
- 只使用 `ranking_date` 當日以前的 artifact。
- 不讀未來 ranking。
- 不重跑 ETL / ranking / model。
- `rank_delta > 0` 代表排名進步，`rank_delta < 0` 代表排名退步。

## 驗收

- `scripts/verify_candidate_persistence.py` 使用 TemporaryDirectory 與 synthetic ranking artifacts。
- 驗證未來日期 artifact 不會被讀入目標日期計算。
- 驗證連續入榜天數。
- 驗證排名變化。
- `py_compile` 通過。

## 後續

- BACKTEST-02 才能判斷入榜天數是否值得進 shadow feature。
- UI 顯示可在 Momentum UI 後續卡接入。
