# Text2Audio installer - sets up everything so the app runs by double-clicking Start.
# Everything is written to a per-user UTF-8 log (install.log). Its quoted path is printed first,
# on every failure and on completion. T2A_LOG_DIR overrides the folder (isolated tests).
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot   # scripts/ -> project root
$script:Utf8 = New-Object System.Text.UTF8Encoding($false)
$script:LogPath = $null
$script:LastExit = 0
# Kokoro (the voice engine) needs Python 3.10, 3.11 or 3.12. 3.13+ is not supported yet.
$MinMinor = 10; $MaxMinor = 12

function Initialize-InstallLog {
    $dirs = @()
    if ($env:T2A_LOG_DIR) { $dirs += $env:T2A_LOG_DIR }
    if ($env:LOCALAPPDATA) { $dirs += (Join-Path $env:LOCALAPPDATA "Text2Audio\logs") }
    $dirs += (Join-Path ([System.IO.Path]::GetTempPath()) "Text2Audio\logs")
    foreach ($d in $dirs) {
        try {
            [void](New-Item -ItemType Directory -Force -Path $d)
            $p = Join-Path $d "install.log"
            [System.IO.File]::AppendAllText($p, ((Get-Date -Format s) + " --- install.ps1 started`r`n"), $script:Utf8)
            return $p
        } catch { continue }
    }
    return $null
}

function Write-Log([string]$msg) {
    if (-not $script:LogPath) { return }
    try { [System.IO.File]::AppendAllText($script:LogPath, ((Get-Date -Format s) + " " + $msg + "`r`n"), $script:Utf8) } catch {}
}

function Show-LogPath {
    if ($script:LogPath) { Write-Host ('Log file: "' + $script:LogPath + '"') -ForegroundColor Cyan }
    else { Write-Host "Log file: could not be created (no writable folder found). Please tell the person helping you." -ForegroundColor Yellow }
}

