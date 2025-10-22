"""Scanning overlay widget for library operations"""
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont


class ScanOverlay(QWidget):
    """Overlay widget shown during library scanning"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.hide()
        
        # Create layout
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        
        # Status label
        self.status_label = QLabel("Scanning library...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 18px;
                font-weight: bold;
                background-color: rgba(32, 32, 32, 230);
                padding: 20px 40px;
                border-radius: 10px;
                border: 2px solid #0078d4;
            }
        """)
        layout.addWidget(self.status_label)
        
        # File label (shows current file being scanned)
        self.file_label = QLabel("")
        self.file_label.setAlignment(Qt.AlignCenter)
        self.file_label.setStyleSheet("""
            QLabel {
                color: #cccccc;
                font-size: 12px;
                background-color: rgba(32, 32, 32, 200);
                padding: 10px 20px;
                border-radius: 5px;
                margin-top: 10px;
            }
        """)
        layout.addWidget(self.file_label)
        
    def show_scanning(self, message="Scanning library..."):
        """Show the scanning overlay with a message"""
        self.status_label.setText(message)
        self.file_label.setText("")
        if self.parent():
            self.resize(self.parent().size())
        self.show()
        self.raise_()
        
    def update_progress(self, current, total, filename=""):
        """Update progress display"""
        if total > 0:
            progress_text = f"Scanning... {current}/{total} files"
        else:
            progress_text = f"Scanning... {current} files"
        
        self.status_label.setText(progress_text)
        
        if filename:
            # Truncate long filenames
            if len(filename) > 50:
                filename = filename[:47] + "..."
            self.file_label.setText(filename)
        
    def hide_scanning(self):
        """Hide the scanning overlay"""
        self.hide()
        
    def resizeEvent(self, event):
        """Ensure overlay covers parent widget"""
        if self.parent():
            self.resize(self.parent().size())
        super().resizeEvent(event)
