"""Library management for audio files"""
import logging
from pathlib import Path
from typing import List, Optional
from PyQt5.QtWidgets import QListWidget, QListWidgetItem
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from utils.helpers import format_file_size


class AudioLibrary:
    """Manage audio file library scanning and organization"""
    
    SUPPORTED_EXTENSIONS = ['.scd', '.wav', '.mp3', '.ogg', '.flac']
    
    def __init__(self, file_list_widget: QListWidget, kh_rando_exporter=None, kh_rando_file_list=None, kh_categories=None):
        self.file_list = file_list_widget
        self.kh_rando_exporter = kh_rando_exporter
        self.kh_rando_file_list = kh_rando_file_list  # Single list widget for KH Rando
        self.kh_categories = kh_categories or {}  # Category mapping
        self.kh_rando_files_by_category = {}  # Store files by category for population
        
    def scan_folders(self, folders: List[str], scan_subdirs: bool = True, kh_rando_folder: str = "") -> None:
        """Scan library folders for supported audio files"""
        self.file_list.clear()
        
        # Clear KH Rando files tracking
        self.kh_rando_files_by_category = {}
        for category_key in self.kh_categories.keys():
            self.kh_rando_files_by_category[category_key] = []
        
        # Refresh KH Rando existing files cache before scanning
        if self.kh_rando_exporter:
            self.kh_rando_exporter.refresh_existing_files()
        
        # Scan regular library folders with user's subdirectory preference
        for folder in folders:
            self._scan_single_folder(Path(folder), scan_subdirs)
        
        # Scan KH Rando folder separately - always with subdirectories enabled
        if kh_rando_folder and kh_rando_folder not in folders:
            self._scan_single_folder(Path(kh_rando_folder), True)
        
        # Force update of KH Rando list after scan completion
        self._update_kh_rando_list()
    
    def _update_kh_rando_list(self):
        """Signal that KH Rando list should be updated"""
        # The main window will call _populate_kh_rando_list which reads self.kh_rando_files_by_category
        pass
    
    def _scan_single_folder(self, folder_path: Path, scan_subdirs: bool) -> None:
        """Scan a single folder for audio files"""
        try:
            if not folder_path.exists() or not folder_path.is_dir():
                logging.warning(f"Folder not found or not a directory: {folder_path}")
                return
                
            if scan_subdirs:
                # Recursively scan all subdirectories
                for file_path in folder_path.rglob('*'):
                    if file_path.is_file() and self._is_supported_file(file_path):
                        self._add_file_to_library(file_path)
            else:
                # Only scan immediate directory
                for file_path in folder_path.iterdir():
                    if file_path.is_file() and self._is_supported_file(file_path):
                        self._add_file_to_library(file_path)
                        
        except (OSError, PermissionError) as e:
            logging.warning(f"Error scanning folder {folder_path}: {e}")
    
    def _is_supported_file(self, file_path: Path) -> bool:
        """Check if file has a supported extension"""
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS
    
    def _get_kh_status(self, file_path: Path) -> tuple[str, bool]:
        """Get KH Rando status for a file"""
        if not self.kh_rando_exporter:
            return "", False
            
        filename = file_path.name
        is_in_kh_rando = False
        
        # Check if file path is within KH Rando folder
        if self.kh_rando_exporter.is_file_path_in_kh_rando(str(file_path)):
            # Extract category from path
            for part in file_path.parts:
                if part in self.kh_rando_exporter.MUSIC_CATEGORIES:
                    return f" [KH: {part}]", True
        
        # Check if filename exists in any KH Rando category
        kh_categories = self.kh_rando_exporter.is_file_in_kh_rando(filename)
        if kh_categories:
            if kh_categories == ['root']:
                return f" [KH: root folder - misplaced]", False
            else:
                # Remove 'root' from display if it's also in proper categories
                display_categories = [cat for cat in kh_categories if cat != 'root']
                if display_categories:
                    return f" [KH: {', '.join(display_categories)} - duplicate]", False
                else:
                    return f" [KH: root folder - misplaced]", False
        
        # Default case: file is not related to KH Rando
        return "", False
        
    def _add_file_to_library(self, file_path: Path) -> None:
        """Add a single file to the library list"""
        try:
            if not file_path.exists():
                return
                
            size = file_path.stat().st_size
            filename = file_path.name
            
            # Get KH Rando status
            kh_status, is_in_kh_rando = self._get_kh_status(file_path)
            
            # Create list item
            display_text = f"{filename} ({format_file_size(size)}){kh_status}"
            item = QListWidgetItem(display_text)
            item.setToolTip(str(file_path))
            item.setData(Qt.UserRole, str(file_path))
            
            # Color code items that are in KH Rando
            if kh_status:
                if is_in_kh_rando:
                    item.setForeground(QColor('lightgreen'))  # Green for files in KH Rando folder
                else:
                    item.setForeground(QColor('orange'))  # Orange for duplicates elsewhere
            
            # Check if this is a KH Rando file and should go in KH list
            if self.kh_rando_file_list and self.kh_rando_exporter:
                filename_base = filename
                added_to_kh_display = False
                
                if self.kh_rando_exporter.is_file_path_in_kh_rando(str(file_path)):
                    # File is in KH Rando folder - determine category from path
                    for part in file_path.parts:
                        if part.lower() in [cat.lower() for cat in self.kh_rando_exporter.MUSIC_CATEGORIES.keys()]:
                            # Find the correct category key
                            for cat_key in self.kh_rando_exporter.MUSIC_CATEGORIES.keys():
                                if part.lower() == cat_key.lower():
                                    if cat_key in self.kh_categories:
                                        # Add to category tracking
                                        simple_display = f"{filename} ({format_file_size(size)})"
                                        self.kh_rando_files_by_category[cat_key].append((str(file_path), simple_display))
                                        added_to_kh_display = True
                                    break
                            break
                    
                    # If file was added to KH display, don't add to regular list
                    if added_to_kh_display:
                        return
                else:
                    # Check if file exists in any KH Rando category (duplicates elsewhere)
                    kh_categories = self.kh_rando_exporter.is_file_in_kh_rando(filename_base)
                    if kh_categories:
                        # This is a duplicate - don't show in KH Rando sections, only in regular list
                        # The regular list will show the duplicate status in orange
                        pass
            
            # Add to regular library list
            self.file_list.addItem(item)
            
        except OSError as e:
            logging.warning(f"Error adding file to library {file_path}: {e}")
    
    def get_playlist(self) -> List[str]:
        """Get all files in library as a playlist"""
        playlist = []
        
        # Add files from regular library
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            file_path = item.data(Qt.UserRole)
            if file_path and not file_path.startswith("FOLDER_HEADER") and file_path not in playlist:
                playlist.append(file_path)
        
        # Add files from KH Rando list
        if self.kh_rando_file_list:
            for i in range(self.kh_rando_file_list.count()):
                item = self.kh_rando_file_list.item(i)
                file_path = item.data(Qt.UserRole)
                if file_path and not file_path.startswith("KH_CATEGORY_HEADER") and file_path not in playlist:
                    playlist.append(file_path)
        
        return playlist
    
    def find_file_index(self, file_path: str) -> int:
        """Find the index of a file in the current playlist"""
        playlist = self.get_playlist()
        try:
            return playlist.index(file_path)
        except ValueError:
            return -1
