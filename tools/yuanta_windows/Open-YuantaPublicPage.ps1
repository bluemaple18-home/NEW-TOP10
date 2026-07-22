[CmdletBinding()]
param(
    [Uri]$Uri = 'https://www.yuanta.com.tw/',
    [switch]$Execute
)

$ErrorActionPreference = 'Stop'
$hostName = $Uri.DnsSafeHost.ToLowerInvariant()
if ($Uri.Scheme -ne 'https' -or ($hostName -ne 'yuanta.com.tw' -and -not $hostName.EndsWith('.yuanta.com.tw'))) {
    throw '只允許開啟 yuanta.com.tw 的 HTTPS 公開頁面。'
}

if (-not $Execute) {
    [pscustomobject]@{ mode = 'dry-run'; action = 'open-public-page'; host = $hostName } | ConvertTo-Json -Compress
    return
}

Start-Process -FilePath $Uri.AbsoluteUri
