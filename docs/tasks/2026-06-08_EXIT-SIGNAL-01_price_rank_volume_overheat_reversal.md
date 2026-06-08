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
