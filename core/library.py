"""Library management for audio files"""
import logging
import os
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
        self.progress_callback = None  # Callback for progress updates
        
    def set_progress_callback(self, callback):
        """Set callback function for progress updates: callback(current, total, filename)"""
        self.progress_callback = callback
        
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
        
        # Pre-compute KH Rando path for faster checking
        kh_rando_path_obj = None
        if self.kh_rando_exporter and self.kh_rando_exporter.kh_rando_path:
            try:
                kh_rando_path_obj = Path(self.kh_rando_exporter.kh_rando_path).resolve()
            except:
                pass
        
        # Build list of all folders to scan
        all_scan_paths = []
        for folder in folders:
            folder_path = Path(folder)
            if folder_path.exists() and folder_path.is_dir():
                all_scan_paths.append((folder_path, scan_subdirs))
        
        # Include KH Rando folder
        if kh_rando_folder and kh_rando_folder not in folders:
            kh_path = Path(kh_rando_folder)
            if kh_path.exists() and kh_path.is_dir():
                all_scan_paths.append((kh_path, True))
        
        # Single pass: scan folders
        current_file_count = 0
        for folder_path, should_scan_subdirs in all_scan_paths:
            current_file_count = self._scan_single_folder(folder_path, should_scan_subdirs, current_file_count, kh_rando_path_obj)
        
        # Force update of KH Rando list after scan completion
        self._update_kh_rando_list()
    
    def _update_kh_rando_list(self):
        """Signal that KH Rando list should be updated"""
        # The main window will call _populate_kh_rando_list which reads self.kh_rando_files_by_category
        pass
    
    def _scan_single_folder(self, folder_path: Path, scan_subdirs: bool, current_count: int = 0, kh_rando_path_obj: Path = None) -> int:
        """Scan a single folder for audio files and return updated count"""
        try:
            if not folder_path.exists() or not folder_path.is_dir():
                logging.warning(f"Folder not found or not a directory: {folder_path}")
                return current_count
                
            if scan_subdirs:
                # Recursively scan all subdirectories
                for file_path in folder_path.rglob('*'):
                    if file_path.is_file() and self._is_supported_file(file_path):
                        self._add_file_to_library(file_path, kh_rando_path_obj)
                        current_count += 1
                        
                        # Report progress (without total since we don't pre-count)
                        if self.progress_callback:
                            self.progress_callback(current_count, 0, file_path.name)
            else:
                # Only scan immediate directory
                for file_path in folder_path.iterdir():
                    if file_path.is_file() and self._is_supported_file(file_path):
                        self._add_file_to_library(file_path, kh_rando_path_obj)
                        current_count += 1
                        
                        # Report progress (without total since we don't pre-count)
                        if self.progress_callback:
                            self.progress_callback(current_count, 0, file_path.name)
                            
        except (OSError, PermissionError) as e:
            logging.warning(f"Error scanning folder {folder_path}: {e}")
        
        return current_count
    
    def _is_supported_file(self, file_path: Path) -> bool:
        """Check if file has a supported extension"""
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS
        
    def _add_file_to_library(self, file_path: Path, kh_rando_path_obj: Path = None) -> None:
        """Add a single file to the library list"""
        try:
            if not file_path.exists():
                return
                
            size = file_path.stat().st_size
            filename = file_path.name
            
            # Fast check if file is in KH Rando folder using pre-computed path
            is_in_kh_rando = False
            if kh_rando_path_obj:
                try:
                    # Use Path.is_relative_to() for cross-platform relative path checking
                    # resolve() ensures both paths are absolute and normalized
                    is_in_kh_rando = file_path.resolve().is_relative_to(kh_rando_path_obj)
                except (ValueError, OSError):
                    pass
            
            # If in KH Rando folder, categorize and return early
            if is_in_kh_rando and self.kh_rando_file_list and self.kh_rando_exporter:
                categories_to_check = self.kh_rando_exporter.get_categories()
                
                for part in file_path.parts:
                    part_lower = part.lower()
                    if part_lower in [cat.lower() for cat in categories_to_check.keys()]:
                        # Find the correct category key
                        for cat_key in categories_to_check.keys():
                            if part_lower == cat_key.lower():
                                # Ensure category exists in tracking dict
                                if cat_key not in self.kh_rando_files_by_category:
                                    self.kh_rando_files_by_category[cat_key] = []
                                
                                # Check if file already exists in this category (avoid duplicates)
                                file_path_str = str(file_path)
                                already_exists = any(fpath == file_path_str for fpath, _ in self.kh_rando_files_by_category[cat_key])
                                
                                if not already_exists:
                                    # Add to category tracking
                                    simple_display = f"{filename} ({format_file_size(size)})"
                                    self.kh_rando_files_by_category[cat_key].append((file_path_str, simple_display))
                                
                                return  # Don't add to main list
                        break
                # File is in KH Rando but couldn't categorize - still don't add to main list
                return
            
            # Get KH Rando status for regular files (duplicates)
            kh_status = ""
            if self.kh_rando_exporter and not is_in_kh_rando:
                kh_categories = self.kh_rando_exporter.is_file_in_kh_rando(filename)
                if kh_categories:
                    if kh_categories == ['root']:
                        kh_status = " [KH: root folder - misplaced]"
                    else:
                        display_categories = [cat for cat in kh_categories if cat != 'root']
                        if display_categories:
                            kh_status = f" [KH: {', '.join(display_categories)} - duplicate]"
            
            # Create list item
            display_text = f"{filename} ({format_file_size(size)}){kh_status}"
            
            # Check if file already exists in main library (avoid duplicates)
            file_path_str = str(file_path)
            for i in range(self.file_list.count()):
                existing_item = self.file_list.item(i)
                if existing_item:
                    item_data = existing_item.data(Qt.UserRole)
                    # Skip folder headers and check file path
                    if item_data and not item_data.startswith("FOLDER_HEADER:") and item_data == file_path_str:
                        # File already exists, don't add duplicate
                        return
            
            item = QListWidgetItem(display_text)
            item.setToolTip(str(file_path))
            item.setData(Qt.UserRole, file_path_str)
            
            # Color code duplicates
            if kh_status:
                item.setForeground(QColor('orange'))  # Orange for duplicates
            
            # Add to regular library list
            self.file_list.addItem(item)
            
        except OSError as e:
            logging.warning(f"Error adding file to library {file_path}: {e}")
    
    def get_playlist(self) -> List[str]:
        """Get all files in library as a playlist (use folder cache if available)"""
        playlist = []
        # Try to use folder cache for main library if available
        files_by_folder = getattr(self.file_list.parent(), '_files_by_folder_cache', None)
        if files_by_folder:
            for folder_name in sorted(files_by_folder.keys()):
                # Sort files alphabetically by filename (case-insensitive)
                sorted_files = sorted(files_by_folder[folder_name], key=lambda x: os.path.basename(x[1]).lower())
                for _, file_path, _ in sorted_files:
                    if file_path and file_path not in playlist:
                        playlist.append(file_path)
        else:
            # Fallback to visible list
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
    
    def _add_single_file(self, file_path: Path):
        """Add a single file to the library without full rescan"""
        if not file_path.exists() or not file_path.is_file():
            return
        
        if not self._is_supported_file(file_path):
            return
        
        try:
            # Pre-compute KH Rando path for fast checking
            kh_rando_path_obj = None
            if self.kh_rando_exporter and self.kh_rando_exporter.kh_rando_path:
                try:
                    kh_rando_path_obj = Path(self.kh_rando_exporter.kh_rando_path).resolve()
                except:
                    pass
            
            # Use the existing _add_file_to_library method
            self._add_file_to_library(file_path, kh_rando_path_obj)
            logging.info(f"Added file to library: {file_path}")
        except Exception as e:
            logging.error(f"Error adding file {file_path}: {e}")

