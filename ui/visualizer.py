"""Audio visualizers for SCDPlayer - retro and modern effects"""
import numpy as np
from PyQt5.QtWidgets import QWidget, QPushButton, QLabel
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QLinearGradient, QRadialGradient, QFont
import math


class AudioVisualizer(QWidget):
    """Base class for audio visualizers"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.audio_data = np.zeros(32)  # FFT data (reduced from 64)
        self.volume = 0.0
        self.position_ms = 0
        self.is_playing = False
        
    def update_audio_data(self, data, volume, position_ms, is_playing):
        """Update visualizer with new audio data"""
        self.audio_data = data
        self.volume = volume
        self.position_ms = position_ms
        self.is_playing = is_playing
        self.update()


class SpectrumBarsVisualizer(AudioVisualizer):
    """Classic spectrum analyzer bars (like Winamp)"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #000000;")
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w = self.width()
        h = self.height()
        
        num_bars = len(self.audio_data)
        bar_width = w / num_bars
        
        for i, value in enumerate(self.audio_data):
            # Color gradient from green -> yellow -> red
            if value < 0.5:
                color = QColor(0, int(255 * value * 2), 0)
            else:
                color = QColor(int(255 * (value - 0.5) * 2), 255, 0)
            
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            
            bar_height = value * h
            x = i * bar_width
            y = h - bar_height
            
            painter.drawRect(int(x), int(y), int(bar_width - 1), int(bar_height))


class OscilloscopeVisualizer(AudioVisualizer):
    """Oscilloscope waveform (retro green screen style)"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #001100;")
        self.waveform = np.zeros(100)
        
    def update_audio_data(self, data, volume, position_ms, is_playing):
        # Simulate waveform from spectrum data
        self.waveform = np.sin(np.linspace(0, 2 * np.pi * 3, 100)) * volume
        super().update_audio_data(data, volume, position_ms, is_playing)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w = self.width()
        h = self.height()
        
        # Green phosphor glow effect
        painter.setPen(QPen(QColor(0, 255, 0, 100), 3))
        
        points = []
        for i, value in enumerate(self.waveform):
            x = (i / len(self.waveform)) * w
            y = h / 2 + value * h * 0.4
            points.append((int(x), int(y)))
        
        # Draw waveform
        for i in range(len(points) - 1):
            painter.drawLine(points[i][0], points[i][1], points[i + 1][0], points[i + 1][1])


class CircularSpectrumVisualizer(AudioVisualizer):
    """Circular spectrum (modern style)"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #0a0a0a;")
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w = self.width()
        h = self.height()
        center_x = w / 2
        center_y = h / 2
        radius = min(w, h) / 3
        
        num_bars = len(self.audio_data)
        angle_step = 360 / num_bars
        
        for i, value in enumerate(self.audio_data):
            angle = math.radians(i * angle_step)
            
            # Cyan to magenta gradient
            hue = int((i / num_bars) * 180 + 180)  # Cyan to magenta range
            color = QColor.fromHsv(hue, 255, 255)
            painter.setPen(QPen(color, 2))
            
            bar_length = value * radius
            x1 = center_x + math.cos(angle) * radius
            y1 = center_y + math.sin(angle) * radius
            x2 = center_x + math.cos(angle) * (radius + bar_length)
            y2 = center_y + math.sin(angle) * (radius + bar_length)
            
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))


