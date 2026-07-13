# CLEANUP-20｜Orphan Triage：Verifiers D

- status: completed
- priority: P1
- task thickness: standard

## 目標

對 operational／portfolio／training／weekend 相關最後 20 支 verifier 做證據分級；本卡不刪檔。

## 範圍

- `scripts/verify_operational_long_rule_validation_report.py`
- `scripts/verify_operational_rule_validation_report.py`
- `scripts/verify_overlap_first_daily_recommendation_shadow.py`
- `scripts/verify_overlap_first_recommendation_performance.py`
- `scripts/verify_portfolio_overlay_promotion_review.py`
- `scripts/verify_portfolio_replay_regime_attribution.py`
- `scripts/verify_production_baseline_materialization_review.py`
- `scripts/verify_production_trail10_batch_08_10.py`
- `scripts/verify_reference_sources.py`
- `scripts/verify_regime_conditional_hybrid_report.py`
- `scripts/verify_regime_conditional_shadow_rankings.py`
- `scripts/verify_regime_feature_offline_ablation.py`
- `scripts/verify_training_candidate_flow.py`
- `scripts/verify_training_candidate_replay_flow.py`
- `scripts/verify_training_candidate_risk_attribution.py`
- `scripts/verify_training_candidate_risk_control_report.py`
- `scripts/verify_weekend_overnight_campaign_summary.py`
- `scripts/verify_weekend_production_baseline_source_audit.py`
- `scripts/verify_weekend_ranking_dir_unlock_smoke.py`
- `scripts/verify_weekend_unsupported_unlock_audit.py`

## 可改檔案

- `.work/CLEANUP-20/evidence/orphan-triage.json`（新增）
- 本卡 status/result

## 不可改

- 所有候選與其他 code/config/docs/artifacts
- 不執行 production daily/retrain/send，不刪檔

## 證據契約

沿用 CLEANUP-17 schema。額外檢查 training/promotion gate、weekend campaign 與 reference source 是否仍有人工 SOP、artifact schema 或 release gate 價值；只因沒有 tracked caller 不足以判定可刪。

## 驗收

- 20/20 全數分類；gate／artifact／替代測試證據可追溯。
- JSON deterministic、repo-relative、無本機絕對路徑。
- `git diff --check` 通過；只提交卡片與 evidence。

## 回報

建立單一 atomic commit；回報分類統計、高信心候選與不能刪的 gate，不 merge、不 push。

## Result

- evidence: `.work/CLEANUP-20/evidence/orphan-triage.json`
- classification: retain 14、archive_candidate 6、delete_candidate 0、unknown 0（20/20）
- 高信心封存候選：`scripts/verify_weekend_overnight_campaign_summary.py`（固定歷史日期與 blocker count，無 verifier output、tracked consumer 或 SOP）；其餘 5 支封存候選仍有 paired builder，僅建議成對封存評估。
- 不可刪 gate：production baseline materialization、production trail10、reference-source contract、overlap shadow/performance、portfolio promotion，以及 weekend source/unlock verifiers；皆有 artifact consumer、人工 SOP 或 release/production boundary contract。
- verification: JSON 已依 path 排序；僅使用 repo-relative evidence paths；未執行 production daily/retrain/send。
