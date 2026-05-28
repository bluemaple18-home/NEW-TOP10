# BACKTEST-08：Backtest Acceptance Report

## 五行派工卡

任務ID：BACKTEST-08
卡片類型｜派工對象：Backtest / Acceptance｜Codex
請讀：`scripts/generate_backtest_acceptance_report.py`、`scripts/run_portfolio_replay.py`、`scripts/research_candidate_persistence_backtest.py`
任務目的：彙整 portfolio replay 與 candidate persistence study 的 evidence，形成一份可 review 的回測驗收報告
證據路徑：`artifacts/backtest/acceptance_report_YYYY-MM-DD.json`、`artifacts/backtest_acceptance_verification_latest.json`

## 範圍

- 只讀既有 backtest artifacts。
- 檢查 portfolio replay contract、總曝險、同族群曝險、event exit 欄位。
- 檢查 persistence study 不讀未來 ranking、不作為 model feature。
- 輸出 JSON 與 Markdown report。

## 非範圍

- 不重跑模型。
- 不重跑 daily ranking。
- 不決定 production feature promotion。
- 不把 persistence 或 group exposure 接進 production score。

## 驗收

- synthetic artifact 驗證 acceptance report schema。
- 真實小樣本 artifacts 可產生 OK report。
- report 明確標示 `production_model_change=false` 與 `ranking_score_change=false`。
- `py_compile` 與 `git diff --check` 通過。

## Review 重點

- 檢查 acceptance report 是否只是彙整證據，不偷跑新策略。
- 檢查 OK 條件是否沒有把缺失藏起來。
- 檢查 report 是否能作為下一輪長區間回測的 review 入口。
