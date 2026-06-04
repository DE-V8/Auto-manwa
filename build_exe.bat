@echo off
setlocal enabledelayedexpansion
title AtoManwa - Build EXE

echo =====================================================
echo   ATO MANWA - BUILD TOOL
echo   This will create a distributable Windows .exe
echo =====================================================
echo.

REM --- Check virtual environment ---
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found at .venv\
    echo         Please run:  python -m venv .venv
    echo         Then:        .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

echo [1/4] Installing PyInstaller into venv...
.venv\Scripts\pip install pyinstaller --quiet
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install PyInstaller.
    pause
    exit /b 1
)
echo       PyInstaller ready.
echo.

echo [2/4] Installing UPX (optional compressor)...
REM UPX reduces exe size by ~30%. Download separately if you want it.
REM If not found, PyInstaller still works fine without it.
where upx >nul 2>&1
if %errorlevel% equ 0 (
    echo       UPX found - compression will be applied.
) else (
    echo       UPX not found - skipping compression (exe will be slightly larger).
)
echo.

echo [3/4] Building with PyInstaller...
echo       This may take 2-5 minutes on first run...
echo.

.venv\Scripts\pyinstaller AtoManwa.spec --clean --noconfirm

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Build failed! Check the output above for errors.
    pause
    exit /b 1
)

echo.
echo [4/4] Build complete!
echo.
echo =====================================================
echo   OUTPUT LOCATION:
echo   dist\AtoManwa\AtoManwa.exe
echo.
echo   To distribute:
echo   Zip the entire  dist\AtoManwa\  folder and share it.
echo   The user just extracts and runs AtoManwa.exe
echo =====================================================
echo.

REM Open the output folder automatically
if exist "dist\AtoManwa\" (
    start "" "dist\AtoManwa\"
)

pause
