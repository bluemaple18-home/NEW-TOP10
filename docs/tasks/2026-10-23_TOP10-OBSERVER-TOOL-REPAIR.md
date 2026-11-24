# TOP10 macOS 程序觀測工具修復

- objective：消除原生 ps 的 setuid 權限造成觀測中止，固定回歸政策；不把不足的停止資訊轉成成功。
- scope：ai-core/scripts/tmp_artifact_lifecycle.py 與對應純記憶體單元測試；TOP10 evidence 中的固定測試啟動器。
- constraints：Production NO-GO；不重開機、不清除既有開發或正式隔離、不部署、不發送；兩個 repo 的未知 root 保留。不執行會產生受管 root 的完整測試。
- hypothesis：完整 BSD 查詢因 setuid ps 被拒；僅非 leader 的明確權限失敗改用短資訊核對成員，但一律保持未收斂，可避免誤中止且不誤放行。
- acceptance：新增反例先 RED 後 GREEN；現有純記憶體程序控制測試通過；兩位獨立 reviewer 判定無誤收束／早 reap；正式 marker/plist 與原隔離內容不變。
- status：BOUNDED_FIX_VERIFIED；patch 已受控套用，17項純記憶體檢查與原生 ps RED→GREEN，兩位獨立 reviewer 通過；舊隔離仍 BLOCKED，完整搬遷／驗證未完成。CodeGraph 工具本輪未提供，沿用前輪查詢並以 rg 定位。
- evidence：docs/evidence/TOP10-INTEGRATED-CANDIDATE-20261022/NON-REBOOT-INVESTIGATION.md；darwin-observer-fix.patch；後續修復 receipt。
- limitation：修復不補回舊事故的歷史程序譜系；完整回歸及兩輪 no-send 尚未通過。
