# SCDPlayer

A Windows audio player for SCD music files from games like Kingdom Hearts and Final Fantasy XIV. Also supports WAV, MP3, OGG, and FLAC files.

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
