# AUTO-TRAINING-14B BIG_BULL Shadow Monitor

## 目標

執行 AUTO-TRAINING-14 Checkpoint B：讓 `BIG_BULL family_only` 以 ranking-only shadow 方式連續監控，不影響正式 ranking、日報或推播。

本卡是 AUTO-TRAINING-14 總卡的 Checkpoint B 執行卡，不是新的研究方向。

## 背景

AUTO-TRAINING-14 Checkpoint A 已通過：

- `shadow_status`: `READY_FOR_SHADOW_MONITOR`
- `shadow_dates`: 24
- `avg_overlap_count`: 0.375 / Top10
- `production_ranking_changed`: false
- `risk_adjusted_score_changed`: false
- `models_latest_changed`: false
- `promotion_ready`: false

重點風險：shadow Top10 與 production Top10 幾乎是兩套股票池，因此只能進 shadow monitor，不得直接進 overlay proposal。

## 必讀輸入

- `docs/tasks/2026-06-01_AUTO-TRAINING-14_big_bull_ranking_only_shadow_dry_run.md`
- `artifacts/model_experiments/big_bull_ranking_only_shadow_dry_run_2026-06-01.json`
- `scripts/build_big_bull_ranking_only_shadow_dry_run.py`
- `artifacts/model_experiments/high_choppy_context_overlay_2026-06-01.json`
- `artifacts/model_experiments/big_bull_ranking_replay_extension_2026-06-01.json`

## 任務範圍

1. 建立 shadow monitor artifact：
   - 每個監控日期產生 shadow Top10。
   - 同時讀取 production Top10 作比較。
   - Artifact 檔名必須明確含 `shadow_monitor`。
2. 每日比較：
   - overlap count。
   - shadow added / removed。
   - rank movement。
   - sector concentration。
   - turnover vs previous shadow day。
   - HIGH_CHOPPY rolling / strict / non-high-choppy 分層。
3. outcome 追蹤：
   - 能成熟的日期才計算 1/3/5/10D paper outcome。
   - 未成熟日期只列 pending，不得當失敗或成功證據。
4. guard：
   - 不寫正式 ranking artifact。
   - 不改 `risk_adjusted_score`。
   - 不覆蓋 `models/latest_lgbm.pkl`。
   - 不產生正式 Clawd message。
   - 不輸出 `PROMOTION_READY`。

## 非目標

- 不改 production ranking。
- 不做 overlay proposal。
- 不正式推播。
- 不做 model promotion。
- 不新增盤勢類別。
- 不讓 HIGH_CHOPPY 變 promotion evidence。

## 驗收標準

- 輸出 shadow monitor artifact，且包含：
  - monitor date range。
  - shadow Top10。
  - production Top10。
  - overlap / diff。
  - turnover。
  - sector concentration。
  - HIGH_CHOPPY stratified result。
  - matured / pending outcome split。
- 必須明確輸出 guard status：
  - `production_ranking_changed=false`
  - `risk_adjusted_score_changed=false`
  - `models_latest_changed=false`
  - `clawd_message_created=false`
  - `promotion_ready=false`
- 若 overlap 長期過低、turnover 過高或 HIGH_CHOPPY slice 明顯失效，本卡只能輸出 `RESTRICTED_SHADOW_ONLY` 或 `MONITOR_ONLY`。
- 只有 shadow monitor 穩定，才允許回到 AUTO-TRAINING-14 Checkpoint C：Overlay Proposal。

## 建議驗證

```bash
uv run --with-requirements requirements.txt python scripts/verify_model_experiment_ledger.py --ledger artifacts/model_experiments/model_experiment_ledger.json
uv run --with-requirements requirements.txt python scripts/verify_training_automation_readiness.py --skip-model-research-flow --timeout-seconds 900
git diff --check
```

## 預期回報格式

```text
checkpoint: B_SHADOW_MONITOR
shadow_monitor_status:
monitor_dates:
matured_outcome_dates:
pending_outcome_dates:
avg_overlap_count:
avg_turnover:
sector_concentration:
high_choppy_stratified:
production_ranking_changed:
risk_adjusted_score_changed:
models_latest_changed:
clawd_message_created:
promotion_ready:
next_gate:
errors:
```

## 執行結果

產出：

- `artifacts/model_experiments/big_bull_shadow_monitor_2026-06-01.json`
- `artifacts/model_experiments/big_bull_shadow_monitor_2026-06-01.md`
- `scripts/build_big_bull_shadow_monitor.py`

Checkpoint B 結論：

```text
checkpoint: B_SHADOW_MONITOR
shadow_monitor_status: RESTRICTED_SHADOW_ONLY
monitor_dates: 24
matured_outcome_dates:
  1D: 24
  3D: 24
  5D: 24
  10D: 24
pending_outcome_dates:
  1D: 0
  3D: 0
  5D: 0
  10D: 0
avg_overlap_count: 0.375
avg_turnover: 3.695652
sector_concentration:
  max_shadow_sector_share: 1.0
  max_production_sector_share: 1.0
high_choppy_stratified:
  rolling_context_dates: 12
  strict_dates: 2
  non_high_choppy_dates: 10
production_ranking_changed: false
risk_adjusted_score_changed: false
models_latest_changed: false
clawd_message_created: false
promotion_ready: false
next_gate: RESTRICTED_SHADOW_ONLY
errors: []
```

Paper outcome：

```text
1D:
  shadow_avg: -0.007783
  production_avg: -0.007418
  delta: -0.000365
3D:
  shadow_avg: 0.002998
  production_avg: 0.001143
  delta: 0.001855
5D:
  shadow_avg: 0.002096
  production_avg: 0.004232
  delta: -0.002136
10D:
  shadow_avg: 0.012319
  production_avg: 0.024120
  delta: -0.011801
```

HIGH_CHOPPY 10D 分層：

```text
rolling_context:
  matured_count: 12
  shadow_avg: -0.000811
  production_avg: 0.028137
  delta: -0.028948
strict:
  matured_count: 2
  shadow_avg: -0.015801
  production_avg: 0.008914
  delta: -0.024715
non_high_choppy:
  matured_count: 10
  shadow_avg: 0.033698
  production_avg: 0.022836
  delta: 0.010863
```

限制原因：

- `avg_overlap_count=0.375`，長期 overlap 低於 3/10。
- `avg_turnover=3.695652`，shadow 自身換手偏高。
- `max_shadow_sector_share=1.0`，sector concentration 過高。
- 10D shadow average return 低於 production，尤其 HIGH_CHOPPY rolling / strict slice 明顯轉弱。

Checkpoint 狀態：

```text
Checkpoint A: PASS
Checkpoint B: RESTRICTED_SHADOW_ONLY
Checkpoint C: BLOCKED
```

結論：不得進 overlay proposal；`BIG_BULL family_only` 只能保留 shadow-only monitor，不得改 production ranking / `risk_adjusted_score` / 正式推播。
