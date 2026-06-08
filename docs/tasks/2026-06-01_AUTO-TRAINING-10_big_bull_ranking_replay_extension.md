# AUTO-TRAINING-10 BIG_BULL Ranking Replay Extension

## 目標

把 AUTO-TRAINING-08 收斂出的兩條候選延伸測完整：

- `BIG_BULL family_only`
- `BIG_BULL blended_rerank`

本卡只做 research / replay / portfolio robustness，不做 production promotion。

## 必讀輸入

- `artifacts/model_experiments/high_choppy_context_overlay_2026-06-01.json`
- `artifacts/model_experiments/high_choppy_context_overlay_verification_latest.json`

`HIGH_CHOPPY rolling context` 必須進入本卡的 soft feature comparison 與 stratified evaluation。不得因為它不能 promotion 就略過。

## 背景

AUTO-TRAINING-08 的 portfolio comparison 結論：

- `family_only` 表現最好。
- `blended_rerank` 表現接近，且保守保留。
- `blended_score` 已淘汰。
- `HIGH_CHOPPY` 不阻塞主訓練；它只在 AUTO-TRAINING-09 中作為 soft feature / stratified evaluation。

因此下一步不需要再擴散測一堆方向，只需要把 `family_only` 與 `blended_rerank` 拉長驗證。

## 任務範圍

1. 延伸 ranking replay：
   - D 日 ranking。
   - D+1 開盤進場。
   - 1/3/5/10 日出場。
   - 比較 current production ranking baseline。
2. 延伸 portfolio replay：
   - Top5 / Top10 / Top15。
   - 等權 portfolio。
   - 最大回撤。
   - turnover。
   - 族群集中度。
3. 做 robustness check：
   - 不同 replay window。
   - 不同進場日假設。
   - 不同 TopN。
   - `BIG_BULL` 內部高檔震盪 context 的分層表現。
4. 納入 `HIGH_CHOPPY rolling context`：
   - soft feature comparison：比較有/無 `HIGH_CHOPPY` context feature 的候選表現。
   - stratified evaluation：切出 `HIGH_CHOPPY` context 日期，檢查 TopN、回撤、hit rate、族群集中度。
   - 若 soft feature 沒幫助，只能標 `MONITOR_ONLY`，不得刪除分層報表。
   - 若分層顯示明確弱點，產出下一張 overlay follow-up，不在本卡直接改 production ranking。
5. 輸出下一階段判斷：
   - 保留 `RANKING_FOLLOWUP_CANDIDATE`。
   - 降級 `MONITOR_ONLY`。
   - 或進入 sealed OOS / rollback gate 準備。

## 非目標

- 不覆蓋 `models/latest_lgbm.pkl`。
- 不直接 production promotion。
- 不恢復 `blended_score`。
- 不讓 `HIGH_CHOPPY` 樣本不足阻塞本卡。
- 不新增正式 base regime 或 family tag。
- 不取代 sealed OOS / replay / rollback / model group acceptance。

## 驗收標準

- 產出 `family_only` 與 `blended_rerank` 的 replay / portfolio comparison artifact。
- 明確列出：
  - total return。
  - average net return。
  - max drawdown。
  - hit rate。
  - turnover。
  - sector concentration。
  - TopN sensitivity。
  - entry-day sensitivity。
- 明確比較 current production ranking baseline。
- 必須輸出 `HIGH_CHOPPY rolling context` 的：
  - soft feature comparison。
  - stratified evaluation。
  - 是否影響 `family_only` / `blended_rerank` 下一階段資格。
  - 若未納入，結論必須標 `FAILED`，不可只標 warning。
- `models/latest_lgbm.pkl` hash 未變。
- 結論不得輸出 `PROMOTION_READY`。

## 2026-06-01 執行結果

