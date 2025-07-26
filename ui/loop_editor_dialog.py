"""
Professional Loop Editor with Audacity-style interface
Features:
- Waveform visualization
- Timeline with time/sample markers
- Loop point editing with visual feedback
- Keyboard shortcuts for precise control
- Fine control with Ctrl+drag
"""
import logging

import sys
import os
import wave
import struct
import numpy as np
from pathlib import Path
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
import logging

class WaveformWidget(QWidget):
    """High-performance waveform display widget"""
    
    positionChanged = pyqtSignal(int)  # Sample position
    loopPointChanged = pyqtSignal(int, int)  # start, end samples
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(200)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        # Audio data
        self.audio_data = None
        self.sample_rate = 44100
        self.total_samples = 0
        
        # Display parameters
        self.zoom_factor = 1.0
        self.scroll_position = 0
        self.samples_per_pixel = 1000
        
        # Loop points
        self.loop_start = 0
        self.loop_end = 0
        
        # UI state
        self.current_position = 0
        self.dragging_start = False
        self.dragging_end = False
        self.drag_offset = 0
        
        # Enable mouse tracking for better interaction
        self.setMouseTracking(True)
        
        # Scroll callbacks
        self.scrollChanged = None
        self.zoomChanged = None
        self.fine_control = False
        
        # Colors
        self.waveform_color = QColor(0, 150, 255)
        self.background_color = QColor(25, 25, 25)
        self.loop_start_color = QColor(0, 255, 0)
        self.loop_end_color = QColor(255, 0, 0)
        self.loop_region_color = QColor(255, 255, 0, 30)
        self.cursor_color = QColor(255, 255, 255)
        
        # Mouse tracking
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        
    def load_audio_data(self, wav_path: str) -> bool:
        """Load audio data from WAV file"""
        try:
            with wave.open(wav_path, 'rb') as wav_file:
                frames = wav_file.getnframes()
                sample_rate = wav_file.getframerate()
                channels = wav_file.getnchannels()
                sample_width = wav_file.getsampwidth()
                
                # Read raw audio data
                raw_data = wav_file.readframes(frames)
                
                # Convert to numpy array
                if sample_width == 1:
                    dtype = np.uint8
                elif sample_width == 2:
                    dtype = np.int16
                elif sample_width == 4:
                    dtype = np.int32
                else:
                    raise ValueError(f"Unsupported sample width: {sample_width}")
                
                audio_array = np.frombuffer(raw_data, dtype=dtype)
                
                # Handle stereo by taking one channel
                if channels == 2:
                    audio_array = audio_array[::2]  # Take left channel
                
                # Normalize to float
                if dtype == np.uint8:
                    audio_array = (audio_array.astype(np.float32) - 128) / 128.0
                elif dtype == np.int16:
                    audio_array = audio_array.astype(np.float32) / 32768.0
                elif dtype == np.int32:
                    audio_array = audio_array.astype(np.float32) / 2147483648.0
                
                self.audio_data = audio_array
                self.sample_rate = sample_rate
                self.total_samples = len(audio_array)
                
                # Calculate initial samples per pixel
                self.samples_per_pixel = max(1, self.total_samples // self.width())
                
                self.update()
                logging.info(f"Loaded audio: {frames} samples, {sample_rate}Hz, {channels}ch")
                return True
                
        except Exception as e:
            logging.error(f"Failed to load audio data: {e}")
            return False
    
    def set_loop_points(self, start: int, end: int):
        """Set loop points"""
        self.loop_start = max(0, min(start, self.total_samples))
        self.loop_end = max(0, min(end, self.total_samples))
        self.update()
        
    def set_current_position(self, position: int):
        """Set current playback position"""
        self.current_position = max(0, min(position, self.total_samples))
        self.update()
        
    def set_scroll_position(self, scroll_pos):
        """Set the scroll position"""
        self.scroll_position = scroll_pos
        self.update()
        
        # Update timeline if callback exists
        if self.scrollChanged:
            self.scrollChanged(self.scroll_position, self.zoom_factor, self.samples_per_pixel)
    
    def get_scroll_info(self):
        """Get scrolling information for scrollbar"""
        if self.total_samples == 0:
            return {'max_scroll': 0, 'page_step': 100, 'current_scroll': 0}
        
        visible_samples = self.width() * self.samples_per_pixel
        max_scroll = max(0, self.total_samples - visible_samples) // self.samples_per_pixel
        page_step = max(1, visible_samples // self.samples_per_pixel // 10)
        
        return {
            'max_scroll': max_scroll,
            'page_step': page_step,
            'current_scroll': self.scroll_position
        }
    
    def paintEvent(self, event):
        """Paint the waveform"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Fill background
        painter.fillRect(self.rect(), self.background_color)
        
        if self.audio_data is None:
            painter.setPen(Qt.white)
            painter.drawText(self.rect(), Qt.AlignCenter, "No audio loaded")
            return
        
        # Calculate visible sample range
        width = self.width()
        height = self.height()
        
        start_sample = int(self.scroll_position * self.samples_per_pixel)
        end_sample = int((self.scroll_position + width) * self.samples_per_pixel)
        end_sample = min(end_sample, self.total_samples)
        
        if start_sample >= end_sample:
            return
        
        # Draw loop region background
        if self.loop_end > self.loop_start > 0:
            loop_start_x = self.sample_to_pixel(self.loop_start)
            loop_end_x = self.sample_to_pixel(self.loop_end)
            
            if loop_end_x > 0 and loop_start_x < width:
                loop_rect = QRect(
                    max(0, loop_start_x),
                    0,
                    min(width, loop_end_x) - max(0, loop_start_x),
                    height
                )
                painter.fillRect(loop_rect, self.loop_region_color)
        
        # Draw waveform
        painter.setPen(QPen(self.waveform_color, 1))
        
        # Downsample for display
        samples_to_draw = end_sample - start_sample
        if samples_to_draw > width * 2:
            # Need to downsample
            step = samples_to_draw // (width * 2)
            
            points = []
            for i in range(0, width, 2):
                sample_idx = start_sample + int(i * self.samples_per_pixel)
                if sample_idx < len(self.audio_data):
                    # Get min/max in this pixel range
                    end_idx = min(sample_idx + step, len(self.audio_data))
                    chunk = self.audio_data[sample_idx:end_idx]
                    
                    if len(chunk) > 0:
                        min_val = np.min(chunk)
                        max_val = np.max(chunk)
                        
                        # Convert to pixel coordinates
                        y_center = height // 2
                        y_min = int(y_center - min_val * y_center * 0.8)
                        y_max = int(y_center - max_val * y_center * 0.8)
                        
                        # Draw vertical line for this pixel
                        painter.drawLine(i, y_max, i, y_min)
        else:
            # Can draw individual samples
            prev_point = None
            for i in range(width):
                sample_idx = start_sample + int(i * self.samples_per_pixel)
                if sample_idx < len(self.audio_data):
                    sample_val = self.audio_data[sample_idx]
                    y = int(height // 2 - sample_val * height // 2 * 0.8)
                    
                    current_point = QPoint(i, y)
                    if prev_point:
                        painter.drawLine(prev_point, current_point)
                    prev_point = current_point
        
        # Draw loop markers with better visibility
        if self.loop_start >= 0:  # Show even at position 0
            start_x = self.sample_to_pixel(self.loop_start)
            if -5 <= start_x <= width + 5:  # Show slightly outside visible area
                painter.setPen(QPen(self.loop_start_color, 2))
                painter.drawLine(start_x, 0, start_x, height)
                
                # Draw label
                painter.setPen(Qt.white)
                painter.drawText(max(2, start_x + 5), 15, "Loop Start")
        
        if self.loop_end > self.loop_start:
            end_x = self.sample_to_pixel(self.loop_end)
            if -5 <= end_x <= width + 5:  # Show slightly outside visible area
                painter.setPen(QPen(self.loop_end_color, 2))
                painter.drawLine(end_x, 0, end_x, height)
                
                # Draw label
                painter.setPen(Qt.white)
                painter.drawText(max(2, end_x + 5), 30, "Loop End")
        
        # Draw loop region highlight
        if self.loop_start >= 0 and self.loop_end > self.loop_start:
            start_x = max(0, self.sample_to_pixel(self.loop_start))
            end_x = min(width, self.sample_to_pixel(self.loop_end))
            
            if start_x < end_x:
                # Semi-transparent highlight
                painter.fillRect(int(start_x), 0, int(end_x - start_x), height, 
                               QColor(255, 255, 0, 30))
        
        # Draw playback cursor with better visibility
        if self.current_position >= 0:  # Show even at position 0
            cursor_x = self.sample_to_pixel(self.current_position)
            if -2 <= cursor_x <= width + 2:  # Show slightly outside visible area
                painter.setPen(QPen(self.cursor_color, 2))
                painter.drawLine(cursor_x, 0, cursor_x, height)
    
    def sample_to_pixel(self, sample: int) -> int:
        """Convert sample position to pixel coordinate"""
        return int((sample / self.samples_per_pixel) - self.scroll_position)
    
    def pixel_to_sample(self, pixel: int) -> int:
        """Convert pixel coordinate to sample position"""
        return int((pixel + self.scroll_position) * self.samples_per_pixel)
    
    def mousePressEvent(self, event):
        """Handle mouse press for dragging loop points"""
        if event.button() == Qt.LeftButton and self.audio_data is not None:
            sample_pos = self.pixel_to_sample(event.x())
            
            # Check if clicking near loop markers (allow for position 0)
            start_x = self.sample_to_pixel(self.loop_start)
            end_x = self.sample_to_pixel(self.loop_end)
            
            self.fine_control = event.modifiers() & Qt.ControlModifier
            
            if abs(event.x() - start_x) < 6 and self.loop_start >= 0:  # Reduced from 10 to 6 pixels
                self.dragging_start = True
                self._drag_start_x = event.x()  # Store starting drag position
                self._fine_base_start = self.loop_start  # Store initial position for fine control
                self.setCursor(Qt.SizeHorCursor)
            elif abs(event.x() - end_x) < 6 and self.loop_end > self.loop_start:  # Reduced from 10 to 6 pixels
                self.dragging_end = True
                self._drag_start_x = event.x()  # Store starting drag position
                self._fine_base_end = self.loop_end  # Store initial position for fine control
                self.setCursor(Qt.SizeHorCursor)
            else:
                # Set playback position
                self.current_position = max(0, min(sample_pos, self.total_samples))
                self.positionChanged.emit(self.current_position)
                self.update()
    
    def mouseMoveEvent(self, event):
        """Handle mouse move for dragging"""
        if self.audio_data is None:
            return
        
        sample_pos = self.pixel_to_sample(event.x())
        
        # Check current Ctrl state
        current_fine_control = event.modifiers() & Qt.ControlModifier
        
        if self.dragging_start:
            # Handle smooth Ctrl toggling during drag
            if current_fine_control != self.fine_control:
                self.fine_control = current_fine_control
                # Store the current position to prevent jumping
                self._ctrl_toggle_reference = self.loop_start
            
            if self.fine_control:
                # Fine control: small increments based on mouse movement
                if hasattr(self, '_ctrl_toggle_reference') and self._ctrl_toggle_reference is not None:
                    # Use stored reference point to prevent jumping
                    base_pos = self._ctrl_toggle_reference
                    self._ctrl_toggle_reference = None
                else:
                    base_pos = getattr(self, '_fine_base_start', self.loop_start)
                    if base_pos is None:
                        base_pos = self.loop_start
                    
                delta = (event.x() - getattr(self, '_drag_start_x', event.x())) * (self.samples_per_pixel // 20)
                self.loop_start = max(0, min(base_pos + delta, self.loop_end - 1))
                self._fine_base_start = base_pos
            else:
                # Normal control: direct position
                self.loop_start = max(0, min(sample_pos, self.loop_end - 1))
            
            self.loopPointChanged.emit(self.loop_start, self.loop_end)
            self.update()
            
        elif self.dragging_end:
            # Handle smooth Ctrl toggling during drag
            if current_fine_control != self.fine_control:
                self.fine_control = current_fine_control
                # Store the current position to prevent jumping
                self._ctrl_toggle_reference = self.loop_end
            
            if self.fine_control:
                # Fine control: small increments based on mouse movement
                if hasattr(self, '_ctrl_toggle_reference') and self._ctrl_toggle_reference is not None:
                    # Use stored reference point to prevent jumping
                    base_pos = self._ctrl_toggle_reference
                    self._ctrl_toggle_reference = None
                else:
                    base_pos = getattr(self, '_fine_base_end', self.loop_end)
                    if base_pos is None:
                        base_pos = self.loop_end
                    
                delta = (event.x() - getattr(self, '_drag_start_x', event.x())) * (self.samples_per_pixel // 20)
                self.loop_end = max(self.loop_start + 1, min(base_pos + delta, self.total_samples))
                self._fine_base_end = base_pos
            else:
                # Normal control: direct position
                self.loop_end = max(self.loop_start + 1, min(sample_pos, self.total_samples))
            
            self.loopPointChanged.emit(self.loop_start, self.loop_end)
            self.update()
        else:
            # Show resize cursor near loop markers (allow for position 0)
            start_x = self.sample_to_pixel(self.loop_start)
            end_x = self.sample_to_pixel(self.loop_end)
            
            if (abs(event.x() - start_x) < 6 and self.loop_start >= 0) or \
               (abs(event.x() - end_x) < 6 and self.loop_end > self.loop_start):
                self.setCursor(Qt.SizeHorCursor)
            else:
                self.setCursor(Qt.ArrowCursor)
        
        self._last_mouse_x = event.x()
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release"""
        if event.button() == Qt.LeftButton:
            self.dragging_start = False
            self.dragging_end = False
            # Clean up fine control state
            self._ctrl_toggle_reference = None
            if hasattr(self, '_fine_base_start'):
                delattr(self, '_fine_base_start')
            if hasattr(self, '_fine_base_end'):
                delattr(self, '_fine_base_end')
            if hasattr(self, '_drag_start_x'):
                delattr(self, '_drag_start_x')
            self.setCursor(Qt.ArrowCursor)
    
    def wheelEvent(self, event):
        """Handle zoom with mouse wheel - zoom around mouse position"""
        if self.audio_data is None:
            return
        
        # Get mouse position in samples before zoom
        mouse_x = event.x()
        mouse_sample_before = self.pixel_to_sample(mouse_x)
        
        # Calculate zoom
        zoom_factor = 1.2 if event.angleDelta().y() > 0 else 1/1.2
        
        # Calculate new samples per pixel with limits
        old_samples_per_pixel = self.samples_per_pixel
        new_samples_per_pixel = self.samples_per_pixel / zoom_factor
        
        # Limit zoom out (minimum samples per pixel to show full track)
        max_samples_per_pixel = max(1, self.total_samples / self.width())
        # Limit zoom in (maximum detail)
        min_samples_per_pixel = 1.0
        
        new_samples_per_pixel = max(min_samples_per_pixel, min(new_samples_per_pixel, max_samples_per_pixel))
        
        # Only update if zoom actually changed
        if abs(new_samples_per_pixel - old_samples_per_pixel) < 0.1:
            return
        
        self.samples_per_pixel = new_samples_per_pixel
        
        # Calculate mouse position after zoom
        mouse_sample_after = self.pixel_to_sample(mouse_x)
        
        # Adjust scroll to keep mouse position stable
        sample_diff = mouse_sample_before - mouse_sample_after
        pixel_diff = sample_diff / self.samples_per_pixel
        
        self.scroll_position += pixel_diff
        
        # Limit scroll position
        max_scroll = max(0, (self.total_samples / self.samples_per_pixel) - self.width())
        self.scroll_position = max(0, min(self.scroll_position, max_scroll))
        
        self.update()
        
        # Notify about zoom change for scrollbar update
        if self.zoomChanged:
            self.zoomChanged()
        
        # Update timeline view
        if self.scrollChanged:
            self.scrollChanged(self.scroll_position, self.zoom_factor, self.samples_per_pixel)
    
    def keyPressEvent(self, event):
        """Handle keyboard shortcuts"""
        if self.audio_data is None:
            return
        
        if event.key() == Qt.Key_S:
            # Set loop start at current position
            self.loop_start = self.current_position
            if self.loop_end <= self.loop_start:
                self.loop_end = self.total_samples
            self.loopPointChanged.emit(self.loop_start, self.loop_end)
            self.update()
            
        elif event.key() == Qt.Key_E:
            # Set loop end at current position
            self.loop_end = self.current_position
            if self.loop_start >= self.loop_end:
                self.loop_start = 0
            self.loopPointChanged.emit(self.loop_start, self.loop_end)
            self.update()
            
        elif event.key() == Qt.Key_C:
            # Clear loop points
            self.loop_start = 0
            self.loop_end = 0
            self.loopPointChanged.emit(0, 0)
            self.update()

class TimelineWidget(QWidget):
    """Timeline widget showing time markers"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(30)
        self.sample_rate = 44100
        self.total_samples = 0
        self.samples_per_pixel = 1000
        self.scroll_position = 0
        
    def set_audio_info(self, sample_rate: int, total_samples: int):
        """Set audio information"""
        self.sample_rate = sample_rate
        self.total_samples = total_samples
        self.update()
    
    def set_view_params(self, scroll_position: float, zoom_factor: float, samples_per_pixel: float):
        """Set view parameters from waveform widget"""
        self.samples_per_pixel = samples_per_pixel
        self.scroll_position = scroll_position
        self.update()
    
    def paintEvent(self, event):
        """Paint timeline with time markers"""
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(40, 40, 40))
        
        if self.total_samples == 0:
            return
        
        # Calculate time intervals
        width = self.width()
        visible_duration = width * self.samples_per_pixel / self.sample_rate
        
        # Choose appropriate time interval
        if visible_duration < 10:
            interval = 1  # 1 second
        elif visible_duration < 60:
            interval = 5  # 5 seconds
        elif visible_duration < 300:
            interval = 30  # 30 seconds
        else:
            interval = 60  # 1 minute
        
        # Draw time markers
        painter.setPen(Qt.white)
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)
        
        start_time = self.scroll_position * self.samples_per_pixel / self.sample_rate
        start_interval = int(start_time / interval) * interval
        
        for i in range(20):  # Max 20 markers
            time_sec = start_interval + i * interval
            sample_pos = time_sec * self.sample_rate
            
            if sample_pos > self.total_samples:
                break
            
            x = int((sample_pos / self.samples_per_pixel) - self.scroll_position)
            if x > width:
                break
            
            if x >= 0:
                # Draw tick mark
                painter.drawLine(x, 20, x, 30)
                
                # Draw time label
                if time_sec >= 60:
                    time_str = f"{int(time_sec // 60)}:{int(time_sec % 60):02d}"
                else:
                    time_str = f"{time_sec:.1f}s"
                
                painter.drawText(x + 2, 15, time_str)

class LoopEditorDialog(QDialog):
    """Professional loop editor dialog"""
    
    def __init__(self, loop_manager, parent=None):
        super().__init__(parent)
        self.loop_manager = loop_manager
        self.parent_window = parent
        
        # Pause main window audio if playing
        if hasattr(parent, 'player') and parent.player.state() == parent.player.PlayingState:
            parent.player.pause()
            self.main_was_playing = True
        else:
            self.main_was_playing = False
        
        # Initialize media player for playback
        self.media_player = QMediaPlayer()
        self.media_player.positionChanged.connect(self.on_playback_position_changed)
        self.media_player.stateChanged.connect(self.on_playback_state_changed)
        self.media_player.durationChanged.connect(self.on_duration_changed)
        
        # Playback state
        self.is_loop_testing = False
        # Position update timer for ultra-smooth sample-based updates
        self.position_timer = QTimer()
        self.position_timer.timeout.connect(self.update_sample_position)
        
        # Loop timer for checking loop boundaries
        self.loop_timer = QTimer()
        self.loop_timer.timeout.connect(self.check_loop_position)
        
        self.setup_ui()
        self.load_audio_data()
        
    def setup_ui(self):
        """Setup the user interface"""
        self.setWindowTitle("Loop Editor - Professional Audio Loop Point Editor")
        self.setMinimumSize(800, 500)
        self.resize(1200, 600)
        
        # Apply professional dark theme styling
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #444;
                border-radius: 4px;
                margin-top: 6px;
                padding-top: 6px;
                background-color: transparent;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px 0 4px;
                color: #ddd;
                background-color: #2b2b2b;
            }
            QLabel {
                color: #ddd;
                border: none;
                background-color: transparent;
            }
            QSpinBox {
                background-color: #404040;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 4px;
                color: white;
            }
            QSpinBox:focus {
                border-color: #4080ff;
            }
            QScrollBar:horizontal {
                background-color: #404040;
                height: 16px;
                border-radius: 8px;
            }
            QScrollBar::handle:horizontal {
                background-color: #666;
                border-radius: 8px;
                min-width: 20px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: #777;
            }
        """)
        
        layout = QVBoxLayout(self)
        
        # Timeline
        self.timeline = TimelineWidget()
        self.timeline.setMaximumHeight(40)
        layout.addWidget(self.timeline)
        
        # Waveform with scrollbar
        waveform_container = QWidget()
        waveform_layout = QHBoxLayout(waveform_container)
        waveform_layout.setContentsMargins(0, 0, 0, 0)
        
        self.waveform = WaveformWidget()
        self.waveform.positionChanged.connect(self.on_position_changed)
        self.waveform.loopPointChanged.connect(self.on_loop_points_changed)
        
        # Add horizontal scrollbar
        self.waveform_scroll = QScrollBar(Qt.Horizontal)
        self.waveform_scroll.valueChanged.connect(self.on_scroll_changed)
        
        waveform_layout.addWidget(self.waveform)
        
        # Vertical layout for waveform and scrollbar
        waveform_with_scroll = QVBoxLayout()
        waveform_with_scroll.setContentsMargins(0, 0, 0, 0)
        waveform_with_scroll.addWidget(self.waveform)
        waveform_with_scroll.addWidget(self.waveform_scroll)
        
        waveform_scroll_widget = QWidget()
        waveform_scroll_widget.setLayout(waveform_with_scroll)
        layout.addWidget(waveform_scroll_widget)
        
        # Playback controls
        playback_group = QGroupBox("Playback Controls")
        playback_layout = QHBoxLayout(playback_group)
        
        self.play_btn = QPushButton("Play")
        self.play_btn.clicked.connect(self.toggle_playback)
        self.play_btn.setStyleSheet("""
            QPushButton {
                background-color: #2060c0;
                border: 1px solid #4080ff;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
                color: white;
                min-width: 60px;
            }
            QPushButton:hover { background-color: #3070d0; }
            QPushButton:pressed { background-color: #1050a0; }
        """)
        playback_layout.addWidget(self.play_btn)
        
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self.stop_playback)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #404040;
                border: 1px solid #666;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
                color: white;
                min-width: 60px;
            }
            QPushButton:hover { background-color: #505050; }
            QPushButton:pressed { background-color: #303030; }
        """)
        playback_layout.addWidget(self.stop_btn)
        
        self.loop_test_btn = QPushButton("Loop")
        self.loop_test_btn.setCheckable(True)
        self.loop_test_btn.clicked.connect(self.toggle_loop_mode)
        self.loop_test_btn.setStyleSheet("""
            QPushButton {
                background-color: #404040;
                border: 1px solid #666;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
                color: white;
                min-width: 80px;
            }
            QPushButton:hover { background-color: #505050; }
            QPushButton:pressed { background-color: #303030; }
            QPushButton:checked {
                background-color: #c06020;
                border-color: #ff8040;
                color: white;
            }
        """)
        playback_layout.addWidget(self.loop_test_btn)
        
        playback_layout.addStretch()
        
        self.position_label = QLabel("0:00 / 0:00")
        self.position_label.setStyleSheet("color: #ccc; font-family: monospace;")
        playback_layout.addWidget(self.position_label)
        
        layout.addWidget(playback_group)
        
        # Controls
        controls_layout = QHBoxLayout()
        
        # Loop info group with better styling
        info_group = QGroupBox("Loop Point Controls")
        info_layout = QVBoxLayout(info_group)
        
        # Add helpful tip
        tip_label = QLabel("Tip: Use S to set start and E to set end at current position\nHold Ctrl while dragging markers for fine precision control (can be toggled mid-drag)")
        tip_label.setStyleSheet("color: #888; font-style: italic; padding: 5px; background-color: rgba(255, 255, 255, 0.05); border-radius: 3px;")
        tip_label.setWordWrap(True)
        info_layout.addWidget(tip_label)
        
        # Start point controls
        start_layout = QHBoxLayout()
        start_layout.addWidget(QLabel("Loop Start:"))
        
        self.start_spin = QSpinBox()
        self.start_spin.setMaximum(2147483647)
        self.start_spin.valueChanged.connect(self.on_loop_start_changed)
        self.start_spin.setStyleSheet("QSpinBox { padding: 4px; }")
        start_layout.addWidget(self.start_spin)
        start_layout.addWidget(QLabel("samples"))
        
        self.start_time_label = QLabel("(0.000s)")
        self.start_time_label.setStyleSheet("color: #aaa; font-size: 11px;")
        start_layout.addWidget(self.start_time_label)
        start_layout.addStretch()
        
        info_layout.addLayout(start_layout)
        
        # End point controls
        end_layout = QHBoxLayout()
        end_layout.addWidget(QLabel("Loop End:"))
        
        self.end_spin = QSpinBox()
        self.end_spin.setMaximum(2147483647)
        self.end_spin.valueChanged.connect(self.on_loop_end_changed)
        self.end_spin.setStyleSheet("QSpinBox { padding: 4px; }")
        end_layout.addWidget(self.end_spin)
        end_layout.addWidget(QLabel("samples"))
        
        self.end_time_label = QLabel("(0.000s)")
        self.end_time_label.setStyleSheet("color: #aaa; font-size: 11px;")
        end_layout.addWidget(self.end_time_label)
        end_layout.addStretch()
        
        info_layout.addLayout(end_layout)
        
        # Duration display
        duration_layout = QHBoxLayout()
        duration_layout.addWidget(QLabel("Duration:"))
        self.duration_label = QLabel("0 samples")
        self.duration_label.setStyleSheet("font-weight: bold; color: #ddd;")
        duration_layout.addWidget(self.duration_label)
        duration_layout.addStretch()
        info_layout.addLayout(duration_layout)
        
        controls_layout.addWidget(info_group)
        
        # Action buttons with professional styling
        button_group = QGroupBox("Actions")
        button_layout = QVBoxLayout(button_group)
        
        # Clear button
        self.clear_btn = QPushButton("Clear Loop Points (C)")
        self.clear_btn.clicked.connect(self.clear_loop_points)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #404040;
                border: 2px solid #666;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                color: white;
            }
            QPushButton:hover {
                background-color: #505050;
                border-color: #777;
            }
            QPushButton:pressed {
                background-color: #303030;
            }
        """)
        button_layout.addWidget(self.clear_btn)
        
        # Save button
        self.save_btn = QPushButton("Save Changes")
        self.save_btn.clicked.connect(self.save_changes)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #2060c0;
                border: 2px solid #4080ff;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                color: white;
            }
            QPushButton:hover {
                background-color: #3070d0;
                border-color: #5090ff;
            }
            QPushButton:pressed {
                background-color: #1050a0;
            }
        """)
        button_layout.addWidget(self.save_btn)
        
        # Cancel button
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancel_dialog)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #604040;
                border: 2px solid #806060;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                color: white;
            }
            QPushButton:hover {
                background-color: #705050;
                border-color: #907070;
            }
            QPushButton:pressed {
                background-color: #503030;
            }
        """)
        button_layout.addWidget(self.cancel_btn)
        
        controls_layout.addWidget(button_group)
        
        layout.addLayout(controls_layout)
        
        # Connect timeline to waveform and scrollbar
        self.waveform.scrollChanged = self.timeline.set_view_params
        self.waveform.zoomChanged = self.update_scrollbar_range
        
    def closeEvent(self, event):
        """Clean up when dialog closes"""
        # Stop all playback and timers
        self.media_player.stop()
        self.position_timer.stop()
        self.loop_timer.stop()
        
        # Resume main window audio if it was playing
        if self.main_was_playing and hasattr(self.parent_window, 'player'):
            self.parent_window.player.play()
        
        super().closeEvent(event)
    
    def keyPressEvent(self, event):
        """Handle global keyboard shortcuts regardless of focus"""
        # Space: Play/Pause toggle
        if event.key() == Qt.Key_Space:
            self.toggle_playback()
            event.accept()
            return
            
        # S: Set loop start at current position
        elif event.key() == Qt.Key_S:
            if hasattr(self.waveform, 'current_position'):
                current_pos = self.waveform.current_position
                end = self.end_spin.value()
                if end <= current_pos:
                    file_info = self.loop_manager.get_file_info()
                    end = file_info.get('total_samples', 0)
                self.waveform.set_loop_points(current_pos, end)
                self.update_loop_info(current_pos, end)
            event.accept()
            return
            
        # E: Set loop end at current position  
        elif event.key() == Qt.Key_E:
            if hasattr(self.waveform, 'current_position'):
                current_pos = self.waveform.current_position
                start = self.start_spin.value()
                if start >= current_pos:
                    start = 0
                self.waveform.set_loop_points(start, current_pos)
                self.update_loop_info(start, current_pos)
            event.accept()
            return
            
        # C: Clear loop points
        elif event.key() == Qt.Key_C:
            self.clear_loop_points()
            event.accept()
            return
            
        # L: Toggle loop mode
        elif event.key() == Qt.Key_L:
            self.loop_test_btn.setChecked(not self.loop_test_btn.isChecked())
            self.toggle_loop_mode()
            event.accept()
            return
        
        # Pass other keys to parent
        super().keyPressEvent(event)
        
    def load_audio_data(self):
        """Load audio data into the waveform widget"""
        if not self.loop_manager.get_wav_path():
            QMessageBox.warning(self, "Error", "No audio file loaded")
            return
        
        success = self.waveform.load_audio_data(self.loop_manager.get_wav_path())
        if not success:
            QMessageBox.warning(self, "Error", "Failed to load audio data")
            return
        
        # Set timeline info
        file_info = self.loop_manager.get_file_info()
        self.timeline.set_audio_info(file_info['sample_rate'], file_info['total_samples'])
        
        # Update file information display
        self.update_file_info_display(file_info)
        
        # Set current loop points or defaults
        start, end = self.loop_manager.get_loop_points()
        
        # If no loop points exist, set default end to track length
        if end == 0:
            file_info = self.loop_manager.get_file_info()
            end = file_info.get('total_samples', 0)
        
        self.waveform.set_loop_points(start, end)
        self.update_loop_info(start, end)
        
        # Initialize scrollbar
        self.update_scrollbar_range()
        
    def on_scroll_changed(self, value):
        """Handle scrollbar changes"""
        if hasattr(self.waveform, 'set_scroll_position'):
            self.waveform.set_scroll_position(value)
        
    def update_scrollbar_range(self):
        """Update scrollbar range based on zoom level"""
        if hasattr(self.waveform, 'get_scroll_info'):
            scroll_info = self.waveform.get_scroll_info()
            self.waveform_scroll.setRange(0, int(scroll_info.get('max_scroll', 0)))
            self.waveform_scroll.setPageStep(int(scroll_info.get('page_step', 100)))
            self.waveform_scroll.setValue(int(scroll_info.get('current_scroll', 0)))
        
    def update_file_info_display(self, file_info):
        """Update the file information display"""
        # This would need to be added to the dialog - for now just placeholder
        pass
        
    def on_position_changed(self, position: int):
        """Handle playback position change from waveform clicks"""
        # Seek to the clicked position
        file_info = self.loop_manager.get_file_info()
        sample_rate = file_info.get('sample_rate', 44100)
        position_ms = int((position / sample_rate) * 1000)
        
        # Seek the media player to this position
        self.media_player.setPosition(position_ms)
    
    def on_loop_points_changed(self, start: int, end: int):
        """Handle loop points change from waveform"""
        self.update_loop_info(start, end)
        
    def on_loop_start_changed(self, value: int):
        """Handle loop start change from spin box"""
        end = self.end_spin.value()
        if value < end:
            self.waveform.set_loop_points(value, end)
            self.update_duration_label(value, end)
            self.update_time_labels()
    
    def on_loop_end_changed(self, value: int):
        """Handle loop end change from spin box"""
        start = self.start_spin.value()
        if value > start:
            self.waveform.set_loop_points(start, value)
            self.update_duration_label(start, value)
            self.update_time_labels()
    
    def update_time_labels(self):
        """Update time labels for loop points"""
        file_info = self.loop_manager.get_file_info()
        sample_rate = file_info.get('sample_rate', 44100)
        
        if sample_rate > 0:
            start_time = f"({self.start_spin.value() / sample_rate:.3f}s)"
            end_time = f"({self.end_spin.value() / sample_rate:.3f}s)"
            self.start_time_label.setText(start_time)
            self.end_time_label.setText(end_time)
    
    def update_loop_info(self, start: int, end: int):
        """Update loop information displays"""
        self.start_spin.blockSignals(True)
        self.end_spin.blockSignals(True)
        
        self.start_spin.setValue(start)
        self.end_spin.setValue(end)
        
        self.start_spin.blockSignals(False)
        self.end_spin.blockSignals(False)
        
        self.update_duration_label(start, end)
        self.update_time_labels()
    
    def update_duration_label(self, start: int, end: int):
        """Update duration label"""
        if end > start:
            duration_samples = end - start
            file_info = self.loop_manager.get_file_info()
            duration_seconds = duration_samples / file_info['sample_rate']
            self.duration_label.setText(f"{duration_samples} samples ({duration_seconds:.2f}s)")
        else:
            self.duration_label.setText("0 samples")
    
    def clear_loop_points(self):
        """Clear loop points - set to track start and end"""
        file_info = self.loop_manager.get_file_info()
        track_end = file_info.get('total_samples', 0)
        self.waveform.set_loop_points(0, track_end)
        self.update_loop_info(0, track_end)
    
    def save_changes(self):
        """Save loop points and close"""
        start = self.start_spin.value()
        end = self.end_spin.value()
        
        logging.debug(f"Save changes - start: {start}, end: {end}")
        
        if end <= start and end > 0:
            QMessageBox.warning(self, "Invalid Loop", "Loop end must be greater than loop start")
            return
        
        # Save to loop manager
        if end > start and end > 0:
            logging.debug(f"Saving loop points: {start} -> {end}")
            success = self.loop_manager.set_loop_points(start, end)
            if success:
                # Save the actual loop data to file
                success = self.loop_manager.save_loop_points()
        else:
            logging.debug(f"Clearing loop points (start={start}, end={end})")
            success = self.loop_manager.clear_loop_points()
        
        if success:
            # Stop playback and all timers before closing
            self.media_player.stop()
            self.position_timer.stop()
            self.loop_timer.stop()
            self.accept()
        else:
            QMessageBox.warning(self, "Error", "Failed to save loop points")
    
    def cancel_dialog(self):
        """Cancel dialog and stop playback"""
        self.media_player.stop()
        self.position_timer.stop()
        self.loop_timer.stop()
        self.reject()
    
    # Playback methods
    def toggle_playback(self):
        """Toggle play/pause"""
        if self.media_player.state() == QMediaPlayer.PlayingState:
            self.media_player.pause()
            # Stop position updates when paused
            self.position_timer.stop()
        elif self.media_player.state() == QMediaPlayer.PausedState:
            # Resume from current position
            self.media_player.play()
            # Restart position updates
            self.position_timer.start(8)  # ~120 FPS for ultra-smooth updates
            if self.is_loop_testing:
                self.loop_timer.start(16)
        else:
            # Start fresh playback
            self.start_playback()
    
    def start_playback(self):
        """Start playback"""
        wav_path = self.loop_manager.get_wav_path()
        if not wav_path or not os.path.exists(wav_path):
            QMessageBox.warning(self, "Error", "No audio file available for playback")
            return
        
        # Only set media content if it's different or not set
        current_media = self.media_player.media()
        new_url = QUrl.fromLocalFile(wav_path)
        if current_media.isNull() or current_media.canonicalUrl() != new_url:
            self.media_player.setMedia(QMediaContent(new_url))
        
        # If loop mode is on and we're outside the loop, start from loop beginning
        if self.is_loop_testing:
            start = self.start_spin.value()
            end = self.end_spin.value()
            
            if start < end:  # Valid loop points
                current_ms = self.media_player.position()
                file_info = self.loop_manager.get_file_info()
                sample_rate = file_info.get('sample_rate', 44100)
                
                start_ms = int((start / sample_rate) * 1000)
                end_ms = int((end / sample_rate) * 1000)
                
                # If current position is outside loop, start from loop beginning
                if current_ms < start_ms or current_ms >= end_ms:
                    self.media_player.setPosition(start_ms)
        
        self.media_player.play()
        
        # Start ultra-smooth position updates
        self.position_timer.start(8)  # ~120 FPS for ultra-smooth updates
        
        # Start loop timer if loop mode is enabled
        if self.is_loop_testing:
            self.loop_timer.start(16)  # ~60 FPS for smooth visual updates
    
    def stop_playback(self):
        """Stop all playback"""
        self.media_player.stop()
        
        # Stop all timers
        self.position_timer.stop()
        self.loop_timer.stop()
    
    def toggle_loop_mode(self):
        """Toggle loop mode on/off"""
        self.is_loop_testing = self.loop_test_btn.isChecked()
        
        if self.is_loop_testing:
            # Start loop timer if playing
            if self.media_player.state() == QMediaPlayer.PlayingState:
                self.loop_timer.start(16)  # ~60 FPS for smooth visual updates
        else:
            # Stop loop timer
            self.loop_timer.stop()
    
    def update_sample_position(self):
        """Update position display with sample-accurate timing"""
        if self.media_player.state() != QMediaPlayer.PlayingState:
            return
            
        current_ms = self.media_player.position()
        if self.media_player.duration() > 0:
            # Ultra-smooth time display
            current_time = self.format_time(current_ms / 1000.0)
            total_time = self.format_time(self.media_player.duration() / 1000.0)
            self.position_label.setText(f"{current_time} / {total_time}")
        
        # Update waveform position with exact sample accuracy
        file_info = self.loop_manager.get_file_info()
        sample_rate = file_info.get('sample_rate', 44100)
        sample_position = int((current_ms / 1000.0) * sample_rate)
        
        if hasattr(self.waveform, 'set_current_position'):
            self.waveform.set_current_position(sample_position)

    def check_loop_position(self):
        """Check if we need to loop back to start"""
        if not self.is_loop_testing or self.media_player.state() != QMediaPlayer.PlayingState:
            return
        
        current_ms = self.media_player.position()
        file_info = self.loop_manager.get_file_info()
        sample_rate = file_info.get('sample_rate', 44100)
        
        start = self.start_spin.value()
        end = self.end_spin.value()
        
        if start >= end:
            return
        
        start_ms = int((start / sample_rate) * 1000)
        end_ms = int((end / sample_rate) * 1000)
        
        # If we've reached the loop end, jump back to start
        if current_ms >= end_ms - 50:  # 50ms buffer
            self.media_player.setPosition(start_ms)
    
    def on_playback_position_changed(self, position):
        """Handle playback position changes"""
        if self.media_player.duration() > 0:
            current_time = self.format_time(position / 1000.0)
            total_time = self.format_time(self.media_player.duration() / 1000.0)
            self.position_label.setText(f"{current_time} / {total_time}")
        
        # Update waveform position
        file_info = self.loop_manager.get_file_info()
        sample_rate = file_info.get('sample_rate', 44100)
        sample_position = int((position / 1000.0) * sample_rate)
        
        if hasattr(self.waveform, 'set_current_position'):
            self.waveform.set_current_position(sample_position)
    
    def on_playback_state_changed(self, state):
        """Handle playback state changes"""
        if state == QMediaPlayer.PlayingState:
            self.play_btn.setText("Pause")
        else:
            self.play_btn.setText("Play")
    
    def on_duration_changed(self, duration):
        """Handle duration changes"""
        if duration > 0:
            total_time = self.format_time(duration / 1000.0)
            current_time = self.format_time(self.media_player.position() / 1000.0)
            self.position_label.setText(f"{current_time} / {total_time}")
    
    def format_time(self, seconds):
        """Format time in mm:ss format"""
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes}:{seconds:02d}"

# Test function
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Mock loop manager for testing
    class MockLoopManager:
        def get_wav_path(self):
            return "test.wav"  # Replace with actual test file
        
        def get_file_info(self):
            return {
                'sample_rate': 44100,
                'total_samples': 1000000,
                'has_loop': False
            }
        
        def get_loop_points(self):
            return (0, 0)
        
        def set_loop_points(self, start, end):
            return True
        
        def clear_loop_points(self):
            return True
    
    mock_manager = MockLoopManager()
    dialog = LoopEditorDialog(mock_manager)
    dialog.show()
    
    sys.exit(app.exec_())
