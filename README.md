# SCDPlayer

A Windows audio player designed for game music files (SCD format) with Kingdom Hearts Randomizer integration. Also plays WAV, MP3, OGG, and FLAC files.

## Features

- **Game Audio Support**: Native SCD file playback from Kingdom Hearts, Final Fantasy XIV, and other games
- **Library Management**: Organize files by folder with search and filtering
- **KH Randomizer Integration**: Export music directly to Kingdom Hearts Randomizer folders
- **Format Conversion**: Convert between SCD, WAV, MP3, OGG, and FLAC formats
- **Loop Editor**: Professional waveform editor for setting precise loop points
- **Auto-Updates**: Built-in update system keeps you current
- **Recycle Bin Safety**: File deletion uses Windows Recycle Bin for safety

## Installation

**Download & Run (Recommended):**
1. Get the latest version from [Releases](https://github.com/skylect-dev/SCDPlayer/releases)
2. Extract `SCDPlayer-vX.X.X.zip`
3. Run `SCDPlayer.exe`

Everything needed is included - no additional setup required.

**Note for SCD Conversion:**
- Converting files **to** SCD format requires .NET 5.0 Desktop Runtime
- SCDPlayer will automatically prompt to install it when needed (one-time setup)
- Or download manually: [.NET 5.0 Runtime](https://dotnet.microsoft.com/download/dotnet/5.0)
- All other features work without .NET

## Quick Start

1. Launch SCDPlayer
2. Click "Add Folder" to add your music folders
3. Double-click any file to play
4. Use the search box to find specific tracks
5. Select files and use conversion/export buttons as needed

Your library and settings are automatically saved.

## Building from Source

**Requirements:**
- Python 3.7+ with `pip install PyQt5 pyinstaller`
- Download [vgmstream](https://github.com/vgmstream/vgmstream/releases) to `vgmstream/` folder
- Download [FFmpeg](https://ffmpeg.org/download.html) to `ffmpeg/` folder

**Build:**
```bash
git clone https://github.com/skylect-dev/SCDPlayer.git
cd SCDPlayer
pip install -r requirements.txt
pyinstaller SCDPlayer.spec
```

## Acknowledgments

Thanks to the KHRando Discord community for feedback and suggestions!

## License

MIT License
