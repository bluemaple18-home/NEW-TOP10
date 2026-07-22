# REVIEW-YUANTA-WIN-AUTOMATION-01 — Re-review 01

- reviewed SHA：`6c2d0ceaed976701d2c4b0da0a6b619926d0cb01`
- branch：`codex/yuanta-win-automation-01-repair-1`
- repair parent：`1cd00f5`
- original NO_GO：`f9b7503`
- original candidate：`d765cb5`
- verdict：`REVIEW_GO`
- scope：只核對 Repair 1 的三個 P1 disposition；未修改 implementation
- safety boundary：未執行真實登入、憑證匯入、外部交易或截圖；未下載或使用外部 runtime

## Ancestry / scope

Candidate 已在指定 branch，且 `6c2d0ce` 的 parent 為 `1cd00f5`；`f9b7503` 與 `d765cb5` 均為 ancestors。Repair diff 只涉及 Repair card allowlist 內的五個檔案：

- `tools/yuanta_windows/Capture-YuantaDiagnostic.ps1`
- `tools/yuanta_windows/Invoke-YuantaLogin.ps1`
- `tools/yuanta_windows/README.md`
- `scripts/verify_yuanta_windows_helpers.py`
- `docs/evidence/REPAIR-YUANTA-WIN-AUTOMATION-01-01/repair.md`

未發現 PFX/P12、installer binary、ZIP、PNG、runtime log 或 credential literal。

## Reproducible verification

```text
/Users/mattkuo/TOP10new/.venv/bin/python -m py_compile scripts/verify_yuanta_windows_helpers.py
PASS (exit 0)

/Users/mattkuo/TOP10new/.venv/bin/python scripts/verify_yuanta_windows_helpers.py
YUANTA_WINDOWS_HELPERS_PASS

git grep -n -E '(password|pin|account|pfx)' -- tools/yuanta_windows scripts/verify_yuanta_windows_helpers.py
Only variable names, guarded environment names, secure API/documentation and verifier patterns;
no literal credential value found.

git diff --check 1cd00f5 6c2d0ceaed976701d2c4b0da0a6b619926d0cb01
PASS (exit 0)
```

Verifier result also records:

- all new env/screenshot source-level boundary checks：`true`
- PowerShell parser：`NOT_RUN_NON_WINDOWS_STATIC_ENV`
- Windows live verification：`NOT_RUN_REQUIRES_WINDOWS_CREDENTIALS_AND_EXPLICIT_AUTHORIZATION`
- UIA failure-path and screenshot boundary live tests：`NOT_RUN`

The NOT_RUN states are accurately reported and are not treated as live PASS.

## P1 disposition

### P1-1 Environment fallback lifecycle — CLOSED

`tools/yuanta_windows/Invoke-YuantaLogin.ps1:24-49` now reads both process variables inside `try`, rejects partial input, and attempts to clear both names in `finally` on success, conversion failure, partial-input failure, and other exceptions. Cleanup errors are collected and cause the helper to throw rather than continue. Account/PIN values and the temporary `SecureString` reference are released in the cleanup path. The verifier asserts the `finally`, partial-input and cleanup-failure guards.

### P1-2 UIA PIN plaintext lifecycle honesty — CLOSED WITH DOCUMENTED LIMIT

`tools/yuanta_windows/Invoke-YuantaLogin.ps1:82-110` keeps the BSTR zero-free operation in `finally`, releases the plaintext reference and UIA references on both success and failure, and no longer releases the plaintext only on the success path. The implementation and README explicitly state that `ValuePattern.SetValue(string)` necessarily creates an immutable managed string and therefore cannot promise memory zeroization. The README includes a Windows failure-path test plan for a throwing `SetValue`; no false zeroization claim remains. This is an honest residual platform limitation, not an undisclosed secret-lifecycle defect.

### P1-3 Screenshot privacy fail-closed boundary — CLOSED

`tools/yuanta_windows/Capture-YuantaDiagnostic.ps1:3-86` removes full-primary-screen capture. Execute mode now requires an explicit acknowledgement plus process name, title pattern, and window handle; it validates the handle, process/title identity, visibility, unique visible top-level window, ownership, positive bounds, single-monitor containment, and overlap with every other visible top-level window. Owned/dialog windows, multiple windows, another visible overlapping surface, and cross-monitor surfaces throw before capture. The verifier asserts each boundary and that `PrimaryScreen`/full-screen capture is absent. The target is captured only after these checks.

## Residual risks / verification gap

- Windows PowerShell parser, UI Automation failure-path test, and screenshot boundary live test remain unexecuted because this host lacks Windows/UIA runtime and the required credentials/authorization. The README and verifier preserve this as NOT_RUN.
- The non-sensitive target designation still requires the user’s explicit acknowledgement; it is paired with structural window/process/handle/geometry guards and is not presented as an automatic classification.
- Real login, certificate import, and external trading remain outside this review and require separate per-execution authorization.

## Final decision

`REVIEW_GO`. All three original P1 findings have a concrete, source-verifiable disposition; no new blocking correctness or security finding was found in Repair 1. This verdict is for the experimental/static boundary only and does not upgrade the unverified Windows live state.
