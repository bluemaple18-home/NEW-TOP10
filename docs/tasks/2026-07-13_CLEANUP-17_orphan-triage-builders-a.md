# CLEANUP-17｜Orphan Triage：Builders A

- status: ready
- priority: P1
- task thickness: standard

## 目標

對下列 27 支無 tracked reference 的分析／builder 工具做證據分級，區分 `retain`、`archive_candidate`、`delete_candidate`、`unknown`；本卡不刪檔。

## 範圍

- `scripts/analyze_fixed_share_persistence.py`
- `scripts/backtest_overlap_first_recommendation_performance.py`
- `scripts/build_alpha_candidate_features.py`
- `scripts/build_big_bull_blocker_resolution_report.py`
- `scripts/build_big_bull_family_only_sealed_rollback_prep.py`
- `scripts/build_big_bull_sealed_split_policy_decision.py`
- `scripts/build_borrow_squeeze_materialized_features.py`
- `scripts/build_candidate_historical_validation_gap_report.py`
- `scripts/build_candidate_trail10_retention_diagnostics.py`
- `scripts/build_consensus_publish_top10.py`
- `scripts/build_constrained_shadow_comparison.py`
- `scripts/build_exit_rule_half_year_decision_report.py`
- `scripts/build_exit_rule_portfolio_level_report.py`
- `scripts/build_exit_rule_rolling_regime_report.py`
- `scripts/build_mainline_a_regime_validation.py`
- `scripts/build_mass_candidate_sector_cap_extension.py`
- `scripts/build_mass_candidate_shadow_dry_run.py`
- `scripts/build_odd_lot_candidate_comparison_report.py`
- `scripts/build_odd_lot_candidate_decision_report.py`
- `scripts/build_odd_lot_exit_horizon_sensitivity_report.py`
- `scripts/build_odd_lot_exit_strategy_report.py`
- `scripts/build_odd_lot_exposure_sensitivity_report.py`
- `scripts/build_odd_lot_regime_sensitivity_report.py`
- `scripts/build_odd_lot_regime_throttle_report.py`
- `scripts/build_operational_long_rule_validation_report.py`
- `scripts/build_operational_rule_candidate_report.py`
- `scripts/build_operational_rule_experiment_report.py`

## 可改檔案

- `.work/CLEANUP-17/evidence/orphan-triage.json`（新增）
- 本卡 status/result

## 不可改

- 所有 `scripts/`、`app/`、`config/`、plist、docs architecture 與 artifacts
- 不執行 production daily/retrain/send，不搬移或刪除檔案

## 證據契約

每支工具記錄：`path`、`verdict`、`confidence`、`git_last_commit`、`repo_reference_count`、`paired_scripts`、`output_artifacts`、`runtime_evidence`、`reason`。`delete_candidate/high` 必須同時證明無 repo consumer、無外部 runtime 證據、無唯一 artifact consumer、無仍在使用的成對工具；證據不足一律 `unknown`。

## 驗收

- 27/27 全數有分類且無重複、無漏項。
- JSON 依 path 排序、repo-relative、無本機絕對路徑。
- `git diff --check` 通過；只提交卡片與 evidence。

## 回報

建立單一 atomic commit；回報四類統計、高信心刪除候選及阻擋刪除的證據，不 merge、不 push。
