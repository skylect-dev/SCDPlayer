# SCDPlayer Icon System

## Simple Icon Customization

SCDPlayer now uses a simple, file-based icon system. The application automatically loads icons from SVG files.

### How to Change the Icon

1. **Replace the SVG file**: Simply replace `assets/icon.svg` with your own SVG file
2. **Restart the application**: The new icon will be loaded automatically
3. **No conversion needed**: The application reads SVG files directly

### Icon Requirements

- **Format**: SVG (Scalable Vector Graphics)
- **Recommended size**: 64x64 viewBox for optimal scaling
- **Colors**: Any colors work, but consider the application's dark theme

### Current Icon Features

The default icon includes:
- Musical note (quarter note with stem and flag)
- Sound waves indicating audio playback
- Waveform visualization at the bottom
- Professional blue color scheme (#4a9eff, #6bb6ff)
- Dark background circle (#2a2a2a)

### Files

- `assets/icon.svg` - Main icon file (replace this to customize)
- `generate_icons.py` - Optional script (informational only)
- `ui/widgets.py` - Contains the icon loading code

### Technical Details

The icon system uses PyQt5's QSvgRenderer to load SVG files directly, providing:
- Crisp scaling at any size (16px to 256px+)
- No pre-generation required
- Automatic fallback to simple icon if SVG fails to load
- Support for all SVG features supported by Qt
