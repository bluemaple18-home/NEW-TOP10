# WEEKEND-TRAINING-11 production baseline ranking source audit

## 任務目的

確認 `artifacts/backtest/production` 這個 baseline ranking 來源應該怎麼合法產生或接線。

這張卡是為了解鎖 `UNSUPPORTED_RANKING_DIR_MISSING`，不是為了直接大跑 `202,176` 格。

## 背景

上一段已完成：

```text
representative queue: 0
full universe classified: 662,256 / 662,256
expanded processed: 21,147 / 662,256
survivor deep replay: 196 / 196
survivor result: 196 MONITOR_ONLY
```

目前最大可疑缺口：

```text
UNSUPPORTED_RANKING_DIR_MISSING: 202,176
top reason: MISSING_BASELINE_RANKINGS_DIR:artifacts/backtest/production
```

`WEEKEND-TRAINING-10` 的 smoke 結論：

```text
decision: SMOKE_DONE_ARTIFACT_REQUIRED
can_expand_without_new_artifacts: false
```

也就是：不能假裝 baseline 存在，必須先確認合法來源。

## 任務範圍

請讀：

- `docs/tasks/2026-06-17_WEEKEND-TRAINING-10_unsupported_unlock_plan.md`
- `artifacts/weekend_training/weekend_unsupported_unlock_audit_2026-06-13.json`
- `artifacts/weekend_training/weekend_ranking_dir_unlock_smoke_2026-06-13.json`
- `scripts/weekend_training_common.py`
- `scripts/build_weekend_universe_inventory.py`

要做：

1. 掃描既有 artifacts，找出 production / baseline ranking 可用來源。
2. 判定 `artifacts/backtest/production` 應該是：
   - 由既有 production ranking artifact materialize。
   - 由既有 backtest production baseline 目錄改接。
   - 還是目前缺資料，不能解鎖。
3. 建立 source audit artifact，列出日期覆蓋、欄位契約、可比較性與風險。
4. 若找到合法來源，只允許提出「最小 smoke replay」下一步，不得直接展開 202,176 格。

## 明確禁止

- 不准改 production ranking。
- 不准改 `models/latest_lgbm.pkl`。
- 不准改 Clawd live publish。
- 不准把 candidate ranking 當 production baseline。
- 不准用 symlink / copy 假裝 baseline 已存在，除非 verifier 能證明來源、日期、欄位契約一致。
- 不准直接批量跑 `202,176` 格。

## 預期產物

- `artifacts/weekend_training/weekend_production_baseline_source_audit_YYYY-MM-DD.json`
- `artifacts/weekend_training/weekend_production_baseline_source_audit_YYYY-MM-DD.md`
- `artifacts/weekend_training/weekend_production_baseline_source_audit_verification_latest.json`

## 驗收標準

Audit 必須回答：

```text
baseline_source_status:
baseline_source_path:
date_coverage:
required_columns:
column_contract_ok:
comparable_with_candidate_rankings:
can_materialize_artifacts_backtest_production:
unlockable_combo_count_estimate:
next_action:
production_impact:
```

Verifier 必須確認：

- source audit status 明確是 `OK` 或 `BLOCKED`。
- `production_impact == NO_PRODUCTION_CHANGE`。
- 若 `can_materialize_artifacts_backtest_production == true`，必須有可追溯 source path 與日期覆蓋。
- 若 `can_materialize_artifacts_backtest_production == false`，必須有 blocker reason。
- 不得出現 `PROMOTION_READY`。

## 完成後的下一步

若 audit 判定可 materialize：

開 `WEEKEND-TRAINING-12_production_baseline_materialize_smoke`，只做 1 個 topic / 1 個 entry filter / 少量日期 smoke。

若 audit 判定不可 materialize：

回到研究地圖，將 `UNSUPPORTED_RANKING_DIR_MISSING` 標成 artifact blocker，不再把它當作「待跑進度」。
