"""Custom UI widgets for SCDPlayer"""
from PyQt5.QtWidgets import QLabel, QSplashScreen
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QPolygon, QPen
from PyQt5.QtCore import QPoint, QRect
from PyQt5.QtSvg import QSvgRenderer
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
        for i in range(15):
            color = QColor("#23272e")
            color.setAlpha(255 - i * 15)
            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(200 - i * 8, 150 - i * 6, i * 16, i * 12)
        
        # Use the new app icon as the centerpiece (larger size)
        app_icon = create_app_icon(80)
        icon_pixmap = app_icon.pixmap(80, 80)
        painter.drawPixmap(160, 120, icon_pixmap)
        
        # Draw title
        font = QFont("Segoe UI", 28, QFont.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#ffffff"))
        title_rect = QRect(0, 220, 400, 40)
        painter.drawText(title_rect, Qt.AlignCenter, "SCDPlayer")
        
        # Draw version with better contrast
        font = QFont("Segoe UI", 14)
        painter.setFont(font)
        painter.setPen(QColor("#4a9eff"))  # Use brand color for better visibility
        version_rect = QRect(0, 250, 400, 30)
        painter.drawText(version_rect, Qt.AlignCenter, f"v{__version__}")
        
        # Add subtitle
        font = QFont("Segoe UI", 11)
        painter.setFont(font)
        painter.setPen(QColor("#cccccc"))
        subtitle_rect = QRect(0, 270, 400, 20)
        painter.drawText(subtitle_rect, Qt.AlignCenter, "Kingdom Hearts Audio Player")
        
        painter.end()
        return pixmap


def create_app_icon(size=32):
    """Load application icon from SVG file"""
    import os
    from pathlib import Path
    
    # Try to load SVG icon first
    assets_dir = Path(__file__).parent.parent / "assets"
    svg_path = assets_dir / "icon.svg"
    
    if svg_path.exists():
        try:
            # Load SVG and create icon
            svg_renderer = QSvgRenderer(str(svg_path))
            if svg_renderer.isValid():
                pixmap = QPixmap(size, size)
                pixmap.fill(Qt.transparent)
                painter = QPainter(pixmap)
                painter.setRenderHint(QPainter.Antialiasing)
                svg_renderer.render(painter)
                painter.end()
                return QIcon(pixmap)
        except Exception as e:
            print(f"Failed to load SVG icon: {e}")
    
    # Fallback to simple generated icon
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    
    # Simple music note icon as fallback
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#4a9eff"))
    painter.drawEllipse(size//4, size//2, size//3, size//4)
    painter.drawRect(size//2, size//4, size//16, size//2)
    
    painter.end()
    return QIcon(pixmap)


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
