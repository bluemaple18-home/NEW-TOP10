# BACKTEST-07：Persistence Replay Evidence Refresh

## 五行派工卡

任務ID：BACKTEST-07
卡片類型｜派工對象：Backtest / Persistence Research｜Codex
請讀：`scripts/research_candidate_persistence_backtest.py`、`scripts/verify_candidate_persistence_backtest.py`、`docs/tasks/2026-05-28_BACKTEST-02_candidate_persistence_study.md`
任務目的：刷新入榜天數 persistence study 的小樣本 evidence，作為 BACKTEST-08 acceptance report 的輸入
證據路徑：`artifacts/backtest/persistence_study_YYYY-MM-DD.json`、`artifacts/candidate_persistence_backtest_verification_latest.json`

## 範圍

- 使用既有 persistence study 腳本。
- 只讀 ranking artifacts 與 clean features parquet。
- 小樣本跑 `--max-ranking-files`，避免本機高負載。
- 確認 streak bucket 與 rank delta direction summary 存在。

## 非範圍

- 不把入榜天數接進模型。
- 不改 ranking score。
- 不重訓模型。
- 不重跑 daily pipeline。

## 驗收

- synthetic persistence verification 通過。
- 小樣本 persistence study 產出 JSON / Markdown。
- JSON 不含 NaN。
- `py_compile` 與 `git diff --check` 通過。

## Review 重點

- 檢查 persistence builder 是否只讀 target date 以前 ranking。
- 檢查本卡是否仍是 research-only。
- 檢查結果是否只作為 shadow feature 候選，不直接進 production。
