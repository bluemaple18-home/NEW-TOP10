# TOP10 測試工具修復與外接搬遷

- objective：先修測試工具，再建立外接 TOP10 副本與路徑接線，最後於外接跑四組回歸及兩輪 no-send。
- scope：本輪測試工具故障、既有 generic run 暫存隔離恢復、開發候選與隔離驗證搬到 VibeCode；內建原件保留回退。
- constraints：Production NO-GO；不清正式 Daily restart-denied、不修改已安裝 launchd、不發送、不部署；保留所有既有未提交修改。測試隔離只可憑實際停止證據恢復，不偽造歷史 session 或繞過容量／掛載檢查。
- acceptance：小範圍測試工具回歸；外接 copy manifest／source digest／卷 UUID 與路徑驗證；最終外接四組回歸；兩個獨立完整 guard no-send 週期；內建回退與正式停跑狀態未變。
- status：SAFE_CLOSEOUT_WITH_VERIFIED_EXTERNAL_STAGING；未完成全目標。pytest 局部修補6/6與兩名盲審通過；外接副本逐檔校驗完成，兩邊 unknown 保留。停止證明候選已拒絕；完整四組與兩輪 no-send 均未啟動。
- evidence refs：docs/evidence/TOP10-DAILY-NATIVE-20261021/；後續搬遷證據存 docs/evidence/TOP10-EXTERNAL-MIGRATION-20261021/。
- decision：測試失敗起因含 pytest 暫存連結累積與 lifecycle 的 fork-observed 保守拒絕。既有 recover 僅支援 browser/review，必須先辨識可用的真實停止證據，再做最小工具修復。
- evidence：`tool-install-receipt.json` 記錄既有 recover 的 opt-in generic 重啟恢復修補；新增 37 項測試通過，原生 ps 既有恢復回歸 29 項通過。原 shared 工具與文件存於 `tool-before/`；這些不是 TOP10 四組完整回歸。
- evidence：`pre-reboot/boot-proof.json` 保存現場 boot UUID／時間及原始 root／manifest／marker 身分；`same-boot-negative-check.json` 證明同一開機階段拒絕恢復，測試與正式 marker、正式 plist 未變。
- decision：原生執行權限已可用；現存 blocker 是舊 pytest 未保存完整後代程序停止證據。真正重開機可證明舊 kernel 程序已停止，準備證據本身不能。
- handoff（已被取代的歷史決策）：先前曾要求重啟；Owner 隨後要求免重啟，因此本輪不要求或執行重啟。以 RESUME.md 與 safe-closeout-receipt.json 為目前狀態。
- acceptance gap：重啟恢復候選不等於整個測試入口已修好；仍須解決 pytest 暫存連結保留與正常 fork 的生命週期契約，不能僅移除完整停止證明旗標。工具確認後才建立外接副本，所有最終產品驗證只在外接執行。

- objective（免重啟修復）：沿既有 lifecycle 加入可反證的原生 original-parent closure，核對 direct child 已 reap／PID 不存在，完整目前程序的 original-parent 鏈均可追溯到 root 建立前程序或 kernel launchd；有缺鏈、短讀、權限缺口、PID 重用、roster 漂移則拒絕，不按名稱 kill。
- evidence：`native-parent-closure-research.json` 原生研究觀測 615 程序，前後 PID 集合一致、查詢錯誤 0、未解祖先鏈 0；目前僅 RESEARCH_ONLY，不是清理授權或停止證明。Apple XNU `p_puniqueid` 保留 fork/spawn 時原父身分，不因 reparent 改變。
- constraints（免重啟）：舊 run 的 direct child 已 wait 證據必須引用當時 `native-regression.log`、原 command_run/run_child 程式與 root/guard receipts；新證據不得冒稱當時原生已記錄不存在的 uniqueid。新 run 沿原 process.wait 接縫取得原生證據；不移除完整停止旗標、不擴 symlink 上限、不新增常駐 supervisor。
- acceptance（免重啟）：真正 double-fork／setsid 且原父已退出的存活子程序須拒絕；實際待其退出後才通過。故障／收據／marker 清理仍經兩名盲審後執行；Production 永遠 NO-GO。

- decision（盲審後）：STOP_LOCAL_CONTINUATION → ABANDON_PATH。原父 closure 被原生 reparent→exec 反例推翻；candidate 禁止安裝或 execute。不是 helper SHA 缺口；增加 census 次數不能修復。舊 root 與 unknown isolation 維持。
- evidence：兩名盲審均拒絕。其他具體缺口含 metadata 在第二次 census 中變更仍刪除、marker unlink 後 ENOSPC／SIGTERM、pytest teardown fail 證據遺失。native-recovery-dry-run/result.json 僅記歷史觀測，不構成清理授權。
- decision（局部工具）：pytest 改 retention=all，等完整 teardown report 全通過才回收該 fixture；4 項 harness 回歸通過，涵蓋真實連結累積 RED→20case GREEN、本體失敗、teardown失敗、foreign links。原生停止證明方案未通過，不宣稱工具整體完成。
- evidence（容量）：native-capacity-current.json 原生 Foundation 內建 admission 33,960,264,896 bytes；外接 74,724,093,833 bytes，卷 UUID 符合。只讀量測，不代表生產准入。
- evidence（最後收尾）：safe-closeout-receipt.json；外接永久副本 60,248 一般檔／4,646,511,747 bytes；31 個 venv 文字入口路徑已替換。內建原件不變，舊 unknown root／marker 保留，外接繼承 unknown 維持拒絕。完整回歸 NOT_RUN、完整 no-send 0；Production NO-GO，正式 marker／plist SHA 未變，launchd not running。
