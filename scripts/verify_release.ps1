<#
.SYNOPSIS
    Pre-release / pre-signing sanity check for the onedir package.

.DESCRIPTION
    Verifies the things that commonly break release pipelines and SignPath
    submissions:
      - zip exists, name contains the current version, layout has index.dist/index.exe
      - index.exe has Windows version metadata (ProductName/ProductVersion/FileVersion)
      - index.exe --version matches VERSION in index.py
      - index.exe.sha256 matches the actual exe hash
      - THIRD_PARTY_NOTICES.md is bundled
      - no model weights (*.onnx/*.pt/*.pth) inside the package
      - (optional) network-dependent checks are NOT performed

    ASCII-only so it runs in Windows PowerShell 5.1 and PowerShell 7+.

.PARAMETER Zip
    Path or glob to the onedir zip. Default: newest dist/*-win-onedir.zip.

.PARAMETER Version
    Expected version. Default: VERSION read from index.py.

.EXAMPLE
    .\scripts\verify_release.ps1

.EXAMPLE
    .\scripts\verify_release.ps1 -Zip dist\MeteorMasterDetecterAI-2.6.1-win-onedir.zip
#>
param(
    [string]$Zip,
    [string]$Version
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$failures = New-Object System.Collections.Generic.List[string]
$checks = 0

function Check {
    param([string]$Name, [bool]$Condition, [string]$Detail = "")
    $script:checks++
    if ($Condition) {
        Write-Host ("PASS  {0}" -f $Name)
    } else {
        $script:failures.Add($Name)
        if ($Detail) { Write-Host ("FAIL  {0}  ({1})" -f $Name, $Detail) }
        else { Write-Host ("FAIL  {0}" -f $Name) }
    }
}

if (-not $Version) {
    $versionLine = Select-String -LiteralPath (Join-Path $RepoRoot "index.py") -Pattern '^VERSION\s*=\s*"([^"]+)"'
    if (-not $versionLine) { throw "Cannot read VERSION from index.py" }
    $Version = $versionLine.Matches[0].Groups[1].Value
}
Write-Host "Expected version: $Version"

if (-not $Zip) {
    $Zip = Get-ChildItem -LiteralPath (Join-Path $RepoRoot "dist") -Filter "*-win-onedir.zip" |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1 -ExpandProperty FullName
} else {
    $Zip = (Resolve-Path -LiteralPath $Zip).Path
}
if (-not $Zip -or -not (Test-Path -LiteralPath $Zip)) {
    throw "onedir zip not found (run 'python build.py --mode onedir --zip')"
}
Write-Host "Package: $Zip"
Check "zip file name contains version" ((Split-Path -Leaf $Zip).Contains($Version)) (Split-Path -Leaf $Zip)

# ---- extract and inspect layout -------------------------------------------
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [System.IO.Compression.ZipFile]::OpenRead($Zip)
try {
    $names = $archive.Entries | ForEach-Object { $_.FullName }

    Check "contains index.dist/index.exe" ($names -contains "index.dist/index.exe")
    Check "contains index.dist/index.exe.sha256" ($names -contains "index.dist/index.exe.sha256")
    Check "contains THIRD_PARTY_NOTICES.md" ($names -contains "index.dist/THIRD_PARTY_NOTICES.md")

    $models = $names | Where-Object { $_ -match '\.(onnx|pt|pth|engine)$' }
    Check "no model weights in package" ($null -eq $models -or $models.Count -eq 0) (($models -join ", "))

    $extract = Join-Path $env:TEMP ("mmad-verify-" + [Guid]::NewGuid().ToString("N"))
    [System.IO.Compression.ZipFile]::ExtractToDirectory($Zip, $extract)
    $exe = Join-Path $extract "index.dist\index.exe"
} finally {
    $archive.Dispose()
}

try {
    Check "index.exe exists after extract" (Test-Path -LiteralPath $exe)

    if (Test-Path -LiteralPath $exe) {
        # ---- version resource ---------------------------------------------
        $vi = (Get-Item -LiteralPath $exe).VersionInfo
        Check "ProductName set" ([bool]$vi.ProductName) $vi.ProductName
        Check "ProductVersion set" ([bool]$vi.ProductVersion) $vi.ProductVersion
        Check "FileVersion set" ([bool]$vi.FileVersion) $vi.FileVersion
        Check "ProductVersion matches $Version" ([string]$vi.ProductVersion -like "$Version*") $vi.ProductVersion

        # ---- --version ----------------------------------------------------
        $out = & $exe --version 2>$null
        Check "index.exe --version contains $Version" (($out -join " ").Contains($Version)) ($out -join " ")

        # ---- --licenses (bundled notices) ---------------------------------
        $lic = & $exe --licenses 2>$null
        Check "index.exe --licenses prints third-party notices" (($lic -join "`n").Contains("Third-Party"))

        # ---- hash manifest ------------------------------------------------
        $actual = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLower()
        $shaFile = "$exe.sha256"
        if (Test-Path -LiteralPath $shaFile) {
            $recorded = ((Get-Content -LiteralPath $shaFile -Raw) -split "\s+")[0].ToLower()
            Check "index.exe.sha256 matches exe" ($recorded -eq $actual) "recorded=$recorded actual=$actual"
        } else {
            Check "index.exe.sha256 exists" $false
        }

        # ---- signature state (informational, expected unsigned here) ------
        $sig = Get-AuthenticodeSignature -LiteralPath $exe
        Write-Host ("INFO  signature status: {0}" -f $sig.Status)
    }

    # ---- zip hash file ----------------------------------------------------
    Check "zip .sha256 file exists" (Test-Path -LiteralPath "$Zip.sha256")
    if (Test-Path -LiteralPath "$Zip.sha256") {
        $zipHash = (Get-FileHash -LiteralPath $Zip -Algorithm SHA256).Hash.ToLower()
        $zipLines = Get-Content -LiteralPath "$Zip.sha256" | Where-Object { $_.Trim() -ne "" }
        $zipRecorded = (($zipLines[-1] -split "\s+")[0]).Trim().ToLower()
        Check "zip .sha256 matches zip hash" ($zipRecorded -eq $zipHash) "recorded=$zipRecorded actual=$zipHash"
    }
} finally {
    if (Test-Path -LiteralPath $extract) { Remove-Item -LiteralPath $extract -Recurse -Force -ErrorAction SilentlyContinue }
}

Write-Host ""
if ($failures.Count -gt 0) {
    Write-Host ("FAILED: {0}/{1} checks failed" -f $failures.Count, $checks) -ForegroundColor Red
    $failures | ForEach-Object { Write-Host ("  - {0}" -f $_) -ForegroundColor Red }
    exit 1
}
Write-Host ("OK: all {0} checks passed" -f $checks) -ForegroundColor Green
exit 0
