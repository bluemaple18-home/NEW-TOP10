# RESEARCH-RESULT-REVIEW-01｜5913 組合有效性審核

## Root Question

5913 組 autonomous research 組合已全部跑完。現在要判斷：這些結果到底有沒有研究價值、哪些值得保留成策略零件、哪些只是噪音、哪些要進下一輪更嚴格 replay / promotion-review 前置驗證。

## 背景

研究地圖已從「漂亮進度圖」接成 deterministic combo registry：

- 73 個 topic hub
- 每個 topic 81 個 scenario
- 總數 5913 個 combo scenario
- run history 已回填成地圖可讀格式
- fog map 已能用 run history 自動點燈

目前不是要重跑 5913 組，而是要認真 review 跑完的結果。

## 請讀

- `scripts/research_map_contract.py`
- `scripts/build_research_campaign_progress.py`
- `scripts/build_research_fog_map.py`
- `scripts/backfill_research_map_run_history.py`
- `scripts/verify_research_fog_map.py`
- `scripts/verify_research_map_run_history_backfill.py`
- `artifacts/autonomous_research/run_history.jsonl`
- `artifacts/autonomous_research/research_campaign_progress_2026-06-11.json`
- `artifacts/autonomous_research/research_campaign_progress_2026-06-11.md`
- `artifacts/research_map/research_fog_map_latest.json`
- `artifacts/research_map/research_fog_map_verification_latest.json`

## 已知現況

以 `artifacts/research_map/research_fog_map_latest.json` 為準：

- `total_combos`: 5913
- `processed_combos`: 5913
- `effective_insight_combos`: 642
- `follow_up_signal_combos`: 563
- `rejected_combos`: 4382
- `low_information_combos`: 326

目前只能說「地圖與批次跑完」，不能直接說「有效策略已找到」。

## 任務目的

請做一份 5913 組結果的 review report，回答以下問題：

1. 這 642 個 `effective` 裡，是否真的有穩定、可解釋、可複用的策略零件？
2. 哪些 topic / scenario family 只是單一條件碰巧好看，不值得保留？
3. 哪些結果值得進下一輪更嚴格的 replay，例如同 exit、同資金、同成本、同 exposure、同 regime normalization？
4. 哪些結果可以變成 strategy component registry 的候選零件？
5. 哪些結果需要明確標成 `DO_NOT_PROMOTE`，避免之後被誤用？
6. 這 5913 組對目前主線 production ranking / trail10 / warning / liquidity / regime 研究，有沒有產生可行下一步？

## Review 維度

請至少按以下維度彙整：

- topic hub
- ranking source
- entry filter
- exit rule
- capital rule
- regime gate
- sector / concentration rule
- liquidity rule
- tape / RR / chase guard
- outcome horizon
- return delta
- drawdown delta
- turnover / concentration risk
- sample size / comparable dates
- insight level

## 判斷規則

請把每個重要 candidate 分成四類之一：

- `KEEP_FOR_NEXT_REPLAY`: 有明確正向訊號，值得進嚴格 replay。
- `MONITOR_ONLY`: 有訊號但不穩或樣本不足，只能觀察。
- `LOW_INFORMATION`: 資訊量不足，暫不採用。
- `REJECTED_OR_DO_NOT_PROMOTE`: 負向、不可解釋、或風險不划算。

## 禁止事項

- 不准改 `models/latest_lgbm.pkl`
- 不准改 production ranking
- 不准改 `risk_adjusted_score`
- 不准改 Clawd live push
- 不准把 `effective_insight` 直接等同 promotion-ready
- 不准只看報酬，不看回撤、樣本數、換手與集中度
- 不准用後照鏡調參後宣稱原本策略有效

## 輸出

請新增 review artifact：

- `artifacts/research_reviews/5913_combo_effectiveness_review_YYYY-MM-DD.json`
- `artifacts/research_reviews/5913_combo_effectiveness_review_YYYY-MM-DD.md`

Markdown 必須包含：

- executive summary
- top useful findings
- rejected / misleading findings
- next replay queue
- strategy component candidates
- production impact: 預設 `NO_PRODUCTION_CHANGE`
- open risks

JSON 必須包含：

- `status`
- `review_date`
- `input_total_combos`
- `input_processed_combos`
- `classification_counts`
- `top_candidates`
- `next_replay_queue`
- `do_not_promote`
- `production_impact`
- `errors`

## 驗證

請新增或更新 verifier，至少檢查：

- review JSON 存在且 schema key 齊全
- `input_total_combos == 5913`
- `input_processed_combos == 5913`
- classification counts 合理對齊
- `production_impact == "NO_PRODUCTION_CHANGE"`
- report 不包含 `PROMOTION_READY`
- 沒有產出 production ranking / model / Clawd live artifact

建議 verifier：

- `scripts/verify_5913_combo_effectiveness_review.py`

## 驗收

完成時請回報：

- review status
- 642 effective 裡保留幾個進 next replay
- 563 follow-up 裡保留幾個進 monitor
- 明確淘汰幾個
- top 5 可複用策略零件
- top 5 誤導性結果
- 下一批 replay queue
- production impact
- errors

## 預期結論邊界

這張卡最多只能產生「研究審核結論」與「下一輪 replay queue」。

它不能直接讓任何策略上 production，也不能宣稱模型變強。