```text
family_only_status: RANKING_FOLLOWUP_CANDIDATE
blended_rerank_status: RANKING_FOLLOWUP_CANDIDATE
baseline_status: current production ranking baseline replayed
best_candidate: BIG_BULL family_only
ranking_replay: OK
portfolio_replay: OK
topn_sensitivity: OK
entry_day_sensitivity: OK
big_bull_high_choppy_stratified: OK
high_choppy_soft_feature_comparison: OK / MONITOR_ONLY
high_choppy_stratified_evaluation: OK
high_choppy_included_in_main_training: true
models_latest_changed: false
promotion_ready: false
next_gate: sealed OOS / rollback gate preparation only if PM wants to continue; no production promotion from this card
errors: none
```

核心結論：

- `family_only` 是本卡最佳候選，Top10 / D+1 portfolio total return `11.06%`，max drawdown `-6.27%`，hit rate `60.87%`。
- `blended_rerank` 幾乎貼近 `family_only`，Top10 / D+1 portfolio total return `11.04%`，max drawdown `-6.27%`，hit rate `61.21%`。
- current production baseline 同窗為 total return `-2.95%`，max drawdown `-9.40%`，hit rate `41.41%`。
- TopN sensitivity：`family_only` 與 `blended_rerank` 在 Top5 / Top10 / Top15 都勝過 baseline；Top10 與 Top15 因可交易樣本限制結果相同。
- Entry-day sensitivity：優勢集中在 D+1；D+2 / D+3 兩條 BIG_BULL 候選都退回小幅負報酬，表示 entry timing 很敏感。
- Replay window sensitivity：完整視窗 winner 是 `family_only`；最近 12 份 ranking 需看主 artifact，不得只用單一漂亮視窗做 promotion。
- `HIGH_CHOPPY rolling context` 已納入主訓練評估：
  - 必讀 artifact：`high_choppy_context_overlay_2026-06-01.json` 與 `high_choppy_context_overlay_verification_latest.json` 均為 OK。
  - soft feature comparison：加入 `high_choppy_rolling_context` 後，AUC delta `-0.000475`，TopN return delta `-0.002503`，TopN uplift delta `-0.002503`。
  - 本輪 soft feature 不改善候選表現，因此 `HIGH_CHOPPY rolling context` 在本卡標為 `MONITOR_ONLY`，但不得刪除分層報表。
- `BIG_BULL` 內部 HIGH_CHOPPY 分層：
  - strict slice 覆蓋少，僅 2026-04-15，兩條候選 avg return `8.93%`，只能作診斷。
  - rolling context slice 覆蓋 8 個 ranking dates，`family_only` avg return `3.61%`，`blended_rerank` avg return `3.70%`。
- 本卡只支持 ranking/replay follow-up，不支持 production promotion。

主要證據：

- `artifacts/model_experiments/big_bull_ranking_replay_extension_2026-06-01.json`
- `artifacts/model_experiments/big_bull_ranking_replay_extension_2026-06-01.md`
- `artifacts/backtest/replay_auto10_family_only_top10_d1_2026-06-01.json`
- `artifacts/backtest/replay_auto10_blended_rerank_top10_d1_2026-06-01.json`
- `artifacts/backtest/replay_auto10_baseline_top10_d1_2026-06-01.json`
- `artifacts/backtest/portfolio_auto10_family_only_top10_d1_2026-06-01.json`
- `artifacts/backtest/portfolio_auto10_blended_rerank_top10_d1_2026-06-01.json`
- `artifacts/backtest/portfolio_auto10_baseline_top10_d1_2026-06-01.json`

## 建議驗證

```bash
uv run --with-requirements requirements.txt python scripts/verify_training_automation_readiness.py --skip-model-research-flow --timeout-seconds 900
uv run --with-requirements requirements.txt python scripts/verify_model_experiment_ledger.py --ledger artifacts/model_experiments/model_experiment_ledger.json
git diff --check
```

## 預期回報格式

```text
family_only_status:
blended_rerank_status:
baseline_status:
best_candidate:
ranking_replay:
portfolio_replay:
topn_sensitivity:
entry_day_sensitivity:
big_bull_high_choppy_stratified:
high_choppy_soft_feature_comparison:
high_choppy_stratified_evaluation:
high_choppy_included_in_main_training:
models_latest_changed:
promotion_ready:
next_gate:
errors:
```
