# Yuanta local prototype — redacted behavior inventory

## Source status

- 來源是交接端未提交的本機 prototype。
- 原檔沒有進入本 branch，因為含真實登入祕密與單機路徑。
- 本文件只保留接手所需的行為，不保留任何 credential value。

## Prototype behavior

1. 一個 CMD 開啟公開元大網頁。
2. 一個 CMD 從使用者 Downloads 複製 setup.exe、PFX、可選 ZIP 到 Public Desktop，接著匯入 PFX 並啟動 installer。
3. 兩個 VBS 以 window title 或固定 PID activate API 測試程式，再 SendKeys 填 account、PIN、Tab、Enter。
4. 一個 CMD 呼叫 PowerShell。
5. PowerShell 擷取 primary screen 並寫入固定路徑的 PNG。

## Problems to repair

- account 與 PIN 硬編碼。
- PFX 密碼硬編碼並可能出現在 command line/log。
- 固定 PID 不可靠。
- 使用者專屬來源與固定 Public Desktop target。
- screenshot 可能捕捉敏感畫面。
- 缺 dry-run、輸入驗證、失敗處理、secret scan 與 tests。

## Required replacement

依 docs/tasks/2026-07-22_YUANTA-WIN-AUTOMATION-01_secure_windows_helpers.md 從零重建安全版本。不要嘗試從 Git 尋找或恢復 redacted values。