function Say($msg)  { Write-Host "`n>>> $msg" -ForegroundColor Cyan; Write-Log ">>> $msg" }
function Have($cmd) { return [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }

function Fail($msg) {
    Write-Log "FAIL: $msg"
    Write-Host ""
    Write-Host "=====================================================" -ForegroundColor Red
    Write-Host "  Setup stopped:" -ForegroundColor Red
    Write-Host "  $msg" -ForegroundColor Red
    Write-Host "=====================================================" -ForegroundColor Red
    Show-LogPath
    exit 1
}

# Runs a native command, shows its output, and keeps stdout/stderr/exit code in the log.
# The exit code is left in $script:LastExit. -Quiet logs only stderr (Python logs its own lines).
function Invoke-Logged {
    param([string]$Exe, [string[]]$ArgList = @(), [switch]$Quiet)
    Write-Log ("RUN: " + $Exe + " " + ($ArgList -join " "))
    $ErrorActionPreference = "Continue"   # native stderr must not become a terminating error
    $script:LastExit = 0
    $global:LASTEXITCODE = 0
    try {
        & $Exe @ArgList 2>&1 | ForEach-Object {
            if ($_ -is [System.Management.Automation.ErrorRecord]) {
                $line = $_.Exception.Message
                Write-Host $line
                Write-Log ("[stderr] " + $line)
            } else {
                $line = "$_"
                Write-Host $line
                if (-not $Quiet) { Write-Log $line }
            }
        }
        if ($null -eq $LASTEXITCODE) { $script:LastExit = 0 } else { $script:LastExit = $LASTEXITCODE }
    } catch {
        Write-Log ("EXCEPTION running " + $Exe + ": " + $_.Exception.Message)
        Write-Host ("Could not run " + $Exe + ": " + $_.Exception.Message) -ForegroundColor Yellow
        $script:LastExit = 1
    }
    Write-Log ("EXIT " + $script:LastExit + ": " + $Exe)
}

function Install-WithWinget($id, $name) {
    if (Have "winget") {
        Say "Installing $name ..."
        Invoke-Logged "winget" @("install", "-e", "--id", $id, "--accept-source-agreements", "--accept-package-agreements")
        if ($script:LastExit -ne 0) {
            Write-Log "winget exited with $($script:LastExit) for $id (this can also mean it is already installed)"
            Write-Host "winget reported a problem installing $name; continuing and re-checking afterwards." -ForegroundColor Yellow
        }
    } else {
        Write-Host "winget not found - please install $name manually." -ForegroundColor Yellow
        Write-Log "winget not found for $name"
        $vp = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
        if (Test-Path $vp) { Invoke-Logged $vp @((Join-Path $PSScriptRoot "install_support.py"), "--winget-guidance") -Quiet }
    }
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

# ---- the log exists BEFORE any Python discovery or bootstrap ----
$script:LogPath = Initialize-InstallLog
if ($script:LogPath) { $env:T2A_INSTALL_LOG = $script:LogPath }
$env:PYTHONUNBUFFERED = "1"; $env:PYTHONIOENCODING = "utf-8"; $env:PYTHONUTF8 = "1"
try { [Console]::OutputEncoding = $script:Utf8 } catch {}
Show-LogPath
Write-Log "Project root: $ProjectRoot"

function Invoke-Install {
    Set-Location $ProjectRoot
    Say "Text2Audio setup starting"

    # 1) Python (real install only - the Microsoft Store "python" shortcut does not count)
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
        Invoke-Logged $pyExe (@($pyPre) + @("-m", "venv", ".venv"))
        if ($script:LastExit -ne 0 -or -not (Test-Path $vpy)) { Fail "Could not create the Python virtual environment (.venv)." }
    }
    Invoke-Logged $vpy @("-m", "pip", "install", "--upgrade", "pip")
    if ($script:LastExit -ne 0) { Fail "Could not upgrade pip. Check your internet connection and try again." }

    # Pre-install hardware check (Python support; never fatal)
    $support = Join-Path $PSScriptRoot "install_support.py"
    Invoke-Logged $vpy @($support, "--stage", "pre") -Quiet
    if ($script:LastExit -ne 0) { Write-Log "pre stage exited with $($script:LastExit) (not fatal)" }

    # 3) PyTorch (CUDA if an NVIDIA GPU is present, else CPU).
    # Pinned to 2.6.0: Chatterbox (the studio voice and cloning engine) requires exactly
    # torch/torchaudio 2.6.0. Installing it first from the CUDA index keeps the GPU build;
    # otherwise pip would later swap in the CPU-only 2.6.0 wheel from PyPI.
    $torchPins = @("torch==2.6.0", "torchaudio==2.6.0")
    $gpu = $false
    try { & nvidia-smi *> $null; if ($LASTEXITCODE -eq 0) { $gpu = $true } } catch { Write-Log "nvidia-smi not available: $($_.Exception.Message)" }
    Write-Log "NVIDIA GPU detected: $gpu"
    if ($gpu) {
        Say "NVIDIA GPU detected - installing CUDA PyTorch"
        Invoke-Logged $vpy (@("-m", "pip", "install") + $torchPins + @("--index-url", "https://download.pytorch.org/whl/cu124"))
        if ($script:LastExit -ne 0) {
            Write-Host "CUDA PyTorch was unavailable; falling back to the CPU build." -ForegroundColor Yellow
            Write-Log "CUDA PyTorch install failed; falling back to CPU build"
            Invoke-Logged $vpy (@("-m", "pip", "install") + $torchPins)
            if ($script:LastExit -ne 0) { Fail "PyTorch installation failed. Check your internet connection and try again." }
        }
    } else {
        Say "No NVIDIA GPU - installing CPU PyTorch (works; use the fast Kokoro voices)"
        Invoke-Logged $vpy (@("-m", "pip", "install") + $torchPins)
        if ($script:LastExit -ne 0) { Fail "PyTorch installation failed. Check your internet connection and try again." }
    }

    # 4) App dependencies
    Say "Installing Text2Audio dependencies"
    Invoke-Logged $vpy @("-m", "pip", "install", "-r", "requirements.txt")
    if ($script:LastExit -ne 0) { Fail "Installing the app dependencies failed. Check your internet connection and try again." }

    # 5) System tools
    if (-not (Have "ffmpeg")) { Install-WithWinget "Gyan.FFmpeg" "ffmpeg" }
    if (-not (Test-Path "C:\Program Files\eSpeak NG\libespeak-ng.dll")) { Install-WithWinget "eSpeak-NG.eSpeak-NG" "espeak-ng" }
    Refresh-Path
    if (-not (Have "ffmpeg")) {
        Write-Host "ffmpeg is still unavailable. Install it manually before rendering." -ForegroundColor Yellow
        Write-Log "ffmpeg still unavailable"
    }
    if (-not (Have "espeak-ng") -and -not (Test-Path "C:\Program Files\eSpeak NG\espeak-ng.exe")) {
        Write-Host "espeak-ng is still unavailable. Install it manually before using Kokoro." -ForegroundColor Yellow
        Write-Log "espeak-ng still unavailable"
    }

    # 5b) Model, language package, post hardware check and offline-readiness gate (all in Python)
    foreach ($stage in "prepare", "post", "verify") {
        Invoke-Logged $vpy @($support, "--stage", $stage) -Quiet
        if ($script:LastExit -ne 0) {
            Fail "Setup is not finished (step '$stage'). Nothing is lost: double-click 'Install Text2Audio.bat' again to continue."
        }
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
        Write-Log "Desktop shortcut failed: $($_.Exception.Message)"
    }

    Write-Log "Setup completed successfully"
    Write-Host "`n=====================================================" -ForegroundColor Green
    Write-Host "  Done! Double-click 'Text2Audio' on your Desktop"     -ForegroundColor Green
    Write-Host "  (or 'Start Text2Audio' in this folder) to run it."   -ForegroundColor Green
    Write-Host "  Voice models and language package are installed; works offline." -ForegroundColor Green
    Write-Host "=====================================================" -ForegroundColor Green
    Show-LogPath
}

try {
    Invoke-Install
} catch {
    Write-Log ("UNEXPECTED ERROR: " + $_.Exception.Message + " | " + $_.ScriptStackTrace)
    Fail ("Setup hit an unexpected problem: " + $_.Exception.Message)
}
exit 0
