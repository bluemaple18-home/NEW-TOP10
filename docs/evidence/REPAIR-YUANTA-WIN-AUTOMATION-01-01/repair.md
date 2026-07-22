# REPAIR-YUANTA-WIN-AUTOMATION-01-01 Evidence

- base／repair 起始 HEAD：`1cd00f5`
- required ancestors：`f9b7503`、`d765cb5`（已核對）
- repair candidate：本 evidence 所在 candidate commit（SHA 於提交後回報）
- scope：三個 P1；未執行真實登入、憑證匯入、外部交易或截圖

## 修復內容

1. `Invoke-YuantaLogin.ps1` 將兩個 process environment secret 的讀取、conversion、Credential 建立與雙變數清除包在 `try/finally`；部分輸入直接 fail closed，清除例外也拒絕繼續。UIA PIN plaintext 只在必要邊界短暫存在，`finally` 釋放 BSTR 與所有 references，並明確記錄 `ValuePattern.SetValue(string)` 無法保證 managed string 零化。
2. `Capture-YuantaDiagnostic.ps1` 移除 full-primary-screen capture，改為使用者指定的 process/title/handle 單一 allowlisted window；owned/dialog、多重視窗、跨 monitor 與其他 visible window 重疊均 fail closed。
3. verifier 新增上述 source-level synthetic boundary checks，並輸出 Windows failure-path test plan 狀態。

## Verification

- `<repo-root>/.venv/bin/python -m py_compile scripts/verify_yuanta_windows_helpers.py` → PASS
- `<repo-root>/.venv/bin/python scripts/verify_yuanta_windows_helpers.py` → `YUANTA_WINDOWS_HELPERS_PASS`
- `git grep -n -E '(password|pin|account|pfx)' -- tools/yuanta_windows scripts/verify_yuanta_windows_helpers.py` → 僅命中變數名、guarded environment names、安全 API／文件與 verifier pattern；未發現 literal credential value
- `git diff --check` → PASS
- `git diff --name-only 1cd00f5..HEAD` → 僅檢查既有變更；repair candidate 變更檔案須符合 repair card allowlist

## 未執行項

- PowerShell parser：`NOT_RUN_NON_WINDOWS_STATIC_ENV`（本機無 `pwsh`）
- Windows UIA failure-path live test：`NOT_RUN_REQUIRES_WINDOWS_CREDENTIALS_AND_EXPLICIT_AUTHORIZATION`
- Windows screenshot boundary live test：`NOT_RUN_REQUIRES_WINDOWS_AND_EXPLICIT_AUTHORIZATION`

上述 NOT_RUN 不等於 PASS；可在 Windows 以隔離測試視窗依 README 的 failure-path test plan 重跑。
