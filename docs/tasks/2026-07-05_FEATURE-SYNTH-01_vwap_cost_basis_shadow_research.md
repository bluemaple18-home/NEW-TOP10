# FEATURE-SYNTH-01 VWAP 成本線 Shadow Research

日期：2026-07-05
狀態：READY_FOR_FIRST_WAVE_RESEARCH
優先級：FIRST_WAVE_INSERT

## 任務卡

任務ID：FEATURE-SYNTH-01
卡片類型｜派工對象：Feature Synthesis Research｜Codex
請讀：`app/volume_indicators.py`、`app/modeling/feature_contract.py`、`scripts/research_regime_feature_offline_ablation.py`、`scripts/build_feature_experiment_gate.py`
任務目的：把 VWAP / 成交量加權成本線整合進正式 `features.parquet` 特徵產出管線，再作為 research-only 候選特徵族驗證是否能提升預測、Top10 replay 與進場品質，不改 production ranking
證據路徑：`artifacts/model_experiments/vwap_cost_basis_features_YYYY-MM-DD.json`、`artifacts/model_experiments/vwap_cost_basis_ablation_YYYY-MM-DD.json`

## 背景

目前系統已有 `close`、`volume`、`value`、`avg_volume_*d`、`volume_ratio_*d`、`avg_value_20d` 等原料。VWAP/cost_basis 維度必須由正式 ETL 指標階段產出，不可只靠一次性研究 artifact 東拼西湊。

這張卡的目的不是直接把 VWAP 當神奇指標，而是把「成交量加權市場成本」送進既有研究流程，讓它接受 IC、walk-forward、regime 分層與 Top10 replay 檢驗。

本卡列入第一輪研究插隊項目，原因是定義明確、資料原料已存在、驗證邊界清楚，適合用來檢查模型是否能從量價成本線獲得增量。插隊只限 research lane，不代表 promotion 或 production 變更。

## 正式資料落點

- 公式來源：`app/volume_indicators.py`
- 正式產出：`IndicatorStage -> VolumeIndicators.calculate_all_volume_indicators() -> data/clean/features.parquet`
- 契約驗證：`app/pipeline/validation.py` 要求 `value`、`daily_vwap`、`rolling_vwap_20d`、`close_vs_vwap_20d`
- 覆蓋 audit：`scripts/audit_research_dataset_coverage.py` 新增 `cost_basis` 維度
- 研究 materializer：`scripts/build_vwap_cost_basis_features.py` 只能作回補 / first-wave research artifact，公式必須呼叫正式 `VolumeIndicators`

## 候選特徵族

第一批只測可由現有日頻資料穩定產出的欄位：

- `daily_vwap`：優先用 `value / volume`；若資料單位不一致，改用 `close * volume` 衍生 proxy 並在 artifact 註明。
- `rolling_vwap_5d`：近 5 日成交量加權成本。
- `rolling_vwap_20d`：近 20 日成交量加權成本。
- `close_vs_vwap_5d`：收盤價相對 5 日 VWAP 乖離。
- `close_vs_vwap_20d`：收盤價相對 20 日 VWAP 乖離。
- `vwap_reclaim_20d`：前一日低於 20 日 VWAP、今日重新站回。
- `vwap_loss_20d`：前一日高於 20 日 VWAP、今日跌破。

## 研究邊界

可以：

- 新增 research-only materializer。
- 產出暫存 feature artifact。
- 跑離線 IC / regime ablation / Top10 replay。
- 把通過者送進 shadow feature experiment gate。

不可以：

- 直接改 `RankingPolicy`。
- 直接改 `risk_adjusted_score`。
- 直接重訓或覆蓋正式模型。
- 直接改每日 Top10 推播文案。
- 把單次回測勝利解讀成 production ready。

## 驗收條件

- Materializer 明確輸出資料單位檢查：`value / volume` 是否落在合理價格區間。
- 每個候選欄位需回報 coverage、missing ratio、極端值比例。
- 至少比較 baseline vs 加入 VWAP family 的 walk-forward 指標。
- 至少輸出 by-regime 結果，避免只在單一盤勢有效。
- Top10 replay 必須回報 return、hit rate、max drawdown、turnover 與 concentration 變化。
- artifact 必須標示 `production_ready=false`，除非另走正式 promotion review。

