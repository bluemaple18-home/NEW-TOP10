# EXIT-SIGNAL-01 價格 / 排名 / 量能 / 過熱後失速

日期：2026-06-08
狀態：READY_FOR_RESEARCH

## 目標

建立下一輪「獲利了結 / 轉弱提醒」研究主線。

本卡承接 `CHIP-FLOW_warning_research_handoff` 的結論：籌碼資料可保留為研究 overlay 或推薦理由輔助，但不作為正式大盤判斷、ranking score、正式 warning channel、個人化賣出或減碼提醒。

## 為什麼不是繼續硬挖 chip_flow

目前證據不支持：

- 外資賣 = 危險。
- 融資增加 = 危險。
- 外資賣且融資增 = 可正式提醒。
- 三大法人 / 融資融券單獨作為大盤方向主判斷。

`COMPOSITE_RISK` 雖然方向比較像風險，但樣本只有 3 筆，不可產品化。

## 下一輪優先測試

1. 價格失速
   - 高檔跌破 MA5 / MA10 / MA20。
   - 強勢後 5D momentum 轉負。
   - 長黑或長上影後收弱。

2. 排名退潮
   - Top10 內排名連續惡化。
   - Top3 掉出 Top10。
   - risk_adjusted_score momentum 轉負。

3. 量能退潮
   - 爆量後不再創高。
   - 價漲量縮後轉跌。
   - 成交量高峰後縮量跌破短均。

4. 過熱後反轉
   - 5D / 10D / 20D 漲幅過大。
   - 乖離偏高。
   - 隨後價格、排名、量能同步轉弱。

## 使用 chip_flow 的邊界

可用：

- 研究 overlay。
- 推薦理由輔助文字。
- 未來檢查是否在 price/rank/volume baseline 之外仍有增量。

不可用：

- 不進 production ranking score。
- 不進正式 warning channel。
- 不作大盤主訊號。
- 不作個人化賣出 / 減碼提醒。
- 不把缺資料填 0 後解讀成法人未買賣。

## 驗收條件

- 產出 replay artifact，比較 price/rank/volume/overheat reversal 對 1D / 3D / 5D / 10D outcome 的效果。
- 至少和 chip_flow aggregate / composite 結論並列表達，不得把 chip_flow 當 baseline 主軸。
- 報告必須標示 production_ready=false，除非另走正式 promotion review。
- 不改模型、不改 Top10、不改 risk_adjusted_score、不發推播。

## 參考證據

- `docs/tasks/2026-06-08_CHIP-FLOW_warning_research_handoff.md`
- `artifacts/model_experiments/chip_warning_replay_aggregate_2026-06-08.json`
- `artifacts/model_experiments/chip_composite_warning_report_top10_20d_2026-06-08.json`
- `artifacts/model_experiments/chip_flow_readiness_report_2026-06-08.json`

## 2026-06-08 初輪研究結果

新增 research artifacts：

- `artifacts/model_experiments/exit_signal_reversal_research_2026-06-08.json`
- `artifacts/model_experiments/exit_signal_volume_warning_portfolio_replay_2026-06-08.json`

結論：

- `price_break_after_overheat`、`momentum_rollover_after_overheat`、`overheat_reversal_composite` 目前不適合當 warning。
- 這些訊號在 Top10 強勢股樣本裡，反而呈現較高平均報酬、較低大跌率，較像洗盤或強勢延續。
- `rank_momentum_break` 單獨效果也不乾淨，不可當出場警訊。
- `volume_climax_reversal` 與 `volume_climax_after_overheat` 是目前唯一可進下一關的 warning-only shadow monitor candidate。

關鍵數字：

| Signal | 5D 樣本 | 5D 標的平均差 | 10D 回撤改善 | 判定 |
| --- | ---: | ---: | ---: | --- |
| `volume_climax_reversal` | 39 | -1.50% | +0.67% | warning monitor candidate |
| `volume_climax_after_overheat` | 32 | -0.86% | +0.67% | warning monitor candidate |
| `volume_climax_plus_rank_break` | 21 | -1.75% | +0.08% | 樣本不足 |

下一步：

- 只把 `volume_climax_reversal` 做 daily warning-only shadow monitor。
- 仍不得作個人持倉賣出通知。
- 仍不得進 production ranking、`risk_adjusted_score` 或正式推播。

## 2026-06-08 Daily Shadow Monitor 雛形

新增 artifact：

- `artifacts/model_experiments/exit_signal_volume_climax_daily_shadow_monitor_2026-06-08.json`

結果：

- target ranking date：`2026-06-05`
- latest Top10 warning count：`0`
- recent 7 ranking days watchlist warning count：`6`
- monitor status：`MONITOR_ACTIVE`
- production ready：`false`

觸發清單：

| Stock | 狀態 |
| --- | --- |
| `1409 新纖` | 近 7 日曾入榜；volume climax weakening |
| `1513 中興電` | 近 7 日曾入榜；volume climax weakening |
| `2641 正德` | 近 7 日曾入榜；volume climax weakening |
| `3630 新鉅科` | 近 7 日曾入榜；volume climax weakening |
| `4720 德淵` | 近 7 日曾入榜；volume climax weakening |
| `5225 東科-KY` | 近 7 日曾入榜；volume climax weakening |

產品邊界：

- 這是 warning-only shadow，不是每日推薦。
- 這不是個人持倉賣出通知。
- 不發送正式推播。
- 不改 production ranking / model / `risk_adjusted_score`。

判讀：

最新 Top10 沒觸發，代表不應把這個訊號塞進每日推薦訊息。
近 7 日觀察池有 6 檔觸發，代表它比較適合獨立 warning channel / observation layer。
