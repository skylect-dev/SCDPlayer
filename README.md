# SCDPlayer

A Windows audio player for SCD music files from games like Kingdom Hearts and Final Fantasy XIV. Also supports WAV, MP3, OGG, and FLAC files.

## Acknowledgements
Thank you to the awesome people at the KHRando Discord for some great suggestions and encouragement on this project!

## Installation

**Download the executable (recommended):**
1. Go to [Releases](https://github.com/skylect-dev/SCDPlayer/releases)
2. Download `SCDPlayer-vX.X.X.zip`
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
2. Add folders containing your audio files using the "Add Folder" button
3. Double-click any file in the library to play
4. Use the conversion buttons to convert files between formats
5. Your library folders and preferences are automatically saved

## Supported Formats

- **SCD**: Game audio files (requires vgmstream)
- **WAV**: Standard uncompressed audio
- **MP3**: Compressed audio (requires FFmpeg for conversion)
- **OGG**: Compressed audio (requires FFmpeg for conversion)  
- **FLAC**: Lossless compressed audio (requires FFmpeg for conversion)

## Technical Notes

- **Portable Executable**: The `.exe` version is completely self-contained with all dependencies bundled
- SCD to WAV conversion uses bundled vgmstream
- WAV to SCD conversion is currently a placeholder (copies file with .scd extension)
- Format conversions use bundled FFmpeg
- MP3 files are automatically converted to WAV for reliable playback
- Tracks auto-advance when finished
- Temporary files are automatically cleaned up when the application closes

## Building from Source

If you want to build the executable yourself:

**Prerequisites:**
1. Python 3.7+ with PyQt5 installed: `pip install PyQt5 pyinstaller`
2. **vgmstream** (for SCD support): 
   - Download from [vgmstream releases](https://github.com/vgmstream/vgmstream/releases)
   - Extract all files to `vgmstream/` folder
   - Ensure `vgmstream-cli.exe` is present
3. **FFmpeg** (for format conversion):
   - Download from [FFmpeg](https://ffmpeg.org/download.html)
   - Extract to `ffmpeg/` folder (maintaining the `bin/`, `lib/`, etc. structure)
   - Ensure `ffmpeg/bin/ffmpeg.exe` is present

**Build Steps:**
```bash
# Clone and navigate to project
git clone https://github.com/skylect-dev/SCDPlayer.git
cd SCDPlayer

# Install Python dependencies
pip install PyQt5 pyinstaller

# Set up vgmstream and ffmpeg folders (see above)

# Build the executable
pyinstaller SCDPlayer.spec

# The executable will be in dist/SCDPlayer/SCDPlayer.exe
```

The resulting executable is completely portable and self-contained!

## License

MIT License - see LICENSE file for details.
