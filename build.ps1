# SCDPlayer Build Script
Write-Host "Building SCDPlayer executable..." -ForegroundColor Green
Write-Host ""

# Check for required executables
if (-not (Test-Path "vgmstream\vgmstream-cli.exe")) {
    Write-Host "WARNING: vgmstream\vgmstream-cli.exe not found!" -ForegroundColor Yellow
    Write-Host "The executable will be built without SCD support." -ForegroundColor Yellow
    Write-Host "Download vgmstream and extract all files to the vgmstream\ folder, then rebuild." -ForegroundColor Yellow
    Write-Host ""
}

if (-not (Test-Path "ffmpeg\ffmpeg.exe")) {
    Write-Host "WARNING: ffmpeg\ffmpeg.exe not found!" -ForegroundColor Yellow
    Write-Host "The executable will be built without MP3/OGG/FLAC conversion support." -ForegroundColor Yellow
    Write-Host "Download FFmpeg and extract all files to the ffmpeg\ folder for full functionality." -ForegroundColor Yellow
    Write-Host ""
}

# Check if PyInstaller is installed
$pyinstaller = python -m pip show pyinstaller 2>$null
if (!$pyinstaller) {
    Write-Host "PyInstaller not found. Installing..." -ForegroundColor Yellow
    python -m pip install pyinstaller
    Write-Host ""
}

# Clean previous builds
Write-Host "Cleaning previous builds..." -ForegroundColor Yellow
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
if (Test-Path "SCDPlayer.exe") { Remove-Item "SCDPlayer.exe" }

# Build the executable
Write-Host "Building executable..." -ForegroundColor Yellow
python -m PyInstaller SCDPlayer.spec

# Check if build was successful
if (Test-Path "dist\SCDPlayer.exe") {
    Copy-Item "dist\SCDPlayer.exe" "SCDPlayer.exe"
    Write-Host ""
    Write-Host "Build successful! SCDPlayer.exe created." -ForegroundColor Green
    Write-Host ""
    
    if (Test-Path "vgmstream\vgmstream-cli.exe") {
        Write-Host "✓ SCD support included (vgmstream with DLLs bundled)" -ForegroundColor Green
    } else {
        Write-Host "✗ SCD support NOT included (vgmstream\ folder missing)" -ForegroundColor Red
    }
    
    if (Test-Path "ffmpeg\ffmpeg.exe") {
        Write-Host "✓ Format conversion support included (FFmpeg with DLLs bundled)" -ForegroundColor Green
    } else {
        Write-Host "✗ Format conversion support NOT included (ffmpeg\ folder missing)" -ForegroundColor Red
    }
    
    Write-Host ""
    Write-Host "The executable is now fully portable and self-contained!" -ForegroundColor Cyan
    Write-Host ""
} else {
    Write-Host "Build failed!" -ForegroundColor Red
    Read-Host "Press Enter to continue"
    exit 1
}

# Clean up build files
Write-Host "Cleaning up build files..." -ForegroundColor Yellow
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
if (Test-Path "__pycache__") { Remove-Item -Recurse -Force "__pycache__" }

Write-Host "Done!" -ForegroundColor Green
Read-Host "Press Enter to continue"
