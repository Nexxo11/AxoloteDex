$ErrorActionPreference = "Stop"

# Build AxoloteDex as compact Windows EXE (onefile, windowed)
# Run this script on Windows with Python 3.11+ installed.

if (-not (Test-Path ".venv")) {
    py -3 -m venv .venv
}

& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-windows-build.txt

if (Test-Path "build") { Remove-Item "build" -Recurse -Force }
if (Test-Path "dist") { Remove-Item "dist" -Recurse -Force }

pyinstaller --noconfirm --clean --onefile --windowed --name "AxoloteDex" app\gui_app.py

Write-Host ""
Write-Host "Build complete: dist\AxoloteDex.exe"
