# .NET 5.0 Runtime Bundling Instructions

## For Release Distribution

To provide the best user experience, bundle the .NET 5.0 Desktop Runtime installer with SCDPlayer releases.

### Download the Installer

**Download Link:** https://download.visualstudio.microsoft.com/download/pr/c6a74d6b-576c-4ab0-bf55-d46d45610730/f70d2252c9f452c2eb679b8041846466/windowsdesktop-runtime-5.0.17-win-x64.exe

**File:** `windowsdesktop-runtime-5.0.17-win-x64.exe` (~54 MB)

### Where to Place It

Option 1 (Recommended): Create a `dotnet_installer` folder in your distribution:
```
SCDPlayer/
├── SCDPlayer.exe
├── dotnet_installer/
│   └── windowsdesktop-runtime-5.0.17-win-x64.exe
├── ...
```

Option 2: Place it in the root directory:
```
SCDPlayer/
├── SCDPlayer.exe
├── windowsdesktop-runtime-5.0.17-win-x64.exe
├── ...
```

### How It Works

1. When a user tries to convert to SCD format, SCDPlayer automatically checks for .NET 5.0
2. If not found:
   - If bundled installer exists → Offers to run it automatically
   - If no bundled installer → Offers to download and install from Microsoft
3. Installation is silent and takes ~1 minute
4. After installation, SCD conversion works normally

### User Experience

- **First-time SCD conversion:** User sees a dialog asking to install .NET 5.0
- **One-time setup:** After installation, no more prompts
- **No manual steps:** Everything is automated

### Alternative: No Bundling

If you prefer not to bundle the installer (to keep distribution size smaller):
- SCDPlayer will automatically download it from Microsoft when needed
- Download is ~50 MB and takes a few minutes depending on connection
- Still fully automatic, just slightly longer first-time setup

### Testing

To test the .NET installation flow:
1. Temporarily rename `dotnet.exe` if you have .NET installed
2. Try converting a file to SCD
3. The installer prompt should appear
4. After installation, conversion should work

### Notes

- .NET 5.0 is required only for **SCD conversion** (WAV→SCD)
- All other features work without .NET
- The installer is the official Microsoft Windows Desktop Runtime
- Silent install uses `/quiet /norestart` flags
- Installation size on disk: ~180 MB
