# Text2Audio installer — sets up everything so the app runs by double-clicking Start.
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot   # scripts/ -> project root
Set-Location $ProjectRoot

function Say($msg)  { Write-Host "`n>>> $msg" -ForegroundColor Cyan }
function Have($cmd) { return [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }
function Winget($id, $name) {
    if (Have "winget") {
        Say "Installing $name ..."
        winget install -e --id $id --accept-source-agreements --accept-package-agreements
    } else {
        Write-Host "winget not found - please install $name manually." -ForegroundColor Yellow
    }
}

Say "Text2Audio setup starting"

# 1) Python
$py = $null
if (Have "py") { $py = "py" } elseif (Have "python") { $py = "python" }
if (-not $py) {
    Winget "Python.Python.3.11" "Python 3.11"
    $env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User")
    if (Have "py") { $py = "py" } elseif (Have "python") { $py = "python" }
}
if (-not $py) {
    Write-Host "Python not found. Install it from https://www.python.org/downloads/ and re-run." -ForegroundColor Red
    exit 1
}

# 2) Virtual environment
if (-not (Test-Path ".venv")) { Say "Creating virtual environment"; & $py -m venv .venv }
$vpy = ".\.venv\Scripts\python.exe"
& $vpy -m pip install --upgrade pip | Out-Null

# 3) PyTorch (CUDA if an NVIDIA GPU is present, else CPU)
$gpu = $false
try { & nvidia-smi *> $null; if ($LASTEXITCODE -eq 0) { $gpu = $true } } catch {}
if ($gpu) {
    Say "NVIDIA GPU detected - installing CUDA PyTorch"
    & $vpy -m pip install torch --index-url https://download.pytorch.org/whl/cu124
    if ($LASTEXITCODE -ne 0) {
        Write-Host "CUDA PyTorch was unavailable; falling back to the CPU build." -ForegroundColor Yellow
        & $vpy -m pip install torch
    }
} else {
    Say "No NVIDIA GPU - installing CPU PyTorch (works, just slower)"
    & $vpy -m pip install torch
}

# 4) App dependencies
Say "Installing Text2Audio dependencies"
& $vpy -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Application dependency installation failed." }

# 5) System tools
if (-not (Have "ffmpeg")) { Winget "Gyan.FFmpeg" "ffmpeg" }
if (-not (Test-Path "C:\Program Files\eSpeak NG\libespeak-ng.dll")) { Winget "eSpeak-NG.eSpeak-NG" "espeak-ng" }
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
