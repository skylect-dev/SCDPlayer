# SCDPlayer

A standalone Windows GUI application for playing SCD music files from games like Kingdom Hearts and Final Fantasy XIV.

## Features

- **Multi-format Support**: Play SCD, WAV, MP3, OGG, and FLAC files
- **Audio Library**: Scan folders for audio files with persistent settings
- **File Conversion**: Convert between different audio formats
- **Modern GUI**: Dark theme with professional audio player interface
- **Temporary File Handling**: SCD files are converted to temporary WAV files for playback

## Requirements

**For Pre-built Executable:**
- No additional requirements! Everything is bundled.

**For Running from Source:**
- Python 3.13.5 or later
- PyQt5
- **vgmstream** - Required for SCD file playback and conversion
- **FFmpeg** - Optional, for converting MP3/OGG/FLAC files

## Installation

### Option 1: Download Pre-built Executable (Recommended)
1. Go to the [Releases](https://github.com/skylect-dev/SCDPlayer/releases) page
2. Download the latest `SCDPlayer-v*.zip` file
3. Extract the ZIP file to a folder of your choice
4. Run `SCDPlayer.exe` - **Everything is already bundled!**

**No additional downloads needed!** The executable includes:
- ✅ **vgmstream** (for SCD files)  
- ✅ **FFmpeg** (for MP3/OGG/FLAC conversion)
- ✅ **All Python dependencies**

### Option 2: Run from Source
1. Install Python dependencies:
   ```
   pip install PyQt5
   ```

2. Create `vgmstream/` and `ffmpeg/` subfolders in the project directory
3. Download vgmstream and extract all files to `vgmstream/` folder
4. Download FFmpeg and extract all files to `ffmpeg/` folder

## Usage

1. Run the application:
   ```
   python main.py
   ```

2. **Add Library Folders**: Use the "Add Folder" button to scan directories for audio files
3. **Load Files**: Either use "Load File" button or double-click files in the library
4. **Convert Files**: Use the conversion buttons to convert between formats
5. **Settings Persistence**: Your library folders and preferences are automatically saved

## Supported Formats

- **SCD**: Game audio files (requires vgmstream)
- **WAV**: Standard uncompressed audio
- **MP3**: Compressed audio (requires FFmpeg for conversion)
- **OGG**: Compressed audio (requires FFmpeg for conversion)  
- **FLAC**: Lossless compressed audio (requires FFmpeg for conversion)

## Notes

- **Portable Executable**: The `.exe` version is completely self-contained with all dependencies bundled
- SCD to WAV conversion uses bundled vgmstream
- WAV to SCD conversion is currently a placeholder (copies file with .scd extension)
- Format conversions use bundled FFmpeg
- Temporary files are automatically cleaned up when the application closes

## Building from Source

If you want to build the executable yourself:

1. Install dependencies: `pip install PyQt5 pyinstaller`
2. Create `vgmstream/` and `ffmpeg/` folders
3. Extract vgmstream files to `vgmstream/` folder (ensure `vgmstream-cli.exe` is present)
4. Extract FFmpeg files to `ffmpeg/` folder  
5. Run `build.bat` or `build.ps1`
6. The resulting `SCDPlayer.exe` will be completely portable
