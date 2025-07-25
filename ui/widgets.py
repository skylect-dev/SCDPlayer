"""Custom UI widgets for SCDPlayer"""
import math
from PyQt5.QtWidgets import QLabel, QSplashScreen
from PyQt5.QtCore import QTimer, Qt, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QPolygon, QPen, QLinearGradient, QRadialGradient
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
    """Custom animated splash screen for SCDPlayer"""
    def __init__(self):
        # Initialize properties first
        self._animation_frame = 0
        self._message = "Loading SCDPlayer..."
        
        # Create initial splash screen pixmap
        splash_pixmap = self.create_splash_pixmap()
        super().__init__(splash_pixmap)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        
        # Animation timer for background waves (smooth animation)
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.update_animation)
        self.animation_timer.start(60)  # ~16 FPS - smooth animation
    
    def update_animation(self):
        """Update animation frame"""
        self._animation_frame = (self._animation_frame + 1) % 300  # 18 second cycle for very smooth animation
        # Force repaint with new animation frame
        self.repaint()
    
    def paintEvent(self, event):
        """Custom paint event to handle animated rendering"""
        # Create the current frame pixmap
        current_pixmap = self.create_splash_pixmap()
        
        # Paint it to the splash screen
        painter = QPainter(self)
        painter.drawPixmap(0, 0, current_pixmap)
        painter.end()
    
    def showMessage(self, message, alignment=Qt.AlignLeft, color=Qt.black):
        """Override to store message for custom rendering"""
        self._message = message
        # Don't call super() - we handle message rendering ourselves
    
    def finish(self, widget):
        """Override finish to stop animations"""
        self.animation_timer.stop()
        super().finish(widget)
        
    def create_splash_pixmap(self):
        """Create the animated splash screen image with minimal modern theme"""
        pixmap = QPixmap(500, 350)
        
        # Create dark gradient background matching the icon
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Dark gradient background (matching icon's background)
        gradient = QLinearGradient(0, 0, 500, 350)
        gradient.setColorAt(0, QColor("#1e293b"))  # Dark slate
        gradient.setColorAt(1, QColor("#0f172a"))  # Very dark blue
        painter.fillRect(pixmap.rect(), gradient)
        
        # Animated radial glow in center - smoother movement
        glow_offset = math.sin(self._animation_frame * 0.03) * 8  # Slower, smoother oscillation
        center_x = 250 + glow_offset * 0.5
        center_y = 175 + glow_offset * 0.3
        
        center_gradient = QRadialGradient(center_x, center_y, 180)
        
        # Animate the glow intensity - smoother
        glow_intensity = 0.25 + 0.1 * (1 + math.sin(self._animation_frame * 0.04)) / 2
        
        glow_color = QColor("#22d3ee")
        glow_color.setAlphaF(glow_intensity)
        center_gradient.setColorAt(0, glow_color)
        center_gradient.setColorAt(0.4, QColor("#1e293b"))
        center_gradient.setColorAt(1, QColor("#0f172a"))
        
        # Apply animated glow
        painter.setCompositionMode(QPainter.CompositionMode_Overlay)
        painter.fillRect(pixmap.rect(), center_gradient)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        
        # Animated sound waves in background - smooth and continuous
        wave_phase = self._animation_frame * 0.04  # Slower, smoother wave animation
        
        for i in range(4):  # 4 rings for good visual effect
            # Calculate expanding wave radius - very smooth animation
            base_radius = 85 + i * 28
            wave_expansion = 10 * math.sin(wave_phase + i * 0.4)
            wave_radius = base_radius + wave_expansion
            
            # Calculate pulsing opacity - visible but subtle
            wave_opacity = 0.25 + 0.1 * math.sin(wave_phase + i * 0.6)
            
            # Alternate colors for visual variety
            if i % 2 == 0:
                color = QColor("#34d399")  # Emerald
            else:
                color = QColor("#22d3ee")  # Cyan
            
            color.setAlphaF(wave_opacity)
            painter.setPen(QPen(color, 2.0, Qt.SolidLine, Qt.RoundCap))
            painter.setBrush(Qt.NoBrush)
            
            # Draw expanding circles around the icon
            painter.drawEllipse(int(250 - wave_radius), int(175 - wave_radius), 
                              int(wave_radius * 2), int(wave_radius * 2))
        
        # Use your minimal icon as centerpiece
        app_icon = create_app_icon(100)
        icon_pixmap = app_icon.pixmap(100, 100)
        painter.drawPixmap(200, 125, icon_pixmap)
        
        # Draw static text (no animation)
        # Modern, clean title with better spacing
        font = QFont("Segoe UI", 38, QFont.Bold)
        painter.setFont(font)
        
        # Use gradient colors from the icon for title
        painter.setPen(QColor("#22d3ee"))  # Bright cyan
        title_rect = QRect(0, 245, 500, 50)
        painter.drawText(title_rect, Qt.AlignCenter, "SCDPlayer")
        
        # Version with emerald accent - better spacing
        font = QFont("Segoe UI", 16, QFont.Normal)
        painter.setFont(font)
        painter.setPen(QColor("#34d399"))  # Emerald green
        version_rect = QRect(0, 300, 500, 25)
        painter.drawText(version_rect, Qt.AlignCenter, f"v{__version__}")
        
        # Loading message at bottom
        if hasattr(self, '_message') and self._message:
            font = QFont("Segoe UI", 12, QFont.Normal)
            painter.setFont(font)
            painter.setPen(QColor("#94a3b8"))  # Light slate gray
            message_rect = QRect(0, 325, 500, 20)
            painter.drawText(message_rect, Qt.AlignCenter, self._message)
        
        painter.setOpacity(1.0)
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
