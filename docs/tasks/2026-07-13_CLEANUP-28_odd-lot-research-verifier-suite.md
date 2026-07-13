# CLEANUP-28｜Odd-lot research verifier suite 收斂

- status: ready
- priority: P1
- task thickness: standard
- blocked_by: CLEANUP-27 已整合為 `0883601`

## 目標

把六支非 candidate-decision 的 odd-lot research verifier 收斂為 `scripts/verify_odd_lot_research_suite.py`，以具名 profile 保留每支 verifier 的 report schema、verification schema、checks 名稱／值／順序、summary、exit code 與輸出格式。只有 valid／invalid parity 與 consumer gate 全通過才退休舊入口。

## 預計範圍

- 新增 `scripts/verify_odd_lot_research_suite.py`
- 新增 `tests/test_odd_lot_research_verifier_suite.py`
- 必要時只調整 `tests/test_odd_lot_decision_suite.py` 的 verifier import，不弱化既有 assertion
- 更新 `config/script_lifecycle.yaml`
- 以下六支舊入口僅在 parity 與 consumer gate 通過後刪除：
  - `scripts/verify_odd_lot_candidate_comparison_report.py`
  - `scripts/verify_odd_lot_exit_horizon_sensitivity_report.py`
  - `scripts/verify_odd_lot_exit_strategy_report.py`
  - `scripts/verify_odd_lot_exposure_sensitivity_report.py`
  - `scripts/verify_odd_lot_regime_sensitivity_report.py`
  - `scripts/verify_odd_lot_regime_throttle_report.py`
- 證據：`.work/CLEANUP-28/evidence/parity.json`、`status.md`、`result.md`

## 必須保留的 profiles

- `candidate_comparison`
- `exit_horizon`
- `exit_strategy`
- `exposure_sensitivity`
- `regime_sensitivity`
- `regime_throttle`

## 明確保留，不納入本卡

- `scripts/verify_odd_lot_candidate_decision_report.py`：保留獨立入口與全部 15 個 checks
- `scripts/verify_odd_lot_capital_matrix_report.py`
- `scripts/verify_odd_lot_portfolio_replay.py`
- 所有 odd-lot builder、研究 artifact 與研究結論

## 不可改

- 每日報牌、publish、模型、權重、正式排名、launchd、plist、automation
- 不重新產生正式研究 artifact，不放寬或刪除任何既有 verifier check
- 不以共用 helper 改變缺欄位、錯誤 payload、failed_count、exit code 或 path 語意
- 不刪除有 active repo/runtime consumer 或無等價替代證據的入口

## 契約與驗收

- TDD：先建立六 profile valid／invalid 的 old/new parity 測試與紅燈，再做最小實作。
- parity 至少鎖定完整 verification payload（只排除 `generated_at`）、checks 名稱／值／順序、summary 與 CLI exit code。
- `tests/test_odd_lot_decision_suite.py` 的 horizon／strategy／throttle consumer 測試改接新 suite 後仍須 valid/invalid 全綠。
- 先重查 repo/runtime consumer；parity 或 consumer gate 未通過時保留相關舊入口並回報 blocker，不可半套退休。
- 通過後跑 reference/lifecycle strict audits、focused tests、完整 pytest、`git diff --check` 與每日四檔 hash gate。
- 不提交大型 raw audit JSON；只保留精簡 parity 與驗收摘要。

## 回報

單一 atomic commit，不 merge、不 push；主線讀實際 diff 與證據後才整合，整合驗證通過即封存任務並回收 worktree。
