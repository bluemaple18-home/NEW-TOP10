# CLEANUP-27｜Odd-lot decision builder suite 收斂

- status: ready
- priority: P1
- task thickness: strict
- blocked_by: none（REFACTOR-05 已整合為 `5b2456a`）

## 目標

將 odd-lot decision chain 的三支分析 builder 與一支 candidate decision builder 收斂為 `scripts/build_odd_lot_decision_suite.py`，保留各 profile 的 JSON／Markdown 欄位、決策與失敗語意；只有逐欄 parity 與 consumer gate 通過才退休四支舊入口。

## 預計範圍

- `scripts/build_odd_lot_decision_suite.py`（新增）
- `tests/test_odd_lot_decision_suite.py`（新增）
- 以下四支舊入口僅在 parity 通過後刪除：
  - `scripts/build_odd_lot_candidate_decision_report.py`
  - `scripts/build_odd_lot_exit_horizon_sensitivity_report.py`
  - `scripts/build_odd_lot_exit_strategy_report.py`
  - `scripts/build_odd_lot_regime_throttle_report.py`
- `scripts/verify_odd_lot_candidate_decision_report.py` 僅允許做必要的 suite/profile 相容調整；其獨特 checks 不得刪除或弱化。
- `config/script_lifecycle.yaml`（同步新舊入口）
- `.work/CLEANUP-27/evidence/parity.json`、`status.md`、`result.md`

## 明確保留，不納入本卡

- `scripts/build_odd_lot_candidate_comparison_report.py`
- `scripts/build_odd_lot_exposure_sensitivity_report.py`
- `scripts/build_odd_lot_regime_sensitivity_report.py`
- 六支 odd-lot research verifier 的共用化另開 REFACTOR-07，不在本卡順手處理。

## 不可改

- 每日報牌、publish、模型、權重、正式排名、launchd、plist、automation
- 不重跑訓練、不寫正式 artifact、不改研究結論
- 不以單一 generic schema 抹平 horizon、exit strategy、regime throttle、candidate decision 的特有欄位與 assertion
- 不刪除有 active consumer 或無等價替代證據的入口

## 契約與驗收

- 先寫 valid／invalid fixture parity 測試，再做最小實作。
- suite 必須保留 `exit_horizon`、`exit_strategy`、`regime_throttle`、`candidate_decision` 四個具名 profile／section。
- old/new 對同一 fixture 的 schema、status、summary/decision、missing/error 條件與 Markdown 逐欄等價。
- candidate decision profile 必須仍可被 `verify_odd_lot_candidate_decision_report.py` 驗證；必要相容調整需有 valid／invalid 回歸測試。
- 先重查 repo/runtime consumer；parity 或 consumer gate 未通過時保留全部舊入口並回報 blocker，不可半套退休。
- 通過後跑 reference/lifecycle strict audits、相關測試、完整 pytest、`git diff --check` 與每日四檔 hash gate。
- 不提交大型可重現 audit 原始 JSON；保留精簡驗證摘要與必要 parity 證據即可。

## 回報

單一 atomic commit，不 merge、不 push；主線讀取實際 diff 與證據後才決定整合，整合驗證通過即封存任務並回收 worktree。
