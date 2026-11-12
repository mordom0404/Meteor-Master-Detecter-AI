<#
.SYNOPSIS
    Sign index.exe (onedir build) with Authenticode, verify it, refresh SHA256.

.DESCRIPTION
    Default target: dist\index.dist\index.exe (the v2.6.0+ onedir layout).
    Certificate source (choose one):
      - certificate store thumbprint: -Thumbprint "ABCDEF..."
      - PFX file: -PfxPath "D:\certs\codesign.pfx" [-PfxPassword "..."]
    Use -Zip to rebuild the onedir zip after signing and refresh its hash
    (signing changes the exe hash).

    NOTE: this script is intentionally ASCII-only so it works in both
    Windows PowerShell 5.1 and PowerShell 7+.

.EXAMPLE
    .\scripts\sign_index.ps1 -Thumbprint "ABCDEF0123456789" -Zip

.EXAMPLE
    .\scripts\sign_index.ps1 -PfxPath "D:\certs\codesign.pfx" -PfxPassword "***" -Zip
#>
[CmdletBinding(DefaultParameterSetName = "Thumbprint")]
param(
    [string]$Path = "dist\index.dist\index.exe",

    [Parameter(ParameterSetName = "Thumbprint", Mandatory = $true)]
    [string]$Thumbprint,

    [Parameter(ParameterSetName = "Pfx", Mandatory = $true)]
    [string]$PfxPath,

    [Parameter(ParameterSetName = "Pfx")]
    [string]$PfxPassword,

    [string]$TimestampUrl = "http://timestamp.digicert.com",
    [switch]$NoTimestamp,

    # Rebuild the onedir zip after signing and refresh its hash
    [switch]$Zip
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not [System.IO.Path]::IsPathRooted($Path)) {
    $Path = Join-Path $RepoRoot $Path
}

if (-not (Test-Path -LiteralPath $Path)) {
    throw "Target not found: $Path (run 'python build.py --mode onedir' first)"
}
$Path = (Resolve-Path -LiteralPath $Path).Path
$ExeName = Split-Path -Leaf $Path

# ---- locate signtool.exe (Windows SDK) ------------------------------------
function Find-SignTool {
    $programFiles = [Environment]::GetEnvironmentVariable("ProgramFiles")
    $programFilesX86 = [Environment]::GetEnvironmentVariable("ProgramFiles(x86)")

    $roots = @()
    if ($programFilesX86) { $roots += (Join-Path $programFilesX86 "Windows Kits\10\bin") }
    if ($programFiles) { $roots += (Join-Path $programFiles "Windows Kits\10\bin") }

    $candidates = @()
    foreach ($root in $roots) {
        if (Test-Path -LiteralPath $root) {
            $candidates += Get-ChildItem -LiteralPath $root -Directory |
                Sort-Object Name -Descending |
                ForEach-Object { Join-Path $_.FullName "x64\signtool.exe" } |
                Where-Object { Test-Path -LiteralPath $_ }
        }
    }
    return ($candidates | Select-Object -First 1)
}

$SignTool = Find-SignTool
if (-not $SignTool) {
    throw "signtool.exe not found. Install the Windows SDK (signing tools) or the VS Windows SDK component."
}

# ---- build signtool arguments ---------------------------------------------
$signArgs = @("sign", "/fd", "SHA256")
if (-not $NoTimestamp) {
    $signArgs += @("/td", "SHA256", "/tr", $TimestampUrl)
}
if ($PSCmdlet.ParameterSetName -eq "Thumbprint") {
    $signArgs += @("/sha1", $Thumbprint)
} else {
    $signArgs += @("/f", (Resolve-Path -LiteralPath $PfxPath).Path)
    if ($PfxPassword) {
        $signArgs += @("/p", $PfxPassword)
    }
}
$signArgs += $Path

Write-Host "signtool: $SignTool"
Write-Host "Signing : $Path"
& $SignTool @signArgs
if ($LASTEXITCODE -ne 0) {
    throw "signtool failed (exit code $LASTEXITCODE)"
}

# ---- verify signature ------------------------------------------------------
$sig = Get-AuthenticodeSignature -LiteralPath $Path
Write-Host "Signature status: $($sig.Status)"
Write-Host "Signer          : $($sig.SignerCertificate.Subject)"
if ($sig.Status -ne "Valid") {
    throw "Signature verification failed: $($sig.StatusMessage) (a self-signed test cert is expected to fail here)"
}

# ---- refresh SHA256 manifest ----------------------------------------------
$hash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLower()
$shaFile = "$Path.sha256"
"$hash  $ExeName" | Set-Content -LiteralPath $shaFile -Encoding ascii
Write-Host "SHA256          : $hash"
Write-Host "Hash file       : $shaFile"

# ---- optional: rebuild zip -------------------------------------------------
if ($Zip) {
    $versionLine = Select-String -LiteralPath (Join-Path $RepoRoot "index.py") -Pattern '^VERSION\s*=\s*"([^"]+)"'
    if (-not $versionLine) { throw "Cannot read VERSION from index.py" }
    $version = $versionLine.Matches[0].Groups[1].Value

    $onedir = Split-Path -Parent $Path
    $zipPath = Join-Path (Split-Path -Parent $onedir) ("MeteorMasterDetecterAI-{0}-win-onedir.zip" -f $version)

    if (Test-Path -LiteralPath $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::CreateFromDirectory(
        $onedir,
        $zipPath,
        [System.IO.Compression.CompressionLevel]::Optimal,
        $true
    )

    $zipHash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLower()
    $zipName = Split-Path -Leaf $zipPath
    "$hash  $ExeName`n$zipHash  $zipName" | Set-Content -LiteralPath "$zipPath.sha256" -Encoding ascii
    Write-Host ("ZIP             : {0}  ({1:N1} MB)" -f $zipPath, ((Get-Item -LiteralPath $zipPath).Length / 1MB))
    Write-Host "ZIP SHA256      : $zipHash"
}

# ---- version resource sanity check ----------------------------------------
$vi = (Get-Item -LiteralPath $Path).VersionInfo
Write-Host ""
Write-Host "Version resource:"
Write-Host ("  ProductName    : {0}" -f $vi.ProductName)
Write-Host ("  ProductVersion : {0}" -f $vi.ProductVersion)
Write-Host ("  FileVersion    : {0}" -f $vi.FileVersion)
if (-not $vi.ProductName -or -not $vi.ProductVersion) {
    Write-Warning "exe has no version resource; signing providers may reject it (build.py should set it)."
}
