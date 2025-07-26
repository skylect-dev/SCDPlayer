"""Advanced waveform visualization widget for loop editing"""
import numpy as np
from PyQt5.QtWidgets import QLabel, QPushButton
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPainter, QPen, QColor, QLinearGradient


class WaveformWidget(QLabel):
    """High-performance waveform display with loop region visualization"""
    
    positionClicked = pyqtSignal(int)  # Emit when waveform is clicked
    loopPointChanged = pyqtSignal(int, int)  # Emit when loop points change (start, end)
    positionChanged = pyqtSignal(int)  # Emit when position is dragged
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(120)
        self.setStyleSheet("""
            QLabel {
                background-color: #1e1e1e;
                border: 2px solid #444;
                border-radius: 6px;
            }
        """)
        
        # Waveform data
        self.waveform_data = None
        self.sample_rate = 44100
        self.total_samples = 0
        
        # Display properties
        self.current_position = 0
        self.loop_start = 0
        self.loop_end = 0
        self.loop_testing_active = False
        
        # Zoom properties
        self.zoom_factor = 1.0
        self.zoom_center = 0.5  # Center of zoom (0.0 to 1.0)
        self.auto_follow = False  # Follow current position
        
        # Interaction state
        self.dragging_position = False
        
        # Visual settings
        self.waveform_color = QColor(100, 150, 255)
        self.loop_color = QColor(0, 255, 0, 60)
        self.position_color = QColor(255, 255, 0)
        
        # Create focus button
        self.focus_button = QPushButton("📍", self)
        self.focus_button.setFixedSize(25, 25)
        self.focus_button.setStyleSheet("""
            QPushButton {
                background-color: #444;
                color: white;
                border: 1px solid #666;
                border-radius: 3px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #555;
            }
            QPushButton:pressed {
                background-color: #333;
            }
            QPushButton:checked {
                background-color: #0078d4;
                border-color: #0078d4;
            }
        """)
        self.focus_button.setCheckable(True)
        self.focus_button.setToolTip("Auto-follow current position")
        self.focus_button.clicked.connect(self._toggle_auto_follow)
        
        # Enable mouse interaction
        self.setCursor(Qt.PointingHandCursor)
    
    def set_waveform_data(self, data, sample_rate):
        """Set waveform data for display"""
        if data is not None and len(data) > 0:
            # Convert to mono if stereo
            if len(data.shape) > 1:
                data = np.mean(data, axis=1)
            
            self.waveform_data = data
            self.sample_rate = sample_rate
            self.total_samples = len(data)
            self.loop_end = self.total_samples
        else:
            self.waveform_data = None
            self.total_samples = 0
        
        self.update()
    
    def set_current_position(self, sample):
        """Update current playback position"""
        self.current_position = max(0, min(sample, self.total_samples))
        
        # Auto-follow current position if enabled
        if self.auto_follow and self.total_samples > 0:
            # Center zoom on current position
            position_ratio = self.current_position / self.total_samples
            self.zoom_center = position_ratio
            
        self.update()
    
    def _toggle_auto_follow(self):
        """Toggle auto-follow mode"""
        self.auto_follow = self.focus_button.isChecked()
        if self.auto_follow:
            # Immediately center on current position
            if self.total_samples > 0:
                position_ratio = self.current_position / self.total_samples
                self.zoom_center = position_ratio
                self.update()
    
    def resizeEvent(self, event):
        """Handle resize to position focus button"""
        super().resizeEvent(event)
        # Position button in top-right corner
        self.focus_button.move(self.width() - 30, 5)
    
    def set_loop_points(self, start_sample, end_sample):
        """Update loop points"""
        self.loop_start = max(0, min(start_sample, self.total_samples))
        self.loop_end = max(self.loop_start, min(end_sample, self.total_samples))
        self.update()
    
    def set_loop_testing_active(self, active):
        """Set loop testing state for visual feedback"""
        self.loop_testing_active = active
        self.update()
    
    def mousePressEvent(self, event):
        """Handle mouse clicks to set position or start dragging"""
        if event.button() != Qt.LeftButton or self.total_samples == 0:
            return
        
        x = event.x()
        
        # Check if clicking near current position indicator (within 8 pixels)
        current_x = self._sample_to_x(self.current_position)
        if abs(x - current_x) <= 8:
            # Start dragging position indicator
            self.dragging_position = True
            self.setCursor(Qt.SizeHorCursor)
            return
        
        # Calculate clicked sample position normally
        self._handle_position_click(x)
    
    def mouseMoveEvent(self, event):
        """Handle mouse move for dragging position indicator"""
        x = event.x()
        
        if self.dragging_position:
            # Drag current position indicator
            sample = self._x_to_sample(x)
            self.current_position = max(0, min(sample, self.total_samples))
            self.positionChanged.emit(self.current_position)
            self.update()
        else:
            # Update cursor based on hover state
            current_x = self._sample_to_x(self.current_position)
            if abs(x - current_x) <= 8:
                self.setCursor(Qt.SizeHorCursor)
            else:
                self.setCursor(Qt.PointingHandCursor)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release"""
        if self.dragging_position:
            self.dragging_position = False
            self.setCursor(Qt.PointingHandCursor)
    
    def _handle_position_click(self, x):
        """Handle click to set position (extracted from original mousePressEvent)"""
        # Calculate clicked sample position accounting for zoom
        width = self.width() - 20  # Account for margins
        relative_x = max(0, min(x - 10, width))
        
        # Calculate visible sample range based on zoom
        visible_samples = int(self.total_samples / self.zoom_factor)
        zoom_start = int(self.zoom_center * (self.total_samples - visible_samples))
        zoom_end = zoom_start + visible_samples
        
        # Ensure bounds are valid
        zoom_start = max(0, min(zoom_start, self.total_samples - 1))
        zoom_end = max(zoom_start + 1, min(zoom_end, self.total_samples))
        
        # Convert click position to sample within the visible range
        if width > 0:
            sample_ratio = relative_x / width
            clicked_sample = zoom_start + int(sample_ratio * (zoom_end - zoom_start))
            clicked_sample = max(0, min(clicked_sample, self.total_samples - 1))
        else:
            clicked_sample = 0
        
        self.positionClicked.emit(clicked_sample)
    
    def _sample_to_x(self, sample):
        """Convert sample position to x coordinate"""
        if self.total_samples == 0:
            return 10
        
        # Calculate visible sample range based on zoom
        visible_samples = int(self.total_samples / self.zoom_factor)
        zoom_start = int(self.zoom_center * (self.total_samples - visible_samples))
        zoom_end = zoom_start + visible_samples
        
        # Ensure bounds are valid
        zoom_start = max(0, min(zoom_start, self.total_samples - 1))
        zoom_end = max(zoom_start + 1, min(zoom_end, self.total_samples))
        
        # Convert sample to x position within visible range
        if sample < zoom_start or sample > zoom_end:
            return -1  # Not visible
        
        width = self.width() - 20  # Account for margins
        if zoom_end > zoom_start:
            relative_pos = (sample - zoom_start) / (zoom_end - zoom_start)
            return 10 + int(relative_pos * width)
        return 10
    
    def _x_to_sample(self, x):
        """Convert x coordinate to sample position"""
        if self.total_samples == 0:
            return 0
        
        width = self.width() - 20  # Account for margins
        relative_x = max(0, min(x - 10, width))
        
        # Calculate visible sample range based on zoom
        visible_samples = int(self.total_samples / self.zoom_factor)
        zoom_start = int(self.zoom_center * (self.total_samples - visible_samples))
        zoom_end = zoom_start + visible_samples
        
        # Ensure bounds are valid
        zoom_start = max(0, min(zoom_start, self.total_samples - 1))
        zoom_end = max(zoom_start + 1, min(zoom_end, self.total_samples))
        
        # Convert x position to sample within visible range
        if width > 0:
            sample_ratio = relative_x / width
            sample = zoom_start + int(sample_ratio * (zoom_end - zoom_start))
            return max(0, min(sample, self.total_samples - 1))
        return 0
    
    def wheelEvent(self, event):
        """Handle mouse wheel for zooming"""
        if self.total_samples == 0:
            return
        
        # Get scroll delta (positive = zoom in, negative = zoom out)
        delta = event.angleDelta().y()
        zoom_speed = 0.1
        
        # Calculate zoom factor change
        if delta > 0:
            # Zoom in
            zoom_change = 1.0 + zoom_speed
        else:
            # Zoom out
            zoom_change = 1.0 - zoom_speed
        
        # Update zoom factor with limits
        new_zoom = self.zoom_factor * zoom_change
        self.zoom_factor = max(1.0, min(new_zoom, 10.0))  # Limit zoom between 1x and 10x
        
        # Update zoom center based on mouse position
        x = event.x()
        width = self.width() - 20  # Account for margins
        relative_x = max(0, min(x - 10, width))
        self.zoom_center = relative_x / width if width > 0 else 0.5
        
        self.update()
        event.accept()
    
    def paintEvent(self, event):
        """Paint the waveform and loop indicators"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Background
        bg_color = QColor(35, 40, 50) if self.loop_testing_active else QColor(30, 30, 30)
        painter.fillRect(self.rect(), bg_color)
        
        if self.waveform_data is None or self.total_samples == 0:
            painter.setPen(QPen(QColor(100, 100, 100), 1))
            painter.drawText(self.rect(), Qt.AlignCenter, "No waveform data")
            return
        
        # Draw waveform
        self._draw_waveform(painter)
        
        # Draw loop region highlight
        if self.loop_start < self.loop_end:
            self._draw_loop_region(painter)
        
        # Draw current position line
        self._draw_position_line(painter)
        
        painter.end()
    
    def _draw_waveform(self, painter):
        """Draw the audio waveform with zoom support"""
        width = self.width() - 20
        height = self.height() - 20
        center_y = self.height() // 2
        margin = 10
        
        if width <= 0 or height <= 0:
            return
        
        # Calculate visible sample range based on zoom
        visible_samples = int(self.total_samples / self.zoom_factor)
        zoom_start = int(self.zoom_center * (self.total_samples - visible_samples))
        zoom_end = zoom_start + visible_samples
        
        # Ensure bounds are valid
        zoom_start = max(0, min(zoom_start, self.total_samples - 1))
        zoom_end = max(zoom_start + 1, min(zoom_end, self.total_samples))
        
        # Calculate samples per pixel for the visible range
        samples_per_pixel = max(1, (zoom_end - zoom_start) // width)
        
        # Create gradient for waveform
        gradient = QLinearGradient(0, center_y - height//4, 0, center_y + height//4)
        base_color = QColor(100, 150, 255) if not self.loop_testing_active else QColor(120, 170, 255)
        gradient.setColorAt(0, base_color)
        gradient.setColorAt(0.5, QColor(base_color.red(), base_color.green(), base_color.blue(), 180))
        gradient.setColorAt(1, base_color)
        
        painter.setPen(Qt.NoPen)
        painter.setBrush(gradient)
        
        # Draw waveform bars for visible range
        for x in range(width):
            # Calculate sample range for this pixel within the zoomed view
            start_sample = zoom_start + int(x * samples_per_pixel)
            end_sample = min(start_sample + samples_per_pixel, zoom_end)
            
            if start_sample >= self.total_samples:
                break
            
            # Get min/max values for this pixel range
            sample_slice = self.waveform_data[start_sample:end_sample]
            if len(sample_slice) > 0:
                min_val = np.min(sample_slice)
                max_val = np.max(sample_slice)
                
                # Scale to display height
                min_y = center_y - int(min_val * height // 4)
                max_y = center_y - int(max_val * height // 4)
                
                # Draw waveform bar
                bar_height = max(1, abs(max_y - min_y))
                painter.drawRect(margin + x, min(min_y, max_y), 1, bar_height)
    
    def _draw_loop_region(self, painter):
        """Draw loop region highlighting with zoom support"""
        if self.total_samples == 0:
            return
        
        width = self.width() - 20
        margin = 10
        
        # Calculate visible sample range based on zoom
        visible_samples = int(self.total_samples / self.zoom_factor)
        zoom_start = int(self.zoom_center * (self.total_samples - visible_samples))
        zoom_end = zoom_start + visible_samples
        
        # Ensure bounds are valid
        zoom_start = max(0, min(zoom_start, self.total_samples - 1))
        zoom_end = max(zoom_start + 1, min(zoom_end, self.total_samples))
        
        # Check if loop region is visible in current zoom
        if self.loop_end <= zoom_start or self.loop_start >= zoom_end:
            return  # Loop region not visible
        
        # Calculate visible loop boundaries
        visible_loop_start = max(self.loop_start, zoom_start)
        visible_loop_end = min(self.loop_end, zoom_end)
        
        # Convert to pixel coordinates within visible range
        if zoom_end > zoom_start:
            start_ratio = (visible_loop_start - zoom_start) / (zoom_end - zoom_start)
            end_ratio = (visible_loop_end - zoom_start) / (zoom_end - zoom_start)
            
            start_x = margin + int(start_ratio * width)
            end_x = margin + int(end_ratio * width)
            
            # Draw loop region background
            loop_color = QColor(0, 255, 0, 40) if not self.loop_testing_active else QColor(0, 255, 0, 60)
            painter.fillRect(start_x, 10, end_x - start_x, self.height() - 20, loop_color)
            
            # Draw loop boundaries if they're at the actual loop points
            boundary_color = QColor(0, 255, 0, 180) if not self.loop_testing_active else QColor(0, 255, 0, 220)
            painter.setPen(QPen(boundary_color, 2))
            
            if visible_loop_start == self.loop_start:
                painter.drawLine(start_x, 10, start_x, self.height() - 10)
            if visible_loop_end == self.loop_end:
                painter.drawLine(end_x, 10, end_x, self.height() - 10)
    
    def _draw_position_line(self, painter):
        """Draw current position indicator with zoom support"""
        if self.total_samples == 0:
            return
        
        width = self.width() - 20
        margin = 10
        
        # Calculate visible sample range based on zoom
        visible_samples = int(self.total_samples / self.zoom_factor)
        zoom_start = int(self.zoom_center * (self.total_samples - visible_samples))
        zoom_end = zoom_start + visible_samples
        
        # Ensure bounds are valid
        zoom_start = max(0, min(zoom_start, self.total_samples - 1))
        zoom_end = max(zoom_start + 1, min(zoom_end, self.total_samples))
        
        # Check if current position is visible in current zoom
        if self.current_position < zoom_start or self.current_position > zoom_end:
            return  # Position not visible
        
        # Calculate position pixel within visible range
        if zoom_end > zoom_start:
            position_ratio = (self.current_position - zoom_start) / (zoom_end - zoom_start)
            position_x = margin + int(position_ratio * width)
            
            # Draw position line with glow effect
            position_color = QColor(255, 255, 0, 200) if not self.loop_testing_active else QColor(255, 255, 100, 220)
            
            # Draw glow
            painter.setPen(QPen(QColor(255, 255, 0, 60), 4))
            painter.drawLine(position_x, 5, position_x, self.height() - 5)
            
            # Draw main line
            painter.setPen(QPen(position_color, 2))
            painter.drawLine(position_x, 5, position_x, self.height() - 5)
