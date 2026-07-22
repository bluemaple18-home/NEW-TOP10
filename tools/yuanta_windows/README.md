# 元大 Windows 安全輔助工具（Experimental）

這組工具用來取代曾含明文登入資料、固定 PID 與單機路徑的 prototype。它們只支援 Windows PowerShell 5.1+／PowerShell 7，預設不做外部寫入；所有會開啟程式、複製檔案、操作登入視窗或截圖的動作都必須明示 `-Execute`。

## 安全邊界

- Git、參數、command line 與輸出不可放帳號、PIN 或 PFX 密碼。
- 登入預設使用 `Get-Credential` 的安全互動提示；也可由呼叫端傳入 `PSCredential`（例如由企業既有 Credential Manager wrapper 取得）。
- 環境變數只在明示 `-AllowEnvironmentFallback` 時讀取 `YUANTA_ACCOUNT`／`YUANTA_PIN`，不會回顯內容；完整輸入、部分輸入與例外路徑都會嘗試在 `finally` 清除兩者，清除失敗即停止。
- PFX 只可複製到指定 workspace。本工具不把 PFX 密碼傳給 `certutil`，也不自動匯入憑證；請在 Windows 憑證匯入精靈內互動輸入密碼。
- 登入操作使用 process name、window title 與 UI Automation ID 定位，不接受固定 PID，也不使用 `SendKeys`。UIA `ValuePattern.SetValue(string)` 必須短暫建立 managed plaintext string；腳本在 `finally` 釋放所有 references，但不能保證該 immutable string 的記憶體零化。
- 截圖工具只擷取使用者明確指定、以 process/title/handle 唯一驗證且確認為非敏感的單一 window；owned/dialog、多重視窗、其他視窗重疊與跨 monitor surface 都 fail closed，不擷取整個 primary screen。
- 真實憑證匯入、登入與任何交易／下單都不在自動驗收範圍，執行前必須取得使用者當次明確授權。

## Dry run

```powershell
.\Open-YuantaPublicPage.ps1
.\Prepare-YuantaWorkspace.ps1 -Workspace C:\SafeWorkspace -InstallerPath D:\Installers\setup.exe
.\Invoke-YuantaLogin.ps1 -ProcessName ApiTest -AccountAutomationId AccountBox -PinAutomationId PinBox
.\Capture-YuantaDiagnostic.ps1 -OutputPath C:\SafeWorkspace\diagnostic.png -CaptureProcessName ApiTest -CaptureWindowTitlePattern 'API.*Test' -CaptureWindowHandle <HANDLE_FROM_INSPECT> -AcknowledgeNonSensitiveWindow
```

沒有 `-Execute` 時只驗證參數並輸出不含敏感值的計畫。

## 明示執行

```powershell
.\Open-YuantaPublicPage.ps1 -Execute
.\Prepare-YuantaWorkspace.ps1 -Workspace C:\SafeWorkspace -InstallerPath D:\Installers\setup.exe -CertificatePath D:\Certificates\client.pfx -Execute
```

接著由使用者雙擊 workspace 內的 PFX，在 Windows 憑證匯入精靈互動輸入密碼。確認授權後，登入可用：

```powershell
$credential = Get-Credential -Message '輸入本次元大 API 測試登入資料'
.\Invoke-YuantaLogin.ps1 -ProcessName ApiTest -WindowTitlePattern 'API.*Test' -AccountAutomationId AccountBox -PinAutomationId PinBox -LoginAutomationId LoginButton -Credential $credential -Execute
```

Automation ID 必須先用 Windows Inspect 工具確認，錯誤時腳本會 fail closed。禁止把帳號或 PIN 寫進 `.ps1`、`.cmd`、fixture 或命令列。

## 診斷截圖

先關閉登入／憑證視窗，使用 Inspect 確認目標 handle、process 與 title，確認目標 window 非敏感且沒有 owned/dialog 或重疊視窗，再執行：

```powershell
.\Capture-YuantaDiagnostic.ps1 -OutputPath C:\SafeWorkspace\diagnostic.png -CaptureProcessName ApiTest -CaptureWindowTitlePattern 'API.*Test' -CaptureWindowHandle <HANDLE_FROM_INSPECT> -AcknowledgeNonSensitiveWindow -Execute
```

Windows failure-path test plan：在隔離測試視窗中讓 `ValuePattern.SetValue` 對 PIN 欄位拋例外，確認 `finally` 仍執行 `ZeroFreeBSTR` 並釋放所有 managed references；另以第二 process dialog 覆蓋目標、同 process 開第二視窗，以及將目標跨 monitor 擺放，確認截圖命令各自 fail closed。這些測試需 Windows UI Automation runtime 與使用者當次明確授權，未在本機執行。

## Rollback

工具不修改系統安全政策，也不自動匯入憑證。回退時關閉啟動的瀏覽器／installer，刪除使用者指定 workspace 內的複本與診斷圖；若使用者已透過 Windows 精靈匯入憑證，請在 Certificate Manager 核對 thumbprint 後手動移除。

## 驗證限制

macOS／Linux 可執行 static verifier，但無法證明 Windows UI Automation ID、實際視窗流程或憑證精靈。正式 Windows live verification 命令與結果必須另行記錄，不得把 static PASS 寫成 live PASS。
