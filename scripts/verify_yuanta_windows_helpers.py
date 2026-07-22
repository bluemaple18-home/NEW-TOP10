#!/usr/bin/env python3
"""以跨平台 static/synthetic checks 驗證元大 Windows helper 的安全邊界。"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = PROJECT_ROOT / "tools" / "yuanta_windows"
ARTIFACT = PROJECT_ROOT / "artifacts" / "yuanta_windows_helpers_verification_latest.json"
EXPECTED = {
    "README.md",
    "Open-YuantaPublicPage.ps1",
    "Prepare-YuantaWorkspace.ps1",
    "Invoke-YuantaLogin.ps1",
    "Capture-YuantaDiagnostic.ps1",
}


def powershell_parse_checks(files: list[Path]) -> dict[str, bool | str]:
    executable = shutil.which("pwsh")
    if executable is None:
        return {"available": False, "status": "NOT_RUN_NON_WINDOWS_STATIC_ENV"}
    quoted = ",".join("'" + str(path).replace("'", "''") + "'" for path in files)
    command = (
        "$failed=$false; foreach($path in @(" + quoted + ")) {"
        "$tokens=$null;$errors=$null;"
        "[System.Management.Automation.Language.Parser]::ParseFile($path,[ref]$tokens,[ref]$errors)|Out-Null;"
        "if($errors.Count -gt 0){$failed=$true}}; if($failed){exit 1}"
    )
    completed = subprocess.run([executable, "-NoProfile", "-Command", command], check=False)
    return {"available": True, "status": "PASS" if completed.returncode == 0 else "FAIL"}


def main() -> int:
    files = sorted(TOOLS_ROOT.glob("*"))
    names = {path.name for path in files}
    scripts = sorted(TOOLS_ROOT.glob("*.ps1"))
    script_source = "\n".join(path.read_text(encoding="utf-8") for path in scripts)
    forbidden_patterns = {
        "hardcoded_windows_user_path": r"(?i)[A-Z]:\\Users\\[^\\\s]+",
        "hardcoded_posix_user_path": r"/(?:Users|home)/[^/\s]+",
        "public_desktop_or_downloads": r"(?i)(Public\\Desktop|\\Downloads\\)",
        "fixed_pid": r"(?i)(?:-Id|ProcessId\s*=)\s*\d{2,}",
        "sendkeys": r"(?i)SendKeys",
        "certutil_password_argument": r"(?is)certutil.{0,120}(?:-p|password)",
        "credential_literal_assignment": r"(?i)(?:password|pin|account)\s*=\s*['\"][^'\"]+['\"]",
    }
    forbidden_hits = {name: bool(re.search(pattern, script_source)) for name, pattern in forbidden_patterns.items()}
    readme = (TOOLS_ROOT / "README.md").read_text(encoding="utf-8") if (TOOLS_ROOT / "README.md").exists() else ""
    login = (TOOLS_ROOT / "Invoke-YuantaLogin.ps1").read_text(encoding="utf-8") if (TOOLS_ROOT / "Invoke-YuantaLogin.ps1").exists() else ""
    capture = (TOOLS_ROOT / "Capture-YuantaDiagnostic.ps1").read_text(encoding="utf-8") if (TOOLS_ROOT / "Capture-YuantaDiagnostic.ps1").exists() else ""
    prepare = (TOOLS_ROOT / "Prepare-YuantaWorkspace.ps1").read_text(encoding="utf-8") if (TOOLS_ROOT / "Prepare-YuantaWorkspace.ps1").exists() else ""
    checks = {
        "expected_files_present": EXPECTED <= names,
        "no_forbidden_static_patterns": not any(forbidden_hits.values()),
        "login_requires_explicit_execute": "[switch]$Execute" in login and "if (-not $Execute)" in login,
        "secure_runtime_input": "[PSCredential]$Credential" in login and "Get-Credential" in login,
        "environment_fallback_opt_in": "AllowEnvironmentFallback" in login,
        "environment_fallback_cleared_in_finally": "finally" in login and login.count("SetEnvironmentVariable($environmentName, $null, 'Process')") == 1,
        "environment_partial_input_fail_closed": "拒絕部分輸入" in login and "IsNullOrEmpty" in login,
        "environment_cleanup_failure_fail_closed": "cleanupErrors" in login and "清除失敗" in login,
        "no_sendkeys": "SendKeys" not in login,
        "dynamic_process_lookup": "Get-Process -Name $ProcessName" in login,
        "ui_automation_ids": "AutomationIdProperty" in login and "ValuePattern" in login,
        "secret_bstr_zeroed": "ZeroFreeBSTR" in login,
        "uia_plaintext_limit_honest": "不能宣稱可零化" in login and "$secretText = $null" in login,
        "certificate_not_imported": "certificate_imported = $false" in prepare and "certutil" not in prepare.lower(),
        "capture_requires_non_sensitive_allowlist": "AcknowledgeNonSensitiveWindow" in capture and "CaptureWindowHandle" in capture,
        "capture_verifies_process_title_handle": "ProcessId" in capture and "CaptureWindowTitlePattern" in capture and "CaptureProcessName" in capture,
        "capture_rejects_owned_windows": "owned/dialog" in capture and "Owner($handle)" in capture,
        "capture_rejects_multi_monitor": "AllScreens" in capture and "拒絕跨 monitor" in capture,
        "capture_rejects_overlapping_other_process_surface": "IntersectsWith" in capture and "其他 process/window" in capture,
        "capture_not_full_primary_screen": "PrimaryScreen" not in capture and "capture-surface" not in capture,
        "readme_documents_dry_run": "Dry run" in readme and "-Execute" in readme,
        "readme_documents_live_limit": "static PASS" in readme and "live PASS" in readme,
        "readme_documents_rollback": "Rollback" in readme,
    }
    parser = powershell_parse_checks(scripts)
    if parser["available"]:
        checks["powershell_parser"] = parser["status"] == "PASS"
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema_version": "yuanta-windows-helpers-verification.v1",
        "status": status,
        "checks": checks,
        "forbidden_hits": forbidden_hits,
        "powershell_parser": parser,
        "windows_live_verification": "NOT_RUN_REQUIRES_WINDOWS_CREDENTIALS_AND_EXPLICIT_AUTHORIZATION",
        "synthetic_boundary_coverage": {
            "partial_env_and_cleanup_exception": "SOURCE_ASSERTED_NON_WINDOWS",
            "uia_setvalue_failure_cleanup_plan": "WINDOWS_TEST_PLAN_ONLY",
            "other_process_dialog": "SOURCE_ASSERTED_NON_WINDOWS",
            "multi_monitor_surface": "SOURCE_ASSERTED_NON_WINDOWS",
        },
    }
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"YUANTA_WINDOWS_HELPERS_{status} output={ARTIFACT}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
