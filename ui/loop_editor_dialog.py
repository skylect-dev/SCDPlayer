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
from core.audio_analysis import AudioAnalyzer, VolumeAdjustment


class SaveWorker(QThread):
    """Worker thread for saving SCD files to prevent UI blocking"""
    
    finished = pyqtSignal(bool)  # True if successful, False if failed
    error = pyqtSignal(str)      # Error message
    
    def __init__(self, loop_manager):
        super().__init__()
        self.loop_manager = loop_manager
    
    def run(self):
        """Run the save operation in background thread"""
        try:
            success = self.loop_manager.save_loop_points()
            self.finished.emit(success)
        except Exception as e:
            self.error.emit(str(e))


class CustomVolumeDialog(QDialog):
    """Dialog for custom volume adjustment settings"""
    
    def __init__(self, current_levels, parent=None):
        super().__init__(parent)
        self.current_levels = current_levels
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the custom volume dialog UI"""
        self.setWindowTitle("Custom Volume Adjustment")
        self.setModal(True)
        self.resize(400, 300)
        
        layout = QVBoxLayout(self)
        
        # Current levels display
        current_group = QGroupBox("Current Audio Levels")
        current_layout = QVBoxLayout(current_group)
        
        current_info = QLabel(f"""Current Peak: {self.current_levels.peak_db:.1f} dB
Current RMS: {self.current_levels.rms_db:.1f} dB
Dynamic Range: {self.current_levels.dynamic_range_db:.1f} dB

