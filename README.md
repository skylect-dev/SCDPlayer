# SCDToolkit

A Windows audio player and toolkit designed for game music files (SCD format) with Kingdom Hearts Randomizer integration. Also plays WAV, MP3, OGG, and FLAC files.

## Bugs
- When updating from a version named SCDPlayer (pre 3.3.1) the updater will not work properly.
- This is resolved in 3.3.1 and up. Please download the full package to update from this version. 
- **You may copy you scdplayer_config.json to the new folder and SCDToolkit will migrate it**

### SCDToolkit has a [Discord](https://discord.gg/FqePtT2BBM) now!

## Features

- **Game Audio Support**: Native SCD file playback from Kingdom Hearts, Final Fantasy XIV, and other games
- **Library Management**: Organize files by folder with search and filtering
- **Kingdom Hearts II Randomizer Integration**: Export music directly to Kingdom Hearts Randomizer folders
- **Kingdom Hearts II Re:Fined Music Pack Creation:** Directly create custom Music Pack mods to be used with Kingdom Hearts II - Re:Fined. 
- **Format Conversion**: Convert between SCD, WAV, MP3, OGG, and FLAC formats
- **Loop Editor**: Professional waveform editor for setting precise loop points
- **Auto-Updates**: Built-in update system keeps you current
- **Recycle Bin Safety**: File deletion uses Windows Recycle Bin for safety

## Batch Normalization: ## 
Normalize volume levels across multiple files directly from the library. This will apply a consistent loudness level to all selected tracks, ensuring a uniform listening experience while in-game.
- **Auto Normalization**: Intelligent volume normalization based on audio characteristics. Targets -12 LUFS with True Peak of -1 dBTP.
- **SCD HEX Float Patching**: Applies float patch directly to SCD files to ensure in-game volume consistency.
- **Caching**: Processed files are cached for faster future access. Run a batch normalization to pre-cache files and speed up exporting.
    - Cached files are automatically reused unless source files change.
    - Cache can be cleared from main window.
    - Cached files export faster since they skip re-processing.
    - Setting personalized loudness levels in the Loop Editor marks files as "sanitized" to skip re-normalization during export.

## Installation

**Download & Run (Recommended):**
1. Get the latest version from [Releases](https://github.com/skylect-dev/SCDToolkit/releases)
2. Extract `SCDToolkit-Windows.zip`
3. Run `SCDToolkit.exe`

Everything needed is included - no additional setup required.

**Note for SCD Conversion:**
- Converting files **to** SCD format requires .NET 5.0 Desktop Runtime
- SCDToolkit will automatically prompt to install it when needed (one-time setup)
- .NET 5.0 Desktop Runtime installer is bundled with SCDToolkit
- All other features work without .NET

## Quick Start

1. Launch SCDToolkit
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
git clone https://github.com/skylect-dev/SCDToolkit.git
cd SCDToolkit
pip install -r requirements.txt
pyinstaller SCDToolkit.spec
```

## Acknowledgments

Thanks to the KHReFined, KHRando, and OpenKH Discord communities for feedback and suggestions!
Special thanks to TopazTK for support and suggestions!
Special thanks to PunningLinguist for identifying the vgmstream loop issue!

## License

MIT License
