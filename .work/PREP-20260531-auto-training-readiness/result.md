# Result

## 目前結果
已完成。readiness 已拆成 training launch gate 與 production promotion gate；正式自動訓練候選可啟動，正式升版仍維持 blocked。

## 已知狀態
- `training_automation_readiness` 目前為 `READY_FOR_AUTOMATED_TRAINING_REVIEW`。
- `training_launch_ready=true`。
- `training_launch_mode=pre_registered_candidate_with_promotion_gate`。
- `promotion_ready=false`。
- `auto_retrain_enabled=false`。
- `auto_retrain_readiness=READY_WITH_MONITORING_WARNINGS`。
- half-year decision 目前為 `MONITOR_ONLY`，已改列為 production promotion blocker；不阻擋預註冊訓練候選啟動。
- `revenue_yoy` / `revenue_mom` 缺口已列為 `data_unavailable_with_explicit_degradation`，允許 technical-only training launch review，但不可 promotion。
- `ranking.realized_outcome` 成熟樣本不足已列為時間未成熟的 monitoring warning，不當作模型失敗。
- 下一階段實驗入口已列出 `model_exp_combined_conservative` 的 `NOT_APPROVED` 條件，不直接批准 promotion。
- blocker detail 數量與 blocker 數量一致：`0/0`。
- warning detail 數量與 warning 數量一致：`7/7`。
- promotion blocker detail 數量與 promotion blocker 數量一致：`4/4`。
- blocker summary：
  - `must_fix_before_training`: 0
  - `data_unavailable_with_explicit_degradation`: 0
  - `waiting_for_approved_experiment`: 0
  - `acceptable_monitoring_warning`: 0
- promotion blocker summary：
  - `must_fix_before_training`: 1
  - `data_unavailable_with_explicit_degradation`: 1
  - `waiting_for_approved_experiment`: 2

## 不可誤讀
- 這代表可以開始自動訓練候選，不代表可以自動 promotion。
- readiness artifact 不會也不能覆蓋 `models/latest_lgbm.pkl`。
- `MONITOR_ONLY` 仍然擋正式升版。
- revenue technical-only 降級只允許 research / training launch，不允許 promotion。

## 證據
- `uv run --with-requirements requirements.txt python scripts/verify_training_automation_readiness.py --skip-model-research-flow --timeout-seconds 900`：OK，輸出 `READY_FOR_AUTOMATED_TRAINING_REVIEW`。
- `uv run --with-requirements requirements.txt python scripts/verify_model_group_acceptance.py`：OK，輸出 `auto_retrain=READY_WITH_MONITORING_WARNINGS`。
- `python3 -m py_compile scripts/verify_training_automation_readiness.py`：OK。
- `python3 -m py_compile scripts/verify_half_year_walkforward_no_hindsight.py scripts/research_regime_feature_offline_ablation.py`：OK。
- `jq` 驗證 blocker / warning / promotion blocker detail 數量與 category summary：OK。
- `TOP10_RESOURCE_PROFILE=host_full bash scripts/daily_retrain.sh readiness`：OK，正式 wrapper 入口輸出 `READY_FOR_AUTOMATED_TRAINING_REVIEW`。
- `TOP10_RESOURCE_PROFILE=host_full bash scripts/daily_retrain.sh retrain --dry-run --trigger manual`：OK，`automation_status.json` 顯示 `dry_run=true`、`mode=retrain`、`sealed_oos.capacity.retrain_preflight=OK`、`model.train=DRY_RUN`。
- 確認 dry-run 沒有真的建立預期 backup model：`models/backup/lgbm_20260531_202923.pkl` 不存在。
- `git diff --check`：OK。
- 更新 artifact：`artifacts/training_automation_readiness_2026-05-31.json`、`artifacts/training_automation_readiness_2026-05-31.md`。
