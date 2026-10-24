# Text2Audio installer — sets up everything so the app runs by double-clicking Start.
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot   # scripts/ -> project root
Set-Location $ProjectRoot

function Say($msg)  { Write-Host "`n>>> $msg" -ForegroundColor Cyan }
function Have($cmd) { return [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }
function Install-WithWinget($id, $name) {
    if (Have "winget") {
        Say "Installing $name ..."
        winget install -e --id $id --accept-source-agreements --accept-package-agreements
    } else {
        Write-Host "winget not found - please install $name manually." -ForegroundColor Yellow
    }
}

Say "Text2Audio setup starting"

# 1) Python (real install only - the Microsoft Store "python" shortcut does not count)
# Kokoro (the voice engine) needs Python 3.10, 3.11 or 3.12. 3.13+ is not supported yet.
$MinMinor = 10; $MaxMinor = 12

function Fail($msg) {
    Write-Host ""
    Write-Host "=====================================================" -ForegroundColor Red
    Write-Host "  Setup stopped:" -ForegroundColor Red
    Write-Host "  $msg" -ForegroundColor Red
    Write-Host "=====================================================" -ForegroundColor Red
    exit 1
}

# Returns @{ Exe=..; Args=@(..); Version=".." } for a working Python in range, else $null.
function Test-Python($exe, $pre) {
    try {
        $out = & $exe @pre -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $out) { return $null }
        $ver = ("$out").Trim()
        if ($ver -notmatch '^3\.(\d+)$') { return $null }
        $minor = [int]$Matches[1]
        if ($minor -lt $MinMinor -or $minor -gt $MaxMinor) { return $null }
        return @{ Exe = $exe; Args = $pre; Version = $ver }
    } catch { return $null }
}

function Find-Python {
    # 1. The py launcher, newest supported version first.
    if (Have "py") {
        foreach ($v in "3.12","3.11","3.10") {
            $r = Test-Python "py" @("-$v")
            if ($r) { return $r }
        }
    }
    # 2. python / python3 on PATH, skipping the Microsoft Store stub in WindowsApps.
    foreach ($name in "python","python3") {
        $cmds = Get-Command $name -All -ErrorAction SilentlyContinue | Where-Object { $_.CommandType -eq "Application" }
        foreach ($c in $cmds) {
            if ($c.Source -like "*\WindowsApps\*") { continue }
            $r = Test-Python $c.Source @()
            if ($r) { return $r }
        }
    }
    return $null
}

function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User")
}

$pyInfo = Find-Python
if (-not $pyInfo -and (Have "winget")) {
    Install-WithWinget "Python.Python.3.12" "Python 3.12"
    Refresh-Path
    $pyInfo = Find-Python
}
if (-not $pyInfo) {
    Fail @"
Python 3.10, 3.11 or 3.12 was not found on this computer.
  (If you saw 'Python was not found; run without arguments to install from the
   Microsoft Store', that is only a placeholder - Python itself is not installed.)

  To fix it:
    1. Go to https://www.python.org/downloads/windows/ and download Python 3.12.
    2. Run the installer and TICK 'Add python.exe to PATH' on the first screen.
       Then click 'Install Now'.
       (Or, in a terminal:  winget install Python.Python.3.12 )
    3. Close this window, then double-click 'Install Text2Audio.bat' again.
"@
}
Say "Using Python $($pyInfo.Version)"
$pyExe = $pyInfo.Exe; $pyPre = $pyInfo.Args

# 2) Virtual environment
$vpy = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if ((Test-Path ".venv") -and -not (Test-Path $vpy)) {
    Say "Removing incomplete virtual environment"
    Remove-Item ".venv" -Recurse -Force -ErrorAction SilentlyContinue
}
if (-not (Test-Path $vpy)) {
    Say "Creating virtual environment"
    & $pyExe @pyPre -m venv .venv
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $vpy)) { Fail "Could not create the Python virtual environment (.venv)." }
}
& $vpy -m pip install --upgrade pip | Out-Null
if ($LASTEXITCODE -ne 0) { Fail "Could not upgrade pip. Check your internet connection and try again." }

# 3) PyTorch (CUDA if an NVIDIA GPU is present, else CPU)
$gpu = $false
try { & nvidia-smi *> $null; if ($LASTEXITCODE -eq 0) { $gpu = $true } } catch {}
if ($gpu) {
    Say "NVIDIA GPU detected - installing CUDA PyTorch"
    & $vpy -m pip install torch --index-url https://download.pytorch.org/whl/cu124
    if ($LASTEXITCODE -ne 0) {
        Write-Host "CUDA PyTorch was unavailable; falling back to the CPU build." -ForegroundColor Yellow
        & $vpy -m pip install torch
        if ($LASTEXITCODE -ne 0) { Fail "PyTorch installation failed. Check your internet connection and try again." }
    }
} else {
    Say "No NVIDIA GPU - installing CPU PyTorch (works, just slower)"
    & $vpy -m pip install torch
    if ($LASTEXITCODE -ne 0) { Fail "PyTorch installation failed. Check your internet connection and try again." }
}

# 4) App dependencies
Say "Installing Text2Audio dependencies"
& $vpy -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { Fail "Installing the app dependencies failed. Check your internet connection and try again." }

# 5) System tools
if (-not (Have "ffmpeg")) { Install-WithWinget "Gyan.FFmpeg" "ffmpeg" }
if (-not (Test-Path "C:\Program Files\eSpeak NG\libespeak-ng.dll")) { Install-WithWinget "eSpeak-NG.eSpeak-NG" "espeak-ng" }
$env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User")
if (-not (Have "ffmpeg")) {
    Write-Host "ffmpeg is still unavailable. Install it manually before rendering." -ForegroundColor Yellow
}
if (-not (Have "espeak-ng") -and -not (Test-Path "C:\Program Files\eSpeak NG\espeak-ng.exe")) {
    Write-Host "espeak-ng is still unavailable. Install it manually before using Kokoro." -ForegroundColor Yellow
}

# 6) Desktop shortcut
try {
    $desktop = [Environment]::GetFolderPath("Desktop")
    $ws = New-Object -ComObject WScript.Shell
    $sc = $ws.CreateShortcut((Join-Path $desktop "Text2Audio.lnk"))
    $sc.TargetPath = Join-Path $ProjectRoot "Start Text2Audio.bat"
    $sc.WorkingDirectory = $ProjectRoot
    $sc.IconLocation = "$env:SystemRoot\System32\SHELL32.dll,138"
    $sc.Save()
    Say "Created Desktop shortcut: Text2Audio"
} catch {
    Write-Host "Could not create a desktop shortcut (non-fatal)." -ForegroundColor Yellow
}

Write-Host "`n=====================================================" -ForegroundColor Green
Write-Host "  Done! Double-click 'Text2Audio' on your Desktop"     -ForegroundColor Green
Write-Host "  (or 'Start Text2Audio' in this folder) to run it."   -ForegroundColor Green
Write-Host "  Tip: voice cloning is optional - see INSTALL.md."    -ForegroundColor Green
Write-Host "=====================================================" -ForegroundColor Green
