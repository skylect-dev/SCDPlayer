import logging
import wave
import numpy as np
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QRect
from PyQt5.QtGui import QPainter, QColor, QPen
from PyQt5.QtWidgets import QWidget, QSizePolicy


class WaveformWidget(QWidget):
    """High-performance waveform display widget"""

    positionChanged = pyqtSignal(int)  # Sample position
    loopPointChanged = pyqtSignal(int, int)  # start, end samples
    trimPointChanged = pyqtSignal(int, int)  # start, end samples

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
        self.trim_region_color = QColor(0, 170, 255, 25)
        self.trim_start_color = QColor(0, 200, 255)
        self.trim_end_color = QColor(0, 120, 255)
        self.cursor_color = QColor(0, 50, 255)

        # Mouse tracking
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        # Track if initial zoom has been calculated
        self._initial_zoom_set = False

        # Trim mode state
        self.mode = 'loop'  # 'loop' or 'trim'
        self.trim_start = 0
        self.trim_end = 0
        self.dragging_trim_start = False
        self.dragging_trim_end = False

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
                    audio_bytes = np.frombuffer(raw_data, dtype=np.uint8)
                    num_samples = len(audio_bytes) // (3 * channels)
                    audio_bytes = audio_bytes.reshape(num_samples * channels, 3)
                    audio_int32 = np.zeros((len(audio_bytes), 4), dtype=np.uint8)
                    audio_int32[:, 1:4] = audio_bytes
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
                    audio_array = audio_array[::2]

                # Normalize to float
                if dtype == np.uint8:
                    audio_array = (audio_array.astype(np.float32) - 128) / 128.0
                elif dtype == np.int16:
                    audio_array = audio_array.astype(np.float32) / 32768.0
                elif dtype == np.int32:
                    if sample_width == 3:
                        audio_array = audio_array.astype(np.float32) / 2147483648.0
                    else:
                        audio_array = audio_array.astype(np.float32) / 2147483648.0

                self.audio_data = audio_array
                self.sample_rate = sample_rate
                self.total_samples = len(audio_array)

                if self.width() > 0:
                    self.samples_per_pixel = max(1, len(audio_array) / self.width())
                    self._initial_zoom_set = True
                else:
                    self._initial_zoom_set = False

                self.update()
                logging.info(f"Loaded audio: {frames} samples, {sample_rate}Hz, {channels}ch")
                return True

        except Exception as e:
            logging.error(f"Failed to load audio data: {e}")
            return False

    def set_loop_points(self, start: int, end: int):
        self.loop_start = max(0, min(start, self.total_samples))
        self.loop_end = max(0, min(end, self.total_samples))
        self.update()

    def set_trim_points(self, start: int, end: int):
        self.trim_start = max(0, min(start, self.total_samples))
        self.trim_end = max(self.trim_start + 1, min(end, self.total_samples)) if self.total_samples else 0
        self.update()

    def reset_trim_points(self):
        self.trim_start = 0
        self.trim_end = self.total_samples
        self.update()

    def set_mode(self, mode: str):
        if mode in ('loop', 'trim'):
            self.mode = mode
            self.update()

    def set_current_position(self, position: int):
        self.current_position = max(0, min(position, self.total_samples))
        if self.is_focused_on_position and self.follow_callback:
            self.follow_callback(self.current_position)
        self.update()

    def smooth_scroll_to(self, target_position):
        import time
        if abs(target_position - self.scroll_position) < 5:
            return
        self._smooth_scroll_start = self.scroll_position
        self._smooth_scroll_target = target_position
        self._smooth_scroll_start_time = time.time() * 1000
        self._smooth_scroll_timer.start(16)

    def _update_smooth_scroll(self):
        import time
        current_time = time.time() * 1000
        elapsed = current_time - self._smooth_scroll_start_time
        if elapsed >= self._smooth_scroll_duration:
            self._smooth_scroll_timer.stop()
            self.scroll_position = self._smooth_scroll_target
            self.update()
            if hasattr(self, 'parent') and hasattr(self.parent(), 'waveform_scroll'):
                parent_dialog = self
                while parent_dialog and not hasattr(parent_dialog, 'waveform_scroll'):
                    parent_dialog = parent_dialog.parent()
                if parent_dialog and hasattr(parent_dialog, 'waveform_scroll'):
                    parent_dialog.waveform_scroll.setValue(int(self.scroll_position))
        else:
            progress = elapsed / self._smooth_scroll_duration
            progress = 1 - pow(1 - progress, 3)
            self.scroll_position = self._smooth_scroll_start + (self._smooth_scroll_target - self._smooth_scroll_start) * progress
            self.update()

    def set_scroll_position(self, scroll_pos):
        if self._smooth_scroll_timer.isActive():
            self._smooth_scroll_timer.stop()
        self.scroll_position = scroll_pos
        if not hasattr(self, '_setting_focus_scroll') and not hasattr(self, '_programmatic_scroll'):
            self.is_focused_on_position = False
        self.update()
        if self.scrollChanged:
            self.scrollChanged(self.scroll_position, self.zoom_factor, self.samples_per_pixel)

    def get_scroll_info(self):
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
        if self.audio_data is not None:
            self.total_samples = len(self.audio_data)
            if self.width() > 0:
                if self.samples_per_pixel <= 0 or not self._initial_zoom_set:
                    self.samples_per_pixel = max(1, self.total_samples / self.width())
                    self._initial_zoom_set = True
                visible_samples = self.width() * self.samples_per_pixel
                max_scroll = max(0, self.total_samples - visible_samples) // self.samples_per_pixel
                self.scroll_position = min(self.scroll_position, max_scroll)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), self.background_color)
        if self.audio_data is None:
            painter.setPen(Qt.white)
            painter.drawText(self.rect(), Qt.AlignCenter, "No audio loaded")
            return
        width = self.width()
        height = self.height()
        start_sample = int(self.scroll_position * self.samples_per_pixel)
        end_sample = int((self.scroll_position + width) * self.samples_per_pixel)
        end_sample = min(end_sample, self.total_samples)
        if start_sample >= end_sample:
            return
        if self.mode == 'trim' and self.trim_end > self.trim_start:
            trim_start_x = self.sample_to_pixel(self.trim_start)
            trim_end_x = self.sample_to_pixel(self.trim_end)
            if trim_end_x > 0 and trim_start_x < width:
                trim_rect = QRect(max(0, trim_start_x), 0, min(width, trim_end_x) - max(0, trim_start_x), height)
                painter.fillRect(trim_rect, self.trim_region_color)
        if self.loop_end > self.loop_start > 0:
            loop_start_x = self.sample_to_pixel(self.loop_start)
            loop_end_x = self.sample_to_pixel(self.loop_end)
            if loop_end_x > 0 and loop_start_x < width:
                loop_rect = QRect(max(0, loop_start_x), 0, min(width, loop_end_x) - max(0, loop_start_x), height)
                painter.fillRect(loop_rect, self.loop_region_color)
        painter.setPen(QPen(self.waveform_color, 1))
        samples_to_draw = end_sample - start_sample
        for x in range(width):
            sample_start = start_sample + int(x * self.samples_per_pixel)
            sample_end = start_sample + int((x + 1) * self.samples_per_pixel)
            sample_end = min(sample_end, len(self.audio_data))
            if sample_start >= len(self.audio_data):
                break
            if sample_end <= sample_start:
                sample_end = sample_start + 1
            chunk = self.audio_data[sample_start:sample_end]
            if len(chunk) > 0:
                min_val = float(np.min(chunk))
                max_val = float(np.max(chunk))
                rms_val = float(np.sqrt(np.mean(chunk ** 2)))
                y_center = height // 2
                scale_factor = 0.9
                y_min = int(y_center - min_val * y_center * scale_factor)
                y_max = int(y_center - max_val * y_center * scale_factor)
                y_rms_pos = int(y_center - rms_val * y_center * scale_factor)
                y_rms_neg = int(y_center + rms_val * y_center * scale_factor)
                y_min = max(0, min(height - 1, y_min))
                y_max = max(0, min(height - 1, y_max))
                y_rms_pos = max(0, min(height - 1, y_rms_pos))
                y_rms_neg = max(0, min(height - 1, y_rms_neg))
                if y_max != y_min:
                    painter.setPen(QPen(self.waveform_color, 1))
                    painter.drawLine(x, y_max, x, y_min)
                if len(chunk) > 10:
                    rms_color = QColor(self.waveform_color)
                    rms_color.setAlpha(180)
                    painter.setPen(QPen(rms_color, 1))
                    if y_rms_pos != y_rms_neg:
                        painter.drawLine(x, y_rms_pos, x, y_rms_neg)
                else:
                    avg_val = float(np.mean(chunk))
                    y_avg = int(y_center - avg_val * y_center * scale_factor)
                    y_avg = max(0, min(height - 1, y_avg))
                    painter.setPen(QPen(self.waveform_color, 1))
                    painter.drawPoint(x, y_avg)
        if self.loop_start >= 0:
            start_x = self.sample_to_pixel(self.loop_start)
            if -5 <= start_x <= width + 5:
                painter.setPen(QPen(self.loop_start_color, 2))
                painter.drawLine(start_x, 0, start_x, height)
                painter.setPen(Qt.white)
                painter.drawText(max(2, start_x + 5), 15, "Loop Start")
        if self.loop_end > self.loop_start:
            end_x = self.sample_to_pixel(self.loop_end)
            if -5 <= end_x <= width + 5:
                painter.setPen(QPen(self.loop_end_color, 2))
                painter.drawLine(end_x, 0, end_x, height)
                painter.setPen(Qt.white)
                painter.drawText(max(2, end_x + 5), 30, "Loop End")
        if self.mode == 'trim' and self.trim_start >= 0:
            ts_x = self.sample_to_pixel(self.trim_start)
            if -5 <= ts_x <= width + 5:
                painter.setPen(QPen(self.trim_start_color, 2, Qt.DashLine))
                painter.drawLine(ts_x, 0, ts_x, height)
                painter.setPen(Qt.white)
                painter.drawText(max(2, ts_x + 5), 45, "Trim Start")
        if self.mode == 'trim' and self.trim_end > self.trim_start:
            te_x = self.sample_to_pixel(self.trim_end)
            if -5 <= te_x <= width + 5:
                painter.setPen(QPen(self.trim_end_color, 2, Qt.DashLine))
                painter.drawLine(te_x, 0, te_x, height)
                painter.setPen(Qt.white)
                painter.drawText(max(2, te_x + 5), 60, "Trim End")
        if self.loop_start >= 0 and self.loop_end > self.loop_start:
            start_x = max(0, self.sample_to_pixel(self.loop_start))
            end_x = min(width, self.sample_to_pixel(self.loop_end))
            if start_x < end_x:
                painter.fillRect(int(start_x), 0, int(end_x - start_x), height, QColor(255, 255, 0, 30))
        if self.current_position >= 0:
            cursor_x = self.sample_to_pixel(self.current_position)
            if -2 <= cursor_x <= width + 2:
                painter.setPen(QPen(self.cursor_color, 2))
                painter.drawLine(cursor_x, 0, cursor_x, height)
        self._draw_focus_icon(painter, width, height)

    def _draw_focus_icon(self, painter, width, height):
        icon_size = 20
        margin = 8
        icon_x = width - icon_size - margin
        icon_y = margin
        self.focus_icon_rect = QRect(icon_x, icon_y, icon_size, icon_size)
        if self.is_focused_on_position:
            if self.focus_icon_hovered:
                bg_color = QColor(100, 150, 255, 220)
                icon_color = QColor(255, 255, 255)
            else:
                bg_color = QColor(70, 120, 255, 180)
                icon_color = QColor(255, 255, 255)
        else:
            if self.focus_icon_hovered:
                bg_color = QColor(80, 80, 80, 200)
                icon_color = QColor(255, 255, 255)
            else:
                bg_color = QColor(50, 50, 50, 150)
                icon_color = QColor(200, 200, 200)
        painter.setPen(Qt.NoPen)
        painter.setBrush(bg_color)
        painter.drawEllipse(self.focus_icon_rect)
        painter.setPen(QPen(icon_color, 2))
        center_x = icon_x + icon_size // 2
        center_y = icon_y + icon_size // 2
        painter.drawLine(center_x - 6, center_y, center_x + 6, center_y)
        painter.drawLine(center_x, center_y - 6, center_x, center_y + 6)
        painter.setPen(QPen(icon_color, 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(center_x - 2, center_y - 2, 4, 4)

    def sample_to_pixel(self, sample: int) -> int:
        return int((sample / self.samples_per_pixel) - self.scroll_position)

    def pixel_to_sample(self, pixel: int) -> int:
        return int((pixel + self.scroll_position) * self.samples_per_pixel)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.audio_data is not None:
            if self.focus_icon_rect.contains(event.pos()):
                if self.focus_callback:
                    self.focus_callback()
                return
            sample_pos = self.pixel_to_sample(event.x())
            start_x = self.sample_to_pixel(self.loop_start)
            end_x = self.sample_to_pixel(self.loop_end)
            cursor_x = self.sample_to_pixel(self.current_position)
            trim_start_x = self.sample_to_pixel(self.trim_start)
            trim_end_x = self.sample_to_pixel(self.trim_end)
            self.fine_control = event.modifiers() & Qt.ControlModifier
            if self.mode == 'trim':
                if abs(event.x() - trim_start_x) < 6 and self.trim_start >= 0:
                    self.dragging_trim_start = True
                    self._drag_start_x = event.x()
                    self._fine_base_trim_start = self.trim_start
                    self.setCursor(Qt.SizeHorCursor)
                    return
                elif abs(event.x() - trim_end_x) < 6 and self.trim_end > self.trim_start:
                    self.dragging_trim_end = True
                    self._drag_start_x = event.x()
                    self._fine_base_trim_end = self.trim_end
                    self.setCursor(Qt.SizeHorCursor)
                    return
            if self.mode == 'loop':
                if abs(event.x() - start_x) < 6 and self.loop_start >= 0:
                    self.dragging_start = True
                    self._drag_start_x = event.x()
                    self._fine_base_start = self.loop_start
                    self.setCursor(Qt.SizeHorCursor)
                    return
                elif abs(event.x() - end_x) < 6 and self.loop_end > self.loop_start:
                    self.dragging_end = True
                    self._drag_start_x = event.x()
                    self._fine_base_end = self.loop_end
                    self.setCursor(Qt.SizeHorCursor)
                    return
            if abs(event.x() - cursor_x) < 6:
                self.dragging_cursor = True
                self._drag_start_x = event.x()
                self._fine_base_cursor = self.current_position
                self.setCursor(Qt.SizeHorCursor)
            else:
                self.current_position = max(0, min(sample_pos, self.total_samples))
                self.positionChanged.emit(self.current_position)
                self.update()

    def mouseMoveEvent(self, event):
        if self.audio_data is None:
            return
        sample_pos = self.pixel_to_sample(event.x())
        current_fine_control = event.modifiers() & Qt.ControlModifier
        if self.dragging_trim_start:
            if current_fine_control != self.fine_control:
                self.fine_control = current_fine_control
                self._ctrl_toggle_reference = self.trim_start
            if self.fine_control:
                base_pos = getattr(self, '_ctrl_toggle_reference', getattr(self, '_fine_base_trim_start', self.trim_start)) or self.trim_start
                self._ctrl_toggle_reference = None
                fine_step = max(1, self.samples_per_pixel // 20)
                delta = (event.x() - getattr(self, '_drag_start_x', event.x())) * fine_step
                self.trim_start = max(0, min(int(base_pos + delta), self.trim_end - 1))
                self._fine_base_trim_start = base_pos
            else:
                self.trim_start = max(0, min(sample_pos, self.trim_end - 1))
            self.trim_start = min(self.trim_start, self.trim_end - 1)
            self.update()
            self.trimPointChanged.emit(self.trim_start, self.trim_end)
        elif self.dragging_trim_end:
            if current_fine_control != self.fine_control:
                self.fine_control = current_fine_control
                self._ctrl_toggle_reference = self.trim_end
            if self.fine_control:
                base_pos = getattr(self, '_ctrl_toggle_reference', getattr(self, '_fine_base_trim_end', self.trim_end)) or self.trim_end
                self._ctrl_toggle_reference = None
                fine_step = max(1, self.samples_per_pixel // 20)
                delta = (event.x() - getattr(self, '_drag_start_x', event.x())) * fine_step
                self.trim_end = max(self.trim_start + 1, min(int(base_pos + delta), self.total_samples))
                self._fine_base_trim_end = base_pos
            else:
                self.trim_end = max(self.trim_start + 1, min(sample_pos, self.total_samples))
            self.update()
            self.trimPointChanged.emit(self.trim_start, self.trim_end)
        elif self.dragging_start:
            if current_fine_control != self.fine_control:
                self.fine_control = current_fine_control
                self._ctrl_toggle_reference = self.loop_start
            if self.fine_control:
                if hasattr(self, '_ctrl_toggle_reference') and self._ctrl_toggle_reference is not None:
                    base_pos = self._ctrl_toggle_reference
                    self._ctrl_toggle_reference = None
                else:
                    base_pos = getattr(self, '_fine_base_start', self.loop_start)
                    if base_pos is None:
                        base_pos = self.loop_start
                fine_step = max(1, self.samples_per_pixel // 20)
                delta = (event.x() - getattr(self, '_drag_start_x', event.x())) * fine_step
                self.loop_start = max(0, min(int(base_pos + delta), self.loop_end - 1))
                self._fine_base_start = base_pos
            else:
                self.loop_start = max(0, min(sample_pos, self.loop_end - 1))
            self.loopPointChanged.emit(self.loop_start, self.loop_end)
            self.update()
        elif self.dragging_end:
            if current_fine_control != self.fine_control:
                self.fine_control = current_fine_control
                self._ctrl_toggle_reference = self.loop_end
            if self.fine_control:
                if hasattr(self, '_ctrl_toggle_reference') and self._ctrl_toggle_reference is not None:
                    base_pos = self._ctrl_toggle_reference
                    self._ctrl_toggle_reference = None
                else:
                    base_pos = getattr(self, '_fine_base_end', self.loop_end)
                    if base_pos is None:
                        base_pos = self.loop_end
                fine_step = max(1, self.samples_per_pixel // 20)
                delta = (event.x() - getattr(self, '_drag_start_x', event.x())) * fine_step
                self.loop_end = max(self.loop_start + 1, min(int(base_pos + delta), self.total_samples))
                self._fine_base_end = base_pos
            else:
                self.loop_end = max(self.loop_start + 1, min(sample_pos, self.total_samples))
            self.loopPointChanged.emit(self.loop_start, self.loop_end)
            self.update()
        elif self.dragging_cursor:
            if current_fine_control != self.fine_control:
                self.fine_control = current_fine_control
                self._ctrl_toggle_reference = self.current_position
            if self.fine_control:
                if hasattr(self, '_ctrl_toggle_reference') and self._ctrl_toggle_reference is not None:
                    base_pos = self._ctrl_toggle_reference
                    self._ctrl_toggle_reference = None
                else:
                    base_pos = getattr(self, '_fine_base_cursor', self.current_position)
                    if base_pos is None:
                        base_pos = self.current_position
                fine_step = max(1, self.samples_per_pixel // 20)
                delta = (event.x() - getattr(self, '_drag_start_x', event.x())) * fine_step
                self.current_position = max(0, min(int(base_pos + delta), self.total_samples))
                self._fine_base_cursor = base_pos
            else:
                self.current_position = max(0, min(sample_pos, self.total_samples))
            self.positionChanged.emit(self.current_position)
            self.update()
        else:
            start_x = self.sample_to_pixel(self.loop_start)
            end_x = self.sample_to_pixel(self.loop_end)
            cursor_x = self.sample_to_pixel(self.current_position)
            trim_start_x = self.sample_to_pixel(self.trim_start)
            trim_end_x = self.sample_to_pixel(self.trim_end)
            if self.mode == 'trim':
                if (abs(event.x() - trim_start_x) < 6 and self.trim_start >= 0) or \
                   (abs(event.x() - trim_end_x) < 6 and self.trim_end > self.trim_start) or \
                   abs(event.x() - cursor_x) < 6:
                    self.setCursor(Qt.SizeHorCursor)
                else:
                    self.setCursor(Qt.ArrowCursor)
            else:
                if (abs(event.x() - start_x) < 6 and self.loop_start >= 0) or \
                   (abs(event.x() - end_x) < 6 and self.loop_end > self.loop_start) or \
                   abs(event.x() - cursor_x) < 6:
                    self.setCursor(Qt.SizeHorCursor)
                else:
                    self.setCursor(Qt.ArrowCursor)
        was_hovered = self.focus_icon_hovered
        self.focus_icon_hovered = self.focus_icon_rect.contains(event.pos())
        if was_hovered != self.focus_icon_hovered:
            self.update()
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
        if event.button() == Qt.LeftButton:
            self.dragging_start = False
            self.dragging_end = False
            self.dragging_cursor = False
            self.dragging_trim_start = False
            self.dragging_trim_end = False
            self._ctrl_toggle_reference = None
            for attr in [
                '_fine_base_start', '_fine_base_end', '_fine_base_cursor',
                '_fine_base_trim_start', '_fine_base_trim_end', '_drag_start_x'
            ]:
                if hasattr(self, attr):
                    delattr(self, attr)
            self.setCursor(Qt.ArrowCursor)

    def wheelEvent(self, event):
        if self.audio_data is None:
            return
        mouse_x = event.x()
        mouse_sample_before = self.pixel_to_sample(mouse_x)
        zoom_factor = 1.2 if event.angleDelta().y() > 0 else 1/1.2
        old_samples_per_pixel = self.samples_per_pixel
        new_samples_per_pixel = self.samples_per_pixel / zoom_factor
        max_samples_per_pixel = max(1, self.total_samples / self.width())
        min_samples_per_pixel = 1.0
        new_samples_per_pixel = max(min_samples_per_pixel, min(new_samples_per_pixel, max_samples_per_pixel))
        if abs(new_samples_per_pixel - old_samples_per_pixel) < 0.1:
            return
        self.samples_per_pixel = new_samples_per_pixel
        mouse_sample_after = self.pixel_to_sample(mouse_x)
        sample_diff = mouse_sample_before - mouse_sample_after
        pixel_diff = sample_diff / self.samples_per_pixel
        self._programmatic_scroll = True
        self.scroll_position += pixel_diff
        max_scroll = max(0, (self.total_samples / self.samples_per_pixel) - self.width())
        self.scroll_position = max(0, min(self.scroll_position, max_scroll))
        delattr(self, '_programmatic_scroll')
        self.update()
        if self.zoomChanged:
            self.zoomChanged()
        if self.scrollChanged:
            self.scrollChanged(self.scroll_position, self.zoom_factor, self.samples_per_pixel)

    def keyPressEvent(self, event):
        if self.audio_data is None:
            super().keyPressEvent(event)
            return
        if event.key() == Qt.Key_S:
            self.loop_start = self.current_position
            if self.loop_end <= self.loop_start:
                self.loop_end = self.total_samples
            self.loopPointChanged.emit(self.loop_start, self.loop_end)
            self.update()
        elif event.key() == Qt.Key_E:
            self.loop_end = self.current_position
            if self.loop_start >= self.loop_end:
                self.loop_start = 0
            self.loopPointChanged.emit(self.loop_start, self.loop_end)
            self.update()
        elif event.key() == Qt.Key_C:
            self.loop_start = 0
            self.loop_end = 0
            self.loopPointChanged.emit(0, 0)
            self.update()
        else:
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
        self.sample_rate = sample_rate
        self.total_samples = total_samples
        self.update()

    def set_view_params(self, scroll_position: float, zoom_factor: float, samples_per_pixel: float):
        self.samples_per_pixel = samples_per_pixel
        self.scroll_position = scroll_position
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(40, 40, 40))
        if self.total_samples == 0:
            return
        width = self.width()
        visible_duration = width * self.samples_per_pixel / self.sample_rate
        if visible_duration < 10:
            interval = 1
        elif visible_duration < 60:
            interval = 5
        elif visible_duration < 300:
            interval = 30
        else:
            interval = 60
        painter.setPen(Qt.white)
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)
        start_time = self.scroll_position * self.samples_per_pixel / self.sample_rate
        start_interval = int(start_time / interval) * interval
        for i in range(20):
            time_sec = start_interval + i * interval
            sample_pos = time_sec * self.sample_rate
            if sample_pos > self.total_samples:
                break
            x = int((sample_pos / self.samples_per_pixel) - self.scroll_position)
            if x > width:
                break
            if x >= 0:
                painter.drawLine(x, 20, x, 30)
                if time_sec >= 60:
                    time_str = f"{int(time_sec // 60)}:{int(time_sec % 60):02d}"
                else:
                    time_str = f"{time_sec:.1f}s"
                painter.drawText(x + 2, 15, time_str)
