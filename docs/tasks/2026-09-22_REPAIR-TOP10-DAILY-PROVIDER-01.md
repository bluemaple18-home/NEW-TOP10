# REPAIR-TOP10-DAILY-PROVIDER-01

## 2026-09-27 主線重查更正

下列舊 handoff 的「待 ai-core 授權」已過期；Repair 2 已核准，ES／Apple 路線已關閉，不再詢問成本或 Apple 帳號。本地候選六檔 digest 仍與 9/22 相同，固定 runtime 未部署。最新[全鏈報告](../evidence/INVESTIGATE-TOP10-AUTOMATION-END-TO-END-01/recheck-report-2026-09-26.md)新增 monitor 9/26 容量停損與 provider 9/25、26 未修 runtime probe PASS；Daily 仍保留原 marker。後續由 TOP10 Mainline 重新鎖定容量／實際工作負載範圍；完整隔離 ETL 的安全收束仍未證明，不能以本地候選或取消 ES 宣告恢復。

以下為 9/22 原始修補契約與交付紀錄。

- objective：處理排查卡定位的 Daily ETL 記憶體尖峰與 Gemini probe JavaScript 逾時，交付可重現測試及安全恢復候選。
- authority：Owner 於 2026-09-22 提供完整排查結果後要求「解決」，授權本機定位、修復及隔離測試；既有外送／production activation 邊界保留，完成具體候選後裁決。
- scope：Daily 指標計算及必要測試；Gemini probe／adapter 及必要測試；既有容量停損契約保持；不改訊號語意、排名權重、模型或 Fog。
- constraints：保留未追蹤研究成果；shared checkout sequential single writer。隔離測試不連外、不呼叫真 Chrome、不送件、不執行 production daily。禁止清 marker、改 installed plist、重啟 Chrome、enable external-review、push。
- acceptance：先執行能抓到目標缺陷的 RED；最小修補後 GREEN，數值等價、目標回歸與 diff check 通過；區分 local candidate 與尚未實測的主機／provider 原因，不宣稱自然排程已恢復。
- evidence：`docs/evidence/INVESTIGATE-TOP10-AUTOMATION-END-TO-END-01/report.md`；後續測試與裁決記於本卡。
- status：LOCAL_CANDIDATE_COMPLETE；RECOVERY_BLOCKED_SCOPE_APPROVAL。Daily local review GO；Gemini 原生編譯已補測，整組測試／複審結果見 evidence。
- decision：不啟動不具安全收束證據的巢狀試跑。共用 lifecycle 1 秒收束與 TOP10 child 分離 session／最長 10 秒收束不相容，須另取 ai-core 最小修復授權；未修改 production 或清 marker。
- evidence：`docs/evidence/REPAIR-TOP10-DAILY-PROVIDER-01/report.md`。
- handoff：Owner 決定是否擴及 ai-core 的有界停止／清理修復；完成 RED/GREEN 與獨立驗證後，再跑兩輪完整 Daily。之後才裁決 exact runtime rollout／provider 實機／自然驗收；external-send 仍需明確授權。
