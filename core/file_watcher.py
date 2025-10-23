"""File system watcher for library changes"""
import logging
import os
from pathlib import Path
from typing import List, Callable, Set
from PyQt5.QtCore import QFileSystemWatcher, QObject, pyqtSignal, QTimer


class LibraryFileWatcher(QObject):
    """Watch library folders for file changes and trigger updates"""
    
    # Signals for file changes
    file_added = pyqtSignal(str)  # file_path
    file_removed = pyqtSignal(str)  # file_path
    file_modified = pyqtSignal(str)  # file_path
    directory_added = pyqtSignal(str)  # directory_path - for KH Rando folder detection
    directory_removed = pyqtSignal(str)  # directory_path - for KH Rando folder removal
    
    SUPPORTED_EXTENSIONS = ['.scd', '.wav', '.mp3', '.ogg', '.flac']
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.watcher = QFileSystemWatcher(self)
        self.watched_folders: Set[str] = set()
        self.watched_files: Set[str] = set()
        
        # Debounce timer to avoid multiple rapid updates
        self.debounce_timer = QTimer(self)
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.setInterval(200)  # 200ms debounce for faster response
        
        # Connect watcher signals
        self.watcher.directoryChanged.connect(self._on_directory_changed)
        self.watcher.fileChanged.connect(self._on_file_changed)
        
        # Track pending changes to debounce
        self.pending_changes: Set[str] = set()
        self.debounce_timer.timeout.connect(self._process_pending_changes)
        
        logging.info("File watcher initialized")
    
    def add_watch_paths(self, folders: List[str], scan_subdirs: bool = True):
        """Add folders to watch for changes"""
        new_folders = set()
        
        for folder in folders:
            folder_path = Path(folder)
            if folder_path.exists() and folder_path.is_dir():
                # Add the folder itself
                folder_str = str(folder_path)
                new_folders.add(folder_str)
                
                # Add subdirectories if requested
                if scan_subdirs:
                    try:
                        for subdir in folder_path.rglob('*'):
                            if subdir.is_dir():
                                new_folders.add(str(subdir))
                    except (OSError, PermissionError) as e:
                        logging.warning(f"Could not scan subdirectories of {folder}: {e}")
        
        # Add new folders to watcher
        folders_to_add = new_folders - self.watched_folders
        if folders_to_add:
            success = self.watcher.addPaths(list(folders_to_add))
            if success:
                self.watched_folders.update(folders_to_add)
                logging.info(f"Added {len(folders_to_add)} folders to file watcher")
    
    def remove_watch_paths(self, folders: List[str]):
        """Remove folders from watching"""
        folders_to_remove = set(str(Path(f)) for f in folders if Path(f).exists())
        folders_to_remove = folders_to_remove & self.watched_folders
        
        if folders_to_remove:
            self.watcher.removePaths(list(folders_to_remove))
            self.watched_folders -= folders_to_remove
            logging.info(f"Removed {len(folders_to_remove)} folders from file watcher")
    
    def clear_watches(self):
        """Clear all watched paths"""
        if self.watched_folders:
            self.watcher.removePaths(list(self.watched_folders))
            self.watched_folders.clear()
        if self.watched_files:
            self.watcher.removePaths(list(self.watched_files))
            self.watched_files.clear()
        logging.info("Cleared all file watches")
    
    def _is_supported_file(self, file_path: str) -> bool:
        """Check if file has supported audio extension"""
        return any(file_path.lower().endswith(ext) for ext in self.SUPPORTED_EXTENSIONS)
    
    def _on_directory_changed(self, path: str):
        """Handle directory change events"""
        # Add to pending changes and restart debounce timer
        self.pending_changes.add(path)
        self.debounce_timer.start()
    
    def _on_file_changed(self, path: str):
        """Handle file change events"""
        if self._is_supported_file(path):
            self.pending_changes.add(path)
            self.debounce_timer.start()
    
    def _process_pending_changes(self):
        """Process all pending changes after debounce period"""
        if not self.pending_changes:
            return
        
        # Create a copy of pending changes to avoid RuntimeError during iteration
        changes_to_process = list(self.pending_changes)
        self.pending_changes.clear()
        
        # Process directory changes
        for path in changes_to_process:
            if os.path.isdir(path):
                self._scan_directory_for_changes(path)
            elif os.path.isfile(path) and self._is_supported_file(path):
                self.file_modified.emit(path)
    
    def _scan_directory_for_changes(self, directory: str):
        """Scan directory to detect added/removed files and new subdirectories"""
        try:
            dir_path = Path(directory)
            
            # Check if directory still exists (handle deletions)
            if not dir_path.exists():
                logging.info(f"Directory no longer exists: {directory}")
                # Emit directory removed signal
                self.directory_removed.emit(directory)
                
                # Remove this directory from watched folders
                if directory in self.watched_folders:
                    self.watched_folders.discard(directory)
                    self.watcher.removePath(directory)
                
                # Find and remove all files that were in this directory
                files_to_remove = [f for f in self.watched_files if Path(f).parent == dir_path or str(Path(f)).startswith(str(dir_path))]
                for file_path in files_to_remove:
                    self.file_removed.emit(file_path)
                    self.watched_files.discard(file_path)
                
                # Find and remove all subdirectories
                subdirs_to_remove = [d for d in self.watched_folders if Path(d).parent == dir_path or str(Path(d)).startswith(str(dir_path))]
                for subdir in subdirs_to_remove:
                    self.watched_folders.discard(subdir)
                    self.watcher.removePath(subdir)
                
                return
            
            # Get current subdirectories
            current_subdirs = set()
            for item in dir_path.iterdir():
                if item.is_dir():
                    current_subdirs.add(str(item))
            
            # Get watched subdirectories that are direct children of this directory
            watched_subdirs_in_dir = {d for d in self.watched_folders if Path(d).parent == dir_path}
            
            # Detect removed subdirectories
            for subdir in watched_subdirs_in_dir:
                if subdir not in current_subdirs:
                    logging.info(f"Subdirectory removed: {subdir}")
                    # Emit directory removed signal
                    self.directory_removed.emit(subdir)
                    
                    self.watched_folders.discard(subdir)
                    self.watcher.removePath(subdir)
                    
                    # Remove all files in the removed subdirectory
                    subdir_path = Path(subdir)
                    files_to_remove = [f for f in self.watched_files if str(Path(f)).startswith(str(subdir_path))]
                    for file_path in files_to_remove:
                        self.file_removed.emit(file_path)
                        self.watched_files.discard(file_path)
            
            # Check for new subdirectories and add them to watcher
            new_subdirs = []
            for item_str in current_subdirs:
                if item_str not in self.watched_folders:
                    new_subdirs.append(item_str)
                    self.watched_folders.add(item_str)
            
            # Add new subdirectories to watcher and scan them for files
            if new_subdirs:
                success = self.watcher.addPaths(new_subdirs)
                if success:
                    logging.info(f"Added {len(new_subdirs)} new subdirectories to watcher")
                    
                    # Emit signal for each new directory (for KH Rando folder detection)
                    for subdir in new_subdirs:
                        self.directory_added.emit(subdir)
                        # Recursively scan new subdirectories for files
                        self._scan_new_directory_recursive(subdir)
            
            # Get current files in THIS directory only (not recursive for existing scan)
            current_files = set()
            for file in dir_path.iterdir():
                if file.is_file() and self._is_supported_file(str(file)):
                    current_files.add(str(file))
            
            # Get watched files that are in this specific directory
            watched_in_dir = {f for f in self.watched_files if Path(f).parent == dir_path}
            
            # Detect new files
            for file_path in current_files:
                if file_path not in self.watched_files:
                    self.file_added.emit(file_path)
                    self.watched_files.add(file_path)
            
            # Detect removed files (only in this directory)
            for file_path in watched_in_dir:
                if file_path not in current_files:
                    self.file_removed.emit(file_path)
                    self.watched_files.discard(file_path)
                    
        except (OSError, PermissionError) as e:
            logging.warning(f"Error scanning directory {directory}: {e}")
    
    def _scan_new_directory_recursive(self, directory: str):
        """Recursively scan a newly added directory for all files and subdirectories"""
        try:
            dir_path = Path(directory)
            if not dir_path.exists() or not dir_path.is_dir():
                return
            
            # Recursively find all files
            for file_path in dir_path.rglob('*'):
                if file_path.is_file() and self._is_supported_file(str(file_path)):
                    file_str = str(file_path)
                    if file_str not in self.watched_files:
                        self.file_added.emit(file_str)
                        self.watched_files.add(file_str)
                elif file_path.is_dir():
                    # Add subdirectories to watcher
                    dir_str = str(file_path)
                    if dir_str not in self.watched_folders:
                        self.watched_folders.add(dir_str)
                        self.watcher.addPath(dir_str)
                        
        except (OSError, PermissionError) as e:
            logging.warning(f"Error scanning new directory {directory}: {e}")
    
    def scan_initial_files_async(self, folders: List[str], scan_subdirs: bool = True):
        """Initial scan to populate watched files list - done incrementally to avoid blocking"""
        import time
        
        # Store scan state
        self._async_scan_state = {
            'folders': folders,
            'scan_subdirs': scan_subdirs,
            'current_folder_idx': 0,
            'file_count': 0,
            'start_time': time.time(),
            'iterators': []
        }
        
        # Start the chunked scan
        self._continue_async_scan()
    
    def _continue_async_scan(self):
        """Continue the async scan in chunks to keep UI responsive"""
        import time
        from PyQt5.QtWidgets import QApplication
        
        if not hasattr(self, '_async_scan_state'):
            return
        
        state = self._async_scan_state
        folders = state['folders']
        scan_subdirs = state['scan_subdirs']
        
        # Process files in chunks of 50 to avoid blocking
        chunk_size = 50
        files_processed = 0
        
        try:
            # Create iterator if we don't have one for current folder
            if not state['iterators'] and state['current_folder_idx'] < len(folders):
                folder = folders[state['current_folder_idx']]
                folder_path = Path(folder)
                if folder_path.exists() and folder_path.is_dir():
                    try:
                        if scan_subdirs:
                            state['iterators'] = [folder_path.rglob('*')]
                        else:
                            state['iterators'] = [folder_path.iterdir()]
                    except (OSError, PermissionError) as e:
                        logging.warning(f"Error scanning folder {folder}: {e}")
                        state['current_folder_idx'] += 1
                        QTimer.singleShot(10, self._continue_async_scan)
                        return
            
            # Process a chunk of files
            if state['iterators']:
                iterator = state['iterators'][0]
                try:
                    while files_processed < chunk_size:
                        file = next(iterator)
                        if file.is_file() and self._is_supported_file(str(file)):
                            self.watched_files.add(str(file))
                            state['file_count'] += 1
                        files_processed += 1
                except StopIteration:
                    # Finished this folder, move to next
                    state['iterators'] = []
                    state['current_folder_idx'] += 1
            
            # Check if we're done
            if state['current_folder_idx'] >= len(folders):
                elapsed = time.time() - state['start_time']
                logging.info(f"File watcher initial scan complete: {state['file_count']} files in {elapsed:.2f}s")
                del self._async_scan_state
                return
            
            # Schedule next chunk
            QTimer.singleShot(10, self._continue_async_scan)
            
        except Exception as e:
            logging.error(f"Error in async scan: {e}")
            if hasattr(self, '_async_scan_state'):
                del self._async_scan_state
    
    def scan_initial_files(self, folders: List[str], scan_subdirs: bool = True):
        """Initial scan to populate watched files list (blocking version for compatibility)"""
        for folder in folders:
            folder_path = Path(folder)
            if folder_path.exists() and folder_path.is_dir():
                try:
                    if scan_subdirs:
                        for file in folder_path.rglob('*'):
                            if file.is_file() and self._is_supported_file(str(file)):
                                self.watched_files.add(str(file))
                    else:
                        for file in folder_path.iterdir():
                            if file.is_file() and self._is_supported_file(str(file)):
                                self.watched_files.add(str(file))
                except (OSError, PermissionError) as e:
                    logging.warning(f"Error scanning initial files in {folder}: {e}")
