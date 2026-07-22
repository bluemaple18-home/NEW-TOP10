[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$OutputPath,
    [Parameter(Mandatory)][ValidatePattern('^[A-Za-z0-9_.-]+$')][string]$SensitiveProcessName,
    [switch]$AcknowledgeSensitiveContentCleared,
    [switch]$Execute
)

$ErrorActionPreference = 'Stop'

if (-not $Execute) {
    [pscustomobject]@{ mode = 'dry-run'; action = 'capture-diagnostic'; sensitive_content_required = 'cleared' } | ConvertTo-Json -Compress
    return
}
if (-not $AcknowledgeSensitiveContentCleared) {
    throw '截圖前必須明示 -AcknowledgeSensitiveContentCleared。'
}
if (-not $IsWindows -and $PSVersionTable.PSEdition -eq 'Core') {
    throw '診斷截圖只支援 Windows。'
}

$visibleSensitiveWindows = @(Get-Process -Name $SensitiveProcessName -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 })
if ($visibleSensitiveWindows.Count -gt 0) {
    throw '敏感應用程式仍有可見主視窗；請先最小化或關閉後再截圖。'
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bitmap = [System.Drawing.Bitmap]::new($bounds.Width, $bounds.Height)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
try {
    $graphics.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
    $target = [IO.Path]::GetFullPath($OutputPath)
    $targetDirectory = [IO.Path]::GetDirectoryName($target)
    if ($targetDirectory) { [IO.Directory]::CreateDirectory($targetDirectory) | Out-Null }
    $bitmap.Save($target, [System.Drawing.Imaging.ImageFormat]::Png)
}
finally {
    $graphics.Dispose()
    $bitmap.Dispose()
}

[pscustomobject]@{ status = 'completed'; format = 'png'; sensitive_window_visible = $false } | ConvertTo-Json -Compress