## 第一階段判定

進下一關條件：

- VWAP family 至少一個特徵在半年度 walk-forward 中呈現穩定正向增量。
- Top10 replay 不惡化 max drawdown 與集中度。
- 弱盤或 RISK_OFF regime 不出現明顯反向傷害。

淘汰條件：

- 只在單一短窗口有效。
- IC 方向不穩。
- replay 改善來自更高集中度或更高 turnover。
- `value / volume` 單位無法被可靠驗證。

## 下一步

已先把 cost_basis 整合進正式特徵產出與資料契約，再排進第一輪研究驗證；若通過基本資料單位檢查，再進 IC / regime ablation / Top10 replay。本卡可以插入第一輪研究，但不得阻塞既有 60 萬節點 burn-down，也不得直接 promotion。

## 2026-07-05 第一輪研究結果

新增 artifacts：

- `artifacts/model_experiments/vwap_cost_basis_research_2026-07-05.json`
- `artifacts/model_experiments/vwap_cost_basis_research_2026-07-05.md`
- `artifacts/model_experiments/vwap_cost_basis_model_ablation_2026-07-05.json`
- `artifacts/model_experiments/vwap_cost_basis_model_ablation_2026-07-05.md`

結論：

- decision：`FIRST_WAVE_SIGNAL_FOUND`
- cost_basis 有明確研究價值，但不可直接 promotion。
- IC 強訊號主要集中在 `PANIC_SELLING`，其中 `close_vs_vwap_*` 呈現「離 VWAP 太遠反而不好」的負向訊號。
- `PANIC_SELLING` 樣本只有 9 天，訊號強但需要更長歷史/更多 regime replay 才能產品化。
- 離線模型 ablation 顯示含 VWAP family 比拔掉 VWAP family 有小幅增量：AUC +0.00126、TopN return +0.2163 個百分點。
- `planned_features_only` TopN proxy 很強，但這是 diagnostic-only，不能當 promotion 證據。
- 正式模型 gate 仍判定 `REJECTED`，原因是 positive folds 未達 4；所以不能說「已升級模型」。

關鍵數字：

| 測試 | 結果 |
| --- | ---: |
| VWAP IC rows | 168 metrics |
| SHADOW_CANDIDATE | 21 |
| WATCH | 55 |
| baseline AUC | 0.667784 |
| drop VWAP AUC | 0.666524 |
| baseline - drop AUC | +0.001260 |
| baseline TopN return | 4.3181% |
| drop VWAP TopN return | 4.1018% |
| baseline - drop TopN return | +0.2163 pct |
| planned-only TopN return | 7.7452% |

初步定位：

- 不直接進 production ranking。
- 下一關應跑 cost_basis 專屬 Top10 replay / entry-quality overlay，而不是直接改模型權重。
- 最有產品語意的方向是「追價風險 / 進場品質」：當價格離 VWAP 成本線過遠，尤其在弱勢或 panic regime，可能代表短線追價不划算。

## 2026-07-05 Entry Quality Replay

新增 artifacts：

- `artifacts/model_experiments/vwap_entry_quality_replay_2026-07-05.json`
- `artifacts/model_experiments/vwap_entry_quality_replay_2026-07-05.md`

結論：

- decision：`NO_ENTRY_QUALITY_UPLIFT`
- 以既有 `historical_rankings_current_model_half_year_dense_2025-11-17_2026-05-15` 測試，VWAP overlay 沒有改善 3D / 5D / 10D replay。
- 原因不是 VWAP 完全無效，而是該 ranking 目錄每天只有 Top10，沒有 Top20 / Top50 候補池；entry overlay 無法真正換股，只能改 Top10 順序。
- 等權 bucket 對順序不敏感，因此 replay 結果與 baseline 幾乎一致。

限制：

- 這次 entry replay 不能回答「用 VWAP 從候選池替換追價股是否有效」。
- 要回答替換效果，下一步需要先產生含 Top20/Top50 的候選 ranking artifact，或在模型驗證窗直接輸出候選池。
- 在候補池補齊前，不可把 VWAP 寫成正式進場過濾器。

