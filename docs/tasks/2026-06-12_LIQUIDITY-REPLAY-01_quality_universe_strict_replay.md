# LIQUIDITY-REPLAY-01｜Liquidity Quality Universe 嚴格 Replay 與失敗歸因

## Root Question

5913 組結果 review 顯示，最值得往下驗的是 `liquidity_quality_candidate_universe` 系列。

現在要回答：流動性品質 universe 到底真的改善每日推薦候選池，還是只是小樣本 / 同 artifact 重複 scenario 造成的假象？

## 背景

`RESEARCH-RESULT-REVIEW-01` 已完成 5913 組 review：

- `KEEP_FOR_NEXT_REPLAY`: 258
- `MONITOR_ONLY`: 947
- `LOW_INFORMATION`: 326
- `REJECTED_OR_DO_NOT_PROMOTE`: 4382
- `production_impact`: `NO_PRODUCTION_CHANGE`

top candidates 集中在：

- `artifacts/backtest/liquidity_quality_candidate_universe_shadow_rankings_smoke_2026-06-03/log_gate`
- `artifacts/backtest/liquidity_quality_candidate_universe_shadow_rankings_stop_smoke_2026-06-03/log_gate`
- `artifacts/backtest/liquidity_quality_candidate_universe_shadow_rankings_halfyear_2026-06-03/log_gate`
- `artifacts/backtest/liquidity_quality_candidate_universe_shadow_rankings_halfyear_with_trade_plan_2026-06-03/production`

這代表「流動性品質股票池」可能有用，但目前證據仍偏 research ranking，不可直接上 production。

## 請讀

- `docs/tasks/2026-06-12_RESEARCH-RESULT-REVIEW-01_5913_combo_effectiveness_review.md`
- `artifacts/research_reviews/5913_combo_effectiveness_review_2026-06-12.json`
- `artifacts/research_reviews/5913_combo_effectiveness_review_2026-06-12.md`
- `scripts/build_5913_combo_effectiveness_review.py`
- `scripts/verify_5913_combo_effectiveness_review.py`
- `artifacts/autonomous_research/run_history.jsonl`
- 相關 liquidity ranking artifacts：
  - `artifacts/backtest/liquidity_quality_candidate_universe_shadow_rankings_smoke_2026-06-03/`
  - `artifacts/backtest/liquidity_quality_candidate_universe_shadow_rankings_stop_smoke_2026-06-03/`
  - `artifacts/backtest/liquidity_quality_candidate_universe_shadow_rankings_halfyear_2026-06-03/`
  - `artifacts/backtest/liquidity_quality_candidate_universe_shadow_rankings_halfyear_with_trade_plan_2026-06-03/`

## 任務目的

做一個嚴格 replay，判斷 liquidity quality universe 是否真的值得成為 strategy component candidate。

重點不是只問「有沒有贏」，也要回答「如果失敗，是敗在哪裡」。

## 嚴格比較要求

請至少比較：

- production baseline ranking
- liquidity quality universe shadow ranking
- liquidity quality + same production exit
- production ranking + same liquidity exit / filter 對照

比較時必須控制：

- same date window
- same entry timing
- same exit rule
- same capital rule
- same fees / tax / slippage
- same max gross exposure
- same max position exposure
- same sector / group exposure cap
- same regime slice
- same comparable dates

## 必做 Failure Attribution

不管結果贏或輸，都要拆原因。

若失敗，請至少歸因到以下類型：

- `SAMPLE_TOO_SMALL`: 樣本不足，不能判定。
- `RETURN_WEAK`: 報酬沒有贏 baseline。
- `DRAWDOWN_WORSE`: 報酬好看但回撤更差。
- `TURNOVER_TOO_HIGH`: 換手太高，交易成本吃掉優勢。
- `CONCENTRATION_RISK`: 產業 / 個股集中度過高。
- `REGIME_ONLY_SIGNAL`: 只在特定盤勢有效，跨盤勢無效。
- `EXIT_RULE_DEPENDENT`: 不是 liquidity universe 有效，而是 exit rule 有效。
- `ENTRY_FILTER_DEPENDENT`: 不是 liquidity universe 有效，而是 entry filter 有效。
- `ARTIFACT_DUPLICATION`: 來自同一 artifact 多個 scenario 重複，不是獨立訊號。
- `NO_ALPHA`: 控制條件後沒有可交易優勢。

若成功，也要說清楚成功來源：

- 是股票池變好？
- 是排除低流動性後風險下降？
- 是減少 drawdown？
- 是提高勝率？
- 是換手下降？
- 是只改善短週期？
- 是只在 BIG_BULL / HIGH_CHOPPY / NEUTRAL 有效？

## 輸出

請新增：

- `scripts/build_liquidity_quality_strict_replay.py`
- `scripts/verify_liquidity_quality_strict_replay.py`
- `artifacts/research_reviews/liquidity_quality_strict_replay_YYYY-MM-DD.json`
- `artifacts/research_reviews/liquidity_quality_strict_replay_YYYY-MM-DD.md`
- `artifacts/research_reviews/liquidity_quality_strict_replay_verification_latest.json`

JSON 必須包含：

- `status`
- `review_date`
- `production_impact`
- `candidate_family`
- `input_review_artifact`
- `comparable_window`
- `baseline`
- `candidate`
- `same_exit_comparison`
- `same_capital_comparison`
- `regime_slices`
- `failure_attribution`
- `decision`
- `next_action`
- `errors`

Markdown 必須包含：

- executive summary
- what was tested
- headline result
- failure attribution / success attribution
- regime breakdown
- risk breakdown
- next action
- production impact

## Decision Labels

請只允許以下 decision：

- `PROMOTE_TO_STRATEGY_COMPONENT_REPLAY`: 值得進下一層 strategy component registry 前置 replay。
- `KEEP_SHADOW_MONITOR`: 有訊號但還不穩，只能繼續觀察。
- `REJECT_FOR_NOW`: 嚴格控制後沒優勢，暫時淘汰。
- `INCONCLUSIVE_MORE_DATA_REQUIRED`: 樣本不足或資料不完整，不能判定。

## 禁止事項

- 不准改 `models/latest_lgbm.pkl`
- 不准改 production ranking
- 不准改 `risk_adjusted_score`
- 不准改 Clawd live push
- 不准把 5913 review 的 `KEEP_FOR_NEXT_REPLAY` 直接當成 production evidence
- 不准只用報酬率判定成功
- 不准忽略失敗原因

## 驗證

Verifier 至少檢查：

- JSON / Markdown 都存在
- `production_impact == "NO_PRODUCTION_CHANGE"`
- `decision` 屬於允許清單
- `failure_attribution` 至少包含一個主要原因或明確 success attribution
- comparable date count > 0
- baseline / candidate 都有 return、drawdown、turnover、concentration 指標
- report 不含 `PROMOTION_READY`
- 沒有寫入 production ranking / model / Clawd live artifact

## 驗收回報

完成時請回報：

- replay status
- comparable window
- baseline vs liquidity candidate 報酬
- baseline vs liquidity candidate max drawdown
- turnover delta
- concentration delta
- regime slices 結論
- decision
- failure attribution 或 success attribution
- next action
- production impact
- errors

## 預期邊界

這張卡最多只能把 liquidity quality universe 推進到下一層 strategy component replay，或把它淘汰 / 留監控。

它不能直接改正式模型、正式排名或正式推播。