Note: Game audio typically peaks at 0.0 to -0.6dB
Real game audio averages around -13 to -18dB RMS""")
        current_info.setStyleSheet("font-family: monospace; color: #ddd; padding: 8px;")
        current_layout.addWidget(current_info)
        
        layout.addWidget(current_group)
        
        # Method selection
        method_group = QGroupBox("Normalization Method")
        method_layout = QVBoxLayout(method_group)
        
        self.method_peak = QRadioButton("Peak Normalization")
        self.method_peak.setChecked(True)  # Default to peak
        self.method_rms = QRadioButton("RMS Normalization") 
        
        method_layout.addWidget(self.method_peak)
        method_layout.addWidget(self.method_rms)
        
        layout.addWidget(method_group)
        
        # Target level input
        target_group = QGroupBox("Target Level")
        target_layout = QVBoxLayout(target_group)
        
        target_layout.addWidget(QLabel("Target dB level:"))
        
        input_layout = QHBoxLayout()
        self.target_spin = QDoubleSpinBox()
        self.target_spin.setRange(-60.0, 0.0)
        self.target_spin.setValue(-0.2)  # Updated to match real game audio
        self.target_spin.setSuffix(" dB")
        self.target_spin.setDecimals(1)
        self.target_spin.setSingleStep(0.1)
        
        input_layout.addWidget(self.target_spin)
        
        # Preset buttons
        preset_layout = QHBoxLayout()
        
        game_preset = QPushButton("Conservative (-0.6dB)")
        game_preset.clicked.connect(lambda: self.target_spin.setValue(-0.6))
        game_preset.setToolTip("Conservative peak level like some game audio")
        game_preset.setStyleSheet("QPushButton { background-color: #2a5a2a; }")
        
        typical_preset = QPushButton("Typical (-0.2dB)")  
        typical_preset.clicked.connect(lambda: self.target_spin.setValue(-0.2))
        typical_preset.setToolTip("Most common game audio peak level")
        typical_preset.setStyleSheet("QPushButton { background-color: #5a5a2a; }")
        
        max_preset = QPushButton("Maximum (0.0dB)")
        max_preset.clicked.connect(lambda: self.target_spin.setValue(0.0))
        max_preset.setToolTip("Maximum level with zero headroom (some game audio)")
        max_preset.setStyleSheet("QPushButton { background-color: #5a2a2a; }")
        
        preset_layout.addWidget(game_preset)
        preset_layout.addWidget(typical_preset)
        preset_layout.addWidget(max_preset)
        
        target_layout.addLayout(input_layout)
        target_layout.addLayout(preset_layout)
        
        layout.addWidget(target_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.ok_btn = QPushButton("Apply")
        self.ok_btn.clicked.connect(self.accept)
        self.ok_btn.setDefault(True)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(self.ok_btn)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
        
        # Connect method change to update recommended values
        self.method_peak.toggled.connect(self.update_recommended_value)
        self.method_rms.toggled.connect(self.update_recommended_value)
        
        # Style the dialog
        self.setStyleSheet("""
            QDialog { background-color: #2b2b2b; color: white; }
            QGroupBox { 
                font-weight: bold; 
                border: 1px solid #444; 
                border-radius: 4px; 
                margin-top: 6px; 
                padding-top: 6px; 
            }
            QGroupBox::title { 
                subcontrol-origin: margin; 
                left: 8px; 
                padding: 0 4px 0 4px; 
                color: #ddd; 
                background-color: #2b2b2b; 
            }
            QPushButton { 
                background-color: #404040; 
                border: 1px solid #666; 
                border-radius: 4px; 
                padding: 6px 12px; 
                color: white; 
            }
            QPushButton:hover { background-color: #505050; }
            QPushButton:pressed { background-color: #303030; }
            QDoubleSpinBox { 
                background-color: #404040; 
                border: 1px solid #555; 
                border-radius: 3px; 
                padding: 4px; 
                color: white; 
            }
        """)
    
    def update_recommended_value(self):
        """Update recommended value based on selected method"""
        if self.method_peak.isChecked():
            # For peak normalization, suggest -0.2dB for gaming (real game audio level)
            if self.target_spin.value() == -15.0:  # If it was RMS default
                self.target_spin.setValue(-0.2)
        else:  # RMS normalization
            # For RMS normalization, suggest -15dB (closer to real game audio)
            if self.target_spin.value() in [-0.6, -0.2, 0.0]:  # If it was peak default
                self.target_spin.setValue(-15.0)
    
    def get_settings(self):
        """Get the selected settings"""
        return {
            'method': 'peak' if self.method_peak.isChecked() else 'rms',
            'target_db': self.target_spin.value()
        }

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
        self.dragging_cursor = False
        self.drag_offset = 0
        
        # Enable mouse tracking for better interaction
        self.setMouseTracking(True)
        
        # Scroll callbacks
        self.scrollChanged = None
        self.zoomChanged = None
        self.fine_control = False
        
        # Colors
        self.waveform_color = QColor(255, 255, 255)
        self.background_color = QColor(20, 20, 20)
        self.loop_start_color = QColor(0, 255, 0)
        self.loop_end_color = QColor(255, 0, 0)
        self.loop_region_color = QColor(55, 100, 0, 5)
        self.cursor_color = QColor(0, 50, 255)
        
        # Mouse tracking
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        
        # Track if initial zoom has been calculated
        self._initial_zoom_set = False
        
        # Focus icon properties
        self.focus_icon_rect = QRect()
        self.focus_icon_hovered = False
        self.focus_callback = None  # Will be set by the dialog
        self.follow_callback = None  # Will be set by the dialog for auto-follow
        self.is_focused_on_position = False  # Track if currently focused on playback position
        
        # Follow mode timing control
        self._last_follow_time = 0
        self._follow_cooldown = 250  # Only allow follow adjustments every 250ms
        
        # Smooth scrolling
        self._smooth_scroll_timer = QTimer()
        self._smooth_scroll_timer.timeout.connect(self._update_smooth_scroll)
        self._smooth_scroll_timer.setSingleShot(False)
        self._smooth_scroll_start = 0
        self._smooth_scroll_target = 0
        self._smooth_scroll_duration = 200  # 200ms for smooth scroll
        self._smooth_scroll_start_time = 0
        
    def showEvent(self, event):
        """Handle show event to set proper initial zoom"""
        super().showEvent(event)
        
        # Set proper initial zoom when widget is first shown and properly sized
        if not self._initial_zoom_set and self.audio_data is not None and self.width() > 0:
            # Show the full track length initially
            self.samples_per_pixel = max(1, self.total_samples / self.width())
            
            self._initial_zoom_set = True
            self.update()
            
            # Update scroll info if callback exists
            if self.scrollChanged:
                self.scrollChanged(self.scroll_position, self.zoom_factor, self.samples_per_pixel)
        
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
                elif sample_width == 3:
                    # 24-bit audio - convert to 32-bit for processing
                    # Read as bytes and convert to int32
                    audio_bytes = np.frombuffer(raw_data, dtype=np.uint8)
                    # Reshape to get 3 bytes per sample
                    num_samples = len(audio_bytes) // (3 * channels)
                    audio_bytes = audio_bytes.reshape(num_samples * channels, 3)
                    # Convert 24-bit to 32-bit (pad with zero byte)
                    audio_int32 = np.zeros((len(audio_bytes), 4), dtype=np.uint8)
                    audio_int32[:, 1:4] = audio_bytes  # Copy 24 bits to upper bytes
                    audio_array = audio_int32.view(np.int32).flatten()
                    dtype = np.int32
                elif sample_width == 4:
                    dtype = np.int32
                else:
                    raise ValueError(f"Unsupported sample width: {sample_width}")
                
                # For non-24-bit, do standard conversion
                if sample_width != 3:
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
                    if sample_width == 3:
                        # 24-bit audio scaled to 32-bit range (shifted left by 8 bits)
                        audio_array = audio_array.astype(np.float32) / 2147483648.0
                    else:
                        # True 32-bit audio
                        audio_array = audio_array.astype(np.float32) / 2147483648.0
                
                self.audio_data = audio_array
                self.sample_rate = sample_rate
                self.total_samples = len(audio_array)
                
                # Calculate initial samples per pixel only if widget is properly sized
                if self.width() > 0:
                    # Show the full track length initially
                    self.samples_per_pixel = max(1, len(audio_array) / self.width())
                    
                    self._initial_zoom_set = True
                else:
                    # Will be calculated in showEvent when widget is properly sized
                    self._initial_zoom_set = False
                
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
        
        # If we're in focused mode, auto-follow the cursor
        if self.is_focused_on_position and self.follow_callback:
            self.follow_callback(self.current_position)
        
        self.update()
        
    def smooth_scroll_to(self, target_position):
        """Smoothly scroll to a target position"""
        import time
        
        # Don't start a new animation if we're already close to the target
        if abs(target_position - self.scroll_position) < 5:
            return
            
        self._smooth_scroll_start = self.scroll_position
        self._smooth_scroll_target = target_position
        self._smooth_scroll_start_time = time.time() * 1000
        
        # Start the smooth scroll timer (60 FPS)
        self._smooth_scroll_timer.start(16)
        
    def _update_smooth_scroll(self):
        """Update smooth scroll animation"""
        import time
        
        current_time = time.time() * 1000
        elapsed = current_time - self._smooth_scroll_start_time
        
        if elapsed >= self._smooth_scroll_duration:
            # Animation complete
            self._smooth_scroll_timer.stop()
            self.scroll_position = self._smooth_scroll_target
            self.update()
            
            # Update scrollbar to match final position
            if hasattr(self, 'parent') and hasattr(self.parent(), 'waveform_scroll'):
                parent_dialog = self
                while parent_dialog and not hasattr(parent_dialog, 'waveform_scroll'):
                    parent_dialog = parent_dialog.parent()
                if parent_dialog and hasattr(parent_dialog, 'waveform_scroll'):
                    parent_dialog.waveform_scroll.setValue(int(self.scroll_position))
        else:
            # Calculate eased position (ease-out cubic)
            progress = elapsed / self._smooth_scroll_duration
            progress = 1 - pow(1 - progress, 3)  # Ease-out cubic
            
            self.scroll_position = self._smooth_scroll_start + (self._smooth_scroll_target - self._smooth_scroll_start) * progress
            self.update()
        
    def set_scroll_position(self, scroll_pos):
        """Set the scroll position"""
        # Stop any smooth scrolling animation
        if self._smooth_scroll_timer.isActive():
            self._smooth_scroll_timer.stop()
            
        self.scroll_position = scroll_pos
        # Only reset focus state for manual user scrolling, not programmatic scrolling
        if not hasattr(self, '_setting_focus_scroll') and not hasattr(self, '_programmatic_scroll'):
            self.is_focused_on_position = False
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
    
    def update_waveform(self):
        """Force update of waveform display after audio data changes"""
        if self.audio_data is not None:
            self.total_samples = len(self.audio_data)
            
            # Recalculate samples per pixel if needed
            if self.width() > 0:
                # Try to maintain current zoom level if reasonable
                if self.samples_per_pixel <= 0 or not self._initial_zoom_set:
                    self.samples_per_pixel = max(1, self.total_samples / self.width())
                    self._initial_zoom_set = True
                
                # Ensure scroll position is still valid
                visible_samples = self.width() * self.samples_per_pixel
                max_scroll = max(0, self.total_samples - visible_samples) // self.samples_per_pixel
                self.scroll_position = min(self.scroll_position, max_scroll)
        
        self.update()  # Trigger a repaint
    
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
        
        # Draw waveform with improved accuracy
        painter.setPen(QPen(self.waveform_color, 1))
        
        # More sophisticated waveform rendering
        samples_to_draw = end_sample - start_sample
        
        # Always use min/max rendering for better accuracy
        for x in range(width):
            sample_start = start_sample + int(x * self.samples_per_pixel)
            sample_end = start_sample + int((x + 1) * self.samples_per_pixel)
            sample_end = min(sample_end, len(self.audio_data))
            
            if sample_start >= len(self.audio_data):
                break
                
            if sample_end <= sample_start:
                sample_end = sample_start + 1
                
            # Get the chunk of audio data for this pixel
            chunk = self.audio_data[sample_start:sample_end]
            
            if len(chunk) > 0:
                # Calculate min, max, and RMS for better visualization
                min_val = float(np.min(chunk))
                max_val = float(np.max(chunk))
                rms_val = float(np.sqrt(np.mean(chunk ** 2)))
                
                # Convert to pixel coordinates
                y_center = height // 2
                scale_factor = 0.9  # Use 90% of available height
                
                y_min = int(y_center - min_val * y_center * scale_factor)
                y_max = int(y_center - max_val * y_center * scale_factor)
                y_rms_pos = int(y_center - rms_val * y_center * scale_factor)
                y_rms_neg = int(y_center + rms_val * y_center * scale_factor)
                
                # Ensure y values are within bounds
                y_min = max(0, min(height - 1, y_min))
                y_max = max(0, min(height - 1, y_max))
                y_rms_pos = max(0, min(height - 1, y_rms_pos))
                y_rms_neg = max(0, min(height - 1, y_rms_neg))
                
                # Draw min/max line for peak information
                if y_max != y_min:
                    painter.setPen(QPen(self.waveform_color, 1))
                    painter.drawLine(x, y_max, x, y_min)
                
                # Draw RMS information with slightly different color for density
                if len(chunk) > 10:  # Only show RMS for chunks with enough samples
                    rms_color = QColor(self.waveform_color)
                    rms_color.setAlpha(180)  # Semi-transparent
                    painter.setPen(QPen(rms_color, 1))
                    if y_rms_pos != y_rms_neg:
                        painter.drawLine(x, y_rms_pos, x, y_rms_neg)
                else:
                    # For small chunks, just draw a single sample
                    avg_val = float(np.mean(chunk))
                    y_avg = int(y_center - avg_val * y_center * scale_factor)
                    y_avg = max(0, min(height - 1, y_avg))
                    painter.setPen(QPen(self.waveform_color, 1))
                    painter.drawPoint(x, y_avg)
        
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
        
        # Draw focus icon in top-right corner
        self._draw_focus_icon(painter, width, height)
    
    def _draw_focus_icon(self, painter, width, height):
        """Draw the focus icon in the top-right corner"""
        icon_size = 20
        margin = 8
        
        # Calculate icon position (top-right corner)
        icon_x = width - icon_size - margin
        icon_y = margin
        self.focus_icon_rect = QRect(icon_x, icon_y, icon_size, icon_size)
        
        # Set colors based on focus state and hover state
        if self.is_focused_on_position:
            # Active follow mode - bright colors
            if self.focus_icon_hovered:
                bg_color = QColor(100, 150, 255, 220)  # Bright blue
                icon_color = QColor(255, 255, 255)
            else:
                bg_color = QColor(70, 120, 255, 180)   # Blue
                icon_color = QColor(255, 255, 255)
        else:
            # Inactive follow mode - muted colors
            if self.focus_icon_hovered:
                bg_color = QColor(80, 80, 80, 200)
                icon_color = QColor(255, 255, 255)
            else:
                bg_color = QColor(50, 50, 50, 150)
                icon_color = QColor(200, 200, 200)
        
        # Draw background circle
        painter.setPen(Qt.NoPen)
        painter.setBrush(bg_color)
        painter.drawEllipse(self.focus_icon_rect)
        
        # Draw crosshair/target icon
        painter.setPen(QPen(icon_color, 2))
        center_x = icon_x + icon_size // 2
        center_y = icon_y + icon_size // 2
        
        # Draw crosshair lines
        painter.drawLine(center_x - 6, center_y, center_x + 6, center_y)  # Horizontal
        painter.drawLine(center_x, center_y - 6, center_x, center_y + 6)  # Vertical
        
        # Draw small circle in center
        painter.setPen(QPen(icon_color, 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(center_x - 2, center_y - 2, 4, 4)
    
    def sample_to_pixel(self, sample: int) -> int:
        """Convert sample position to pixel coordinate"""
        return int((sample / self.samples_per_pixel) - self.scroll_position)
    
    def pixel_to_sample(self, pixel: int) -> int:
        """Convert pixel coordinate to sample position"""
        return int((pixel + self.scroll_position) * self.samples_per_pixel)
    
    def mousePressEvent(self, event):
        """Handle mouse press for dragging loop points"""
        if event.button() == Qt.LeftButton and self.audio_data is not None:
            # Check if clicking on focus icon first
            if self.focus_icon_rect.contains(event.pos()):
                if self.focus_callback:
                    self.focus_callback()
                return
            
            sample_pos = self.pixel_to_sample(event.x())
            
            # Check if clicking near loop markers (allow for position 0)
            start_x = self.sample_to_pixel(self.loop_start)
            end_x = self.sample_to_pixel(self.loop_end)
            cursor_x = self.sample_to_pixel(self.current_position)
            
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
            elif abs(event.x() - cursor_x) < 6:  # Check if clicking near current time cursor
                self.dragging_cursor = True
                self._drag_start_x = event.x()  # Store starting drag position
                self._fine_base_cursor = self.current_position  # Store initial position for fine control
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
            
        elif self.dragging_cursor:
            # Handle smooth Ctrl toggling during drag
            if current_fine_control != self.fine_control:
                self.fine_control = current_fine_control
                # Store the current position to prevent jumping
                self._ctrl_toggle_reference = self.current_position
            
            if self.fine_control:
                # Fine control: small increments based on mouse movement
                if hasattr(self, '_ctrl_toggle_reference') and self._ctrl_toggle_reference is not None:
                    # Use stored reference point to prevent jumping
                    base_pos = self._ctrl_toggle_reference
                    self._ctrl_toggle_reference = None
                else:
                    base_pos = getattr(self, '_fine_base_cursor', self.current_position)
                    if base_pos is None:
                        base_pos = self.current_position
                    
                delta = (event.x() - getattr(self, '_drag_start_x', event.x())) * (self.samples_per_pixel // 20)
                self.current_position = max(0, min(base_pos + delta, self.total_samples))
                self._fine_base_cursor = base_pos
            else:
                # Normal control: direct position
                self.current_position = max(0, min(sample_pos, self.total_samples))
            
            self.positionChanged.emit(self.current_position)
            self.update()
        else:
            # Show resize cursor near loop markers or current time cursor (allow for position 0)
            start_x = self.sample_to_pixel(self.loop_start)
            end_x = self.sample_to_pixel(self.loop_end)
            cursor_x = self.sample_to_pixel(self.current_position)
            
            if (abs(event.x() - start_x) < 6 and self.loop_start >= 0) or \
               (abs(event.x() - end_x) < 6 and self.loop_end > self.loop_start) or \
               abs(event.x() - cursor_x) < 6:
                self.setCursor(Qt.SizeHorCursor)
            else:
                self.setCursor(Qt.ArrowCursor)
        
        # Check if mouse is over focus icon
        was_hovered = self.focus_icon_hovered
        self.focus_icon_hovered = self.focus_icon_rect.contains(event.pos())
        if was_hovered != self.focus_icon_hovered:
            self.update()  # Redraw to show hover state
            if self.focus_icon_hovered:
                self.setCursor(Qt.PointingHandCursor)
                if self.is_focused_on_position:
                    self.setToolTip("Show full track (F)")
                else:
                    self.setToolTip("Toggle auto-follow cursor mode (F)")
            elif not (self.dragging_start or self.dragging_end or self.dragging_cursor):
                self.setCursor(Qt.ArrowCursor)
                self.setToolTip("")
        
        self._last_mouse_x = event.x()
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release"""
        if event.button() == Qt.LeftButton:
            self.dragging_start = False
            self.dragging_end = False
            self.dragging_cursor = False
            # Clean up fine control state
            self._ctrl_toggle_reference = None
            if hasattr(self, '_fine_base_start'):
                delattr(self, '_fine_base_start')
            if hasattr(self, '_fine_base_end'):
                delattr(self, '_fine_base_end')
            if hasattr(self, '_fine_base_cursor'):
                delattr(self, '_fine_base_cursor')
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
        
        # Protect follow state during zoom operations
        self._programmatic_scroll = True
        self.scroll_position += pixel_diff
        
        # Limit scroll position
        max_scroll = max(0, (self.total_samples / self.samples_per_pixel) - self.width())
        self.scroll_position = max(0, min(self.scroll_position, max_scroll))
        
        # Remove the programmatic scroll flag
        delattr(self, '_programmatic_scroll')
        
        # Don't reset focus state when zooming - preserve it
        
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
            super().keyPressEvent(event)
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
        else:
            # Pass unhandled keys to parent
            super().keyPressEvent(event)

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
        
        # Initialize audio analyzer
        self.audio_analyzer = AudioAnalyzer()
        
        # Track if volume has been adjusted
        self._volume_adjusted = False
        self._original_audio_data = None  # Keep copy of original for comparison
        
        # Temporary file management for volume adjustments
        self._temp_wav_path = None  # Path to temporary volume-adjusted WAV file
        self._original_wav_path = None  # Original WAV file path
        self._temp_file_created = False  # Track if we created a temp file
        
        # Pause main window audio if playing
        if hasattr(parent, 'player') and parent.player.state() == parent.player.PlayingState:
            parent.pause_audio()
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
        self.setMinimumSize(800, 650)
        self.resize(1200, 750)
        
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
            QDoubleSpinBox {
                background-color: #404040;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 4px;
                color: white;
            }
            QDoubleSpinBox:focus {
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
        
        # Connect focus callback
        self.waveform.focus_callback = self.toggle_follow_mode
        
        # Connect follow callback for auto-follow behavior
        self.waveform.follow_callback = self.follow_playback_cursor
        
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
        tip_label = QLabel(
            "Hotkeys:\n"
            "S: Set loop start at cursor\n"
            "E: Set loop end at cursor\n"
            "C: Clear loop points\n"
            "F: Toggle auto-follow cursor\n"
            "L: Toggle loop playback\n"
            "Space: Play/Pause\n"
            "Ctrl+drag: Fine marker control"
        )
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
        
        # Add seconds input for start point
        start_layout.addWidget(QLabel("or"))
        self.start_time_spin = QDoubleSpinBox()
        self.start_time_spin.setMaximum(999999.999)
        self.start_time_spin.setDecimals(3)
        self.start_time_spin.setSingleStep(0.001)
        self.start_time_spin.valueChanged.connect(self.on_loop_start_time_changed)
        self.start_time_spin.setStyleSheet("QDoubleSpinBox { padding: 4px; }")
        start_layout.addWidget(self.start_time_spin)
        start_layout.addWidget(QLabel("seconds"))
        
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
        
        # Add seconds input for end point
        end_layout.addWidget(QLabel("or"))
        self.end_time_spin = QDoubleSpinBox()
        self.end_time_spin.setMaximum(999999.999)
        self.end_time_spin.setDecimals(3)
        self.end_time_spin.setSingleStep(0.001)
        self.end_time_spin.valueChanged.connect(self.on_loop_end_time_changed)
        self.end_time_spin.setStyleSheet("QDoubleSpinBox { padding: 4px; }")
        end_layout.addWidget(self.end_time_spin)
        end_layout.addWidget(QLabel("seconds"))
        
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
        
        # Audio Analysis Panel
        self.analysis_group = QGroupBox("Audio Analysis")
        self.analysis_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        analysis_layout = QVBoxLayout(self.analysis_group)
        
        # Analysis display area - make it expand with window
        self.analysis_text = QTextEdit()
        self.analysis_text.setMinimumHeight(150)
        self.analysis_text.setReadOnly(True)
        self.analysis_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.analysis_text.setStyleSheet("""
            QTextEdit {
                background-color: #2a2a2a;
                border: 1px solid #666;
                border-radius: 4px;
                padding: 8px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 11px;
                color: #ddd;
            }
        """)
        analysis_layout.addWidget(self.analysis_text)
        
        # Analysis button
        analyze_btn = QPushButton("Analyze Audio Levels")
        analyze_btn.clicked.connect(self.analyze_audio)
        analyze_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a4a4a;
                border: 1px solid #666;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
                color: white;
            }
            QPushButton:hover { background-color: #5a5a5a; }
            QPushButton:pressed { background-color: #3a3a3a; }
        """)
        analysis_layout.addWidget(analyze_btn)
        
        # Volume adjustment buttons
        volume_btn_layout = QHBoxLayout()
        
        self.auto_volume_btn = QPushButton("Auto Volume")
        self.auto_volume_btn.clicked.connect(self.auto_volume_adjustment)
        self.auto_volume_btn.setToolTip("Intelligent auto-leveling that targets realistic game audio levels (-0.2dB peak, -15dB RMS typical)")
        
        self.normalize_peak_btn = QPushButton("Normalize Peak")
        self.normalize_peak_btn.clicked.connect(self.normalize_peak)
        self.normalize_peak_btn.setToolTip("Normalize to -0.2dB peak level (typical game audio)")
        
        self.normalize_rms_btn = QPushButton("Normalize RMS") 
        self.normalize_rms_btn.clicked.connect(self.normalize_rms)
        self.normalize_rms_btn.setToolTip("Normalize to -15dB RMS level (game audio range)")
        
        self.custom_volume_btn = QPushButton("Custom Volume")
        self.custom_volume_btn.clicked.connect(self.custom_volume_adjustment)
        self.custom_volume_btn.setToolTip("Set custom target levels for peak or RMS normalization")
        
        self.reset_volume_btn = QPushButton("Reset Volume")
        self.reset_volume_btn.clicked.connect(self.reset_volume_adjustment)
        self.reset_volume_btn.setToolTip("Reset audio to original volume levels")
        self.reset_volume_btn.setEnabled(False)  # Only enabled after volume adjustment
        
        # Style the volume buttons
        volume_btn_style = """
            QPushButton {
                background-color: #2a5a2a;
                border: 1px solid #4a8a4a;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 10px;
                font-weight: bold;
                color: white;
            }
            QPushButton:hover { background-color: #3a6a3a; }
            QPushButton:pressed { background-color: #1a4a1a; }
            QPushButton:disabled { 
                background-color: #333;
                border-color: #555;
                color: #888;
            }
        """
        
        reset_btn_style = """
            QPushButton {
                background-color: #5a2a2a;
                border: 1px solid #8a4a4a;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 10px;
                font-weight: bold;
                color: white;
            }
            QPushButton:hover { background-color: #6a3a3a; }
            QPushButton:pressed { background-color: #4a1a1a; }
            QPushButton:disabled { 
                background-color: #333;
                border-color: #555;
                color: #888;
            }
        """
        
        self.auto_volume_btn.setStyleSheet(volume_btn_style)
        self.normalize_peak_btn.setStyleSheet(volume_btn_style)
        self.normalize_rms_btn.setStyleSheet(volume_btn_style)
        self.custom_volume_btn.setStyleSheet(volume_btn_style)
        self.reset_volume_btn.setStyleSheet(reset_btn_style)
        
        volume_btn_layout.addWidget(self.auto_volume_btn)
        volume_btn_layout.addWidget(self.normalize_peak_btn)
        volume_btn_layout.addWidget(self.normalize_rms_btn)
        volume_btn_layout.addWidget(self.custom_volume_btn)
        volume_btn_layout.addWidget(self.reset_volume_btn)
        
        analysis_layout.addLayout(volume_btn_layout)
        
        # Initially disable volume buttons until audio is loaded
        self.auto_volume_btn.setEnabled(False)
        self.normalize_peak_btn.setEnabled(False)
        self.normalize_rms_btn.setEnabled(False)
        self.custom_volume_btn.setEnabled(False)
        self.reset_volume_btn.setEnabled(False)
        
        controls_layout.addWidget(self.analysis_group, 1)  # Give analysis group more space with stretch factor
        
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
        
        # Clean up temporary files to release all file handles
        self._cleanup_temp_files()
        
        # Resume main window audio if it was playing
        if self.main_was_playing and hasattr(self.parent_window, 'play_audio'):
            self.parent_window.play_audio()
        
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
            
        # F: Toggle auto-follow cursor mode
        elif event.key() == Qt.Key_F:
            self.toggle_follow_mode()
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

        # Store original audio data for volume change detection
        if self.waveform.audio_data is not None:
            self._original_audio_data = self.waveform.audio_data.copy()
            self._volume_adjusted = False

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

        # Automatically analyze audio levels when file loads
        self.analysis_text.setText("Analyzing audio levels...")
        QTimer.singleShot(100, self.analyze_audio)  # Delay slightly to let UI update

        # Update volume button states  
        self._update_volume_buttons_state()

        # Initialize scrollbar and zoom properly after widget is shown
        QTimer.singleShot(200, self._finalize_waveform_setup)

    def _finalize_waveform_setup(self):
        """Finalize waveform setup after UI is fully initialized"""
        # Ensure proper zoom initialization
        if hasattr(self.waveform, 'audio_data') and self.waveform.audio_data is not None:
            # Reset zoom to show full waveform with proper scaling
            total_samples = len(self.waveform.audio_data)
            widget_width = self.waveform.width()
            if widget_width > 0:
                # Set samples per pixel to show full track
                self.waveform.samples_per_pixel = max(1, total_samples / widget_width)
                self.waveform._scroll_position = 0
                self.waveform.update()
                
                # IMPORTANT: Update timeline with the correct initial parameters
                if hasattr(self.waveform, 'scrollChanged') and self.waveform.scrollChanged:
                    self.waveform.scrollChanged(
                        self.waveform._scroll_position, 
                        self.waveform.zoom_factor, 
                        self.waveform.samples_per_pixel
                    )
        
        # Initialize scrollbar with correct values
        self.update_scrollbar_range()
        
    def on_scroll_changed(self, value):
        """Handle scrollbar changes"""
        if hasattr(self.waveform, 'set_scroll_position'):
            # Mark this as programmatic scroll to prevent follow state reset
            self.waveform._programmatic_scroll = True
            self.waveform.set_scroll_position(value)
            if hasattr(self.waveform, '_programmatic_scroll'):
                delattr(self.waveform, '_programmatic_scroll')
        
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
            self.update_time_spinboxes()
    
    def on_loop_end_changed(self, value: int):
        """Handle loop end change from spin box"""
        start = self.start_spin.value()
        if value > start:
            self.waveform.set_loop_points(start, value)
            self.update_duration_label(start, value)
            self.update_time_spinboxes()
    
    def on_loop_start_time_changed(self, time_seconds: float):
        """Handle loop start time change from seconds spin box"""
        file_info = self.loop_manager.get_file_info()
        sample_rate = file_info.get('sample_rate', 44100)
        
        if sample_rate > 0:
            sample_value = int(time_seconds * sample_rate)
            end = self.end_spin.value()
            if sample_value < end:
                self.start_spin.blockSignals(True)
                self.start_spin.setValue(sample_value)
                self.start_spin.blockSignals(False)
                self.waveform.set_loop_points(sample_value, end)
                self.update_duration_label(sample_value, end)
    
    def on_loop_end_time_changed(self, time_seconds: float):
        """Handle loop end time change from seconds spin box"""
        file_info = self.loop_manager.get_file_info()
        sample_rate = file_info.get('sample_rate', 44100)
        
        if sample_rate > 0:
            sample_value = int(time_seconds * sample_rate)
            start = self.start_spin.value()
            if sample_value > start:
                self.end_spin.blockSignals(True)
                self.end_spin.setValue(sample_value)
                self.end_spin.blockSignals(False)
                self.waveform.set_loop_points(start, sample_value)
                self.update_duration_label(start, sample_value)
    
    def update_time_spinboxes(self):
        """Update time spinboxes for loop points"""
        file_info = self.loop_manager.get_file_info()
        sample_rate = file_info.get('sample_rate', 44100)
        
        if sample_rate > 0:
            self.start_time_spin.blockSignals(True)
            self.end_time_spin.blockSignals(True)
            
            start_time = self.start_spin.value() / sample_rate
            end_time = self.end_spin.value() / sample_rate
            
            self.start_time_spin.setValue(start_time)
            self.end_time_spin.setValue(end_time)
            
            self.start_time_spin.blockSignals(False)
            self.end_time_spin.blockSignals(False)
    
    def update_time_labels(self):
        """Update time spinboxes for loop points (backward compatibility)"""
        self.update_time_spinboxes()
    
    def update_loop_info(self, start: int, end: int):
        """Update loop information displays"""
        self.start_spin.blockSignals(True)
        self.end_spin.blockSignals(True)
        self.start_time_spin.blockSignals(True)
        self.end_time_spin.blockSignals(True)
        
        self.start_spin.setValue(start)
        self.end_spin.setValue(end)
        
        # Update time spinboxes
        file_info = self.loop_manager.get_file_info()
        sample_rate = file_info.get('sample_rate', 44100)
        if sample_rate > 0:
            self.start_time_spin.setValue(start / sample_rate)
            self.end_time_spin.setValue(end / sample_rate)
        
        self.start_spin.blockSignals(False)
        self.end_spin.blockSignals(False)
        self.start_time_spin.blockSignals(False)
        self.end_time_spin.blockSignals(False)
        
        self.update_duration_label(start, end)
    
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
    
    def _save_volume_adjusted_audio(self) -> bool:
        """Save volume-adjusted audio data back to the temp WAV file"""
        if not self._volume_adjusted or self.waveform.audio_data is None:
            return True  # No volume adjustment to save
        
        try:
            import wave
            import struct
            import time
            import tempfile
            import shutil
            import os
            
            wav_path = self.loop_manager.get_wav_path()
            if not wav_path:
                logging.error("No WAV path available for saving volume adjustments")
                return False
            
            # Stop media player to release file handle
            was_playing = self.media_player.state() == QMediaPlayer.PlayingState
            self.media_player.stop()
            
            # Clear media to fully release file handle
            self.media_player.setMedia(QMediaContent())
            
            # Give more time for the file to be released (Windows can be slow)
            import time
            time.sleep(0.3)  # Increased from 0.1 to 0.3 seconds
            
            # Check if file is accessible before attempting to write
            try:
                # Try to open the file in append mode to test accessibility
                with open(wav_path, 'ab') as test_file:
                    pass  # Just test if we can open it
            except PermissionError:
                logging.warning("File still locked, waiting longer...")
                time.sleep(0.5)  # Wait even longer
                try:
                    with open(wav_path, 'ab') as test_file:
                        pass
                except PermissionError:
                    QMessageBox.critical(None, "File Access Error",
                                       f"Cannot access audio file for volume changes.\n\n"
                                       f"The file may be locked by another process.\n"
                                       f"Try closing and reopening the Loop Editor.")
                    return False
            
            # Read original WAV file info first
            try:
                with wave.open(wav_path, 'rb') as original_wav:
                    channels = original_wav.getnchannels()
                    sample_width = original_wav.getsampwidth()
                    sample_rate = original_wav.getframerate()
            except Exception as e:
                logging.error(f"Error reading original WAV file info: {e}")
                return False
            
            # Convert adjusted audio data back to the original format
            adjusted_data = self.waveform.audio_data
            
            # Scale back to original bit depth
            if sample_width == 1:  # 8-bit
                # Convert from float32 [-1,1] to uint8 [0,255]
                audio_int = ((adjusted_data + 1.0) * 127.5).clip(0, 255).astype(np.uint8)
            elif sample_width == 2:  # 16-bit
                # Convert from float32 [-1,1] to int16 [-32768,32767]
                audio_int = (adjusted_data * 32767).clip(-32768, 32767).astype(np.int16)
            elif sample_width == 3:  # 24-bit
                # Convert from float32 [-1,1] to int32, then extract 24 bits
                audio_int32 = (adjusted_data * 2147483647).clip(-2147483648, 2147483647).astype(np.int32)
                # Convert to bytes and extract middle 3 bytes (24-bit)
                audio_bytes = audio_int32.view(np.uint8).reshape(-1, 4)
                audio_int = audio_bytes[:, 1:4].flatten()  # Take bytes 1-3 (24-bit portion)
            elif sample_width == 4:  # 32-bit
                # Convert from float32 [-1,1] to int32
                audio_int = (adjusted_data * 2147483647).clip(-2147483648, 2147483647).astype(np.int32)
            else:
                logging.error(f"Unsupported sample width: {sample_width}")
                return False
            
            # Handle stereo conversion if original was stereo
            if channels == 2:
                if sample_width == 3:
                    # For 24-bit, we already have bytes, need to handle differently
                    # audio_int is already flattened bytes, reshape for stereo duplication
                    mono_samples = len(audio_int) // 3
                    audio_24bit = audio_int.reshape(mono_samples, 3)
                    stereo_data = np.empty((mono_samples * 2, 3), dtype=np.uint8)
                    stereo_data[0::2] = audio_24bit  # Left channel
                    stereo_data[1::2] = audio_24bit  # Right channel (duplicate)
                    audio_int = stereo_data.flatten()
                else:
                    # Duplicate mono to stereo (interleave)
                    stereo_data = np.empty(len(audio_int) * 2, dtype=audio_int.dtype)
                    stereo_data[0::2] = audio_int  # Left channel
                    stereo_data[1::2] = audio_int  # Right channel (duplicate)
                    audio_int = stereo_data
            
            # Write new WAV file with proper error handling and retry
            # Use temporary file approach to avoid file locking issues
            import tempfile
            import shutil
            
            temp_wav_path = None
            try:
                # Create temporary file in the same directory
                temp_dir = os.path.dirname(wav_path)
                temp_fd, temp_wav_path = tempfile.mkstemp(suffix='.wav', dir=temp_dir)
                os.close(temp_fd)  # Close the file descriptor
                
                # Write to temporary file first
                with wave.open(temp_wav_path, 'wb') as wav_file:
                    wav_file.setnchannels(channels)
                    wav_file.setsampwidth(sample_width)
                    wav_file.setframerate(sample_rate)
                    wav_file.writeframes(audio_int.tobytes())
                
                # Now try to replace the original file
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        shutil.move(temp_wav_path, wav_path)
                        break  # Success
                    except PermissionError as e:
                        if attempt < max_retries - 1:
                            logging.warning(f"Permission denied replacing file on attempt {attempt + 1}, retrying...")
                            time.sleep(0.3)
                            continue
                        else:
                            logging.error(f"Permission denied replacing WAV file after {max_retries} attempts: {e}")
                            QMessageBox.critical(None, "File Access Error", 
                                               f"Cannot save volume changes: File is in use or write-protected.\n\n"
                                               f"Please ensure the file is not open in another application.\n"
                                               f"You may need to restart the application if the file remains locked.")
                            return False
                            
            except Exception as e:
                logging.error(f"Error writing WAV file: {e}")
                return False
            finally:
                # Clean up temporary file if it still exists
                if temp_wav_path and os.path.exists(temp_wav_path):
                    try:
                        os.remove(temp_wav_path)
                    except:
                        pass  # Ignore cleanup errors
            
            logging.info(f"Saved volume-adjusted audio to {wav_path}")
            
            # Reload media if it was playing
            if was_playing and wav_path:
                url = QUrl.fromLocalFile(wav_path)
                self.media_player.setMedia(QMediaContent(url))
                
            return True
            
        except Exception as e:
            logging.error(f"Error saving volume-adjusted audio: {e}")
            return False
    
    def _reload_media_after_volume_change(self):
        """Force reload media player after volume changes are saved"""
        try:
            wav_path = self.loop_manager.get_wav_path()
            if not wav_path:
                return
            
            # Clear current media to force reload
            self.media_player.setMedia(QMediaContent())
            
            # Wait a moment for the clear to take effect
            QTimer.singleShot(50, lambda: self._set_fresh_media(wav_path))
            
        except Exception as e:
            logging.error(f"Error reloading media after volume change: {e}")
    
    def _set_fresh_media(self, wav_path: str):
        """Set fresh media content after a brief delay"""
        try:
            url = QUrl.fromLocalFile(wav_path)
            self.media_player.setMedia(QMediaContent(url))
            logging.info("Media player reloaded with volume-adjusted audio")
        except Exception as e:
            logging.error(f"Error setting fresh media: {e}")
    
    def _force_media_refresh(self):
        """Force media player to reload for immediate volume change preview"""
        try:
            # Clear the media player cache by setting empty content then reloading
            self.media_player.stop()
            self.media_player.setMedia(QMediaContent())
            
            # Small delay then reload
            QTimer.singleShot(100, self._reload_current_media)
            
        except Exception as e:
            logging.error(f"Error forcing media refresh: {e}")
    
    def _reload_current_media(self):
        """Reload the current media file"""
        try:
            # Use temporary file if volume was adjusted, otherwise use original
            wav_path = self._get_playback_wav_path()
            if wav_path:
                url = QUrl.fromLocalFile(wav_path)
                self.media_player.setMedia(QMediaContent(url))
                logging.info(f"Forced media refresh after volume adjustment: {wav_path}")
        except Exception as e:
            logging.error(f"Error reloading current media: {e}")
    
    def _write_volume_to_wav_immediately(self) -> bool:
        """Write volume-adjusted audio to temporary file for immediate playback"""
        try:
            # Use the new temporary file approach instead of writing to original
            return self._write_volume_to_temp_file()
        except Exception as e:
            logging.error(f"Error writing volume to temp file immediately: {e}")
            return False
    
    def _create_temp_wav_file(self) -> str:
        """Create a temporary WAV file for volume adjustments"""
        try:
            import tempfile
            import shutil
            
            # Get original WAV path
            original_path = self.loop_manager.get_wav_path()
            if not original_path:
                raise ValueError("No original WAV path available")
            
            # Store original path if not already stored
            if not self._original_wav_path:
                self._original_wav_path = original_path
            
            # Create temporary file in system temp directory instead of project root
            temp_fd, temp_path = tempfile.mkstemp(suffix='_volume_temp.wav', prefix='scdplayer_')
            os.close(temp_fd)  # Close the file descriptor
            
            # Copy original file to temporary location
            shutil.copy2(original_path, temp_path)
            
            self._temp_wav_path = temp_path
            self._temp_file_created = True
            
            logging.info(f"Created temporary WAV file: {temp_path}")
            return temp_path
            
        except Exception as e:
            logging.error(f"Error creating temporary WAV file: {e}")
            return None
    
    def _write_volume_to_temp_file(self) -> bool:
        """Write volume-adjusted audio to temporary file for playback"""
        if not self._volume_adjusted or self.waveform.audio_data is None:
            return True  # Nothing to write
        
        try:
            # Create temp file if it doesn't exist
            if not self._temp_wav_path or not os.path.exists(self._temp_wav_path):
                temp_path = self._create_temp_wav_file()
                if not temp_path:
                    return False
                self._temp_wav_path = temp_path
            
            # Stop media player to release any handles on temp file
            was_playing = self.media_player.state() == QMediaPlayer.PlayingState
            self.media_player.stop()
            self.media_player.setMedia(QMediaContent())
            
            # Small delay to ensure file handle release
            import time
            time.sleep(0.1)
            
            # Read original WAV file info
            original_path = self._original_wav_path or self.loop_manager.get_wav_path()
            with wave.open(original_path, 'rb') as original_wav:
                channels = original_wav.getnchannels()
                sample_width = original_wav.getsampwidth()
                sample_rate = original_wav.getframerate()
            
            # Convert adjusted audio data back to the original format
            adjusted_data = self.waveform.audio_data
            
            # Scale back to original bit depth
            if sample_width == 1:  # 8-bit
                audio_int = ((adjusted_data + 1.0) * 127.5).clip(0, 255).astype(np.uint8)
            elif sample_width == 2:  # 16-bit
                audio_int = (adjusted_data * 32767).clip(-32768, 32767).astype(np.int16)
            elif sample_width == 3:  # 24-bit
                # Convert from float32 [-1,1] to int32, then extract 24 bits
                audio_int32 = (adjusted_data * 2147483647).clip(-2147483648, 2147483647).astype(np.int32)
                # Convert to bytes and extract middle 3 bytes (24-bit)
                audio_bytes = audio_int32.view(np.uint8).reshape(-1, 4)
                audio_int = audio_bytes[:, 1:4].flatten()  # Take bytes 1-3 (24-bit portion)
            elif sample_width == 4:  # 32-bit
                audio_int = (adjusted_data * 2147483647).clip(-2147483648, 2147483647).astype(np.int32)
            else:
                logging.error(f"Unsupported sample width: {sample_width}")
                return False
            
            # Handle stereo conversion if original was stereo
            if channels == 2:
                if sample_width == 3:
                    # For 24-bit, we already have bytes, need to handle differently
                    mono_samples = len(audio_int) // 3
                    audio_24bit = audio_int.reshape(mono_samples, 3)
                    stereo_data = np.empty((mono_samples * 2, 3), dtype=np.uint8)
                    stereo_data[0::2] = audio_24bit  # Left channel
                    stereo_data[1::2] = audio_24bit  # Right channel (duplicate)
                    audio_int = stereo_data.flatten()
                else:
                    stereo_data = np.empty(len(audio_int) * 2, dtype=audio_int.dtype)
                    stereo_data[0::2] = audio_int  # Left channel
                    stereo_data[1::2] = audio_int  # Right channel (duplicate)
                    audio_int = stereo_data
            
            # Write to temporary file
            with wave.open(self._temp_wav_path, 'wb') as wav_file:
                wav_file.setnchannels(channels)
                wav_file.setsampwidth(sample_width)
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio_int.tobytes())
            
            logging.info(f"Volume-adjusted audio written to temp file: {self._temp_wav_path}")
            
            # Reload media player with temp file if it was playing
            if was_playing:
                url = QUrl.fromLocalFile(self._temp_wav_path)
                self.media_player.setMedia(QMediaContent(url))
            
            return True
            
        except Exception as e:
            logging.error(f"Error writing volume to temp file: {e}")
            return False
    
    def _get_playback_wav_path(self) -> str:
        """Get the WAV path to use for playback (temp file if volume adjusted, original otherwise)"""
        if self._volume_adjusted and self._temp_wav_path and os.path.exists(self._temp_wav_path):
            return self._temp_wav_path
        return self.loop_manager.get_wav_path()
    
    def _cleanup_temp_files(self):
        """Clean up temporary files"""
        try:
            if self._temp_wav_path and os.path.exists(self._temp_wav_path):
                # Stop media player first
                self.media_player.stop()
                self.media_player.setMedia(QMediaContent())
                
                # Small delay to ensure file handle release
                import time
                time.sleep(0.1)
                
                # Remove temp file
                os.remove(self._temp_wav_path)
                logging.info(f"Cleaned up temporary file: {self._temp_wav_path}")
                
            self._temp_wav_path = None
            self._temp_file_created = False
            
        except Exception as e:
            logging.error(f"Error cleaning up temp files: {e}")
    
    def save_changes(self):
        """Save loop points and volume changes, then close"""
        start = self.start_spin.value()
        end = self.end_spin.value()
        
        logging.debug(f"Save changes - start: {start}, end: {end}")
        
        if end <= start and end > 0:
            QMessageBox.warning(self, "Invalid Loop", "Loop end must be greater than loop start")
            return
        
        # First, save volume-adjusted audio data if it was modified
        if self._volume_adjusted and self._temp_wav_path and os.path.exists(self._temp_wav_path):
            # Copy temporary file back to original location
            try:
                import shutil
                original_path = self._original_wav_path or self.loop_manager.get_wav_path()
                
                # Stop media player to release file handles
                self.media_player.stop()
                self.media_player.setMedia(QMediaContent())
                
                # Small delay to ensure file handle release
                import time
                time.sleep(0.2)
                
                # Copy temp file to original location
                shutil.copy2(self._temp_wav_path, original_path)
                logging.info(f"Volume-adjusted audio saved to original file: {original_path}")
                
            except Exception as e:
                logging.error(f"Error saving volume changes to original file: {e}")
                QMessageBox.warning(self, "Save Warning", 
                                  f"Could not save volume changes to original file.\n"
                                  f"Loop points will be saved, but volume changes may not persist.\n\n"
                                  f"Error: {str(e)}")
        
        # Save loop points to loop manager
        if end > start and end > 0:
            logging.debug(f"Saving loop points: {start} -> {end}")
            success = self.loop_manager.set_loop_points(start, end)
            if success:
                # Check if this is an SCD file that will need conversion
                if hasattr(self.loop_manager, 'original_scd_path') and self.loop_manager.original_scd_path:
                    # Show progress dialog for SCD conversion
                    self._save_with_progress()
                    return
                else:
                    # Save the actual loop data to file (WAV - quick operation)
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
    
    def _save_with_progress(self):
        """Save SCD file with progress dialog"""
        # Create progress dialog
        progress = QProgressDialog("Saving SCD", "Cancel", 0, 0, self)
        progress.setWindowTitle("Saving Audio File")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)  # Show immediately
        progress.setCancelButton(None)  # No cancel button - operation must complete
        progress.setRange(0, 0)  # Indeterminate progress
        progress.show()
        
        # Process events to show the dialog
        QApplication.processEvents()
        
        try:
            # Create a worker thread for the save operation
            worker = SaveWorker(self.loop_manager)
            worker.finished.connect(self._on_save_finished)
            worker.error.connect(self._on_save_error)
            
            # Keep reference to prevent garbage collection
            self._save_worker = worker
            self._progress_dialog = progress
            
            # Start the worker
            worker.start()
            
        except Exception as e:
            progress.close()
            logging.error(f"Error starting save operation: {e}")
            QMessageBox.critical(self, "Save Error", f"Failed to start save operation: {str(e)}")
    
    def _on_save_finished(self, success):
        """Handle save operation completion"""
        try:
            if hasattr(self, '_progress_dialog'):
                self._progress_dialog.close()
            
            if success:
                logging.info("SCD save operation completed successfully")
                # Stop playback and all timers before closing
                self.media_player.stop()
                self.position_timer.stop()
                self.loop_timer.stop()
                self.accept()
            else:
                QMessageBox.warning(self, "Error", "Failed to save loop points to SCD file")
                
        except Exception as e:
            logging.error(f"Error handling save completion: {e}")
        finally:
            # Clean up worker reference
            if hasattr(self, '_save_worker'):
                delattr(self, '_save_worker')
            if hasattr(self, '_progress_dialog'):
                delattr(self, '_progress_dialog')
    
    def _on_save_error(self, error_msg):
        """Handle save operation error"""
        try:
            if hasattr(self, '_progress_dialog'):
                self._progress_dialog.close()
            
            logging.error(f"Save operation failed: {error_msg}")
            QMessageBox.critical(self, "Save Error", f"Failed to save SCD file:\n{error_msg}")
            
        except Exception as e:
            logging.error(f"Error handling save error: {e}")
        finally:
            # Clean up worker reference
            if hasattr(self, '_save_worker'):
                delattr(self, '_save_worker')
            if hasattr(self, '_progress_dialog'):
                delattr(self, '_progress_dialog')
    
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
        # Use temporary file if volume was adjusted, otherwise use original
        wav_path = self._get_playback_wav_path()
        if not wav_path or not os.path.exists(wav_path):
            QMessageBox.warning(self, "Error", "No audio file available for playback")
            return

        # Get current cursor position from waveform first
        file_info = self.loop_manager.get_file_info()
        sample_rate = file_info.get('sample_rate', 44100)
        target_position_ms = 0
        
        if hasattr(self.waveform, 'current_position'):
            current_sample_pos = self.waveform.current_position
            target_position_ms = int((current_sample_pos / sample_rate) * 1000)

        # Only set media content if it's different or not set
        current_media = self.media_player.media()
        new_url = QUrl.fromLocalFile(wav_path)
        media_changed = (current_media.isNull() or 
                        current_media.canonicalUrl() != new_url)
        
        if media_changed:
            self.media_player.setMedia(QMediaContent(new_url))
            logging.info(f"Loaded media for playbook: {wav_path}")
            # Store target position for after playback starts
            self._target_position_ms = target_position_ms
        else:
            # Media already loaded, set position immediately
            self.media_player.setPosition(target_position_ms)
            self._target_position_ms = None
        
        # If loop mode is on and we're outside the loop, start from loop beginning
        if self.is_loop_testing:
            start = self.start_spin.value()
            end = self.end_spin.value()
            
            if start < end:  # Valid loop points
                start_ms = int((start / sample_rate) * 1000)
                end_ms = int((end / sample_rate) * 1000)
                
                # If current position is outside loop, start from loop beginning
                if target_position_ms < start_ms or target_position_ms >= end_ms:
                    if media_changed:
                        self._target_position_ms = start_ms
                    else:
                        self.media_player.setPosition(start_ms)

        self.media_player.play()
        
        # If we have a target position to set after media starts, do it with a short delay
        if hasattr(self, '_target_position_ms') and self._target_position_ms is not None:
            QTimer.singleShot(100, lambda: self._set_delayed_position(self._target_position_ms))
        
        # Start ultra-smooth position updates
        self.position_timer.start(8)  # ~120 FPS for ultra-smooth updates
        
        # Start loop timer if loop mode is enabled
        if self.is_loop_testing:
            self.loop_timer.start(16)  # ~60 FPS for smooth visual updates
            
    def _set_delayed_position(self, position_ms):
        """Set media position after a short delay to ensure media is ready"""
        if self.media_player.state() == QMediaPlayer.PlayingState:
            self.media_player.setPosition(position_ms)
            self._target_position_ms = None
            
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
    
    def toggle_follow_mode(self):
        """Toggle the auto-follow mode for the playback cursor"""
        if self.waveform.audio_data is None:
            return
        
        # Simple, robust toggle - works immediately regardless of playback state
        if self.waveform.is_focused_on_position:
            # Currently following, turn it off
            self.waveform.is_focused_on_position = False
        else:
            # Not following, turn it on and immediately center if cursor is visible
            self.waveform.is_focused_on_position = True
            # Center on current position to start following
            self._center_on_current_position()
        
        # Force visual update to show new state
        self.waveform.update()
    
    def focus_on_current_position(self):
        """Center the view on current position (legacy method - kept for compatibility)"""
        self._center_on_current_position()
    
    def _zoom_to_full_track(self):
        """Zoom out to show the entire track"""
        if self.waveform.audio_data is None:
            return
        
        # Set zoom to show the full track
        self.waveform.samples_per_pixel = max(1, self.waveform.total_samples / self.waveform.width())
        self.waveform.scroll_position = 0
        self.waveform.is_focused_on_position = False
        
        # Update display
        self.waveform.update()
        self.update_scrollbar_range()
        self.waveform_scroll.setValue(0)
    
    def _center_on_current_position(self):
        """Center the waveform view on the current playback position"""
        if not hasattr(self.waveform, 'current_position'):
            return
        
        current_sample = self.waveform.current_position
        
        # Calculate the scroll position to center the current position
        # We want the current position to be in the middle of the visible area
        visible_samples = self.waveform.width() * self.waveform.samples_per_pixel
        center_scroll_pos = (current_sample / self.waveform.samples_per_pixel) - (self.waveform.width() / 2)
        
        # Ensure scroll position is within valid bounds
        max_scroll = max(0, (self.waveform.total_samples / self.waveform.samples_per_pixel) - self.waveform.width())
        center_scroll_pos = max(0, min(center_scroll_pos, max_scroll))
        
        # Set flags to prevent focus state reset during this scroll
        self.waveform._setting_focus_scroll = True
        self.waveform._programmatic_scroll = True
        
        # Update the waveform scroll position
        self.waveform.set_scroll_position(center_scroll_pos)
        self.waveform.is_focused_on_position = True
        
        # Clear the flags
        if hasattr(self.waveform, '_setting_focus_scroll'):
            delattr(self.waveform, '_setting_focus_scroll')
        if hasattr(self.waveform, '_programmatic_scroll'):
            delattr(self.waveform, '_programmatic_scroll')
        
        # Update the scrollbar to match
        self.waveform_scroll.setValue(int(center_scroll_pos))
    
    def follow_playback_cursor(self, current_sample):
        """Auto-follow the playback cursor when in focused mode"""
        if not self.waveform.is_focused_on_position:
            return
        
        # Calculate current cursor position in pixels
        cursor_pixel = (current_sample / self.waveform.samples_per_pixel) - self.waveform.scroll_position
        
        # Check if cursor is getting close to the edges of the visible area
        width = self.waveform.width()
        margin = width * 0.25  # 25% margin on each side
        
        # If cursor is outside the comfortable viewing area, re-center
        if cursor_pixel < margin or cursor_pixel > (width - margin):
            # Throttle rapid re-centering but don't block the toggle functionality
            import time
            current_time = time.time() * 1000
            if current_time - self.waveform._last_follow_time < self.waveform._follow_cooldown:
                return  # Skip this scroll update but keep following enabled
            
            # Calculate new scroll position to center the cursor
            center_scroll_pos = (current_sample / self.waveform.samples_per_pixel) - (width / 2)
            
            # Ensure scroll position is within valid bounds
            max_scroll = max(0, (self.waveform.total_samples / self.waveform.samples_per_pixel) - width)
            center_scroll_pos = max(0, min(center_scroll_pos, max_scroll))
            
            # Set flags to prevent focus state reset during this scroll
            self.waveform._setting_focus_scroll = True
            self.waveform._programmatic_scroll = True
            
            # Use smooth scrolling to the new position
            self.waveform.smooth_scroll_to(center_scroll_pos)
            
            # Clear the flags
            if hasattr(self.waveform, '_setting_focus_scroll'):
                delattr(self.waveform, '_setting_focus_scroll')
            if hasattr(self.waveform, '_programmatic_scroll'):
                delattr(self.waveform, '_programmatic_scroll')
            
            # Update the last follow time
            self.waveform._last_follow_time = current_time
    
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
    
    def analyze_audio(self):
        """Analyze the current audio file for level information"""
        if self.waveform.audio_data is None or len(self.waveform.audio_data) == 0:
            self.analysis_text.setText("No audio data available for analysis")
            return
        
        try:
            # Initialize audio analyzer
            analyzer = AudioAnalyzer()
            
            # Analyze the audio
            levels = analyzer.analyze_audio_levels(
                self.waveform.audio_data, 
                self.waveform.sample_rate
            )
            
            # Get gain recommendations
            recommendations = analyzer.get_gain_recommendation(levels)
            
            # Format the results
            analysis_text = "=== AUDIO LEVEL ANALYSIS ===\n\n"
            
            # Display level information
            level_dict = levels.to_dict()
            for key, value in level_dict.items():
                analysis_text += f"{key:<15}: {value}\n"
            
            analysis_text += "\n=== RECOMMENDATIONS ===\n"
            
            if recommendations['recommendations']:
                for rec in recommendations['recommendations']:
                    icon = "⚠️" if rec['type'] == 'warning' else "❌" if rec['type'] == 'error' else "ℹ️"
                    analysis_text += f"\n{icon} {rec['message']}\n"
                    analysis_text += f"   → {rec['suggestion']}\n"
            else:
                analysis_text += "\n✅ Audio levels look good!"
            
            # Add file information
            file_info = self.loop_manager.get_file_info()
            duration_seconds = file_info.get('total_samples', 0) / file_info.get('sample_rate', 44100)
            
            analysis_text += f"\n=== FILE INFO ===\n"
            analysis_text += f"Sample Rate    : {file_info.get('sample_rate', 0)} Hz\n"
            analysis_text += f"Duration       : {self.format_time(duration_seconds)}\n"
            analysis_text += f"Total Samples  : {file_info.get('total_samples', 0):,}\n"
            
            # Display the results
            self.analysis_text.setText(analysis_text)
            
            logging.info(f"Audio analysis completed - Peak: {levels.peak_db:.1f}dB, RMS: {levels.rms_db:.1f}dB")
            
            # Enable volume adjustment buttons after analysis
            self.auto_volume_btn.setEnabled(True)
            self.normalize_peak_btn.setEnabled(True)
            self.normalize_rms_btn.setEnabled(True)
            self.custom_volume_btn.setEnabled(True)
            # Reset button only enabled if volume was adjusted
            self.reset_volume_btn.setEnabled(self._volume_adjusted)
            
        except Exception as e:
            logging.error(f"Error during audio analysis: {e}")
            self.analysis_text.setText(f"Error analyzing audio: {str(e)}")
    
    def auto_volume_adjustment(self):
        """Apply automatic volume adjustment targeting realistic game audio levels"""
        self._apply_volume_adjustment("auto")
    
    def normalize_peak(self):
        """Normalize audio to -0.2dB peak level (typical game audio)"""
        self._apply_volume_adjustment("peak")
    
    def normalize_rms(self):
        """Normalize audio to -15dB RMS level (game audio range)"""
        self._apply_volume_adjustment("rms")
    
    def custom_volume_adjustment(self):
        """Open custom volume adjustment dialog"""
        self._apply_volume_adjustment("custom")
    
    def reset_volume_adjustment(self):
        """Reset audio to original volume levels"""
        if not self._volume_adjusted or self._original_audio_data is None:
            return
        
        reply = QMessageBox.question(
            self,
            "Reset Volume",
            "Reset audio to original volume levels?\n\nThis will undo all volume adjustments.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Restore original audio data
            self.waveform.audio_data = self._original_audio_data.copy()
            self._volume_adjusted = False
            
            # Reset window title
            self.setWindowTitle("Loop Editor - Professional Audio Loop Point Editor")
            
            # Disable reset button
            self.reset_volume_btn.setEnabled(False)
            
            # Update waveform display
            self.waveform.update_waveform()
            self.waveform.update()
            
            # Re-analyze audio to show original levels
            QTimer.singleShot(100, self.analyze_audio)
            
            logging.info("Volume reset to original levels")
    
    def reset_volume_adjustment(self):
        """Reset audio to original volume levels"""
        if self._original_audio_data is None:
            QMessageBox.information(self, "No Changes", "No original audio data to restore")
            return
        
        reply = QMessageBox.question(
            self, 
            "Reset Volume", 
            "This will reset the audio to its original volume levels.\n\nContinue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        
        if reply == QMessageBox.Yes:
            # Restore original audio data
            self.waveform.audio_data = self._original_audio_data.copy()
            self._volume_adjusted = False
            
            # Reset window title
            self.setWindowTitle("Loop Editor - Professional Audio Loop Point Editor")
            
            # Update waveform display
            self.waveform.update_waveform()
            self.waveform.update()
            
            # Disable reset button
            self.reset_volume_btn.setEnabled(False)
            
            # Re-analyze audio
            QTimer.singleShot(100, self.analyze_audio)
            
            QMessageBox.information(self, "Volume Reset", "Audio volume has been reset to original levels.")
    
    def _apply_volume_adjustment(self, method: str):
        """Apply volume adjustment using the specified method"""
        if self.waveform.audio_data is None or len(self.waveform.audio_data) == 0:
            QMessageBox.warning(self, "No Audio", "No audio data available for volume adjustment")
            return
        
        try:
            # Initialize audio analyzer
            analyzer = AudioAnalyzer()
            
            # Analyze current audio before adjustment
            original_levels = analyzer.analyze_audio_levels(
                self.waveform.audio_data, 
                self.waveform.sample_rate
            )
            
            # Apply the appropriate normalization
            if method == "auto":
                adjustment = analyzer.auto_level_adjustment(self.waveform.audio_data)
            elif method == "peak":
                adjustment = analyzer.normalize_peak(self.waveform.audio_data, target_db=-0.2)
            elif method == "rms":
                adjustment = analyzer.normalize_rms(self.waveform.audio_data, target_db=-15.0)
            elif method == "custom":
                # Open custom volume dialog
                dialog = CustomVolumeDialog(original_levels, self)
                if dialog.exec_() != QDialog.Accepted:
                    return  # User cancelled
                
                settings = dialog.get_settings()
                if settings['method'] == 'peak':
                    adjustment = analyzer.normalize_peak(self.waveform.audio_data, target_db=settings['target_db'])
                else:  # RMS
                    adjustment = analyzer.normalize_rms(self.waveform.audio_data, target_db=settings['target_db'])
            else:
                raise ValueError(f"Unknown volume adjustment method: {method}")
            
            # Ask user for confirmation
            adjustment_info = adjustment.to_dict()
            
            message = f"Volume Adjustment Preview:\n\n"
            for key, value in adjustment_info.items():
                message += f"{key}: {value}\n"
            
            message += f"\nThis will modify the audio in memory only.\n"
            message += f"To save changes, you must export/save the file.\n\n"
            message += f"Continue with volume adjustment?"
            
            reply = QMessageBox.question(
                self, 
                "Confirm Volume Adjustment", 
                message,
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            
            if reply == QMessageBox.Yes:
                # Apply the adjustment
                self.waveform.audio_data = adjustment.adjusted_audio.copy()
                
                # Mark that volume has been adjusted
                self._volume_adjusted = True
                
                # Update window title to show volume was adjusted
                self.setWindowTitle("Loop Editor - Professional Audio Loop Point Editor (Volume Adjusted*)")
                
                # Enable reset button
                self.reset_volume_btn.setEnabled(True)
                
                # Immediately write volume changes to WAV file for playback
                if self._write_volume_to_wav_immediately():
                    logging.info("Volume changes written to WAV file for immediate playback")
                
                # Update the waveform display
                self.waveform.update_waveform()
                self.waveform.update()
                
                # Force media player to recognize volume changes for immediate playback
                self._force_media_refresh()
                
                # Run analysis again to show new levels
                QTimer.singleShot(100, self.analyze_audio)
                
                # Show success message
                success_msg = f"Volume adjustment applied successfully!\n\n"
                success_msg += f"Method: {adjustment.normalization_type}\n"
                success_msg += f"Gain Applied: {adjustment.gain_applied_db:+.1f} dB\n"
                if adjustment.clipping_prevented:
                    success_msg += f"Note: Gain was reduced to prevent clipping."
                
                QMessageBox.information(self, "Volume Adjusted", success_msg)
                
                logging.info(f"Volume adjustment applied: {adjustment.normalization_type}, "
                           f"Gain: {adjustment.gain_applied_db:+.1f}dB")
            
        except Exception as e:
            logging.error(f"Error during volume adjustment: {e}")
            QMessageBox.critical(self, "Volume Adjustment Error", 
                               f"Failed to adjust volume: {str(e)}")
    
    def _update_volume_buttons_state(self):
        """Update the enabled state of volume adjustment buttons"""
        has_audio = (self.waveform.audio_data is not None and 
                    len(self.waveform.audio_data) > 0)
        
        self.auto_volume_btn.setEnabled(has_audio)
        self.normalize_peak_btn.setEnabled(has_audio)
        self.normalize_rms_btn.setEnabled(has_audio)
        self.custom_volume_btn.setEnabled(has_audio)
        # Reset button only enabled if volume was adjusted
        self.reset_volume_btn.setEnabled(has_audio and self._volume_adjusted)
    
    def showEvent(self, event):
        """Handle dialog show event to ensure proper initialization"""
        super().showEvent(event)
        # Ensure waveform is properly initialized when dialog becomes visible
        if hasattr(self, 'waveform') and hasattr(self.waveform, 'audio_data'):
            QTimer.singleShot(50, self._finalize_waveform_setup)

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
