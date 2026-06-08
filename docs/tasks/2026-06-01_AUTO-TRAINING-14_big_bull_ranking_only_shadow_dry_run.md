# AUTO-TRAINING-14 BIG_BULL Ranking-Only Shadow Path

## 目標

把 `BIG_BULL family_only` 以 ranking-only 方式接近正式流程做 shadow path，觀察它每天若真的拿來排 Top10，會選誰、與正式榜差多少、風險差多少。

本卡不做模型升版、不改正式 ranking、不覆蓋模型。

本卡是 AUTO-TRAINING-14 ~ 16 的合併總卡。除非要動正式 production ranking、`risk_adjusted_score`、正式推播或模型檔，否則後續以本卡 checkpoint 推進，不再每一步新開卡。

## 背景

AUTO-TRAINING-13 已收斂：

- sealed split policy：`SPLIT_POLICY_CONFLICT`
- `BIG_BULL family_only`：`RANKING_ONLY_CANDIDATE`
- model promotion allowed：false
- promotion_ready：false
- `models/latest_lgbm.pkl` hash unchanged

因此 `BIG_BULL family_only` 不再走 model promotion。下一步只能走 production-adjacent shadow ranking path。

## 必讀輸入

- `artifacts/model_experiments/big_bull_sealed_split_policy_ranking_only_decision_2026-06-01.json`
- `artifacts/model_experiments/big_bull_ranking_replay_extension_2026-06-01.json`
- `artifacts/model_experiments/high_choppy_context_overlay_2026-06-01.json`
- `artifacts/model_experiments/model_promotion_review_big_bull_auto13_2026-06-01.json`
- `scripts/research_big_bull_blended_shadow_ranking.py`
- `scripts/build_big_bull_ranking_replay_extension_report.py`
- `scripts/run_backtest_replay.py`
- `scripts/run_portfolio_replay.py`

## Checkpoint A：Shadow Dry Run

1. 建立 ranking-only shadow output：
   - 每個交易日產生 `BIG_BULL family_only` shadow Top10。
   - 同時保留 current production ranking Top10。
   - 不寫入正式 daily ranking 檔。
2. 差異比較：
   - overlap count。
   - 新增 / 移除股票。
   - 排名變化。
   - sector concentration。
   - turnover。
   - HIGH_CHOPPY rolling context 分層。
3. dry-run report：
   - 模擬每日報表會看到的 Top10。
   - 標明這是 shadow，不可推播為正式推薦。
   - 不產生正式 Clawd message。
4. production-adjacent guard：
   - 不改 `risk_adjusted_score`。
   - 不覆蓋 `models/latest_lgbm.pkl`。
   - 不改 production ranking path。
   - 不輸出 `PROMOTION_READY`。

## Checkpoint B：Shadow Monitor

若 Checkpoint A 通過，進入 shadow monitor：

1. 連續多個交易日產生 shadow artifact。
2. 每日比較 shadow Top10 與 production Top10：
   - overlap。
   - 新增 / 移除。
   - sector concentration。
   - turnover。
   - HIGH_CHOPPY rolling context 分層。
3. 不影響正式 daily report / Clawd message。
4. 觀察條件：
   - shadow 是否穩定改善 replay / paper outcome。
   - 是否只在 `BIG_BULL` 日期有效。
   - 是否遇到 HIGH_CHOPPY context 時失效。
   - turnover 是否過高。

## Checkpoint C：Overlay Proposal

若 Checkpoint B 穩定，才產出 ranking overlay proposal：

1. 明確說明 overlay 生效條件：
   - 僅限 `BIG_BULL`。
   - 是否排除 `HIGH_CHOPPY`。
   - TopN / sector cap / turnover cap。
2. 明確說明 fallback：
   - 非 `BIG_BULL` 回 production ranking。
   - guard 失敗回 production ranking。
3. 輸出 review-ready proposal，不自動啟用 production。

## 後續判斷

- `READY_FOR_SHADOW_MONITOR`
- `READY_FOR_OVERLAY_PROPOSAL`
- `RESTRICTED_SHADOW_ONLY`
- `MONITOR_ONLY`
- `FAILED`

## 非目標

