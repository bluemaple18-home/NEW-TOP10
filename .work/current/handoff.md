# Handoff: MINI-REMAINING-01 Closeout

## 完成

- SHADOW feature experiment runner 已以 shadow-only contract 整合主線，未改 production ranking／model。
- Yuanta Windows helpers 已重建為 dry-run-first、可設定路徑、runtime secure input；初審三個 P1 經正式 Repair 與原 Reviewer re-review 關閉。
- 完整 task／verification／review／repair／acceptance evidence 均已保存。

## 仍受限制

- Yuanta 工具為 `EXPERIMENTAL`；本機無 Windows／PowerShell UIA runtime。
- 真實登入、憑證匯入、截圖與交易均需另行授權與 Windows 隔離環境驗證。
- 不得直接把任何 shadow 結果升 production；RankingPolicy、risk_adjusted_score、模型權重未修改。

## 本輪 cleanup

接收端只刪除已證明整合的任務 branches／worktrees，並 archive 正式 Review／Repair tasks。來源主機未進 Git 的 10 個檔案不在接收端控制範圍；含敏感資料 prototype 不可再跨機搬運，應在來源主機輪替祕密後安全處理。
