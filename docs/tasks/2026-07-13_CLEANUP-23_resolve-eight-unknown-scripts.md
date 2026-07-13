# CLEANUP-23｜解除八支 unknown 腳本

- status: ready
- priority: P0
- task thickness: strict

## 目標

針對前輪仍為 `unknown` 的 8 支工具補齊 repo 外 runtime、人工 SOP、成對 builder/verifier 與 artifact consumer 證據，分類為 `retain`、`archive_candidate`、`delete_candidate` 或維持 `unknown`；本卡不改程式、不刪檔。

## 範圍

- `scripts/build_consensus_publish_top10.py`
- `scripts/run_controlled_grid_drain_host_runner.sh`
- `scripts/sync_from_remote.sh`
- `scripts/verify_clawd_live_send_config.py`
- `scripts/verify_consensus_publish_top10.py`
- `scripts/verify_exit_rule_half_year_decision_report.py`
- `scripts/verify_exit_rule_portfolio_level_report.py`
- `scripts/verify_exit_rule_rolling_regime_report.py`

## 可改檔案

- `.work/CLEANUP-23/evidence/unknown-resolution.json`（新增）
- 本卡 status/result

## 不可改

- 所有 scripts/config/plist/docs architecture/artifacts
- 不執行 sync、push、send、daily、retrain，不改 launchd/cron/外部狀態

## 證據契約

每項記錄 `path/verdict/confidence/repo_consumers/external_runtime_checks/paired_scripts/artifact_consumers/git_history/rationale`。shell、sync、publish、live-send 只有在 launchd、cron、shell profile、人工 SOP 與 handoff 都能排除時才可判高信心刪除；證據不足維持 `unknown`。

## 驗收

- 8/8 無重複、無漏項；證據 repo-relative、無 token/secret/本機絕對路徑。
- 所有外部檢查唯讀且在 JSON 說明查核邊界。
- `git diff --check` 通過；只提交卡片與 evidence。

## 回報

建立單一 atomic commit；回報分類、外部 consumer 與仍無法解除的 blocker，不 merge、不 push。
