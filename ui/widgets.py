"""Custom UI widgets for SCDToolkit"""
import math
import logging
from PyQt5.QtWidgets import QLabel, QSplashScreen, QSlider
from PyQt5.QtCore import QTimer, Qt, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QPolygon, QPen, QRadialGradient
from PyQt5.QtCore import QPoint, QRect
from PyQt5.QtSvg import QSvgRenderer


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
    """Minimal splash showing a pulsing app icon."""

    def __init__(self):
        pixmap = self._create_base_pixmap()
        super().__init__(pixmap)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)

        self._fade = None

    def _create_base_pixmap(self):
        size = 220
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # Soft radial background to frame the icon
        bg = QRadialGradient(size / 2, size / 2, size / 1.2)
        bg.setColorAt(0.0, QColor("#0f172a"))
        bg.setColorAt(1.0, QColor("#020617"))
        painter.setBrush(bg)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(0, 0, size, size)

        # Centered app icon from assets/icon.svg
        icon_size = int(size * 0.6)
        app_icon = create_app_icon(icon_size)
        icon_pixmap = app_icon.pixmap(icon_size, icon_size)
        x = (size - icon_pixmap.width()) // 2
        y = (size - icon_pixmap.height()) // 2
        painter.drawPixmap(x, y, icon_pixmap)

        painter.end()
        return pixmap

    def showMessage(self, *args, **kwargs):
        """No-op to keep API compatibility without rendering text."""
        return

    def fade_and_finish(self, widget, duration_ms: int = 500):
        """Fade out once the main window is ready, then finish."""
        if self._fade:
            self._fade.stop()

        self._fade = QPropertyAnimation(self, b"windowOpacity")
        self._fade.setDuration(duration_ms)
        self._fade.setStartValue(1.0)
        self._fade.setEndValue(0.0)
        self._fade.setEasingCurve(QEasingCurve.InOutQuad)

        def _on_done():
            super(SplashScreen, self).finish(widget)
        self._fade.finished.connect(_on_done)
        self._fade.start()


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
            logging.error(f"Failed to load SVG icon: {e}")
    
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


class LoopSlider(QSlider):
    """Custom slider that can display loop markers"""
    
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.loop_start = 0
        self.loop_end = 0
        self.show_markers = False
        
    def set_loop_markers(self, start, end, total_duration):
        """Set loop markers positions (all in milliseconds)"""
        print(f"DEBUG: Setting loop markers - start: {start}ms, end: {end}ms, total: {total_duration}ms")
        if total_duration > 0:
            self.loop_start = start
            self.loop_end = end
            self.show_markers = True
            self.update()  # Trigger repaint
        else:
            self.show_markers = False
            
    def clear_loop_markers(self):
        """Clear loop markers"""
        self.show_markers = False
        self.update()
        
    def paintEvent(self, event):
        """Custom paint to show loop markers"""
        # Draw the normal slider first
        super().paintEvent(event)
        
        if not self.show_markers:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Calculate marker positions
        slider_range = self.maximum() - self.minimum()
        if slider_range <= 0:
            return
            
        width = self.width()
        groove_margin = 10  # Approximate margin for the groove
        usable_width = width - (2 * groove_margin)
        
        # Calculate pixel positions for loop markers
        start_ratio = (self.loop_start - self.minimum()) / slider_range
        end_ratio = (self.loop_end - self.minimum()) / slider_range
        
        start_x = groove_margin + (start_ratio * usable_width)
        end_x = groove_margin + (end_ratio * usable_width)
        
        # Draw loop start marker (green)
        painter.setPen(QPen(QColor("#4a8a4a"), 2))
        painter.drawLine(int(start_x), 5, int(start_x), self.height() - 5)
        
        # Draw loop end marker (red)
        painter.setPen(QPen(QColor("#8a4a4a"), 2))
        painter.drawLine(int(end_x), 5, int(end_x), self.height() - 5)
        
        # Draw loop region highlight (semi-transparent)
        if end_x > start_x:
            painter.fillRect(int(start_x), 8, int(end_x - start_x), self.height() - 16, 
                           QColor(80, 120, 80, 40))
        
        painter.end()


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
        
    elif icon_type == "loop":
        # Loop icon - circular arrow
        painter.setPen(QPen(QColor("#f0f0f0"), 2, Qt.SolidLine))
        painter.setBrush(Qt.NoBrush)
        # Draw circular path
        painter.drawEllipse(center - 6, center - 6, 12, 12)
        # Draw arrow at the end
        arrow = QPolygon([
            QPoint(center + 6, center - 2),
            QPoint(center + 4, center - 6),
            QPoint(center + 8, center - 6)
        ])
        painter.setBrush(QColor("#f0f0f0"))
        painter.setPen(Qt.NoPen)
        painter.drawPolygon(arrow)
        
    elif icon_type == "loop_on":
        # Loop icon - circular arrow (highlighted)
        painter.setPen(QPen(QColor("#4a8a4a"), 3, Qt.SolidLine))
        painter.setBrush(Qt.NoBrush)
        # Draw circular path
        painter.drawEllipse(center - 6, center - 6, 12, 12)
        # Draw arrow at the end
        arrow = QPolygon([
            QPoint(center + 6, center - 2),
            QPoint(center + 4, center - 6),
            QPoint(center + 8, center - 6)
        ])
        painter.setBrush(QColor("#4a8a4a"))
        painter.setPen(Qt.NoPen)
        painter.drawPolygon(arrow)
    
    painter.end()
    return QIcon(pixmap)
