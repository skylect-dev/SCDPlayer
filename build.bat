@echo off
echo Building SCDPlayer executable...
echo.

REM Check for required executables
if not exist "vgmstream\vgmstream-cli.exe" (
    echo WARNING: vgmstream\vgmstream-cli.exe not found!
    echo The executable will be built without SCD support.
    echo Download vgmstream and extract all files to the vgmstream\ folder, then rebuild.
    echo.
)

if not exist "ffmpeg\ffmpeg.exe" (
    echo WARNING: ffmpeg\ffmpeg.exe not found!
    echo The executable will be built without MP3/OGG/FLAC conversion support.
    echo Download FFmpeg and extract all files to the ffmpeg\ folder for full functionality.
    echo.
)

REM Check if PyInstaller is installed
python -m pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo PyInstaller not found. Installing...
    python -m pip install pyinstaller
    echo.
)

REM Clean previous builds
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "SCDPlayer.exe" del "SCDPlayer.exe"

REM Build the executable
echo Building executable...
python -m PyInstaller SCDPlayer.spec

REM Copy the executable to the main folder
if exist "dist\SCDPlayer.exe" (
    copy "dist\SCDPlayer.exe" "SCDPlayer.exe"
    echo.
    echo Build successful! SCDPlayer.exe created.
    echo.
    if exist "vgmstream\vgmstream-cli.exe" (
        echo ✓ SCD support included (vgmstream with DLLs bundled)
    ) else (
        echo ✗ SCD support NOT included (vgmstream\ folder missing)
    )
    if exist "ffmpeg\ffmpeg.exe" (
        echo ✓ Format conversion support included (FFmpeg with DLLs bundled)
    ) else (
        echo ✗ Format conversion support NOT included (ffmpeg\ folder missing)
    )
    echo.
    echo The executable is now fully portable and self-contained!
    echo.
) else (
    echo Build failed!
    pause
    exit /b 1
)

REM Clean up build files (optional)
echo Cleaning up build files...
rmdir /s /q "build"
rmdir /s /q "dist"
rmdir /s /q "__pycache__"

echo Done!
pause
