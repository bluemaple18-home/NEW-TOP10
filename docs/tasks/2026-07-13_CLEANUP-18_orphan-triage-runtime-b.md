# CLEANUP-18｜Orphan Triage：Runtime／Research B

- status: ready
- priority: P0
- task thickness: strict

## 目標

對下列 28 支 portfolio／weekend／research／runtime 工具做證據分級，特別排除 launchd、cron、外部 shell、人工 SOP 等 repo 外 consumer；本卡不刪檔。

## 範圍

- `scripts/build_overnight_risk_matrix_summary.py`
- `scripts/build_portfolio_overlay_promotion_review.py`
- `scripts/build_portfolio_replay_regime_attribution.py`
- `scripts/build_production_baseline_materialization_review.py`
- `scripts/build_regime_conditional_hybrid_report.py`
- `scripts/build_regime_conditional_shadow_rankings.py`
- `scripts/build_training_candidate_risk_attribution.py`
- `scripts/build_training_candidate_risk_control_report.py`
- `scripts/build_weekend_overnight_campaign_audits.py`
- `scripts/build_weekend_production_baseline_source_audit.py`
- `scripts/build_weekend_ranking_dir_unlock_smoke.py`
- `scripts/build_weekend_unsupported_unlock_audit.py`
- `scripts/com.new-top10.external-review-preflight.plist`
- `scripts/compare_portfolio_replay_variants.py`
- `scripts/push_changes.sh`
- `scripts/research_alpha_candidate_signal_check.py`
- `scripts/research_map_linkage_smoke.py`
- `scripts/research_ranking_score_shadow.py`
- `scripts/research_risk_off_narrow_routing.py`
- `scripts/research_vwap_cost_basis.py`
- `scripts/run_a1_forward_shadow_monitor.py`
- `scripts/run_candidate_stress_matrix.py`
- `scripts/run_controlled_grid_drain_host_runner.sh`
- `scripts/run_overnight_shadow_training.py`
- `scripts/run_production_trail10_batch_08_10.py`
- `scripts/run_training_candidate_replay_flow.py`
- `scripts/send_pm_review_card_local.sh`
- `scripts/sync_from_remote.sh`

## 可改檔案

- `.work/CLEANUP-18/evidence/orphan-triage.json`（新增）
- 本卡 status/result

## 不可改

- 所有候選檔、`app/`、`config/`、其他 plist/docs/artifacts
- 不 unload/reload、不改 cron/launchd、不執行 runner/send/sync/push

## 證據契約

每項記錄 CLEANUP-17 相同欄位，另加 `external_runtime_checks`。可唯讀檢查 repo plist、目前 `launchctl list`、crontab 文字與 Git history；不得改外部狀態。shell、sync、push、send、plist 缺外部證據時不得判 `delete_candidate/high`。

## 驗收

- 28/28 全數分類；production／外部 runtime 不確定性明確標示。
- JSON deterministic、repo-relative、無 secret／token／本機絕對路徑。
- `git diff --check` 通過；只提交卡片與 evidence。

## 回報

建立單一 atomic commit；回報統計、外部 runtime 發現與高信心候選，不 merge、不 push、不改外部狀態。
