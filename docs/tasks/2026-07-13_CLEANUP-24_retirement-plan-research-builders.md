# CLEANUP-24｜研究／Builder 退休計畫

- status: complete
- priority: P1
- task thickness: standard

## 目標

把前輪 31 支 `archive_candidate` 轉成可執行退休決策：`retire_delete`、`retain_reproducibility`、`merge_candidate`、`unknown`。本卡只產生證據與成組建議，不搬移、不刪檔。

## 範圍

- `scripts/build_big_bull_family_only_sealed_rollback_prep.py`
- `scripts/build_candidate_historical_validation_gap_report.py`
- `scripts/build_exit_rule_half_year_decision_report.py`
- `scripts/build_exit_rule_portfolio_level_report.py`
- `scripts/build_exit_rule_rolling_regime_report.py`
- `scripts/build_odd_lot_candidate_comparison_report.py`
- `scripts/build_odd_lot_candidate_decision_report.py`
- `scripts/build_odd_lot_exit_horizon_sensitivity_report.py`
- `scripts/build_odd_lot_exit_strategy_report.py`
- `scripts/build_odd_lot_exposure_sensitivity_report.py`
- `scripts/build_odd_lot_regime_sensitivity_report.py`
- `scripts/build_odd_lot_regime_throttle_report.py`
- `scripts/build_operational_rule_candidate_report.py`
- `scripts/build_operational_rule_experiment_report.py`
- `scripts/build_overnight_risk_matrix_summary.py`
- `scripts/build_portfolio_overlay_promotion_review.py`
- `scripts/build_portfolio_replay_regime_attribution.py`
- `scripts/build_regime_conditional_hybrid_report.py`
- `scripts/build_regime_conditional_shadow_rankings.py`
- `scripts/build_training_candidate_risk_attribution.py`
- `scripts/build_training_candidate_risk_control_report.py`
- `scripts/build_weekend_overnight_campaign_audits.py`
- `scripts/build_weekend_ranking_dir_unlock_smoke.py`
- `scripts/build_weekend_unsupported_unlock_audit.py`
- `scripts/compare_portfolio_replay_variants.py`
- `scripts/research_alpha_candidate_signal_check.py`
- `scripts/research_ranking_score_shadow.py`
- `scripts/research_risk_off_narrow_routing.py`
- `scripts/run_a1_forward_shadow_monitor.py`
- `scripts/run_candidate_stress_matrix.py`
- `scripts/run_overnight_shadow_training.py`

## 可改檔案

- `.work/CLEANUP-24/evidence/retirement-plan.json`（新增）
- 本卡 status/result

## 證據契約

沿用 CLEANUP-17/18 證據，額外列出 `rebuild_value`、`unique_contract`、`retained_consumers`、`replacement_or_merge_target`、`recommended_batch`。只有能證明無 runtime consumer、無唯一契約、歷史 artifact 已足以留存且無必要重建者，才可判 `retire_delete/high`。

## 驗收

- 31/31 分類，並提供互斥、可分批執行的刪除／合併群組。
- 不把「移到 archive 目錄」當作完成方案。
- JSON deterministic、repo-relative；`git diff --check` 通過；只提交卡片與 evidence。

## 回報

建立單一 atomic commit；回報可安全退休數量、需保留重現者與合併群組，不 merge、不 push。

## 結果

- retirement plan：`.work/CLEANUP-24/evidence/retirement-plan.json`
- 分類：`retire_delete` 2、`retain_reproducibility` 8、`merge_candidate` 20、`unknown` 1（共 31）。
- 本卡僅完成規劃；所有刪除與合併批次均保留執行前 runtime 重查條件。
