# AUTO-TRAINING-08 Global / BIG_BULL / Blended Training

## 目標

繼續主線自動訓練研究，不讓 `HIGH_CHOPPY` 樣本不足卡住 global、`BIG_BULL`、blended、ranking-oriented experiments。

## 負責

```text
global
BIG_BULL
blended
ranking-oriented replay
portfolio replay
```

`HIGH_CHOPPY` 樣本不足不能卡住這張主訓練卡；相關診斷與 context / overlay 研究由 AUTO-TRAINING-09 承接。

## 背景

盤勢分類的原意是幫助訓練降低雜訊，不是把整個訓練流程綁死。`BIG_BULL` 已有足夠樣本可進一步做 ranking/replay-oriented 研究；global 與 blended experiment 也應持續推進。

`HIGH_CHOPPY` 另由 AUTO-TRAINING-09 處理，不在本卡阻斷主訓練。

## 任務範圍

1. 跑 global baseline 訓練候選，建立後續比較基準。
2. 跑 `BIG_BULL` family candidate：
   - family-only training。
   - family-weighted training。
   - global model filtered to `BIG_BULL` dates。
3. 跑 blended candidate：
   - global + `BIG_BULL` score blend。
   - global + `BIG_BULL` ranking rerank。
   - 不改 production `risk_adjusted_score`。
4. 跑 ranking-oriented replay：
   - D 日 ranking。
   - D+1 開盤進場。
   - 1/3/5/10 日出場。
5. 跑 portfolio replay：
   - Top10 等權。
   - drawdown。
   - turnover。
   - 族群集中度。

## 非目標

- 不覆蓋 `models/latest_lgbm.pkl`。
- 不直接 promotion。
- 不用 `HIGH_CHOPPY` 樣本不足阻擋本卡。
- 不新增正式 base regime 或 family tag。
- 不取代 sealed OOS / replay / rollback / model group acceptance。

## 驗收標準

- 產出 global / `BIG_BULL` / blended 的 research artifact。
- 明確標示每個 candidate 是：
  - `RESEARCH_ONLY`
  - `RANKING_FOLLOWUP_CANDIDATE`
  - `MODEL_PROMOTION_BLOCKED`
  - 或其他既有合法狀態。
- `training_launch_ready` 不因 `HIGH_CHOPPY` 樣本不足變 false。
- 若 candidate 要進下一階段，必須能追溯 ledger id。
- `models/latest_lgbm.pkl` 未變更。

## 2026-06-01 執行結果

```text
training_launch_ready: true
global_candidate_status: OK / baseline included
big_bull_candidate_status: PROMOTE_CANDIDATE in training matrix; MODEL_PROMOTION_BLOCKED for model promotion; RANKING_FOLLOWUP_CANDIDATE
blended_candidate_status: OK, score_blend + ranking_rerank both produced
ranking_replay_status: OK
portfolio_replay_status: OK
high_choppy_blocked_main_training: false
models_latest_changed: false
promotion_ready: false
errors: none
```

關鍵判定：

- `HIGH_CHOPPY` 只有 14 個 family dates，維持 `MONITOR_ONLY`，不阻塞本卡。
- `BIG_BULL` 有 168 個 family dates，training matrix 顯示 `PROMOTE_CANDIDATE`，但 sealed stability 顯示 `MODEL_PROMOTION_BLOCKED`。
- `BIG_BULL` sealed stability 的 ranking 結論是 `RANKING_FOLLOWUP_CANDIDATE`，不得升成 production model promotion evidence。
- portfolio replay 三路比較：
  - family-only：total return `11.06%`，max drawdown `-6.27%`。
  - blended score：total return `7.41%`，max drawdown `-7.85%`，劣於 baseline。
  - blended rerank：total return `11.04%`，max drawdown `-6.27%`，接近 family-only，win rate 略高。
- 下一步只應延伸 family-only / blended rerank 的 ranking/replay follow-up；不要推 blended score，也不要做 production promotion。

主要證據：

- `artifacts/model_experiments/regime_family_training_candidates_2026-06-01.json`
- `artifacts/model_experiments/regime_family_sealed_stability_2026-06-01.json`
- `artifacts/model_experiments/big_bull_blended_shadow_ranking_2026-06-01.json`
- `artifacts/backtest/replay_big_bull_ranking_2026-06-01.json`
- `artifacts/backtest/portfolio_replay_big_bull_ranking_2026-06-01.json`
- `artifacts/backtest/portfolio_replay_big_bull_variant_comparison_2026-06-01.json`
- `artifacts/training_automation_readiness_2026-06-01.json`

## 建議驗證

```bash
uv run --with-requirements requirements.txt python scripts/verify_training_automation_readiness.py --skip-model-research-flow --timeout-seconds 900
uv run --with-requirements requirements.txt python scripts/verify_model_experiment_ledger.py --ledger artifacts/model_experiments/model_experiment_ledger.json
git diff --check
```

## 預期回報格式

```text
training_launch_ready:
global_candidate_status:
big_bull_candidate_status:
blended_candidate_status:
ranking_replay_status:
portfolio_replay_status:
high_choppy_blocked_main_training:
models_latest_changed:
promotion_ready:
errors:
```
