"""Precise timeline widget for audio loop editing with high-accuracy sample tracking"""
import numpy as np
from decimal import Decimal, getcontext
from PyQt5.QtWidgets import QLabel
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPainter, QPen, QColor, QFont, QPolygon
from PyQt5.QtCore import QPoint

# Set high precision for sample calculations
getcontext().prec = 50


class PreciseTimelineWidget(QLabel):
    """High-precision timeline with draggable markers for audio loop editing"""
    
    positionChanged = pyqtSignal(int)  # Current position changed
    loopStartChanged = pyqtSignal(int)  # Loop start changed
    loopEndChanged = pyqtSignal(int)  # Loop end changed
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(80)  # Increased height for better tooltip rendering
        self.setStyleSheet("""
            QLabel {
                background-color: #2a2a2a;
                border: 1px solid #444;
                border-radius: 4px;
            }
        """)
        
        # Audio properties - use Decimal for precision
        self.total_samples = 0
        self.sample_rate = Decimal('44100')
        self.duration_seconds = Decimal('0')
        
        # Timeline positions (in samples)
        self.current_position = 0
        self.loop_start = 0
        self.loop_end = 0
        
        # UI state
        self.dragging_current = False
        self.dragging_start = False
        self.dragging_end = False
        self.hover_marker = None
        self.loop_testing_active = False  # Track loop testing state
        self.fine_control_mode = False  # Track Ctrl key for fine control
        self.last_drag_sample = 0  # For fine control calculations
        self.drag_start_x = 0  # Starting x position for fine control
        self.current_drag_sample = 0  # Current sample during drag (for smooth transitions)
        
        # Visual properties
        self.margin = 10
        
        # Enable mouse tracking
        self.setMouseTracking(True)
        self.setCursor(Qt.ArrowCursor)
    
    def set_audio_info(self, total_samples, sample_rate):
        """Set audio information with high precision"""
        self.total_samples = total_samples
        self.sample_rate = Decimal(str(sample_rate))
        self.duration_seconds = Decimal(str(total_samples)) / self.sample_rate
        self.loop_end = total_samples
        self.update()
    
    def set_current_position(self, sample):
        """Set current playback position"""
        self.current_position = max(0, min(sample, self.total_samples))
        self.update()
    
    def set_loop_points(self, start_sample, end_sample):
        """Set loop points"""
        self.loop_start = max(0, min(start_sample, self.total_samples))
        self.loop_end = max(self.loop_start, min(end_sample, self.total_samples))
        self.update()
    
    def set_loop_testing_active(self, active):
        """Set loop testing state for visual feedback"""
        self.loop_testing_active = active
        self.update()
    
    def _sample_to_x(self, sample):
        """Convert sample position to X coordinate with high precision"""
        if self.total_samples == 0:
            return self.margin
        
        width = self.width() - 2 * self.margin
        # Use Decimal for precise calculation
        sample_decimal = Decimal(str(sample))
        total_decimal = Decimal(str(self.total_samples))
        position_ratio = sample_decimal / total_decimal
        
        x = self.margin + int(position_ratio * width)
        return x
    
    def _x_to_sample(self, x):
        """Convert X coordinate to sample position with high precision"""
        if self.total_samples == 0:
            return 0
        
        width = self.width() - 2 * self.margin
        relative_x = max(0, min(x - self.margin, width))
        
        # Use Decimal for precise calculation
        position_ratio = Decimal(str(relative_x)) / Decimal(str(width))
        sample = int(position_ratio * Decimal(str(self.total_samples)))
        
        return max(0, min(sample, self.total_samples))
    
    def _format_time_precise(self, sample):
        """Format sample position as precise time string"""
        if self.sample_rate == 0:
            return "0:00.000"
        
        # Use Decimal for precise time calculation
        sample_decimal = Decimal(str(sample))
        seconds_decimal = sample_decimal / self.sample_rate
        
        minutes = int(seconds_decimal // 60)
        remaining_seconds = seconds_decimal % 60
        seconds = int(remaining_seconds)
        milliseconds = int((remaining_seconds % 1) * 1000)
        
        return f"{minutes}:{seconds:02d}.{milliseconds:03d}"
    
    def mousePressEvent(self, event):
        """Handle mouse press for dragging markers"""
        if event.button() != Qt.LeftButton or self.total_samples == 0:
            return
        
        x = event.x()
        
        # Check for fine control mode
        self.fine_control_mode = bool(event.modifiers() & Qt.ControlModifier)
        
        # Check which marker is being clicked (8 pixel tolerance)
        current_x = self._sample_to_x(self.current_position)
        start_x = self._sample_to_x(self.loop_start)
        end_x = self._sample_to_x(self.loop_end)
        
        # Current position has highest priority
        if abs(x - current_x) <= 8:
            self.dragging_current = True
            self.current_drag_sample = self.current_position
            self.drag_start_x = x
            self.setCursor(Qt.SizeHorCursor)
        elif abs(x - start_x) <= 8:
            self.dragging_start = True
            self.current_drag_sample = self.loop_start
            self.drag_start_x = x
            self.setCursor(Qt.SizeHorCursor)
        elif abs(x - end_x) <= 8:
            self.dragging_end = True
            self.current_drag_sample = self.loop_end
            self.drag_start_x = x
            self.setCursor(Qt.SizeHorCursor)
        else:
            # Click on timeline to set current position
            sample = self._x_to_sample(x)
            self.current_position = sample
            self.positionChanged.emit(sample)
            self.update()
    
    def mouseMoveEvent(self, event):
        """Handle mouse move for dragging and hover effects"""
        x = event.x()
        
        # Update fine control mode dynamically during drag
        if self.dragging_current or self.dragging_start or self.dragging_end:
            new_fine_mode = bool(event.modifiers() & Qt.ControlModifier)
            
            # If switching to/from fine control, update both reference points for smooth transition
            if new_fine_mode != self.fine_control_mode:
                self.fine_control_mode = new_fine_mode
                self.drag_start_x = x  # Reset reference point for smooth transition
                
                # Update the current drag sample to current actual position to prevent snap-back
                if self.dragging_current:
                    self.current_drag_sample = self.current_position
                elif self.dragging_start:
                    self.current_drag_sample = self.loop_start
                elif self.dragging_end:
                    self.current_drag_sample = self.loop_end
        
        if self.dragging_current:
            if self.fine_control_mode:
                # Fine control: move 1 sample per 2 pixels (faster fine control)
                pixel_delta = x - self.drag_start_x
                sample_delta = int(pixel_delta / 2)
                sample = max(0, min(self.current_drag_sample + sample_delta, self.total_samples))
            else:
                # Normal control: direct pixel-to-sample conversion but slightly dampened
                sample = self._x_to_sample(x)
            
            # If loop testing is active, constrain to loop region
            if self.loop_testing_active:
                sample = max(self.loop_start, min(sample, self.loop_end))
            self.current_position = sample
            self.positionChanged.emit(sample)
            self.update()
            
        elif self.dragging_start:
            if self.fine_control_mode:
                # Fine control: move 1 sample per 2 pixels
                pixel_delta = x - self.drag_start_x
                sample_delta = int(pixel_delta / 2)
                sample = max(0, min(self.current_drag_sample + sample_delta, self.loop_end - 1))
            else:
                # Normal control: direct conversion
                sample = self._x_to_sample(x)
            
            self.loop_start = sample
            self.loopStartChanged.emit(self.loop_start)
            self.update()
            
        elif self.dragging_end:
            if self.fine_control_mode:
                # Fine control: move 1 sample per 2 pixels
                pixel_delta = x - self.drag_start_x
                sample_delta = int(pixel_delta / 2)
                sample = max(self.loop_start + 1, min(self.current_drag_sample + sample_delta, self.total_samples))
            else:
                # Normal control: direct conversion
                sample = self._x_to_sample(x)
            
            self.loop_end = sample
            self.loopEndChanged.emit(self.loop_end)
            self.update()
            
        else:
            # Update hover state for visual feedback
            current_x = self._sample_to_x(self.current_position)
            start_x = self._sample_to_x(self.loop_start)
            end_x = self._sample_to_x(self.loop_end)
            
            old_hover = self.hover_marker
            if abs(x - current_x) <= 8:
                self.hover_marker = "current"
                self.setCursor(Qt.SizeHorCursor)
            elif abs(x - start_x) <= 8:
                self.hover_marker = "start"
                self.setCursor(Qt.SizeHorCursor)
            elif abs(x - end_x) <= 8:
                self.hover_marker = "end"
                self.setCursor(Qt.SizeHorCursor)
            else:
                self.hover_marker = None
                self.setCursor(Qt.ArrowCursor)
            
            if old_hover != self.hover_marker:
                self.update()
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release"""
        self.dragging_current = False
        self.dragging_start = False
        self.dragging_end = False
        self.fine_control_mode = False
        self.current_drag_sample = 0
        self.setCursor(Qt.ArrowCursor)
    
    def paintEvent(self, event):
        """Paint the timeline and markers"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Background with loop testing indication
        if self.loop_testing_active:
            painter.fillRect(self.rect(), QColor(45, 50, 65))  # Slightly blue tint
        else:
            painter.fillRect(self.rect(), QColor(42, 42, 42))
        
        if self.total_samples == 0:
            painter.setPen(QPen(QColor(100, 100, 100), 1))
            painter.drawText(self.rect(), Qt.AlignCenter, "Load audio file to see timeline")
            return
        
        width = self.width() - 2 * self.margin
        timeline_y = self.height() // 2
        
        # Draw main timeline
        timeline_color = QColor(200, 220, 255) if self.loop_testing_active else QColor(180, 180, 180)
        painter.setPen(QPen(timeline_color, 2))
        painter.drawLine(self.margin, timeline_y, self.margin + width, timeline_y)
        
        # Draw time markers with precise intervals
        self._draw_time_markers(painter, timeline_y)
        
        # Draw loop region highlight
        if self.loop_start < self.loop_end:
            start_x = self._sample_to_x(self.loop_start)
            end_x = self._sample_to_x(self.loop_end)
            loop_color = QColor(0, 255, 0, 80) if self.loop_testing_active else QColor(0, 255, 0, 60)
            painter.fillRect(start_x, timeline_y - 3, end_x - start_x, 6, loop_color)
        
        # Draw markers
        self._draw_markers(painter, timeline_y)
        
        painter.end()
    
    def _draw_time_markers(self, painter, timeline_y):
        """Draw precise time markers along the timeline"""
        if float(self.duration_seconds) == 0:
            return
        
        # Calculate appropriate interval for readability
        duration_float = float(self.duration_seconds)
        if duration_float <= 10:
            interval_seconds = 1
        elif duration_float <= 60:
            interval_seconds = 5
        elif duration_float <= 300:
            interval_seconds = 15
        else:
            interval_seconds = 30
        
        painter.setPen(QPen(QColor(120, 120, 120), 1))
        painter.setFont(QFont("Segoe UI", 8))
        
        current_time = 0
        while current_time <= duration_float:
            sample = int(float(self.sample_rate) * current_time)
            if sample > self.total_samples:
                break
            
            x = self._sample_to_x(sample)
            
            # Draw tick mark
            painter.drawLine(x, timeline_y - 5, x, timeline_y + 5)
            
            # Draw time label with precise formatting
            time_str = self._format_time_precise(sample)
            painter.drawText(x - 20, timeline_y - 10, time_str)
            
            current_time += interval_seconds
    
    def _draw_markers(self, painter, timeline_y):
        """Draw loop and position markers"""
        # Loop start marker (green)
        start_x = self._sample_to_x(self.loop_start)
        start_color = QColor(0, 255, 0) if self.hover_marker != "start" else QColor(0, 200, 0)
        self._draw_marker(painter, start_x, timeline_y, start_color, f"Start: {self._format_time_precise(self.loop_start)}")
        
        # Loop end marker (red)
        end_x = self._sample_to_x(self.loop_end)
        end_color = QColor(255, 100, 100) if self.hover_marker != "end" else QColor(255, 50, 50)
        self._draw_marker(painter, end_x, timeline_y, end_color, f"End: {self._format_time_precise(self.loop_end)}")
        
        # Current position marker (yellow, drawn on top)
        current_x = self._sample_to_x(self.current_position)
        current_color = QColor(255, 255, 0) if self.hover_marker != "current" else QColor(255, 200, 0)
        self._draw_marker(painter, current_x, timeline_y, current_color, 
                         f"Current: {self._format_time_precise(self.current_position)}", top_priority=True)
    
    def _draw_marker(self, painter, x, y, color, tooltip, top_priority=False):
        """Draw a timeline marker with precise positioning"""
        # Draw vertical line
        line_color = QColor(color)
        line_color.setAlpha(180)
        painter.setPen(QPen(line_color, 2))
        
        line_top = y - (20 if top_priority else 15)
        line_bottom = y + (20 if top_priority else 15)
        painter.drawLine(x, line_top, x, line_bottom)
        
        # Draw arrow triangle
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        
        arrow_y = line_top - (8 if top_priority else 5)
        triangle = QPolygon([
            QPoint(x, arrow_y + 8),
            QPoint(x - 6, arrow_y),
            QPoint(x + 6, arrow_y)
        ])
        painter.drawPolygon(triangle)
        
        # Draw tooltip on hover
        marker_type = "current" if top_priority else ("start" if "Start" in tooltip else "end")
        if self.hover_marker == marker_type:
            painter.setPen(QPen(QColor(255, 255, 255), 1))
            painter.setFont(QFont("Segoe UI", 8))
            text_rect = painter.fontMetrics().boundingRect(tooltip)
            
            # Position tooltip above the arrow with better spacing
            text_x = max(5, min(x - text_rect.width() // 2, self.width() - text_rect.width() - 5))
            text_y = arrow_y - 10  # More space above the arrow
            
            # Ensure tooltip doesn't go above widget bounds
            if text_y - text_rect.height() < 5:
                text_y = arrow_y + 25  # Position below if not enough space above
            
            # Draw tooltip background with rounded corners effect
            bg_rect_x = text_x - 4
            bg_rect_y = text_y - text_rect.height() - 4
            bg_rect_w = text_rect.width() + 8
            bg_rect_h = text_rect.height() + 8
            
            painter.setBrush(QColor(0, 0, 0, 200))
            painter.setPen(QPen(QColor(100, 100, 100), 1))
            painter.drawRect(bg_rect_x, bg_rect_y, bg_rect_w, bg_rect_h)
            
            # Draw tooltip text
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(255, 255, 255), 1))
            painter.drawText(text_x, text_y - 2, tooltip)