## 2026-07-05 Top50 Candidate Pool Replay

新增能力 / artifacts：

- `scripts/build_historical_ranking_replay_set.py` 新增 `--top-n`，可產生 Top50 研究候選池；`top_n > 10` 時不套正式投組權重，避免把 Top50 誤寫成正式配置。
- `artifacts/research_rankings/current_model_top50_2025-11-17_2026-05-15/manifest.json`
- `artifacts/model_experiments/vwap_entry_quality_replay_top50_2026-07-05.json`
- `artifacts/model_experiments/vwap_entry_quality_replay_top50_2026-07-05.md`
- `artifacts/model_experiments/vwap_regime_gated_entry_quality_2026-07-05.json`
- `artifacts/model_experiments/vwap_regime_gated_entry_quality_2026-07-05.md`

Top50 全域 overlay 結論：

- decision：`NO_ENTRY_QUALITY_UPLIFT`
- Top50 候選池共 117 個交易日，ranking 產生失敗 0。
- 全域套 VWAP entry overlay 不可 promotion；最佳全域政策仍為負增量：
  - 5D `lowest_vwap_distance_5d`：return delta `-0.000244`
  - 3D / 10D 全部 policy 也都輸 baseline。
- 原因：把「離 VWAP 最近」當主排序會犧牲原模型 alpha，且 turnover 約 `0.91`，替換太激進。

By-regime 發現：

- Regime 覆蓋完整：338 個 regime dates，ranking unknown dates `0`。
- `RISK_OFF` 佔 98/117 天，是全域失效主因；VWAP 不應在 RISK_OFF 全面替代模型排序。
- `NARROW_LEADER` 與 `PANIC_SELLING` 有局部正訊號：
  - `NARROW_LEADER`：`balanced_cost_basis` 在 3D / 5D 為正，5D delta `+0.013198`。
  - `PANIC_SELLING`：`balanced_cost_basis` 在 5D / 10D 為正，10D delta `+0.014061`。

Regime-gated replay 結論：

- 若只在 `NARROW_LEADER` / `PANIC_SELLING` 啟用 `balanced_cost_basis`，其餘 regime 保持 baseline，三個 horizon 都有正增量：

| Horizon | Return Delta | Hit Rate | Max Drawdown | Turnover |
| ---: | ---: | ---: | ---: | ---: |
| 3D | +0.001245 | 0.445102 | -0.341024 | 0.853448 |
| 5D | +0.001492 | 0.464937 | -0.390225 | 0.853448 |
| 10D | +0.001560 | 0.509626 | -0.337227 | 0.853448 |

判定：

- VWAP 不升級成「全域進場過濾器」。
- VWAP 可保留為 `regime-gated entry quality overlay` 的研究候選。
- 下一關若要推進，應把候選形態固定為：「只在 `NARROW_LEADER` / `PANIC_SELLING` 啟用 balanced cost-basis overlay；RISK_OFF 不替代原模型排序」，再跑更長窗 / sealed split / turnover gate。

## 2026-07-06 Long-Window / Sealed / Production-Style Replay

新增 scripts / artifacts：

- `scripts/research_vwap_regime_gated_entry_quality.py`
- `scripts/materialize_vwap_regime_gated_rankings.py`
- `artifacts/research_rankings/current_model_top50_long_2025-01-02_2026-05-15/manifest.json`
- `artifacts/model_experiments/vwap_entry_quality_replay_top50_long_2026-07-06.json`
- `artifacts/model_experiments/vwap_regime_gated_entry_quality_long_2026-07-06.json`
- `artifacts/research_rankings/vwap_nl_panic_balanced_top10_long_2025-01-02_2026-05-15/manifest.json`
- `artifacts/research_rankings/vwap_nl_panic_avoid5_top10_long_2025-01-02_2026-05-15/manifest.json`
- `artifacts/research_rankings/vwap_narrow_only_balanced_top10_long_2025-01-02_2026-05-15/manifest.json`
- `artifacts/backtest/replay_compare_vwap_gated_plans_long_2026-07-06.json`

