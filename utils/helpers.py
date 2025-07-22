"""Path and file utilities for SCDPlayer"""
import sys
import os
import tempfile
from typing import List, Optional


def get_bundled_path(subfolder: str, filename: str) -> str:
    """Get the path to a bundled executable in a subfolder, 
    handling both development and PyInstaller modes"""
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller executable
        bundle_dir = sys._MEIPASS
        return os.path.join(bundle_dir, subfolder, filename)
    else:
        # Running in development mode
        return os.path.join(os.getcwd(), subfolder, filename)


def create_temp_wav() -> str:
    """Create a temporary WAV file path"""
    fd, wav_path = tempfile.mkstemp(
        suffix='.wav', 
        prefix='scdplayer_', 
        dir=tempfile.gettempdir()
    )
    os.close(fd)
    return wav_path


def cleanup_temp_files(temp_files: List[str]) -> None:
    """Clean up temporary files"""
    for temp_file in temp_files:
        try:
            os.remove(temp_file)
        except Exception:
            pass


def format_time(seconds: int) -> str:
    """Format seconds as MM:SS"""
    m, s = divmod(seconds, 60)
    return f'{int(m):02}:{int(s):02}'


def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes // 1024} KB"
    else:
        return f"{size_bytes // (1024 * 1024)} MB"
