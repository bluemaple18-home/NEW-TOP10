# YUANTA-WIN-AUTOMATION-01 Secure Package Comparison

## Intake evidence

- Encrypted package SHA-256: `7273e1bfa5eb7fe39570967704d582ba81e3f31875359ffe702a4a94f1b55d53`.
- Package SHA matches the handoff receipt.
- Reverse decryption, ZIP listing and every entry in `MANIFEST.sha256`: PASS.
- Decrypted content was inspected only in an isolated temporary directory.
- No credential value, certificate content, installer content or local absolute path was copied into Git, logs or this evidence.

## Legacy-to-safe behavior mapping

| Legacy behavior | Safe replacement | Disposition |
| --- | --- | --- |
| CMD opens a Yuanta public page | `Open-YuantaPublicPage.ps1` | HTTPS and `yuanta.com.tw` host allowlist; dry-run by default |
| CMD copies installer/PFX/ZIP to a fixed Public Desktop and launches setup | `Prepare-YuantaWorkspace.ps1` | Configurable workspace, validated extensions, collision guard, explicit `-Execute`/`-LaunchInstaller` |
| VBS activates a fixed PID/window and types account/PIN with SendKeys | `Invoke-YuantaLogin.ps1` | Unique process/title lookup, UI Automation IDs, runtime `PSCredential`, no fixed PID or SendKeys |
| CMD/PowerShell captures the primary screen to a fixed path | `Capture-YuantaDiagnostic.ps1` | Explicit process/title/handle, single-window surface, overlap/dialog/multi-monitor fail-closed guards |
| Prototype imports PFX using a stored password | Interactive Windows certificate wizard | Automatic import intentionally removed; PFX password never enters script/process arguments/logs |

The comparison found no missing required repo-side behavior. Unsafe implementation details are intentionally not preserved.

## Review findings

No blocking repo-side finding was found.

- `secrets_exposure`: legacy scripts contain credential-like literals; values were not displayed or copied. The repository replacement contains no literal value.
- `hardcoded_local_path`: present only in legacy scripts; absent from repository helpers.
- `installer_side_effects`: legacy installer is a Windows PE executable and was not launched.
- `permission_audit`: PFX/ZIP were not imported or expanded beyond package integrity inspection.
- `runtime_boundary`: repository helpers remain dry-run-first and require `-Execute` for local actions.

## Fresh verification

- `scripts/verify_yuanta_windows_helpers.py`: `YUANTA_WINDOWS_HELPERS_PASS`.
- Python compilation: PASS.
- Tracked secret/binary/prototype scan: no prohibited tracked file.
- Forbidden-pattern grep: documentation/verifier pattern names only; no implementation hit.
- `git diff --check`: PASS.

## Remaining live boundary

- PowerShell parser: `NOT_RUN_NON_WINDOWS_STATIC_ENV` (`pwsh` unavailable on this host).
- Windows Authenticode, UI Automation IDs, failure-path UIA tests and screenshot geometry: `NOT_RUN_REQUIRES_WINDOWS`.
- PFX import and real login: `NOT_RUN_REQUIRES_EXPLICIT_PER_EXECUTION_AUTHORIZATION`.
- Trading/order submission remains forbidden and outside this task.

`external_tool_gate`:

```text
tool/service: local OpenSSL/ZIP/static verifier; Yuanta external service not contacted
operation_level: read_only / dry_run
connection_status: no external connection attempted
schema_checked: package manifest and repository helper contract checked
confirmation_required: required before any real certificate import or login
execution_status: static comparison PASS; Windows live NOT_RUN
remaining_risk: Windows-only runtime behavior and credential rotation
```
