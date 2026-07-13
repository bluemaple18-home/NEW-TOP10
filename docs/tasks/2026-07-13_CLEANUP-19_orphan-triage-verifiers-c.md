# CLEANUP-19｜Orphan Triage：Verifiers C

- status: completed
- priority: P1
- task thickness: standard

## 目標

對 alpha／candidate／exit／odd-lot 相關 26 支 verifier 做成對關係與 artifact consumer 分級；本卡不刪檔。

## 範圍

- `scripts/verify_alpha_candidate_features.py`
- `scripts/verify_alpha_candidate_offline_ablation.py`
- `scripts/verify_alpha_candidate_overlay.py`
- `scripts/verify_alpha_candidate_overlay_replay.py`
- `scripts/verify_alpha_candidate_signal_check.py`
- `scripts/verify_backtest_acceptance_report.py`
- `scripts/verify_candidate_historical_validation_gap_report.py`
- `scripts/verify_candidate_trail10_daily_shadow_monitor.py`
- `scripts/verify_candidate_trail10_retention_diagnostics.py`
- `scripts/verify_clawd_live_send_config.py`
- `scripts/verify_consensus_publish_top10.py`
- `scripts/verify_exit_rule_half_year_decision_report.py`
- `scripts/verify_exit_rule_portfolio_level_report.py`
- `scripts/verify_exit_rule_rolling_regime_report.py`
- `scripts/verify_feature_group_ablation_by_regime.py`
- `scripts/verify_gross55_operational_shadow_dry_run.py`
- `scripts/verify_high_choppy_context_overlay.py`
- `scripts/verify_long_candidate_validation_report.py`
- `scripts/verify_odd_lot_candidate_comparison_report.py`
- `scripts/verify_odd_lot_candidate_decision_report.py`
- `scripts/verify_odd_lot_exit_horizon_sensitivity_report.py`
- `scripts/verify_odd_lot_exit_strategy_report.py`
- `scripts/verify_odd_lot_exposure_sensitivity_report.py`
- `scripts/verify_odd_lot_portfolio_replay.py`
- `scripts/verify_odd_lot_regime_sensitivity_report.py`
- `scripts/verify_odd_lot_regime_throttle_report.py`

## 可改檔案

- `.work/CLEANUP-19/evidence/orphan-triage.json`（新增）
- 本卡 status/result

## 不可改

- 所有候選與其他 code/config/docs/artifacts
- 不執行 production daily/retrain/send，不刪檔

## 證據契約

沿用 CLEANUP-17 schema。額外確認 builder/verifier 是否成對、輸入 artifact 是否仍由 tracked code 產生、驗證契約是否被其他 test 取代。名稱相近不能單獨視為 consumer；無法證明替代驗證時不得判高信心刪除。

## 驗收

- 26/26 全數分類；paired builder、artifact 與替代測試均有證據。
- JSON deterministic、repo-relative、無本機絕對路徑。
- `git diff --check` 通過；只提交卡片與 evidence。

## 回報

建立單一 atomic commit；回報分類統計、可合併／可刪候選及保留理由，不 merge、不 push。

## Result

- 完成 26/26 verifier 分類；證據檔：`.work/CLEANUP-19/evidence/orphan-triage.json`。
- 統計：`retain=15`、`unknown=5`、`archive_candidate=6`、`delete_candidate=0`。
- 15 支 retain 有 builder／research pair、artifact consumer 或 gate 證據；5 支因外部 runtime、現況 artifact 或下游使用不足列 `unknown`；6 支 odd-lot standalone verifier 僅列低風險 archive review candidate，不代表可刪。
- 未發現可高信心刪除或可直接合併項目；名稱相近的 verifier 未當作替代測試，所有缺乏替代證據者保守保留或列 unknown。
- 只修改本卡與 evidence；未刪檔、未修改或執行 production code/daily/retrain/send，未 merge、未 push。

## Verification

- JSON parse、26 entries、26 unique paths、path sort、required fields、repo-relative path：PASS。
- `git diff --check`：PASS。
