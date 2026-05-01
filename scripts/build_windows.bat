@echo off
setlocal

REM Build AxoloteDex as compact Windows EXE (onefile, windowed)
REM Run this script on Windows with Python 3.11+ installed.

if not exist .venv (
  py -3 -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements-windows-build.txt

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

pyinstaller --noconfirm --clean --onefile --windowed --name "AxoloteDex" app\gui_app.py

echo.
echo Build complete: dist\AxoloteDex.exe
endlocal
