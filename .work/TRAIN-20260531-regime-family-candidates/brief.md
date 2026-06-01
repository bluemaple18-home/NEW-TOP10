# TRAIN-20260531-regime-family-candidates

## 卡片類型
Model Training Prep / Research

## 任務目的
針對 PM 指定的「高檔震盪盤」與「大牛市」建立預註冊、可重跑、不可後照鏡的訓練候選研究，判斷是否值得進下一階段 sealed OOS / replay / promotion review。

## Scope
- 建立 `HIGH_CHOPPY` 與 `BIG_BULL` 的預註冊定義。
- 比較 `global_baseline`、`family_only_training`、`family_weighted_training`。
- 只產 research artifact，不保存模型。
- 樣本不足時必須降級 `MONITOR_ONLY`。

## Out Of Scope
- 不正式 retrain。
- 不覆蓋 `models/latest_lgbm.pkl`。
- 不改 production ranking score。
- 不用同輪結果補新 filter。

## 驗收條件
- `scripts/research_regime_family_training_candidates.py` 可產出 artifact。
- `scripts/verify_regime_family_training_candidates.py` 驗證通過。
- artifact 明確標出 family date count、selected candidate、decision、promotion restriction。
- `git diff --check` 通過。
