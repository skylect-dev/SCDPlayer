# Contributing to SCDPlayer

Thank you for contributing to SCDPlayer! This guide will help you get started with development.

## Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/skylect-dev/SCDPlayer.git
   cd SCDPlayer
   ```

2. **Install Python dependencies:**
   ```bash
   pip install PyQt5 pyinstaller
   ```

3. **Set up external dependencies:**
   
   Create folders and download dependencies:
   - **vgmstream/**: Download from [vgmstream releases](https://github.com/vgmstream/vgmstream/releases)
   - **ffmpeg/**: Download from [FFmpeg](https://ffmpeg.org/download.html) - extract to `ffmpeg/bin/`

   See DEVELOPMENT.txt for detailed setup instructions.

4. **Test the setup:**
   ```bash
   python main.py
   ```

## Project Structure

```
SCDPlayer/
├── main.py                 # Main application with GUI
├── version.py              # Version information  
├── DEVELOPMENT.txt         # Detailed setup guide
├── SCDPlayer.spec          # PyInstaller build config
├── build.bat/.ps1          # Build scripts
├── .github/workflows/      # Automated CI/CD
├── vgmstream/             # SCD conversion tools (not in git)
├── ffmpeg/                # Audio conversion tools (not in git)
└── README.md              # User documentation
```

## Development Workflow

**Branch Strategy:**
- `main`: Stable releases only
- `dev`: Active development 
- `feature/name`: New features

**Making Changes:**
1. Fork the repository
2. Create feature branch from `dev`: `git checkout -b feature/your-feature`
3. Make your changes
4. Test thoroughly
5. Submit PR to `dev` branch

**Code Guidelines:**
- Follow PEP 8 style guidelines
- Add docstrings to new functions
- Test with various audio files
- Ensure UI remains responsive

## Building

**Requirements:**
- Python 3.7+ with pip
- Required Python packages: `pip install -r requirements.txt`
- FFmpeg: Download from https://ffmpeg.org and extract to `ffmpeg/bin/ffmpeg.exe`
- VGMStream: Download from https://github.com/vgmstream/vgmstream and extract to `vgmstream/vgmstream.exe`

**Build the standalone executable:**

```bash
# Install PyInstaller
pip install pyinstaller

# Build executable
pyinstaller SCDPlayer.spec

# Executable will be in dist/SCDPlayer/
```

**File Structure Required:**
```
SCDPlayer/
├── assets/
├── ffmpeg/bin/ffmpeg.exe
├── vgmstream/vgmstream.exe
└── dist/SCDPlayer/ (after build)
```

## Testing

Test these scenarios before submitting:
- SCD file playback and conversion
- MP3/OGG/FLAC playback (auto-conversion to WAV)
- Library folder scanning
- Auto-play and playlist advancement
- UI responsiveness during file loading
- Built executable functionality

## Features Overview

**Current Features:**
- Multi-format audio playback (SCD, WAV, MP3, OGG, FLAC)
- Professional dark theme with splash screen
- Auto-play and playlist management
- Smart codec handling (MP3 → WAV conversion)
- Library folder scanning
- Audio format conversion
- Scrolling track titles

## Reporting Issues

Include in your issue report:
- Windows version
- Audio file format and source
- Steps to reproduce
- Screenshots if helpful
- Error messages or logs

## External Dependencies

**vgmstream** and **FFmpeg** are not in the repository due to size and licensing. They're downloaded during automated builds and must be set up manually for development.

Thanks for contributing!
