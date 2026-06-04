@echo off
cd /d "%~dp0"
echo Launching Hindi Manhwa Shorts GUI...

:: Ensure FFmpeg is available in PATH
set "FFMPEG_BIN=C:\Users\debji\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin"
if exist "%FFMPEG_BIN%\ffmpeg.exe" (
    set "PATH=%FFMPEG_BIN%;%PATH%"
    echo [OK] FFmpeg 8.1.1 found and added to PATH.
) else (
    echo [WARNING] FFmpeg not found at expected path. GPU check may fail.
)

call .venv\Scripts\activate.bat
python gui.py
pause
