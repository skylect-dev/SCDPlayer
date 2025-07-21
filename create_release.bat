@echo off
echo SCDPlayer Releas# Create dependencies note
echo SCDPlayer v%VERSION% - Portable Audio Player > "SCDPlayer-v%VERSION%\README.txt"
echo ================================================= >> "SCDPlayer-v%VERSION%\README.txt"
echo. >> "SCDPlayer-v%VERSION%\README.txt"
echo This is a completely self-contained, portable version of SCDPlayer. >> "SCDPlayer-v%VERSION%\README.txt"
echo No additional downloads or installations are required! >> "SCDPlayer-v%VERSION%\README.txt"
echo. >> "SCDPlayer-v%VERSION%\README.txt"
echo INCLUDED FEATURES: >> "SCDPlayer-v%VERSION%\README.txt"
echo - Full SCD file support (vgmstream bundled) >> "SCDPlayer-v%VERSION%\README.txt"
echo - Multi-format conversion (FFmpeg bundled) >> "SCDPlayer-v%VERSION%\README.txt"
echo - Support for SCD, WAV, MP3, OGG, and FLAC files >> "SCDPlayer-v%VERSION%\README.txt"
echo - Audio library with folder scanning >> "SCDPlayer-v%VERSION%\README.txt"
echo - Modern dark theme GUI >> "SCDPlayer-v%VERSION%\README.txt"
echo. >> "SCDPlayer-v%VERSION%\README.txt"
echo USAGE: >> "SCDPlayer-v%VERSION%\README.txt"
echo Simply run SCDPlayer.exe - no setup required! >> "SCDPlayer-v%VERSION%\README.txt"
echo. >> "SCDPlayer-v%VERSION%\README.txt"
echo For more information, see the included documentation files. >> "SCDPlayer-v%VERSION%\README.txt"Creator
echo ====================================

set /p VERSION="Enter version number (e.g., 1.0.0): "
if "%VERSION%"=="" (
    echo No version specified. Exiting.
    pause
    exit /b 1
)

echo.
echo Building SCDPlayer v%VERSION%...

REM Build the executable
call build.bat

if not exist "SCDPlayer.exe" (
    echo Build failed! Executable not found.
    pause
    exit /b 1
)

REM Create release folder
if exist "SCDPlayer-v%VERSION%" rmdir /s /q "SCDPlayer-v%VERSION%"
mkdir "SCDPlayer-v%VERSION%"

REM Copy files
copy "SCDPlayer.exe" "SCDPlayer-v%VERSION%\"
copy "README.md" "SCDPlayer-v%VERSION%\"
copy "QUICKSTART.txt" "SCDPlayer-v%VERSION%\"

REM Create dependencies note
echo Place the following files in this folder for full functionality: > "SCDPlayer-v%VERSION%\DEPENDENCIES.txt"
echo. >> "SCDPlayer-v%VERSION%\DEPENDENCIES.txt"
echo REQUIRED: >> "SCDPlayer-v%VERSION%\DEPENDENCIES.txt"
echo - test.exe (from vgmstream) - Required for SCD file support >> "SCDPlayer-v%VERSION%\DEPENDENCIES.txt"
echo   Download from: https://github.com/vgmstream/vgmstream/releases >> "SCDPlayer-v%VERSION%\DEPENDENCIES.txt"
echo. >> "SCDPlayer-v%VERSION%\DEPENDENCIES.txt"
echo OPTIONAL: >> "SCDPlayer-v%VERSION%\DEPENDENCIES.txt"
echo - ffmpeg.exe - Required for MP3/OGG/FLAC conversion >> "SCDPlayer-v%VERSION%\DEPENDENCIES.txt"
echo   Download from: https://ffmpeg.org/download.html >> "SCDPlayer-v%VERSION%\DEPENDENCIES.txt"

echo.
echo Release package created: SCDPlayer-v%VERSION%\
echo.
echo To create a ZIP for distribution:
echo 1. Right-click the SCDPlayer-v%VERSION% folder
echo 2. Select "Send to" > "Compressed (zipped) folder"
echo.
pause
