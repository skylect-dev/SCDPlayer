"""Library management for audio files"""
import os
from typing import List
from PyQt5.QtWidgets import QListWidget, QListWidgetItem
from PyQt5.QtCore import Qt
from utils.helpers import format_file_size


class AudioLibrary:
    """Manage audio file library scanning and organization"""
    
    SUPPORTED_EXTENSIONS = ['.scd', '.wav', '.mp3', '.ogg', '.flac']
    
    def __init__(self, file_list_widget: QListWidget):
        self.file_list = file_list_widget
        
    def scan_folders(self, folders: List[str], scan_subdirs: bool = True) -> None:
        """Scan library folders for supported audio files"""
        self.file_list.clear()
        
        for folder in folders:
            try:
                if scan_subdirs:
                    for root, _, files in os.walk(folder):
                        for f in files:
                            if any(f.lower().endswith(ext) for ext in self.SUPPORTED_EXTENSIONS):
                                full_path = os.path.join(root, f)
                                self._add_file_to_library(full_path)
                else:
                    for f in os.listdir(folder):
                        if any(f.lower().endswith(ext) for ext in self.SUPPORTED_EXTENSIONS):
                            full_path = os.path.join(folder, f)
                            self._add_file_to_library(full_path)
            except (OSError, PermissionError):
                continue
    
    def _add_file_to_library(self, file_path: str) -> None:
        """Add a single file to the library list"""
        try:
            size = os.path.getsize(file_path)
            item = QListWidgetItem(f"{os.path.basename(file_path)} ({format_file_size(size)})")
            item.setToolTip(file_path)
            item.setData(Qt.UserRole, file_path)
            self.file_list.addItem(item)
        except OSError:
            pass
    
    def get_playlist(self) -> List[str]:
        """Get all files in library as a playlist"""
        playlist = []
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            playlist.append(item.data(Qt.UserRole))
        return playlist
    
    def find_file_index(self, file_path: str) -> int:
        """Find the index of a file in the current playlist"""
        playlist = self.get_playlist()
        try:
            return playlist.index(file_path)
        except ValueError:
            return -1
