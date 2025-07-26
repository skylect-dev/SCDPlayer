# SCDPlayer Recovery & Rebuild Guide

## 🚨 Emergency Recovery Plan

If the loop point implementation fails or causes critical issues, follow this guide to restore the application to a working state.

## Quick Recovery Options

### Option 1: Git Reset (Recommended)
```bash
# Revert to last known good commit
git log --oneline -10  # Find the commit hash before loop point changes
git reset --hard <commit_hash>

# Alternative: Reset to latest GitHub version
git fetch origin
git reset --hard origin/main
```

### Option 2: GitHub Download
1. Go to: https://github.com/skylect-dev/SCDPlayer
2. Click "Code" → "Download ZIP"  
3. Extract over current directory (backup first!)
4. Reinstall dependencies: `pip install -r requirements.txt`

### Option 3: Backup Restore
```bash
# If you created a backup before changes
cp -r SCDPlayer_backup/* SCDPlayer/
```

## Full Rebuild Process

### 1. Environment Setup
```bash
# Create fresh virtual environment
python -m venv scdplayer_env
scdplayer_env\Scripts\activate  # Windows
# source scdplayer_env/bin/activate  # Linux/Mac

# Install dependencies
pip install PyQt5 soundfile numpy scipy pillow requests
```

### 2. Core Dependencies
```bash
# Ensure these are present in project root:
├── vgmstream/
│   └── vgmstream-cli.exe
├── khpc_tools/
│   └── SingleEncoder/
│       ├── MusicEncoder.exe
│       └── mass_convert.bat
└── requirements.txt
```

### 3. Test Basic Functionality
```python
# Test script - save as test_basic.py
import sys
from PyQt5.QtWidgets import QApplication
from ui.main_window import SCDPlayer

app = QApplication(sys.argv)
window = SCDPlayer()
window.show()
print("✅ Basic UI loads successfully")
app.quit()
```

### 4. Verify Core Components
```bash
# Test vgmstream
.\vgmstream\vgmstream-cli.exe -m your_file.scd

# Test MusicEncoder (if needed)
cd khpc_tools\SingleEncoder
MusicEncoder.exe --help
```

## Component-by-Component Rebuild

### Core Loop Manager (`core/loop_manager.py`)
```python
# Minimal working version - basic functionality only
class LoopPoint:
    def __init__(self, start_sample: int = 0, end_sample: int = 0):
        self.start_sample = start_sample
        self.end_sample = end_sample

class LoopPointManager:
    def __init__(self):
        self.current_loop = None
        self.sample_rate = 44100
        self.total_samples = 0
    
    def set_loop_points(self, start: int, end: int):
        self.current_loop = LoopPoint(start, end)
        return True
    
    def read_loop_metadata_from_scd(self, filepath: str):
        # Use vgmstream only - no custom parsing
        try:
            from ui.metadata_reader import LoopMetadataReader
            reader = LoopMetadataReader()
            metadata = reader.read_metadata(filepath)
            
            if metadata.get('has_loop', False):
                self.current_loop = LoopPoint(
                    metadata.get('loop_start', 0),
                    metadata.get('loop_end', 0)
                )
                return True
            return False
        except:
            return False
```

### Simplified Loop Editor (`ui/loop_editor.py`)
- Remove save functionality temporarily
- Keep only playback and visualization
- Add back features incrementally

### Progressive Feature Restoration

#### Phase 1: Basic Functionality ✅
- [x] File loading
- [x] Audio playback  
- [x] Loop point display
- [x] Basic controls

#### Phase 2: Loop Editing ✅
- [x] Loop point adjustment
- [x] Visual feedback
- [x] Precision controls
- [x] Time/sample conversion

#### Phase 3: File Operations (Current Focus)
- [x] Read existing loop points
- [x] Save to native SCD format
- [ ] Verify external tool compatibility
- [ ] Batch processing

## Known Working Configurations

### Configuration A: Minimal (Always Works)
```
- vgmstream for reading only
- No file modification
- Display and playback only
- Safe fallback mode
```

### Configuration B: Read-Only Loop Detection
```
- vgmstream reads native SCD loops
- UI displays loop points
- Playback with loop testing
- No file modification
```

### Configuration C: Full Featured (Current Goal)
```
- Native SCD loop point writing
- Complete workflow support
- Advanced precision controls
- External tool compatibility
```

## Troubleshooting Common Issues

### Import Errors
```python
# Add to top of main.py if needed
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
```

### PyQt5 Issues
```bash
# Reinstall PyQt5
pip uninstall PyQt5
pip install PyQt5==5.15.7
```

### vgmstream Problems
```bash
# Test vgmstream directly
.\vgmstream\vgmstream-cli.exe test.scd
# Should output file info without errors
```

### Audio Playback Issues
```bash
# Install audio backends
pip install pygame  # Alternative audio backend
pip install pyaudio  # Another option
```

## Testing Protocol

### Before Major Changes
1. **Create backup**: `cp -r SCDPlayer SCDPlayer_backup`
2. **Document current state**: Note what's working
3. **Test core functionality**: Verify basic features work
4. **Commit changes**: `git commit -m "Working state before X"`

### After Changes
1. **Test incrementally**: One feature at a time
2. **Verify no regressions**: Old features still work
3. **Document issues**: Note any problems immediately
4. **Create restore point**: `git commit` or backup

### Critical Tests
```bash
# Must pass before release
1. python main.py  # Launches without error
2. Load SCD file   # File loads and displays correctly
3. Play audio      # Playback works normally
4. (Optional) Save loop points  # If implemented
```

## File Structure Verification

### Essential Files
```
SCDPlayer/
├── main.py                 # Entry point
├── requirements.txt        # Dependencies
├── core/
│   ├── __init__.py
│   ├── loop_manager.py     # Loop point handling
│   └── audio_engine.py     # Audio playback
├── ui/
│   ├── __init__.py
│   ├── main_window.py      # Main interface
│   ├── loop_editor.py      # Loop editing
│   └── metadata_reader.py  # File metadata
├── vgmstream/
│   └── vgmstream-cli.exe   # Audio format support
└── utils/
    └── helpers.py          # Utility functions
```

### Optional Files (Can be removed if problematic)
```
├── khpc_tools/             # MusicEncoder workflow
├── analyze_scd.py          # Development scripts
└── *.backup               # Backup files
```

## Recovery Commands Quick Reference

```bash
# Emergency reset
git reset --hard HEAD~1

# View recent changes
git log --oneline -5
git diff HEAD~1

# Restore specific file
git checkout HEAD~1 -- core/loop_manager.py

# Clean workspace
git clean -fd  # Remove untracked files
```

## Contact & Support

If rebuild fails:
1. Check GitHub Issues: https://github.com/skylect-dev/SCDPlayer/issues
2. Review commit history for last working version
3. Consider minimal configuration until issues resolved

---

## Success Indicators ✅

After recovery/rebuild, verify:
- [x] Application launches without errors
- [x] SCD files load and display metadata
- [x] Audio playback works correctly
- [x] UI responds to user input
- [x] No file corruption occurs
- [x] Basic loop point detection works (read-only)

Once these work, loop point saving can be re-implemented incrementally.
