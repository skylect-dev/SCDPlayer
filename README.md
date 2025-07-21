# SCDPlayer

A Windows audio player for SCD music files from games like Kingdom Hearts and Final Fantasy XIV. Also supports WAV, MP3, OGG, and FLAC files.

## Features

- Play SCD, WAV, MP3, OGG, and FLAC audio files
- Modern dark interface with splash screen
- Audio library with folder scanning
- Auto-play and playlist functionality
- Convert between audio formats
- Scrolling track titles for long filenames
- All dependencies bundled in executable

## Installation

**Download the executable (recommended):**
1. Go to [Releases](https://github.com/skylect-dev/SCDPlayer/releases)
2. Download `SCDPlayer-v1.0.2.zip`
3. Extract and run `SCDPlayer.exe`

No additional setup needed - everything is included.

**Run from source:**
```bash
git clone https://github.com/skylect-dev/SCDPlayer.git
cd SCDPlayer
pip install PyQt5
python main.py
```

You'll also need to download vgmstream and FFmpeg to the appropriate folders.

## Usage

1. Launch SCDPlayer
2. Add folders containing your audio files
3. Double-click any file to play
4. Use the conversion buttons to convert files between formats

The app remembers your library folders and settings.

## Technical Notes

- SCD conversion uses vgmstream
- MP3/OGG/FLAC conversion uses FFmpeg  
- MP3 files are automatically converted to WAV for reliable playback
- Tracks auto-advance when finished

## Building

To build your own executable:
```bash
pip install PyInstaller
pyinstaller scdplayer.spec
```

## License

MIT License - see LICENSE file for details.
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
