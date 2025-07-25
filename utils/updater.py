"""Auto-update system for SCDPlayer"""
import os
import sys
import json
import tempfile
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
import urllib.request
import urllib.error
from PyQt5.QtWidgets import QMessageBox, QProgressDialog
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from ui.dialogs import show_themed_message, apply_title_bar_theming
from version import __version__


class UpdateChecker(QThread):
    """Thread to check for updates without blocking UI"""
    update_available = pyqtSignal(dict)
    update_check_failed = pyqtSignal(str)
    no_update_available = pyqtSignal()
    
    def __init__(self, silent=True):
        super().__init__()
        self.silent = silent
        
    def run(self):
        """Check GitHub releases for updates"""
        try:
            # GitHub API endpoint for latest release
            api_url = "https://api.github.com/repos/skylect-dev/SCDPlayer/releases/latest"
            
            # Create request with user agent
            request = urllib.request.Request(api_url)
            request.add_header('User-Agent', f'SCDPlayer/{__version__}')
            
            # Get latest release info
            with urllib.request.urlopen(request, timeout=10) as response:
                release_data = json.loads(response.read().decode())
            
            latest_version = release_data['tag_name']
            current_version = f"v{__version__.split(' ')[0]}"  # Extract version from "2.0.0 - 'Keyblade Harmony'"
            
            # Compare versions (simple string comparison for now)
            if latest_version != current_version:
                # Find the executable asset
                exe_asset = None
                zip_asset = None
                
                for asset in release_data['assets']:
                    if asset['name'].endswith('.exe'):
                        exe_asset = asset
                    elif asset['name'].endswith('.zip'):
                        zip_asset = asset
                
                update_info = {
                    'version': latest_version,
                    'release_notes': release_data['body'],
                    'published_at': release_data['published_at'],
                    'exe_asset': exe_asset,
                    'zip_asset': zip_asset,
                    'html_url': release_data['html_url']
                }
                
                self.update_available.emit(update_info)
            else:
                self.no_update_available.emit()
                
        except Exception as e:
            if not self.silent:
                self.update_check_failed.emit(str(e))


class UpdateDownloader(QThread):
    """Thread to download and install updates"""
    download_progress = pyqtSignal(int)
    download_complete = pyqtSignal()
    download_failed = pyqtSignal(str)
    
    def __init__(self, download_url: str, update_type: str = 'exe'):
        super().__init__()
        self.download_url = download_url
        self.update_type = update_type
        self.temp_path = None
        
    def run(self):
        """Download the update"""
        try:
            # Create temporary file
            temp_dir = tempfile.gettempdir()
            if self.update_type == 'exe':
                self.temp_path = os.path.join(temp_dir, 'SCDPlayer_update.exe')
            else:
                self.temp_path = os.path.join(temp_dir, 'SCDPlayer_update.zip')
            
            # Download with progress tracking
            def progress_hook(block_count, block_size, total_size):
                if total_size > 0:
                    progress = int((block_count * block_size * 100) / total_size)
                    self.download_progress.emit(min(progress, 100))
            
            urllib.request.urlretrieve(self.download_url, self.temp_path, progress_hook)
            self.download_complete.emit()
            
        except Exception as e:
            self.download_failed.emit(str(e))