class VUMeterVisualizer(AudioVisualizer):
    """Classic VU meters"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #1a1a1a;")
        self.left_level = 0
        self.right_level = 0
        
    def update_audio_data(self, data, volume, position_ms, is_playing):
        # Split spectrum into left/right channels (simulated)
        mid = len(data) // 2
        self.left_level = np.mean(data[:mid])
        self.right_level = np.mean(data[mid:])
        super().update_audio_data(data, volume, position_ms, is_playing)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w = self.width()
        h = self.height()
        
        # Draw left channel VU meter
        self._draw_vu_meter(painter, 10, h * 0.25, w - 20, h * 0.15, self.left_level, "L")
        
        # Draw right channel VU meter
        self._draw_vu_meter(painter, 10, h * 0.6, w - 20, h * 0.15, self.right_level, "R")
        
    def _draw_vu_meter(self, painter, x, y, w, h, level, label):
        # Background
        painter.setBrush(QBrush(QColor(30, 30, 30)))
        painter.setPen(QPen(QColor(60, 60, 60), 1))
        painter.drawRect(int(x), int(y), int(w), int(h))
        
        # Level bar with gradient
        bar_width = w * level
        
        gradient = QLinearGradient(x, 0, x + w, 0)
        gradient.setColorAt(0, QColor(0, 255, 0))
        gradient.setColorAt(0.7, QColor(255, 255, 0))
        gradient.setColorAt(1, QColor(255, 0, 0))
        
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.NoPen)
        painter.drawRect(int(x), int(y), int(bar_width), int(h))
        
        # Label
        painter.setPen(QPen(QColor(200, 200, 200)))
        painter.drawText(int(x + 5), int(y - 5), label)


class WaveformVisualizer(AudioVisualizer):
    """Symmetric waveform (like SoundCloud)"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #0f0f0f;")
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w = self.width()
        h = self.height()
        center_y = h / 2
        
        num_bars = len(self.audio_data)
        bar_width = w / num_bars
        
        # Orange gradient
        gradient = QLinearGradient(0, 0, 0, h)
        gradient.setColorAt(0, QColor(255, 140, 0, 200))
        gradient.setColorAt(1, QColor(255, 80, 0, 200))
        
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.NoPen)
        
        for i, value in enumerate(self.audio_data):
            bar_height = value * h * 0.4
            x = i * bar_width
            
            # Draw symmetrical bars from center
            painter.drawRect(int(x), int(center_y - bar_height), int(bar_width - 1), int(bar_height * 2))


class ParticleVisualizer(AudioVisualizer):
    """Particle burst effect (modern)"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #000000;")
        self.particles = []
        
    def update_audio_data(self, data, volume, position_ms, is_playing):
        # Generate particles based on audio intensity
        if is_playing and volume > 0.1:
            for _ in range(int(volume * 5)):
                angle = np.random.rand() * 2 * np.pi
                speed = np.random.rand() * volume * 3
                self.particles.append({
                    'x': self.width() / 2,
                    'y': self.height() / 2,
                    'vx': math.cos(angle) * speed,
                    'vy': math.sin(angle) * speed,
                    'life': 1.0,
                    'color': QColor.fromHsv(int(np.random.rand() * 360), 255, 255)
                })
        
        # Update particles
        self.particles = [p for p in self.particles if p['life'] > 0]
        for p in self.particles:
            p['x'] += p['vx']
            p['y'] += p['vy']
            p['life'] -= 0.02
            
        super().update_audio_data(data, volume, position_ms, is_playing)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        for p in self.particles:
            color = p['color']
            color.setAlphaF(p['life'])
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            
            size = p['life'] * 4
            painter.drawEllipse(int(p['x'] - size/2), int(p['y'] - size/2), int(size), int(size))


class RetroPlasmaVisualizer(AudioVisualizer):
    """Retro plasma effect (demo scene style)"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #000000;")
        self.time = 0
        
    def update_audio_data(self, data, volume, position_ms, is_playing):
        if is_playing:
            self.time += 0.05 * (1 + volume)
        super().update_audio_data(data, volume, position_ms, is_playing)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        
        w = self.width()
        h = self.height()
        
        # Low-res plasma for performance
        step = 8
        
        for x in range(0, w, step):
            for y in range(0, h, step):
                # Plasma formula
                value = math.sin(x / 16.0 + self.time)
                value += math.sin(y / 8.0 - self.time)
                value += math.sin((x + y) / 16.0)
                value += math.sin(math.sqrt(x * x + y * y) / 8.0 + self.time)
                value = (value + 4) / 8  # Normalize to 0-1
                
                # Color based on plasma value and audio
                hue = int((value + self.volume) * 360) % 360
                color = QColor.fromHsv(hue, 255, int(200 + 55 * self.volume))
                
                painter.fillRect(x, y, step, step, color)


