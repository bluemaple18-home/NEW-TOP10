# WEEKEND-TRAINING-OVERNIGHT-01 full-night unlock and replay campaign

## 任務目的

安排一個可以跑整晚的研究流程，但不盲目暴力跑。

核心目標：

1. 先把目前已知 blocker 誠實寫進 rollup / map。
2. 再依序檢查三大 unsupported 類別是否能解鎖。
3. 只有通過 source / contract / sample gate 的類別，才進小批 replay。
4. 每一批都要更新研究地圖與產出 failure attribution。

這張卡是 overnight orchestration，不是 production rollout。

## 起始狀態

目前基準：

```text
full universe: 662,256
expanded processed: 21,147
classified total: 662,256 / 662,256
representative queue: 0
survivor deep replay: 196 / 196
survivor result: 196 MONITOR_ONLY
unsupported total: 574,695
```

Unsupported 分布：

```text
UNSUPPORTED_RANKING_DIR_MISSING: 202,176
UNSUPPORTED_ENTRY_FILTER_NOT_AVAILABLE: 88,695
UNSUPPORTED_REGIME_SLICE_NO_DATA: 283,824
```

WEEKEND-TRAINING-11 已判定：

```text
artifacts/backtest/production cannot be materialized
baseline_source_status: BLOCKED_PROVENANCE_GAP
unlockable_combo_count_estimate: 0
```

## 整晚流程

### Phase 0：安全前置檢查

目的：避免整晚任務干擾每日推薦。

必跑：

```bash
git status --short
.venv/bin/python scripts/verify_weekend_training_rollup.py --date 2026-06-13
.venv/bin/python scripts/verify_research_fog_map.py --date 2026-06-17
```

要求：

- 不得啟動 ETL。
- 不得啟動 daily publish。
- 不得修改 production ranking / model / Clawd。
- 若有 live daily job 正在跑，整晚研究任務必須停等或跳過。

### Phase 1：收 WEEKEND-TRAINING-12

目的：把 `202,176` 個 production baseline provenance gap 顯示成 artifact blocker。

要完成：

- `artifact_blocker_count == 202176`
- `artifact_blocker_category_counts.ARTIFACT_BLOCKER_PROVENANCE_GAP == 202176`
- research map 顯示 artifact blocker，而不是把它當成待跑進度。

不得：

- materialize `artifacts/backtest/production`
- symlink / copy 任一候選目錄
- 增加 `expanded_processed`

### Phase 2：production baseline provenance design

任務建議 ID：

```text
WEEKEND-TRAINING-13_production_baseline_provenance_design
```

目的：設計 canonical production baseline 應該怎麼長出來。

要回答：

```text
baseline source of truth 是 daily ranking 還是 backtest production replay？
需要哪些欄位？
需要覆蓋哪些日期？
如何證明它不是 candidate ranking？
如何避免未來 provenance gap 再發生？
```

產物：

- `artifacts/weekend_training/weekend_production_baseline_provenance_design_YYYY-MM-DD.json`
- `artifacts/weekend_training/weekend_production_baseline_provenance_design_YYYY-MM-DD.md`

Gate：

- 只能產 design / contract。
- 不准直接產 `artifacts/backtest/production`。

### Phase 3：TOPIC_DEFAULT entry filter contract audit

任務建議 ID：

```text
WEEKEND-TRAINING-14_topic_default_entry_filter_contract_audit
```

目的：處理 `88,695` 個 `UNSUPPORTED_ENTRY_FILTER_NOT_AVAILABLE`。

要回答：

```text
TOPIC_DEFAULT 是有效 filter 嗎？
它等於 NONE、topic 原生 filter，還是 deprecated coordinate？
如果 deprecated，是否應從 full universe 移除或標成 contract blocker？
如果有效，runner adapter 最小契約是什麼？
```

Gate：

- 沒有明確定義前，不准映射到 `LOG_GATE` / `PERCENTILE_GATE`。
- 若要解鎖，只能先做 1 topic / 1 horizon / 1 entry smoke。

### Phase 4：regime slice data adequacy audit

任務建議 ID：

```text
WEEKEND-TRAINING-15_regime_slice_data_adequacy_audit
```

目的：處理 `283,824` 個 `UNSUPPORTED_REGIME_SLICE_NO_DATA`。

要分別檢查：

```text
NEUTRAL_ONLY
PANIC_SELLING_ONLY
RISK_OFF_ONLY
```

每個 regime 必須回答：

```text
可用交易日數
可比較 ranking 日期數
進出場 outcome 樣本數
是否足以做 replay
是否只能做 monitoring
是否應維持 unsupported
```

Gate：

- 不足樣本不可跑策略結論。
- 可以做 data adequacy / monitoring audit。
- 不可把低樣本 regime 結論包裝成有效策略。

### Phase 5：小批 unlock smoke replay

只有 Phase 2 / 3 / 4 任一項明確通過 gate，才進本階段。

允許範圍：

```text
每類最多 100 ~ 500 格
每批必須固定 seed / deterministic queue
每批必須更新 run_history.jsonl
每批必須更新 rollup / research map
```

每批輸出：

```text
completed_count
next_stage_count
monitor_only_count
low_information_count
rejected_count
failure_attribution
production_impact
```

Stop condition：

- verifier fail
- production impact 不是 `NO_PRODUCTION_CHANGE`
- expanded_processed 被 artifact blocker 錯誤推高
- 出現 `PROMOTION_READY`
- daily automation / publish job 需要資源

### Phase 6：整晚總結

早上產出：

- `artifacts/weekend_training/overnight_campaign_summary_YYYY-MM-DD.json`
- `artifacts/weekend_training/overnight_campaign_summary_YYYY-MM-DD.md`

總結必須包含：

```text
跑了哪些 phase
哪些 blocker 被確認
哪些 blocker 被解鎖
實際 replay 幾格
哪些候選進 next_stage
哪些失敗但有 insight
哪些只是 low_information
research map 進度變化
下一個最有槓桿的動作
```

## 明確禁止

- 不准跑 representative drain。
- 不准直接跑 202,176 / 88,695 / 283,824 全量。
- 不准 materialize production baseline，除非另有已通過 verifier 的 materialize smoke 卡。
- 不准改 production ranking。
- 不准改 `models/latest_lgbm.pkl`。
- 不准 live send Clawd。
- 不准讓研究任務影響每日推薦排程。

## 整晚成功定義

成功不是「格子跑越多越好」。

成功是：

```text
1. 地圖狀態更誠實
2. blocker 被分類到可決策
3. 至少一個最大灰霧類別有明確下一步
4. 若有解鎖，只跑通過 gate 的小批 smoke
5. 所有結果都能回寫 map / rollup
6. 沒有任何 production side effect
```

## 驗證清單

收工前必跑：

```bash
.venv/bin/python -m py_compile scripts/*.py
.venv/bin/python scripts/verify_weekend_training_rollup.py --date 2026-06-13
.venv/bin/python scripts/verify_research_map_v2_schema.py
.venv/bin/python scripts/verify_research_fog_map.py --date 2026-06-17
git diff --check
```

若有新增 phase-specific verifier，也必須一併跑。
