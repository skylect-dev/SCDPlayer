"""Path and file utilities for SCDPlayer"""
import sys
import logging
import tempfile
from pathlib import Path
from typing import List, Optional


def get_bundled_path(subfolder: str, filename: Optional[str] = None) -> str:
    """Get the path to a bundled executable or directory,
    handling both development and PyInstaller modes"""
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller executable
        bundle_dir = Path(sys._MEIPASS)
        if filename:
            return str(bundle_dir / subfolder / filename)
        else:
            return str(bundle_dir / subfolder)
    else:
        # Running in development mode
        if filename:
            return str(Path.cwd() / subfolder / filename)
        else:
            return str(Path.cwd() / subfolder)


def create_temp_wav() -> str:
    """Create a temporary WAV file path"""
    fd, wav_path = tempfile.mkstemp(
        suffix='.wav', 
        prefix='scdplayer_', 
        dir=tempfile.gettempdir()
    )
    # Close the file descriptor immediately since we only need the path
    try:
        import os
        os.close(fd)
    except OSError:
        pass
    return wav_path


def cleanup_temp_files(temp_files: List[str]) -> None:
    """Clean up temporary files"""
    for temp_file in temp_files:
        try:
            Path(temp_file).unlink(missing_ok=True)
        except Exception as e:
            logging.warning(f"Failed to delete temp file {temp_file}: {e}")


def format_time(seconds: int) -> str:
    """Format seconds as MM:SS"""
    m, s = divmod(int(seconds), 60)
    return f'{m:02}:{s:02}'


def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
