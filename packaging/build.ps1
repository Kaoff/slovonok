<#
.SYNOPSIS
  Builds the Windows installer: frontend, PyInstaller package, smoke test, Inno Setup, checksum.

.DESCRIPTION
  Run from anywhere:  powershell -File packaging\build.ps1
  Needs: the backend venv with requirements-build.txt installed, Node.js, espeak-ng installed,
  the Vosk model in backend\models, and Inno Setup 6 (winget install JRSoftware.InnoSetup).
  The version comes from backend\version.py. Output: packaging\output\Slovonok-Setup-<version>.exe
  and its .sha256. See RELEASING.md for how to publish it.

.PARAMETER SkipFrontend
  Reuse the existing frontend\build.
.PARAMETER SkipSmoke
  Don't run the package's self-test (not recommended: it is the proof the package is complete).
#>
param(
    [switch]$SkipFrontend,
    [switch]$SkipSmoke
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
# Uppercase drive letter: with "d:\..." Vite writes absolute D:/... URLs for the fonts into the
# panel's CSS (they 404 once served by the app), and vitest loads twice.
$root = $root.Substring(0, 1).ToUpper() + $root.Substring(1)
$packaging = Join-Path $root "packaging"
$python = Join-Path $root "backend\.venv\Scripts\python.exe"

function Step($text) { Write-Host "`n== $text" -ForegroundColor Cyan }
function Fail($text) { Write-Host "ERROR: $text" -ForegroundColor Red; exit 1 }

if (-not (Test-Path $python)) { Fail "No backend venv at $python (see README, Setup)" }

# --- Version -------------------------------------------------------------------------------------
$versionLine = Select-String -Path (Join-Path $root "backend\version.py") -Pattern '__version__\s*=\s*"([^"]+)"'
if (-not $versionLine) { Fail "Cannot read the version from backend\version.py" }
$version = $versionLine.Matches[0].Groups[1].Value
if ($version -notmatch '^\d+\.\d+\.\d+$') { Fail "Version '$version' must look like 1.2.3" }
Write-Host "Building Slovonok $version"

# --- Tools ---------------------------------------------------------------------------------------
$iscc = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { Fail "Inno Setup 6 not found. Install it: winget install JRSoftware.InnoSetup" }

# --- Frontend --------------------------------------------------------------------------------------
if (-not $SkipFrontend) {
    Step "Frontend build"
    Push-Location (Join-Path $root "frontend")
    try {
        npm ci
        if ($LASTEXITCODE) { Fail "npm ci failed" }
        npm run build
        if ($LASTEXITCODE) { Fail "npm run build failed" }
    } finally { Pop-Location }
}
$absolute = Get-ChildItem (Join-Path $root "frontend\build\_app\immutable\assets\*.css") | Select-String -Pattern 'url\([A-Za-z]:' -List
if ($absolute) { Fail "The panel's CSS contains absolute file paths ($($absolute[0].Path)): rebuild the frontend from a path with an uppercase drive letter" }

# --- PyInstaller -----------------------------------------------------------------------------------
Step "PyInstaller package"
Push-Location $root
try {
    Remove-Item -Recurse -Force (Join-Path $packaging "dist"), (Join-Path $packaging "build") -ErrorAction SilentlyContinue
    & $python -m PyInstaller --noconfirm --distpath (Join-Path $packaging "dist") --workpath (Join-Path $packaging "build") (Join-Path $packaging "slovonok.spec")
    if ($LASTEXITCODE) { Fail "PyInstaller failed" }
} finally { Pop-Location }
$app = Join-Path $packaging "dist\Slovonok"
$exe = Join-Path $app "Slovonok.exe"
if (-not (Test-Path $exe)) { Fail "No $exe after the build" }
$sizeMb = [math]::Round((Get-ChildItem $app -Recurse | Measure-Object Length -Sum).Sum / 1MB)
Write-Host "Package: $sizeMb MB"

# --- Smoke test ----------------------------------------------------------------------------------------
if (-not $SkipSmoke) {
    Step "Smoke test of the package"
    $scratch = Join-Path $env:TEMP "slovonok-smoke"
    Remove-Item -Recurse -Force $scratch -ErrorAction SilentlyContinue
    New-Item -ItemType Directory $scratch | Out-Null
    $report = Join-Path $scratch "report.json"
    # An isolated data folder, a free port and no microphone: it must not touch a real installation
    $env:SLOVONOK_DATA_DIR = Join-Path $scratch "data"
    $env:SLOVONOK_PORT = "8790"
    $env:SLOVONOK_NO_LISTENING = "1"
    try {
        $process = Start-Process -FilePath $exe -ArgumentList @("--smoke", $report) -PassThru -Wait -WindowStyle Hidden
    } finally {
        Remove-Item Env:SLOVONOK_DATA_DIR, Env:SLOVONOK_PORT, Env:SLOVONOK_NO_LISTENING -ErrorAction SilentlyContinue
    }
    if (-not (Test-Path $report)) { Fail "The package produced no smoke report (exit code $($process.ExitCode)); see $env:TEMP\slovonok-smoke\data\logs" }
    $result = Get-Content $report -Raw | ConvertFrom-Json
    foreach ($check in $result.checks) {
        $mark = if ($check.ok) { "OK  " } else { "FAIL" }
        $color = if ($check.ok) { "Green" } else { "Red" }
        Write-Host ("{0} {1}: {2}" -f $mark, $check.name, $check.detail) -ForegroundColor $color
    }
    if (-not $result.ok) { Fail "The package is incomplete: not making an installer" }
}

# --- Installer -------------------------------------------------------------------------------------------
Step "Installer"
& $iscc "/DAppVersion=$version" "/DSourceDir=$app" (Join-Path $packaging "installer.iss")
if ($LASTEXITCODE) { Fail "Inno Setup failed" }
$installer = Join-Path $packaging "output\Slovonok-Setup-$version.exe"
if (-not (Test-Path $installer)) { Fail "No installer at $installer" }

# The updater refuses an installer without a checksum: publish it next to the installer
$hash = (Get-FileHash $installer -Algorithm SHA256).Hash.ToLower()
"$hash  $(Split-Path -Leaf $installer)" | Set-Content -Encoding ascii "$installer.sha256"

$installerMb = [math]::Round((Get-Item $installer).Length / 1MB)
Write-Host "`nDone: $installer ($installerMb MB)" -ForegroundColor Green
Write-Host "SHA-256: $hash"
Write-Host "Next: see packaging\RELEASING.md to publish it as release v$version."
