# Capital-Aware Exit Rule Framework

日期：2026-06-03

## 結論

目前正式版不是爛掉，而是「比較敢讓強股跑」。在近半年牛市資料裡，正式版 `fixed40 / gross65` 的報酬最好，但它不是小白最舒服的交易規則。

真正該補的不是再硬換模型，而是把交易規則從「模型選股」升級成「有限本金的小白可執行策略」：

- 不再用每檔固定買 100 股、金額無上限當主要評估。
- 加入本金、現金、單檔上限、產業上限、買不起就跳過或降股數。
- 把 15% 停利改成「部分停利 + 續抱 runner + 盤勢好才再上車」，不是 15% 全部賣掉。
- 原正式版保留為比較組，新規則用同一套回測口徑比較。

## 目前證據

近半年主要結果：

| 規則 | 報酬 | 最大回撤 | 勝率 | 判斷 |
| --- | ---: | ---: | ---: | --- |
| 現正式版：Top10 / fixed40 / gross65 | +63.3% | -6.6% | 73.5% | 報酬最好，保留為 baseline |
| gross55：Top10 不變，只降總曝險 | +47.0% | -6.3% | 72.8% | 較保守，但近半年少賺不少 |
| 15% 全停利 / gross65 | +35.2% | -5.3% | 81.9% | 勝率高，但牛市太早下車 |
| 15% 全停利 / gross55 | +28.9% | -4.2% | 81.8% | 最舒服，但報酬砍太多 |
| 30D + 25%停利 + 10%停損 | +37.8% | -6.1% | 54.7% | 不是主線 |
| 產業上限 45% | +62.6% | -6.6% | 73.0% | 幾乎沒降風險，不當預設 |
| Top3 | +73.0% | -11.1% | 76.1% | 報酬高但太集中，不能給小白當預設 |

長區間 dense validation：

| 規則 | 報酬 | 最大回撤 | 判斷 |
| --- | ---: | ---: | --- |
| fixed40 | +183.1% | -33.4% | 報酬強，但小白痛感太大 |
| gross55 | +154.3% | -28.8% | 少賺，但明顯降回撤 |
| sector45 | +159.7% | -33.3% | 報酬降，回撤幾乎沒改善 |

目前證據支持：

- 正式版「報酬」仍然比較好。
- gross55 是風控候選，不是 alpha 候選。
- 15% 全停利太粗，不能直接上。
- 7+3 / sector 類規則目前沒有證明比正式 Top10 強。

## 新的本金假設

預設用小白可接受的本金：

```text
初始本金：500,000 TWD
交易單位：100 股 odd-lot
最大投入：依盤勢，強多盤可到 85% ~ 90%
保留現金：依盤勢，強多盤最多保留 10% ~ 15%
單檔上限：本金 8%，高信心最多 10%
單一產業上限：30%
單日新增買進上限：最多 3 檔
```

為什麼不用 100 萬或無限本金：

- 小白不一定有足夠資金同時買滿 10 檔。
- 高價股如 600 元以上，100 股就是 60,000 元以上，單檔會吃掉太多本金。
- 如果不限制本金，回測會高估可執行性，也會低估現金不足造成的漏單。

盤勢曝險設定：

| 盤勢 | 目標投入 | 保留現金 | 說明 |
| --- | ---: | ---: | --- |
| BIG_BULL / 強多盤 | 85% ~ 90% | 10% ~ 15% | 牛市不該太保守，重點是讓強股跑 |
| RISK_ON / 偏多盤 | 75% ~ 85% | 15% ~ 25% | 仍偏積極，但保留一點機動現金 |
| HIGH_CHOPPY / 高檔震盪 | 60% ~ 75% | 25% ~ 40% | 有行情但容易洗，要降一點曝險 |
| NEUTRAL / 普通盤 | 50% ~ 65% | 35% ~ 50% | 沒有明確優勢，不硬上滿 |
| RISK_OFF / 弱勢盤 | 20% ~ 35% | 65% ~ 80% | 先防守，除非有極強個股 |

因此 `gross55` 不應該當所有盤勢的主線。它比較像高檔震盪或不確定盤的保守版本；牛市主測應該是 `gross85 / gross90 + partial runner`。

買進規則：

```text
每檔目標金額 = min(本金 * 建議權重, 本金 * 單檔上限)
實際股數 = floor(目標金額 / 股價 / 100) * 100
若實際股數 = 0，跳過或降到觀察名單，不硬買
若產業超過 30%，從同產業低排名開始跳過
```

這會讓推薦更像真實小白會遇到的情況：不是上榜就都能買，也不是每檔一定買 100 股。

## 新規則：TP15 Partial Runner

這是我認為應該主動測的規則，不是沿用舊 15% 全停利。

