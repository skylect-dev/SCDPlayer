"""Dialog utilities and themed dialogs for SCDPlayer"""
import sys
import ctypes
import logging
from PyQt5.QtWidgets import QMessageBox, QFileDialog
from PyQt5.QtCore import Qt


def apply_title_bar_theming(dialog):
    """Apply title bar theming to any dialog"""
    if sys.platform != "win32":
        return
        
    try:
        from ctypes import wintypes
        
        # Windows 11 dark mode constants
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        
        # Get window handle
        hwnd = int(dialog.winId())
        
        # Try to enable dark title bar
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 
            DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(ctypes.c_int(1)),
            ctypes.sizeof(ctypes.c_int)
        )
    except (AttributeError, OSError) as e:
        logging.debug(f"Title bar theming not available: {e}")


def show_themed_message(parent, icon, title, text, buttons=QMessageBox.Ok, default_button=None):
    """Show a message box with title bar theming"""
    msg_box = QMessageBox(parent)
    msg_box.setIcon(icon)
    msg_box.setWindowTitle(title)
    msg_box.setText(text)
    msg_box.setStandardButtons(buttons)
    if default_button:
        msg_box.setDefaultButton(default_button)
    
    # Apply title bar theming
    apply_title_bar_theming(msg_box)
    
    return msg_box.exec_()


def _create_file_dialog(parent, title, dialog_type="open"):
    """Factory function to create file dialogs"""
    dialog = QFileDialog(parent)
    dialog.setWindowTitle(title)
    
    if dialog_type == "save":
        dialog.setFileMode(QFileDialog.AnyFile)
        dialog.setAcceptMode(QFileDialog.AcceptSave)
    elif dialog_type == "directory":
        dialog.setFileMode(QFileDialog.Directory)
        dialog.setAcceptMode(QFileDialog.AcceptOpen)
    else:  # default to "open"
        dialog.setFileMode(QFileDialog.ExistingFile)
        dialog.setAcceptMode(QFileDialog.AcceptOpen)
    
    apply_title_bar_theming(dialog)
    return dialog


def show_themed_file_dialog(parent, dialog_type, title, directory="", filter=""):
    """Show a file dialog with title bar theming"""
    dialog = _create_file_dialog(parent, title, dialog_type)
    
    # Set directory or file selection
    if directory:
        if dialog_type == "save":
            dialog.selectFile(directory)
        else:
            dialog.setDirectory(directory)
    
    # Set file filter
    if filter:
        dialog.setNameFilter(filter)
    
    # Execute dialog and return result
    if dialog.exec_() == QFileDialog.Accepted:
        selected_files = dialog.selectedFiles()
        return selected_files[0] if selected_files else None
    return None


class LogViewerDialog(QMessageBox):
    """Dialog for viewing log files with live updates"""
    def __init__(self, parent=None):
        super().__init__(parent)
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout
        from PyQt5.QtCore import QTimer
        import os
        
        # Create as a proper dialog instead of message box
        self.dialog = QDialog(parent)
        self.dialog.setWindowTitle("SCDPlayer Log Viewer")
        self.dialog.resize(800, 600)
        self.dialog.setWindowFlags(Qt.Window)  # Make it a non-modal window
        
        # Connect close event to stop timer
        self.dialog.closeEvent = self.on_dialog_close
        
        # Apply title bar theming
        apply_title_bar_theming(self.dialog)
        
        # Layout
        layout = QVBoxLayout()
        
        # Text area for log content
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a1a;
                color: #14ffec;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 10pt;
                border: 2px solid #0d7377;
            }
        """)
        layout.addWidget(self.log_text)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.load_log)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #0d7377;
                color: #14ffec;
                border: 2px solid #0d7377;
                border-radius: 5px;
                padding: 5px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #14ffec;
                color: #212121;
                border: 2px solid #14ffec;
            }
        """)
        button_layout.addWidget(refresh_btn)
        
        clear_btn = QPushButton("Clear Log")
        clear_btn.clicked.connect(self.clear_log)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #0d7377;
                color: #14ffec;
                border: 2px solid #0d7377;
                border-radius: 5px;
                padding: 5px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #14ffec;
                color: #212121;
                border: 2px solid #14ffec;
            }
        """)
        button_layout.addWidget(clear_btn)
        
        button_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.dialog.accept)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #0d7377;
                color: #14ffec;
                border: 2px solid #0d7377;
                border-radius: 5px;
                padding: 5px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #14ffec;
                color: #212121;
                border: 2px solid #14ffec;
            }
        """)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        self.dialog.setLayout(layout)
        
        # Timer for auto-refresh (every 5 seconds to reduce lag)
        self.timer = QTimer()
        self.timer.timeout.connect(self.load_log)
        self.timer.start(5000)  # 5 seconds instead of 2
        
        # Initial load
        self.load_log()
    
    def load_log(self):
        """Load and display log file content"""
        import os
        log_path = 'scdplayer_debug.log'
        
        try:
            if os.path.exists(log_path):
                with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    self.log_text.setPlainText(content)
                    # Scroll to bottom
                    scrollbar = self.log_text.verticalScrollBar()
                    scrollbar.setValue(scrollbar.maximum())
            else:
                self.log_text.setPlainText("Log file not found.")
        except Exception as e:
            self.log_text.setPlainText(f"Error reading log file: {e}")
    
    def clear_log(self):
        """Clear the log file"""
        import os
        log_path = 'scdplayer_debug.log'
        
        try:
            if os.path.exists(log_path):
                with open(log_path, 'w', encoding='utf-8') as f:
                    f.write("")
                self.log_text.setPlainText("Log cleared.")
                logging.info("Log file cleared by user")
        except Exception as e:
            self.log_text.setPlainText(f"Error clearing log file: {e}")
    
    def show(self):
        """Show the dialog (non-blocking)"""
        self.timer.start(5000)  # Resume auto-refresh when shown
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
    
    def on_dialog_close(self, event):
        """Stop timer when dialog is closed"""
        self.timer.stop()
        event.accept()
    
    def exec_(self):
        """Execute the dialog (kept for compatibility, but uses show() for non-modal behavior)"""
        self.show()
