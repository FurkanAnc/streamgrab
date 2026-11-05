# StreamGrab paketleme: dist\StreamGrab-Setup-<surum>.exe uretir.
#
# Gereksinimler:
#   .venv\Scripts\pip install -r requirements-dev.txt
#   winget install JRSoftware.InnoSetup --scope user

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw ".venv bulunamadi. README'deki kurulum adimlarini uygula." }

$iscc = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup bulunamadi: winget install JRSoftware.InnoSetup --scope user" }

$version = & $python -c "import streamgrab; print(streamgrab.__version__)"

& $python packaging\make_icon.py
if ($LASTEXITCODE -ne 0) { throw "simge uretilemedi" }

& $python -m PyInstaller packaging\streamgrab.spec --noconfirm --clean --distpath dist --workpath build
if ($LASTEXITCODE -ne 0) { throw "PyInstaller basarisiz" }

& $iscc "/DAppVersion=$version" packaging\streamgrab.iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup basarisiz" }

Write-Host "Hazir: dist\StreamGrab-Setup-$version.exe"
