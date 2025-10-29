"""
.NET Runtime detection and installation helper for MusicEncoder
"""
import logging
import subprocess
import os
from pathlib import Path
from typing import Tuple, Optional
from PyQt5.QtWidgets import QMessageBox, QProgressDialog
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from utils.helpers import get_bundled_path


class DotNetRuntimeChecker:
    """Check for .NET 5.0 runtime availability (required for MusicEncoder)"""
    
    REQUIRED_VERSION = "5.0"  # Exact version required by MusicEncoder (SingleEncoder.runtimeconfig.json)
    DOWNLOAD_URL = "https://dotnet.microsoft.com/download/dotnet/5.0"
    # Direct link to .NET 5.0 Desktop Runtime installer (Windows x64)
    DIRECT_DOWNLOAD_URL = "https://download.visualstudio.microsoft.com/download/pr/7ab0bc25-5b00-42c3-b7cc-bb8e08f05135/91528a790a28c1f0e05daaf1d0e8c4e8/windowsdesktop-runtime-5.0.17-win-x64.exe"
    
    @staticmethod
    def check_dotnet_installed() -> Tuple[bool, Optional[str]]:
        """
        Check if .NET 5.0 runtime is installed (required for MusicEncoder)
        
        Returns:
            Tuple of (is_installed, version_string)
        """
        try:
            # Try to run dotnet --list-runtimes
            result = subprocess.run(
                ['dotnet', '--list-runtimes'],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            if result.returncode == 0:
                output = result.stdout
                # Look specifically for .NET 5.0.x runtime (required by MusicEncoder)
                # Check for Microsoft.NETCore.App 5.0.x (required for MusicEncoder.exe)
                found_versions = []
                for line in output.splitlines():
                    if 'Microsoft.NETCore.App' in line:
                        parts = line.split()
                        if len(parts) >= 2:
                            version = parts[1]
                            try:
                                # Check if major version is 5
                                major_version = int(version.split('.')[0])
                                if major_version == 5:
                                    found_versions.append(version)
                            except (ValueError, IndexError):
                                continue
                
                if found_versions:
                    # Return the highest 5.x version found
                    best_version = max(found_versions, key=lambda v: tuple(map(int, v.split('.')[:3])))
                    logging.info(f".NET {best_version} runtime found (required for MusicEncoder)")
                    return True, best_version
                
                logging.warning(".NET 5.0 runtime not found (required for MusicEncoder)")
                logging.debug(f"Available runtimes:\n{output}")
                return False, None
            else:
                logging.warning("dotnet command failed")
                return False, None
                
        except FileNotFoundError:
            logging.warning("dotnet command not found - .NET not installed")
            return False, None
        except subprocess.TimeoutExpired:
            logging.warning("dotnet command timed out")
            return False, None
        except Exception as e:
            logging.error(f"Error checking .NET runtime: {e}")
            return False, None
    
    @staticmethod
    def check_bundled_installer() -> Optional[Path]:
        """Check if .NET installer is bundled with the app"""
        try:
            # First check in redist folder (for bundled .NET 5.0 runtime)
            redist_dir = Path(__file__).parent.parent / 'redist'
            if redist_dir.exists():
                for installer in redist_dir.glob('windowsdesktop-runtime-*.exe'):
                    logging.info(f"Found bundled .NET installer in redist: {installer}")
                    return installer
            
            # Check in the bundled dotnet_installer directory
            installer_dir = Path(get_bundled_path('dotnet_installer'))
            if installer_dir.exists():
                # Look for installer exe
                for installer in installer_dir.glob('windowsdesktop-runtime-*.exe'):
                    logging.info(f"Found bundled .NET installer: {installer}")
                    return installer
            
            # Also check in root directory
            root_dir = Path(__file__).parent.parent
            for installer in root_dir.glob('windowsdesktop-runtime-*.exe'):
                logging.info(f"Found .NET installer in root: {installer}")
                return installer
                
            logging.debug("No bundled .NET installer found")
            return None
            
        except Exception as e:
            logging.error(f"Error checking for bundled installer: {e}")
            return None


class DotNetInstallerThread(QThread):
    """Thread for downloading/installing .NET runtime"""
    
    progress = pyqtSignal(str, int)  # message, percentage
    finished = pyqtSignal(bool, str)  # success, message
    
    def __init__(self, installer_path: Optional[Path] = None):
        super().__init__()
        self.installer_path = installer_path
        self.cancelled = False
    
    def run(self):
        """Run the installation process"""
        try:
            if self.installer_path and self.installer_path.exists():
                # Use bundled installer
                self.progress.emit("Running .NET 5.0 installer...", 50)
                self._run_installer(self.installer_path)
            else:
                # Download installer
                self.progress.emit("Downloading .NET 5.0 installer...", 25)
                downloaded_path = self._download_installer()
                
                if self.cancelled:
                    self.finished.emit(False, "Installation cancelled")
                    return
                
                if downloaded_path:
                    self.progress.emit("Running .NET 5.0 installer...", 75)
                    self._run_installer(downloaded_path)
                    
                    # Clean up downloaded installer
                    try:
                        downloaded_path.unlink()
                    except:
                        pass
                else:
                    self.finished.emit(False, "Failed to download installer")
                    return
            
            # Verify installation
            self.progress.emit("Verifying installation...", 90)
            is_installed, version = DotNetRuntimeChecker.check_dotnet_installed()
            
            if is_installed:
                self.finished.emit(True, f".NET runtime installed successfully (version {version})")
            else:
                self.finished.emit(False, "Installation completed but .NET runtime not detected. Please try installing manually.")
                
        except Exception as e:
            logging.error(f"Error during .NET installation: {e}")
            self.finished.emit(False, f"Installation error: {str(e)}")
    
    def _download_installer(self) -> Optional[Path]:
        """Download the .NET installer"""
        try:
            import urllib.request
            import tempfile
            
            # Create temp file for installer
            fd, temp_path = tempfile.mkstemp(suffix='.exe', prefix='dotnet_installer_')
            os.close(fd)
            temp_file = Path(temp_path)
            
            # Download with progress
            def reporthook(block_num, block_size, total_size):
                if self.cancelled:
                    raise Exception("Download cancelled")
                if total_size > 0:
                    percent = min(int((block_num * block_size / total_size) * 100), 100)
                    self.progress.emit(f"Downloading... {percent}%", 25 + int(percent * 0.5))
            
            urllib.request.urlretrieve(
                DotNetRuntimeChecker.DIRECT_DOWNLOAD_URL,
                temp_file,
                reporthook=reporthook
            )
            
            return temp_file
            
        except Exception as e:
            logging.error(f"Failed to download .NET installer: {e}")
            return None
    
    def _run_installer(self, installer_path: Path):
        """Run the .NET installer"""
        try:
            # Run installer silently with /quiet /norestart flags
            result = subprocess.run(
                [str(installer_path), '/quiet', '/norestart'],
                timeout=300,  # 5 minute timeout
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            if result.returncode != 0 and result.returncode != 3010:  # 3010 = reboot required
                logging.warning(f"Installer returned code {result.returncode}")
                
        except subprocess.TimeoutExpired:
            raise Exception("Installer timed out")
        except Exception as e:
            raise Exception(f"Failed to run installer: {e}")
    
    def cancel(self):
        """Cancel the installation"""
        self.cancelled = True


def prompt_dotnet_install(parent_widget) -> bool:
    """
    Show dialog prompting user to install .NET 5.0
    
    Returns:
        True if user wants to proceed with installation
    """
    from ui.dialogs import show_themed_message
    
    # Check if bundled installer exists
    bundled_installer = DotNetRuntimeChecker.check_bundled_installer()
    
    if bundled_installer:
        message = (
            "🔧 .NET 5.0 Runtime Required\n\n"
            "SCD file conversion requires the .NET 5.0 Desktop Runtime.\n\n"
            "A bundled installer has been found. Would you like to install it now?\n\n"
            "This is a one-time setup and only takes a minute."
        )
    else:
        message = (
            "🔧 .NET 5.0 Runtime Required\n\n"
            "SCD file conversion requires the .NET 5.0 Desktop Runtime.\n\n"
            "The .NET 5.0 Desktop Runtime installer will be downloaded (~50 MB) and installed automatically.\n\n"
            "This is a one-time setup and only takes a few minutes.\n\n"
            "Alternative: You can download it manually from:\n"
            f"{DotNetRuntimeChecker.DOWNLOAD_URL}"
        )
    
    reply = show_themed_message(
        parent_widget,
        QMessageBox.Question,
        ".NET Runtime Required",
        message,
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.Yes
    )
    
    return reply == QMessageBox.Yes


def install_dotnet_runtime(parent_widget) -> bool:
    """
    Install .NET 5.0 runtime with progress dialog
    
    Returns:
        True if installation succeeded
    """
    from ui.dialogs import show_themed_message
    
    # Check for bundled installer
    bundled_installer = DotNetRuntimeChecker.check_bundled_installer()
    
    # Create progress dialog
    progress_dialog = QProgressDialog(
        "Preparing .NET installation...",
        "Cancel",
        0, 100,
        parent_widget
    )
    progress_dialog.setWindowTitle(".NET Runtime Installation")
    progress_dialog.setWindowModality(Qt.WindowModal)
    progress_dialog.setMinimumDuration(0)
    progress_dialog.setValue(0)
    
    # Create installer thread
    installer_thread = DotNetInstallerThread(bundled_installer)
    
    # Track result
    result = [False, ""]  # [success, message]
    
    def on_progress(message, percent):
        progress_dialog.setLabelText(message)
        progress_dialog.setValue(percent)
    
    def on_finished(success, message):
        result[0] = success
        result[1] = message
        progress_dialog.close()
    
    def on_cancelled():
        installer_thread.cancel()
    
    installer_thread.progress.connect(on_progress)
    installer_thread.finished.connect(on_finished)
    progress_dialog.canceled.connect(on_cancelled)
    
    # Start installation
    installer_thread.start()
    
    # Show dialog and wait
    progress_dialog.exec_()
    installer_thread.wait()
    
    # Show result
    if result[0]:
        show_themed_message(
            parent_widget,
            QMessageBox.Information,
            "Installation Successful",
            f"✅ {result[1]}\n\nYou can now convert SCD files!"
        )
        return True
    else:
        show_themed_message(
            parent_widget,
            QMessageBox.Warning,
            "Installation Failed",
            f"❌ {result[1]}\n\nYou can install .NET 5.0 manually from:\n{DotNetRuntimeChecker.DOWNLOAD_URL}\n\nAlternatively, you can use WAV files instead of SCD."
        )
        return False
