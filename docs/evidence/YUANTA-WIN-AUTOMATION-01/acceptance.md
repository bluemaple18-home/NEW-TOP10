# YUANTA-WIN-AUTOMATION-01 Mainline Acceptance

- base：`2aadec4`
- original candidate：`d765cb5`
- original review：`REVIEW_NO_GO`／`f9b7503`
- repair candidate：`6c2d0ceaed976701d2c4b0da0a6b619926d0cb01`
- final reviewed candidate：`6c2d0ceaed976701d2c4b0da0a6b619926d0cb01`
- final review：`REVIEW_GO`／`5505a7e`
- integrated content SHA（含完整 Review／Repair evidence）：`af2c108`
- acceptance：`PASS_EXPERIMENTAL_STATIC_BOUNDARY`

## Mainline rerun

- 專案既有 `.venv` py_compile：PASS
- `scripts/verify_yuanta_windows_helpers.py`：PASS（`YUANTA_WINDOWS_HELPERS_PASS`）
- credential／PIN／account／PFX grep 人工判讀：僅安全名稱、文件與 verifier pattern，沒有真實值
- tracked binary／PFX／screenshot／prototype scan：無命中
- `git diff --check origin/main...HEAD`：PASS

## 未驗證與禁止宣稱

- PowerShell parser：`NOT_RUN_NON_WINDOWS_STATIC_ENV`
- Windows UI Automation／failure paths：`NOT_RUN`
- Windows screenshot surface：`NOT_RUN`
- 真實憑證匯入、登入、外部交易：`NOT_RUN_REQUIRES_WINDOWS_CREDENTIALS_AND_EXPLICIT_AUTHORIZATION`

因此本次只接受安全化、可攜、dry-run-first 的 experimental helpers 進主線，不宣稱 Windows live acceptance。真實使用前仍需在隔離 Windows 環境依 README 驗證，且每次外部 write 需使用者明確授權。

## Secure package post-acceptance comparison

- Encrypted package and internal manifest integrity: PASS.
- Six legacy prototypes were compared by redacted behavior only; no secret value was displayed or copied.
- Required behavior is fully mapped to the four accepted safe helpers; no repo-side implementation gap was found.
- Fresh static verifier: PASS.
- Detailed evidence: `docs/evidence/YUANTA-WIN-AUTOMATION-01/secure-package-comparison.md`.
