# Contributing to SCDPlayer

Thank you for your interest in contributing to SCDPlayer! This guide will help you get started.

## Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/skylect-dev/SCDPlayer.git
   cd SCDPlayer
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up external dependencies:**
   
   **For vgmstream:**
   - Download from: https://github.com/vgmstream/vgmstream/releases
   - Create `vgmstream/` folder in project root
   - Extract all files to `vgmstream/` folder

   **For FFmpeg (optional):**
   - Download from: https://ffmpeg.org/download.html
   - Create `ffmpeg/` folder in project root  
   - Extract all files to `ffmpeg/` folder

4. **Test the setup:**
   ```bash
   python main.py
   ```

## Project Structure

```
SCDPlayer/
├── main.py                 # Main application
├── version.py              # Version information
├── requirements.txt        # Python dependencies
├── SCDPlayer.spec          # PyInstaller configuration
├── build.bat/.ps1          # Build scripts
├── .github/workflows/      # GitHub Actions
├── vgmstream/             # External dependency (not in git)
├── ffmpeg/                # External dependency (not in git)
└── docs/                  # Documentation
```

## Building

To build the executable:

1. **Windows Batch:**
   ```bash
   build.bat
   ```

2. **PowerShell:**
   ```bash
   ./build.ps1
   ```

3. **Manual:**
   ```bash
   python -m PyInstaller SCDPlayer.spec
   ```

## Code Style

- Follow PEP 8 style guidelines
- Use descriptive variable names
- Add docstrings to functions and classes
- Keep functions focused and small

## Testing

Before submitting changes:

1. Test with various SCD files
2. Test with different audio formats (WAV, MP3, OGG, FLAC)
3. Test library scanning functionality
4. Test conversion features
5. Ensure the built executable works

## Pull Requests

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Reporting Issues

When reporting issues, please include:

- Operating System and version
- Python version
- Steps to reproduce
- Expected vs actual behavior
- Screenshots if relevant
- Sample files (if safe to share)

## External Dependencies

**Note:** vgmstream and FFmpeg are NOT included in the repository due to:
- Large file sizes
- Licensing considerations
- Frequent updates

These are downloaded automatically during CI builds and must be set up manually for development.

Thank you for contributing!
