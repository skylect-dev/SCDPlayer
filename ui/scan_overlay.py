"""
Library scanning overlay with blur effect and progress tracking
"""
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QPainter, QColor


class ScanOverlay(QWidget):
    """Overlay widget that shows scanning progress with blur effect"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ScanOverlay")
        
        # Make overlay cover the entire parent
        if parent:
            self.setGeometry(parent.rect())
        
        # Set up semi-transparent background
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setAttribute(Qt.WA_NoSystemBackground, False)
        
        # Create layout
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        
        # Status label
        self.status_label = QLabel("Scanning library...")
        self.status_label.setObjectName("ScanStatusLabel")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("""
            QLabel#ScanStatusLabel {
                color: white;
                font-size: 18px;
                font-weight: bold;
                background: transparent;
                padding: 10px 20px;
            }
        """)
        
        # Current file label
        self.file_label = QLabel("")
        self.file_label.setObjectName("ScanFileLabel")
        self.file_label.setAlignment(Qt.AlignCenter)
        self.file_label.setStyleSheet("""
            QLabel#ScanFileLabel {
                color: #aaaaaa;
                font-size: 12px;
                background: transparent;
                padding: 5px 20px;
                max-width: 500px;
            }
        """)
        self.file_label.setWordWrap(True)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("ScanProgressBar")
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p% (%v/%m files)")
        self.progress_bar.setFixedWidth(400)
        self.progress_bar.setFixedHeight(30)
        self.progress_bar.setStyleSheet("""
            QProgressBar#ScanProgressBar {
                border: 2px solid #555555;
                border-radius: 8px;
                background-color: rgba(40, 40, 40, 200);
                text-align: center;
                color: white;
                font-size: 12px;
                font-weight: bold;
            }
            QProgressBar#ScanProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                                   stop:0 #4a9eff, stop:1 #2d7dd2);
                border-radius: 6px;
            }
        """)
        
        # Add widgets to layout
        layout.addWidget(self.status_label)
        layout.addWidget(self.file_label)
        layout.addSpacing(10)
        layout.addWidget(self.progress_bar, 0, Qt.AlignCenter)
        
        # Set overall style with blur effect
        self.setStyleSheet("""
            QWidget#ScanOverlay {
                background-color: rgba(20, 20, 20, 180);
            }
        """)
        
        # Animation for smooth appearance
        self.fade_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_animation.setDuration(200)
        self.fade_animation.setEasingCurve(QEasingCurve.InOutQuad)
        
        # Hide initially
        self.hide()
    
    def show_scanning(self, status_text="Scanning library..."):
        """Show the overlay with scanning animation"""
        self.status_label.setText(status_text)
        self.file_label.setText("")
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(100)
        
        # Update geometry to match parent
        if self.parent():
            self.setGeometry(self.parent().rect())
        
        # Stop any running animation
        if self.fade_animation.state() == QPropertyAnimation.Running:
            self.fade_animation.stop()
        
        # Disconnect any previous connections
        try:
            self.fade_animation.finished.disconnect()
        except:
            pass
        
        # Raise to top and show
        self.raise_()
        self.show()
        
        # Start fade-in animation
        self.setWindowOpacity(0)
        self.fade_animation.setStartValue(0)
        self.fade_animation.setEndValue(1)
        self.fade_animation.start()
    
    def update_progress(self, current, total, current_file=""):
        """Update progress bar and current file label"""
        if total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
            
        if current_file:
            # Truncate long filenames
            if len(current_file) > 60:
                current_file = "..." + current_file[-57:]
            self.file_label.setText(f"Scanning: {current_file}")
    
    def update_status(self, status_text):
        """Update the status label text"""
        self.status_label.setText(status_text)
    
    def hide_scanning(self):
        """Hide the overlay with fade-out animation"""
        # Stop any running animation
        if self.fade_animation.state() == QPropertyAnimation.Running:
            self.fade_animation.stop()
        
        # Disconnect any previous connections
        try:
            self.fade_animation.finished.disconnect()
        except:
            pass
        
        # Connect for this hide operation
        self.fade_animation.finished.connect(self.hide)
        
        # Fade out
        self.fade_animation.setStartValue(self.windowOpacity())
        self.fade_animation.setEndValue(0)
        self.fade_animation.start()
    
    def paintEvent(self, event):
        """Custom paint event for semi-transparent background"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw semi-transparent background with slight blur effect
        painter.fillRect(self.rect(), QColor(20, 20, 20, 180))
        
        super().paintEvent(event)
    
    def resizeEvent(self, event):
        """Handle parent resize"""
        if self.parent():
            self.setGeometry(self.parent().rect())
        super().resizeEvent(event)
