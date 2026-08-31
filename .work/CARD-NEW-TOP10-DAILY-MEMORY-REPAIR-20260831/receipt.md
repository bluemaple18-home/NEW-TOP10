# Daily Memory Repair 驗收收據

## 結論

- 狀態：`GO`
- 代表日：`2026-08-31`
- 最終 source state 的峰值 process-tree RSS：`2,442,182,656 bytes`
- 三次 GREEN 峰值：`2,483,208,192`、`2,387,312,640`、`2,442,182,656 bytes`
- GREEN 最差值距 `4,026,531,840 bytes` 驗收線仍有 `1,543,323,648 bytes` headroom。
- ranking 子程序三次皆 `exit_code=0`。
- 未調高 `4 GiB` guard，未執行 production、publish、send、push、merge 或 Issue 變更。

## RED → GREEN

| 階段 | 變更 | 峰值 RSS | 結果 |
|---|---|---:|---|
| 正式 RED | `<main-checkout>/logs/storage_safety/daily_latest.json` | 4,548,247,552 | `STOPPED` |
| candidate RED | freshness 僅讀必要欄位 | 4,738,203,648 | `FAILED` |
| falsification | 再投影 universe 為 `date,stock_id` | 4,825,382,912 | `FAILED` |
| GREEN 1 | 把既有 90 日 ranking window 下推到 features/events parquet read | 2,483,208,192 | `OK` |
| GREEN 2 | 相同輸入重跑 | 2,387,312,640 | `OK` |
| final acceptance | 最終 source state 重跑 | 2,442,182,656 | `OK` |

candidate RED 與 universe-only 的峰值差異屬執行期波動；兩者均明確高於驗收線，因此「只修 freshness 即足夠」與「只投影 universe 即足夠」兩個假說皆被否證。90 日 window 下推後，三次結果皆穩定低於驗收線，所以未再擴大修復。

## Source decision 與資料契約

- CodeGraph index：`cd7f59ab5e9f9a4ac617f5576f2c8d1309b74209`。
- semantic query 追到 `StockRanker.load_daily_data → load_m4_feature_frame → build_m4_feature_frame → _join_fundamentals`，確認原流程先組裝全歷史 features/events/fundamentals，再切 90 日。
- `features.parquet`：540,431 rows；既有 90 日 window 為 122,337 rows（2026-06-02 至 2026-08-31）。
- 修復保持原本的 90 日邊界與 as-of fundamental join，只把相同 row predicate 下推到 parquet read；`load_m4_feature_frame` 未傳 `start_date` 時仍維持全歷史預設，訓練 caller 不變。
- universe 在 ranking 只用日期與股票代碼，故只讀 `date,stock_id`。
- freshness 只讀日期與啟用 market coverage 時必要的 `stock_id,market`。
- 模型、feature definitions、signals、weights、ranking policy、SHAP、report、provider、scheduler 與 guard policy 均未變更。

## 輸入與 evidence hashes

| Artifact | SHA-256 |
|---|---|
| official RED receipt | `0e165cd76d5d8e9bb45e5131d6a21fcecf8070de2b736e72a1c0b51fcf050d66` |
| features.parquet | `42afb1b0b82fdecdd99ad68b68de17455c91d31f7981348b9dc0a34e5b02a272` |
| events.parquet | `3af28116af5195ee02c9ac6005988d6139316f20cfc94a38b1b8269567eab6c2` |
| universe.parquet | `2ae2638b792595ed0e006f23c7e4d3334d38243835687272ef6bb7a3214da81f` |
| latest_lgbm.pkl | `ce64379701339bf7eadd696872efa0f64be118b4b8c58582e90691ec175c8a5d` |
| signals.yaml | `b34c1a20a705bb67f107de870ddd0cec5a2e3419aa385258370d88ceb553d60a` |
| legacy/current/repaired ranking | `586cc374e0de9039a00fe4e0d1aaab9ef6db227c0b3133a9ed604b3fdc865a7f` |

## Ranking reconciliation

- legacy、main-checkout current、原五份 measurement output、三份新 GREEN output 與 final acceptance output 的 CSV SHA-256 全部一致。
- exact-byte equality：`true`
- schema equality：`true`（45 columns）
- row count：`10 == 10`
- Top10 identity/order：`2409, 2890, 3324, 5386, 2834, 2421, 5536, 3167, 4991, 3006`
- key score fields equality：`risk_adjusted_score, final_score, model_prob, rule_score, prediction_score, setup_score, quality_score, risk_penalty`
- machine-readable evidence：`measurement/final-acceptance/profile.json`、`measurement/projected-history-repeat/reconciliation.json`（measurement 保持 untracked）。

## Commands

RED/GREEN loop（每階段使用不同 `measurement/<stage>`）：

```bash
<main-checkout>/.venv/bin/python scripts/profile_daily_ranking_memory.py \
  --data-dir <main-checkout>/data/clean \
  --model-dir <main-checkout>/models \
  --config <main-checkout>/config/signals.yaml \
  --artifact-dir measurement/<stage> \
  --freshness-mode projected \
  --max-process-tree-rss-bytes 4026531840 \
  --receipt-path measurement/<stage>/profile.json
```

受影響回歸：

```bash
<main-checkout>/.venv/bin/python -m pytest -q \
  tests/test_ranking_memory_projection.py \
  tests/test_daily_freshness_memory.py \
  tests/test_mops_xbrl_fundamentals.py \
  tests/test_daily_automation_orchestrator.py \
  tests/test_automation_execution.py \
  tests/test_automation_pipeline_policy.py \
  tests/test_automation_status_contract.py \
  tests/test_automation_status_contract_unit.py \
  tests/test_daily_storage_validation.py \
  tests/test_isolated_daily_backfill.py \
  tests/test_historical_ranking_replay_set_lineage.py \
  tests/test_ranking_provenance_admission.py \
  tests/test_ranking_provenance_receipt.py \
  tests/test_overlay_shadow_daily_automation.py \
  tests/test_tskg_t86_automation.py
```

結果：`68 passed, 17 subtests passed, 0 failed`。另有既有 SHAP colormap deprecation warnings 3 筆。

## 最終 gates

- `git diff --check`：PASS
- source/test 中 `[DBG-`：0
- production rerun：未執行；本卡只完成隔離代表性 ranking profile 與語意對帳。
- 剩餘風險：process-tree RSS 會受同機背景負載波動，但三次 GREEN 最差值仍有 1.44 GiB 以上安全餘裕；production 補跑仍應由既有 4 GiB guard 保護。
