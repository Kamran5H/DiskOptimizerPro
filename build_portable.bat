@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found. Install Python 3.10 or newer and try again.
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 exit /b 1
)

".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --windowed --name DiskOptimizerPro --collect-all customtkinter --add-data "assets;assets" main.py
if errorlevel 1 exit /b 1

echo.
echo Portable app created in dist\DiskOptimizerPro
echo Zip the entire folder and send it to another Windows 10/11 PC.
echo No Python installation is needed on the receiving PC.
endlocal
