# REFACTOR-05｜Exit-rule validation suite 收斂

- status: completed
- priority: P1
- task thickness: strict
- blocked_by: none（CLEANUP-26 已整合為 `3413b18`）

## 目標

將三支 exit-rule report builder 與三支 verifier 收斂為一組具 profile／section 的 builder + verifier，保留現有 JSON／Markdown 決策欄位與失敗語意；只有 parity 證據通過才退休舊入口。

## 預計範圍

- `scripts/build_exit_rule_validation_suite.py`（新增）
- `scripts/verify_exit_rule_validation_suite.py`（新增）
- `tests/test_exit_rule_validation_suite.py`（新增）
- 以下六支舊入口僅在 parity 通過後刪除：
  - `scripts/build_exit_rule_half_year_decision_report.py`
  - `scripts/build_exit_rule_portfolio_level_report.py`
  - `scripts/build_exit_rule_rolling_regime_report.py`
  - `scripts/verify_exit_rule_half_year_decision_report.py`
  - `scripts/verify_exit_rule_portfolio_level_report.py`
  - `scripts/verify_exit_rule_rolling_regime_report.py`
- `config/script_lifecycle.yaml`（同步新舊入口）
- `.work/REFACTOR-05/evidence/parity.json`、status/result

## 不可改

- 每日報牌、publish、模型、正式排名、launchd、plist、automation
- 不重跑訓練、不改權重、不寫正式 artifact
- 不以單一 generic schema 刪除各 profile 的特有 assertion

## 契約與驗收

- 先寫 valid／invalid fixture parity 測試，再做最小實作。
- suite 必須保留 half-year decision、portfolio-level、rolling-regime 三個具名 profile／section。
- old/new 對同一 fixture 的 status、decision、checks 與錯誤條件逐欄等價；特有 assertion 不得遺失。
- parity 未通過時保留全部舊入口並回報 blocker，不可半套退休。
- 通過後跑 reference/lifecycle audit、相關測試、完整 pytest、`git diff --check` 與每日控制檔 hash gate。

## 回報

CLEANUP-26 整合後才可派工；單一 atomic commit，不 merge、不 push。
