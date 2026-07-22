[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Workspace,
    [Parameter(Mandatory)][string]$InstallerPath,
    [string]$CertificatePath,
    [string]$ArchivePath,
    [switch]$LaunchInstaller,
    [switch]$Force,
    [switch]$Execute
)

$ErrorActionPreference = 'Stop'

function Get-ValidatedSource([string]$PathValue, [string[]]$AllowedExtensions) {
    $item = Get-Item -LiteralPath $PathValue -ErrorAction Stop
    if (-not $item.PSIsContainer -and $AllowedExtensions -notcontains $item.Extension.ToLowerInvariant()) {
        throw "不支援的來源副檔名：$($item.Extension)"
    }
    if ($item.PSIsContainer) { throw '來源必須是檔案。' }
    return $item
}

$installer = Get-ValidatedSource $InstallerPath @('.exe', '.msi')
$certificate = if ($CertificatePath) { Get-ValidatedSource $CertificatePath @('.pfx', '.p12') } else { $null }
$archive = if ($ArchivePath) { Get-ValidatedSource $ArchivePath @('.zip') } else { $null }
$plannedFiles = @($installer.Name)
if ($certificate) { $plannedFiles += $certificate.Name }
if ($archive) { $plannedFiles += $archive.Name }

if (-not $Execute) {
    [pscustomobject]@{ mode = 'dry-run'; action = 'prepare-workspace'; file_names = $plannedFiles; import_certificate = $false } | ConvertTo-Json -Compress
    return
}

$workspaceItem = New-Item -ItemType Directory -Path $Workspace -Force
foreach ($source in @($installer, $certificate, $archive)) {
    if ($null -eq $source) { continue }
    $destination = Join-Path $workspaceItem.FullName $source.Name
    if ((Test-Path -LiteralPath $destination) -and -not $Force) {
        throw "目的檔已存在；請先核對或明示 -Force：$($source.Name)"
    }
    Copy-Item -LiteralPath $source.FullName -Destination $destination -Force:$Force
}

if ($LaunchInstaller) {
    $installerCopy = Join-Path $workspaceItem.FullName $installer.Name
    Start-Process -FilePath $installerCopy
}

[pscustomobject]@{ status = 'completed'; copied_file_names = $plannedFiles; certificate_imported = $false } | ConvertTo-Json -Compress