核心想法：

```text
先保護一部分獲利，但不要把強股太早賣光。
```

規則草案：

```text
進場：
- D 日收盤入榜，D+1 開盤買進。
- 只買得起且符合部位上限的股票。

至少持有：
- 至少持有 5 個交易日。

部分停利：
- 持有滿 5 天後，若浮盈 >= 15%，先賣出 50%。
- 剩下 50% 變成 runner。

runner 續抱：
- 若大盤仍是 BIG_BULL / RISK_ON / HEALTHY_NEUTRAL，且個股仍在 Top20 或趨勢未壞，繼續持有。
- 最長先測 40 個交易日。

runner 出場：
- 從高點回落 10%。
- 或跌回成本附近。
- 或連續 3 天跌出 Top20。
- 或盤勢轉 RISK_OFF / PANIC_SELLING。

再上車：
- 若部分停利後，股票重新進 Top10，且盤勢仍好，可以補回到原目標部位。
- 完全出場後冷卻 3 天，避免同一檔反覆追高殺低。
```

這條規則要解決的問題：

- 15% 全賣太早下車。
- fixed40 太敢抱，遇到回吐時小白很痛。
- runner 讓強股有機會繼續貢獻報酬。
- 部分停利讓使用者心理上知道「已經有鎖一部分」。

## 下一輪測試矩陣

正式比較組：

```text
C0 current_production_fixed40_gross65
```

新候選：

```text
C1 capital_aware_fixed40_regime_gross
C2 capital_aware_tp15_partial50_runner_regime_gross
C3 capital_aware_tp15_partial33_runner_regime_gross
C4 capital_aware_7plus3_fixed40_regime_gross
C5 capital_aware_7plus3_tp15_partial50_runner_regime_gross
C6 high_choppy_capital_aware_fixed40_gross65
C7 high_choppy_capital_aware_tp15_partial50_runner_gross65
```

測試區間：

```text
近半年：2025-11-17 ~ 2026-05-15
長區間：2023-11-21 ~ 2026-05-15
盤勢分層：BIG_BULL / HIGH_CHOPPY_CONTEXT / RISK_OFF / OTHER
```

評估指標：

```text
總報酬
最大回撤
勝率
平均持有天數
現金使用率
買不起而跳過的次數
單檔最大虧損
單檔最大回吐
15% 後續抱 runner 的貢獻
再上車成功率
產業集中度
換手率
```

小白體感指標：

```text
任一時間最大未實現虧損
連續虧損天數
從曾經賺錢變成賠錢的次數
上榜後 5 天內就套牢的比例
賣太早後又噴出的比例
```

## 上線判斷

可以直接上的只有「不改名單」或「風控呈現」類規則。

不能直接上的：

- 會改 Top10 名單的 7+3。
- 會改模型分數的規則。
- 只在近半年牛市漂亮、長區間不穩的規則。

新版若要變正式，至少要做到：

```text
報酬不得低於正式版太多
最大回撤要有明顯改善
小白體感指標要明顯改善
BIG_BULL 不能太早下車
HIGH_CHOPPY 不能擴大虧損
買不起 / 現金不足情境要被納入
```

## 我的判斷

我前面偷懶的地方，是把 exit rule 當成幾個粗參數在掃，沒有先建一個「真實小白資金限制下的交易系統」。

正確順序應該是：

1. 固定本金與部位規則。
2. 用真實可買股數重跑回測。
3. 測 TP15 partial runner，而不是 15% 全停利。
4. 再測 7+3 是否值得改名單。
5. 最後才決定是否改正式推播。

下一步要做的是 `CAPITAL-01`：

```text
建立 capital-aware replay engine
本金 500,000 TWD
100 股 odd-lot
有限現金
單檔 8% / 10% cap
產業 30% cap
TP15 partial runner
盤勢動態總曝險：BIG_BULL 85%~90%，HIGH_CHOPPY 60%~75%，RISK_OFF 20%~35%
原正式版作比較組
```

## CAPITAL-01 結果

狀態：完成第一輪有限本金 replay 與 exit rule 比較。

產物：

```text
scripts/run_capital_aware_replay.py
scripts/build_capital_exit_rule_report.py
scripts/verify_capital_exit_rule_report.py
artifacts/model_experiments/capital_exit_rule_report_2026-06-03.json
artifacts/model_experiments/capital_exit_rule_report_2026-06-03.md
```

近半年有限本金結果：

