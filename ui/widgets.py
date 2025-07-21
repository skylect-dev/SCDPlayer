"""Custom UI widgets for SCDPlayer"""
from PyQt5.QtWidgets import QLabel, QSplashScreen
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QPolygon
from PyQt5.QtCore import QPoint
from version import __version__


class ScrollingLabel(QLabel):
    """Label that scrolls text when it's too long"""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.full_text = text
        self.scroll_timer = QTimer()
        self.scroll_timer.timeout.connect(self.scroll_text)
        self.scroll_position = 0
        self.pause_counter = 0
        self.pause_duration = 20  # Pause at start for 2 seconds (20 * 100ms)
        self.end_pause_duration = 15  # Pause at end for 1.5 seconds
        self.end_pause_counter = 0
        self.visible_length = 35  # Increased from 30 for more visible text
        self.scrolling_forward = True
        
    def setText(self, text):
        self.full_text = text
        self.scroll_position = 0
        self.pause_counter = 0
        self.end_pause_counter = 0
        self.scrolling_forward = True
        
        if len(text) > self.visible_length:
            super().setText(text[:self.visible_length])
            self.scroll_timer.start(100)  # Update every 100ms
        else:
            super().setText(text)
            self.scroll_timer.stop()
    
    def scroll_text(self):
        if len(self.full_text) <= self.visible_length:
            self.scroll_timer.stop()
            return
            
        # Pause at the beginning
        if self.scrolling_forward and self.pause_counter < self.pause_duration:
            self.pause_counter += 1
            return
            
        # Pause at the end
        if not self.scrolling_forward and self.end_pause_counter < self.end_pause_duration:
            self.end_pause_counter += 1
            return
            
        # Create scrolling effect
        if self.scrolling_forward:
            if self.scroll_position <= len(self.full_text) - self.visible_length:
                display_text = self.full_text[self.scroll_position:self.scroll_position + self.visible_length]
                super().setText(display_text)
                self.scroll_position += 1
            else:
                # Reached the end, start scrolling back
                self.scrolling_forward = False
                self.end_pause_counter = 0
        else:
            if self.scroll_position > 0:
                self.scroll_position -= 1
                display_text = self.full_text[self.scroll_position:self.scroll_position + self.visible_length]
                super().setText(display_text)
            else:
                # Reached the beginning, start scrolling forward
                self.scrolling_forward = True
                self.pause_counter = 0


class SplashScreen(QSplashScreen):
    """Custom splash screen for SCDPlayer"""
    def __init__(self):
        # Create splash screen pixmap
        splash_pixmap = self.create_splash_pixmap()
        super().__init__(splash_pixmap)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        
        # Show loading message
        self.showMessage("Loading SCDPlayer...", Qt.AlignCenter | Qt.AlignBottom, Qt.white)
        
    def create_splash_pixmap(self):
        """Create the splash screen image"""
        pixmap = QPixmap(400, 300)
        pixmap.fill(QColor("#1a1d23"))
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw background gradient effect
        for i in range(20):
            color = QColor("#23272e")
            color.setAlpha(255 - i * 10)
            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(200 - i * 10, 150 - i * 8, i * 20, i * 16)
        
        # Draw large music note icon
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#4a9eff"))
        
        # Note head
        painter.drawEllipse(160, 180, 40, 30)
        # Note stem
        painter.drawRect(195, 120, 8, 70)
        # Note flag
        painter.drawEllipse(203, 110, 30, 40)
        
        # Draw title
        font = QFont("Arial", 24, QFont.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#f0f0f0"))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "SCDPlayer")
        
        # Draw version
        font = QFont("Arial", 12)
        painter.setFont(font)
        painter.setPen(QColor("#888888"))
        version_rect = pixmap.rect()
        version_rect.adjust(0, 40, 0, 0)
        painter.drawText(version_rect, Qt.AlignCenter, f"v{__version__}")
        
        painter.end()
        return pixmap


def create_icon(icon_type, size=24):
    """Create simple icons using QPainter"""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#f0f0f0"))
    
    center = size // 2
    
    if icon_type == "play":
        # Triangle pointing right
        triangle = QPolygon([
            QPoint(center - 6, center - 8),
            QPoint(center - 6, center + 8),
            QPoint(center + 8, center)
        ])
        painter.drawPolygon(triangle)
        
    elif icon_type == "pause":
        # Two rectangles
        painter.drawRect(center - 8, center - 8, 5, 16)
        painter.drawRect(center + 3, center - 8, 5, 16)
        
    elif icon_type == "stop":
        # Square
        painter.drawRect(center - 6, center - 6, 12, 12)
        
    elif icon_type == "previous":
        # Left-pointing triangle with line
        painter.drawRect(center - 8, center - 8, 2, 16)
        triangle = QPolygon([
            QPoint(center + 6, center - 8),
            QPoint(center + 6, center + 8),
            QPoint(center - 4, center)
        ])
        painter.drawPolygon(triangle)
        
    elif icon_type == "next":
        # Right-pointing triangle with line
        triangle = QPolygon([
            QPoint(center - 6, center - 8),
            QPoint(center - 6, center + 8),
            QPoint(center + 4, center)
        ])
        painter.drawPolygon(triangle)
        painter.drawRect(center + 6, center - 8, 2, 16)
    
    painter.end()
    return QIcon(pixmap)