class VisualizerWidget(QWidget):
    """Container widget for visualizers with toggle button and navigation arrows"""
    
    visualizer_changed = pyqtSignal(str)  # Emits visualizer name
    
    VISUALIZERS = [
        ("Off", None),
        ("Spectrum Bars", SpectrumBarsVisualizer),
        ("Oscilloscope", OscilloscopeVisualizer),
        ("Circular Spectrum", CircularSpectrumVisualizer),
        ("VU Meters", VUMeterVisualizer),
        ("Waveform", WaveformVisualizer),
        ("Particles", ParticleVisualizer),
        ("Retro Plasma", RetroPlasmaVisualizer),
    ]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_index = 0
        self.current_visualizer = None
        self.is_visible = False
        
        # Set transparent background
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setStyleSheet("background-color: transparent;")
        
        # Toggle button (on/off)
        self.toggle_button = QPushButton("▶", self)
        self.toggle_button.setFixedSize(30, 30)
        self.toggle_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(13, 115, 119, 150);
                color: #14ffec;
                border: 2px solid #0d7377;
                border-radius: 5px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(13, 115, 119, 200);
                border: 2px solid #14ffec;
            }
            QPushButton:pressed {
                background-color: rgba(10, 95, 99, 200);
            }
        """)
        self.toggle_button.setToolTip("Show/Hide Visualizer")
        self.toggle_button.clicked.connect(self.toggle_visibility)
        
        # Previous button (navigate visualizers)
        self.prev_button = QPushButton("◀", self)
        self.prev_button.setFixedSize(30, 30)
        self.prev_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(13, 115, 119, 150);
                color: #14ffec;
                border: 2px solid #0d7377;
                border-radius: 5px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(13, 115, 119, 200);
                border: 2px solid #14ffec;
            }
            QPushButton:pressed {
                background-color: rgba(10, 95, 99, 200);
            }
        """)
        self.prev_button.setToolTip("Previous Visualizer")
        self.prev_button.clicked.connect(self.previous_visualizer)
        self.prev_button.hide()  # Hidden by default
        
        # Next button (navigate visualizers)
        self.next_button = QPushButton("▶", self)
        self.next_button.setFixedSize(30, 30)
        self.next_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(13, 115, 119, 150);
                color: #14ffec;
                border: 2px solid #0d7377;
                border-radius: 5px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(13, 115, 119, 200);
                border: 2px solid #14ffec;
            }
            QPushButton:pressed {
                background-color: rgba(10, 95, 99, 200);
            }
        """)
        self.next_button.setToolTip("Next Visualizer")
        self.next_button.clicked.connect(self.next_visualizer)
        self.next_button.hide()  # Hidden by default
        
        # Name label (shows visualizer name when changed)
        self.name_label = QLabel(self)
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 0, 0, 180);
                color: #14ffec;
                border: 2px solid #0d7377;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 16px;
                font-weight: bold;
            }
        """)
        self.name_label.hide()
        
        # Timer to hide name label
        self.name_timer = QTimer()
        self.name_timer.setSingleShot(True)
        self.name_timer.timeout.connect(self.hide_name_label)
        
        # Update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_visualizer)
        self.update_timer.start(33)  # ~30 FPS
        
        # Set minimum size and initial size
        self.setMinimumSize(450, 350)
        self.resize(450, 350)
        
    def toggle_visibility(self):
        """Toggle visualizer visibility"""
        self.is_visible = not self.is_visible
        
        if self.is_visible:
            # Show visualizer
            self.toggle_button.setText("◼")
            self.toggle_button.setToolTip("Hide Visualizer")
            if self.current_index == 0:  # If "Off", switch to first visualizer
                self.current_index = 1
            self.switch_visualizer(self.current_index)
        else:
            # Hide visualizer
            self.toggle_button.setText("▶")
            self.toggle_button.setToolTip("Show Visualizer")
            if self.current_visualizer:
                self.current_visualizer.hide()
            self.prev_button.hide()
            self.next_button.hide()
    
    def previous_visualizer(self):
        """Switch to previous visualizer"""
        # Skip "Off" when navigating
        self.current_index -= 1
        if self.current_index <= 0:
            self.current_index = len(self.VISUALIZERS) - 1
        self.switch_visualizer(self.current_index)
    
    def next_visualizer(self):
        """Switch to next visualizer"""
        # Skip "Off" when navigating
        self.current_index += 1
        if self.current_index >= len(self.VISUALIZERS):
            self.current_index = 1
        self.switch_visualizer(self.current_index)
    
    def switch_visualizer(self, index):
        """Switch to specific visualizer"""
        self.current_index = index
        name, viz_class = self.VISUALIZERS[self.current_index]
        
        # Remove old visualizer
        if self.current_visualizer:
            self.current_visualizer.setParent(None)
            self.current_visualizer.deleteLater()
            self.current_visualizer = None
        
        # Create new visualizer
        if viz_class:
            self.current_visualizer = viz_class(self)
            self.current_visualizer.setGeometry(0, 0, self.width(), self.height())
            self.current_visualizer.show()
            self.current_visualizer.lower()  # Put behind buttons
        
        # Show name briefly
        self.show_visualizer_name(name)
        
        # Raise all controls
        self.toggle_button.raise_()
        self.prev_button.raise_()
        self.next_button.raise_()
        self.name_label.raise_()
        
        self.visualizer_changed.emit(name)
    
    def show_visualizer_name(self, name):
        """Show visualizer name for 2 seconds"""
        self.name_label.setText(name)
        
        # Center the label
        self.name_label.adjustSize()
        x = (self.width() - self.name_label.width()) // 2
        y = (self.height() - self.name_label.height()) // 2
        self.name_label.move(x, y)
        
        self.name_label.show()
        self.name_label.raise_()
        
        # Hide after 2 seconds
        self.name_timer.stop()
        self.name_timer.start(2000)
    
    def hide_name_label(self):
        """Hide the name label"""
        self.name_label.hide()
    
    def enterEvent(self, event):
        """Show navigation arrows on hover"""
        if self.is_visible:
            self.prev_button.show()
            self.next_button.show()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Hide navigation arrows when mouse leaves"""
        self.prev_button.hide()
        self.next_button.hide()
        super().leaveEvent(event)
        
    def resizeEvent(self, event):
        """Keep visualizer and buttons sized correctly"""
        if self.current_visualizer:
            self.current_visualizer.setGeometry(0, 0, self.width(), self.height())
        
        # Position buttons in bottom-left corner
        self.toggle_button.move(5, self.height() - 35)
        self.prev_button.move(40, self.height() - 35)
        self.next_button.move(75, self.height() - 35)
        
        # Reposition name label if visible
        if self.name_label.isVisible():
            x = (self.width() - self.name_label.width()) // 2
            y = (self.height() - self.name_label.height()) // 2
            self.name_label.move(x, y)
        
    def update_visualizer(self):
        """Update visualizer with audio data"""
        if self.current_visualizer and self.is_visible and hasattr(self, 'audio_callback'):
            # Get real audio analysis
            data, volume, position, playing = self.audio_callback()
            self.current_visualizer.update_audio_data(data, volume, position, playing)
        elif self.current_visualizer and self.is_visible:
            # Dummy data for testing
            data = np.random.rand(32) * 0.5
            self.current_visualizer.update_audio_data(data, 0.3, 0, False)
    
    def set_audio_callback(self, callback):
        """Set callback to get real-time audio data"""
        self.audio_callback = callback

