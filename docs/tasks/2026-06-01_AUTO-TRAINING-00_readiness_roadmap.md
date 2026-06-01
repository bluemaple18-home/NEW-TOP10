# AUTO-TRAINING-00 readiness roadmap

## 任務ID

`AUTO-TRAINING-00`

## 卡片類型｜派工對象

Roadmap / Training Readiness｜Codex

## 任務目的

把目前離「可長期自動訓練候選」還差的工作收斂成 5 張可執行卡，避免把治理、資料、盤勢、模型 promotion 混在同一個任務裡。

## 目前狀態

`training_launch_ready=true`，代表可以準備啟動自動訓練候選。

`promotion_ready=false`，代表沒有任何模型可正式升版。

## 卡片順序

1. `AUTO-TRAINING-01`：收掉 `MODEL-GOV-FULL` review，建立治理基線。
2. `AUTO-TRAINING-02`：補 `candidate_persistence` materializer，解除 blocked experiment。
3. `AUTO-TRAINING-03`：做 `BIG_BULL` ranking/replay 實驗，不升正式盤勢模型。
4. `AUTO-TRAINING-04`：處理 `revenue_yoy` / `revenue_mom` 缺口，或正式化 technical-only lane。
5. `AUTO-TRAINING-05`：拆半年 walk-forward 負 fold，開下一輪 no-hindsight 診斷實驗。

## 依賴圖

```text
AUTO-TRAINING-01
  -> AUTO-TRAINING-02
      -> AUTO-TRAINING-03
  -> AUTO-TRAINING-04
  -> AUTO-TRAINING-05
```

`AUTO-TRAINING-03` 可以和 `AUTO-TRAINING-04/05` 平行，但不得進 promotion。

## 全域不可做

- 不覆蓋 `models/latest_lgbm.pkl`。
- 不修改 production ranking / `risk_adjusted_score`。
- 不把 `MONITOR_ONLY` 當 promotion evidence。
- 不讓 ledger 取代 sealed OOS / replay / rollback / model group acceptance。
- 不用同輪診斷結果回頭修改同一輪 gate。

## 最終目標

完成後應達到：

- 自動訓練候選可啟動。
- 每個候選都有 ledger entry。
- blocked experiments 有清楚下一步。
- 月營收缺口有明確降級或資料修補策略。
- `BIG_BULL` 只作 ranking/replay follow-up，不被誤升成正式盤勢模型。
- 半年 walk-forward 負 fold 進下一輪假設，不做後照鏡修補。
