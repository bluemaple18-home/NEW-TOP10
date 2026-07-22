[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$OutputPath,
    [Parameter(Mandatory)][ValidatePattern('^[A-Za-z0-9_.-]+$')][string]$CaptureProcessName,
    [Parameter(Mandatory)][string]$CaptureWindowTitlePattern,
    [Parameter(Mandatory)][ValidateRange(1,9223372036854775807)][Int64]$CaptureWindowHandle,
    [switch]$AcknowledgeNonSensitiveWindow,
    [switch]$Execute
)

$ErrorActionPreference = 'Stop'

if (-not $Execute) {
    [pscustomobject]@{ mode = 'dry-run'; action = 'capture-diagnostic-window'; target = 'explicit-process-title-handle'; non_sensitive_window_required = $true } | ConvertTo-Json -Compress
    return
}
if (-not $AcknowledgeNonSensitiveWindow) {
    throw '截圖前必須明示指定視窗是非敏感 allowlisted surface。'
}
if (-not $IsWindows -and $PSVersionTable.PSEdition -eq 'Core') {
    throw '診斷截圖只支援 Windows。'
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class YuantaWindowGuard {
    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool IsWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern IntPtr GetWindow(IntPtr hWnd, uint command);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
    [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, System.Text.StringBuilder text, int max);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc callback, IntPtr state);
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
    public static List<IntPtr> VisibleTopLevelWindows() {
        var result = new List<IntPtr>();
        EnumWindows((h, _) => { if (IsWindowVisible(h)) result.Add(h); return true; }, IntPtr.Zero);
        return result;
    }
    public static IntPtr Owner(IntPtr hWnd) { return GetWindow(hWnd, 4); }
    public static RECT Bounds(IntPtr hWnd) { RECT rect; if (!GetWindowRect(hWnd, out rect)) throw new InvalidOperationException("無法驗證視窗 bounds"); return rect; }
    public static string Title(IntPtr hWnd) { var text = new System.Text.StringBuilder(512); GetWindowText(hWnd, text, text.Capacity); return text.ToString(); }
    public static uint ProcessId(IntPtr hWnd) { uint id; if (GetWindowThreadProcessId(hWnd, out id) == 0) throw new InvalidOperationException("無法驗證視窗 process"); return id; }
}
'@
$handle = [IntPtr]$CaptureWindowHandle
if (-not [YuantaWindowGuard]::IsWindow($handle) -or -not [YuantaWindowGuard]::IsWindowVisible($handle)) { throw '指定視窗不存在或不可見。' }
$targetProcessId = [YuantaWindowGuard]::ProcessId($handle)
$targetProcess = Get-Process -Id $targetProcessId -ErrorAction Stop
if ($targetProcess.ProcessName -ne $CaptureProcessName -or [YuantaWindowGuard]::Title($handle) -notmatch $CaptureWindowTitlePattern) { throw '指定視窗的 process/title 驗證失敗。' }
if ([YuantaWindowGuard]::Owner($handle) -ne [IntPtr]::Zero) { throw 'owned/dialog window 不允許擷取。' }
$visibleWindows = @([YuantaWindowGuard]::VisibleTopLevelWindows())
$sameProcessWindows = @($visibleWindows | Where-Object { [YuantaWindowGuard]::ProcessId($_) -eq $targetProcessId })
if ($sameProcessWindows.Count -ne 1 -or $sameProcessWindows[0] -ne $handle) { throw '目標 process 必須只有一個可見 top-level window。' }
$targetRect = [YuantaWindowGuard]::Bounds($handle)
$bounds = [System.Drawing.Rectangle]::FromLTRB($targetRect.Left, $targetRect.Top, $targetRect.Right, $targetRect.Bottom)
if ($bounds.Width -le 0 -or $bounds.Height -le 0) { throw '指定視窗 surface 無效。' }
$screen = @([System.Windows.Forms.Screen]::AllScreens | Where-Object { $_.Bounds.Contains($bounds.Location) -and $_.Bounds.Contains([System.Drawing.Point]::new($bounds.Right - 1, $bounds.Bottom - 1)) })
if ($screen.Count -ne 1) { throw '指定視窗必須完整位於單一 monitor；拒絕跨 monitor surface。' }
foreach ($window in $visibleWindows) {
    if ($window -eq $handle) { continue }
    if ([YuantaWindowGuard]::Owner($window) -eq $handle) { throw '目標視窗有可見 owned/dialog window。' }
    $otherRect = [YuantaWindowGuard]::Bounds($window)
    $otherBounds = [System.Drawing.Rectangle]::FromLTRB($otherRect.Left, $otherRect.Top, $otherRect.Right, $otherRect.Bottom)
    if ($bounds.IntersectsWith($otherBounds)) { throw '其他 process/window 與目標 surface 重疊；拒絕截圖。' }
}
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

[pscustomobject]@{ status = 'completed'; format = 'png'; capture_surface = 'single-allowlisted-window'; cross_monitor = $false; sensitive_window_visible = $false } | ConvertTo-Json -Compress
