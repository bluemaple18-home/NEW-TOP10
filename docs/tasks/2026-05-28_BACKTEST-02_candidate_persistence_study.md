# BACKTEST-02：入榜天數有效性研究

## 五行派工卡

任務ID：BACKTEST-02
卡片類型｜派工對象：Backtest / Persistence Research｜Codex
請讀：`scripts/research_candidate_persistence_backtest.py`、`scripts/build_candidate_persistence.py`、`scripts/run_backtest_replay.py`
任務目的：驗證入榜天數對 1D / 3D / 5D / 10D replay 報酬、勝率、MAE、MFE 的影響，判斷是否值得進 shadow feature
證據路徑：`artifacts/backtest/persistence_study_YYYY-MM-DD.json`、`artifacts/candidate_persistence_backtest_verification_latest.json`

## 背景

動能策略不應假設「入榜越久越好」。入榜天數可能代表：

- 第 1 天：剛突破，尚未確認。
- 第 2-3 天：動能延續。
- 第 4-5 天：趨勢可能成熟。
- 第 6 天以上：可能過熱或追高。

因此本卡只做研究分組，不改模型、不改 ranking。

## 實作

- 新增 `scripts/research_candidate_persistence_backtest.py`。
- 先呼叫 production replay 取得 D+1 交易結果。
- 對每個 ranking date 重新建立當日以前的 persistence index。
- 將 `consecutive_ranked_days`、`rank_delta` 合併到 trades。
- 依 streak bucket 與 rank delta direction 分組統計。

## 契約

- 不讀未來 ranking。
- 不訓練模型。
- 不重跑 ranking。
- 不改 `risk_adjusted_score`。
- 只輸出 research artifact。

## 驗收

- `scripts/verify_candidate_persistence_backtest.py` 使用 TemporaryDirectory synthetic ranking / OHLC。
- 驗證 2026-01-06 的股票不會吃到 2026-01-07 ranking。
- 驗證 `1D::1` 與 `1D::2-3` 分組存在。
- 驗證 JSON 不含 NaN。
- `py_compile` 與 `git diff --check` 通過。

## 判讀

這張卡不直接決定進模型，只回答：

- 入榜第 2-3 天是否比第 1 天穩？
- 排名進步是否比排名退步好？
- 某些 streak bucket 是否有較差 MAE / hit rate？

若結果穩定改善，才開 `FEATURE-EXP-01` 的 shadow feature gate。