長窗候選池：

- Top50 ranking window：`2025-01-02` ~ `2026-05-15`
- ranking_count：248
- failure_count：0

Gated diagnostics：

- `nl_panic_balanced` 在 long-window 仍通過 research gate：
  - overall 3D delta `+0.000615`
  - overall 5D delta `+0.000696`
  - overall 10D delta `+0.000739`
  - sealed 3D / 5D / 10D 全正，分別 `+0.002503` / `+0.003004` / `+0.002367`
  - pre-sealed 幾乎持平，最差 `-0.000040`
- 判定：`REGIME_GATED_ENTRY_CANDIDATE`，但仍 `production_ready=false`。

Production-style bucket replay：

| Plan | 3D Avg Delta | 5D Avg Delta | 10D Avg Delta | 3D MDD Delta | 5D MDD Delta | 10D MDD Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `nl_panic_balanced` | +0.000366 | +0.000378 | +0.000307 | +0.016239 | +0.004073 | -0.011154 |
| `nl_panic_avoid5` | +0.000105 | +0.000232 | +0.000328 | +0.003318 | -0.000075 | -0.007943 |
| `narrow_only_balanced` | +0.000352 | +0.000351 | +0.000178 | +0.015061 | +0.003083 | +0.000000 |

更新判定：

- `nl_panic_balanced` 是 entry-quality 診斷中最強，但 10D production-style MDD 退化 `-0.011154`，略超 1% gate；不可直接推進。
- `nl_panic_avoid5` 報酬改善較小，但三個 horizon 的 MDD 退化都低於 1%，更適合作為下一關 production-style shadow candidate。
- `narrow_only_balanced` 防守性最好，但 10D hit rate 下降，訊號較窄。
- 下一關若繼續，優先測 `nl_panic_avoid5`：只在 `NARROW_LEADER` / `PANIC_SELLING` 避免 5D VWAP 過度延伸；其餘 regime 保持 baseline。

## 2026-07-06 Overlap Portfolio Replay

新增 artifacts：

- `artifacts/backtest/portfolio_compare_vwap_avoid5_long_group55_2026-07-06.json`
- `artifacts/backtest/portfolio_compare_vwap_avoid5_long_group55_sl12_tp25_2026-07-06.json`

設定：

- baseline：`artifacts/research_rankings/current_model_top50_long_2025-01-02_2026-05-15`
- candidate：`artifacts/research_rankings/vwap_nl_panic_avoid5_top10_long_2025-01-02_2026-05-15`
- long window：248 ranking days
- top_n：10
- max gross exposure：0.65
- max position weight：0.20
- max group exposure：0.55

Group-cap only：

| Horizon | Return Delta | MDD Delta | Win Rate Delta | Avg Trade Delta |
| ---: | ---: | ---: | ---: | ---: |
| 3D | +0.005871 | -0.002239 | +0.001053 | +0.000187 |
| 5D | +0.020365 | -0.003514 | +0.001145 | +0.000041 |
| 10D | +0.000851 | -0.008290 | +0.003072 | -0.000051 |

Group-cap + 12% stop / 25% take-profit：

| Horizon | Return Delta | MDD Delta | Win Rate Delta | Avg Trade Delta |
| ---: | ---: | ---: | ---: | ---: |
| 3D | -0.006542 | -0.003747 | +0.001044 | +0.000166 |
| 5D | +0.013147 | +0.000453 | +0.002546 | +0.000400 |
| 10D | +0.002262 | -0.007475 | +0.003078 | +0.000389 |

更新判定：

- `nl_panic_avoid5` 在重疊持倉 + group cap 下三個 horizon 都有正 total return delta，MDD 退化均小於 1%。
- 加入 12% stop / 25% take-profit 後，5D / 10D 仍正，3D 轉負；因此它不是 3D 短線全域改善器。
- 最合理定位：`5D/10D regime-gated shadow candidate`，不適合直接寫成正式 production filter。
- 下一關應做 forward daily shadow monitor，追蹤 `NARROW_LEADER` / `PANIC_SELLING` 啟用日是否持續改善，不再擴大到 RISK_OFF。