| 規則 | 報酬 | 最大回撤 | 勝率 | 判斷 |
| --- | ---: | ---: | ---: | --- |
| fixed40 + fixed65 | +49.58% | -13.65% | 66.67% | 有限本金 baseline |
| fixed40 + regime gross | +62.93% | -7.17% | 72.41% | 目前最佳 capital-aware candidate |
| TP15 sell 33% runner | +49.96% | -13.70% | 100.00% | 不採用主規則 |
| TP15 sell 40% runner | +54.66% | -14.37% | 100.00% | 不採用主規則 |
| TP15 sell 50% runner | +55.31% | -14.35% | 100.00% | 最佳 TP variant，但仍輸主線 |
| TP20 sell 33% runner | +34.64% | -11.25% | 100.00% | 報酬掉太多 |
| TP20 sell 50% runner | +34.99% | -11.23% | 100.00% | 報酬掉太多 |

結論：

```text
winner = fixed40 + regime gross
TP15 / TP20 partial runner = REJECT_AS_PRIMARY_RULE
production_ready = false
models/latest_lgbm.pkl unchanged
ranking score unchanged
```

對應假設：

- H1：有限本金 replay 是必要的。不能再只看無限資金每檔 100 股。
- H2：牛市不該過度保留現金；盤勢曝險比固定 gross65 更適合目前資料。
- H3：TP15 / TP20 partial runner 沒有解決問題；勝率漂亮但回撤與報酬都不如主線。

下一步：

```text
CAPITAL-02
把 fixed40 + regime gross 做長區間驗證與盤勢分層診斷。
TP runner 不再當主線，只保留為使用者偏好風控或頁面說明素材。
```

## CAPITAL-02 結果

狀態：完成長區間驗證，阻擋直接 production change。

產物：

```text
artifacts/backtest/capital_aware_replay_current_fixed40_fixed65_long_dense_2026-06-03.json
artifacts/backtest/capital_aware_replay_current_fixed40_regime_long_dense_2026-06-03.json
artifacts/model_experiments/capital_long_validation_report_2026-06-03.json
artifacts/model_experiments/capital_long_validation_report_2026-06-03.md
scripts/build_capital_long_validation_report.py
scripts/verify_capital_long_validation_report.py
```

長區間結果：

| 規則 | 報酬 | 最大回撤 | 勝率 | 判斷 |
| --- | ---: | ---: | ---: | --- |
| fixed40 + fixed65 | +75.70% | -36.38% | 46.81% | 長區間 baseline 較會賺 |
| fixed40 + regime gross | +49.30% | -33.69% | 46.72% | 回撤小一點，但少賺太多 |

盤勢分層：

| family | fixed65 | regime gross | delta |
| --- | ---: | ---: | ---: |
| BIG_BULL | +89.82% | +79.77% | -10.05% |
| HIGH_CHOPPY_CONTEXT | +24.10% | +5.97% | -18.13% |
| OTHER | -4.43% | -4.36% | +0.07% |
| RISK_OFF | -21.96% | -18.05% | +3.91% |

結論：

```text
decision = LONG_VALIDATION_BLOCKS_PRODUCTION_CHANGE
production_ready = false
```

這不是說 regime gross 沒用，而是它不能整套上線：

- 在 RISK_OFF 有防守價值。
- 在 BIG_BULL 少賺太多。
- 在 HIGH_CHOPPY_CONTEXT 掉最多，代表現在的高檔震盪降曝險規則太粗。

下一步：

```text
CAPITAL-03
不再測 TP runner 當主線。
改測 selective defensive overlay：
- BIG_BULL 維持接近 fixed65 / 不降太多
- RISK_OFF 才明確降曝險
- HIGH_CHOPPY 不直接大降曝險，先測產業集中 / 單檔風險 / 新倉限制
```

## CAPITAL-03 結果

狀態：完成防守 overlay 掃描，沒有任何 overlay 可直接取代預設。

產物：

```text
artifacts/model_experiments/capital_defensive_overlay_report_2026-06-03.json
artifacts/model_experiments/capital_defensive_overlay_report_2026-06-03.md
scripts/build_capital_defensive_overlay_report.py
scripts/verify_capital_defensive_overlay_report.py
```

核心結果：

| 規則 | 近半年報酬 / DD | 長區間報酬 / DD | 判斷 |
| --- | ---: | ---: | --- |
| fixed65 | +49.58% / -13.65% | +75.70% / -36.38% | 仍是預設比較組 |
| fixed60 | +44.72% / -12.54% | +71.91% / -33.69% | 可當保守 profile shadow |
| fixed55 | +44.51% / -11.41% | +58.69% / -30.18% | 少賺太多 |
| full regime | +62.93% / -7.17% | +49.30% / -33.69% | 近半年漂亮，長區間不穩 |
| RISK_OFF 30%, others 65% | +42.07% / -5.94% | +65.34% / -36.38% | 近半年少賺太多，長區間 DD 不降 |
| RISK_OFF 40%, others 65% | +42.26% / -8.32% | +46.90% / -36.38% | 不採用 |
| 單檔 8% cap | 無變化 | 無變化 | 現有交易已未觸發 |
| 產業 25% cap | +46.65% / -13.65% | +62.36% / -36.22% | 少賺，風險沒改善 |

