# REVIEW-YUANTA-WIN-AUTOMATION-01

- reviewed SHA：`d765cb5`
- review branch：`codex/review-yuanta-win-automation-01`
- verdict：`REVIEW_NO_GO`
- review scope：candidate `d765cb5^..d765cb5`；只審不修
- safety boundary：未執行真實登入、憑證匯入、外部交易或敏感截圖；未使用外部網路或下載 runtime

## Scope / allowlist

Candidate 變更共 10 個檔案，均符合 implementation card allowlist：

- `tools/yuanta_windows/**`
- `scripts/verify_yuanta_windows_helpers.py`
- `docs/tasks/2026-07-22_YUANTA-WIN-AUTOMATION-01_secure_windows_helpers.md`
- `docs/evidence/YUANTA-WIN-AUTOMATION-01/**`
- `.work/YUANTA-WIN-AUTOMATION-01/**`
- `.gitignore`

未發現 PFX、P12、EXE、MSI、ZIP、PNG、runtime log、prototype 或登入資料進入 candidate tree。review artifact 本身不屬於 implementation candidate。

## Reproducible verification

Commands were run against the checked-out reviewed SHA before this review artifact was added:

```text
/Users/mattkuo/TOP10new/.venv/bin/python -m py_compile scripts/verify_yuanta_windows_helpers.py
PASS (exit 0)

/Users/mattkuo/TOP10new/.venv/bin/python scripts/verify_yuanta_windows_helpers.py
YUANTA_WINDOWS_HELPERS_PASS output=artifacts/yuanta_windows_helpers_verification_latest.json

git grep -n -E '(password|pin|account|pfx)' -- tools/yuanta_windows scripts/verify_yuanta_windows_helpers.py
Only variable names, guarded environment-variable names, secure-input API references,
documentation, and verifier patterns; no literal credential value found.

git diff --check d765cb5^ d765cb5
PASS (exit 0)
```

PowerShell parser and Windows live verification were not run because this host has no PowerShell／Windows UI Automation runtime. This is recorded as NOT_RUN, not PASS. No real external write was attempted.

## Findings

### [P1] Environment fallback is not fail-safe on partial input or cleanup failure

Location: `tools/yuanta_windows/Invoke-YuantaLogin.ps1:24-33`

When only one of `YUANTA_ACCOUNT` / `YUANTA_PIN` exists, the `if ($accountValue -and $pinValue)` block is skipped and the present environment secret is never cleared. The same leak occurs if `ConvertTo-SecureString`, `PSCredential` construction, or either `SetEnvironmentVariable` call throws, because cleanup is not in a `finally` block. A process environment value can therefore remain available to child processes and later commands after the helper exits or fails, violating the task's required secret lifecycle.

Required fix: put environment reads and cleanup in a `try/finally`; clear both process variables on every fallback path, including incomplete input and exceptions, and fail closed without constructing a credential from partial input. Add a synthetic test for partial variables and an exception during conversion/cleanup.

### [P1] PIN is copied into an uncleared immutable managed string

Location: `tools/yuanta_windows/Invoke-YuantaLogin.ps1:66-72`

`PtrToStringBSTR` creates an immutable managed `System.String` containing the PIN. Setting `$secretText = $null` at line 72 only drops the reference; it does not overwrite the string's contents. The string can remain in the PowerShell/.NET heap until garbage collection, and an exception from either `SetValue` call can leave the value referenced until scope teardown. This contradicts the claimed secret lifecycle and is especially relevant because the code drives a GUI control that requires a plaintext value.

Required fix: redesign the UIA input boundary to minimize plaintext lifetime and document the unavoidable UIA string conversion; ensure all references are released in `finally`, avoid retaining the `PSCredential` longer than needed, and add a Windows-specific review/test plan proving failure-path cleanup. Do not claim complete in-memory zeroization where the UIA API requires `string`.

### [P1] Screenshot guard does not prove the screen is free of sensitive windows

Location: `tools/yuanta_windows/Capture-YuantaDiagnostic.ps1:22-37`

The execute path checks only visible top-level windows belonging to the single caller-supplied `$SensitiveProcessName`, then captures the entire primary screen. A password/certificate dialog owned by another process, a child/owned window not represented by that process's `MainWindowHandle`, a second instance, or a sensitive window on another monitor can remain visible and be written to the PNG. The acknowledgement switch is only a user assertion and does not make the check fail closed. This violates the requirement that screenshots avoid sensitive windows.

Required fix: make the safety contract explicit and fail closed for the whole capture surface (for example, enumerate all visible top-level/owned windows across all screens and require an allowlisted non-sensitive capture target, or require a user-selected/verified window region rather than full-screen capture). Keep acknowledgement as an additional confirmation, not the sole control, and add synthetic coverage for another-process dialogs and multi-monitor cases.

## Boundary checks

- Dry-run／`-Execute`: all four helpers gate side effects behind `-Execute`; login, installer launch, public-page launch, and screenshot were not executed.
- Windows-only: PowerShell Core on non-Windows is rejected by the explicit guard; Windows live behavior remains unverified on this host.
- Process/window/UIA: process name plus title pattern and exactly-one-window check are dynamic; controls use UI Automation IDs and Value/Invoke patterns; no fixed PID or `SendKeys` found.
- PFX: `Prepare-YuantaWorkspace.ps1` only validates and copies `.pfx`/`.p12`; no certutil/import call or plaintext password argument found.
- Secret output: JSON output contains status/metadata only; no credential fields are serialized. The two lifecycle findings above remain blockers despite this.
- Portable paths: no hardcoded user/PID/Downloads/Public Desktop path found; paths are parameters.
- README: documents experimental status, platforms, parameters, dry-run, rollback, and that Windows live verification is not complete.

## Final decision

`REVIEW_NO_GO`. The candidate must address all three P1 findings and add targeted regression/synthetic evidence before an independent reviewer can issue `REVIEW_GO`. No implementation files were changed by this review.
