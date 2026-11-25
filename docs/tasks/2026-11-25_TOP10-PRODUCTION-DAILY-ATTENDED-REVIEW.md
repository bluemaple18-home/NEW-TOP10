# 正式 runtime、每日報牌與研究接收收尾

- 目標：沿既有入口部署已驗證版本、核對 daily 排程及研究 consumer；不建立新服務或無人 review 排程。
- 授權：Owner 已同意恢復既有 AppleScript，並明示授權停損後一輪 30 分鐘有界 activation 修補；最新回覆為「切好帳號了，繼續」。activation 修補完成後凍結；後續只處理另已授權的 AppleScript 畫面相容性與交付驗證。
- 契約：同版本容量安全、正負路徑及回退證據；daily 有實際送達回執；review 原契約接受；研究 consumer 實際讀取且來源雜湊相符。結果未知不重送。
- activation：同 root daily 切版候選完成；181 案通過，兩名獨立盲審 GO（36／15 案）。非目標 preflight hold 與無人 review 停用狀態須原樣保留。實際部署狀態以外接 activation receipt 為準。
- daily：子程序暫存接線修正，4 項回歸通過；相同來源完整 features 快照兩週期通過，原 RSS／swap 上限未放寬，暫存與 marker 均清理。初期覆蓋拒絕與 swap 停損證據保留。
- review：恢復原 host AppleScript shell；每次先驗實際帳號、對話 URL 與標題，送出前逐字驗草稿；未知送出只收不重送。新版畫面沿語意說話者標題回收，僅去除已知介面尾巴；嚴格 normalizer 不變。
- 實測：家維 郭 Plus 的 GPT 原對話、bluemaple17 的 Gemini PROD 均成功 probe／collect；兩份 11/23 JSON 與原驗收結果逐欄相同，皆 ACCEPTED。此輪未送 provider 訊息。32 項回歸及 11 項子測試通過。
- 排程：原 daily 已 enabled／loaded，平日 17:30；不可稱本輪才恢復。無人 review 保持 disabled／unloaded；preflight 的 RECOVERY_READINESS_OWNER_HOLD 保留。daily 不以人工 Chrome 授權為前提。
- 已知限制：原測試 second_result=70 在 72 次重跑未重現，原因未證明；已保留診斷，不宣稱修復。Chrome 的 host AppleScript 與 CDP 授權不同；本次 host probe／collect 無需每次按 CDP 允許，但不保證瀏覽器升級或系統權限重設後永不需重新授權。
- 狀態：ACCEPTED_SOURCE_PENDING_RUNTIME_ACTIVATION；程式驗證完成，實際部署、runtime research consumer 與排程 readback 仍須同一輪 receipt 證明，不能提前結案。
- 證據：既有外接 `TOP10-Checks/EXTERNAL-REVIEW-PATH-RESTORE-20261124/formal-review/production-daily-closeout-20261125` 及 `TOP10-STORAGE-LIFECYCLE-20261118/evidence`；失敗原件與回復備份保留，不另建 ledger。