- 不做 model promotion。
- 不覆蓋 `models/latest_lgbm.pkl`。
- 不改正式 ranking artifact。
- 不改 production `risk_adjusted_score`。
- 不正式推播每日訊息或正式 Clawd message。
- 不啟用 auto / scheduled retrain promotion。
- 不把 `HIGH_CHOPPY` 當 promotion evidence。

## 驗收標準

- 產出 shadow ranking / dry-run artifact，且檔名明確含 `shadow` 或 `dry_run`。
- Artifact 必須包含：
  - shadow Top10。
  - production Top10。
  - overlap / diff。
  - sector concentration。
  - turnover。
  - HIGH_CHOPPY stratified result。
  - guard status。
- Guard status 必須確認：
  - `production_ranking_changed=false`
  - `risk_adjusted_score_changed=false`
  - `models_latest_changed=false`
  - `promotion_ready=false`
- 若任一 guard 無法驗證，本卡必須 `FAILED`，不可只 warning。
- Checkpoint A 未通過，不得進 Checkpoint B。
- Checkpoint B 未通過，不得產出 overlay proposal。
- Checkpoint C 只能產出 proposal，不得直接改 production。

## 建議驗證

```bash
uv run --with-requirements requirements.txt python scripts/verify_model_experiment_ledger.py --ledger artifacts/model_experiments/model_experiment_ledger.json
uv run --with-requirements requirements.txt python scripts/verify_training_automation_readiness.py --skip-model-research-flow --timeout-seconds 900
git diff --check
```

## 預期回報格式

```text
shadow_status:
shadow_dates:
production_comparison:
overlap_summary:
sector_concentration:
turnover:
high_choppy_stratified:
production_ranking_changed:
risk_adjusted_score_changed:
models_latest_changed:
promotion_ready:
next_gate:
checkpoint:
errors:
```

## 執行結果

產出：

- `artifacts/model_experiments/big_bull_ranking_only_shadow_dry_run_2026-06-01.json`
- `artifacts/model_experiments/big_bull_ranking_only_shadow_dry_run_2026-06-01.md`
- `scripts/build_big_bull_ranking_only_shadow_dry_run.py`

Checkpoint A 結論：

```text
shadow_status: READY_FOR_SHADOW_MONITOR
shadow_dates: 24
production_comparison:
  date_range: 2026-04-08 ~ 2026-05-13
  avg_overlap_count: 0.375
  min_overlap_count: 0
overlap_summary:
  avg_shadow_added_vs_production: 9.625
sector_concentration:
  max_shadow_sector_share: 1.0
  max_production_sector_share: 1.0
turnover:
  avg_shadow_added_vs_production: 9.625
  avg_shadow_turnover_vs_previous: 3.695652
high_choppy_stratified:
  rolling_context_dates: 12
  strict_dates: 2
  non_high_choppy_dates: 10
production_ranking_changed: false
risk_adjusted_score_changed: false
models_latest_changed: false
promotion_ready: false
next_gate: READY_FOR_SHADOW_MONITOR
checkpoint: A_SHADOW_DRY_RUN
errors: []
```

重點解讀：

- Checkpoint A 已通過，只代表可以進 Checkpoint B shadow monitor，不代表可以產 overlay proposal。
- Shadow Top10 與 production Top10 差異很大：平均 overlap 只有 `0.375 / 10`，平均每日相對 production 新增 `9.625` 檔。
- Shadow 自身 turnover 平均 `3.695652` 檔 / 日，需在 Checkpoint B 持續監控。
- HIGH_CHOPPY 分層已納入：rolling context 12 日、strict 2 日、non-high-choppy 10 日。
- Guard 全部通過：未改 production ranking、未改 `risk_adjusted_score`、未改模型、`promotion_ready=false`。

Checkpoint 狀態：

```text
Checkpoint A: PASS
Checkpoint B: NOT_STARTED / entry_allowed=true
Checkpoint C: NOT_STARTED / entry_allowed=false
```

驗證：

```text
py_compile: OK
verify_model_experiment_ledger: OK
verify_training_automation_readiness: FAILED（預期；promotion_ready=false）
git diff --check: OK
models/latest_lgbm.pkl hash unchanged
```

模型 hash：

```text
76f530f6491f996f4838500acacbde40a10c90f43116cec0dcc69fb6b4935675
```