class AutoUpdater:
    """Main auto-update manager"""
    
    def __init__(self, parent_window):
        self.parent = parent_window
        self.update_checker = None
        self.update_downloader = None
        
    def check_for_updates(self, silent=True):
        """Check for updates (silent=True for startup check)"""
        if self.update_checker and self.update_checker.isRunning():
            return
            
        self.update_checker = UpdateChecker(silent)
        self.update_checker.update_available.connect(self.handle_update_available)
        self.update_checker.update_check_failed.connect(self.handle_check_failed)
        self.update_checker.no_update_available.connect(self.handle_no_update)
        self.update_checker.start()
        
    def handle_update_available(self, update_info):
        """Handle when an update is available"""
        version = update_info['version']
        notes = update_info['release_notes'][:500] + "..." if len(update_info['release_notes']) > 500 else update_info['release_notes']
        
        msg = f"SCDPlayer {version} is available!\n\n"
        msg += f"Current version: v{__version__.split(' ')[0]}\n"
        msg += f"New version: {version}\n\n"
        msg += "Release notes:\n" + notes + "\n\n"
        msg += "Would you like to download and install the update?"
        
        reply = show_themed_message(
            self.parent, 
            QMessageBox.Question, 
            "Update Available", 
            msg,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        
        if reply == QMessageBox.Yes:
            # Prefer exe update if available, otherwise use zip
            if update_info['exe_asset']:
                self.download_update(update_info['exe_asset']['browser_download_url'], 'exe')
            elif update_info['zip_asset']:
                self.download_update(update_info['zip_asset']['browser_download_url'], 'zip')
            else:
                show_themed_message(
                    self.parent,
                    QMessageBox.Information,
                    "Manual Update Required",
                    f"Please download the update manually from:\n{update_info['html_url']}"
                )
                
    def handle_check_failed(self, error_msg):
        """Handle update check failure"""
        show_themed_message(
            self.parent,
            QMessageBox.Warning,
            "Update Check Failed",
            f"Failed to check for updates:\n{error_msg}"
        )
        
    def handle_no_update(self):
        """Handle when no update is available (for manual checks)"""
        if self.update_checker and not self.update_checker.silent:
            show_themed_message(
                self.parent,
                QMessageBox.Information,
                "No Updates",
                "You are running the latest version of SCDPlayer."
            )
    
    def download_update(self, download_url: str, update_type: str = 'exe'):
        """Download the update"""
        # Create progress dialog
        progress = QProgressDialog("Downloading update...", "Cancel", 0, 100, self.parent)
        progress.setWindowTitle("SCDPlayer Update")
        progress.setModal(True)
        apply_title_bar_theming(progress)
        progress.show()
        
        # Start download
        self.update_downloader = UpdateDownloader(download_url, update_type)
        self.update_downloader.download_progress.connect(progress.setValue)
        self.update_downloader.download_complete.connect(lambda: self.install_update(progress, update_type))
        self.update_downloader.download_failed.connect(lambda err: self.handle_download_failed(progress, err))
        
        # Handle cancel
        progress.canceled.connect(self.update_downloader.terminate)
        
        self.update_downloader.start()
        
    def install_update(self, progress_dialog, update_type: str):
        """Install the downloaded update"""
        progress_dialog.close()
        
        if not self.update_downloader or not self.update_downloader.temp_path:
            show_themed_message(self.parent, QMessageBox.Critical, "Update Failed", "Download path not found.")
            return
            
        temp_path = self.update_downloader.temp_path
        
        if update_type == 'exe':
            self.install_exe_update(temp_path)
        else:
            self.install_zip_update(temp_path)
            
    def install_exe_update(self, exe_path: str):
        """Install single exe update"""
        try:
            current_exe = sys.executable
            backup_exe = current_exe + ".backup"
            
            # Create backup
            shutil.copy2(current_exe, backup_exe)
            
            msg = "Update downloaded successfully!\n\n"
            msg += "SCDPlayer will now restart to complete the update.\n"
            msg += "Click OK to restart."
            
            reply = show_themed_message(
                self.parent,
                QMessageBox.Information,
                "Update Ready",
                msg
            )
            
            if reply == QMessageBox.Ok:
                # Create update script
                script_content = f'''@echo off
timeout /t 2 /nobreak >nul
move "{exe_path}" "{current_exe}"
start "" "{current_exe}"
del "{backup_exe}"
del "%~f0"
'''
                script_path = os.path.join(tempfile.gettempdir(), 'scd_update.bat')
                with open(script_path, 'w') as f:
                    f.write(script_content)
                
                # Run update script and exit
                subprocess.Popen([script_path], shell=True)
                self.parent.close()
                
        except Exception as e:
            show_themed_message(
                self.parent,
                QMessageBox.Critical,
                "Update Failed",
                f"Failed to install update:\n{str(e)}"
            )
            
    def install_zip_update(self, zip_path: str):
        """Install zip update (extract over current directory)"""
        try:
            import zipfile
            current_dir = Path(sys.executable).parent
            
            msg = "Update downloaded successfully!\n\n"
            msg += "The update will be extracted to replace the current installation.\n"
            msg += "SCDPlayer will close during this process.\n\n"
            msg += "Click OK to proceed."
            
            reply = show_themed_message(
                self.parent,
                QMessageBox.Information,
                "Update Ready",
                msg
            )
            
            if reply == QMessageBox.Ok:
                # Create update script
                script_content = f'''@echo off
echo Updating SCDPlayer...
timeout /t 3 /nobreak >nul
powershell -Command "Expand-Archive -Path '{zip_path}' -DestinationPath '{current_dir}' -Force"
echo Update complete!
timeout /t 2 /nobreak >nul
start "" "{sys.executable}"
del "%~f0"
'''
                script_path = os.path.join(tempfile.gettempdir(), 'scd_update_zip.bat')
                with open(script_path, 'w') as f:
                    f.write(script_content)
                
                # Run update script and exit
                subprocess.Popen([script_path], shell=True)
                self.parent.close()
                
        except Exception as e:
            show_themed_message(
                self.parent,
                QMessageBox.Critical,
                "Update Failed",
                f"Failed to install update:\n{str(e)}"
            )
            
    def handle_download_failed(self, progress_dialog, error_msg):
        """Handle download failure"""
        progress_dialog.close()
        show_themed_message(
            self.parent,
            QMessageBox.Critical,
            "Download Failed",
            f"Failed to download update:\n{error_msg}"
        )
