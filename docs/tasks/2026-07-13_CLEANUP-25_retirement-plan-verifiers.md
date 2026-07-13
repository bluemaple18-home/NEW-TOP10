# CLEANUP-25｜Verifier 退休／合併計畫

- status: completed
- priority: P1
- task thickness: standard

## 目標

把前輪 12 支 `archive_candidate` verifier 分成 `retire_delete`、`retain_contract`、`merge_candidate`、`unknown`，優先找出重複 schema 驗證與可由共用 verifier 取代的群組；本卡不改程式、不刪檔。

## 範圍

- `scripts/verify_odd_lot_candidate_comparison_report.py`
- `scripts/verify_odd_lot_exit_horizon_sensitivity_report.py`
- `scripts/verify_odd_lot_exit_strategy_report.py`
- `scripts/verify_odd_lot_exposure_sensitivity_report.py`
- `scripts/verify_odd_lot_regime_sensitivity_report.py`
- `scripts/verify_odd_lot_regime_throttle_report.py`
- `scripts/verify_operational_rule_validation_report.py`
- `scripts/verify_regime_conditional_hybrid_report.py`
- `scripts/verify_regime_conditional_shadow_rankings.py`
- `scripts/verify_training_candidate_risk_attribution.py`
- `scripts/verify_training_candidate_risk_control_report.py`
- `scripts/verify_weekend_overnight_campaign_summary.py`

## 可改檔案

- `.work/CLEANUP-25/evidence/verifier-retirement-plan.json`（新增）
- 本卡 status/result

## 證據契約

每支記錄 `path/verdict/confidence/builder_pair/input_schema/unique_assertions/replacement_test_or_verifier/retained_consumers/rationale`。沒有證明 assertion 等價替代時不得判 `retire_delete/high`；可合併者必須列出共同欄位與仍須保留的特有 assertion。

## 驗收

- 12/12 分類，輸出可實作的合併群組與建議批次。
- JSON deterministic、repo-relative；不改 code/config/artifact。
- `git diff --check` 通過；只提交卡片與 evidence。

## 回報

建立單一 atomic commit；回報可刪、需保留與合併方案，不 merge、不 push。

## Result

- evidence: `.work/CLEANUP-25/evidence/verifier-retirement-plan.json`
- coverage: 12/12；`retire_delete=0`、`retain_contract=2`、`merge_candidate=10`、`unknown=0`
- merge groups: odd-lot research contract（6）、regime conditional research（2）、training candidate risk（2）
- retained contracts: `scripts/verify_operational_rule_validation_report.py`、`scripts/verify_weekend_overnight_campaign_summary.py`
- deletion gate: 無任何項目具備已證明的等價替代 verifier；不得直接刪除。

## Verification

- JSON 可解析、12 entries、path 排序、repo-relative，且每筆包含 builder pair、input schema、unique assertions、replacement、retained consumers 與 rationale。
- 未修改 `scripts/`、`app/`、`config/` 或 runtime artifacts；只新增本卡 evidence 並更新本卡結果。
- `git diff --check` 應於提交前執行。
