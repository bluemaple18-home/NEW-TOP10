# PREP-20260531-auto-training-readiness

## 卡片類型
Preparation / Readiness Fix

## 任務目的
補齊正式自動模型訓練前仍未完成的事前準備，讓 `training_automation_readiness` 從 `PREPARED_WITH_BLOCKERS` 收斂到可人工 review 的狀態。

## 背景
目前 half-year walk-forward 與 no-hindsight governance 已接進 readiness，但正式自動訓練仍被阻擋。現況不是模型可自動訓練，而是治理閘門已可 review。這張卡負責處理治理之外的 readiness blockers 與資料缺口。

## Scope
- 分類處理 `artifacts/training_automation_readiness_2026-05-31.json` 的 blockers / warnings。
- 查明 `model health is WARN` 的來源是否為真問題、樣本成熟度不足、或可接受的暫時狀態。
- 查明 `model_group auto_retrain_readiness is BLOCKED` 還缺哪些硬條件。
- 查明基本面 / 月營收資料為空是否會影響本輪大量測試；若不能立即補齊，需明確降級策略與 verifier 表示方式。
- 查明目前沒有 experiment approved for next-stage training 的原因，並定義下一個可驗證實驗需要補哪份 artifact。
- 更新必要的 readiness 文件或 verifier，讓「可訓練 / 不可訓練 / 只能 monitor」不靠人工口頭判斷。

## Out Of Scope
- 不正式 retrain。
- 不覆蓋 `models/latest_lgbm.pkl`。
- 不開啟 auto retrain 排程。
- 不改 production ranking score。
- 不用 post-hoc negative fold 直接補同輪 filter。
- 不把 `MONITOR_ONLY` 解讀成可 promotion。

## 驗收條件
- `uv run --with-requirements requirements.txt python scripts/verify_training_automation_readiness.py --skip-model-research-flow --timeout-seconds 900` 可清楚輸出剩餘 blocker 分類。
- 每個 blocker 必須被分類為：
  - `must_fix_before_training`
  - `acceptable_monitoring_warning`
  - `data_unavailable_with_explicit_degradation`
  - `waiting_for_approved_experiment`
- 基本面 / 月營收缺口不得靜默通過；若降級，artifact 必須明確寫出降級理由。
- 至少定義一個「下一階段可驗證實驗」的進入條件，但不得直接批准 promotion。
- `git diff --check` 通過。

## 已知 Blockers
- `model health is WARN`
- `model_group auto_retrain_readiness is BLOCKED`
- `no model experiment is approved for next-stage training yet`

## 已知 Warnings
- `waiting experiments: model_exp_combined_conservative`
- `half-year research decision is MONITOR_ONLY`
- half-year negative / flat folds 僅可作 diagnostic：
  - `2026-02-06~2026-03-17`
  - `2026-04-17~2026-05-15`

## Review / Decision Questions
- [P1] `MONITOR_ONLY` 在正式自動化前應該維持 warning，還是提升成 blocker？
- [P1] 基本面資料缺口若短期補不齊，是否允許先以 technical-only 模型進行 research，但禁止 promotion？
- [P2] PSI baseline feature 數量不一致 `84 < 86` 是資料漂移、監控欄位缺漏，還是可接受的監控差異？
- [P2] ranking realized outcome 成熟樣本不足時，是否需要明確標成「時間未成熟」而非模型失敗？
- [P2] 下一個實驗批准條件應該以 half-year baseline、sealed OOS、replay，還是三者共同 gate？
