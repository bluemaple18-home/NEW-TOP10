# Current Brief

任務：TOP10new 已完成 `TSKG-MFO-DAILY-01` 獨立 Review 與 mainline acceptance。

已完成：

- `MARKET-CONTEXT-02-TW`：台灣國內 market context artifact。
- `DECISION-QUALITY-01`：每日 Top10 決策品質摘要。
- `FEATURE-EXP-01`：shadow feature promotion gate。
- `REVIEW-REGIME-RESEARCH-01`：五支研究腳本邊界審查與 shadow output guard。
- `REVIEW-TSKG-MFO-DAILY-01`：跨機獨立 Review，裁決 `REVIEW_GO`。
- `TSKG-MFO-DAILY-01`：mainline acceptance `GO`；T86 只作本機 read-only artifact／market-context reuse。

目前主線：TSKG T86 daily 能力已接受；此 acceptance 不代表 ranking/model promotion。

下一步：如要繼續提升模型，另開 sealed OOS candidate 實驗卡；不得直接改 ranking 權重。
