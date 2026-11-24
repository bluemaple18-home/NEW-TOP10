# TOP10 發布保護與已驗證修補整合

- objective：將已安裝 3b6ff80 正式發布保護整合至目前工作樹修補，完成回歸與同版兩輪最新行情 no-send。
- scope：scripts 的發布／鎖／sender／事件／rollup 相依鏈與對應測試；其餘現有容量、隔離、快取、市場參考修補保留。完整程式集合比較 927 路徑、34 差異見 docs/evidence/TOP10-INTEGRATED-CANDIDATE-20261022/full-code-comparison.json。
- constraints：Production NO-GO；不解除 denied、不部署、不啟動 launchd、不外送、不改正式 runtime 或外接副本；共享工作樹 sequential single writer；既有修改先保留雜湊，禁止整樹覆蓋。standard bounded integration，無可用 Terra lane，native worker 繼承當前模型不覆寫設定。
- acceptance：已確認送達與未決收據不可重送／覆寫，無有效鎖不得進入發布；四組回歸＋發布相依測試 PASS；最終來源固定、兩輪完整最新行情 no-send PASS、容量 PASS、正式 marker/plist 不變。
- status／evidence：BLOCKED_TOOL_ISOLATION；18檔移植完成、鎖反例RED→GREEN、兩位唯讀review通過；主線錯用通用tmp政策致回歸中斷（34 passed／1 failed），留下unknown隔離；兩輪no-send為0/2。完整證據及正確續跑政策見 docs/evidence/TOP10-INTEGRATED-CANDIDATE-20261022/RESULT.md 與 RESUME.md。未部署或解除正式marker。
