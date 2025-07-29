#!/usr/bin/env python3
"""
SCDPlayer Standalone Updater
A separate executable that handles SCDPlayer updates with a proper GUI
"""
import sys
import os
import shutil
import zipfile
import time
import subprocess
from pathlib import Path
from PyQt5.QtWidgets import (QApplication, QDialog, QVBoxLayout, QHBoxLayout, 
                           QLabel, QProgressBar, QPushButton, QTextEdit)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt5.QtGui import QIcon, QFont


class UpdateWorker(QThread):
    """Worker thread to perform the actual update"""
    progress_updated = pyqtSignal(int, str)  # progress, message
    update_complete = pyqtSignal(bool, str)  # success, message
    
    def __init__(self, zip_path, install_dir, exe_path):
        super().__init__()
        self.zip_path = zip_path
        self.install_dir = Path(install_dir)
        self.exe_path = exe_path
        
    def run(self):
        """Perform the update process"""
        try:
            # Wait a moment for SCDPlayer to fully close
            self.progress_updated.emit(5, "Waiting for SCDPlayer to close...")
            time.sleep(2)
            
            # Step 1: Extract archive
            self.progress_updated.emit(15, "Extracting update archive...")
            time.sleep(0.3)  # Brief pause for visual feedback
            
            temp_dir = self.install_dir / "temp_update"
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
            temp_dir.mkdir()
            
            with zipfile.ZipFile(self.zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            self.progress_updated.emit(35, "Archive extracted successfully")
            time.sleep(0.3)
            
            # Step 2: Determine source directory
            self.progress_updated.emit(45, "Analyzing update structure...")
            
            # Check if we have a nested SCDPlayer folder
            nested_folder = temp_dir / "SCDPlayer"
            if nested_folder.exists():
                source_dir = nested_folder
                self.progress_updated.emit(50, "Found nested folder structure")
            else:
                source_dir = temp_dir
                self.progress_updated.emit(50, "Found direct structure")
            
            time.sleep(0.3)
            
            # Step 3: Copy files with progress
            self.progress_updated.emit(60, "Installing update files...")
            
            # Get all files to copy for progress tracking
            all_files = list(source_dir.rglob('*'))
            files_to_copy = [f for f in all_files if f.is_file()]
            total_files = len(files_to_copy)
            
            copied_files = 0
            for item in files_to_copy:
                # Calculate relative path and destination
                rel_path = item.relative_to(source_dir)
                dest_path = self.install_dir / rel_path
                
                # Skip the updater itself to avoid conflicts
                if dest_path.name in ['updater.exe', 'updater_standalone.exe']:
                    continue
                
                # Create parent directories if needed
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Copy file
                shutil.copy2(item, dest_path)
                copied_files += 1
                
                # Update progress (60-85% range for file copying)
                file_progress = 60 + int((copied_files / total_files) * 25)
                self.progress_updated.emit(file_progress, f"Copied {copied_files}/{total_files} files")
            
            self.progress_updated.emit(90, "Update files installed successfully")
            time.sleep(0.5)
            
            # Step 4: Cleanup
            self.progress_updated.emit(95, "Cleaning up temporary files...")
            shutil.rmtree(temp_dir)
            if os.path.exists(self.zip_path):
                os.remove(self.zip_path)
            
            self.progress_updated.emit(100, "Update complete!")
            time.sleep(0.5)
            
            self.update_complete.emit(True, "Update installed successfully!")
            
        except Exception as e:
            self.update_complete.emit(False, f"Update failed: {str(e)}")


class UpdateDialog(QDialog):
    """Main update dialog with progress bar"""
    
    def __init__(self, zip_path, install_dir, exe_path):
        super().__init__()
        self.zip_path = zip_path
        self.install_dir = install_dir
        self.exe_path = exe_path
        self.worker = None
        
        self.init_ui()
        self.start_update()
        
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("SCDPlayer Update")
        self.setFixedSize(500, 280)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowStaysOnTopHint)
        
        # Try to set icon if available
        try:
            icon_path = Path(self.install_dir) / "assets" / "icon.ico"
            if icon_path.exists():
                self.setWindowIcon(QIcon(str(icon_path)))
        except:
            pass
        
        # Main layout
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Title
        title = QLabel("Updating SCDPlayer")
        title.setAlignment(Qt.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # Subtitle
        subtitle = QLabel("Please wait while the update is being applied...")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #cccccc; font-size: 11px;")
        layout.addWidget(subtitle)
        
        # Status label
        self.status_label = QLabel("Preparing update...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size: 12px; margin: 10px 0px;")
        layout.addWidget(self.status_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #555555;
                border-radius: 8px;
                text-align: center;
                background-color: #404040;
                font-weight: bold;
                height: 25px;
            }
            QProgressBar::chunk {
                background-color: #0078d4;
                border-radius: 6px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # Details text (hidden by default)
        self.details_text = QTextEdit()
        self.details_text.setMaximumHeight(100)
        self.details_text.setVisible(False)
        self.details_text.setStyleSheet("""
            QTextEdit {
                background-color: #333333;
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 4px;
                font-family: 'Consolas', monospace;
                font-size: 10px;
            }
        """)
        layout.addWidget(self.details_text)
        
        # Button layout
        button_layout = QHBoxLayout()
        
        # Show details button
        self.details_btn = QPushButton("Show Details")
        self.details_btn.clicked.connect(self.toggle_details)
        self.details_btn.setStyleSheet("""
            QPushButton {
                background-color: #404040;
                color: #ffffff;
                border: 1px solid #555555;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
            QPushButton:pressed {
                background-color: #303030;
            }
        """)
        button_layout.addWidget(self.details_btn)
        
        button_layout.addStretch()
        
        # Close button (hidden initially)
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.close_and_restart)
        self.close_btn.setVisible(False)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: #ffffff;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
        """)
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
        # Apply dark theme
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
            }
        """)
        
    def toggle_details(self):
        """Toggle details text visibility"""
        if self.details_text.isVisible():
            self.details_text.setVisible(False)
            self.details_btn.setText("Show Details")
            self.setFixedSize(500, 280)
        else:
            self.details_text.setVisible(True)
            self.details_btn.setText("Hide Details")
            self.setFixedSize(500, 400)
            
    def start_update(self):
        """Start the update process"""
        self.worker = UpdateWorker(self.zip_path, self.install_dir, self.exe_path)
        self.worker.progress_updated.connect(self.update_progress)
        self.worker.update_complete.connect(self.update_finished)
        self.worker.start()
        
    def update_progress(self, progress, message):
        """Update progress bar and status"""
        self.progress_bar.setValue(progress)
        self.status_label.setText(message)
        
        # Add to details log
        self.details_text.append(f"[{progress:3d}%] {message}")
        
    def update_finished(self, success, message):
        """Handle update completion"""
        if success:
            self.status_label.setText("✓ " + message)
            self.progress_bar.setValue(100)
            self.close_btn.setVisible(True)
            self.details_btn.setVisible(False)
            
            # Auto-restart after 3 seconds
            self.restart_timer = QTimer()
            self.restart_timer.setSingleShot(True)
            self.restart_timer.timeout.connect(self.close_and_restart)
            self.restart_timer.start(3000)
            
            # Update close button text with countdown
            self.update_close_button_countdown(3)
        else:
            self.status_label.setText("✗ " + message)
            self.close_btn.setText("Close")
            self.close_btn.setVisible(True)
            self.details_btn.setVisible(False)
            
    def update_close_button_countdown(self, seconds):
        """Update close button with countdown"""
        if seconds > 0:
            self.close_btn.setText(f"Restart SCDPlayer ({seconds})")
            QTimer.singleShot(1000, lambda: self.update_close_button_countdown(seconds - 1))
        else:
            self.close_btn.setText("Restart SCDPlayer")
            
    def close_and_restart(self):
        """Close dialog and restart SCDPlayer"""
        try:
            # Start SCDPlayer
            subprocess.Popen([self.exe_path], shell=False)
        except Exception as e:
            print(f"Failed to restart SCDPlayer: {e}")
        
        self.close()


def main():
    """Main entry point"""
    if len(sys.argv) not in [4, 5]:
        print("Usage: updater.exe <zip_path> <install_dir> <exe_path> [--silent]")
        sys.exit(1)
        
    zip_path = sys.argv[1]
    install_dir = sys.argv[2]
    exe_path = sys.argv[3]
    silent = len(sys.argv) == 5 and sys.argv[4] == "--silent"
    
    # Validate arguments
    if not os.path.exists(zip_path):
        print(f"Error: Update file not found: {zip_path}")
        sys.exit(1)
        
    if not os.path.exists(install_dir):
        print(f"Error: Installation directory not found: {install_dir}")
        sys.exit(1)
    
    # Create QApplication
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    
    # Set application properties
    app.setApplicationName("SCDPlayer Updater")
    app.setApplicationVersion("1.0")
    
    # Create and show dialog
    dialog = UpdateDialog(zip_path, install_dir, exe_path)
    dialog.show()
    
    # Center the dialog on screen
    screen = app.primaryScreen().geometry()
    dialog.move(
        (screen.width() - dialog.width()) // 2,
        (screen.height() - dialog.height()) // 2
    )
    
    # Run event loop
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
