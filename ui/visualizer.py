"""Audio visualizers for SCDToolkit - retro and modern effects"""
import numpy as np
from PyQt5.QtWidgets import QWidget, QPushButton, QLabel
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QLinearGradient, QRadialGradient, QFont
import math


class AudioVisualizer(QWidget):
    """Base class for audio visualizers"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.audio_data = np.zeros(64)  # FFT data (now 64 bars)
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

    def update_audio_data(self, data, volume, position_ms, is_playing):
        super().update_audio_data(data, volume, position_ms, is_playing)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()

        legend_height = 24  # Space for Hz legend
        bar_area_height = h - legend_height

        num_bars = len(self.audio_data)
        bar_width = w / num_bars

        # Draw bars
        for i, value in enumerate(self.audio_data):
            # Always green unless peaking, transition to yellow at 80%, red at 95%+
            if value >= 0.95:
                color = QColor(255, 0, 0)  # Red
            elif value >= 0.8:
                t = (value - 0.8) / 0.15
                t = min(max(t, 0.0), 1.0)
                r = 255
                g = int(255 * (1 - t))
                b = 0
                color = QColor(r, g, b)
            else:
                t = value / 0.8
                t = min(max(t, 0.0), 1.0)
                r = int(255 * t)
                g = 255
                b = 0
                color = QColor(r, g, b)

            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)

            bar_height = value * bar_area_height
            x = i * bar_width
            y = bar_area_height - bar_height

            painter.drawRect(int(x), int(y), int(bar_width - 1), int(bar_height))

        # Draw Hz legend below bars
        painter.setPen(QPen(QColor(180, 255, 180), 1))
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)

        # Frequencies to label (log scale, musically relevant)
        freq_labels = [20, 100, 250, 500, 1000, 2500, 5000, 10000, 20000]
        # Get bar positions for these frequencies using Mel scale math
        def hz_to_mel(hz):
            return 2595 * np.log10(1 + hz / 700)
        def mel_to_hz(mel):
            return 700 * (10**(mel / 2595) - 1)
        sample_rate = 44100  # Assume standard, or could be passed in
        nyquist = sample_rate / 2
        min_hz = 0
        max_hz = nyquist
        min_mel = hz_to_mel(min_hz)
        max_mel = hz_to_mel(max_hz)
        mel_points = np.linspace(min_mel, max_mel, num_bars + 1)
        hz_points = mel_to_hz(mel_points)

        for freq in freq_labels:
            # Find the closest bar edge to this frequency
            idx = np.argmin(np.abs(hz_points - freq))
            x = int(idx * bar_width)
            label = f"{freq//1000}k" if freq >= 1000 else str(freq)
            if freq == 1000:
                label = "1k"
            # Draw tick
            painter.drawLine(x, bar_area_height, x, bar_area_height + 6)
            # Draw label
            painter.drawText(x - 12, bar_area_height + 18, 24, 12, Qt.AlignCenter, label)


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

    def update_audio_data(self, data, volume, position_ms, is_playing):
        super().update_audio_data(data, volume, position_ms, is_playing)
        
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


class WaveformVisualizer(AudioVisualizer):
    """Symmetric waveform (like SoundCloud)"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #0f0f0f;")

    def update_audio_data(self, data, volume, position_ms, is_playing):
        super().update_audio_data(data, volume, position_ms, is_playing)
        
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
        # Generate particles based on audio intensity (more responsive)
        if is_playing and volume > 0.05:
            # More particles with better volume scaling
            num_particles = int(volume * 10) + 2  # At least 2 particles, up to 12
            for _ in range(num_particles):
                angle = np.random.rand() * 2 * np.pi
                speed = (np.random.rand() * 0.5 + 0.5) * volume * 5  # Faster particles
                self.particles.append({
                    'x': self.width() / 2,
                    'y': self.height() / 2,
                    'vx': math.cos(angle) * speed,
                    'vy': math.sin(angle) * speed,
                    'life': 1.0,
                    'color': QColor.fromHsv(int(np.random.rand() * 360), 255, 255)
                })
        
        # Update particles - remove dead ones immediately
        self.particles = [p for p in self.particles if p['life'] > 0.01]  # Small threshold
        for p in self.particles:
            p['x'] += p['vx']
            p['y'] += p['vy']
            p['life'] -= 0.025  # Slightly faster decay
            
        super().update_audio_data(data, volume, position_ms, is_playing)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        for p in self.particles:
            color = p['color']
            # Clamp alpha to valid range [0.0, 1.0] to avoid negative values
            alpha = max(0.0, min(1.0, p['life']))
            color.setAlphaF(alpha)
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            
            size = alpha * 6  # Slightly larger particles
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
        ("Circular Spectrum", CircularSpectrumVisualizer),
        ("Waveform", WaveformVisualizer),
        ("Particles", ParticleVisualizer),
        ("Retro Plasma", RetroPlasmaVisualizer),
    ]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_index = 0
        self.current_visualizer = None
        self.is_visible = False
        
        # Set background with border
        self.setStyleSheet("""
            QWidget {
                background-color: #1a1a1a;
                border: 2px solid #404040;
                border-radius: 8px;
            }
        """)
        
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
        self.prev_button.hide()  # Hidden until visualizer is active
        
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
        self.next_button.hide()  # Hidden until visualizer is active
        
        # Name label (shows current visualizer name, always visible when active)
        self.name_label = QLabel("Off", self)
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setStyleSheet("""
            QLabel {
                background-color: rgba(13, 115, 119, 150);
                color: #14ffec;
                border: 2px solid #0d7377;
                border-radius: 5px;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: bold;
            }
        """)
        self.name_label.hide()  # Hidden until visualizer is active
        
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
            # Show arrow buttons and name label
            self.prev_button.show()
            self.next_button.show()
            self.name_label.show()
        else:
            # Hide visualizer
            self.toggle_button.setText("▶")
            self.toggle_button.setToolTip("Show Visualizer")
            if self.current_visualizer:
                self.current_visualizer.hide()
            self.prev_button.hide()
            self.next_button.hide()
            self.name_label.hide()
    
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
            # Leave 40px at bottom for buttons, with padding for border
            button_bar_height = 40
            visualizer_height = self.height() - button_bar_height
            self.current_visualizer.setGeometry(4, 4, self.width() - 8, visualizer_height - 8)
            self.current_visualizer.show()
            self.current_visualizer.lower()  # Put behind buttons
        
        # Update name label
        self.name_label.setText(name)
        self.name_label.adjustSize()
        
        # Raise all controls
        self.toggle_button.raise_()
        self.prev_button.raise_()
        self.next_button.raise_()
        self.name_label.raise_()
        
        self.visualizer_changed.emit(name)
    
    def resizeEvent(self, event):
        """Keep visualizer and buttons sized correctly"""
        # Leave 40px at the bottom for buttons
        button_bar_height = 40
        visualizer_height = self.height() - button_bar_height
        
        if self.current_visualizer:
            # Visualizer takes up space minus button bar, with padding for border
            self.current_visualizer.setGeometry(4, 4, self.width() - 8, visualizer_height - 8)
        
        # Position buttons at the bottom, centered
        button_y = self.height() - button_bar_height + 5
        self.toggle_button.move(5, button_y)
        self.prev_button.move(40, button_y)
        self.next_button.move(75, button_y)
        
        # Position name label next to the next button
        self.name_label.move(110, button_y + 3)  # Slight vertical adjustment for alignment
        
    def update_visualizer(self):
        """Update visualizer with audio data"""
        if self.current_visualizer and self.is_visible and hasattr(self, 'audio_callback'):
            # Get real audio analysis
            data, volume, position, playing = self.audio_callback()
            self.current_visualizer.update_audio_data(data, volume, position, playing)
        elif self.current_visualizer and self.is_visible:
            # Dummy data for testing
            data = np.random.rand(64) * 0.5
            self.current_visualizer.update_audio_data(data, 0.3, 0, False)
    
    def set_audio_callback(self, callback):
        """Set callback to get real-time audio data"""
        self.audio_callback = callback

