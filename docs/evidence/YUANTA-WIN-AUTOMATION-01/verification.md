# YUANTA-WIN-AUTOMATION-01 Verification

- base：`2aadec4`
- static／synthetic：`PASS`
- Windows live：`NOT_RUN_REQUIRES_WINDOWS_CREDENTIALS_AND_EXPLICIT_AUTHORIZATION`
- 真實登入、憑證匯入、外部交易：均未執行

安全版本只接受 runtime `PSCredential`／互動提示；環境變數 fallback 必須明示，且不得回顯。PFX 僅複製到可設定 workspace，憑證匯入保留給 Windows 互動精靈。

## Commands

- 專案既有 `.venv`：`python -m py_compile scripts/verify_yuanta_windows_helpers.py` → PASS
- `python scripts/verify_yuanta_windows_helpers.py` → `YUANTA_WINDOWS_HELPERS_PASS`
- credential／PID／使用者路徑／`SendKeys`／`certutil` password argument 人工判讀 → 無真實祕密或危險執行碼
- `git diff --check` → PASS

目前主機沒有 PowerShell／Windows UI Automation runtime，因此 parser/live checks 誠實記錄為 `NOT_RUN`；這不等於 live PASS。
