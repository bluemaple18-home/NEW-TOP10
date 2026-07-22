[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidatePattern('^[A-Za-z0-9_.-]+$')][string]$ProcessName,
    [string]$WindowTitlePattern = '.*',
    [Parameter(Mandatory)][ValidatePattern('^[A-Za-z0-9_.:-]+$')][string]$AccountAutomationId,
    [Parameter(Mandatory)][ValidatePattern('^[A-Za-z0-9_.:-]+$')][string]$PinAutomationId,
    [ValidatePattern('^[A-Za-z0-9_.:-]+$')][string]$LoginAutomationId,
    [PSCredential]$Credential,
    [switch]$AllowEnvironmentFallback,
    [switch]$Execute
)

$ErrorActionPreference = 'Stop'

if (-not $Execute) {
    [pscustomobject]@{ mode = 'dry-run'; action = 'ui-login'; process = $ProcessName; credential_source = 'secure-runtime-input' } | ConvertTo-Json -Compress
    return
}

if (-not $IsWindows -and $PSVersionTable.PSEdition -eq 'Core') {
    throw 'UI Automation 登入只支援 Windows。'
}

if ($null -eq $Credential -and $AllowEnvironmentFallback) {
    $accountValue = $null
    $pinValue = $null
    try {
        $accountValue = [Environment]::GetEnvironmentVariable('YUANTA_ACCOUNT', 'Process')
        $pinValue = [Environment]::GetEnvironmentVariable('YUANTA_PIN', 'Process')
        if ([string]::IsNullOrEmpty($accountValue) -or [string]::IsNullOrEmpty($pinValue)) {
            if ($accountValue -or $pinValue) { throw '環境變數 fallback 必須同時提供帳號與 PIN；已拒絕部分輸入。' }
        }
        else {
            $securePin = ConvertTo-SecureString $pinValue -AsPlainText -Force
            $Credential = [PSCredential]::new($accountValue, $securePin)
            $securePin = $null
        }
    }
    finally {
        $cleanupErrors = [System.Collections.Generic.List[object]]::new()
        foreach ($environmentName in @('YUANTA_ACCOUNT', 'YUANTA_PIN')) {
            try { [Environment]::SetEnvironmentVariable($environmentName, $null, 'Process') }
            catch { $cleanupErrors.Add($_.Exception) }
        }
        $accountValue = $null
        $pinValue = $null
        $securePin = $null
        if ($cleanupErrors.Count -gt 0) { throw '環境變數 fallback 清除失敗；已拒絕繼續執行。' }
    }
}
if ($null -eq $Credential) {
    $Credential = Get-Credential -Message '輸入本次 API 測試登入資料；內容不會寫入檔案或輸出。'
}
if ($null -eq $Credential) { throw '未取得登入資料。' }

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

$processes = @(Get-Process -Name $ProcessName -ErrorAction Stop | Where-Object {
    $_.MainWindowHandle -ne 0 -and $_.MainWindowTitle -match $WindowTitlePattern
})
if ($processes.Count -ne 1) {
    throw "必須精確找到一個符合條件的登入視窗，目前數量：$($processes.Count)"
}

$root = [System.Windows.Automation.AutomationElement]::FromHandle($processes[0].MainWindowHandle)
function Find-Control([string]$AutomationId) {
    $condition = [System.Windows.Automation.PropertyCondition]::new(
        [System.Windows.Automation.AutomationElement]::AutomationIdProperty,
        $AutomationId
    )
    $element = $root.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $condition)
    if ($null -eq $element) { throw "找不到指定 UI Automation control：$AutomationId" }
    return $element
}

$accountControl = Find-Control $AccountAutomationId
$pinControl = Find-Control $PinAutomationId
$accountPattern = $accountControl.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)
$pinPattern = $pinControl.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)

$secretPointer = [IntPtr]::Zero
$secretText = $null
$button = $null
$invokePattern = $null
try {
    $secretPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Credential.Password)
    $secretText = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($secretPointer)
    $accountPattern.SetValue($Credential.UserName)
    $pinPattern.SetValue($secretText)
    if ($LoginAutomationId) {
        $button = Find-Control $LoginAutomationId
        $invokePattern = $button.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
        $invokePattern.Invoke()
    }
}
finally {
    if ($secretPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($secretPointer)
    }
    # UIA ValuePattern.SetValue(string) 必須建立 managed string；此處只能縮短其存活，不能宣稱可零化該 string。
    $secretText = $null
    $accountPattern = $null
    $pinPattern = $null
    $accountControl = $null
    $pinControl = $null
    $button = $null
    $invokePattern = $null
    $Credential = $null
}

[pscustomobject]@{ status = 'submitted'; process = $ProcessName; secret_logged = $false } | ConvertTo-Json -Compress
