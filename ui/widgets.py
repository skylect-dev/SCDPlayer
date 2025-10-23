"""Custom UI widgets for SCDPlayer"""
import math
import logging
from PyQt5.QtWidgets import QLabel, QSplashScreen, QSlider
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
    """Custom splash screen for SCDPlayer"""
    def __init__(self):
        # Initialize properties first
        self._message = "Loading SCDPlayer..."
        
        # Create base splash screen pixmap ONCE (cached)
        self._base_pixmap = self.create_base_pixmap()
        splash_pixmap = self.create_splash_with_message(self._message)
        super().__init__(splash_pixmap)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
    
    def showMessage(self, message, alignment=Qt.AlignLeft, color=Qt.black):
        """Override to efficiently update message without redrawing everything"""
        self._message = message
        # Only redraw the message on top of cached base pixmap
        new_pixmap = self.create_splash_with_message(message)
        self.setPixmap(new_pixmap)
    
    def finish(self, widget):
        """Override finish to clean up"""
        super().finish(widget)
    
    def create_base_pixmap(self):
        """Create the base splash screen image ONCE (without message text)"""
        # Create larger pixmap with transparent background
        width = 550
        height = 420  # Increased to prevent text cutoff
        pixmap = QPixmap(width, height)
        pixmap.fill(Qt.transparent)
        
        # Create painter
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Create rounded rectangle path for clipping
        from PyQt5.QtGui import QPainterPath
        path = QPainterPath()
        path.addRoundedRect(0, 0, width, height, 20, 20)
        
        # Clip to rounded rectangle
        painter.setClipPath(path)
        
        # Dark gradient background
        gradient = QLinearGradient(0, 0, width, height)
        gradient.setColorAt(0, QColor("#1e293b"))  # Dark slate
        gradient.setColorAt(1, QColor("#0f172a"))  # Very dark blue
        
        painter.fillRect(0, 0, width, height, gradient)
        
        # Static radial glow in center
        center_x = width // 2
        center_y = height // 2
        
        center_gradient = QRadialGradient(center_x, center_y, 220)
        glow_color = QColor("#22d3ee")
        glow_color.setAlphaF(0.3)
        center_gradient.setColorAt(0, glow_color)
        center_gradient.setColorAt(0.4, QColor("#1e293b"))
        center_gradient.setColorAt(1, QColor("#0f172a"))
        
        # Apply glow without clipping
        painter.setCompositionMode(QPainter.CompositionMode_Overlay)
        painter.fillRect(pixmap.rect(), center_gradient)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        
        # Static sound waves in background
        for i in range(4):  # 4 rings for good visual effect
            wave_radius = 85 + i * 30
            wave_opacity = 0.3 - i * 0.05  # Fade out as rings get larger
            
            # Alternate colors for visual variety
            if i % 2 == 0:
                color = QColor("#34d399")  # Emerald
            else:
                color = QColor("#22d3ee")  # Cyan
            
            color.setAlphaF(wave_opacity)
            painter.setPen(QPen(color, 2.5, Qt.SolidLine, Qt.RoundCap))
            painter.setBrush(Qt.NoBrush)
            
            # Draw static circles around the icon (centered)
            painter.drawEllipse(int(center_x - wave_radius), int(center_y - wave_radius), 
                              int(wave_radius * 2), int(wave_radius * 2))
        
        # Use your minimal icon as centerpiece (centered)
        icon_size = 100
        app_icon = create_app_icon(icon_size)
        icon_pixmap = app_icon.pixmap(icon_size, icon_size)
        painter.drawPixmap(center_x - icon_size // 2, center_y - icon_size // 2, icon_pixmap)
        
        # Draw static text (no animation)
        # Modern, clean title with sufficient vertical space
        font = QFont("Segoe UI", 38, QFont.Bold)  # Slightly smaller to prevent clipping
        painter.setFont(font)
        
        # Use gradient colors from the icon for title
        painter.setPen(QColor("#22d3ee"))  # Bright cyan
        title_rect = QRect(0, height - 145, width, 70)  # More vertical space and padding
        painter.drawText(title_rect, Qt.AlignCenter, "SCDPlayer")
        
        # Version with emerald accent
        font = QFont("Segoe UI", 12, QFont.Normal)
        painter.setFont(font)
        painter.setPen(QColor("#34d399"))  # Emerald green
        version_rect = QRect(0, height - 75, width, 25)
        painter.drawText(version_rect, Qt.AlignCenter, f"v{__version__}")
        
        # NOTE: Message text NOT drawn here - added separately in create_splash_with_message()
        
        painter.setOpacity(1.0)
        painter.end()
        return pixmap
    
    def create_splash_with_message(self, message):
        """Efficiently composite message text onto cached base pixmap"""
        # Copy the base pixmap (fast operation - just copies the pixel buffer)
        pixmap = QPixmap(self._base_pixmap)
        
        # Only paint the message text
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = 550
        height = 420
        
        # Loading message at bottom with more space
        if message:
            font = QFont("Segoe UI", 9, QFont.Normal)
            painter.setFont(font)
            painter.setPen(QColor("#94a3b8"))  # Light slate gray
            # Enable word wrap by drawing multiple lines if needed
            text_lines = message.split('\n') if '\n' in message else [message]
            y_offset = 0
            line_height = 15
            start_y = height - 50
            for line in text_lines:
                line_rect = QRect(10, start_y + y_offset, width - 20, line_height)
                painter.drawText(line_rect, Qt.AlignCenter, line)
                y_offset += line_height
        
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
