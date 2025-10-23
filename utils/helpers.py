"""Path and file utilities for SCDToolkit"""
import sys
import os
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
        prefix='scdtoolkit_', 
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


def send_to_recycle_bin(file_path: str) -> bool:
    """Send a file to the recycle bin instead of permanently deleting it.
    
    Args:
        file_path: Path to the file to delete
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # First try using send2trash library if available
        try:
            import send2trash
            send2trash.send2trash(file_path)
            return True
        except ImportError:
            pass
        
        # Fallback to Windows Shell API
        if sys.platform == 'win32':
            try:
                import ctypes
                from ctypes import wintypes
                
                # Use Windows Shell API to move file to recycle bin
                # This is the equivalent of right-click -> Delete
                shell32 = ctypes.windll.shell32
                
                # Define the structure for SHFILEOPSTRUCT
                class SHFILEOPSTRUCT(ctypes.Structure):
                    _fields_ = [
                        ("hwnd", wintypes.HWND),
                        ("wFunc", wintypes.UINT),
                        ("pFrom", wintypes.LPCWSTR),
                        ("pTo", wintypes.LPCWSTR),
                        ("fFlags", wintypes.WORD),
                        ("fAnyOperationsAborted", wintypes.BOOL),
                        ("hNameMappings", wintypes.LPVOID),
                        ("lpszProgressTitle", wintypes.LPCWSTR)
                    ]
                
                # Constants
                FO_DELETE = 0x0003
                FOF_ALLOWUNDO = 0x0040  # Allow undo (send to recycle bin)
                FOF_NO_UI = 0x0004      # No user interface
                FOF_NOCONFIRMATION = 0x0010  # No confirmation dialog
                
                # Prepare the operation
                fileop = SHFILEOPSTRUCT()
                fileop.wFunc = FO_DELETE
                fileop.pFrom = file_path + '\0'  # Must be null-terminated
                fileop.fFlags = FOF_ALLOWUNDO | FOF_NO_UI | FOF_NOCONFIRMATION
                
                # Perform the operation
                result = shell32.SHFileOperationW(ctypes.byref(fileop))
                return result == 0
                
            except Exception as e:
                logging.warning(f"Windows Shell API failed for {file_path}: {e}")
        
        # Final fallback - use os.remove (permanent deletion)
        logging.warning(f"Could not send {file_path} to recycle bin, using permanent deletion")
        os.remove(file_path)
        return True
        
    except Exception as e:
        logging.error(f"Failed to delete {file_path}: {e}")
        return False