結論：

```text
default_rule = fixed40_fixed65
conservative_profile_candidate = fixed60
production_ready = false
```

下一步不是再亂掃停利或現金比例，而是測「入場品質」：

```text
CAPITAL-04
測 persistence / rank stability filters：
- 連續入榜幾天再買是否更穩
- 排名變化是否能過濾假突破
- 新進榜 vs 連續榜哪個報酬更好
- HIGH_CHOPPY 下是否要限制新進榜，而不是整體降曝險
```

## CAPITAL-04 結果

狀態：完成入場品質 filter 掃描，找到兩個 shadow 候選。

產物：

```text
artifacts/model_experiments/capital_entry_quality_report_2026-06-03.json
artifacts/model_experiments/capital_entry_quality_report_2026-06-03.md
scripts/build_capital_entry_quality_report.py
scripts/verify_capital_entry_quality_report.py
```

核心結果：

| 規則 | 近半年報酬 / DD | 長區間報酬 / DD | 判斷 |
| --- | ---: | ---: | --- |
| baseline all entries | +49.58% / -13.65% | +75.70% / -36.38% | 預設比較組 |
| first_day | +69.91% / -13.64% | +26.06% / -30.41% | 近半年牛市強，但跨盤勢失效 |
| streak_2_plus | +37.56% / -13.13% | +61.84% / -23.90% | 太保守 |
| improved_or_new | +51.56% / -13.13% | +65.17% / -33.51% | 有改善但不夠 |
| non_worsening | +51.29% / -13.13% | +71.55% / -32.08% | balanced shadow candidate |
| improved_only | +54.50% / -13.13% | +47.97% / -22.92% | conservative shadow candidate |

結論：

```text
default_rule = fixed40_fixed65_all_entries
balanced_shadow_candidate = non_worsening
conservative_shadow_candidate = improved_only
production_ready = false
```

對產品的意義：

- 不要把「連續入榜才買」當鐵律；它會錯過很多動能。
- 新進榜在近半年牛市很強，但長區間不穩，不能直接上。
- 排名沒有轉弱的股票比較適合做平衡版 shadow。
- 排名明確改善的股票可作保守版 shadow，犧牲報酬換大幅降回撤。

下一步：

```text
CAPITAL-05
建立 daily shadow monitor：
- production baseline
- non_worsening balanced shadow
- improved_only conservative shadow
每天跟正式 Top10 一起產 artifact，但不改正式推播。
```

## CAPITAL-05 結果

狀態：完成每日 shadow monitor 接入。

新增產物：

```text
scripts/build_capital_entry_quality_daily_shadow_monitor.py
scripts/verify_capital_entry_quality_daily_shadow_monitor.py
scripts/build_capital_entry_quality_daily_shadow_monitor_batch.py
scripts/verify_capital_entry_quality_daily_shadow_monitor_batch.py
artifacts/model_experiments/capital_entry_quality_daily_shadow_monitor_2026-06-02.json
artifacts/model_experiments/capital_entry_quality_daily_shadow_monitor_batch_2026-06-02.json
```

daily automation 接入：

```text
config/automation.yaml
  daily.capital_entry_quality_shadow_monitor_enabled = true
  daily.capital_entry_quality_shadow_monitor_batch_enabled = true

scripts/run_automation.py
  ranking 後、Clawd payload 前產生入場品質 shadow monitor
  allow_failure=True，不阻斷 daily 主流程
```

2026-06-02 實跑：

| monitor | 結果 |
| --- | --- |
| production Top10 | 10 檔 |
| balanced non_worsening | 9 檔 |
| conservative improved_only | 1 檔 |
| batch ranking days | 6 天 |
| avg balanced eligible | 9.5 檔 |
| avg conservative eligible | 0.67 檔 |

2026-06-02 balanced 名單：

```text
8043, 1815, 3147, 1809, 3338, 3260, 2379, 2104, 3234
```

2026-06-02 conservative 名單：

```text
1815
```

驗證：

```text
verify_capital_entry_quality_daily_shadow_monitor.py: OK
verify_capital_entry_quality_daily_shadow_monitor_batch.py: OK
run_automation.py daily --dry-run: OK
```

dry-run step 順序：

```text
decision.quality
gross55.shadow_monitor
gross55.shadow_monitor_batch
capital_entry_quality.shadow_monitor
capital_entry_quality.shadow_monitor_batch
clawd.payload
```

邊界：

```text
不改正式 Top10
不改 ranking CSV
不改 Clawd 訊息
不改模型
不允許升預設
```
