# Daily Brief Absorption

## 目標

吸收 `daily_stock_analysis` 的晨報與決策看板優點，但保留 TOP10new 的可驗證 ranking 主線。

## 已落地

- 晨報輸出格式：`analysis_report.md` 會輸出核心摘要、入選理由、分數拆解、風險警報、正向催化、操作檢查清單。
- `not_supported` 降級語意：外部新聞催化與通知投遞尚未接入時，報告會明確標記，不讓空值被包裝成結論。
- Artifact 保留：`StockReportGenerator` 會同時輸出 `analysis_report.yaml`、`analysis_report.md`、`analysis_report.json`、`analysis_report.html` 與 `ranked_stocks_detailed.csv`。

## 保留邊界

- `daily_brief` 只讀 ranking / trade plan / risk guard 欄位，不改 `risk_adjusted_score`。
- 不呼叫 LLM 產生入選理由。
- 外部新聞、通知渠道、設定診斷與自選股匯入仍是後續切片，不在這次改動中假裝完成。

## 下一切片

1. 通知接點：建立 `notification_delivery` adapter，只推送既有 report artifact。
2. 設定診斷：新增 read-only health artifact，檢查資料源、模型檔、股票清單與通知渠道。
3. 自選股匯入/補全：支援 CSV / clipboard schema，先輸出候選清單，不直接改正式股票池。
4. 新聞催化：若接入外部新聞，必須保留來源、日期與 `not_supported/missing/stale` 狀態。
