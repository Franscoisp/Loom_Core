# Loom Core — one-line install for Windows (PowerShell)
# §14: curl | iex, or save and run manually.
# Sets up a Python venv, installs loom-core, and runs loom doctor.

$ErrorActionPreference = "Stop"
$Repo = "https://github.com/Franscoisp/Loom_Core.git"
$InstallDir = "$env:USERPROFILE\loom-core"

Write-Host "=== Loom Core Installer ===" -ForegroundColor Cyan

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python 3.11+ is required but not found on PATH. Install it first: https://python.org"
    exit 1
}

$pyVer = (python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
Write-Host "Python $pyVer detected" -ForegroundColor Green

if (-not (Test-Path $InstallDir)) {
    Write-Host "Cloning Loom Core..." -ForegroundColor Cyan
    git clone $Repo $InstallDir
} else {
    Write-Host "Updating existing install..." -ForegroundColor Cyan
    Push-Location $InstallDir; git pull; Pop-Location
}

Push-Location $InstallDir

if (-not (Test-Path ".venv")) {
    Write-Host "Creating Python virtual environment..." -ForegroundColor Cyan
    python -m venv .venv
}

.\.venv\Scripts\Activate.ps1
Write-Host "Installing loom-core + dev extras..." -ForegroundColor Cyan
pip install -q -e ".[dev]"

Write-Host "`n=== Running quality gates ===" -ForegroundColor Cyan
pytest -q 2>&1 | Select-Object -Last 2
ruff check . 2>&1 | Select-Object -Last 1

Write-Host "`n=== Running loom doctor ===" -ForegroundColor Cyan
python -m loom_core.cli doctor

Write-Host "`n=== All done! ===" -ForegroundColor Green
Write-Host "To start using Loom Core:"
Write-Host "  cd $InstallDir" -ForegroundColor Yellow
Write-Host "  .\.venv\Scripts\Activate.ps1" -ForegroundColor Yellow
Write-Host "  loom version" -ForegroundColor Yellow
Write-Host "  loom tui       (launch the TUI)" -ForegroundColor Yellow
Write-Host "  loom --help    (see all commands)" -ForegroundColor Yellow

Pop-Location
