---
id: FUNDAMENTAL-OFFICIAL-BACKFILL-01
status: completed
type: implementation
---

# FUNDAMENTAL-OFFICIAL-BACKFILL-01

## 目的

以 MOPS 官方季度 XBRL 整批檔回填目前研究區間的基本面資料，取代低覆蓋的零散 Goodinfo cache，並維持 point-in-time 防偷看契約。

## 範圍

- 解析 MOPS IFRS 季度 XBRL ZIP。
- 產生既有 `FundamentalRepository` 可讀的九個 `fundamental_*` 指標。
- 只在離線匯入命令存取外部來源；API、排名與訓練流程不得即時抓取。
- 不調整 ranking、feature promotion 或 production 權重。

## 日期契約

- XBRL 整批檔未提供可直接驗證的逐公司原始申報時間。
- 為涵蓋金融控股公司等特殊申報情形，回填資料一律採較晚可用日：Q1 於 6/1、Q2 於 8/30、Q3 於 11/30、Q4 於次年 5/1 起可用。
- 季度 ZIP 可能包含後續更補正後的目前版本；artifact 必須揭露此限制，不得宣稱為逐版本歷史真值。

## 驗收

1. parser 測試覆蓋一般財報欄位、負號、合併報表優先與保守可用日。
2. 匯入後 feature universe cache coverage 達 80% 以上。
3. 重新產生 point-in-time readiness artifact，成熟日期 Top200 coverage 達研究門檻。
4. 受影響測試與 `git diff --check` 通過。
