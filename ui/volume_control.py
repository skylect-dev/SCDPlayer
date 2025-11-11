"""Visual volume control with speaker icon and draggable bars."""
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QRect, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QPen, QPainterPath, QCursor
from ui.tooltip import TooltipMixin


class VolumeControl(QWidget, TooltipMixin):
    """Outline speaker icon with 8 horizontal volume bars that can be clicked/dragged to adjust volume."""
    
    volumeChanged = pyqtSignal(int)  # Emits 0-100
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_tooltip()  # Initialize tooltip system
        
        self.setFixedSize(120, 40)
        self._volume = 70  # 0-100
        self._dragging = False
        self._hover = False
        self.setMouseTracking(True)
    
    def setVolume(self, volume: int):
        """Set volume (0-100)."""
        self._volume = max(0, min(100, volume))
        self.update()
    
    def volume(self) -> int:
        """Get current volume (0-100)."""
        return self._volume
    
    def _volume_from_x(self, x: int) -> int:
        """Convert X position to volume value based on bars."""
        # Calculate volume based on horizontal position in the bars area
        bars_start_x = 35
        bars_width = self.width() - bars_start_x - 5
        
        if x < bars_start_x:
            return self._volume  # Don't change if clicking on speaker icon
        
        # Calculate which bar was clicked
        relative_x = x - bars_start_x
        volume = int((relative_x / bars_width) * 100)
        return max(0, min(100, volume))
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            volume = self._volume_from_x(event.x())
            if volume != self._volume:
                self._volume = volume
                self.volumeChanged.emit(self._volume)
                self.update()
    
    def mouseMoveEvent(self, event):
        if self._dragging:
            volume = self._volume_from_x(event.x())
            if volume != self._volume:
                self._volume = volume
                self.volumeChanged.emit(self._volume)
                self.update()
                # Update tooltip during drag
                self.show_tooltip(f"{self._volume}%", QCursor.pos(), delay=0)
        else:
            # Check if hovering
            was_hover = self._hover
            self._hover = self.rect().contains(event.pos())
            if was_hover != self._hover:
                if self._hover:
                    # Show tooltip on hover
                    self.show_tooltip(f"{self._volume}%", QCursor.pos())
                else:
                    # Hide tooltip when leaving
                    self.hide_tooltip()
                self.update()
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = False
            # Keep tooltip visible after release if still hovering
            if self._hover:
                self.show_tooltip(f"{self._volume}%", QCursor.pos(), delay=0)
    
    def leaveEvent(self, event):
        self._hover = False
        self.hide_tooltip()
        self.update()
    
    def wheelEvent(self, event):
        """Adjust volume with mouse wheel."""
        delta = event.angleDelta().y()
        if delta > 0:
            self._volume = min(100, self._volume + 5)
        else:
            self._volume = max(0, self._volume - 5)
        self.volumeChanged.emit(self._volume)
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Colors
        if self._volume == 0:
            icon_color = QColor(150, 150, 150)  # Muted gray
        else:
            icon_color = QColor(220, 220, 220)  # White-ish
        
        bar_color_active = QColor(30, 126, 204)  # Blue bars
        bar_color_inactive = QColor(60, 60, 60)  # Dark gray
        if self._hover:
            bar_color_active = QColor(50, 146, 224)  # Lighter blue on hover
        
        # Draw outline speaker icon (left side) - simple, no sound waves
        speaker_x = 8
        speaker_y = self.height() // 2
        
        # Speaker cone outline
        path = QPainterPath()
        path.moveTo(speaker_x, speaker_y - 6)
        path.lineTo(speaker_x + 6, speaker_y - 6)
        path.lineTo(speaker_x + 10, speaker_y - 10)
        path.lineTo(speaker_x + 10, speaker_y + 10)
        path.lineTo(speaker_x + 6, speaker_y + 6)
        path.lineTo(speaker_x, speaker_y + 6)
        path.closeSubpath()
        
        painter.setPen(QPen(icon_color, 1.5))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)
        
        # Draw 8 volume bars (right side) aligned at bottom
        bars_start_x = 35
        bar_width = 8
        bar_spacing = 2
        bar_gap = bar_width + bar_spacing
        num_bars = 8
        
        # Calculate how many bars should be lit based on volume
        bars_to_show = int((self._volume / 100.0) * num_bars)
        
        for i in range(num_bars):
            # Each bar has different height, all aligned at bottom
            # Heights increase from left to right
            bar_height = 8 + (i * 3)  # Progressive heights: 8, 11, 14, 17, 20, 23, 26, 29
            
            bar_x = bars_start_x + (i * bar_gap)
            bar_y = self.height() - bar_height - 5  # Align to bottom with 5px margin
            
            # Determine if this bar should be lit
            if i < bars_to_show:
                # Active bar
                painter.setBrush(bar_color_active)
                painter.setPen(QPen(bar_color_active.lighter(110), 1))
            elif i == bars_to_show and self._volume % 13 > 0:
                # Partial bar based on volume within range (100/8 ≈ 12.5)
                opacity = (self._volume % 13) / 13.0
                color = QColor(bar_color_active)
                painter.setOpacity(opacity)
                painter.setBrush(color)
                painter.setPen(QPen(color.lighter(110), 1))
            else:
                # Inactive bar
                painter.setBrush(bar_color_inactive)
                painter.setPen(QPen(bar_color_inactive.lighter(120), 1))
                painter.setOpacity(0.4)
            
            painter.drawRoundedRect(bar_x, bar_y, bar_width, bar_height, 2, 2)
            painter.setOpacity(1.0)
        
        # Draw mute "X" over speaker if volume is 0
        if self._volume == 0:
            painter.setPen(QPen(QColor(200, 80, 80), 2))
            painter.drawLine(
                speaker_x + 12, speaker_y - 8,
                speaker_x + 22, speaker_y + 8
            )
            painter.drawLine(
                speaker_x + 12, speaker_y + 8,
                speaker_x + 22, speaker_y - 8
            )
